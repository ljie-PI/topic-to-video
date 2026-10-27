#!/usr/bin/env python3
"""Deterministic post-render checks for a finished video.

Runs after composition rendering (Phase 9 final.mp4) and replaces any
whole-film frame sampling. Three families of checks, all deterministic:

  1. Container metadata checks: audio track present; container duration
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
               "findings": [{"scene_id", "check", "issue", "time_s", "frame"}],
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
from pathlib import Path

import cli
import media
from timeline_scenes import normalize_scenes, scene_ranges

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


log = cli.make_logger(TOOL_NAME)


def parse_args() -> argparse.Namespace:
    parser = cli.JsonArgumentParser(TOOL_NAME, description='Deterministic post-render checks (metadata, blackdetect, freezedetect).')
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


def load_orientation(inputs_path: Path) -> str | None:
    data = json.loads(inputs_path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'{inputs_path} is not a JSON object')
    orientation = data.get('orientation')
    return orientation if isinstance(orientation, str) else None


def load_timeline_scene_ranges(timeline_path: Path | None) -> list[tuple[str, float, float]]:
    """Optional scene time ranges from timeline.json (shared lenient reader)."""
    if timeline_path is None:
        return []
    data = json.loads(Path(timeline_path).read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'{timeline_path} is not a JSON object')
    scenes, warnings = normalize_scenes(data)
    for warning in warnings:
        log(f'timeline scenes: {warning}')
    return scene_ranges(scenes)


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
    result = media.run_ffmpeg(
        [
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
        timeout=FFMPEG_TIMEOUT_SECONDS,
    )
    return result.stderr


def parse_intervals(stderr_text: str) -> tuple[list[tuple[float, float]], list[tuple[float, float | None]]]:
    black_intervals = []
    freeze_starts: list[float] = []
    freeze_ends: list[float] = []
    line_count = 0
    unmatched_count = 0
    for line in stderr_text.splitlines():
        line_count += 1
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
            continue
        if 'black' in line or 'freeze' in line:
            unmatched_count += 1
    # Pair starts with ends in order; a start whose end never arrived (freeze
    # running into EOF) keeps None and is clamped to the container duration.
    if len(freeze_starts) != len(freeze_ends):
        log(
            f'warning: {len(freeze_starts)} freeze_start line(s) but {len(freeze_ends)} '
            f'freeze_end line(s); unpaired starts are clamped to the video end'
        )
    freeze_intervals: list[tuple[float, float | None]] = [
        (start, freeze_ends[index] if index < len(freeze_ends) else None)
        for index, start in enumerate(freeze_starts)
    ]
    log(
        f'detection log parsed: {len(black_intervals)} black interval(s), '
        f'{len(freeze_intervals)} freeze interval(s), {unmatched_count} unmatched '
        f'black/freeze line(s) out of {line_count} log lines'
    )
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
    args = parse_args()
    video_path = Path(args.video).expanduser()
    if not video_path.is_file():
        raise FileNotFoundError(f'video file not found: {args.video}')
    inputs_path = Path(args.inputs).expanduser()
    if not inputs_path.is_file():
        raise FileNotFoundError(f'inputs file not found: {args.inputs}')
    if args.timeline and not Path(args.timeline).expanduser().is_file():
        raise FileNotFoundError(f'timeline file not found: {args.timeline}')

    metadata = media.probe(video_path.resolve(), timeout=FFPROBE_TIMEOUT_SECONDS)
    if metadata['width'] is None or metadata['height'] is None:
        raise ValueError(f'no video stream found in {video_path}')
    probe = {
        'width': metadata['width'],
        'height': metadata['height'],
        'has_audio': metadata['has_audio'],
        'audio_duration_s': metadata['audio_duration_seconds'],
        'container_duration_s': metadata['duration_seconds'] or 0.0,
    }
    orientation = load_orientation(inputs_path.resolve())
    if orientation not in LANDSCAPE_ORIENTATIONS | PORTRAIT_ORIENTATIONS:
        log(f'orientation {orientation!r} not recognized; skipping orientation check')
        orientation = None
    scene_ranges = load_timeline_scene_ranges(Path(args.timeline).expanduser().resolve() if args.timeline else None)

    findings = check_container(probe, orientation)
    stderr_text = run_detection_pass(video_path.resolve(), args.black_threshold, args.freeze_threshold)
    findings.extend(
        check_black_and_freeze(
            stderr_text, probe['container_duration_s'], args.freeze_threshold, scene_ranges
        )
    )
    # Deterministic findings carry no frame reference; qa-report.json
    # requires the frame key on every finding, so default it to null.
    for finding in findings:
        finding.setdefault('frame', None)

    verdict = 'fail' if findings else 'pass'
    log(f'checks complete: {len(findings)} finding(s), verdict={verdict}')
    cli.print_json(
        {
            'success': True,
            'video': str(video_path.resolve()),
            'duration_s': round(probe['container_duration_s'], 3),
            'findings': findings,
            'verdict': verdict,
        }
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
