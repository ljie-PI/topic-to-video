"""Shared Chrome discovery, CDP attachment, and isolated browser launching."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import urlparse

CDP_READY_TIMEOUT_S = 15.0
CDP_POLL_INTERVAL_S = 0.5
CHROME_CANDIDATES_LINUX = [
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
]
CHROME_CANDIDATES_MAC = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary',
]
CHROME_CANDIDATES_WIN = [
    os.path.expandvars(r'%ProgramFiles%\Google\Chrome\Application\chrome.exe'),
    os.path.expandvars(r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe'),
    os.path.expandvars(r'%LocalAppData%\Google\Chrome\Application\chrome.exe'),
]


@dataclass
class ChromeSession:
    """A Playwright browser plus the lifecycle and CDP attachment metadata."""

    browser: Any
    launched: bool
    ignored_flags: list[str]
    cdp_url: Optional[str] = None
    _playwright: Any = field(default=None, repr=False)

    @property
    def reused(self) -> bool:
        return not self.launched

    def metadata(self) -> dict[str, Any]:
        return {
            'cdp_url': self.cdp_url,
            'reused': self.reused,
            'ignored_flags': self.ignored_flags,
        }

    def __enter__(self) -> 'ChromeSession':
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the Playwright connection; attached Chrome is left running."""
        try:
            self.browser.close()
        finally:
            if self._playwright is not None:
                self._playwright.stop()


def compute_ignored_flags(
    reused: bool,
    *,
    profile_dir: object = None,
    headless: object = None,
    chrome_path: object = None,
    no_sandbox: object = None,
) -> list[str]:
    """Return explicit launch flags that cannot affect an attached Chrome."""
    if not reused:
        return []
    values = (
        ('--profile-dir', profile_dir),
        ('--headless', headless),
        ('--chrome-path', chrome_path),
        ('--no-sandbox', no_sandbox),
    )
    return [flag for flag, value in values if value is not None]


def _chrome_candidates() -> list[str]:
    import platform

    system = platform.system()
    if system == 'Darwin':
        return CHROME_CANDIDATES_MAC
    if system == 'Windows':
        return CHROME_CANDIDATES_WIN
    return CHROME_CANDIDATES_LINUX


def find_chrome(explicit: Optional[str]) -> Optional[str]:
    """Find Chrome using an explicit path, CHROME_PATH, then system paths."""
    if explicit:
        return explicit if Path(explicit).is_file() else None
    env_path = os.environ.get('CHROME_PATH')
    if env_path and Path(env_path).is_file():
        return env_path
    for candidate in _chrome_candidates():
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def cdp_ready(url: str) -> bool:
    """Return whether a Chrome DevTools endpoint answers ``/json/version``."""
    try:
        with urlrequest.urlopen(f'{url.rstrip("/")}/json/version', timeout=2.0) as response:
            return response.status == 200
    except (urlerror.URLError, urlerror.HTTPError, TimeoutError, ConnectionError, OSError):
        return False


def _should_be_headless(mode: Optional[str]) -> bool:
    if mode == 'on':
        return True
    if mode in (None, 'off'):
        return False
    return not os.environ.get('DISPLAY')


def _should_disable_sandbox(no_sandbox: Optional[bool]) -> bool:
    if no_sandbox:
        return True
    try:
        if os.geteuid() == 0:
            return True
    except AttributeError:
        pass
    return Path('/.dockerenv').exists()


def _launch_chrome(
    chrome_path: str,
    cdp_url: str,
    profile_dir: Path,
    *,
    headless: Optional[str],
    window_size: str,
    no_sandbox: Optional[bool],
) -> subprocess.Popen:
    port = urlparse(cdp_url).port or 9222
    profile_dir.mkdir(parents=True, exist_ok=True)
    args = [
        chrome_path,
        f'--remote-debugging-port={port}',
        f'--user-data-dir={profile_dir}',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-features=Translate',
        f'--window-size={window_size}',
    ]
    if _should_be_headless(headless):
        args.extend(['--headless=new', '--disable-gpu'])
    if _should_disable_sandbox(no_sandbox):
        args.append('--no-sandbox')
    return subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def _wait_for_cdp(cdp_url: str, profile_dir: Path, process: subprocess.Popen) -> None:
    deadline = time.monotonic() + CDP_READY_TIMEOUT_S
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f'Chrome exited immediately (code {process.returncode}). '
                'Profile may be locked by another Chrome window. '
                f'Profile path: {profile_dir}. CDP URL: {cdp_url}. '
                'Close other Chrome instances using this profile, or pass a different --profile-dir.'
            )
        if cdp_ready(cdp_url):
            return
        time.sleep(CDP_POLL_INTERVAL_S)
    raise RuntimeError(
        f'CDP at {cdp_url} did not become ready within {CDP_READY_TIMEOUT_S}s. '
        f'Profile path: {profile_dir}. Check that the port is free and Chrome can launch.'
    )


def attach_or_launch(
    cdp_url: str,
    profile_dir: str,
    *,
    headless: Optional[str],
    window_size: str,
    no_sandbox: Optional[bool],
    chrome_path: Optional[str],
) -> ChromeSession:
    """Attach to ready CDP or launch Chrome with the required shared profile."""
    from playwright.sync_api import sync_playwright

    reused = cdp_ready(cdp_url)
    ignored = compute_ignored_flags(
        reused,
        profile_dir=profile_dir,
        headless=headless,
        chrome_path=chrome_path,
        no_sandbox=no_sandbox,
    )
    if reused:
        print(
            f'[chrome-cdp] CDP already ready at {cdp_url}; reusing existing Chrome',
            file=sys.stderr,
        )
        if ignored:
            print(
                f'[chrome-cdp] warning: ignored flags while reusing CDP: {", ".join(ignored)}',
                file=sys.stderr,
            )
    else:
        executable = find_chrome(chrome_path)
        if not executable:
            raise RuntimeError(
                'System Chrome not found. Tried: '
                f'{", ".join(_chrome_candidates())}. Install Chrome or pass --chrome-path.'
            )
        profile = Path(profile_dir).expanduser()
        process = _launch_chrome(
            executable,
            cdp_url,
            profile,
            headless=headless,
            window_size=window_size,
            no_sandbox=no_sandbox,
        )
        _wait_for_cdp(cdp_url, profile, process)

    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.connect_over_cdp(cdp_url)
    except Exception:
        playwright.stop()
        raise
    return ChromeSession(
        browser=browser,
        launched=not reused,
        ignored_flags=ignored,
        cdp_url=cdp_url,
        _playwright=playwright,
    )


def launch_isolated(chrome_path: Optional[str] = None, headless: bool = True) -> ChromeSession:
    """Launch Chrome with Playwright's temporary profile, closed by session.close()."""
    from playwright.sync_api import sync_playwright

    executable = find_chrome(chrome_path)
    if not executable:
        raise RuntimeError('Chrome executable not found; set CHROME_PATH or pass --chrome-path')
    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.launch(
            executable_path=executable,
            headless=headless,
            args=['--allow-file-access-from-files'],
        )
    except Exception:
        playwright.stop()
        raise
    return ChromeSession(
        browser=browser,
        launched=True,
        ignored_flags=[],
        _playwright=playwright,
    )
