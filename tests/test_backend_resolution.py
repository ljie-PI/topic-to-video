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

import subprocess
from pathlib import Path

import pytest

from cli_helpers import parse_stdout, run_cli as run_script

REPO_ROOT = Path(__file__).resolve().parent.parent
VOICE_CLONE = REPO_ROOT / 'scripts' / 'voice-clone.py'
TRANSCRIBE = REPO_ROOT / 'scripts' / 'transcribe.py'
BACKENDS = [
    pytest.param(VOICE_CLONE, 'TTS', 'qwen3tts', id='voice-clone'),
    pytest.param(TRANSCRIBE, 'ASR', 'qwen3', id='transcribe'),
]

# Backend-affecting env vars that must not leak from the host into a test run.
_ENV_BLACKLIST = (
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
)


def run_cli(script: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return run_script(script, *args, env=env or {}, blocked=_ENV_BLACKLIST)


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


@pytest.mark.parametrize('script, prefix, backend', BACKENDS)
def test_resolve_auto_cuda_picks_the_gpu_backend(script, prefix, backend):
    proc = run_cli(
        script,
        '--resolve-backend',
        env={
            f'{prefix}_DETECT_PLATFORM': 'linux',
            f'{prefix}_DETECT_MACHINE': 'x86_64',
            f'{prefix}_DETECT_CUDA': '1',
        },
    )
    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['success'] is True
    assert (result['backend'], result['backend_source']) == (backend, 'auto')


@pytest.mark.parametrize('script, prefix, backend', BACKENDS)
def test_resolve_auto_dashscope_key_picks_dashscope(script, prefix, backend):
    proc = run_cli(
        script,
        '--resolve-backend',
        env={
            f'{prefix}_DETECT_PLATFORM': 'linux',
            f'{prefix}_DETECT_MACHINE': 'x86_64',
            f'{prefix}_DETECT_CUDA': '0',
            'DASHSCOPE_API_KEY': 'sk-test',
        },
    )
    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['backend'] == 'dashscope'


@pytest.mark.parametrize('script, prefix, backend', BACKENDS)
def test_resolve_auto_nothing_available_reports_missing_backends_without_picking_fake(script, prefix, backend):
    proc = run_cli(
        script,
        '--resolve-backend',
        env={
            f'{prefix}_DETECT_PLATFORM': 'linux',
            f'{prefix}_DETECT_MACHINE': 'x86_64',
            f'{prefix}_DETECT_CUDA': '0',
        },
    )
    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert any('cuda' in item.lower() or 'gpu' in item.lower() for item in result['missing'])
    assert any('dashscope' in item.lower() for item in result['missing'])
    assert not any('fake' in item.lower() for item in result['missing'])


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


@pytest.mark.parametrize('script, prefix, backend', BACKENDS)
def test_resolve_explicit_backend_wins_over_environment_and_auto(script, prefix, backend):
    proc = run_cli(
        script,
        '--backend',
        'dashscope',
        '--resolve-backend',
        env={
            f'{prefix}_BACKEND': backend,
            f'{prefix}_DETECT_PLATFORM': 'darwin',
            f'{prefix}_DETECT_MACHINE': 'arm64',
            f'{prefix}_DETECT_CUDA': '1',
            f'{prefix}_DETECT_MLX_AUDIO': '1',
        },
    )
    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['backend'] == 'dashscope'
    assert result['backend_source'] == 'cli'


@pytest.mark.parametrize('script, prefix, backend', BACKENDS)
def test_resolve_backend_env_respected(script, prefix, backend):
    proc = run_cli(
        script,
        '--resolve-backend',
        env={
            f'{prefix}_BACKEND': backend,
            f'{prefix}_DETECT_PLATFORM': 'darwin',
            f'{prefix}_DETECT_MACHINE': 'arm64',
            f'{prefix}_DETECT_CUDA': '0',
            f'{prefix}_DETECT_MLX_AUDIO': '1',
            'DASHSCOPE_API_KEY': 'sk-test',
        },
    )
    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['backend'] == backend
    assert result['backend_source'] == 'env'


@pytest.mark.parametrize('script, prefix, backend', BACKENDS)
@pytest.mark.parametrize('source', ['cli', 'env'])
def test_unknown_backend_exits_2(script, prefix, backend, source):
    args = ('--backend', 'bogus') if source == 'cli' else ()
    env = {f'{prefix}_BACKEND': 'bogus'} if source == 'env' else {}
    proc = run_cli(script, *args, '--resolve-backend', env=env)
    assert proc.returncode == 2
    result = parse_stdout(proc)
    assert result['success'] is False


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
@pytest.mark.parametrize('source', ['cli', 'env'])
def test_fake_backend_is_selectable_by_flag_and_by_environment(script, env_var, probes, source):
    args = ('--backend', 'fake') if source == 'cli' else ()
    env = {**probes, env_var: 'fake'} if source == 'env' else probes
    proc = run_cli(script, *args, '--resolve-backend', env=env)
    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert (result['backend'], result['backend_source']) == ('fake', source)
