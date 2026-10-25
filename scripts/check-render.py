#!/usr/bin/env python3
"""Deterministic post-render checks for a finished video.

Runs after composition rendering (Phase 9 final.mp4) and replaces any
whole-film frame sampling. Three families of checks, all deterministic:

  1. ffprobe-level container checks: audio track present; container duration
     vs audio duration deviation <= 0.5s; video resolution matches the
     orientation recorded in inputs.json (landscape: width > height;
     portrait / portrait-3:4: height > width).
  2. Black-screen detection via ffmpeg's blackdetect filter (decoded-frame
     analysis inside ffmpeg): any black segment longer than --black-threshold
     (default 0.5s), plus a black tail at the very end of the film.
  3. Freeze detection via ffmpeg's freezedetect filter: any frozen segment
     longer than --freeze-threshold (default 4s).

Both filters run in a single ffmpeg decode pass; their interval reports are
parsed from stderr. A freeze that runs to the end of the file has no
freeze_end line; it is clamped to the container duration.

Every finding is mapped back to a scene_id through the time ranges in
timeline.json's optional `scenes` list ([{scene_id, begin_s, end_s}]). When a
finding's time falls inside no scene, the scene whose midpoint is nearest is
used; when timeline.json has no scenes at all, scene_id is null.

Usage:
  python3 check-render.py --video composition/renders/final.mp4 \
      --inputs inputs.json [--timeline transcribe/timeline.json] \
      [--freeze-threshold 4.0] [--black-threshold 0.5]

Output convention:
  stdout: single JSON object
    success:  {"success": true, "video": ..., "duration_s": ...,
               "findings": [{"scene_id", "check", "issue", "time_s"}],
               "verdict": "pass" | "fail"}
    error:    {"success": false, "error": "..."}
  stderr: human-readable progress lines prefixed with `[check-render]`
  Exit codes: 0 = run completed (check verdict pass/fail is in the JSON),
              1 = runtime error, 2 = invalid arguments
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

TOOL_NAME = 'check-render'

FFMPEG_TIMEOUT_SECONDS = 600
FFPROBE_TIMEOUT_SECONDS = 30

DURATION_TOLERANCE_S = 0.5
BLACK_PIX_THRESHOLD = 0.10
FREEZE_NOISE_THRESHOLD = 0.001
END_EPSILON_S = 0.1

# inputs.json orientation values -> expected width/height relation.
LANDSCAPE_ORIENTATIONS = {'landscape'}
PORTRAIT_ORIENTATIONS = {'portrait', 'portrait-3:4', 'portrait-3x4'}

BLACK_START_RE = re.compile(r'black_start[:=]?\s*([0-9.]+)')
BLACK_END_RE = re.compile(r'black_end[:=]?\s*([0-9.]+)')
FREEZE_START_RE = re.compile(r'freeze_start[:=]?\s*([0-9.]+)')
FREEZE_END_RE = re.compile(r'freeze_end[:=]?\s*([0-9.]+)')


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        log(f'Argument error: {message}')
        print(json.dumps({'success': False, 'error': message}, ensure_ascii=False))
        self.exit(2)


def log(message: str) -> None:
    print(f'[{TOOL_NAME}] {message}', file=sys.stderr)


def print_json(payload: dict[str, object]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get('success') else 1


def error_json(message: str) -> int:
    log(message)
    return print_json({'success': False, 'error': message})


def parse_args() -> argparse.Namespace:
    parser = ArgumentParser(description='Deterministic post-render checks (ffprobe, blackdetect, freezedetect).')
    parser.add_argument('--video', required=True, help='Rendered video file to check.')
    parser.add_argument('--inputs', required=True, help='inputs.json (orientation source).')
    parser.add_argument('--timeline', help='timeline.json; optional scene time ranges for scene_id mapping.')
    parser.add_argument(
        '--freeze-threshold',
        type=float,
        default=4.0,
        help='Minimum frozen segment length in seconds (default: 4.0).',
    )
    parser.add_argument(
        '--black-threshold',
        type=float,
        default=0.5,
        help='Minimum black segment length in seconds (default: 0.5).',
    )
    args = parser.parse_args()
    if args.freeze_threshold <= 0:
        parser.error('--freeze-threshold must be greater than 0')
    if args.black_threshold <= 0:
        parser.error('--black-threshold must be greater than 0')
    return args


def ensure_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise FileNotFoundError(f'{name} is not installed or not available on PATH')


def probe_video(video_path: Path) -> dict[str, object]:
    result = subprocess.run(
        [
            'ffprobe',
            '-v',
            'error',
            '-show_entries',
            'format=duration',
            '-show_entries',
            'stream=codec_type,width,height,duration',
            '-of',
            'json',
            str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=FFPROBE_TIMEOUT_SECONDS,
    )
    data = json.loads(result.stdout)
    streams = data.get('streams') or []
    video_streams = [s for s in streams if s.get('codec_type') == 'video']
    audio_streams = [s for s in streams if s.get('codec_type') == 'audio']
    if not video_streams:
        raise ValueError(f'no video stream found in {video_path}')
    video_stream = video_streams[0]
    format_duration = float((data.get('format') or {}).get('duration') or 0)
    audio_duration = None
    if audio_streams:
        raw = audio_streams[0].get('duration')
        if raw is not None:
            audio_duration = float(raw)
    return {
        'width': int(video_stream.get('width') or 0),
        'height': int(video_stream.get('height') or 0),
        'has_audio': bool(audio_streams),
        'audio_duration_s': audio_duration,
        'container_duration_s': format_duration,
    }


def load_orientation(inputs_path: Path) -> str | None:
    data = json.loads(inputs_path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'{inputs_path} is not a JSON object')
    orientation = data.get('orientation')
    return orientation if isinstance(orientation, str) else None


def load_scene_ranges(timeline_path: Path | None) -> list[tuple[str, float, float]]:
    """Optional scene time ranges from timeline.json: [{scene_id, begin_s, end_s}]."""
    if timeline_path is None:
        return []
    data = json.loads(Path(timeline_path).read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'{timeline_path} is not a JSON object')
    raw_scenes = data.get('scenes')
    if not isinstance(raw_scenes, list):
        return []
    ranges = []
    for index, scene in enumerate(raw_scenes):
        if not isinstance(scene, dict):
            continue
        scene_id = scene.get('scene_id') or scene.get('id') or f'scene_{index + 1}'
        begin = scene.get('begin_s', scene.get('start_s'))
        end = scene.get('end_s')
        if isinstance(begin, (int, float)) and isinstance(end, (int, float)) and end > begin:
            ranges.append((str(scene_id), float(begin), float(end)))
    return ranges


def map_time_to_scene(scene_ranges: list[tuple[str, float, float]], time_s: float) -> str | None:
    # Half-open ranges so a finding starting exactly at a cut maps to the
    # scene that follows the cut; the final scene also claims its end point.
    for index, (scene_id, begin, end) in enumerate(scene_ranges):
        is_last = index == len(scene_ranges) - 1
        if begin <= time_s < end or (is_last and time_s == end):
            return scene_id
    if not scene_ranges:
        return None
    # Fall back to the scene whose midpoint is nearest to the finding.
    nearest = min(scene_ranges, key=lambda r: abs((r[1] + r[2]) / 2 - time_s))
    return nearest[0]


def run_detection_pass(video_path: Path, black_threshold: float, freeze_threshold: float) -> str:
    """One ffmpeg decode pass running blackdetect + freezedetect; returns stderr."""
    filter_expr = (
        f'blackdetect=d={black_threshold}:pix_th={BLACK_PIX_THRESHOLD},'
        f'freezedetect=n={FREEZE_NOISE_THRESHOLD}:d={freeze_threshold}'
    )
    log(f'Running detection pass: {filter_expr}')
    result = subprocess.run(
        [
            'ffmpeg',
            '-hide_banner',
            '-loglevel',
            'info',
            '-i',
            str(video_path),
            '-vf',
            filter_expr,
            '-an',
            '-f',
            'null',
            '-',
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=FFMPEG_TIMEOUT_SECONDS,
    )
    return result.stderr


def parse_intervals(stderr_text: str) -> tuple[list[tuple[float, float]], list[tuple[float, float | None]]]:
    black_intervals = []
    freeze_starts: list[float] = []
    freeze_ends: list[float] = []
    for line in stderr_text.splitlines():
        black_start = BLACK_START_RE.search(line)
        if black_start:
            black_end = BLACK_END_RE.search(line)
            start = float(black_start.group(1))
            end = float(black_end.group(1)) if black_end else start
            black_intervals.append((start, end))
            continue
        freeze_start = FREEZE_START_RE.search(line)
        if freeze_start:
            freeze_starts.append(float(freeze_start.group(1)))
            continue
        freeze_end = FREEZE_END_RE.search(line)
        if freeze_end:
            freeze_ends.append(float(freeze_end.group(1)))
    freeze_intervals: list[tuple[float, float | None]] = []
    for index, start in enumerate(freeze_starts):
        end = freeze_ends[index] if index < len(freeze_ends) else None
        freeze_intervals.append((start, end))
    return black_intervals, freeze_intervals


def check_container(probe: dict[str, object], orientation: str | None) -> list[dict[str, object]]:
    findings = []
    if not probe['has_audio']:
        findings.append(
            {
                'scene_id': None,
                'check': 'audio_track',
                'issue': 'no audio track in rendered video',
                'time_s': None,
            }
        )
    elif probe['audio_duration_s'] is not None:
        deviation = abs(probe['container_duration_s'] - float(probe['audio_duration_s']))
        if deviation > DURATION_TOLERANCE_S:
            findings.append(
                {
                    'scene_id': None,
                    'check': 'duration_deviation',
                    'issue': (
                        f'container duration {probe["container_duration_s"]:.2f}s deviates from '
                        f'audio duration {probe["audio_duration_s"]:.2f}s by {deviation:.2f}s '
                        f'(tolerance {DURATION_TOLERANCE_S}s)'
                    ),
                    'time_s': None,
                }
            )
    width = int(probe['width'])
    height = int(probe['height'])
    if orientation in LANDSCAPE_ORIENTATIONS and width <= height:
        findings.append(
            {
                'scene_id': None,
                'check': 'orientation',
                'issue': f'expected landscape (width > height) but video is {width}x{height}',
                'time_s': None,
            }
        )
    elif orientation in PORTRAIT_ORIENTATIONS and height <= width:
        findings.append(
            {
                'scene_id': None,
                'check': 'orientation',
                'issue': f'expected portrait (height > width) but video is {width}x{height}',
                'time_s': None,
            }
        )
    return findings


def check_black_and_freeze(
    stderr_text: str,
    container_duration: float,
    freeze_threshold: float,
    scene_ranges: list[tuple[str, float, float]],
) -> list[dict[str, object]]:
    findings = []
    black_intervals, freeze_intervals = parse_intervals(stderr_text)
    for start, end in black_intervals:
        duration = end - start
        scene_id = map_time_to_scene(scene_ranges, start)
        findings.append(
            {
                'scene_id': scene_id,
                'check': 'black_screen',
                'issue': f'black screen for {duration:.2f}s',
                'time_s': round(start, 3),
            }
        )
        if end >= container_duration - END_EPSILON_S:
            findings.append(
                {
                    'scene_id': scene_id,
                    'check': 'black_tail',
                    'issue': 'black tail at the end of the video',
                    'time_s': round(start, 3),
                }
            )
    for start, end in freeze_intervals:
        effective_end = end if end is not None else container_duration
        duration = effective_end - start
        findings.append(
            {
                'scene_id': map_time_to_scene(scene_ranges, start),
                'check': 'freeze',
                'issue': f'frozen picture for {duration:.2f}s (threshold {freeze_threshold}s)',
                'time_s': round(start, 3),
            }
        )
    return findings


def main() -> int:
    try:
        args = parse_args()
        ensure_binary('ffmpeg')
        ensure_binary('ffprobe')
        video_path = Path(args.video).expanduser()
        if not video_path.is_file():
            raise FileNotFoundError(f'video file not found: {args.video}')
        inputs_path = Path(args.inputs).expanduser()
        if not inputs_path.is_file():
            raise FileNotFoundError(f'inputs file not found: {args.inputs}')
        if args.timeline and not Path(args.timeline).expanduser().is_file():
            raise FileNotFoundError(f'timeline file not found: {args.timeline}')

        probe = probe_video(video_path.resolve())
        orientation = load_orientation(inputs_path.resolve())
        if orientation not in LANDSCAPE_ORIENTATIONS | PORTRAIT_ORIENTATIONS:
            log(f'orientation {orientation!r} not recognized; skipping orientation check')
            orientation = None
        scene_ranges = load_scene_ranges(Path(args.timeline).expanduser().resolve() if args.timeline else None)

        findings = check_container(probe, orientation)
        stderr_text = run_detection_pass(video_path.resolve(), args.black_threshold, args.freeze_threshold)
        findings.extend(
            check_black_and_freeze(
                stderr_text, probe['container_duration_s'], args.freeze_threshold, scene_ranges
            )
        )

        verdict = 'fail' if findings else 'pass'
        log(f'checks complete: {len(findings)} finding(s), verdict={verdict}')
        return print_json(
            {
                'success': True,
                'video': str(video_path.resolve()),
                'duration_s': round(probe['container_duration_s'], 3),
                'findings': findings,
                'verdict': verdict,
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
