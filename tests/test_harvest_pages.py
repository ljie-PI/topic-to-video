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

import harvest_manifest


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
        elif self.path == '/clip.mp4':
            body = self.server.video_bytes
            content_type = 'video/mp4'
        elif self.path == '/':
            self.server.page_requests += 1
            body = b'<!doctype html><title>Harvest fixture</title><img src="/pixel.png"><video src="/clip.mp4"></video>'
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
    clip = tmp_path / 'fixture.mp4'
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi',
        '-i', 'testsrc=size=64x48:rate=10', '-t', '1', '-pix_fmt', 'yuv420p', str(clip),
    ], check=True, timeout=30)
    server = ThreadingHTTPServer(('127.0.0.1', 0), _PageHandler)
    server.page_requests = 0
    server.video_bytes = clip.read_bytes()
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
        assert recording['duration_seconds'] > 0
        assert 'duration_sec' not in recording
        assert recording['width'] == 1280
        assert recording['height'] == 720
        assert Path(output_dir / recording['local_path']).is_file()
        assert server.page_requests == 1
        assert proc.stderr.count(f'loaded {url}') == 1
        assert json.loads(proc.stdout)['chrome'] == {
            'cdp_url': cdp_url,
            'reused': False,
            'ignored_flags': [],
        }
        assert len(entry['images']) == 1
        assert Path(output_dir / entry['images'][0]['local_path']).is_file()
        assert len(entry['videos']) == 1
        native = entry['videos'][0]
        assert native['width'] == 64
        assert native['height'] == 48
        assert native['duration_seconds'] == 1.0
        assert Path(output_dir / native['local_path']).is_file()
        assert manifest['version'] == 2
        assert len(manifest['harvest_batches']) == 1

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


def test_direct_video_batches_upsert_without_erasing_papers(tmp_path: Path):
    harvest_dir = tmp_path / 'harvest_page'
    harvest_manifest.upsert_entries(harvest_dir, [{
        'slug': 'main-paper', 'success': True, 'source_type': 'paper_pdf',
        'paper_metadata': {'full_markdown_path': 'main-paper/mineru/full.md'},
        'images': [], 'videos': [],
    }])
    urls = [
        'https://www.youtube.com/watch?v=first123',
        'https://www.youtube.com/watch?v=second123',
    ]
    for url in urls:
        proc = subprocess.run([
            sys.executable, str(SCRIPT), '--urls', url,
            '--output-dir', str(harvest_dir), '--profile-dir', str(tmp_path / 'unused-profile'),
        ], capture_output=True, text=True, timeout=30, check=False)
        assert proc.returncode == 0, proc.stderr
        batch = json.loads(proc.stdout)
        assert [entry['url'] for entry in batch['entries']] == [url]
        assert batch['succeeded'] == 1

    manifest = json.loads((harvest_dir / 'manifest.json').read_text(encoding='utf-8'))
    assert {entry['slug'] for entry in manifest['entries']} == {
        'main-paper', harvest_manifest.slug_for_url(urls[0]), harvest_manifest.slug_for_url(urls[1]),
    }
    assert len(manifest['harvest_batches']) == 2
    assert [batch['urls'] for batch in manifest['harvest_batches']] == [[urls[0]], [urls[1]]]
    assert len(manifest['pending_downloads']) == 2
    for entry in manifest['entries']:
        for video in entry['videos']:
            assert not Path(video['suggested_output_dir']).is_absolute()
