"""Chrome-free tests for the shared Chrome/CDP adapters."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

import chrome_cdp


def test_cdp_ready_returns_false_for_unreachable_port():
    assert chrome_cdp.cdp_ready('http://127.0.0.1:1') is False


def test_ignored_flags_reports_only_explicit_flags_when_reusing_cdp():
    assert chrome_cdp.compute_ignored_flags(
        reused=True,
        profile_dir='/tmp/shared-profile',
        headless='on',
        chrome_path='/opt/chrome',
        no_sandbox=True,
    ) == ['--profile-dir', '--headless', '--chrome-path', '--no-sandbox']


def test_ignored_flags_uses_none_sentinels_and_is_empty_when_launching():
    assert chrome_cdp.compute_ignored_flags(
        reused=True,
        profile_dir=None,
        headless=None,
        chrome_path=None,
        no_sandbox=None,
    ) == []
    assert chrome_cdp.compute_ignored_flags(
        reused=False,
        profile_dir='/tmp/shared-profile',
        headless='off',
        chrome_path='/opt/chrome',
        no_sandbox=True,
    ) == []
