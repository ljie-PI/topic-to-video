"""composition/scene-config.json 的公共读取与校验契约。

覆盖计划 4.1 的校验项（画布、有限数值、合法时间范围、源场景引用、区域几何、
正的字幕规格、模板资源存在性），错误定位到 scene_id 与字段；契约文档
references/delegation/composition/scene-config.md 里的 JSON 示例必须能通过
同一个公共读取接口——示例不是只给人看的。
"""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

import pytest

import scene_config

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / 'references' / 'delegation' / 'composition' / 'scene-config.md'
LANDSCAPE = (1920, 1080)


def region(region_id: str, kind: str, rect: dict, component: str | None = None) -> dict:
    item = {'id': region_id, 'kind': kind, 'rect': rect}
    if component is not None:
        item['component'] = component
    return item


def caption_layout(preset: str | None = None, **overrides) -> dict:
    layout = {
        'preset': preset,
        'regions': [
            region('main', 'content', {'x': 96, 'y': 80, 'width': 1728, 'height': 820}),
            region('caption', 'reserved', {'x': 96, 'y': 930, 'width': 1728, 'height': 120}, 'caption-bar'),
        ],
        'caption': {'width_px': 1728, 'font_size_px': 36, 'max_lines': 2},
    }
    layout.update(overrides)
    return layout


def scene(scene_id: str, begin: float, end: float, *, sources: list[str] | None = None,
          template=None, layout: dict | None = None) -> dict:
    return {
        'scene_id': scene_id,
        'source_scene_ids': ['scene_1'] if sources is None else sources,
        'begin_s': begin,
        'end_s': end,
        'template': template,
        'layout': caption_layout() if layout is None else layout,
    }


def config(*scenes: dict, canvas: dict | None = None, total_s: float = 20.0) -> dict:
    return {
        'version': 1,
        'canvas': canvas or {'width': 1920, 'height': 1080},
        'total_s': total_s,
        'scenes': list(scenes),
    }


def problem(data: dict, **kwargs) -> str | None:
    return scene_config.scene_config_problem(data, **kwargs)


def test_valid_config_loads_snaps_boundaries_and_supports_split_merge_and_free_layout(tmp_path: Path):
    path = tmp_path / 'scene-config.json'
    path.write_text(json.dumps(config(
        scene('intro_1', 0.02, 6.0, sources=['scene_1']),
        scene('intro_2', 6.0, 10.0, sources=['scene_1']),
        scene('demo', 10.0, 19.98, sources=['scene_2', 'scene_3'], template={'name': 'github-trending', 'scene': 'project-cover'}),
    )), encoding='utf-8')

    loaded = scene_config.load_scene_config(
        path, expected_canvas=LANDSCAPE, known_scene_ids={'scene_1', 'scene_2', 'scene_3'},
        modules_root=ROOT,
    )

    assert loaded['total_s'] == 20.0
    assert [(s['scene_id'], s['begin_s'], s['end_s'], s['source_scene_ids']) for s in loaded['scenes']] == [
        ('intro_1', 0.0, 6.0, ['scene_1']),
        ('intro_2', 6.0, 10.0, ['scene_1']),
        ('demo', 10.0, 20.0, ['scene_2', 'scene_3']),
    ]
    assert loaded['scenes'][2]['template'] == {'name': 'github-trending', 'scene': 'project-cover'}
    assert loaded['scenes'][0]['template'] is None
    assert loaded['scenes'][0]['layout']['preset'] is None  # 自由布局无需注册


def test_caption_layout_segments_and_region_lookup():
    data = config(scene('a', 0, 8), scene('b', 8, 20))
    assert problem(data) is None
    segments = scene_config.caption_layout_segments(data['scenes'])
    assert [(s['scene_id'], s['begin_s'], s['end_s'], s['layout']) for s in segments] == [
        ('a', 0, 8, None), ('b', 8, 20, None),
    ]
    assert segments[0]['layout_data']['caption'] == {'width_px': 1728, 'font_size_px': 36, 'max_lines': 2}

    assert scene_config.caption_region(caption_layout())['id'] == 'caption'
    renamed = caption_layout()
    renamed['regions'][1]['id'] = 'caption-text'
    assert scene_config.caption_region(renamed)['id'] == 'caption-text'
    no_caption = caption_layout()
    no_caption['regions'] = no_caption['regions'][:1]
    assert scene_config.caption_region(no_caption) is None


def test_invalid_configs_tracking_sources_and_canvas_fail_with_located_errors():
    for mutate, expected in (
        (lambda c: c.pop('version'), 'version'),
        (lambda c: c.update(version=2), 'version'),
        (lambda c: c.pop('canvas'), 'root must contain exactly'),
        (lambda c: c.update(total_s=float('inf')), 'total_s'),
        (lambda c: c.update(total_s=-1), 'total_s'),
        (lambda c: c.update(scenes=[]), 'non-empty'),
        (lambda c: c['scenes'][0].update(scene_id='x') or c['scenes'][1].update(scene_id='x'), 'duplicate'),
        (lambda c: c['scenes'][0].update(source_scene_ids=[]), 'source_scene_ids'),
        (lambda c: c['scenes'][0].update(begin_s=-1), 'begin_s'),
        (lambda c: c['scenes'][0].update(end_s=0), 'begin_s'),
        (lambda c: c['scenes'][0].update(end_s=21), 'beyond total_s'),
        (lambda c: c['scenes'][0].pop('layout'), 'must contain exactly'),
        (lambda c: c['scenes'][0]['layout'].update(preset='missing-layout'), 'not an available layout'),
        (lambda c: c['scenes'][0].update(content_sha256='deadbeef'), 'tracking'),
    ):
        data = config(scene('a', 0, 10), scene('b', 10, 20))
        mutate(data)
        detail = problem(data, expected_canvas=LANDSCAPE, modules_root=ROOT)
        assert detail is not None and expected in detail, detail

    data = config(scene('a', 0, 20))
    assert problem(data, known_scene_ids={'scene_1'}) is None
    assert 'scene_1' in problem(data, known_scene_ids={'other'})

    portrait_region = region('main', 'content', {'x': 48, 'y': 60, 'width': 984, 'height': 1000})
    portrait_cfg = config(
        scene('a', 0, 20, layout={'preset': None, 'regions': [portrait_region], 'caption': {'width_px': 984, 'font_size_px': 40, 'max_lines': 2}}),
        canvas={'width': 1080, 'height': 1920},
    )
    assert '1080x1920' in problem(portrait_cfg, expected_canvas=LANDSCAPE)
    assert problem(portrait_cfg, expected_canvas=(1080, 1920)) is None


def test_region_geometry_caption_specs_and_template_resources_are_validated():
    for mutate, expected in (
        (lambda l: l.update(regions=[]), 'regions must be a non-empty list'),
        (lambda l: l['regions'][0].update(id='caption'), 'duplicate region id'),
        (lambda l: l['regions'][0].pop('rect'), 'must contain id, kind, rect'),
        (lambda l: l['regions'][0].update(kind='floating'), 'kind must be one of'),
        (lambda l: l['regions'][1].pop('component'), 'must declare its component'),
        (lambda l: l['regions'][0]['rect'].update(width=0), 'width / height must be positive'),
        (lambda l: l['regions'][0]['rect'].update(x=-1), 'x / y must be >= 0'),
        (lambda l: l['regions'][0]['rect'].update(width=3000), 'beyond the 1920x1080 canvas'),
        (lambda l: l['regions'][0]['rect'].update(width=float('nan')), 'finite'),
        (lambda l: l.update(caption={'width_px': 0, 'font_size_px': 36, 'max_lines': 2}), 'positive integers'),
        (lambda l: l.update(caption={'width_px': 1728, 'font_size_px': 36}), 'caption must be exactly'),
    ):
        data = config(scene('a', 0, 20))
        mutate(data['scenes'][0]['layout'])
        detail = problem(data, expected_canvas=LANDSCAPE)
        assert detail is not None and expected in detail and "'a'" in detail, detail

    for template, expected in (
        ('not-a-dict', 'template must be null or exactly'),
        ({'name': 'github-trending'}, 'template must be null or exactly'),
        ({'name': 'nope', 'scene': 'project-cover'}, 'must be null or one of'),
        ({'name': 'github-trending', 'scene': 'nope'}, 'has no scene'),
    ):
        detail = problem(config(scene('a', 0, 20, template=template)), modules_root=ROOT)
        assert detail is not None and expected in detail, detail
        if isinstance(template, dict) and set(template) == {'name', 'scene'}:
            assert problem(config(scene('a', 0, 20, template=template))) is None


def test_scene_ranges_must_be_ordered_disjoint_and_covering():
    out_of_order = config(scene('b', 10, 20), scene('a', 0, 10))
    detail = problem(out_of_order)
    assert detail is not None and 'ordered by begin_s' in detail

    overlapping = config(scene('a', 0, 10.2), scene('b', 10.0, 20))
    detail = problem(overlapping)
    assert detail is not None and 'overlaps' in detail

    gapped = config(scene('a', 0, 10), scene('b', 12, 20))
    detail = problem(gapped)
    assert detail is not None and 'uncovered' in detail

    short = config(scene('a', 0, 19), scene('b', 19, 19.5))
    detail = problem(short)
    assert detail is not None and 'cover total_s' in detail

    late_start = config(scene('a', 1, 10), scene('b', 10, 20))
    detail = problem(late_start)
    assert detail is not None and 'start at 0' in detail


def test_load_reports_path_and_problem():
    with pytest.raises(ValueError, match='cannot be read'):
        scene_config.load_scene_config(ROOT / 'no-such-file.json')
    data = config(scene('a', 0, 20))
    data['version'] = scene_config.SCENE_CONFIG_VERSION + 100
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'scene-config.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        with pytest.raises(ValueError, match='version must be'):
            scene_config.load_scene_config(path)


def doc_json_blocks() -> list[dict]:
    text = DOC.read_text(encoding='utf-8')
    return [json.loads(block) for block in re.findall(r'^```json\n(.*?)^```$', text, re.MULTILINE | re.DOTALL)]


def test_contract_doc_examples_pass_the_public_reader():
    blocks = doc_json_blocks()
    assert len(blocks) >= 2, 'scene-config.md must keep verifiable JSON examples'
    for block in blocks:
        assert problem(
            block,
            expected_canvas=LANDSCAPE,
            known_scene_ids={'scene_1', 'scene_2'},
            modules_root=ROOT,
        ) is None
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'scene-config.json'
            path.write_text(json.dumps(block), encoding='utf-8')
            loaded = scene_config.load_scene_config(
                path, expected_canvas=LANDSCAPE,
                known_scene_ids={'scene_1', 'scene_2'}, modules_root=ROOT,
            )
        assert [s['scene_id'] for s in loaded['scenes']] == [s['scene_id'] for s in block['scenes']]
