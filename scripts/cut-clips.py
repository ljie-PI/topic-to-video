#!/usr/bin/env python3
"""Cut every selected clip of the material catalog into a silent video file.

Phase 5 writes `selected_clips` as references (`{start, end, reason, ...}`) into
a source video. This script materialises each one as `<ws>/clips/<video_id>_<start:.2f>-<end:.2f>.mp4`
with the audio track stripped (SKILL.md guardrail 6), so composition embeds a
short silent file instead of the whole original video. The clip's catalog
entry gets `clip_path` (relative to the workspace, POSIX separators), and
material-catalog.json is updated in place (atomic write).

A clip whose target file already exists and passes the cut-file checks (a
non-empty, playable, silent video of the expected length) is not cut again;
a stale or foreign file at the target is re-cut. A clip that fails (bad
window, missing source, ffmpeg error) is reported in `errors` and carries no
clip_path; the others are still cut. The catalog is saved incrementally —
after every clip and again in a `finally`, so an interrupted run keeps the
clip_path updates of the clips it already finished.

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
from pathlib import Path
from typing import Any

import cli
import clip_paths
import media
from harvest_manifest import _stage_json

TOOL_NAME = 'cut-clips'

CATALOG_NAME = 'material-catalog.json'
HARVEST_DIR = 'harvest_page'
FFMPEG_TIMEOUT_SECONDS = 600
# A clip cut from the very end of a source may come out a few frames short.
DURATION_SLACK_S = 0.1


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
    """Yield (entry, video, clip) for every selected clip of every catalog video."""
    for entry in catalog['entries']:
        videos = entry.get('videos') if isinstance(entry, dict) else None
        for video in videos if isinstance(videos, list) else []:
            clips = video.get('selected_clips') if isinstance(video, dict) else None
            for clip in clips if isinstance(clips, list) else []:
                if isinstance(clip, dict):
                    yield entry, video, clip


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


def clip_relpath(entry: dict[str, Any], video: dict[str, Any], start: Any, end: Any) -> str:
    if not (is_number(start) and is_number(end)):
        raise ClipError('clip start and end must be numbers')
    if start < 0 or end <= start:
        raise ClipError(f'clip window {start}-{end} must satisfy 0 <= start < end')
    try:
        # clip_paths namespaces by entry slug and millisecond window, so ids
        # recurring across entries and sub-centisecond edits cannot collide.
        return clip_paths.clip_relpath(entry.get('slug'), video.get('id'), start, end)
    except ValueError as exc:
        raise ClipError(str(exc)) from exc


def is_cut(target: Path, expected_duration_s: float) -> bool:
    """Whether `target` is a usable silent clip of the expected length.

    Any non-empty file used to count, so a leftover with its original audio
    track (or a truncated half-write) was reported as skipped; probe it
    instead: playable, no audio (SKILL.md guardrail 6), roughly the length
    the window promises.
    """
    if not target.is_file() or target.stat().st_size == 0:
        return False
    try:
        info = media.probe(target)
    except media.MediaProbeError:
        return False
    return (
        info['width'] is not None
        and not info['has_audio']
        and info['duration_seconds'] is not None
        and info['duration_seconds'] >= expected_duration_s - DURATION_SLACK_S
    )


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
                # Browser-safe output: even dimensions and yuv420p, whatever
                # the source was (10-bit / 4:4:4 / odd-sized sources otherwise
                # fail or render black in Chrome).
                '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p',
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
        expected = end - start
        if info['duration_seconds'] < expected - DURATION_SLACK_S:
            raise ClipError(
                f'window {start}-{end} is {expected:.3f}s but only {info["duration_seconds"]:.3f}s was '
                f'cut: the window extends past the end of the source, fix the selected clip'
            )
        os.replace(partial, target)
    finally:
        partial.unlink(missing_ok=True)


def process_clip(ws: Path, entry: dict[str, Any], video: dict[str, Any], clip: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Make sure the clip's file exists and clip_path is set. Returns (result, catalog_changed)."""
    start, end = clip.get('start'), clip.get('end')
    relpath = clip_relpath(entry, video, start, end)
    target = ws / relpath
    skipped = is_cut(target, (end or 0) - (start or 0))
    if skipped:
        log(f'{relpath} already cut, skipping')
    else:
        log(f'cutting {relpath}')
        cut(source_path(ws, video), float(start), float(end), target)
    changed = clip.get('clip_path') != relpath
    clip['clip_path'] = relpath
    return {'clip_path': relpath, 'skipped': skipped}, changed


def save_catalog(ws: Path, catalog: dict[str, Any]) -> None:
    """Atomically, preserving the catalog's existing file permissions."""
    staged = _stage_json(ws / CATALOG_NAME, catalog)
    os.replace(staged, ws / CATALOG_NAME)


def main() -> int:
    args = parse_args()
    ws = Path(args.workspace).expanduser()
    if not ws.is_dir():
        raise NotADirectoryError(f'workspace is not a directory: {args.workspace}')
    # cut() probes every finished clip, so ffprobe is required up front —
    # a missing probe used to surface only after the first full re-encode.
    media.ensure_media_binaries()
    catalog = load_catalog(ws)

    clips: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    catalog_changed = False
    try:
        for entry, video, clip in iter_selected_clips(catalog):
            ref = f"{video.get('id')}:{clip.get('start')}-{clip.get('end')}"
            try:
                result, changed = process_clip(ws, entry, video, clip)
            except (ClipError, media.FfmpegError, subprocess.TimeoutExpired) as exc:
                log(f'{ref} failed: {exc}')
                error = {'ref': ref, 'error': str(exc)}
                if isinstance(exc, media.FfmpegError):
                    error['stderr_tail'] = exc.stderr_tail
                errors.append(error)
                # clip_path must name the file of the clip's current window, or nothing.
                if clip.pop('clip_path', None) is not None:
                    catalog_changed = True
                continue
            clips.append({'ref': ref, **result})
            catalog_changed = catalog_changed or changed
            if changed:
                # Incremental: a crash or a kill must not lose the clip_path
                # updates of the clips already finished.
                save_catalog(ws, catalog)
                catalog_changed = False
    finally:
        if catalog_changed:
            save_catalog(ws, catalog)
    log(f'{len(clips)} clip(s) in place, {len(errors)} failed')
    cli.print_json({'success': not errors, 'clips': clips, 'errors': errors})
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
