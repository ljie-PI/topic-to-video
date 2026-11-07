"""Scene-aware subtitle generation against real narration-media duration."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_align_narration import make_workspace, unit_texts, write_json

pytestmark = pytest.mark.usefixtures('require_ffmpeg')

ROOT = Path(__file__).resolve().parent.parent


def layout_spec(name: str) -> dict:
    """把注册 layout 的 regions / caption 借进逐场景配置（preset 记录出处）。"""
    data = json.loads((ROOT / 'modules' / 'layouts' / f'{name}.json').read_text(encoding='utf-8'))
    return {'preset': name, 'regions': data['regions'], 'caption': data['caption']}


def visual_scene(scene_id: str, begin: float, end: float, layout: dict) -> dict:
    return {
        'scene_id': scene_id,
        'source_scene_ids': ['scene_1'],
        'begin_s': begin,
        'end_s': end,
        'template': None,
        'layout': layout,
    }


def scene_config(path: Path, *scenes: dict, total_s: float = 6.0) -> Path:
    write_json(path, {
        'version': 1,
        'canvas': {'width': 1920, 'height': 1080},
        'total_s': total_s,
        'scenes': list(scenes),
    })
    return path


def one_word_transcript(text: str, begin: int = 0, end: int = 6000) -> list:
    return [{
        'begin': begin, 'end': end, 'text': text,
        'words': [{'begin': begin, 'end': end, 'text': text}],
    }]


def test_each_visual_scene_budget_applies_without_reordering_text(tmp_path: Path):
    text = '宽场景先展示完整内容，再切换窄场景继续说明。'
    config = scene_config(tmp_path / 'scene-config.json',
        visual_scene('wide', 0, 3, layout_spec('stage')),
        visual_scene('narrow', 3, 6, layout_spec('presenter')),
    )

    proc, result, units, timeline = make_workspace(
        tmp_path, text, {}, one_word_transcript(text), scene_config=config,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert ''.join(unit_texts(units)) == text.rstrip('。')
    assert [item['layout'] for item in units['caption_segments']] == ['stage', 'presenter']
    assert [item['begin_s'] for item in units['caption_segments']] == [0, 3]
    for unit in units['units']:
        active = [s for s in units['caption_segments']
                  if s['begin_s'] < unit['end_s'] and s['end_s'] > unit['begin_s']]
        assert active
        for segment in active:
            spec = segment['caption']
            assert len(unit['text']) <= int(spec['width_px'] / spec['font_size_px']) * spec['max_lines']
    assert timeline['total_s'] == 6


def test_atom_and_version_crossing_a_boundary_use_the_whole_display_range(tmp_path: Path):
    text = '版本 5.4 在切换前后保持完整。'
    config = scene_config(tmp_path / 'scene-config.json',
        visual_scene('wide', 0, 3, layout_spec('stage')),
        visual_scene('narrow', 3, 6, layout_spec('presenter')),
    )

    proc, _, units, _ = make_workspace(
        tmp_path, text, {}, one_word_transcript(text), scene_config=config,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert any('5.4' in unit['text'] for unit in units['units'])
    assert all('5.' != unit['text'] and not unit['text'].startswith('4 ') for unit in units['units'])


def test_an_unfittable_token_fails_instead_of_being_broken(tmp_path: Path):
    text = 'Supercalifragilistic'
    narrow = {
        'preset': None,
        'regions': [
            {'id': 'main', 'kind': 'content', 'rect': {'x': 96, 'y': 100, 'width': 1048, 'height': 800}},
            {'id': 'caption', 'kind': 'reserved', 'component': 'caption-bar',
             'rect': {'x': 96, 'y': 1008, 'width': 120, 'height': 72}},
        ],
        'caption': {'width_px': 120, 'font_size_px': 40, 'max_lines': 1},
    }
    config = scene_config(tmp_path / 'scene-config.json', visual_scene('narrow', 0, 6, narrow))

    proc, result, units, _ = make_workspace(
        tmp_path, text, {}, one_word_transcript(text), scene_config=config,
    )

    assert proc.returncode == 1
    assert 'without breaking it' in result['error'] or 'exceeds its visual-scene budget' in result['error']
    assert units is None


def test_visual_coverage_includes_silent_head_and_tail_without_extra_units(tmp_path: Path):
    text = '只有中间有旁白。'
    config = scene_config(tmp_path / 'scene-config.json', visual_scene('all', 0, 6, layout_spec('stage')))

    proc, _, units, _ = make_workspace(
        tmp_path, text, {}, one_word_transcript(text, begin=1000, end=5000), scene_config=config,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert units['units'][0]['begin_s'] == 1
    assert units['units'][-1]['end_s'] == 5
    assert units['caption_segments'][0]['begin_s'] == 0
    assert units['caption_segments'][0]['end_s'] == 6


def test_subtitle_regeneration_does_not_touch_phase_7_timeline(tmp_path: Path):
    text = '先对齐时间轴，再按视觉场景生成字幕。'
    config = scene_config(tmp_path / 'scene-config.json',
        visual_scene('a', 0, 3, layout_spec('presenter')),
        visual_scene('b', 3, 6, layout_spec('stage')),
    )

    proc, _, units, timeline = make_workspace(
        tmp_path, text, {}, one_word_transcript(text), scene_config=config,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert units['units']
    assert timeline['paragraphs'][0]['end_s'] == 6
    # make_workspace runs timing after subtitles; a second subtitles run must leave it untouched.
    timeline_path = tmp_path / 'transcribe/timeline.json'
    before = timeline_path.read_bytes()
    from test_align_narration import align_args, run_cli
    rerun = run_cli(*align_args(tmp_path, 'subtitles', scene_config=config))
    assert rerun.returncode == 0, rerun.stdout + rerun.stderr
    assert timeline_path.read_bytes() == before
