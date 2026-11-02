"""Chrome-free CLI tests for Gemini Deep Research resume state handling."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'gemini-deep-research.py'


def run_resume(output_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable, str(SCRIPT),
            '--output-dir', str(output_dir),
            '--resume',
            '--profile-dir', str(output_dir / 'profile'),
            '--chrome-path', str(output_dir / 'missing-chrome'),
            '--cdp-url', 'http://127.0.0.1:9',
        ],
        cwd=output_dir,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_self_check_requires_profile_dir(tmp_path: Path):
    proc = subprocess.run(
        [
            sys.executable, str(SCRIPT), '--self-check',
            '--cdp-url', 'http://127.0.0.1:1',
            '--chrome-path', str(tmp_path / 'missing-chrome'),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert proc.returncode == 2
    result = json.loads(proc.stdout)
    assert result['success'] is False
    assert '--profile-dir' in result['error']


@pytest.mark.parametrize('state, error', [
    pytest.param(None, 'state', id='missing-state'),
    pytest.param('{"state_file_version": 1}', 'session_url', id='missing-session-url'),
])
def test_invalid_resume_state_returns_json_error_without_chrome(tmp_path: Path, state, error):
    if state is not None:
        (tmp_path / 'gemini_deep_research_state.json').write_text(state, encoding='utf-8')

    proc = run_resume(tmp_path)

    assert proc.returncode == 1, proc.stderr
    result = json.loads(proc.stdout)
    assert result['success'] is False
    assert error in result['error'].lower()
    assert not (tmp_path / 'profile').exists()
