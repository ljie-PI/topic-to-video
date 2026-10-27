#!/usr/bin/env python3
"""Shared definition of a composition's checkable sources.

Both check-composition.py (which embeds a sources fingerprint in its report)
and pipeline-status.py (which compares that fingerprint on later scans) must
agree on exactly which files determine the rendered DOM, so the rule lives
here in one place.

The checkable sources are index.html plus every visible file under
compositions/ and assets/, except assets/fonts/: fonts are byte-identical
copies from resources/fonts/, and re-copying them (fonts-download.sh runs on
every prepare) must not invalidate a saved check report.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

# Directories whose visible files are part of the checkable sources, relative
# to the composition dir. index.html is always included when present.
SOURCE_DIRS = ('compositions', 'assets')
FONT_DIR = 'assets/fonts'


def visible_files(directory: Path) -> list[Path]:
    """The files under `directory` at any depth; hidden ones such as .DS_Store are left out."""
    return [
        item
        for item in directory.rglob('*')
        if item.is_file() and not any(part.startswith('.') for part in item.relative_to(directory).parts)
    ]


def composition_source_relpaths(composition_dir: Path) -> list[str]:
    """The checkable source files as posix paths relative to composition_dir, sorted."""
    paths: list[Path] = []
    index = composition_dir / 'index.html'
    if index.is_file():
        paths.append(index)
    for name in SOURCE_DIRS:
        subdir = composition_dir / name
        if subdir.is_dir():
            paths.extend(
                path
                for path in visible_files(subdir)
                if FONT_DIR not in path.relative_to(composition_dir).as_posix().split('/')
            )
    return sorted(path.relative_to(composition_dir).as_posix() for path in paths)


def fingerprint_relpaths(root: Path, relpaths: list[str]) -> str:
    """One sha256 over the sorted relpaths and the current content of each.

    A file that no longer exists hashes as <absent>, so deleting a source
    without re-checking also shows up as a fingerprint change.
    """
    digest = hashlib.sha256()
    for relpath in sorted(relpaths):
        digest.update(relpath.encode('utf-8'))
        digest.update(b'\0')
        path = root / relpath
        if path.is_file():
            with path.open('rb') as handle:
                for chunk in iter(lambda: handle.read(1 << 20), b''):
                    digest.update(chunk)
        else:
            digest.update(b'<absent>')
        digest.update(b'\n')
    return digest.hexdigest()


def composition_sources_fingerprint(composition_dir: Path) -> str:
    """The sources fingerprint embedded in a check-composition report."""
    return fingerprint_relpaths(composition_dir, composition_source_relpaths(composition_dir))
