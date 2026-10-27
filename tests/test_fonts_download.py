"""CLI tests for scripts/fonts-download.sh.

Installing copies the fonts committed under resources/fonts/<theme>/ and never
touches the network; --refresh re-downloads a theme's families and is tested
against a local HTTP server standing in for Google Fonts (FONTS_CSS2_URL),
writing into a tmp resources dir (FONTS_RESOURCES_DIR).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'fonts-download.sh'
DESIGNS = sorted(p.parent.name for p in (REPO_ROOT / 'modules' / 'designs').glob('*/*.json'))


def load_fonts(design: str) -> dict:
    path = REPO_ROOT / 'modules' / 'designs' / design / f'{design}.json'
    return json.loads(path.read_text(encoding='utf-8'))['fonts']
# Unreachable on purpose: install must never fetch anything.
NO_NETWORK = {'FONTS_CSS2_URL': 'http://127.0.0.1:9/css2'}


def run(*args: str, env: dict[str, str] | None = None, cwd: Path = REPO_ROOT) -> tuple[subprocess.CompletedProcess, dict]:
    proc = subprocess.run(
        ['bash', str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env={**os.environ, **(env or {})},
    )
    lines = proc.stdout.strip().splitlines()
    assert len(lines) == 1, proc.stdout
    return proc, json.loads(lines[0])


def css_references(css: str) -> list[str]:
    return re.findall(r'url\(([^)]+)\)', css)


def test_every_design_has_complete_vendored_fonts():
    for design in DESIGNS:
        manifest = load_fonts(design)
        vendored = REPO_ROOT / 'resources' / 'fonts' / design
        css = (vendored / manifest['css_filename']).read_text()
        refs = css_references(css)
        assert refs, design
        for ref in refs:
            assert not ref.startswith('http'), (design, ref)
            assert (vendored / ref).is_file(), (design, ref)


def test_install_copies_vendored_fonts_without_network(tmp_path: Path):
    proc, result = run(str(tmp_path / 'fonts'), '--theme', 'modules/designs/github', env=NO_NETWORK)
    assert proc.returncode == 0, proc.stderr
    assert result['success'] is True and result['mode'] == 'install'
    css = (tmp_path / 'fonts' / 'github-fonts.css').read_text()
    for ref in css_references(css):
        assert (tmp_path / 'fonts' / ref).is_file()
    assert len(result['files']) == len(list((tmp_path / 'fonts').iterdir()))


def test_install_legacy_named_style(tmp_path: Path):
    proc, result = run(str(tmp_path), 'default', env=NO_NETWORK)
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / 'default-fonts.css').is_file()
    assert "'NotoSansSC'" in (tmp_path / 'default-fonts.css').read_text()


def test_install_dry_run_writes_nothing(tmp_path: Path):
    target = tmp_path / 'fonts'
    proc, result = run(str(target), '--theme', 'producthunt', '--dry-run', env=NO_NETWORK)
    assert proc.returncode == 0, proc.stderr
    assert result['files'] and not target.exists()


def test_unknown_theme_is_a_clean_usage_error(tmp_path: Path):
    proc, result = run(str(tmp_path), '--theme', 'nosuch')
    assert proc.returncode == 2
    assert result['success'] is False
    assert "unknown theme 'nosuch'" in result['error']
    assert 'import' not in result['error'] and 'Traceback' not in proc.stderr


def test_missing_vendored_fonts_point_at_refresh(tmp_path: Path):
    proc, result = run(str(tmp_path / 'out'), '--theme', 'github', env={'FONTS_RESOURCES_DIR': str(tmp_path / 'empty')})
    assert proc.returncode == 1
    assert '--refresh --theme github' in result['error']


def test_refresh_requires_a_theme():
    proc, result = run('--refresh')
    assert proc.returncode == 2 and result['success'] is False


@pytest.mark.parametrize('design', ['default', 'github', 'producthunt'])
def test_refresh_dry_run_uses_every_family_from_the_design_json(design: str):
    proc, result = run('--refresh', '--theme', design, '--dry-run')

    assert proc.returncode == 0, proc.stderr
    assert result['success'] is True and result['files'] == []
    for family in load_fonts(design)['css2_families']:
        assert family in proc.stderr


def test_font_family_names_are_not_hardcoded_in_the_downloader():
    source = SCRIPT.read_text(encoding='utf-8')

    assert 'Noto Sans' not in source
    assert 'IBM Plex' not in source


def test_refresh_rejects_contract_paths(tmp_path: Path):
    copy = tmp_path / 'modules' / 'designs' / 'default'
    copy.mkdir(parents=True)
    (copy / 'default.json').write_text((REPO_ROOT / 'modules/designs/default/default.json').read_text())
    proc, result = run('--refresh', '--theme', str(copy), env={'FONTS_RESOURCES_DIR': str(tmp_path / 'res')})
    assert proc.returncode == 2
    assert 'theme name under modules/designs' in result['error']
    assert not (tmp_path / 'res').exists()


class FakeGoogleFonts(BaseHTTPRequestHandler):
    """Serves one css2 response whose two src urls point back at this server."""

    font_bytes = b'wOF2-fake-font'

    def do_GET(self):  # noqa: N802 - http.server API
        port = self.server.server_address[1]
        if self.path.startswith('/css2'):
            body = (
                "@font-face { font-family: 'Noto Sans SC'; src: url(http://127.0.0.1:%d/a.woff2) format('woff2'); }\n"
                "@font-face { font-family: 'IBM Plex Mono'; src: url(http://127.0.0.1:%d/b.woff2) format('woff2'); }\n"
                % (port, port)
            ).encode()
        elif self.path.endswith('.woff2'):
            body = self.font_bytes
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence the test server
        pass


def test_named_style_ignores_same_named_file_in_cwd(tmp_path: Path):
    (tmp_path / 'github').write_text('not a manifest')
    proc, result = run('out', 'github', env=NO_NETWORK, cwd=tmp_path)
    assert proc.returncode == 0, result
    assert (tmp_path / 'out' / 'github-fonts.css').is_file()


class FakeGoogleFontsMissingFont(BaseHTTPRequestHandler):
    """Serves the css2 response but 404s every font file."""

    def do_GET(self):  # noqa: N802 - http.server API
        if not self.path.startswith('/css2'):
            self.send_error(404)
            return
        body = b"@font-face { src: url(http://127.0.0.1:%d/a.woff2); }" % self.server.server_address[1]
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def test_failed_refresh_keeps_committed_fonts_and_leaves_no_debris(tmp_path: Path):
    server = ThreadingHTTPServer(('127.0.0.1', 0), FakeGoogleFontsMissingFont)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    resources = tmp_path / 'resources'
    (resources / 'default').mkdir(parents=True)
    (resources / 'default' / 'default-fonts.css').write_text('kept')
    try:
        proc, result = run('--refresh', '--theme', 'default', env={
            'FONTS_RESOURCES_DIR': str(resources),
            'FONTS_CSS2_URL': f'http://127.0.0.1:{server.server_address[1]}/css2',
        })
    finally:
        server.shutdown()
    assert proc.returncode == 1 and result['success'] is False
    assert (resources / 'default' / 'default-fonts.css').read_text() == 'kept'
    assert sorted(p.name for p in resources.iterdir()) == ['default']


def test_refresh_downloads_into_resources_and_replaces_stale_files(tmp_path: Path):
    server = ThreadingHTTPServer(('127.0.0.1', 0), FakeGoogleFonts)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        resources = tmp_path / 'resources'
        (resources / 'default').mkdir(parents=True)
        (resources / 'default' / 'stale.woff2').write_bytes(b'old')
        env = {
            'FONTS_RESOURCES_DIR': str(resources),
            'FONTS_CSS2_URL': f'http://127.0.0.1:{server.server_address[1]}/css2',
        }
        proc, result = run('--refresh', '--theme', 'default', env=env)
    finally:
        server.shutdown()
    assert proc.returncode == 0, proc.stderr
    assert result['mode'] == 'refresh'
    out = resources / 'default'
    assert not (out / 'stale.woff2').exists()
    css = (out / 'default-fonts.css').read_text()
    assert "'NotoSansSC'" in css and "'IBMPlexMono'" in css  # default renames families
    refs = css_references(css)
    assert len(refs) == 2
    for ref in refs:
        assert (out / ref).read_bytes() == FakeGoogleFonts.font_bytes
