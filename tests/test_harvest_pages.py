"""CLI tests for the shared-profile page harvester."""
from __future__ import annotations

import base64
import json
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'harvest-pages.py'


def test_profile_dir_is_required(tmp_path: Path):
    proc = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            '--urls', 'http://127.0.0.1:1/',
            '--output-dir', str(tmp_path / 'output'),
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


class _PageHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server API
        if self.path == '/pixel.png':
            body = base64.b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk'
                '+A8AAQUBAScY42YAAAAASUVORK5CYII='
            )
            content_type = 'image/png'
        elif self.path == '/':
            self.server.page_requests += 1
            body = b'<!doctype html><title>Harvest fixture</title><img src="/pixel.png">'
            content_type = 'text/html; charset=utf-8'
        else:
            self.send_response(204)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def _unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def _close_test_chrome(cdp_url: str) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=5000)
        browser.new_browser_cdp_session().send('Browser.close')


def test_local_page_loads_once_and_manifest_contains_image(
    tmp_path: Path,
    require_chrome: None,
    require_ffmpeg: None,
):
    server = ThreadingHTTPServer(('127.0.0.1', 0), _PageHandler)
    server.page_requests = 0
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    cdp_url = f'http://127.0.0.1:{_unused_port()}'
    profile_dir = tmp_path / 'profile'
    output_dir = tmp_path / 'output'
    url = f'http://127.0.0.1:{server.server_port}/'
    try:
        proc = subprocess.run(
            [
                sys.executable, str(SCRIPT),
                '--urls', url,
                '--output-dir', str(output_dir),
                '--profile-dir', str(profile_dir),
                '--cdp-url', cdp_url,
                '--headless', 'on',
                '--no-sandbox',
                '--scroll-duration', '5',
                '--min-image-width', '1',
                '--min-image-height', '1',
            ],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )

        assert proc.returncode == 0, proc.stderr
        manifest = json.loads((output_dir / 'manifest.json').read_text(encoding='utf-8'))
        entry = next(item for item in manifest['entries'] if item['url'] == url)
        assert entry['success'] is True
        recording = entry['scroll_recording']
        assert recording is not None
        assert recording['method'] == 'playwright'
        assert server.page_requests == 1
        assert proc.stderr.count(f'loaded {url}') == 1
        assert manifest['chrome'] == {
            'cdp_url': cdp_url,
            'reused': False,
            'ignored_flags': [],
        }
        assert len(entry['images']) == 1
        assert Path(entry['images'][0]['local_path']).is_file()

        reused_output_dir = tmp_path / 'reused-output'
        reused = subprocess.run(
            [
                sys.executable, str(SCRIPT),
                '--urls', url,
                '--output-dir', str(reused_output_dir),
                '--profile-dir', str(profile_dir),
                '--cdp-url', cdp_url,
                '--headless', 'on',
                '--no-sandbox',
                '--no-scroll-record',
                '--min-image-width', '1',
                '--min-image-height', '1',
            ],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        assert reused.returncode == 0, reused.stderr
        assert 'warning' in reused.stderr.lower()
        assert '--headless' in reused.stderr
        reused_manifest = json.loads(reused.stdout)
        assert reused_manifest['chrome'] == {
            'cdp_url': cdp_url,
            'reused': True,
            'ignored_flags': ['--profile-dir', '--headless', '--no-sandbox'],
        }
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
        if profile_dir.exists():
            _close_test_chrome(cdp_url)
