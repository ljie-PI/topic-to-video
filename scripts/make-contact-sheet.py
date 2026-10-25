#!/usr/bin/env python3
"""Build per-scene contact sheets from a rendered video.

Extracts one frame per scene at the scene's peak moment (timeline.json scene
`peak_s` when present, otherwise the scene midpoint). qa_level strict adds an
entrance frame per scene (scene begin + 0.25s) and three frames per cut point
between consecutive scenes (0.4s before / at / 0.4s after the cut, clamped to
the video duration).

Every 4 frames are montaged into one 2x2 sheet with Pillow: each frame gets a
black strip annotated with scene_id, frame kind and timestamp. Sheets are
written to the output directory (default qa/) as sheet_001.jpg, ...; the
individual annotated frames are kept under <output_dir>/frames/.

This script makes no vision calls — the main agent (and the user) look at the
sheets. Frame-to-scene mapping is reported on stdout.

Usage:
  python3 make-contact-sheet.py --video composition/renders/final.mp4 \
      --timeline transcribe/timeline.json [--output-dir qa] \
      [--qa-level standard|strict]

Output convention:
  stdout: single JSON object
    success: {"success": true, "output_dir": ..., "qa_level": ...,
              "frame_count": N, "sheet_count": M, "sheets": [...],
              "frames": [{"scene_id", "kind", "time_s", "image", "sheet", "cell"}]}
    error:   {"success": false, "error": "..."}
  stderr: human-readable progress lines prefixed with `[make-contact-sheet]`
  Exit codes: 0 = success, 1 = runtime error, 2 = invalid arguments
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from timeline_scenes import normalize_scenes

TOOL_NAME = 'make-contact-sheet'

FFMPEG_TIMEOUT_SECONDS = 300
FFPROBE_TIMEOUT_SECONDS = 30

FRAMES_PER_SHEET = 4
GRID_COLUMNS = 2
CELL_WIDTH_PX = 640
FRAME_QUALITY = 3

CUT_WINDOW_S = 0.4
ENTRANCE_OFFSET_S = 0.25

QA_LEVELS = ('standard', 'strict')

FRAME_GLOB = 'frame_*.jpg'


@dataclass
class FrameSpec:
    scene_id: str
    kind: str
    time_s: float


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


def parse_args() -> argparse.Namespace:
    parser = ArgumentParser(description='Extract per-scene frames and montage 2x2 contact sheets.')
    parser.add_argument('--video', required=True, help='Rendered video file.')
    parser.add_argument('--timeline', required=True, help='timeline.json with a scenes list.')
    parser.add_argument('--output-dir', default='qa', help='Output directory for sheets (default: qa).')
    parser.add_argument('--qa-level', default='standard', choices=QA_LEVELS, help='standard (default) or strict.')
    args = parser.parse_args()
    return args


def ensure_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise FileNotFoundError(f'{name} is not installed or not available on PATH')


def probe_duration(video_path: Path) -> float:
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
    duration = float(result.stdout.strip())
    if duration <= 0:
        raise ValueError(f'invalid video duration: {result.stdout.strip()}')
    return duration


def load_scenes(timeline_path: Path) -> list[dict[str, object]]:
    """Scene list from timeline.json (shared lenient reader).

    Invalid scenes are skipped with a warning; only a completely empty
    result is an error, since there would be nothing to build sheets from.
    """
    data = json.loads(timeline_path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'{timeline_path} is not a JSON object')
    scenes, warnings = normalize_scenes(data)
    for warning in warnings:
        log(f'timeline scenes: {warning}')
    if not scenes:
        raise ValueError(f'{timeline_path} has no valid scenes; nothing to build sheets from')
    return scenes


def clamp_time(time_s: float, duration_s: float) -> float:
    return min(max(time_s, 0.0), max(duration_s - 0.01, 0.0))


def build_frame_specs(scenes: list[dict[str, object]], qa_level: str, duration_s: float) -> list[FrameSpec]:
    specs = []
    for scene in scenes:
        scene_id = scene['scene_id']
        begin = scene['begin_s']
        end = scene['end_s']
        peak = scene['peak_s']
        if peak is None or not (begin <= peak <= end):
            peak = (begin + end) / 2
        specs.append(FrameSpec(scene_id=scene_id, kind='peak', time_s=clamp_time(peak, duration_s)))
        if qa_level == 'strict':
            entrance = clamp_time(begin + ENTRANCE_OFFSET_S, duration_s)
            specs.append(FrameSpec(scene_id=scene_id, kind='entrance', time_s=entrance))
    if qa_level == 'strict':
        for previous, current in zip(scenes, scenes[1:]):
            cut = (previous['end_s'] + current['begin_s']) / 2
            label = f"{previous['scene_id']}->{current['scene_id']}"
            specs.append(
                FrameSpec(scene_id=label, kind='cut_before', time_s=clamp_time(cut - CUT_WINDOW_S, duration_s))
            )
            specs.append(FrameSpec(scene_id=label, kind='cut_mid', time_s=clamp_time(cut, duration_s)))
            specs.append(
                FrameSpec(scene_id=label, kind='cut_after', time_s=clamp_time(cut + CUT_WINDOW_S, duration_s))
            )
    return specs


def extract_frame(video_path: Path, time_s: float, output_path: Path) -> None:
    result = subprocess.run(
        [
            'ffmpeg',
            '-hide_banner',
            '-loglevel',
            'error',
            '-y',
            '-ss',
            f'{time_s:.3f}',
            '-i',
            str(video_path),
            '-frames:v',
            '1',
            '-q:v',
            str(FRAME_QUALITY),
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=FFMPEG_TIMEOUT_SECONDS,
    )


def annotate_frame(image_path: Path, spec: FrameSpec) -> None:
    """Draw a black annotation strip (scene_id, kind, timestamp) onto the frame."""
    with Image.open(image_path) as image:
        frame = image.convert('RGB')
    width, height = frame.size
    strip_height = max(24, height // 12)
    annotation = Image.new('RGB', (width, strip_height), (0, 0, 0))
    draw = ImageDraw.Draw(annotation)
    font_size = max(14, strip_height - 10)
    try:
        font = ImageFont.load_default(size=font_size)
    except TypeError:  # pragma: no cover - Pillow < 10.1 fallback
        font = ImageFont.load_default()
    text = f'{spec.scene_id}  [{spec.kind}]  t={spec.time_s:.2f}s'
    draw.text((8, strip_height // 2), text, fill=(255, 255, 255), font=font, anchor='lm')
    combined = Image.new('RGB', (width, height + strip_height), (0, 0, 0))
    combined.paste(annotation, (0, 0))
    combined.paste(frame, (0, strip_height))
    combined.save(image_path, quality=FRAME_QUALITY)


def scale_to_width(image: Image.Image, width: int) -> Image.Image:
    if image.width == width:
        return image
    height = round(image.height * width / image.width)
    return image.resize((width, height), Image.LANCZOS)


def build_sheets(
    frames_dir: Path, specs: list[FrameSpec], output_dir: Path
) -> tuple[list[Path], list[dict[str, object]]]:
    sheet_paths = []
    mapping = []
    sheet_count = math.ceil(len(specs) / FRAMES_PER_SHEET)
    for sheet_index in range(sheet_count):
        chunk_offset = sheet_index * FRAMES_PER_SHEET
        chunk = specs[chunk_offset : chunk_offset + FRAMES_PER_SHEET]
        cells: list[tuple[FrameSpec, Path]] = []
        images = []
        for cell_index, spec in enumerate(chunk):
            frame_path = frames_dir / f'frame_{chunk_offset + cell_index + 1:03d}.jpg'
            cells.append((spec, frame_path))
            with Image.open(frame_path) as image:
                images.append(scale_to_width(image.convert('RGB'), CELL_WIDTH_PX))
        cell_height = max(image.height for image in images)
        sheet = Image.new('RGB', (CELL_WIDTH_PX * GRID_COLUMNS, cell_height * GRID_COLUMNS), (255, 255, 255))
        for cell_index, image in enumerate(images):
            left = (cell_index % GRID_COLUMNS) * CELL_WIDTH_PX
            top = (cell_index // GRID_COLUMNS) * cell_height
            sheet.paste(image, (left, top))
        sheet_path = output_dir / f'sheet_{sheet_index + 1:03d}.jpg'
        sheet.save(sheet_path, quality=FRAME_QUALITY)
        sheet_paths.append(sheet_path)
        for cell_index, (spec, frame_path) in enumerate(cells):
            mapping.append(
                {
                    'scene_id': spec.scene_id,
                    'kind': spec.kind,
                    'time_s': round(spec.time_s, 3),
                    'image': str(frame_path),
                    'sheet': str(sheet_path),
                    'cell': cell_index,
                }
            )
    return sheet_paths, mapping


def main() -> int:
    try:
        args = parse_args()
        ensure_binary('ffmpeg')
        ensure_binary('ffprobe')
        video_path = Path(args.video).expanduser()
        if not video_path.is_file():
            raise FileNotFoundError(f'video file not found: {args.video}')
        timeline_path = Path(args.timeline).expanduser()
        if not timeline_path.is_file():
            raise FileNotFoundError(f'timeline file not found: {args.timeline}')
        output_dir = Path(args.output_dir).expanduser()
        frames_dir = output_dir / 'frames'
        frames_dir.mkdir(parents=True, exist_ok=True)
        for stale in frames_dir.glob(FRAME_GLOB):
            stale.unlink()

        duration_s = probe_duration(video_path.resolve())
        scenes = load_scenes(timeline_path.resolve())
        specs = build_frame_specs(scenes, args.qa_level, duration_s)
        log(f'Extracting {len(specs)} frame(s) from {video_path} (qa_level={args.qa_level})...')
        for index, spec in enumerate(specs):
            frame_path = frames_dir / f'frame_{index + 1:03d}.jpg'
            extract_frame(video_path.resolve(), spec.time_s, frame_path)
            annotate_frame(frame_path, spec)

        sheet_paths, mapping = build_sheets(frames_dir, specs, output_dir)
        log(f'Wrote {len(sheet_paths)} sheet(s) to {output_dir}')
        return print_json(
            {
                'success': True,
                'output_dir': str(output_dir.resolve()),
                'qa_level': args.qa_level,
                'frame_count': len(specs),
                'sheet_count': len(sheet_paths),
                'sheets': [str(path.resolve()) for path in sheet_paths],
                'frames': mapping,
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


def error_json(message: str) -> int:
    log(message)
    return print_json({'success': False, 'error': message})


if __name__ == '__main__':
    sys.exit(main())
