"""CLI and shared-profile tests for the page harvester."""
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import chrome_cdp
import harvest_manifest


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'harvest-pages.py'
PIXEL_PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk'
    '+A8AAQUBAScY42YAAAAASUVORK5CYII='
)
# The fixture asks the server whether the page saw the profile's localStorage:
# a fetch keeps the answer out of the harvested media, so the entry still holds
# exactly one image.
LOGIN_PAGE = b'''<!doctype html><title>Gated fixture</title>
<div id="who">anonymous</div>
<img src="/gated.png">
<script>
  const logged = localStorage.getItem('user') === 'alice';
  document.getElementById('who').textContent = logged ? 'logged-in' : 'anonymous';
  fetch('/marker?logged=' + (logged ? 'yes' : 'no'));
</script>'''


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
            body = PIXEL_PNG
            content_type = 'image/png'
        elif self.path == '/clip.mp4':
            body = self.server.video_bytes
            content_type = 'video/mp4'
        elif self.path == '/gated.png':
            if 'session=1' in (self.headers.get('Cookie') or ''):
                self.server.gated_requests += 1
                body = PIXEL_PNG
                content_type = 'image/png'
            else:
                # 未继承 profile 登录态的证据：受保护媒体只能匿名读到 403。
                self.server.gated_anonymous += 1
                self.send_response(403)
                self.end_headers()
                return
        elif self.path == '/login-required':
            self.server.login_page_requests += 1
            body = LOGIN_PAGE
            content_type = 'text/html; charset=utf-8'
        elif self.path.startswith('/marker'):
            self.server.logged_markers.append(
                'yes' if self.path.endswith('=yes') else 'no'
            )
            self.send_response(204)
            self.end_headers()
            return
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


def _start_fixture_server(video_bytes: bytes = b'') -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = ThreadingHTTPServer(('127.0.0.1', 0), _PageHandler)
    server.page_requests = 0
    server.video_bytes = video_bytes
    server.login_page_requests = 0
    server.gated_requests = 0
    server.gated_anonymous = 0
    server.logged_markers = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _stop_fixture_server(server: ThreadingHTTPServer, thread: threading.Thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def _write_urls_file(path: Path, urls: list[str]) -> Path:
    path.write_text('\n'.join(urls) + '\n', encoding='utf-8')
    return path


def _run_harvest(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, timeout=90, check=False,
    )


def _reset_fixture_counters(server: ThreadingHTTPServer) -> None:
    """预热页自己也会打一次请求；清零后只统计本用例真正关心的加载。"""
    server.page_requests = 0
    server.login_page_requests = 0
    server.gated_requests = 0
    server.gated_anonymous = 0
    server.logged_markers.clear()


def _launch_logged_in_chrome(tmp_path: Path, page_url: str):
    """启动一个共享 profile 的 Chrome，并在它的默认 context 里写入登录态。

    先写 cookie 再导航，避免预热页自己产生匿名请求；保留这个标签页不关：
    localStorage 属于已访问的 origin，页面关闭后 storage_state() 不一定
    还能读到它。
    """
    cdp_url = f'http://127.0.0.1:{_unused_port()}'
    session = chrome_cdp.attach_or_launch(
        cdp_url,
        str(tmp_path / 'profile'),
        headless='on',
        window_size='1680,1680',
        no_sandbox=True,
        chrome_path=None,
    )
    context = session.browser.contexts[0]
    context.add_cookies([{'name': 'session', 'value': '1', 'url': page_url}])
    page = context.new_page()
    page.goto(page_url, wait_until='domcontentloaded')
    page.wait_for_load_state('networkidle', timeout=5000)
    page.evaluate("localStorage.setItem('user', 'alice')")
    return session, cdp_url, page


def _load_harvester():
    """按路径加载带 dash 的脚本，以便在本进程里验证兜底录制路径。"""
    spec = importlib.util.spec_from_file_location('harvest_pages_under_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _close_test_chrome(cdp_url: str) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=5000)
        browser.new_browser_cdp_session().send('Browser.close')


def test_local_page_harvests_media_with_available_recording_backend(
    tmp_path: Path,
    require_chrome: None,
    require_ffmpeg: None,
):
    clip = tmp_path / 'fixture.mp4'
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi',
        '-i', 'testsrc=size=64x48:rate=10', '-t', '1', '-pix_fmt', 'yuv420p', str(clip),
    ], check=True, timeout=30)
    server, server_thread = _start_fixture_server(video_bytes=clip.read_bytes())
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
        assert recording['method'] in {'playwright', 'cdp_screencast'}
        # Playwright recording needs its own ffmpeg, not just the system ffmpeg.
        # Its documented CDP fallback reloads the page after primary recording fails.
        expected_loads = 1 if recording['method'] == 'playwright' else 2
        if recording['method'] == 'cdp_screencast':
            assert 'primary scroll-record failed' in proc.stderr
        assert recording['duration_seconds'] > 0
        assert 'duration_sec' not in recording
        assert recording['width'] == 1280
        assert recording['height'] == 720
        assert Path(output_dir / recording['local_path']).is_file()
        assert server.page_requests == expected_loads
        assert proc.stderr.count(f'loaded {url}') == expected_loads
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


def test_reharvesting_same_direct_video_preserves_applied_download(tmp_path: Path):
    harvest_dir = tmp_path / 'harvest_page'
    url = 'https://www.youtube.com/watch?v=shared123'
    command = [
        sys.executable, str(SCRIPT), '--urls', url,
        '--output-dir', str(harvest_dir), '--profile-dir', str(tmp_path / 'unused-profile'),
    ]
    first = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    assert first.returncode == 0, first.stderr
    slug = harvest_manifest.slug_for_url(url)
    video_path = harvest_dir / slug / 'videos' / 'shared123.mp4'
    subtitle_path = harvest_dir / slug / 'videos' / 'shared123.en.srt'
    harvest_manifest.apply_download(harvest_dir, url, {
        'files': [str(video_path), str(subtitle_path)],
        'videos': [{
            'path': str(video_path), 'width': 1280, 'height': 720, 'duration_seconds': 2.5,
        }],
    })

    second = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)

    assert second.returncode == 0, second.stderr
    batch = json.loads(second.stdout)
    downloaded = batch['entries'][0]['videos'][0]
    assert downloaded['download_required'] is False
    assert downloaded['downloaded'] is True
    assert downloaded['local_path'] == f'{slug}/videos/shared123.mp4'
    assert downloaded['subtitle_path'] == f'{slug}/videos/shared123.en.srt'
    assert downloaded['id'] == 'shared123'
    assert downloaded['width'] == 1280
    assert downloaded['height'] == 720
    assert downloaded['duration_seconds'] == 2.5
    assert 'pending_downloads' not in batch
    manifest = json.loads((harvest_dir / 'manifest.json').read_text(encoding='utf-8'))
    assert len(manifest['entries']) == 1
    assert manifest['entries'][0] == batch['entries'][0]
    assert manifest['pending_downloads'] == []
    assert len(manifest['harvest_batches']) == 2


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


DIRECT_A = 'https://www.youtube.com/watch?v=file000001'
DIRECT_B = 'https://www.youtube.com/watch?v=file000002'


def test_urls_file_matches_urls_argument_and_keeps_order(tmp_path: Path):
    urls_file = tmp_path / 'harvest-urls.txt'
    # BOM、空行、重复项、行首尾空白：都应归一到与 --urls 相同的结果。
    urls_file.write_text(
        f'\ufeff{DIRECT_A}\n\n   \n{DIRECT_A}\n  {DIRECT_B}  \n',
        encoding='utf-8',
    )
    from_file = _run_harvest(
        '--urls-file', str(urls_file),
        '--output-dir', str(tmp_path / 'from-file'),
        '--profile-dir', str(tmp_path / 'unused-profile'),
    )
    from_args = _run_harvest(
        '--urls', DIRECT_A, DIRECT_B, DIRECT_A,
        '--output-dir', str(tmp_path / 'from-args'),
        '--profile-dir', str(tmp_path / 'unused-profile'),
    )

    assert from_file.returncode == 0, from_file.stderr
    assert from_args.returncode == 0, from_args.stderr
    file_batch = json.loads(from_file.stdout)
    args_batch = json.loads(from_args.stdout)
    assert [entry['url'] for entry in file_batch['entries']] == [DIRECT_A, DIRECT_B]
    assert [entry['url'] for entry in args_batch['entries']] == [DIRECT_A, DIRECT_B]
    assert file_batch['batch_size'] == args_batch['batch_size'] == 2
    assert len(file_batch['pending_downloads']) == 2


def test_urls_file_errors_are_reported_before_chrome_and_output_dir(tmp_path: Path):
    valid_file = _write_urls_file(tmp_path / 'ok-urls.txt', [DIRECT_A])
    output_dir = tmp_path / 'missing-file-output'

    missing = _run_harvest(
        '--urls-file', str(tmp_path / 'absent.txt'),
        '--output-dir', str(output_dir),
        '--profile-dir', str(tmp_path / 'unused-profile'),
    )
    assert missing.returncode == 2
    missing_result = json.loads(missing.stdout)
    assert missing_result['success'] is False
    assert 'not found' in missing_result['error']
    assert not output_dir.exists()

    empty_file = tmp_path / 'empty-urls.txt'
    empty_file.write_text('\n   \n\n', encoding='utf-8')
    empty = _run_harvest(
        '--urls-file', str(empty_file),
        '--output-dir', str(tmp_path / 'empty-file-output'),
        '--profile-dir', str(tmp_path / 'unused-profile'),
    )
    assert empty.returncode == 2
    assert 'no URLs' in json.loads(empty.stdout)['error']

    not_utf8 = tmp_path / 'not-utf8.txt'
    not_utf8.write_bytes(b'\xff\xfehttps://example.com/\n')
    bad_encoding = _run_harvest(
        '--urls-file', str(not_utf8),
        '--output-dir', str(tmp_path / 'encoding-output'),
        '--profile-dir', str(tmp_path / 'unused-profile'),
    )
    assert bad_encoding.returncode == 2
    assert 'UTF-8' in json.loads(bad_encoding.stdout)['error']

    both = _run_harvest(
        '--urls', DIRECT_A, '--urls-file', str(valid_file),
        '--output-dir', str(tmp_path / 'both-output'),
        '--profile-dir', str(tmp_path / 'unused-profile'),
    )
    assert both.returncode == 2
    assert '--urls-file' in json.loads(both.stdout)['error']

    neither = _run_harvest(
        '--output-dir', str(tmp_path / 'neither-output'),
        '--profile-dir', str(tmp_path / 'unused-profile'),
    )
    assert neither.returncode == 2
    assert '--urls' in json.loads(neither.stdout)['error']


def test_local_storage_read_rejects_a_tab_that_navigated_away(require_chrome: None):
    """选中以后、读取之前跳走：不能把新站点的数据贴上旧 origin 的标签。"""
    module = _load_harvester()
    server_a, thread_a = _start_fixture_server()
    server_b, thread_b = _start_fixture_server()
    origin_a = f'http://127.0.0.1:{server_a.server_port}'
    origin_b = f'http://127.0.0.1:{server_b.server_port}'
    session = chrome_cdp.launch_isolated(headless=True)
    try:
        context = session.browser.new_context()
        page = context.new_page()
        page.goto(f'{origin_a}/login-required', wait_until='domcontentloaded')
        page.evaluate("localStorage.setItem('session_token', 'origin-A')")
        page.goto(f'{origin_b}/login-required', wait_until='domcontentloaded')
        page.evaluate("localStorage.setItem('session_token', 'origin-B')")

        class ReportedAsOriginA:
            """真实标签页已在 B，而选中时记录的 url 仍是 A。"""

            def __init__(self, real_page, reported_url):
                self._page = real_page
                self.url = reported_url

            def evaluate(self, script, arg=None):
                return self._page.evaluate(script, arg)

        profile_context = SimpleNamespace(
            pages=[ReportedAsOriginA(page, f'{origin_a}/login-required')],
            cookies=lambda: [{'name': 'session', 'value': '1'}],
        )

        state, warning = module.profile_storage_state(profile_context, [origin_a])

        assert state['origins'] == [], 'B 的 localStorage 被归到了 A'
        assert warning and 'navigated' in warning
        assert 'origin-B' not in warning
    finally:
        session.close()
        _stop_fixture_server(server_a, thread_a)
        _stop_fixture_server(server_b, thread_b)


def test_profile_state_read_failures_are_reported(tmp_path: Path):
    module = _load_harvester()

    # 没有 profile context（比如整批都是视频直链）不是错误。
    assert module.profile_storage_state(None) == (None, None)

    class BrokenContext:
        pages: list = []

        def cookies(self):
            raise RuntimeError('profile unavailable')

    state, warning = module.profile_storage_state(BrokenContext(), ['https://example.com'])
    assert state is None
    assert 'profile unavailable' in warning

    class CookiesOnlyContext:
        pages: list = []

        def cookies(self):
            return [{'name': 'session', 'value': '1'}]

    # 没有同 origin 的标签页时只继承 cookies：能读到就够，不是错误。
    state, warning = module.profile_storage_state(CookiesOnlyContext(), ['https://example.com'])
    assert warning is None
    assert state == {'cookies': [{'name': 'session', 'value': '1'}], 'origins': []}


def test_harvest_inherits_the_profile_login_state_for_pages_and_media(
    tmp_path: Path, require_chrome: None,
):
    server, server_thread = _start_fixture_server()
    page_url = f'http://127.0.0.1:{server.server_port}/login-required'
    output_dir = tmp_path / 'output'
    session, cdp_url, _page = _launch_logged_in_chrome(tmp_path, page_url)
    _reset_fixture_counters(server)
    try:
        proc = _run_harvest(
            '--urls-file', str(_write_urls_file(tmp_path / 'harvest-urls.txt', [page_url])),
            '--output-dir', str(output_dir),
            '--profile-dir', str(tmp_path / 'ignored-profile'),
            '--cdp-url', cdp_url,
            '--scroll-duration', '5',
            '--min-image-width', '1',
            '--min-image-height', '1',
        )

        assert proc.returncode == 0, proc.stderr
        entry = json.loads(proc.stdout)['entries'][0]
        assert 'login state' in proc.stderr
        # localStorage 与 cookie 都必须真正落到采集 context 上。
        assert 'logged-in' in entry['text_excerpt']
        harvest_loads = server.login_page_requests
        assert harvest_loads >= 1
        assert server.logged_markers == ['yes'] * harvest_loads
        assert server.gated_anonymous == 0
        assert len(entry['images']) == 1
        assert Path(output_dir / entry['images'][0]['local_path']).is_file()
    finally:
        session.close()
        _stop_fixture_server(server, server_thread)
        _close_test_chrome(cdp_url)


def test_cdp_fallback_recording_keeps_the_profile_login_state(
    tmp_path: Path, require_chrome: None, require_ffmpeg: None, monkeypatch,
):
    module = _load_harvester()
    server, server_thread = _start_fixture_server()
    page_url = f'http://127.0.0.1:{server.server_port}/login-required'
    session, cdp_url, _page = _launch_logged_in_chrome(tmp_path, page_url)
    _reset_fixture_counters(server)
    try:
        browser = session.browser
        storage_state, state_warning = module.profile_storage_state(
            browser.contexts[0], [module.page_origin(page_url)],
        )
        assert state_warning is None
        assert storage_state and storage_state['origins']

        def forced_primary_failure(*args, **kwargs):
            raise RuntimeError('forced primary recording failure')

        monkeypatch.setattr(module, 'primary_scroll_record', forced_primary_failure)
        entry = module.harvest_one(
            browser, page_url, 'gated', tmp_path / 'harvest_page' / 'gated',
            argparse.Namespace(
                scroll_record=True, scroll_duration=5, page_load_timeout=30,
                max_images_per_url=20, max_videos_per_url=5,
                min_image_width=1, min_image_height=1,
            ),
            (1280, 720), storage_state,
        )

        recording = entry['scroll_recording']
        assert recording is not None and recording['method'] == 'cdp_screencast'
        # 主路径与兜底路径各加载一次；两次都必须看到登录态。
        harvest_loads = server.login_page_requests
        assert harvest_loads == 2
        assert server.logged_markers == ['yes', 'yes']
        assert server.gated_anonymous == 0
    finally:
        session.close()
        _stop_fixture_server(server, server_thread)
        _close_test_chrome(cdp_url)
