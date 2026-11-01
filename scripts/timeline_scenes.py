#!/usr/bin/env python3
"""QA 脚本共享的 timeline.json scene 归一化。

check-render.py（把发现映射到 scene_id）和 make-contact-sheet.py（抽帧）都需
要以同样宽松的方式读取 timeline.json 中可选的 `scenes` 列表。策略是：非法的
scene 跳过并给出警告，绝不致命——由调用方决定空结果算错误（make-contact-sheet）
还是可以接受（check-render）。
"""

from __future__ import annotations

from typing import Any


def normalize_scenes(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """归一化 timeline.json 中可选的 scenes 列表。

    返回 (scenes, warnings)。每个 scene 是只含 scene_id、begin_s、end_s 的
    dict，结果按 begin_s 排序。缺少 `scenes` 键和非法条目都会作为警告 / 被
    跳过的条目报告，而不是抛异常。
    """
    warnings: list[str] = []
    raw_scenes = data.get('scenes')
    if not isinstance(raw_scenes, list):
        return [], warnings
    scenes: list[dict[str, Any]] = []
    for index, scene in enumerate(raw_scenes):
        label = f'scene {index}'
        if not isinstance(scene, dict):
            warnings.append(f'{label} is not an object; skipped')
            continue
        scene_id = scene.get('scene_id') or f'scene_{index + 1}'
        label = f'scene {index} ({scene_id})'
        begin = scene.get('begin_s')
        end = scene.get('end_s')
        if (
            not isinstance(begin, (int, float))
            or not isinstance(end, (int, float))
            or end <= begin
        ):
            warnings.append(f'{label} has no valid begin_s / end_s range; skipped')
            continue
        scenes.append(
            {
                'scene_id': str(scene_id),
                'begin_s': float(begin),
                'end_s': float(end),
            }
        )
    scenes.sort(key=lambda s: s['begin_s'])
    return scenes, warnings


def scene_ranges(scenes: list[dict[str, Any]]) -> list[tuple[str, float, float]]:
    """用于包含关系查询的紧凑 (scene_id, begin_s, end_s) 元组。"""
    return [(s['scene_id'], s['begin_s'], s['end_s']) for s in scenes]
