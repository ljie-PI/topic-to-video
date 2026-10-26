"""Chrome-free CLI tests for Gemini Deep Research resume state handling."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'gemini-deep-research.py'


def run_resume(output_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable, str(SCRIPT),
            '--output-dir', str(output_dir),
            '--resume',
            '--chrome-path', str(output_dir / 'missing-chrome'),
            '--cdp-url', 'http://127.0.0.1:9',
        ],
        cwd=output_dir,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_resume_with_missing_state_file_returns_json_error_without_chrome(tmp_path: Path):
    proc = run_resume(tmp_path)

    assert proc.returncode == 1, proc.stderr
    result = json.loads(proc.stdout)
    assert result['success'] is False
    assert 'state' in result['error'].lower()
    assert not (tmp_path / 'chrome_profile').exists()


def test_resume_without_session_url_returns_json_error_without_chrome(tmp_path: Path):
    state_file = tmp_path / 'gemini_deep_research_state.json'
    state_file.write_text('{"state_file_version": 1}', encoding='utf-8')

    proc = run_resume(tmp_path)

    assert proc.returncode == 1, proc.stderr
    result = json.loads(proc.stdout)
    assert result['success'] is False
    assert 'session_url' in result['error']
    assert not (tmp_path / 'chrome_profile').exists()
