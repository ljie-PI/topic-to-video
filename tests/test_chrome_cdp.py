"""Chrome-free tests for the shared Chrome/CDP adapters."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

import chrome_cdp


def test_cdp_ready_returns_false_for_unreachable_port():
    assert chrome_cdp.cdp_ready('http://127.0.0.1:1') is False


@pytest.mark.parametrize('reused, flags, expected', [
    pytest.param(True, {
        'profile_dir': '/tmp/shared-profile', 'headless': 'on',
        'chrome_path': '/opt/chrome', 'no_sandbox': True,
    }, ['--profile-dir', '--headless', '--chrome-path', '--no-sandbox'], id='reusing-explicit'),
    pytest.param(True, {
        'profile_dir': None, 'headless': None, 'chrome_path': None, 'no_sandbox': None,
    }, [], id='reusing-unset'),
    pytest.param(False, {
        'profile_dir': '/tmp/shared-profile', 'headless': 'off',
        'chrome_path': '/opt/chrome', 'no_sandbox': True,
    }, [], id='launching'),
])
def test_ignored_flags_reports_only_explicit_flags_when_reusing_cdp(reused, flags, expected):
    assert chrome_cdp.compute_ignored_flags(
        reused=reused, **flags,
    ) == expected
