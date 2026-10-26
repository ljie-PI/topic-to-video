"""CLI contract tests for the voice-utils scripts (stdout = one JSON).

These cover the seams a pipeline caller depends on:

* diagnostics (``[latency]``) never pollute stdout — voice-clone's mlx backend
  calls tts_qwen.synthesize, and voice-clone's stdout must stay one JSON;
* ``text_align.py`` usage errors exit 2 with a JSON error, unreadable input
  exits 1 with a JSON error (repo convention: exit codes 0 / 1 / 2);
* standalone ``tts_qwen.py`` / ``narrate.py`` keep human output on success but
  end failures with one JSON line instead of a bare traceback;
* the documented env inputs are real: TTS_TEXT_FILE, ALIGN_TEXT and
  ALIGN_LANGUAGE.

Every test drives a script through its command line only.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / 'scripts'
TTS_QWEN = SCRIPTS / 'tts_qwen.py'
NARRATE = SCRIPTS / 'narrate.py'
TEXT_ALIGN = SCRIPTS / 'text_align.py'
VOICE_CLONE = SCRIPTS / 'voice-clone.py'

# Input env vars that must not leak from the host into a test run. The
# prefixes cover TTS_* (incl. TTS_DETECT_*), ALIGN*, NARRATE_* and VOICE_REF.
_ENV_BLACKLIST_PREFIXES = ('TTS_', 'ALIGN', 'NARRATE_', 'VOICE_')


def run_cli(
    script: Path,
    *args: str,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    clean = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(_ENV_BLACKLIST_PREFIXES)
    }
    if env:
        clean.update(env)
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        env=clean,
        cwd=str(cwd) if cwd else None,
    )


def parse_stdout(proc: subprocess.CompletedProcess) -> dict:
    """stdout must be exactly one parseable JSON document."""
    return json.loads(proc.stdout)


# --- diagnostics must not pollute stdout ---------------------------------------


def test_log_latency_writes_to_stderr_only():
    """voice-clone's mlx path calls log_latency before printing its JSON."""
    proc = subprocess.run(
        [sys.executable, '-c', "from utils import log_latency; log_latency('x', 0.1)"],
        capture_output=True,
        text=True,
        cwd=str(SCRIPTS),
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == ''
    assert '[latency] x:' in proc.stderr


@pytest.mark.usefixtures('require_ffmpeg')
def test_voice_clone_honors_ffprobe_override_and_preserves_duration_output(tmp_path: Path):
    audio = tmp_path / 'source.mp3'
    subprocess.run(
        [
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1',
            '-c:a', 'libmp3lame', str(audio),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    fake_package = tmp_path / 'fake_package'
    tts_package = fake_package / 'dashscope' / 'audio'
    tts_package.mkdir(parents=True)
    (fake_package / 'dashscope' / '__init__.py').write_text('', encoding='utf-8')
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

    probe_marker = tmp_path / 'probe-invoked'
    probe_wrapper = tmp_path / 'ffprobe-wrapper'
    probe_wrapper.write_text(
        f'#!{sys.executable}\n'
        'import os\n'
        'from pathlib import Path\n'
        'import subprocess\n'
        'import sys\n'
        "Path(os.environ['FFPROBE_MARKER']).write_text('invoked', encoding='utf-8')\n"
        f'raise SystemExit(subprocess.call([{shutil.which("ffprobe")!r}, *sys.argv[1:]]))\n',
        encoding='utf-8',
    )
    probe_wrapper.chmod(0o755)
    narration_text = tmp_path / 'narration.txt'
    narration_text.write_text('Hello world.', encoding='utf-8')

    proc = run_cli(
        VOICE_CLONE,
        '--backend', 'dashscope',
        '--input-file', str(narration_text),
        '--output-dir', str(tmp_path / 'output'),
        env={
            'DASHSCOPE_API_KEY': 'test-key',
            'COSYVOICE_VOICE_ID': 'test-voice',
            'FAKE_DASHSCOPE_AUDIO': str(audio),
            'FFPROBE_BIN': str(probe_wrapper),
            'FFPROBE_MARKER': str(probe_marker),
            'PYTHONPATH': str(fake_package),
        },
    )

    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['success'] is True
    assert result['duration_s'] == pytest.approx(1.0, abs=0.1)
    assert probe_marker.read_text(encoding='utf-8') == 'invoked'


# --- text_align.py exit / JSON contract ---------------------------------------


@pytest.mark.parametrize(
    'args',
    [
        ('--align-json', 'narration.align.json'),
        ('--emit-transcript', 'transcript.json'),
    ],
    ids=['align-json-only', 'emit-transcript-only'],
)
def test_conversion_flags_must_be_passed_together(args):
    proc = run_cli(TEXT_ALIGN, *args)
    assert proc.returncode == 2
    result = parse_stdout(proc)
    assert result['success'] is False
    assert '--align-json' in result['error']
    assert '--emit-transcript' in result['error']


def test_unreadable_align_json_exits_1_with_json_error(tmp_path: Path):
    proc = run_cli(
        TEXT_ALIGN,
        '--align-json', str(tmp_path),  # a directory: unreadable as a JSON file
        '--emit-transcript', str(tmp_path / 'transcript.json'),
    )
    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert 'align.json' in result['error']


# --- standalone scripts: JSON on failure, no traceback ------------------------


@pytest.mark.parametrize('script', [TTS_QWEN, NARRATE], ids=['tts_qwen', 'narrate'])
def test_failures_end_with_one_json_line_not_a_traceback(script: Path, tmp_path: Path):
    proc = run_cli(
        script,
        env={
            'TTS_TEXT': 'hello',
            'TTS_MODEL': str(tmp_path / 'missing-model'),
            'VOICE_REF': str(tmp_path / 'missing-voice.wav'),
        },
    )
    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert 'not found' in result['error']
    assert 'Traceback' not in proc.stderr


@pytest.mark.parametrize('script', [TTS_QWEN, NARRATE], ids=['tts_qwen', 'narrate'])
def test_tts_text_file_env_is_read_when_text_flags_absent(script: Path, tmp_path: Path):
    text_file = tmp_path / 'script.txt'
    text_file.write_text('大家好。\n', encoding='utf-8')
    # The text file resolves, so the run proceeds to the model check. Without
    # TTS_TEXT_FILE the same invocation fails earlier with a "no text" error.
    proc = run_cli(
        script,
        env={
            'TTS_TEXT_FILE': str(text_file),
            'TTS_MODEL': str(tmp_path / 'missing-model'),
        },
    )
    assert proc.returncode == 1
    assert 'model not found' in parse_stdout(proc)['error']

    no_text = run_cli(script, env={'TTS_MODEL': str(tmp_path / 'missing-model')})
    assert no_text.returncode == 1
    error = parse_stdout(no_text)['error']
    assert 'no script text' in error or 'no text' in error


# --- text_align.py env inputs --------------------------------------------------


def test_align_text_and_language_env_are_used(tmp_path: Path):
    audio = tmp_path / 'narration.wav'
    audio.write_bytes(b'')
    model_dir = tmp_path / 'aligner-model'
    model_dir.mkdir()
    env = {
        'ALIGN_AUDIO': str(audio),
        'ALIGNER_MODEL': str(model_dir),
        'ALIGN_LANGUAGE': 'Japanese',
        'ALIGN_TEXT': 'こんにちは。',
    }
    proc = run_cli(TEXT_ALIGN, env=env)
    # No aligner model is actually loaded: the run fails after diagnostics.
    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert 'language : Japanese' in proc.stderr
    assert 'Traceback' not in proc.stderr

    # Without ALIGN_TEXT the run stops before the audio/model checks.
    no_text = run_cli(
        TEXT_ALIGN,
        env={
            'ALIGN_AUDIO': str(audio),
            'ALIGNER_MODEL': str(model_dir),
        },
    )
    assert no_text.returncode == 1
    assert 'no text' in parse_stdout(no_text)['error']
