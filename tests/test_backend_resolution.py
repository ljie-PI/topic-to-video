"""Tests for the --resolve-backend seam of voice-clone.py and transcribe.py.

Both scripts default to backend "auto" and expose ``--resolve-backend`` to
print the auto decision as one JSON document WITHOUT loading any model
(exit 0). Hardware/OS probes are overridable via documented env vars so the
decision logic is testable on any machine:

  voice-clone.py:  TTS_DETECT_PLATFORM / TTS_DETECT_MACHINE /
                   TTS_DETECT_CUDA / TTS_DETECT_MLX_AUDIO
  transcribe.py:   ASR_DETECT_PLATFORM / ASR_DETECT_MACHINE / ASR_DETECT_CUDA

Auto order (voice-clone): darwin+arm64 with mlx-audio -> mlx; CUDA -> qwen3tts;
DASHSCOPE_API_KEY -> dashscope; otherwise exit 1 with a JSON error listing
what is missing. Auto order (transcribe): CUDA -> qwen3; DASHSCOPE_API_KEY ->
dashscope; otherwise exit 1 listing what is missing (no platform special case:
ASR is the fallback when voice-clone's direct alignment fails).
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
TRANSCRIBE = REPO_ROOT / 'scripts' / 'transcribe.py'

# Backend-affecting env vars that must not leak from the host into a test run.
_ENV_BLACKLIST = [
    'TTS_BACKEND',
    'ASR_BACKEND',
    'DASHSCOPE_API_KEY',
    'COSYVOICE_VOICE_ID',
    'TTS_DETECT_PLATFORM',
    'TTS_DETECT_MACHINE',
    'TTS_DETECT_CUDA',
    'TTS_DETECT_MLX_AUDIO',
    'ASR_DETECT_PLATFORM',
    'ASR_DETECT_MACHINE',
    'ASR_DETECT_CUDA',
]


def run_cli(script: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    clean = {k: v for k, v in os.environ.items() if k not in _ENV_BLACKLIST}
    if env:
        clean.update(env)
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        env=clean,
    )


def parse_stdout(proc: subprocess.CompletedProcess) -> dict:
    return json.loads(proc.stdout)


# --- voice-clone.py --resolve-backend -----------------------------------------


def test_resolve_auto_apple_silicon_picks_mlx():
    proc = run_cli(
        VOICE_CLONE,
        '--resolve-backend',
        env={
            'TTS_DETECT_PLATFORM': 'darwin',
            'TTS_DETECT_MACHINE': 'arm64',
            'TTS_DETECT_CUDA': '0',
            'TTS_DETECT_MLX_AUDIO': '1',
        },
    )
    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['success'] is True
    assert result['backend'] == 'mlx'
    assert result['backend_source'] == 'auto'


def test_resolve_auto_cuda_picks_qwen3tts():
    proc = run_cli(
        VOICE_CLONE,
        '--resolve-backend',
        env={
            'TTS_DETECT_PLATFORM': 'linux',
            'TTS_DETECT_MACHINE': 'x86_64',
            'TTS_DETECT_CUDA': '1',
        },
    )
    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['backend'] == 'qwen3tts'


def test_resolve_auto_dashscope_key_picks_dashscope():
    proc = run_cli(
        VOICE_CLONE,
        '--resolve-backend',
        env={
            'TTS_DETECT_PLATFORM': 'linux',
            'TTS_DETECT_MACHINE': 'x86_64',
            'TTS_DETECT_CUDA': '0',
            'DASHSCOPE_API_KEY': 'sk-test',
        },
    )
    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['backend'] == 'dashscope'


def test_resolve_auto_nothing_available_exits_1_with_missing_list():
    proc = run_cli(
        VOICE_CLONE,
        '--resolve-backend',
        env={
            'TTS_DETECT_PLATFORM': 'linux',
            'TTS_DETECT_MACHINE': 'x86_64',
            'TTS_DETECT_CUDA': '0',
        },
    )
    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert 'missing' in result
    assert any('cuda' in item.lower() or 'gpu' in item.lower() for item in result['missing'])
    assert any('dashscope' in item.lower() for item in result['missing'])


def test_resolve_auto_apple_silicon_without_mlx_audio_falls_through():
    """arm64 Mac without mlx-audio installed: no mlx, error lists it missing."""
    proc = run_cli(
        VOICE_CLONE,
        '--resolve-backend',
        env={
            'TTS_DETECT_PLATFORM': 'darwin',
            'TTS_DETECT_MACHINE': 'arm64',
            'TTS_DETECT_CUDA': '0',
            'TTS_DETECT_MLX_AUDIO': '0',
        },
    )
    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert any('mlx' in item.lower() for item in result['missing'])


def test_resolve_explicit_backend_wins_over_auto():
    proc = run_cli(
        VOICE_CLONE,
        '--backend',
        'dashscope',
        '--resolve-backend',
        env={
            'TTS_DETECT_PLATFORM': 'darwin',
            'TTS_DETECT_MACHINE': 'arm64',
            'TTS_DETECT_CUDA': '1',
            'TTS_DETECT_MLX_AUDIO': '1',
        },
    )
    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['backend'] == 'dashscope'
    assert result['backend_source'] == 'cli'


def test_resolve_tts_backend_env_respected():
    proc = run_cli(
        VOICE_CLONE,
        '--resolve-backend',
        env={
            'TTS_BACKEND': 'qwen3tts',
            'TTS_DETECT_PLATFORM': 'darwin',
            'TTS_DETECT_MACHINE': 'arm64',
            'TTS_DETECT_CUDA': '0',
            'TTS_DETECT_MLX_AUDIO': '1',
        },
    )
    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['backend'] == 'qwen3tts'
    assert result['backend_source'] == 'env'


def test_unknown_backend_env_exits_2():
    proc = run_cli(VOICE_CLONE, '--resolve-backend', env={'TTS_BACKEND': 'bogus'})
    assert proc.returncode == 2
    result = parse_stdout(proc)
    assert result['success'] is False


def test_unknown_backend_cli_exits_2():
    proc = run_cli(VOICE_CLONE, '--backend', 'bogus', '--resolve-backend')
    assert proc.returncode == 2
    result = parse_stdout(proc)
    assert result['success'] is False


# --- transcribe.py --resolve-backend ------------------------------------------


def test_transcribe_resolve_auto_cuda_picks_qwen3():
    proc = run_cli(
        TRANSCRIBE,
        '--resolve-backend',
        env={'ASR_DETECT_PLATFORM': 'linux', 'ASR_DETECT_MACHINE': 'x86_64', 'ASR_DETECT_CUDA': '1'},
    )
    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['success'] is True
    assert result['backend'] == 'qwen3'
    assert result['backend_source'] == 'auto'


def test_transcribe_resolve_auto_dashscope_key_picks_dashscope():
    proc = run_cli(
        TRANSCRIBE,
        '--resolve-backend',
        env={
            'ASR_DETECT_PLATFORM': 'linux',
            'ASR_DETECT_MACHINE': 'x86_64',
            'ASR_DETECT_CUDA': '0',
            'DASHSCOPE_API_KEY': 'sk-test',
        },
    )
    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['backend'] == 'dashscope'


def test_transcribe_resolve_apple_silicon_without_asr_is_a_plain_unavailable_error():
    """arm64 Macs get no special case: ASR is the fallback when mlx alignment
    fails, so auto must report what is missing, not tell the caller to go back
    to voice-clone's mlx backend."""
    proc = run_cli(
        TRANSCRIBE,
        '--resolve-backend',
        env={'ASR_DETECT_PLATFORM': 'darwin', 'ASR_DETECT_MACHINE': 'arm64', 'ASR_DETECT_CUDA': '0'},
    )
    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert result['error'].startswith('no usable ASR backend: ')
    assert 'none is needed' not in result['error']
    assert any('cuda' in item.lower() for item in result['missing'])
    assert any('dashscope' in item.lower() for item in result['missing'])

    # A real run resolves the backend the same way, so it fails the same way.
    run = run_cli(
        TRANSCRIBE,
        'narration.mp3',
        'transcript.json',
        env={'ASR_DETECT_PLATFORM': 'darwin', 'ASR_DETECT_MACHINE': 'arm64', 'ASR_DETECT_CUDA': '0'},
    )
    assert run.returncode == 1
    assert parse_stdout(run)['error'] == result['error']


def test_transcribe_resolve_nothing_available_exits_1():
    proc = run_cli(
        TRANSCRIBE,
        '--resolve-backend',
        env={'ASR_DETECT_PLATFORM': 'linux', 'ASR_DETECT_MACHINE': 'x86_64', 'ASR_DETECT_CUDA': '0'},
    )
    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert 'missing' in result


def test_transcribe_resolve_explicit_backend_wins_over_auto():
    proc = run_cli(
        TRANSCRIBE,
        '--backend',
        'dashscope',
        '--resolve-backend',
        env={'ASR_DETECT_PLATFORM': 'linux', 'ASR_DETECT_MACHINE': 'x86_64', 'ASR_DETECT_CUDA': '1'},
    )
    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['backend'] == 'dashscope'
    assert result['backend_source'] == 'cli'


def test_transcribe_resolve_asr_backend_env_respected():
    proc = run_cli(
        TRANSCRIBE,
        '--resolve-backend',
        env={
            'ASR_BACKEND': 'qwen3',
            'ASR_DETECT_PLATFORM': 'linux',
            'ASR_DETECT_MACHINE': 'x86_64',
            'ASR_DETECT_CUDA': '0',
            'DASHSCOPE_API_KEY': 'sk-test',
        },
    )
    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['backend'] == 'qwen3'
    assert result['backend_source'] == 'env'


def test_transcribe_unknown_backend_env_exits_2():
    proc = run_cli(TRANSCRIBE, '--resolve-backend', env={'ASR_BACKEND': 'bogus'})
    assert proc.returncode == 2
    result = parse_stdout(proc)
    assert result['success'] is False


def test_transcribe_unknown_backend_cli_exits_2():
    proc = run_cli(TRANSCRIBE, '--backend', 'bogus', '--resolve-backend')
    assert proc.returncode == 2
    result = parse_stdout(proc)
    assert result['success'] is False


# --- the test-only fake backends ------------------------------------------------

_FAKE_CASES = [
    pytest.param(
        VOICE_CLONE,
        'TTS_BACKEND',
        {'TTS_DETECT_PLATFORM': 'linux', 'TTS_DETECT_MACHINE': 'x86_64', 'TTS_DETECT_CUDA': '0'},
        id='voice-clone',
    ),
    pytest.param(
        TRANSCRIBE,
        'ASR_BACKEND',
        {'ASR_DETECT_PLATFORM': 'linux', 'ASR_DETECT_MACHINE': 'x86_64', 'ASR_DETECT_CUDA': '0'},
        id='transcribe',
    ),
]


@pytest.mark.parametrize('script, env_var, probes', _FAKE_CASES)
def test_fake_backend_is_selectable_by_flag_and_by_environment(script, env_var, probes):
    by_flag = run_cli(script, '--backend', 'fake', '--resolve-backend', env=probes)
    assert by_flag.returncode == 0, by_flag.stderr
    assert parse_stdout(by_flag)['backend'] == 'fake'
    assert parse_stdout(by_flag)['backend_source'] == 'cli'

    by_env = run_cli(script, '--resolve-backend', env={**probes, env_var: 'fake'})
    assert by_env.returncode == 0, by_env.stderr
    assert parse_stdout(by_env)['backend'] == 'fake'
    assert parse_stdout(by_env)['backend_source'] == 'env'


@pytest.mark.parametrize('script, env_var, probes', _FAKE_CASES)
def test_auto_never_picks_fake(script, env_var, probes):
    # Nothing real is usable here: auto must fail rather than fall back to fake.
    proc = run_cli(script, '--resolve-backend', env=probes)
    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert not any('fake' in item.lower() for item in result['missing'])
