"""Versioned harvest manifest persistence, path, and download helpers.

All writes to ``manifest.json`` and per-slug ``metadata.json`` belong here.
Paths persisted in either file are POSIX paths relative to the harvest root.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

VIDEO_EXTS = {'.mp4', '.webm', '.mov', '.mkv', '.m4v', '.avi'}
SUBTITLE_EXTS = {'.srt', '.vtt'}
_PATH_FIELDS = {'local_path', 'subtitle_path', 'suggested_output_dir', 'full_markdown_path'}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _root(harvest_dir: str | os.PathLike[str]) -> Path:
    return Path(harvest_dir).expanduser().resolve()


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'expected JSON object: {path}')
    return data


def _new_manifest() -> dict[str, Any]:
    return {
        'version': 2,
        'entries': [],
        'pending_downloads': [],
        'harvest_batches': [],
        'updated_at': '',
    }


def _replace_entries(target: list[dict[str, Any]], entries: list[dict[str, Any]]) -> None:
    by_slug = {entry.get('slug'): index for index, entry in enumerate(target)}
    for entry in entries:
        slug = entry.get('slug')
        if slug in by_slug:
            target[by_slug[slug]] = entry
        else:
            by_slug[slug] = len(target)
            target.append(entry)


def load(harvest_dir: str | os.PathLike[str]) -> dict[str, Any]:
    """Load v2 data, or merge ``manifest_papers.json`` for legacy manifests."""
    root = _root(harvest_dir)
    raw = _read(root / 'manifest.json')
    manifest = _new_manifest()
    entries = raw.get('entries', [])
    if not isinstance(entries, list):
        raise ValueError('manifest.json entries must be a list')
    _replace_entries(manifest['entries'], copy.deepcopy(entries))
    if raw.get('version') != 2:
        papers = _read(root / 'manifest_papers.json')
        paper_entries = papers.get('entries', [])
        if not isinstance(paper_entries, list):
            raise ValueError('manifest_papers.json entries must be a list')
        _replace_entries(manifest['entries'], copy.deepcopy(paper_entries))
    batches = raw.get('harvest_batches', [])
    if not isinstance(batches, list):
        raise ValueError('manifest.json harvest_batches must be a list')
    manifest['harvest_batches'] = copy.deepcopy(batches)
    manifest['updated_at'] = raw.get('updated_at', '')
    manifest['pending_downloads'] = _pending_downloads(manifest['entries'])
    return manifest


def resolve(harvest_dir: str | os.PathLike[str], rel: str | os.PathLike[str]) -> Path:
    """Resolve a stored path; legacy absolute paths remain absolute."""
    path = Path(rel).expanduser()
    return path if path.is_absolute() else _root(harvest_dir) / path


def _relative_path(root: Path, value: str) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        return Path(value).as_posix()
    return Path(os.path.relpath(path, root)).as_posix()


def _normalize_paths(value: Any, root: Path) -> Any:
    if isinstance(value, dict):
        return {
            key: _relative_path(root, item) if key in _PATH_FIELDS and isinstance(item, str) and item
            else _normalize_paths(item, root)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_paths(item, root) for item in value]
    return value


def _pending_downloads(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pending: list[dict[str, Any]] = []
    by_url: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not entry.get('success'):
            continue
        for video in entry.get('videos', []) or []:
            if not video.get('download_required') or not video.get('url'):
                continue
            url = video['url']
            if url in by_url:
                item = by_url[url]
                slug = entry.get('slug', '')
                if slug and slug != item['source_slug'] and slug not in item['also_referenced_by']:
                    item['also_referenced_by'].append(slug)
                continue
            item = {
                'url': url,
                'platform': video.get('platform', ''),
                'suggested_output_dir': video.get('suggested_output_dir', ''),
                'source_slug': entry.get('slug', ''),
                'also_referenced_by': [],
            }
            by_url[url] = item
            pending.append(item)
    for item in pending:
        if not item['also_referenced_by']:
            del item['also_referenced_by']
    return pending


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def save(
    harvest_dir: str | os.PathLike[str],
    manifest: dict[str, Any],
    *,
    dirty_slugs: set[str] | None = None,
) -> dict[str, Any]:
    """Atomically save the v2 manifest and mirrors for changed entries."""
    root = _root(harvest_dir)
    root.mkdir(parents=True, exist_ok=True)
    saved = _new_manifest()
    saved['entries'] = _normalize_paths(copy.deepcopy(manifest.get('entries', [])), root)
    saved['harvest_batches'] = copy.deepcopy(manifest.get('harvest_batches', []))
    saved['pending_downloads'] = _pending_downloads(saved['entries'])
    saved['updated_at'] = _now()
    _atomic_json(root / 'manifest.json', saved)
    mirrors = saved['entries'] if dirty_slugs is None else [
        entry for entry in saved['entries'] if entry.get('slug') in dirty_slugs
    ]
    for entry in mirrors:
        slug = entry.get('slug')
        if not slug or Path(slug).name != slug or slug in {'.', '..'}:
            raise ValueError(f'invalid entry slug: {slug!r}')
        _atomic_json(root / slug / 'metadata.json', entry)
    return saved


def upsert_entries(
    harvest_dir: str | os.PathLike[str], entries: list[dict[str, Any]],
) -> dict[str, Any]:
    manifest = load(harvest_dir)
    _replace_entries(manifest['entries'], copy.deepcopy(entries))
    return save(harvest_dir, manifest, dirty_slugs={entry.get('slug', '') for entry in entries})


def record_harvest_batch(
    harvest_dir: str | os.PathLike[str], batch: dict[str, Any],
) -> dict[str, Any]:
    manifest = load(harvest_dir)
    recorded = {
        'at': batch.get('at') or _now(),
        'urls': list(batch.get('urls', [])),
        'succeeded': int(batch.get('succeeded', 0)),
        'failed': int(batch.get('failed', 0)),
        'rejected': copy.deepcopy(batch.get('rejected', [])),
    }
    manifest['harvest_batches'].append(recorded)
    return save(harvest_dir, manifest, dirty_slugs=set())


def apply_download(
    harvest_dir: str | os.PathLike[str], url: str, result: dict[str, Any],
) -> dict[str, Any]:
    """Fan a successful yt-dlp result out to every entry referencing ``url``."""
    manifest = load(harvest_dir)
    if result.get('success') is False:
        return manifest
    files = result.get('files', []) or []
    videos = [path for path in files if Path(path).suffix.lower() in VIDEO_EXTS]
    subtitles = [path for path in files if Path(path).suffix.lower() in SUBTITLE_EXTS]
    if not videos:
        raise ValueError('download result did not include a video file')
    local_path = videos[0]
    subtitle_path = subtitles[0] if subtitles else None
    infos = result.get('videos', []) or []
    info = next((item for item in infos if item.get('path') == local_path), None)
    if info is None and infos:
        info = infos[0]
    info = info or {}
    dirty: set[str] = set()
    for entry in manifest['entries']:
        changed = False
        for video in entry.get('videos', []) or []:
            if video.get('url') != url:
                continue
            video.update({
                'download_required': False,
                'downloaded': True,
                'local_path': local_path,
                'subtitle_path': subtitle_path,
                'id': Path(local_path).stem,
                'width': info.get('width'),
                'height': info.get('height'),
                'duration_seconds': info.get('duration_seconds'),
            })
            changed = True
        if changed and entry.get('slug'):
            dirty.add(entry['slug'])
    if dirty:
        return save(harvest_dir, manifest, dirty_slugs=dirty)
    return manifest


def slug_for_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or 'unknown').lower().replace('.', '-').replace(':', '-')
    path = (parsed.path or '/').strip('/').lower()
    path = re.sub(r'[^a-z0-9]+', '-', path).strip('-')[:60]
    digest = hashlib.sha1(url.encode('utf-8')).hexdigest()[:6]
    slug = f'{host}-{path}-{digest}' if path else f'{host}-{digest}'
    return slug.strip('-')[:120]


def slug_for_pdf(url: str | None, pdf_path: str | None) -> str:
    if url:
        base = Path(urlparse(url).path).stem or 'paper'
    else:
        base = Path(pdf_path).stem
    slug = re.sub(r'[^a-z0-9]+', '-', base.lower()).strip('-')
    return slug[:80] or 'paper'
