#!/usr/bin/env python3
"""Shared timeline.json scene normalization for the QA scripts.

Both check-render.py (scene_id mapping for findings) and
make-contact-sheet.py (frame extraction) need the same lenient reading of
timeline.json's optional `scenes` list. Policy: invalid scenes are skipped
with a warning, never fatal — callers decide whether an empty result is an
error (make-contact-sheet) or fine (check-render).
"""

from __future__ import annotations

from typing import Any


def normalize_scenes(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Normalize timeline.json's optional scenes list.

    Returns (scenes, warnings). Each scene is a dict with exactly scene_id,
    begin_s, and end_s. Results are sorted by begin_s. Missing `scenes` key
    and invalid entries are reported as
    warnings / skipped entries, not exceptions.
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
    """Compact (scene_id, begin_s, end_s) tuples for containment lookups."""
    return [(s['scene_id'], s['begin_s'], s['end_s']) for s in scenes]
