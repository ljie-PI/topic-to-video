#!/usr/bin/env python3
"""对成品视频做确定性的渲染后检查。

在 composition 渲染（Phase 9 的 final.mp4）之后运行，替代任何整片抽帧采样。三组
检查，都是确定性的：

  1. 容器元数据检查：存在音轨；容器时长与音频时长的偏差 <= 0.5s；视频分辨率与
     inputs.json 中记录的 orientation 对应的精确画布一致（1920×1080、1080×1920
     或 1080×1440），不是只判断横竖。
  2. 通过 ffmpeg 的 blackdetect 滤镜检测黑屏（在 ffmpeg 内部对解码帧分析）：
     任何长于 --black-threshold（默认 0.5s）的黑屏区间，以及片尾的黑屏尾巴。
  3. 通过 ffmpeg 的 freezedetect 滤镜检测定格：任何长于 --freeze-threshold
     （默认 4s）的定格区间。

两个滤镜在单次 ffmpeg 解码中运行；它们的区间报告从 stderr 解析。一直持续到文件
末尾的定格没有 freeze_end 行，会按容器时长收口。

每条发现通过 --timeline 的 scene 时间范围映射回 scene_id：Phase 8 的
composition/scene-config.json（最终视觉 scenes）或旧工程的 timeline.json 叙事
scenes 都可以直接传入（都只读 scene_id / begin_s / end_s）。当发现的时间不落
在任何 scene 内时，取中点最近的 scene；完全没有 scenes 时，scene_id 为 null。

用法：
  python3 check-render.py --video composition/renders/final.mp4 \
      --inputs inputs.json [--timeline composition/scene-config.json] \
      [--freeze-threshold 4.0] [--black-threshold 0.5]

输出约定：
  stdout: 单个 JSON 对象
    success:  {"success": true, "video": ..., "duration_s": ...,
               "findings": [{"scene_id", "check", "issue", "time_s", "frame"}],
               "verdict": "pass" | "fail"}
    error:    {"success": false, "error": "..."}
  stderr: 带 `[check-render]` 前缀的人类可读进度行
  退出码：0 = 运行完成（检查结论 pass/fail 在 JSON 里），
          1 = 运行时错误，2 = 参数非法
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import cli
import media
import video_contract
from timeline_scenes import normalize_scenes, scene_ranges

TOOL_NAME = 'check-render'

FFMPEG_TIMEOUT_SECONDS = 600
FFPROBE_TIMEOUT_SECONDS = 30

DURATION_TOLERANCE_S = 0.5
BLACK_PIX_THRESHOLD = 0.10
FREEZE_NOISE_THRESHOLD = 0.001
END_EPSILON_S = 0.1

BLACK_START_RE = re.compile(r'black_start[:=]?\s*([0-9.]+)')
BLACK_END_RE = re.compile(r'black_end[:=]?\s*([0-9.]+)')
FREEZE_START_RE = re.compile(r'freeze_start[:=]?\s*([0-9.]+)')
FREEZE_END_RE = re.compile(r'freeze_end[:=]?\s*([0-9.]+)')


log = cli.make_logger(TOOL_NAME)


def parse_args() -> argparse.Namespace:
    parser = cli.JsonArgumentParser(TOOL_NAME, description='Deterministic post-render checks (metadata, blackdetect, freezedetect).')
    parser.add_argument('--video', required=True, help='Rendered video file to check.')
    parser.add_argument('--inputs', required=True, help='inputs.json (orientation source).')
    parser.add_argument(
        '--timeline',
        help='Scene ranges for scene_id mapping: Phase 8 composition/scene-config.json (final visual '
             'scenes), or legacy timeline.json narrative scenes.',
    )
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
    problem = video_contract.orientation_problem(orientation)
    if problem:
        raise ValueError(problem)
    return orientation


def load_timeline_scene_ranges(timeline_path: Path | None) -> list[tuple[str, float, float]]:
    """scene 时间范围（共享的宽松读取器）：scene-config.json 的最终视觉 scenes
    或旧 timeline.json 的叙事 scenes，都只读 scene_id / begin_s / end_s。"""
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
    # 半开区间，使恰好从切点开始的发现归到切点之后的那个 scene；
    # 最后一个 scene 同时认领它的终点。
    final_end = max((end for _, _, end in scene_ranges), default=None)
    containing = [
        (index, scene_id, begin) for index, (scene_id, begin, end) in enumerate(scene_ranges)
        if begin <= time_s < end or (time_s == final_end and end == final_end)
    ]
    if containing:
        # 转场重叠时，后开始的视觉 scene 接管当前反馈归属。
        return max(containing, key=lambda item: (item[2], item[0]))[1]
    if not scene_ranges:
        return None
    # 回退到中点离该发现最近的 scene。
    nearest = min(scene_ranges, key=lambda r: abs((r[1] + r[2]) / 2 - time_s))
    return nearest[0]


def run_detection_pass(video_path: Path, black_threshold: float, freeze_threshold: float) -> str:
    """一次 ffmpeg 解码同时跑 blackdetect + freezedetect；返回 stderr。"""
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
    # 按顺序把 start 与 end 配对；始终没等到 end 的 start（定格跑到 EOF）保留
    # None，之后按容器时长收口。
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
    expected = video_contract.orientation_canvas(orientation)
    if expected is None:
        raise ValueError(video_contract.orientation_problem(orientation))
    if (width, height) != expected:
        findings.append(
            {
                'scene_id': None,
                'check': 'orientation',
                'issue': f'expected {orientation} {expected[0]}x{expected[1]} but video is {width}x{height}',
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
        raise FileNotFoundError(f'timeline / scene-config file not found: {args.timeline}')

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
    scene_ranges = load_timeline_scene_ranges(Path(args.timeline).expanduser().resolve() if args.timeline else None)

    findings = check_container(probe, orientation)
    stderr_text = run_detection_pass(video_path.resolve(), args.black_threshold, args.freeze_threshold)
    findings.extend(
        check_black_and_freeze(
            stderr_text, probe['container_duration_s'], args.freeze_threshold, scene_ranges
        )
    )
    # 确定性检查不带帧引用；qa-report.json 要求每条发现都有 frame 键，
    # 因此默认置为 null。
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
