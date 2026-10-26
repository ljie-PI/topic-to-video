#!/usr/bin/env python3
"""Cut every selected clip of the material catalog into a silent video file.

Phase 5 writes `selected_clips` as references (`{start, end, reason, ...}`) into
a source video. This script materialises each one as `<ws>/clips/<video_id>_<start:.2f>-<end:.2f>.mp4`
with the audio track stripped (SKILL.md guardrail 6), so composition embeds a
short silent file instead of the whole original video. The clip's catalog
entry gets `clip_path` (relative to the workspace, POSIX separators), and
material-catalog.json is updated in place (atomic write).

A clip whose target file already exists and is non-empty is not cut again. A
clip that fails (bad window, missing source, ffmpeg error) is reported in
`errors`; the others are still cut, and the clips already cut stay.

Usage:
  python3 scripts/cut-clips.py <workspace_dir>

A video's relative `local_path` is relative to `<workspace_dir>/harvest_page/`
(the v2 manifest base); an absolute one (old catalogs) is used as is.

Output: one JSON document on stdout.
  {"success": true, "clips": [{"ref": "<video_id>:<start>-<end>", "clip_path": "clips/...", "skipped": false}],
   "errors": []}
  A failed clip is {"ref": ..., "error": "...", "stderr_tail": "..."?} in `errors`
  and makes `success` false.
Exit codes: 0 = every clip is in place, 1 = a clip failed or a runtime error
(e.g. no catalog), 2 = invalid arguments.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import cli
import media

TOOL_NAME = 'cut-clips'

CATALOG_NAME = 'material-catalog.json'
CLIPS_DIR = 'clips'
HARVEST_DIR = 'harvest_page'
FFMPEG_TIMEOUT_SECONDS = 600


class ClipError(ValueError):
    """One selected clip cannot be cut; the other clips are unaffected."""


log = cli.make_logger(TOOL_NAME)


def parse_args() -> argparse.Namespace:
    parser = cli.JsonArgumentParser(
        TOOL_NAME,
        description='Cut the selected clips of material-catalog.json into silent files under clips/.',
    )
    parser.add_argument('workspace', help='Project workspace directory ({work_dir}/{topic_name}).')
    return parser.parse_args()


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def load_catalog(ws: Path) -> dict[str, Any]:
    catalog_path = ws / CATALOG_NAME
    try:
        catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        raise ValueError(f'{CATALOG_NAME} is not valid JSON: {exc}') from exc
    if not isinstance(catalog, dict) or not isinstance(catalog.get('entries'), list):
        raise ValueError(f'{CATALOG_NAME} has no entries list')
    return catalog


def iter_selected_clips(catalog: dict[str, Any]):
    """Yield (video, clip) for every selected clip of every catalog video."""
    for entry in catalog['entries']:
        videos = entry.get('videos') if isinstance(entry, dict) else None
        for video in videos if isinstance(videos, list) else []:
            clips = video.get('selected_clips') if isinstance(video, dict) else None
            for clip in clips if isinstance(clips, list) else []:
                if isinstance(clip, dict):
                    yield video, clip


def source_path(ws: Path, video: dict[str, Any]) -> Path:
    local_path = video.get('local_path')
    if not isinstance(local_path, str) or not local_path:
        raise ClipError('video has no local_path')
    path = Path(local_path)
    if not path.is_absolute():
        path = ws / HARVEST_DIR / path
    if not path.is_file():
        raise ClipError(f'source video not found: {path}')
    return path


def clip_relpath(video_id: Any, start: Any, end: Any) -> str:
    if not isinstance(video_id, str) or not video_id:
        raise ClipError('video has no id')
    if any(char in video_id for char in '/\\\0') or video_id.startswith('.'):
        raise ClipError(f'video id {video_id!r} cannot be used in a file name')
    if not (is_number(start) and is_number(end)):
        raise ClipError('clip start and end must be numbers')
    if start < 0 or end <= start:
        raise ClipError(f'clip window {start}-{end} must satisfy 0 <= start < end')
    return f'{CLIPS_DIR}/{video_id}_{start:.2f}-{end:.2f}.mp4'


def is_cut(target: Path) -> bool:
    return target.is_file() and target.stat().st_size > 0


def cut(source: Path, start: float, end: float, target: Path) -> None:
    """Cut into a sibling file and rename it, so an interrupted ffmpeg never leaves a
    half-written file at the path later runs treat as done."""
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(f'.{target.stem}.part{target.suffix}')
    try:
        media.run_ffmpeg(
            [
                '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
                '-ss', f'{start:.3f}', '-to', f'{end:.3f}', '-i', source,
                '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
                '-movflags', '+faststart',
                partial,
            ],
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
        # A window past the end of the source makes ffmpeg exit 0 with a tiny file holding no frames.
        try:
            info = media.probe(partial)
        except media.MediaProbeError as exc:
            raise ClipError(f'ffmpeg produced an unreadable file: {exc}') from exc
        if info['width'] is None or not info['duration_seconds']:
            raise ClipError(f'ffmpeg produced no video for window {start}-{end} (past the end of the source?)')
        os.replace(partial, target)
    finally:
        partial.unlink(missing_ok=True)


def process_clip(ws: Path, video: dict[str, Any], clip: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Make sure the clip's file exists and clip_path is set. Returns (result, catalog_changed)."""
    start, end = clip.get('start'), clip.get('end')
    relpath = clip_relpath(video.get('id'), start, end)
    target = ws / relpath
    skipped = is_cut(target)
    if skipped:
        log(f'{relpath} already cut, skipping')
    else:
        log(f'cutting {relpath}')
        cut(source_path(ws, video), start, end, target)
    changed = clip.get('clip_path') != relpath
    clip['clip_path'] = relpath
    return {'clip_path': relpath, 'skipped': skipped}, changed


def main() -> int:
    args = parse_args()
    ws = Path(args.workspace).expanduser()
    if not ws.is_dir():
        raise NotADirectoryError(f'workspace is not a directory: {args.workspace}')
    media.ensure_media_binaries(require_duration_probe=False)
    catalog = load_catalog(ws)

    clips: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    catalog_changed = False
    for video, clip in iter_selected_clips(catalog):
        ref = f"{video.get('id')}:{clip.get('start')}-{clip.get('end')}"
        try:
            result, changed = process_clip(ws, video, clip)
        except (ClipError, media.FfmpegError, subprocess.TimeoutExpired) as exc:
            log(f'{ref} failed: {exc}')
            error = {'ref': ref, 'error': str(exc)}
            if isinstance(exc, media.FfmpegError):
                error['stderr_tail'] = exc.stderr_tail
            errors.append(error)
            continue
        clips.append({'ref': ref, **result})
        catalog_changed = catalog_changed or changed

    if catalog_changed:
        write_json_atomic(ws / CATALOG_NAME, catalog)
    log(f'{len(clips)} clip(s) in place, {len(errors)} failed')
    cli.print_json({'success': not errors, 'clips': clips, 'errors': errors})
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
