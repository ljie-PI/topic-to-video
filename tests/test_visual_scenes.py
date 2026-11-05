"""Strict Phase 8 visual-scene contracts and caption-layout projection."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import video_contract

ROOT = Path(__file__).resolve().parent.parent


def declaration(*scenes: dict) -> dict:
    return {'version': 1, 'scenes': list(scenes)}


def scene(scene_id: str, begin: float, end: float, layout: str = 'stage') -> dict:
    return {'scene_id': scene_id, 'begin_s': begin, 'end_s': end, 'layout': layout}


def problem(data: dict, *, orientation: str = 'landscape', duration: float = 20) -> str | None:
    return video_contract.visual_scenes_problem(data, ROOT, orientation, duration)


def test_visual_scenes_cover_actual_duration_and_project_caption_layouts(tmp_path: Path):
    path = tmp_path / 'scenes.json'
    path.write_text(json.dumps(declaration(
        scene('intro', 0, 10, 'presenter'),
        scene('demo', 9.5, 20, 'stage'),
    )), encoding='utf-8')

    scenes = video_contract.load_visual_scenes(path, ROOT, 'landscape', 20)
    segments = video_contract.caption_layout_segments(scenes)

    assert [(s['scene_id'], s['begin_s'], s['end_s']) for s in segments] == [
        ('intro', 0, 9.5), ('demo', 9.5, 20),
    ]
    assert [s['layout'] for s in segments] == ['presenter', 'stage']
    assert video_contract.visual_layout_relpaths(scenes) == [
        'modules/layouts/presenter.json', 'modules/layouts/stage.json',
    ]


@pytest.mark.parametrize('data, expected', [
    ({}, 'version'),
    ({'version': 2, 'scenes': []}, 'version'),
    (declaration(), 'non-empty'),
    (declaration(scene('a', 0, 10), scene('a', 10, 20)), 'duplicate'),
    (declaration(scene('a', -1, 20)), 'begin_s'),
    (declaration(scene('a', 0, 0)), 'begin_s'),
    (declaration(scene('a', 0, 21)), 'beyond'),
    (declaration(scene('a', 0, 20, 'missing')), 'not an available layout'),
    (declaration(scene('a', 1, 20)), 'start at 0'),
    (declaration(scene('a', 0, 19)), 'cover narration duration'),
    (declaration(scene('a', 0, 10), scene('b', 12, 20)), 'uncovered'),
    (declaration(scene('a', 0, 10, 'presenter'), scene('b', 0, 20, 'stage')), 'ambiguous'),
])
def test_invalid_visual_scene_contracts_fail_explicitly(data: dict, expected: str):
    assert expected in problem(data)


def test_visual_scene_layout_canvas_must_match_exact_orientation():
    assert '1080x1920' in problem(
        declaration(scene('a', 0, 20, 'portrait')), orientation='portrait-3:4',
    )


def test_visual_scenes_validate_the_effective_workspace_layout_copy(tmp_path: Path):
    ws = tmp_path / 'ws'
    copy = ws / 'modules/layouts/stage.json'
    copy.parent.mkdir(parents=True)
    data = json.loads((ROOT / 'modules/layouts/stage.json').read_text(encoding='utf-8'))
    data['canvas'] = {'width': 1080, 'height': 1920}
    copy.write_text(json.dumps(data), encoding='utf-8')

    detail = video_contract.visual_scenes_problem(
        declaration(scene('a', 0, 20)), ROOT, 'landscape', 20, ws=ws,
    )
    assert '1080x1920' in detail


def test_long_earlier_scene_can_own_coverage_after_a_shorter_overlap(tmp_path: Path):
    path = tmp_path / 'scenes.json'
    path.write_text(json.dumps(declaration(
        scene('long', 0, 20), scene('short', 5, 10, 'presenter'),
    )), encoding='utf-8')

    scenes = video_contract.load_visual_scenes(path, ROOT, 'landscape', 20)
    assert [s['scene_id'] for s in video_contract.caption_layout_segments(scenes)] == ['long', 'short', 'long']
    assert [s['scene_id'] for s in video_contract.active_visual_scenes(scenes, 20)] == ['long']


def test_active_visual_scenes_include_both_sides_of_a_transition(tmp_path: Path):
    path = tmp_path / 'scenes.json'
    path.write_text(json.dumps(declaration(
        scene('a', 0, 11, 'presenter'), scene('b', 10, 20),
    )), encoding='utf-8')
    scenes = video_contract.load_visual_scenes(path, ROOT, 'landscape', 20)

    assert [s['scene_id'] for s in video_contract.active_visual_scenes(scenes, 10.5)] == ['a', 'b']
