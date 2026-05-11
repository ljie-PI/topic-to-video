#!/usr/bin/env python3
"""Extract JPEG frames from a video with ffmpeg.

Usage:
  python3 extract-frames.py video.mp4 frames/ --max-frames 20
  python3 extract-frames.py video.mp4 frames/ --start-time 00:01:30 --end-time 00:02:00
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

FFMPEG_TIMEOUT_SECONDS = 300
FFPROBE_TIMEOUT_SECONDS = 30
FRAME_GLOB = 'frame_*.jpg'
FRAME_PATTERN = 'frame_%04d.jpg'


def print_json(payload: dict[str, object]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get('success') else 1


def error_json(message: str) -> int:
    return print_json({'success': False, 'error': message})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Extract JPEG frames from a video with ffmpeg.')
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


def ensure_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise FileNotFoundError(f'{name} is not installed or not available on PATH')


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


def get_duration_seconds(video_path: Path) -> float:
    result = subprocess.run(
        [
            'ffprobe',
            '-v',
            'error',
            '-show_entries',
            'format=duration',
            '-of',
            'default=noprint_wrappers=1:nokey=1',
            str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=FFPROBE_TIMEOUT_SECONDS,
    )
    duration_text = result.stdout.strip()
    if not duration_text:
        raise ValueError('ffprobe returned an empty duration')
    duration = float(duration_text)
    if duration <= 0:
        raise ValueError(f'Invalid video duration: {duration_text}')
    return duration


def build_ffmpeg_command(args: argparse.Namespace, video_path: Path, output_dir: Path) -> list[str]:
    has_time_window = bool(args.start_time or args.end_time)
    if has_time_window:
        filter_expr = f"fps=1,scale='min({args.max_width},iw)':-2"
    else:
        duration = get_duration_seconds(video_path)
        interval = max(1, math.floor(duration / args.max_frames))
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
    return command


def list_frames(output_dir: Path) -> list[str]:
    frames = []
    for frame_path in sorted(output_dir.glob(FRAME_GLOB)):
        resolved = frame_path.resolve()
        if resolved.parent != output_dir:
            raise ValueError(f'Unsafe frame path detected: {frame_path}')
        if resolved.is_file():
            frames.append(frame_path.name)
    return frames


def main() -> int:
    try:
        args = parse_args()
        ensure_binary('ffmpeg')
        ensure_binary('ffprobe')
        video_path = resolve_video_path(args.video_path)
        output_dir = prepare_output_dir(args.output_dir)
        remove_existing_frames(output_dir)
        command = build_ffmpeg_command(args, video_path, output_dir)
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
        frames = list_frames(output_dir)
        return print_json(
            {
                'success': True,
                'output_dir': str(output_dir),
                'frame_count': len(frames),
                'frames': frames,
            }
        )
    except subprocess.TimeoutExpired as exc:
        command_name = exc.cmd[0] if isinstance(exc.cmd, list) and exc.cmd else 'command'
        timeout_seconds = getattr(exc, 'timeout', None) or FFMPEG_TIMEOUT_SECONDS
        return error_json(f'{command_name} timed out after {int(timeout_seconds)} seconds')
    except subprocess.CalledProcessError as exc:
        command_name = exc.cmd[0] if isinstance(exc.cmd, list) and exc.cmd else 'command'
        stderr = (exc.stderr or exc.stdout or '').strip()
        return error_json(stderr or f'{command_name} command failed')
    except Exception as exc:
        return error_json(str(exc))


if __name__ == '__main__':
    sys.exit(main())
