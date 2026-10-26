"""Tests for voice-clone.py's transcript contract, driven through its command line.

Contract (issue #105): when the run needs a transcript (``--emit-transcript``,
or a backend whose ``transcript_capability`` is ``'always'``), voice-clone
either produces a FRESH transcript at the target path or fails:

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
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
VOICE_CLONE = REPO_ROOT / 'scripts' / 'voice-clone.py'

# Input env vars that must not leak from the host into a test run.
_ENV_BLACKLIST_PREFIXES = ('TTS_', 'ASR_', 'ALIGN', 'QWEN3', 'DASHSCOPE_', 'COSYVOICE_')

NARRATION = '大家好。今天我们来聊聊视频制作。'  # 15 non-whitespace characters


def run_voice_clone(
    *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    clean = {
        k: v for k, v in os.environ.items() if not k.startswith(_ENV_BLACKLIST_PREFIXES)
    }
    if env:
        clean.update(env)
    return subprocess.run(
        [sys.executable, str(VOICE_CLONE), *args],
        capture_output=True,
        text=True,
        env=clean,
        timeout=120,
    )


def parse_stdout(proc: subprocess.CompletedProcess) -> dict:
    """stdout must be exactly one parseable JSON document."""
    assert len(proc.stdout.splitlines()) == 1, proc.stdout
    return json.loads(proc.stdout)


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
    # 15 non-whitespace characters / 7.5 per second = 2.0 s (floor 1.0 s).
    assert result['duration_s'] == pytest.approx(2.0, abs=0.15)

    transcript_file = tmp_path / 'tr' / 'transcript.json'
    assert result['transcript_path'] == str(transcript_file.resolve())
    transcript = json.loads(transcript_file.read_text(encoding='utf-8'))
    assert [sentence['text'] for sentence in transcript] == ['大家好。', '今天我们来聊聊视频制作。']
    words = [word for sentence in transcript for word in sentence['words']]
    assert ''.join(word['text'] for word in words) == NARRATION  # one word per character
    # Even spread over the whole audio: starts at 0, no gaps, ends at the duration.
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


def test_backend_without_aligner_reports_both_attempts_when_asr_is_unavailable(
    tmp_path: Path, dashscope_env: dict[str, str]
):
    # The DashScope key set for synthesis would make auto ASR usable, so pin
    # ASR to the fake backend, which fails without ASR_FAKE_TEXT.
    proc = synthesize_dashscope(
        tmp_path,
        '--emit-transcript',
        env={**dashscope_env, 'ASR_BACKEND': 'fake'},
    )

    assert proc.returncode == 1
    result = parse_stdout(proc)
    direct, asr = result['transcript_attempts']
    assert direct == {'method': 'direct_align', 'error': 'dashscope backend has no direct aligner'}
    assert asr['method'] == 'asr'
    assert 'ASR_FAKE_TEXT' in asr['error']
    assert (tmp_path / 'out' / 'narration.mp3').stat().st_size > 0


def test_help_marks_fake_as_test_only():
    proc = run_voice_clone('--help')

    assert proc.returncode == 0
    assert 'fake' in proc.stdout
    assert '测试用' in proc.stdout
    assert 'transcript_attempts' in proc.stdout  # the backend docs live in --help
