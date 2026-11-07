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
    joined = ''.join(unit_texts(units))
    # 切点恰好落在「，」上：它成为某个单元的结尾，按字幕惯例省略尾逗号（与
    # 单 layout 入口一致）；除此之外的字符一个不丢、顺序不变。
    assert [c for c in joined if c not in '，。'] == [c for c in text if c not in '，。']
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


# --- 多场景混合（#151）：三种版面共存、scene_id、切点规则 -----------------------


def free_layout(width_px: int = 1728, font_size_px: int = 36, max_lines: int = 2) -> dict:
    return {
        'preset': None,
        'regions': [
            {'id': 'main', 'kind': 'content', 'rect': {'x': 96, 'y': 80, 'width': 1728, 'height': 820}},
            {'id': 'caption', 'kind': 'reserved', 'component': 'caption-bar',
             'rect': {'x': 96, 'y': 930, 'width': 1728, 'height': 120}},
        ],
        'caption': {'width_px': width_px, 'font_size_px': font_size_px, 'max_lines': max_lines},
    }


def words_transcript(words: list[tuple[str, int, int]]) -> list:
    """一个句子里带词级时间戳的 transcript。"""
    return [{
        'begin': words[0][1], 'end': words[-1][2],
        'text': ''.join(text for text, _, _ in words),
        'words': [{'text': text, 'begin': begin, 'end': end} for text, begin, end in words],
    }]


def cap_of(layout: dict) -> int:
    caption = layout['caption']
    return int(caption['width_px'] / caption['font_size_px']) * caption['max_lines']


def test_three_scene_kinds_keep_scene_local_budgets_and_scene_ids(tmp_path: Path):
    """模板+预设 / 无模板+另一预设 / 自由布局同片共存（#151 验收场景）。

    跨切点的句子按 scene 各自预算切分：宽 scene 里可以存在超出窄 scene 预算的
    单元，证明没有拿全片最小预算冒充逐场景规格；每个单元带自己 scene 的
    scene_id。
    """
    text = '长句子在前半段完整展示，过切点后继续。'
    narrow = free_layout(width_px=288, font_size_px=36, max_lines=1)
    transcript = words_transcript([
        ('长句子在前半段完整展示', 1400, 2900),
        ('过切点后继续', 3100, 4200),
    ])
    config = scene_config(tmp_path / 'scene-config.json',
        {**visual_scene('wide', 0, 3, layout_spec('stage')),
         'template': {'name': 'github', 'scene': 'project-cover'}},
        visual_scene('narrow', 3, 6, narrow),
    )

    proc, result, units, _ = make_workspace(tmp_path, text, {}, transcript, scene_config=config)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    narrow_cap = cap_of(narrow)
    assert narrow_cap < 12  # 确保宽 scene 的单元真的能超出窄预算
    wide_units = [u for u in units['units'] if u['scene_id'] == 'wide']
    assert wide_units and max(len(u['text']) for u in wide_units) > narrow_cap
    for unit in units['units']:
        spec = next(s['caption'] for s in units['caption_segments'] if s['scene_id'] == unit['scene_id'])
        assert len(unit['text']) <= int(spec['width_px'] / spec['font_size_px']) * spec['max_lines']
    assert {u['scene_id'] for u in units['units']} == {'wide', 'narrow'}
    # 汉字不丢、顺序不变（尾标点按字幕惯例省略）
    joined = ''.join(u['text'] for u in units['units'])
    assert [c for c in joined if c not in '，。'] == [c for c in text if c not in '，。']


def test_short_units_merge_within_but_not_across_different_layout_cuts(tmp_path: Path):
    text = '上游收尾。下游起步。'
    transcript = words_transcript([
        ('上游', 2500, 2750), ('收尾', 2750, 2950),
        ('下游', 3100, 3350), ('起步', 3350, 3550),
    ])

    different = scene_config(tmp_path / 'different.json',
        visual_scene('a', 0, 3, layout_spec('stage')),
        visual_scene('b', 3, 6, layout_spec('presenter')),
    )
    proc, result, units, _ = make_workspace(
        tmp_path, text, {}, transcript, scene_config=different,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    by_scene: dict[str, list[str]] = {}
    for unit in units['units']:
        by_scene.setdefault(unit['scene_id'], []).append(unit['text'])
    assert by_scene['a'] == ['上游收尾']
    assert by_scene['b'] == ['下游起步']
    assert any('layout cut point' in w for w in result['summary']['warnings'])

    same = scene_config(tmp_path / 'same.json',
        visual_scene('a', 0, 3, layout_spec('stage')),
        visual_scene('b', 3, 6, layout_spec('stage')),
    )
    proc, result, units, _ = make_workspace(
        tmp_path, text, {}, transcript, scene_config=same,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    # 同一版面（caption 规格一致）的切点允许合并，消除字幕闪烁
    merged = [u for u in units['units'] if u['begin_s'] < 3 < u['end_s']]
    assert len(merged) == 1
    assert merged[0]['text'] == '上游收尾。下游起步'


def test_latin_token_crossing_a_cut_fails_with_locatable_bounds(tmp_path: Path):
    text = '切换到 v2 版本继续。'
    transcript = words_transcript([
        ('切换到', 1000, 2900), ('v2', 2900, 3100), ('版本继续', 3100, 4000),
    ])
    config = scene_config(tmp_path / 'scene-config.json',
        visual_scene('wide', 0, 3, layout_spec('stage')),
        visual_scene('narrow', 3, 6, layout_spec('presenter')),
    )

    proc, result, units, _ = make_workspace(tmp_path, text, {}, transcript, scene_config=config)

    assert proc.returncode == 1
    assert units is None
    error = result['error']
    assert 'v2' in error and 'wide' in error and 'narrow' in error
    assert '2900' in error and '3100' in error  # 真实可用时间边界（ms）
    assert 'move the scene cut point or edit the subtitle' in error


def test_fallback_units_carry_scene_id(tmp_path: Path):
    text = '正常朗读的内容。'
    transcript = words_transcript([
        ('正常', 1000, 1600), ('朗读的', 1600, 2200), ('内容', 2200, 2600), ('干扰词', 2600, 3000),
    ])
    config = scene_config(tmp_path / 'scene-config.json',
        visual_scene('a', 0, 3, layout_spec('stage')),
        visual_scene('b', 3, 6, layout_spec('presenter')),
    )

    proc, result, units, _ = make_workspace(tmp_path, text, {}, transcript, scene_config=config)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert result['summary']['fallback_units'] >= 1
    fallbacks = [u for u in units['units'] if u['fallback']]
    assert fallbacks and all('scene_id' in u for u in fallbacks)


def test_silent_scenes_at_head_and_tail_keep_caption_coverage(tmp_path: Path):
    text = '只有中间一场有旁白。'
    transcript = one_word_transcript(text, begin=2500, end=3500)
    config = scene_config(tmp_path / 'scene-config.json',
        visual_scene('head', 0, 2, layout_spec('stage')),
        visual_scene('mid', 2, 4, layout_spec('presenter')),
        visual_scene('tail', 4, 6, free_layout()),
    )

    proc, _, units, _ = make_workspace(tmp_path, text, {}, transcript, scene_config=config)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert {u['scene_id'] for u in units['units']} == {'mid'}
    assert [(s['begin_s'], s['end_s']) for s in units['caption_segments']] == [(0, 2), (2, 4), (4, 6)]


def test_non_tail_merge_keeps_following_units_scene_id(tmp_path: Path):
    """中间发生短字幕合并后，合并点之后的单元 scene_id 不得错位（回归）。"""
    text = '第一句短。第二句也够短。第三句终于足够长了一些。'
    transcript = words_transcript([
        ('第一句短', 1000, 1300),
        ('第二句也够短', 1500, 2000),
        ('第三句终于足够长了一些', 3100, 3900),
    ])
    config = scene_config(tmp_path / 'scene-config.json',
        visual_scene('a', 0, 3, layout_spec('stage')),
        visual_scene('b', 3, 6, layout_spec('stage')),
    )

    proc, result, units, _ = make_workspace(tmp_path, text, {}, transcript, scene_config=config)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert result['summary']['merged_units'] == 1
    assert [(u['text'], u['scene_id']) for u in units['units']] == [
        ('第一句短。第二句也够短', 'a'),
        ('第三句终于足够长了一些', 'b'),
    ]


def test_empty_middle_scene_is_still_a_layout_cut_barrier(tmp_path: Path):
    """中间 scene 没有 atoms 时仍是「不同版面」切点：A/C 同规格也不得跨它合并。"""
    text = '上游收尾。下游起步。'
    transcript = words_transcript([
        ('上游', 2500, 2750), ('收尾', 2750, 2950),
        ('下游', 4100, 4350), ('起步', 4350, 4550),
    ])
    config = scene_config(tmp_path / 'scene-config.json',
        visual_scene('a', 0, 3, layout_spec('stage')),
        visual_scene('empty_mid', 3, 4, layout_spec('presenter')),
        visual_scene('c', 4, 6, layout_spec('stage')),
    )

    proc, result, units, _ = make_workspace(tmp_path, text, {}, transcript, scene_config=config)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    by_scene: dict[str, list[str]] = {}
    for unit in units['units']:
        by_scene.setdefault(unit['scene_id'], []).append(unit['text'])
    assert by_scene == {'a': ['上游收尾'], 'c': ['下游起步']}
    assert any('layout cut point' in w for w in result['summary']['warnings'])


def test_interior_punctuation_is_preserved_verbatim(tmp_path: Path):
    """标点只允许在单元结尾省略；单元中间的标点必须逐字保留。"""
    text = '宽场景里，逗号留在中间，切点后再继续。'
    transcript = words_transcript([
        ('宽场景里', 1000, 1600), ('逗号留在中间', 1600, 2200),
        ('切点后再继续', 3100, 3900),
    ])
    config = scene_config(tmp_path / 'scene-config.json',
        visual_scene('a', 0, 3, layout_spec('stage')),
        visual_scene('b', 3, 6, layout_spec('presenter')),
    )

    proc, _, units, _ = make_workspace(tmp_path, text, {}, transcript, scene_config=config)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert [(u['text'], u['scene_id']) for u in units['units']] == [
        ('宽场景里，逗号留在中间', 'a'),  # 中间的「，」逐字保留，仅结尾「，」省略
        ('切点后再继续', 'b'),
    ]
