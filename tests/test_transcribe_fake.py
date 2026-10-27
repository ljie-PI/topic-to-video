"""Tests for transcribe.py's test-only ``fake`` ASR backend, via its command line.

The fake backend "recognizes" the text in ``ASR_FAKE_TEXT`` and spreads its
characters evenly over the ffprobe duration of the audio. It runs without any
model and is selected only explicitly (``--backend fake`` / ``ASR_BACKEND=fake``).
ffmpeg / ffprobe are required.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cli_helpers import parse_stdout, run_cli

REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSCRIBE = REPO_ROOT / 'scripts' / 'transcribe.py'

_ENV_BLACKLIST_PREFIXES = ('ASR_', 'QWEN3', 'DASHSCOPE_')

TEXT = '你好。再见。'  # 6 non-whitespace characters, two sentences


def run_transcribe(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return run_cli(
        TRANSCRIBE, *args, env=env or {}, blocked_prefixes=_ENV_BLACKLIST_PREFIXES
    )


@pytest.fixture
def silent_mp3(tmp_path: Path, require_ffmpeg) -> Path:
    audio = tmp_path / 'narration.mp3'
    subprocess.run(
        [
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', '3',
            '-c:a', 'libmp3lame', str(audio),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return audio


def test_fake_asr_spreads_text_evenly_over_audio_duration(tmp_path: Path, silent_mp3: Path):
    output = tmp_path / 'out' / 'transcript.json'

    proc = run_transcribe(
        str(silent_mp3), str(output), '--backend', 'fake',
        env={'ASR_FAKE_TEXT': TEXT},
    )

    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['success'] is True
    assert result['backend'] == 'fake'
    assert result['output_path'] == str(output.resolve())
    assert result['sentence_count'] == 2
    assert result['word_count'] == 6

    transcript = json.loads(output.read_text(encoding='utf-8'))
    assert [sentence['text'] for sentence in transcript] == ['你好。', '再见。']
    words = [word for sentence in transcript for word in sentence['words']]
    assert [word['text'] for word in words] == list(TEXT)
    # ffprobe measures the 3 s clip (an mp3 may add a few ms of padding).
    assert words[0]['begin'] == 0
    assert words[-1]['end'] == pytest.approx(3000, abs=100)
    assert all(a['end'] == b['begin'] for a, b in zip(words, words[1:]))
    step = words[0]['end'] - words[0]['begin']
    assert all(w['end'] - w['begin'] == pytest.approx(step, abs=1) for w in words)


def test_fake_asr_is_selectable_through_the_environment(tmp_path: Path, silent_mp3: Path):
    proc = run_transcribe(
        str(silent_mp3), str(tmp_path / 'transcript.json'),
        env={'ASR_BACKEND': 'fake', 'ASR_FAKE_TEXT': TEXT},
    )

    assert proc.returncode == 0, proc.stderr
    assert parse_stdout(proc)['backend'] == 'fake'


def test_fake_asr_without_text_is_a_runtime_error(tmp_path: Path, silent_mp3: Path):
    output = tmp_path / 'transcript.json'

    proc = run_transcribe(str(silent_mp3), str(output), '--backend', 'fake')

    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert 'ASR_FAKE_TEXT' in result['error']
    assert not output.exists()


def test_help_marks_fake_as_test_only():
    proc = run_transcribe('--help')

    assert proc.returncode == 0
    assert 'fake' in proc.stdout
    assert '测试用' in proc.stdout
