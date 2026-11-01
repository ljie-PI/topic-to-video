"""带版本的 harvest manifest 持久化、路径与下载辅助函数。

对 ``manifest.json`` 和各 slug 的 ``metadata.json`` 的所有写入都应集中在这里。
这两种文件里持久化的路径都是相对于 harvest 根的 POSIX 路径。
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any
from urllib.parse import urlparse

VIDEO_EXTS = {'.mp4', '.webm', '.mov', '.mkv', '.m4v', '.avi'}
SUBTITLE_EXTS = {'.srt', '.vtt'}
MANIFEST_VERSION = 2
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
        'version': MANIFEST_VERSION,
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
    """载入 v2 数据。

    manifest.json 不存在时得到一份新的 v2 manifest（首次写入时落盘）；已经存在时
    必须自己声明当前版本，否则报错而不是去合并旧文件或就地升级——那样的项目应该
    重建素材。
    """
    root = _root(harvest_dir)
    path = root / 'manifest.json'
    raw = _read(path)
    if path.exists():
        problem = manifest_problem(raw, base=root)
        if problem:
            raise ValueError(f'{path}: {problem}; regenerate the manifest with the current scripts')
    manifest = _new_manifest()
    manifest['entries'] = copy.deepcopy(raw.get('entries', []))
    manifest['harvest_batches'] = copy.deepcopy(raw.get('harvest_batches', []))
    manifest['updated_at'] = raw.get('updated_at', '')
    manifest['pending_downloads'] = pending_downloads(manifest['entries'])
    return manifest


def stored_path_problem(rel: Any, *, base: Path | None = None) -> str | None:
    """一个已持久化的路径不合法的原因，或 None。

    持久化路径只能是相对 harvest 根目录的 POSIX 路径：绝对路径、~ 展开、以及用
    .. 走到基准目录之外的路径都不接受，因为那样读出来的文件已经不在这个项目的
    素材目录里了。
    """
    if not isinstance(rel, str) or not rel:
        return f'{rel!r} is not a non-empty path'
    if '\\' in rel:
        return f'{rel!r} is not a POSIX path'
    path = Path(rel)
    if path.is_absolute() or PureWindowsPath(rel).drive or rel.startswith('~'):
        return f'{rel!r} is not relative to the harvest directory'
    if '..' in path.parts:
        return f'{rel!r} leaves the harvest directory'
    if base is not None:
        try:
            (base / path).resolve().relative_to(base.resolve())
        except ValueError:
            return f'{rel!r} resolves outside the harvest directory'
    return None


def paths_problem(value: Any, *, base: Path | None = None, where: str = '') -> str | None:
    """读取持久化路径的共同校验；不改写或迁移已经保存的数据。"""
    if isinstance(value, dict):
        for key, item in value.items():
            label = f'{where}.{key}' if where else key
            if key in _PATH_FIELDS and item is not None:
                problem = stored_path_problem(item, base=base)
            else:
                problem = paths_problem(item, base=base, where=label)
            if problem:
                return f'{label}: {problem}' if key in _PATH_FIELDS else problem
    elif isinstance(value, list):
        for index, item in enumerate(value):
            problem = paths_problem(item, base=base, where=f'{where}[{index}]')
            if problem:
                return problem
    return None


def manifest_problem(
    data: Any, *, base: Path | None = None, validate_paths: bool = True,
) -> str | None:
    """manifest 的当前读取契约，生产者与状态验收共用。"""
    if not isinstance(data, dict):
        return 'manifest JSON root is not an object'
    if data.get('version') != MANIFEST_VERSION:
        return f'not a version {MANIFEST_VERSION} manifest (found version {data.get("version")!r})'
    entries = data.get('entries')
    if not isinstance(entries, list):
        return 'manifest entries must be a list'
    slugs: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            return 'manifest entry is not an object'
        slug = entry.get('slug')
        if not isinstance(slug, str) or not slug or any(c in slug for c in '/\\') or slug in {'.', '..'}:
            return f'invalid entry slug: {slug!r}'
        if slug in slugs:
            return f'manifest repeats entry slug: {slug!r}'
        slugs.add(slug)
    if not isinstance(data.get('harvest_batches', []), list):
        return 'manifest harvest_batches must be a list'
    return paths_problem(data, base=base) if validate_paths else None


def resolve(harvest_dir: str | os.PathLike[str], rel: str | os.PathLike[str]) -> Path:
    """把已持久化的相对路径解析到 harvest 根目录下。"""
    problem = stored_path_problem(str(rel), base=_root(harvest_dir))
    if problem:
        raise ValueError(f'stored path is unusable: {problem}')
    return _root(harvest_dir) / Path(rel)


def _relative_path(root: Path, value: str) -> str:
    """把生产者内部的绝对路径规范成持久化相对路径。

    这是写入时的规范化，不是读取时的兼容：读到的绝对路径仍然一律拒绝。
    """
    path = Path(value).expanduser()
    if path.is_absolute():
        path = Path(os.path.relpath(path.resolve(), root))
    relpath = path.as_posix()
    problem = stored_path_problem(relpath, base=root)
    if problem:
        raise ValueError(f'cannot persist {value!r} under {root}: {problem}')
    return relpath


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


def pending_downloads(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _stage_json(path: Path, payload: dict[str, Any]) -> Path:
    """把临时文件写到原子改名目标旁边，并做 fsync。

    mkstemp 创建的临时文件权限是 0600；替换时不能让共享的 manifest / catalog 对
    同组或其他用户变得不可读，因此保留目标原有的权限（目标尚不存在时用 0644）。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        try:
            mode = stat.S_IMODE(path.stat().st_mode)
        except OSError:
            mode = 0o644
        os.chmod(temporary, mode)
        return Path(temporary)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _restore_file(path: Path, contents: bytes | None) -> None:
    if contents is None:
        path.unlink(missing_ok=True)
        return
    fd, temporary = tempfile.mkstemp(prefix=f'.{path.name}.rollback.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(contents)
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
    """原子地保存 v2 manifest，并为有变化的条目更新镜像文件。"""
    root = _root(harvest_dir)
    problem = manifest_problem(manifest, validate_paths=False)
    if problem:
        raise ValueError(problem)
    entries = copy.deepcopy(manifest['entries'])
    saved = _new_manifest()
    saved['entries'] = _normalize_paths(entries, root)
    saved['harvest_batches'] = copy.deepcopy(manifest.get('harvest_batches', []))
    saved['pending_downloads'] = pending_downloads(saved['entries'])
    saved['updated_at'] = _now()
    problem = manifest_problem(saved, base=root)
    if problem:
        raise ValueError(problem)
    normalized_slugs = {
        normalized.get('slug')
        for original, normalized in zip(entries, saved['entries'])
        if original != normalized
    }
    effective_dirty = dirty_slugs if dirty_slugs is not None else set()
    effective_dirty = set(effective_dirty) | normalized_slugs
    mirrors = saved['entries'] if dirty_slugs is None else [
        entry for entry in saved['entries'] if entry.get('slug') in effective_dirty
    ]
    targets = [(root / entry['slug'] / 'metadata.json', entry) for entry in mirrors]
    targets.append((root / 'manifest.json', saved))
    originals = {path: path.read_bytes() if path.exists() else None for path, _ in targets}
    staged: dict[Path, Path] = {}
    replaced: list[Path] = []
    try:
        # 任何目标被修改之前，序列化与镜像暂存都必须全部成功。
        for path, payload in targets:
            staged[path] = _stage_json(path, payload)
        for path, _ in targets:
            os.replace(staged[path], path)
            replaced.append(path)
    except Exception:
        # 尽力回滚，使 manifest 与所有镜像停留在同一代数据上。
        for path in reversed(replaced):
            try:
                _restore_file(path, originals[path])
            except OSError:
                pass
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
    return saved


def _preserve_completed_downloads(
    existing: dict[str, Any], incoming: dict[str, Any],
) -> dict[str, Any]:
    """刷新 harvest 元数据，同时不把已完成的视频重新变成待下载。"""
    previous_videos = {
        video.get('url'): video
        for video in existing.get('videos', []) or []
        if video.get('url') and video.get('downloaded') and video.get('download_required') is False
    }
    for video in incoming.get('videos', []) or []:
        previous = previous_videos.get(video.get('url'))
        if previous is None or video.get('local_path'):
            continue
        video['download_required'] = False
        video['downloaded'] = True
        for field in ('local_path', 'subtitle_path', 'id', 'width', 'height', 'duration_seconds'):
            if field in previous:
                video.setdefault(field, previous[field])
    return incoming


def upsert_entries(
    harvest_dir: str | os.PathLike[str], entries: list[dict[str, Any]],
) -> dict[str, Any]:
    manifest = load(harvest_dir)
    existing_by_slug = {entry.get('slug'): entry for entry in manifest['entries']}
    merged = [
        _preserve_completed_downloads(existing_by_slug[entry.get('slug')], copy.deepcopy(entry))
        if entry.get('slug') in existing_by_slug else copy.deepcopy(entry)
        for entry in entries
    ]
    _replace_entries(manifest['entries'], merged)
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
    """把一次成功的 yt-dlp 结果分发到所有引用 ``url`` 的条目上。"""
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
