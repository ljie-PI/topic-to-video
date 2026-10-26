#!/usr/bin/env python3
"""Extract JPEG frames from a video with ffmpeg.

Usage:
  python3 extract-frames.py video.mp4 frames/ --max-frames 20
  python3 extract-frames.py video.mp4 frames/ --start-time 00:01:30 --end-time 00:02:00

Output JSON includes interval_s and frames as {path, t_s} objects. Frame names
use their source-video timestamps, for example frame_t0012.50s.jpg.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import cli
import media

FFMPEG_TIMEOUT_SECONDS = 300
FFPROBE_TIMEOUT_SECONDS = 30
FRAME_GLOB = 'frame_*.jpg'
FRAME_PATTERN = 'frame_%04d.jpg'
TOOL_NAME = 'extract-frames'


log = cli.make_logger(TOOL_NAME)


def print_json(payload: dict[str, object]) -> int:
    cli.print_json(payload)
    return 0 if payload.get('success') else 1


def parse_args() -> argparse.Namespace:
    parser = cli.JsonArgumentParser(TOOL_NAME, description='Extract JPEG frames from a video with ffmpeg.')
    parser.add_argument('video_path', help='Video file path')
    parser.add_argument('output_dir', help='Output directory for extracted frames')
    parser.add_argument('--max-frames', type=int, default=20, help='Maximum frames to extract (default: 20)')
    parser.add_argument('--start-time', help='Optional start time (for example: 00:01:30)')
    parser.add_argument('--end-time', help='Optional end time (for example: 00:02:00)')
    parser.add_argument('--max-width', type=int, default=512, help='Maximum output width in pixels (default: 512)')
    args = parser.parse_args()

    if args.max_frames <= 0:
        parser.error('--max-frames must be greater than 0')
    if args.max_width <= 0:
        parser.error('--max-width must be greater than 0')

    return args


def resolve_video_path(raw_path: str) -> Path:
    video_path = Path(raw_path).expanduser()
    if not video_path.is_file():
        raise FileNotFoundError(f'Video file not found: {raw_path}')
    return video_path.resolve()


def prepare_output_dir(raw_path: str) -> Path:
    output_dir = Path(raw_path).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved = output_dir.resolve()
    if not resolved.is_dir():
        raise NotADirectoryError(f'Output path is not a directory: {raw_path}')
    return resolved


def output_pattern(output_dir: Path) -> str:
    pattern_path = (output_dir / FRAME_PATTERN).resolve()
    if pattern_path.parent != output_dir:
        raise ValueError('Unsafe output path detected')
    return str(pattern_path)


def remove_existing_frames(output_dir: Path) -> None:
    for frame_path in output_dir.glob(FRAME_GLOB):
        resolved = frame_path.resolve()
        if resolved.parent != output_dir:
            raise ValueError(f'Unsafe frame path detected: {frame_path}')
        if resolved.is_file():
            resolved.unlink()


def timestamp_to_seconds(value: str | None) -> float:
    if not value:
        return 0.0
    parts = value.split(':')
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    raise ValueError(f'Invalid start time: {value}')


def build_ffmpeg_command(
    args: argparse.Namespace, video_path: Path, output_dir: Path
) -> tuple[list[str], float]:
    has_time_window = bool(args.start_time or args.end_time)
    if has_time_window:
        interval = 1.0
        filter_expr = f"fps=1,scale='min({args.max_width},iw)':-2"
    else:
        log(f'Probing duration for {video_path}...')
        duration = media.probe_duration(video_path)
        interval = float(max(1, math.floor(duration / args.max_frames)))
        filter_expr = f"fps=1/{interval},scale='min({args.max_width},iw)':-2"

    command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y']
    if args.start_time:
        command.extend(['-ss', args.start_time])
    if args.end_time:
        command.extend(['-to', args.end_time])
    command.extend(
        [
            '-i',
            str(video_path),
            '-vf',
            filter_expr,
            '-frames:v',
            str(args.max_frames),
            output_pattern(output_dir),
        ]
    )
    return command, interval


def list_frames(output_dir: Path, start_s: float, interval_s: float) -> list[dict[str, object]]:
    frames = []
    for index, frame_path in enumerate(sorted(output_dir.glob(FRAME_GLOB))):
        resolved = frame_path.resolve()
        if resolved.parent != output_dir:
            raise ValueError(f'Unsafe frame path detected: {frame_path}')
        if resolved.is_file():
            t_s = start_s + index * interval_s
            timestamped_path = output_dir / f'frame_t{t_s:07.2f}s.jpg'
            resolved.rename(timestamped_path)
            frames.append({'path': str(timestamped_path.resolve()), 't_s': t_s})
    return frames


def main() -> int:
    args = parse_args()
    video_path = resolve_video_path(args.video_path)
    output_dir = prepare_output_dir(args.output_dir)
    remove_existing_frames(output_dir)
    command, interval_s = build_ffmpeg_command(args, video_path, output_dir)
    start_s = timestamp_to_seconds(args.start_time)
    log(f'Extracting up to {args.max_frames} frames into {output_dir}...')
    media.run_ffmpeg(command[1:], timeout=FFMPEG_TIMEOUT_SECONDS)
    frames = list_frames(output_dir, start_s, interval_s)
    log(f'Extracted {len(frames)} frame(s)')
    return print_json(
        {
            'success': True,
            'output_dir': str(output_dir),
            'frame_count': len(frames),
            'interval_s': interval_s,
            'frames': frames,
        }
    )


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
