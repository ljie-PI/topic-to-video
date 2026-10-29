"""CLI tests for scripts/fonts-download.sh.

Each theme commits only its CSS under resources/fonts/<theme>/; the WOFF2 files
it references live once in the shared pool resources/fonts/files/. Installing
copies the CSS plus the pool files it references and never touches the
network; --refresh re-downloads a theme's families and is tested against a
local HTTP server standing in for Google Fonts (FONTS_CSS2_URL), writing into a
tmp resources dir (FONTS_RESOURCES_DIR).
"""
from __future__ import annotations

import hashlib
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


FONTS = REPO_ROOT / 'resources' / 'fonts'
POOL = FONTS / 'files'


def vendored_css(design: str) -> str:
    return (FONTS / design / load_fonts(design)['css_filename']).read_text()


def test_every_design_has_complete_vendored_fonts():
    for design in DESIGNS:
        refs = css_references(vendored_css(design))
        assert refs, design
        for ref in refs:
            assert re.fullmatch(r'[0-9a-f]{12}\.woff2', ref), (design, ref)
            assert (POOL / ref).is_file(), (design, ref)


def test_a_design_directory_holds_only_its_css():
    for design in DESIGNS:
        assert [p.name for p in (FONTS / design).iterdir()] == [load_fonts(design)['css_filename']]


def test_shared_pool_has_no_unreferenced_or_duplicate_files():
    referenced = {ref for design in DESIGNS for ref in css_references(vendored_css(design))}
    pooled = {p.name for p in POOL.iterdir()}
    assert pooled == referenced

    by_content: dict[str, list[str]] = {}
    for font in POOL.iterdir():
        by_content.setdefault(hashlib.sha256(font.read_bytes()).hexdigest(), []).append(font.name)
    assert [names for names in by_content.values() if len(names) > 1] == []


def test_designs_with_the_same_font_source_share_the_same_pool_files():
    by_source: dict[str, list[list[str]]] = {}
    for design in DESIGNS:
        manifest = load_fonts(design)
        source = json.dumps({k: manifest[k] for k in ('css2_families', 'rename')}, sort_keys=True)
        by_source.setdefault(source, []).append(css_references(vendored_css(design)))

    for refs in by_source.values():
        assert all(r == refs[0] for r in refs)


def test_install_copies_vendored_fonts_without_network(tmp_path: Path):
    proc, result = run(str(tmp_path / 'fonts'), '--theme', 'modules/designs/github', env=NO_NETWORK)
    assert proc.returncode == 0, proc.stderr
    assert result['success'] is True and result['mode'] == 'install'
    css = (tmp_path / 'fonts' / 'github-fonts.css').read_text()
    assert css == vendored_css('github')
    refs = css_references(css)
    for ref in refs:
        assert (tmp_path / 'fonts' / ref).read_bytes() == (POOL / ref).read_bytes()
    installed = sorted(p.name for p in (tmp_path / 'fonts').iterdir())
    assert installed == sorted(['github-fonts.css', *refs])
    assert len(result['files']) == len(installed)


def test_install_copies_only_the_files_the_design_references(tmp_path: Path):
    github = set(css_references(vendored_css('github')))
    default = set(css_references(vendored_css('default')))
    assert github != default  # the pool holds both; each install takes just its own

    run(str(tmp_path), '--theme', 'default', env=NO_NETWORK)

    assert {p.name for p in tmp_path.glob('*.woff2')} == default


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


def make_resources(root: Path, css: str, pool: dict[str, bytes]) -> Path:
    resources = root / 'resources'
    (resources / 'github').mkdir(parents=True)
    (resources / 'github' / 'github-fonts.css').write_text(css)
    if pool:
        (resources / 'files').mkdir()
    for name, data in pool.items():
        (resources / 'files' / name).write_bytes(data)
    return resources


def test_install_names_pool_files_missing_for_a_design(tmp_path: Path):
    resources = make_resources(
        tmp_path,
        "@font-face { src: url('have.woff2'); }\n@font-face { src: url(lost.woff2); }",
        {'have.woff2': b'x'},
    )

    proc, result = run(str(tmp_path / 'out'), '--theme', 'github', env={'FONTS_RESOURCES_DIR': str(resources)})

    assert proc.returncode == 1 and result['success'] is False
    assert 'lost.woff2' in result['error'] and 'have.woff2' not in result['error']
    assert '--refresh --theme github' in result['error']
    assert not (tmp_path / 'out').exists()


def test_install_installs_quoted_references(tmp_path: Path):
    resources = make_resources(tmp_path, "@font-face { src: url('q.woff2'); }", {'q.woff2': b'font'})

    proc, _ = run(str(tmp_path / 'out'), '--theme', 'github', env={'FONTS_RESOURCES_DIR': str(resources)})

    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / 'out' / 'q.woff2').read_bytes() == b'font'


@pytest.mark.parametrize('ref', ['../files/a.woff2', 'sub/a.woff2', 'https://example.test/a.woff2'])
def test_install_rejects_references_that_are_not_bare_pool_names(tmp_path: Path, ref: str):
    resources = make_resources(tmp_path, f'@font-face {{ src: url({ref}); }}', {'a.woff2': b'x'})

    proc, result = run(str(tmp_path / 'out'), '--theme', 'github', env={'FONTS_RESOURCES_DIR': str(resources)})

    assert proc.returncode == 1 and result['success'] is False
    assert 'bare file name' in result['error']
    assert not (tmp_path / 'out').exists()


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
            self.server.font_requests.append(self.path)
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


@pytest.fixture
def google_fonts():
    server = ThreadingHTTPServer(('127.0.0.1', 0), FakeGoogleFonts)
    server.font_requests = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server
    server.shutdown()


def refresh_env(resources: Path, server: ThreadingHTTPServer) -> dict[str, str]:
    return {
        'FONTS_RESOURCES_DIR': str(resources),
        'FONTS_CSS2_URL': f'http://127.0.0.1:{server.server_address[1]}/css2',
    }


def test_refresh_downloads_into_the_pool_and_replaces_the_theme_dir(tmp_path: Path, google_fonts):
    resources = tmp_path / 'resources'
    (resources / 'default').mkdir(parents=True)
    (resources / 'default' / 'stale.woff2').write_bytes(b'old')

    proc, result = run('--refresh', '--theme', 'default', env=refresh_env(resources, google_fonts))

    assert proc.returncode == 0, proc.stderr
    assert result['mode'] == 'refresh'
    out = resources / 'default'
    assert [p.name for p in out.iterdir()] == ['default-fonts.css']
    css = (out / 'default-fonts.css').read_text()
    assert "'NotoSansSC'" in css and "'IBMPlexMono'" in css  # default renames families
    refs = css_references(css)
    assert len(refs) == 2
    for ref in refs:
        assert (resources / 'files' / ref).read_bytes() == FakeGoogleFonts.font_bytes
    assert sorted(p.name for p in (resources / 'files').iterdir()) == sorted(refs)
    assert sorted(result['files']) == sorted(str(p.resolve()) for p in [out / 'default-fonts.css', *(resources / 'files' / r for r in refs)])
    assert sorted(p.name for p in resources.iterdir()) == ['default', 'files']  # no staging debris


def test_refresh_reuses_pool_files_across_designs(tmp_path: Path, google_fonts):
    resources = tmp_path / 'resources'
    env = refresh_env(resources, google_fonts)

    run('--refresh', '--theme', 'default', env=env)
    assert len(google_fonts.font_requests) == 2
    proc, _ = run('--refresh', '--theme', 'producthunt', env=env)

    assert proc.returncode == 0, proc.stderr
    assert len(google_fonts.font_requests) == 2  # producthunt downloaded nothing new
    assert css_references((resources / 'default' / 'default-fonts.css').read_text()) == css_references(
        (resources / 'producthunt' / 'producthunt-fonts.css').read_text()
    )
    assert len(list((resources / 'files').iterdir())) == 2


def test_refresh_prunes_pool_files_no_design_references(tmp_path: Path, google_fonts):
    resources = tmp_path / 'resources'
    (resources / 'files').mkdir(parents=True)
    (resources / 'files' / 'orphan.woff2').write_bytes(b'unused')
    (resources / 'files' / 'other.woff2').write_bytes(b'used by another theme')
    (resources / 'other').mkdir()
    (resources / 'other' / 'other-fonts.css').write_text('@font-face { src: url(other.woff2); }')

    proc, _ = run('--refresh', '--theme', 'default', env=refresh_env(resources, google_fonts))

    assert proc.returncode == 0, proc.stderr
    pooled = {p.name for p in (resources / 'files').iterdir()}
    assert 'orphan.woff2' not in pooled
    assert 'other.woff2' in pooled
    assert len(pooled) == 3  # the two new fonts plus the other theme's
