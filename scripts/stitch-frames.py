#!/usr/bin/env python3
"""把 extract-frames 的 JSON 结果按时间顺序拼成 4x4 多帧图（Phase 5）。

用法：
  python3 scripts/stitch-frames.py --frames-json detail/frames.json --output-dir detail/sheets

每张 PNG 最多 16 帧，带帧号与源时间戳；不足 16 帧的格子标为 EMPTY，超过 16 帧
自动生成多张图，不丢帧。原帧不修改。相对图片路径以输入 JSON 所在目录为 base。
输出目录的 manifest.json 和 stdout 都是同一份 JSON，sheets 中每项包含 path、
start_s / end_s（首末采样时刻）、frames（原帧映射）和可传给 vision-analyze 的 prompt。
PNG 先在临时目录完整生成，再发布到独立的 generation-* 目录，最后原子切换根目录
manifest.json；旧代图片保留，不会被重跑覆盖。只读取 manifest 引用的当前代，不扫描
目录猜产物。本脚本只拼图，不调用模型；退出码 0 成功、1 运行时错误、2 参数非法。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

import cli

TOOL_NAME = 'stitch-frames'
GRID_SIZE = 4
FRAMES_PER_SHEET = GRID_SIZE * GRID_SIZE
LABEL_HEIGHT = 32
log = cli.make_logger(TOOL_NAME)


def parse_args() -> argparse.Namespace:
    parser = cli.JsonArgumentParser(TOOL_NAME, description='Stitch timestamped video frames into 4x4 sheets.')
    parser.add_argument('--frames-json', required=True, help='JSON output saved from extract-frames.py.')
    parser.add_argument('--output-dir', required=True, help='Directory for PNG sheets and manifest.json.')
    parser.add_argument('--cell-width', type=int, default=640, help='Maximum frame width per cell (default: 640).')
    args = parser.parse_args()
    if args.cell_width <= 0:
        parser.error('--cell-width must be greater than 0')
    return args


def load_frames(path: Path) -> list[dict[str, Any]]:
    from PIL import Image

    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('frames'), list) or not data['frames']:
        raise ValueError('frames JSON must contain a non-empty frames list')
    if data.get('success') is False:
        raise ValueError('Cannot stitch a failed extraction result')
    frames = []
    for index, record in enumerate(data['frames'], 1):
        if not isinstance(record, dict):
            raise ValueError(f'Frame {index} must be an object')
        raw_path, t_s = record.get('path'), record.get('t_s')
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(f'Frame {index} path must be a non-empty string')
        if isinstance(t_s, bool) or not isinstance(t_s, (int, float)) or not math.isfinite(t_s) or t_s < 0:
            raise ValueError(f'Frame {index} t_s must be a finite non-negative number')
        image_path = Path(raw_path).expanduser()
        if not image_path.is_absolute():
            image_path = path.parent / image_path
        image_path = image_path.resolve()
        # Decode pixels too: JPEG verify() alone can accept truncated image data.
        with Image.open(image_path) as image:
            image.load()
        frames.append({'path': str(image_path), 't_s': float(t_s)})
    frames.sort(key=lambda frame: frame['t_s'])
    if len({frame['t_s'] for frame in frames}) != len(frames):
        raise ValueError('Frame timestamps must be distinct')
    return frames


def analysis_prompt(frames: list[dict[str, Any]]) -> str:
    time_table = '\n'.join(f"#{frame['index']:03d}: t={frame['t_s']:.2f}s" for frame in frames)
    return (
        '这是一张 4×4 拼图，由同一视频按时间顺序采样的连续多帧拼接而成；'
        '每格是不同时间的帧，不是单张画面的空间分区。\n'
        '阅读顺序：从左到右、从上到下。请作为一个时序整体理解，不逐帧独立打分。\n'
        f"本图包含 {len(frames)} 帧，源视频采样时间范围为 {frames[0]['t_s']:.2f}s"
        f"–{frames[-1]['t_s']:.2f}s；末帧时刻不是片段终点。\n"
        '标为 EMPTY 的格子没有采样帧，不属于视频内容。帧时间是抽帧工具的采样网格，'
        '不是逐帧精确的源 PTS；不要假定采样间隙内一定发生了某个动作。\n'
        '结合相邻帧识别动作顺序、状态变化、关键 UI 和可见时间段；看不清的细节注明不确定。\n'
        f'帧号 / 源时间表：\n{time_table}'
    )


def write_sheet(frames: list[dict[str, Any]], path: Path, cell_width: int) -> None:
    from PIL import Image, ImageDraw, ImageFont

    images = []
    for frame in frames:
        with Image.open(frame['path']) as source:
            image = source.convert('RGB')
        if image.width > cell_width:
            height = max(1, round(image.height * cell_width / image.width))
            image = image.resize((cell_width, height), Image.Resampling.LANCZOS)
        images.append(image)
    body_height = max(image.height for image in images)
    cell_height = body_height + LABEL_HEIGHT
    sheet = Image.new('RGB', (cell_width * GRID_SIZE, cell_height * GRID_SIZE), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default(size=20)
    except TypeError:  # Pillow < 10.1
        font = ImageFont.load_default()
    for cell in range(FRAMES_PER_SHEET):
        left = (cell % GRID_SIZE) * cell_width
        top = (cell // GRID_SIZE) * cell_height
        draw.rectangle((left, top, left + cell_width - 1, top + cell_height - 1), outline=(80, 80, 80))
        if cell < len(frames):
            frame, image = frames[cell], images[cell]
            sheet.paste(image, (left + (cell_width - image.width) // 2, top + LABEL_HEIGHT + (body_height - image.height) // 2))
            label = f"#{frame['index']:03d}  t={frame['t_s']:.2f}s"
        else:
            label = 'EMPTY'
        draw.text((left + 8, top + LABEL_HEIGHT // 2), label, font=font, fill='white', anchor='lm')
    sheet.save(path, format='PNG')


def publish_sheets(frames: list[dict[str, Any]], output_dir: Path, cell_width: int) -> dict[str, Any]:
    """Publish complete, immutable sheets by atomically switching one manifest."""
    output_dir.mkdir(parents=True, exist_ok=True)
    generation = output_dir / f'generation-{uuid.uuid4().hex}'
    with tempfile.TemporaryDirectory(prefix='.stitch-', dir=output_dir) as temporary:
        staging = Path(temporary)
        sheets = []
        for offset in range(0, len(frames), FRAMES_PER_SHEET):
            name = f'sheet_{len(sheets) + 1:03d}.png'
            chunk = [
                {**frame, 'index': offset + cell + 1, 'cell': cell}
                for cell, frame in enumerate(frames[offset:offset + FRAMES_PER_SHEET])
            ]
            write_sheet(chunk, staging / name, cell_width)
            sheets.append({
                'path': str(generation / name),
                'frame_count': len(chunk),
                'start_s': chunk[0]['t_s'],
                'end_s': chunk[-1]['t_s'],
                'frames': chunk,
                'prompt': analysis_prompt(chunk),
            })
        result = {
            'success': True,
            'output_dir': str(output_dir),
            'frame_count': len(frames),
            'sheet_count': len(sheets),
            'sheets': sheets,
        }
        (staging / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        os.replace(staging, generation)
        # The assets already exist at fresh paths before the commit point. Never remove
        # generations here: old manifest readers may still be using them, and a failed
        # commit may leave an unreferenced (but complete) generation for later cleanup.
        os.replace(generation / 'manifest.json', output_dir / 'manifest.json')
    return result


def main() -> int:
    args = parse_args()
    frames_json = Path(args.frames_json).expanduser().resolve()
    frames = load_frames(frames_json)
    output_dir = Path(args.output_dir).expanduser().resolve()
    source_paths = {Path(frame['path']) for frame in frames} | {frames_json}
    if (output_dir / 'manifest.json').resolve() in source_paths:
        raise ValueError('Output would overwrite an input file')
    result = publish_sheets(frames, output_dir, args.cell_width)
    log(f"Stitched {len(frames)} frame(s) into {result['sheet_count']} sheet(s)")
    cli.print_json(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
