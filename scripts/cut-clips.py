#!/usr/bin/env python3
"""把素材 catalog 中每个选中片段切成静音视频文件。

Phase 5 把 `selected_clips` 以引用（`{start, end, reason, ...}`）的形式写进某个源
视频。本脚本把每一个都落地为
`<ws>/clips/<video_id>_<start:.2f>-<end:.2f>.mp4` 并去掉音轨（Phase 5 的护栏见
`references/phases/05-material-catalog.md`），这样 composition 嵌入的是一个短的
静音文件，而不是整段原始视频。该片段在 catalog 中的条目会被写上 `clip_path`
（相对于 workspace，POSIX 分隔符），material-catalog.json 就地更新（原子写入）。

目标文件已存在且非空的片段不再重切。失败的片段（时间窗非法、源文件缺失、ffmpeg
报错）会写进 `errors` 且不携带 clip_path；其余片段仍会被切出。catalog 是增量保存
的——每切完一个片段保存一次，并在 `finally` 中再保存一次，因此被中断的运行会保留
其已完成的那些片段的 clip_path 更新。

用法：
  python3 scripts/cut-clips.py <workspace_dir>

视频的相对 `local_path` 相对于 `<workspace_dir>/harvest_page/`（v2 manifest 的
基准目录）；绝对路径（旧 catalog）则原样使用。

输出：stdout 上的一份 JSON 文档。
  {"success": true, "clips": [{"ref": "<slug>/<video_id>:<start>-<end>", "clip_path": "clips/...", "skipped": false}],
   "errors": []}
  失败的片段是 `errors` 中的 {"ref": ..., "error": "...", "stderr_tail": "..."?}，
  并使 `success` 为 false。
退出码：0 = 所有片段均已就位，1 = 有片段失败或运行时错误（例如没有 catalog），
2 = 参数非法。
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
# 从源视频末尾切出的片段可能短掉几帧。
DURATION_SLACK_S = 0.1


class ClipError(ValueError):
    """某个选中片段无法切出；其他片段不受影响。"""


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
    """对 catalog 中每个视频的每个选中片段产出 (slug, video, clip)。"""
    for entry in catalog['entries']:
        videos = entry.get('videos') if isinstance(entry, dict) else None
        slug = entry.get('slug') if isinstance(entry, dict) else None
        for video in videos if isinstance(videos, list) else []:
            clips = video.get('selected_clips') if isinstance(video, dict) else None
            for clip in clips if isinstance(clips, list) else []:
                if isinstance(clip, dict):
                    yield slug, video, clip


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


def clip_relpath(video: dict[str, Any], start: Any, end: Any) -> str:
    if not (is_number(start) and is_number(end)):
        raise ClipError('clip start and end must be numbers')
    if start < 0 or end <= start:
        raise ClipError(f'clip window {start}-{end} must satisfy 0 <= start < end')
    try:
        return clip_paths.clip_relpath(video.get('id'), start, end)
    except ValueError as exc:
        raise ClipError(str(exc)) from exc


def is_cut(target: Path) -> bool:
    return target.is_file() and target.stat().st_size > 0


def cut(source: Path, start: float, end: float, target: Path) -> None:
    """切到同级的一个文件再改名，因此被中断的 ffmpeg 绝不会在后续运行视为
    已完成的路径上留下写了一半的文件。"""
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
            timeout=float(os.environ.get('CUT_CLIPS_FFMPEG_TIMEOUT', FFMPEG_TIMEOUT_SECONDS)),
        )
        # 时间窗超出源视频末尾时，ffmpeg 会以退出码 0 产出一个不含任何帧的极小文件。
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


def process_clip(ws: Path, video: dict[str, Any], clip: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """确保该片段的文件存在且 clip_path 已设置。返回 (result, catalog_changed)。"""
    start, end = clip.get('start'), clip.get('end')
    relpath = clip_relpath(video, start, end)
    target = ws / relpath
    skipped = is_cut(target)
    if skipped:
        log(f'{relpath} already cut, skipping')
    else:
        log(f'cutting {relpath}')
        cut(source_path(ws, video), float(start), float(end), target)
    changed = clip.get('clip_path') != relpath
    clip['clip_path'] = relpath
    return {'clip_path': relpath, 'skipped': skipped}, changed


def save_catalog(ws: Path, catalog: dict[str, Any]) -> None:
    """原子写入，并保留 catalog 原有的文件权限。"""
    staged = _stage_json(ws / CATALOG_NAME, catalog)
    os.replace(staged, ws / CATALOG_NAME)


def main() -> int:
    args = parse_args()
    ws = Path(args.workspace).expanduser()
    if not ws.is_dir():
        raise NotADirectoryError(f'workspace is not a directory: {args.workspace}')
    # cut() 会探测每个切完的片段，因此一开始就要求有 ffprobe ——
    # 否则缺少它时，要等到第一次完整重编码之后才会暴露。
    media.ensure_media_binaries()
    catalog = load_catalog(ws)

    clips: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    catalog_changed = False
    try:
        for slug, video, clip in iter_selected_clips(catalog):
            ref = f"{slug}/{video.get('id')}:{clip.get('start')}-{clip.get('end')}"
            try:
                result, changed = process_clip(ws, video, clip)
            except (ClipError, media.FfmpegError, subprocess.TimeoutExpired) as exc:
                log(f'{ref} failed: {exc}')
                error = {'ref': ref, 'error': str(exc)}
                if isinstance(exc, media.FfmpegError):
                    error['stderr_tail'] = exc.stderr_tail
                errors.append(error)
                # clip_path 必须指向该片段当前时间窗的文件，否则就什么都不指。
                if clip.pop('clip_path', None) is not None:
                    catalog_changed = True
                continue
            clips.append({'ref': ref, **result})
            catalog_changed = catalog_changed or changed
            if changed:
                # 增量保存：崩溃或被 kill 都不能丢掉已切完片段的 clip_path
                # 更新。
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
