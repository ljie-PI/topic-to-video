"""Voice-clone CLI output and model-free voice-utils import contracts.

The CLI check uses the fake backend, so no model or external service is needed.
The import check explicitly rejects mlx imports: both library modules must stay
cheap to import while keeping their model imports lazy inside the public calls.
"""
from __future__ import annotations

import builtins
import importlib
import subprocess
import sys
from pathlib import Path

import pytest

from cli_helpers import parse_stdout, run_cli

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / 'scripts'
VOICE_CLONE = SCRIPTS / 'voice-clone.py'

# Input env vars that must not leak from the host into a test run.
_ENV_BLACKLIST_PREFIXES = ('TTS_', 'ASR_', 'ALIGN', 'NARRATE_', 'VOICE_')


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
def test_voice_clone_fake_backend_emits_one_json_result_on_stdout(tmp_path: Path):
    narration = tmp_path / 'narration.txt'
    narration.write_text('Hello world.', encoding='utf-8')

    proc = run_cli(
        VOICE_CLONE,
        '--backend', 'fake',
        '--input-file', str(narration),
        '--output-dir', str(tmp_path / 'output'),
        '--transcript-output', str(tmp_path / 'transcript.json'),
        env={},
        blocked_prefixes=_ENV_BLACKLIST_PREFIXES,
        timeout=120,
    )

    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['success'] is True
    assert result['backend'] == 'fake'
    assert result['transcript_method'] == 'direct_align'


def test_mlx_library_functions_import_without_mlx(monkeypatch: pytest.MonkeyPatch):
    for module_name in ('tts_qwen', 'text_align', 'mlx_align', 'utils'):
        sys.modules.pop(module_name, None)

    real_import = builtins.__import__

    def reject_mlx_import(name, *args, **kwargs):
        if name == 'mlx' or name.startswith(('mlx.', 'mlx_audio')):
            raise AssertionError(f'top-level voice-utils import pulled in {name}')
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', reject_mlx_import)

    assert callable(importlib.import_module('tts_qwen').synthesize)
    assert callable(importlib.import_module('text_align').align_text)
