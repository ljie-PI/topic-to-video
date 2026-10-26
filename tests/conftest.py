"""Required external dependencies for the tests that need them.

ffmpeg / ffprobe, a system Chrome and the playwright package are required
dependencies of the skill (see SKILL.md). Tests that need them never skip:
a missing dependency makes exactly those tests fail with a message naming
what to install, while unrelated tests still run. Chrome is located with
chrome_cdp.find_chrome (CHROME_PATH, then the platform's standard install
paths), so the tests accept exactly the browsers the scripts accept.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

import chrome_cdp


def find_chrome() -> str | None:
    return chrome_cdp.find_chrome(None)


@pytest.fixture(scope='session')
def require_ffmpeg() -> None:
    missing = [tool for tool in ('ffmpeg', 'ffprobe') if shutil.which(tool) is None]
    if missing:
        pytest.fail(f'missing required dependency: {", ".join(missing)} (system package)', pytrace=False)


@pytest.fixture(scope='session')
def require_chrome() -> None:
    missing = []
    if importlib.util.find_spec('playwright') is None:
        missing.append('playwright (pip install -r requirements-dev.txt)')
    if find_chrome() is None:
        missing.append('system Chrome (or set CHROME_PATH)')
    if missing:
        pytest.fail(f'missing required dependency: {", ".join(missing)}', pytrace=False)
