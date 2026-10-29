#!/usr/bin/env bash
# Install the vendored WOFF2 fonts of a topic-to-video theme into a project.
#
# Usage:
#   bash fonts-download.sh [target_dir] [--theme <theme_dir|theme_name> | style] [--dry-run]
#   bash fonts-download.sh --refresh (--theme <theme_dir|theme_name> | style) [--dry-run]
#     target_dir defaults to ./fonts; style (legacy) is a theme name or all
#
# Fonts are committed under resources/fonts/: each theme keeps only its CSS in
# resources/fonts/<theme>/<fonts.css_filename>, and the WOFF2 files it
# references live once, named by the hash of their Google Fonts URL, in the
# shared pool resources/fonts/files/. Themes using the same families therefore
# share the same files. Installing copies the theme's CSS plus the pool files
# it references into target_dir and never touches the network. --refresh is
# the maintenance path: it re-downloads the families in
# modules/designs/<theme>/<theme>.json from Google Fonts, replaces the theme's
# CSS, adds only the pool files that are missing, and prunes pool files no
# theme references any more, so the result can be committed.
#
# Output: one JSON document on stdout, logs on stderr; exit 0 = success,
# 1 = runtime error, 2 = invalid arguments.
# Overrides (maintenance and tests): FONTS_RESOURCES_DIR (default
# <repo>/resources/fonts), FONTS_CSS2_URL (default
# https://fonts.googleapis.com/css2).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 - "$SCRIPT_DIR" "$@" <<'PY'
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(sys.argv[1]).parent
DESIGNS = REPO / 'modules' / 'designs'
RESOURCES = Path(os.environ.get('FONTS_RESOURCES_DIR') or REPO / 'resources' / 'fonts')
POOL = RESOURCES / 'files'
CSS2_URL = os.environ.get('FONTS_CSS2_URL') or 'https://fonts.googleapis.com/css2'
# A modern browser UA makes Google Fonts serve real WOFF2 (unicode-range
# subsets, variable axes kept); a bare UA gets static TrueType per instance.
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    )
}


class BadArguments(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise BadArguments(message)


def log(message: str) -> None:
    print(f'[fonts] {message}', file=sys.stderr)


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = Parser(prog='fonts-download.sh', add_help=False)
    parser.add_argument('positionals', nargs='*')
    parser.add_argument('--theme')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_intermixed_args(argv)
    limit = 1 if args.refresh else 2
    if len(args.positionals) > limit:
        raise BadArguments(
            'usage: fonts-download.sh [target_dir] [--theme <theme> | style] [--dry-run] | '
            '--refresh (--theme <theme> | style) [--dry-run]'
        )
    style = args.positionals[-1] if len(args.positionals) == limit else None
    if args.theme and style:
        raise BadArguments('pass either --theme or a named style, not both')
    args.spec = args.theme or style
    if args.refresh and not args.spec:
        raise BadArguments('--refresh needs --theme <theme> or a theme name / all')
    args.spec = args.spec or 'default'
    args.target = None if args.refresh else Path(args.positionals[0] if args.positionals else 'fonts')
    return args


def contract_path(theme: Path) -> Path:
    return theme / f'{theme.name}.json'


def known_themes() -> list[str]:
    return sorted(path.parent.name for path in DESIGNS.glob('*/*.json') if path.stem == path.parent.name)


def resolve_manifests(spec: str) -> list[Path]:
    if spec == 'all':
        return [contract_path(DESIGNS / theme) for theme in known_themes()]
    # A bare theme name always means modules/designs/<name>, whatever the
    # working directory contains; only path-like specs are resolved as paths.
    if '/' not in spec and contract_path(DESIGNS / spec).is_file():
        return [contract_path(DESIGNS / spec)]
    for base in (Path.cwd(), REPO):
        path = base / spec
        if path.is_file() and path.suffix == '.json' and path.stem == path.parent.name:
            return [path]
        if path.is_dir() and contract_path(path).is_file():
            return [contract_path(path)]
    raise BadArguments(f"unknown theme '{spec}'. Expected one of: {' '.join(known_themes())} all")


def load_manifest(path: Path) -> dict:
    contract = json.loads(path.read_text(encoding='utf-8'))
    manifest = contract.get('fonts') if isinstance(contract, dict) else None
    if not isinstance(manifest, dict):
        raise ValueError(f'design {path}: fonts must be an object')
    families = manifest.get('css2_families')
    if not isinstance(families, list) or not families:
        raise ValueError(f'design {path}: fonts.css2_families must be a non-empty list')
    if not isinstance(manifest.get('css_filename'), str) or not manifest['css_filename']:
        raise ValueError(f'design {path}: fonts.css_filename must be a non-empty string')
    rename = manifest.get('rename')
    if not isinstance(rename, dict) or not all(
        isinstance(old, str) and isinstance(new, str) for old, new in rename.items()
    ):
        raise ValueError(f'design {path}: fonts.rename must be a string mapping')
    return manifest


def css_refs(css: str) -> list[str]:
    """The bare WOFF2 file names a theme CSS references, in order, once each."""
    refs = [ref.strip('\'" ') for ref in re.findall(r'url\(([^)]+)\)', css)]
    for ref in refs:
        if Path(ref).name != ref:
            raise ValueError(f'font reference {ref!r} must be a bare file name in the shared pool')
    return list(dict.fromkeys(refs))


def theme_files(theme: str, manifest: dict) -> list[Path]:
    """The vendored CSS of a theme followed by the pool files it references."""
    css = RESOURCES / theme / manifest['css_filename']
    if not css.is_file():
        raise FileNotFoundError(
            f'no vendored fonts for theme {theme} in {css.parent}; '
            f'run: bash scripts/fonts-download.sh --refresh --theme {theme}'
        )
    refs = css_refs(css.read_text(encoding='utf-8'))
    missing = [ref for ref in refs if not (POOL / ref).is_file()]
    if missing:
        raise FileNotFoundError(
            f'theme {theme} references fonts missing from the shared pool {POOL}: {", ".join(missing)}; '
            f'run: bash scripts/fonts-download.sh --refresh --theme {theme}'
        )
    return [css, *sorted(POOL / ref for ref in refs)]


def install(manifest_path: Path, target: Path, dry_run: bool) -> list[str]:
    theme = manifest_path.parent.name
    files = theme_files(theme, load_manifest(manifest_path))
    if not dry_run:
        target.mkdir(parents=True, exist_ok=True)
        for file in files:
            shutil.copyfile(file, target / file.name)
    log(f"{'would install' if dry_run else 'installed'} {len(files)} files for {theme} into {target}")
    return [str((target / file.name).resolve()) for file in files]


def prune_pool() -> None:
    """Delete pool files that no theme CSS references (a refresh can orphan them)."""
    if not POOL.is_dir():
        return
    referenced = {
        ref
        for css in RESOURCES.glob('[!.]*/*.css')
        for ref in css_refs(css.read_text(encoding='utf-8'))
    }
    for file in sorted(POOL.iterdir()):
        if file.name not in referenced:
            log(f'pruning unreferenced {file.name}')
            file.unlink()


def fetch(url: str, attempts: int = 3) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            # 4xx will not get better on retry; only server errors are retried.
            if exc.code < 500 or attempt == attempts:
                raise
            log(f'retry {attempt}/{attempts - 1} after {exc}')
            time.sleep(2 * attempt)
        except OSError as exc:
            if attempt == attempts:
                raise
            log(f'retry {attempt}/{attempts - 1} after {exc}')
            time.sleep(2 * attempt)
    raise AssertionError('unreachable')


def refresh(manifest_path: Path, dry_run: bool) -> list[str]:
    theme = manifest_path.parent.name
    manifest = load_manifest(manifest_path)
    css_url = CSS2_URL + '?family=' + '&family='.join(manifest['css2_families']) + '&display=swap'
    out = RESOURCES / theme
    if dry_run:
        log(f'dry-run {theme} css: {css_url}')
        log(f'dry-run {theme} output: {out}')
        return []
    css = fetch(css_url).decode('utf-8')
    urls = list(dict.fromkeys(re.findall(r'url\((https?://[^)]+)\)', css)))
    if not urls:
        raise ValueError(f'no font URLs found in the CSS for {theme}')
    # Download into a hidden staging dir and swap it in only when complete, so
    # a failed refresh leaves the committed fonts untouched and no debris.
    # staging/fonts holds the pool files this theme adds, staging/css the new
    # theme dir.
    staging = RESOURCES / f'.{theme}.partial'
    previous = RESOURCES / f'.{theme}.previous'
    shutil.rmtree(staging, ignore_errors=True)
    (staging / 'fonts').mkdir(parents=True)
    (staging / 'css').mkdir()
    try:
        for url in urls:
            filename = hashlib.sha256(url.encode('utf-8')).hexdigest()[:12] + '.woff2'
            if (POOL / filename).is_file():
                log(f'reusing {filename}')
            else:
                log(f'downloading {filename}')
                (staging / 'fonts' / filename).write_bytes(fetch(url))
            css = css.replace(url, filename)
        for old, new in manifest['rename'].items():
            css = css.replace(f"'{old}'", f"'{new}'")
        (staging / 'css' / manifest['css_filename']).write_text(css, encoding='utf-8')
        POOL.mkdir(parents=True, exist_ok=True)
        for file in (staging / 'fonts').iterdir():
            file.replace(POOL / file.name)
        shutil.rmtree(previous, ignore_errors=True)
        if out.exists():
            out.rename(previous)
        try:
            (staging / 'css').rename(out)
        except OSError:
            if previous.exists() and not out.exists():
                previous.rename(out)
            raise
        shutil.rmtree(previous, ignore_errors=True)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    prune_pool()
    files = theme_files(theme, manifest)
    log(f'refreshed {theme}: {len(urls)} font files in {POOL}, css in {out}')
    return [str(file.resolve()) for file in files]


def main(argv: list[str]) -> int:
    try:
        args = parse_args(argv)
        if args.refresh and args.spec != 'all' and (
            '/' in args.spec or not contract_path(DESIGNS / args.spec).is_file()
        ):
            # Refresh rewrites committed fonts, so it only takes theme names
            # under modules/designs, never paths to other manifests.
            raise BadArguments(
                f"--refresh takes a theme name under modules/designs: {' '.join(known_themes())} all"
            )
        manifests = resolve_manifests(args.spec)
        files: list[str] = []
        for manifest in manifests:
            if args.refresh:
                files += refresh(manifest, args.dry_run)
            else:
                files += install(manifest, args.target, args.dry_run)
        output_dir = RESOURCES if args.refresh else args.target
        print_json({
            'success': True,
            'mode': 'refresh' if args.refresh else 'install',
            'output_dir': str(output_dir.resolve()),
            'files': files,
        })
        return 0
    except BadArguments as exc:
        log(f'bad arguments: {exc}')
        print_json({'success': False, 'error': str(exc)})
        return 2
    except Exception as exc:  # noqa: BLE001 - every runtime failure becomes one JSON error
        log(f'error: {exc}')
        print_json({'success': False, 'error': str(exc)})
        return 1


sys.exit(main(sys.argv[2:]))
PY
