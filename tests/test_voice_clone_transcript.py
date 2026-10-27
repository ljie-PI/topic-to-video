"""Tests for voice-clone.py's transcript contract, driven through its command line.

Contract (issue #105): when the run needs a transcript (``--emit-transcript``,
or a backend that ``always_emits_transcript``), voice-clone either produces a
FRESH transcript at the target path or fails:

* any pre-existing file at the target path is deleted before synthesis;
* the backend's own direct aligner runs first (``transcript_method`` =
  ``direct_align``); when it writes nothing, ``transcribe.py`` runs as a
  subprocess (``transcript_method`` = ``asr``);
* when both fail: exit 1, the mp3 is kept, and the JSON error carries
  ``transcript_attempts``.

Every test uses the ``fake`` backends (``--backend fake``, ``ASR_BACKEND=fake``)
so the whole path runs without any model. ffmpeg / ffprobe are required.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cli_helpers import parse_stdout, run_cli

REPO_ROOT = Path(__file__).resolve().parent.parent
VOICE_CLONE = REPO_ROOT / 'scripts' / 'voice-clone.py'

# Input env vars that must not leak from the host into a test run.
_ENV_BLACKLIST_PREFIXES = ('TTS_', 'ASR_', 'ALIGN', 'QWEN3', 'DASHSCOPE_', 'COSYVOICE_')

NARRATION = '大家好。今天我们来聊聊视频制作。'  # 15 non-whitespace characters


def run_voice_clone(
    *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    return run_cli(
        VOICE_CLONE, *args, env=env or {},
        blocked_prefixes=_ENV_BLACKLIST_PREFIXES, timeout=120,
    )


def synthesize(tmp_path: Path, *extra: str, env: dict[str, str] | None = None):
    """One fake-backend run: narration.txt -> out/narration.mp3 + tr/transcript.json."""
    narration = tmp_path / 'narration.txt'
    narration.write_text(NARRATION, encoding='utf-8')
    return run_voice_clone(
        '--backend', 'fake',
        '--input-file', str(narration),
        '--output-dir', str(tmp_path / 'out'),
        '--transcript-output', str(tmp_path / 'tr' / 'transcript.json'),
        '--emit-transcript',
        *extra,
        env=env,
    )


@pytest.mark.usefixtures('require_ffmpeg')
def test_fake_backend_direct_align_succeeds_without_asr(tmp_path: Path):
    proc = synthesize(tmp_path)

    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['success'] is True
    assert result['backend'] == 'fake'
    assert result['transcript_method'] == 'direct_align'
    assert result['output_path'] == str((tmp_path / 'out' / 'narration.mp3').resolve())
    assert (tmp_path / 'out' / 'narration.mp3').stat().st_size > 0
    # 15 non-whitespace characters / 7.5 per second (punctuation counts).
    assert result['duration_s'] == pytest.approx(15 / 7.5, abs=0.15)

    transcript_file = tmp_path / 'tr' / 'transcript.json'
    assert result['transcript_path'] == str(transcript_file.resolve())
    transcript = json.loads(transcript_file.read_text(encoding='utf-8'))
    assert [sentence['text'] for sentence in transcript] == ['大家好。', '今天我们来聊聊视频制作。']
    words = [word for sentence in transcript for word in sentence['words']]
    assert ''.join(word['text'] for word in words) == NARRATION
    # Even spread over the whole audio: starts at 0, no gaps.
    assert words[0]['begin'] == 0
    assert all(a['end'] == b['begin'] for a, b in zip(words, words[1:]))
    assert words[-1]['end'] == pytest.approx(result['duration_s'] * 1000, abs=2)


@pytest.mark.usefixtures('require_ffmpeg')
def test_failed_direct_align_falls_back_to_asr(tmp_path: Path):
    # The fake ASR returns ASR_FAKE_TEXT, which differs from the narration, so
    # the transcript content proves it came from the transcribe.py subprocess.
    proc = synthesize(
        tmp_path,
        env={
            'TTS_FAKE_ALIGN_FAIL': '1',
            'ASR_BACKEND': 'fake',
            'ASR_FAKE_TEXT': '这是识别出来的文字。',
        },
    )

    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['success'] is True
    assert result['transcript_method'] == 'asr'
    transcript_file = tmp_path / 'tr' / 'transcript.json'
    assert result['transcript_path'] == str(transcript_file.resolve())
    transcript = json.loads(transcript_file.read_text(encoding='utf-8'))
    assert [sentence['text'] for sentence in transcript] == ['这是识别出来的文字。']
    assert 'transcript_attempts' not in result


# No ASR can run: not CUDA, no DashScope key (the env blacklist drops it).
NO_ASR_ENV = {
    'ASR_DETECT_PLATFORM': 'linux',
    'ASR_DETECT_MACHINE': 'x86_64',
    'ASR_DETECT_CUDA': '0',
}


@pytest.mark.usefixtures('require_ffmpeg')
def test_both_paths_failing_exits_1_with_attempts_and_keeps_the_mp3(tmp_path: Path):
    proc = synthesize(tmp_path, env={'TTS_FAKE_ALIGN_FAIL': '1', **NO_ASR_ENV})

    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert result['error']
    mp3 = tmp_path / 'out' / 'narration.mp3'
    assert mp3.stat().st_size > 0
    assert result['output_path'] == str(mp3.resolve())
    direct, asr = result['transcript_attempts']
    assert direct['method'] == 'direct_align'
    assert 'TTS_FAKE_ALIGN_FAIL' in direct['error']
    assert asr['method'] == 'asr'
    assert 'no usable ASR backend' in asr['error']
    assert not (tmp_path / 'tr' / 'transcript.json').exists()


@pytest.mark.usefixtures('require_ffmpeg')
def test_stale_transcript_does_not_survive_a_failed_run(tmp_path: Path):
    stale = tmp_path / 'tr' / 'transcript.json'
    stale.parent.mkdir(parents=True)
    stale.write_text(
        json.dumps([{'begin': 0, 'end': 999, 'text': '旧的。', 'words': [
            {'text': '旧', 'begin': 0, 'end': 500},
            {'text': '的', 'begin': 500, 'end': 999},
        ]}], ensure_ascii=False),
        encoding='utf-8',
    )

    proc = synthesize(tmp_path, env={'TTS_FAKE_ALIGN_FAIL': '1', **NO_ASR_ENV})

    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert 'transcript_path' not in result
    assert not stale.exists()


@pytest.mark.usefixtures('require_ffmpeg')
def test_stale_transcript_is_removed_before_synthesis_even_if_synthesis_fails(tmp_path: Path):
    stale = tmp_path / 'tr' / 'transcript.json'
    stale.parent.mkdir(parents=True)
    stale.write_text('[]', encoding='utf-8')

    proc = synthesize(tmp_path, env={'FFMPEG_BIN': str(tmp_path / 'no-such-ffmpeg')})

    assert proc.returncode == 1
    assert parse_stdout(proc)['success'] is False
    assert not stale.exists()


@pytest.fixture
def dashscope_env(tmp_path: Path, require_ffmpeg) -> dict[str, str]:
    """Env that makes ``--backend dashscope`` synthesize a silent mp3 offline.

    A stand-in ``dashscope`` package on PYTHONPATH returns the bytes of a
    pre-made mp3 from ``SpeechSynthesizer.call``, as the real service would.
    """
    audio = tmp_path / 'cosyvoice.mp3'
    subprocess.run(
        [
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', '2',
            '-c:a', 'libmp3lame', str(audio),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    tts_package = tmp_path / 'fake_package' / 'dashscope' / 'audio'
    tts_package.mkdir(parents=True)
    (tmp_path / 'fake_package' / 'dashscope' / '__init__.py').write_text('', encoding='utf-8')
    (tts_package / '__init__.py').write_text('', encoding='utf-8')
    (tts_package / 'tts_v2.py').write_text(
        'import os\n'
        'from pathlib import Path\n'
        'class SpeechSynthesizer:\n'
        '    def __init__(self, **kwargs):\n'
        '        pass\n'
        '    def call(self, text):\n'
        "        return Path(os.environ['FAKE_DASHSCOPE_AUDIO']).read_bytes()\n"
        '    def get_last_request_id(self):\n'
        "        return 'test-request'\n"
        '    def get_first_package_delay(self):\n'
        '        return 0\n',
        encoding='utf-8',
    )
    return {
        'DASHSCOPE_API_KEY': 'test-key',
        'COSYVOICE_VOICE_ID': 'test-voice',
        'FAKE_DASHSCOPE_AUDIO': str(audio),
        'PYTHONPATH': str(tmp_path / 'fake_package'),
    }


def synthesize_dashscope(tmp_path: Path, *extra: str, env: dict[str, str]):
    narration = tmp_path / 'narration.txt'
    narration.write_text(NARRATION, encoding='utf-8')
    return run_voice_clone(
        '--backend', 'dashscope',
        '--input-file', str(narration),
        '--output-dir', str(tmp_path / 'out'),
        '--transcript-output', str(tmp_path / 'tr' / 'transcript.json'),
        *extra,
        env=env,
    )


def test_run_without_transcript_request_deletes_the_stale_file_and_reports_none(
    tmp_path: Path, dashscope_env: dict[str, str]
):
    stale = tmp_path / 'tr' / 'transcript.json'
    stale.parent.mkdir(parents=True)
    stale.write_text('[]', encoding='utf-8')

    proc = synthesize_dashscope(tmp_path, env=dashscope_env)

    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['success'] is True
    assert 'transcript_path' not in result
    assert 'transcript_method' not in result
    assert not stale.exists()


def test_backend_without_aligner_goes_straight_to_asr_when_a_transcript_is_requested(
    tmp_path: Path, dashscope_env: dict[str, str]
):
    proc = synthesize_dashscope(
        tmp_path,
        '--emit-transcript',
        env={**dashscope_env, 'ASR_BACKEND': 'fake', 'ASR_FAKE_TEXT': NARRATION},
    )

    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['transcript_method'] == 'asr'
    assert result['transcript_path'] == str((tmp_path / 'tr' / 'transcript.json').resolve())


def test_backend_without_aligner_reports_the_asr_attempt_when_asr_is_unavailable(
    tmp_path: Path, dashscope_env: dict[str, str]
):
    # No direct aligner exists for dashscope, so no fake direct_align attempt
    # is recorded: the attempts list holds the ASR failure only.
    proc = synthesize_dashscope(
        tmp_path,
        '--emit-transcript',
        env={**dashscope_env, 'ASR_BACKEND': 'fake'},
    )

    assert proc.returncode == 1
    result = parse_stdout(proc)
    (asr,) = result['transcript_attempts']
    assert asr['method'] == 'asr'
    assert 'ASR_FAKE_TEXT' in asr['error']
    assert (tmp_path / 'out' / 'narration.mp3').stat().st_size > 0


def test_help_marks_fake_as_test_only():
    proc = run_voice_clone('--help')

    assert proc.returncode == 0
    assert 'fake' in proc.stdout
    assert '测试用' in proc.stdout
    assert 'transcript_attempts' in proc.stdout  # the backend docs live in --help


# --- the capability contract holds without any transcript flags -------------


@pytest.mark.usefixtures('require_ffmpeg')
def test_always_backend_emits_at_the_default_path_without_any_flags(tmp_path: Path):
    # mlx's guarantee — "a run produces a transcript, flag or not" — rests on
    # wants_transcript() returning True for always-emits backends; this pins it.
    narration = tmp_path / 'narration.txt'
    narration.write_text(NARRATION, encoding='utf-8')

    proc = run_voice_clone(
        '--backend', 'fake',
        '--input-file', str(narration),
        '--output-dir', str(tmp_path / 'out'),
    )

    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['transcript_method'] == 'direct_align'
    transcript = tmp_path / 'out' / 'transcript.json'
    assert result['transcript_path'] == str(transcript.resolve())
    assert transcript.is_file()


@pytest.mark.usefixtures('require_ffmpeg')
def test_asr_fallback_hits_the_default_path_without_flags(tmp_path: Path):
    narration = tmp_path / 'narration.txt'
    narration.write_text(NARRATION, encoding='utf-8')

    proc = run_voice_clone(
        '--backend', 'fake',
        '--input-file', str(narration),
        '--output-dir', str(tmp_path / 'out'),
        env={'TTS_FAKE_ALIGN_FAIL': '1', 'ASR_BACKEND': 'fake', 'ASR_FAKE_TEXT': NARRATION},
    )

    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['transcript_method'] == 'asr'
    assert result['transcript_path'] == str((tmp_path / 'out' / 'transcript.json').resolve())


# --- ASR subprocess stdout parsing and success guards, through the CLI -------


def fake_asr_process_env(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """Fake third-party imports and transcribe-child process side effects."""
    root = tmp_path / 'asr_process_fakes'
    (root / 'torch').mkdir(parents=True)
    (root / 'qwen_asr').mkdir()
    (root / 'torch' / '__init__.py').write_text(
        "float16 = 'float16'\nfloat32 = 'float32'\n"
        'class cuda:\n'
        '    @staticmethod\n'
        '    def is_available():\n'
        '        return False\n',
        encoding='utf-8',
    )
    (root / 'sitecustomize.py').write_text(
        'import atexit\n'
        'import os\n'
        'import sys\n'
        'from pathlib import Path\n'
        "if Path(sys.argv[0]).name == 'transcribe.py':\n"
        "    if os.environ.get('FAKE_TRANSCRIBE_STRAY_STDOUT') == '1':\n"
        "        print('stray sdk log line')\n"
        "    if os.environ.get('FAKE_TRANSCRIBE_DELETE_OUTPUT') == '1':\n"
        '        atexit.register(lambda: Path(sys.argv[2]).unlink(missing_ok=True))\n',
        encoding='utf-8',
    )
    return root, {'PYTHONPATH': str(root), 'TTS_FAKE_ALIGN_FAIL': '1'}


def asr_failure(result: dict) -> dict:
    direct, asr = result['transcript_attempts']
    assert direct['method'] == 'direct_align'
    assert asr['method'] == 'asr'
    return asr


@pytest.mark.usefixtures('require_ffmpeg')
def test_asr_cli_failure_uses_its_json_result_and_stderr_tail(tmp_path: Path):
    root, env = fake_asr_process_env(tmp_path)
    (root / 'qwen_asr' / '__init__.py').write_text(
        'import sys\n'
        "print('stray sdk log line')\n"
        "print('traceback\\nboom', file=sys.stderr)\n"
        "raise RuntimeError('model blew up')\n",
        encoding='utf-8',
    )

    proc = synthesize(tmp_path, env={**env, 'ASR_BACKEND': 'qwen3'})

    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    error = asr_failure(result)['error']
    assert 'model blew up' in error
    assert 'stderr: traceback\nboom' in error
    assert not (tmp_path / 'tr' / 'transcript.json').exists()
    assert (tmp_path / 'out' / 'narration.mp3').is_file()


@pytest.mark.usefixtures('require_ffmpeg')
def test_asr_cli_accepts_stray_stdout_before_a_successful_result(tmp_path: Path):
    _root, env = fake_asr_process_env(tmp_path)

    proc = synthesize(
        tmp_path,
        env={
            **env,
            'ASR_BACKEND': 'fake',
            'ASR_FAKE_TEXT': '识别成功。',
            'FAKE_TRANSCRIBE_STRAY_STDOUT': '1',
        },
    )

    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['success'] is True
    assert result['transcript_method'] == 'asr'
    transcript = json.loads((tmp_path / 'tr' / 'transcript.json').read_text(encoding='utf-8'))
    assert [sentence['text'] for sentence in transcript] == ['识别成功。']


@pytest.mark.usefixtures('require_ffmpeg')
def test_asr_cli_success_without_sentences_is_a_public_failure(tmp_path: Path):
    root, env = fake_asr_process_env(tmp_path)
    (root / 'qwen_asr' / '__init__.py').write_text(
        'from types import SimpleNamespace\n'
        'class Qwen3ASRModel:\n'
        '    @staticmethod\n'
        '    def from_pretrained(*args, **kwargs):\n'
        '        return Qwen3ASRModel()\n'
        '    def transcribe(self, audio, language, return_time_stamps):\n'
        "        return [SimpleNamespace(text='', time_stamps=None)]\n",
        encoding='utf-8',
    )

    proc = synthesize(tmp_path, env={**env, 'ASR_BACKEND': 'qwen3'})

    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert 'reported success but wrote no sentences' in asr_failure(result)['error']
    assert not (tmp_path / 'tr' / 'transcript.json').exists()
    assert (tmp_path / 'out' / 'narration.mp3').is_file()


@pytest.mark.usefixtures('require_ffmpeg')
def test_asr_cli_success_without_a_transcript_file_is_a_public_failure(tmp_path: Path):
    _root, env = fake_asr_process_env(tmp_path)

    proc = synthesize(
        tmp_path,
        env={
            **env,
            'ASR_BACKEND': 'fake',
            'ASR_FAKE_TEXT': NARRATION,
            'FAKE_TRANSCRIBE_DELETE_OUTPUT': '1',
        },
    )

    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert 'reported success but wrote no sentences' in asr_failure(result)['error']
    assert not (tmp_path / 'tr' / 'transcript.json').exists()
    assert (tmp_path / 'out' / 'narration.mp3').is_file()
