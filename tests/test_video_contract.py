"""Unit tests for the single shared pipeline contract module.

The status script, the handoff builder and the aligner all read these definitions,
so drift here shows up as contradictory rules instead of one failing check.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import video_contract
from cli_helpers import load_script_module

REPO_ROOT = Path(__file__).resolve().parent.parent


# --- Phase 1 & step field boundaries ---------------------------------------------


def test_phase_1_and_step_field_boundaries():
    assert not {'design', 'layout', 'template', 'bgm'} & set(video_contract.INPUTS_BASE_FIELDS)
    for name in ('source', 'input_mode', 'duration', 'language', 'orientation',
                 'coding_agent', 'fetch_materials'):
        assert name in video_contract.INPUTS_BASE_FIELDS

    # bgm 默认开启，属于可选布尔字段，不强制要求旧工作区补填。
    assert video_contract.bgm_applies({}) is True
    assert video_contract.bgm_applies({'bgm': True}) is True
    assert video_contract.bgm_applies({'bgm': False}) is False
    assert video_contract.input_field_problem('bgm', True) is None
    assert video_contract.input_field_problem('bgm', False) is None
    assert video_contract.input_field_problem('bgm', 'none') is not None

    for step in ('catalog', 'script'):
        assert not {'source', 'design', 'layout', 'orientation', 'template'} & set(
            video_contract.STEP_INPUTS_FIELDS[step])
    assert 'orientation' in video_contract.STEP_INPUTS_FIELDS['composition']
    assert 'design' not in video_contract.STEP_INPUTS_FIELDS['composition']
    assert 'layout' not in video_contract.STEP_INPUTS_FIELDS['composition']
    assert 'duration' not in video_contract.STEP_INPUTS_FIELDS['catalog']
    assert video_contract.STEP_REQUESTS_FIELD == {
        'catalog': None,
        'script': 'narration_requests',
        'composition': 'composition_requests',
    }


# --- orientation -> canvas ---------------------------------------------------------


def test_orientations_and_canvas_matching():
    for orientation, size in (
        ('landscape', (1920, 1080)),
        ('portrait', (1080, 1920)),
        ('portrait-3:4', (1080, 1440)),
    ):
        assert video_contract.orientation_canvas(orientation) == size
        assert video_contract.orientation_problem(orientation) is None

    for bad_orientation in ('vertical', 'portrait-3x4', '', None, 3):
        assert video_contract.orientation_canvas(bad_orientation) is None
        assert 'orientation' in video_contract.orientation_problem(bad_orientation)

    nine_by_sixteen = {'width': 1080, 'height': 1920}
    three_by_four = {'width': 1080, 'height': 1440}
    assert video_contract.canvas_problem(nine_by_sixteen, 'portrait', 'portrait') is None
    assert video_contract.canvas_problem(three_by_four, 'portrait-3:4', 'portrait-3x4') is None
    portrait_mismatch = video_contract.canvas_problem(nine_by_sixteen, 'portrait-3:4', 'portrait')
    assert '1080x1920' in portrait_mismatch and '1080x1440' in portrait_mismatch
    uhd_mismatch = video_contract.canvas_problem({'width': 3840, 'height': 2160}, 'landscape', 'landscape')
    assert '3840x2160' in uhd_mismatch and '1920x1080' in uhd_mismatch
    assert 'no canvas object' in video_contract.canvas_problem(None, 'landscape', 'landscape')
    assert 'width' in video_contract.canvas_problem({'width': 'wide'}, 'landscape', 'landscape')

    render_mod = load_script_module('check-render.py', 'check_render_contract')
    for orientation, width, height, matches in (
        ('landscape', 1920, 1080, True), ('landscape', 1280, 720, False),
        ('portrait', 1080, 1920, True), ('portrait', 1080, 1440, False),
        ('portrait-3:4', 1080, 1440, True), ('portrait-3:4', 1080, 1920, False),
    ):
        probe = dict(width=width, height=height, has_audio=True,
                     audio_duration_s=1.0, container_duration_s=1.0)
        assert (not render_mod.check_container(probe, orientation)) == matches


# --- requests & removed scene fields -----------------------------------------------


def test_requests_and_removed_scene_fields():
    assert video_contract.requests_problem('narration_requests', []) is None
    assert video_contract.requests_problem('narration_requests', ['语气更口语']) is None
    for bad in ('语气更口语', [''], ['  '], ['ok', 3], None, {'a': 1}):
        assert video_contract.requests_problem('narration_requests', bad) is not None

    assert video_contract.request_items({}, 'narration_requests') == []
    assert video_contract.request_items({'narration_requests': []}, 'narration_requests') == []
    assert video_contract.request_items({}, None) == []
    assert video_contract.request_items({'composition_requests': ['不要人物区']}, 'composition_requests') == ['不要人物区']

    assert video_contract.removed_scene_fields_problem([]) is None
    assert video_contract.removed_scene_fields_problem([
        {'scene_id': 's1', 'paragraphs': [1], 'cues': ['句子']}
    ]) is None
    for name in video_contract.REMOVED_SCENE_FIELDS:
        for value in ([], None, 'x'):
            problem = video_contract.removed_scene_fields_problem(
                [{'scene_id': 's1', 'paragraphs': [1], name: value}]
            )
            assert problem and name in problem and 'scene 0' in problem and 'composition' in problem


# --- library discovery & resource policy -------------------------------------------


def test_library_discovery_and_effective_resource_policy(tmp_path: Path):
    assert video_contract.available_designs(REPO_ROOT) == ['default', 'github', 'producthunt']
    assert video_contract.available_layouts(REPO_ROOT) == [
        'landscape',
        'landscape-presenter',
        'portrait',
        'portrait-3x4',
        'portrait-3x4-presenter',
        'portrait-presenter',
    ]
    assert video_contract.available_templates(REPO_ROOT) == ['github-trending']

    problem = video_contract.layout_contract_problem(REPO_ROOT, 'portrait-3:4')
    assert 'not an available layout' in problem and 'landscape-presenter' in problem
    assert video_contract.layout_contract_problem(REPO_ROOT, 'landscape-presenter') is None
    assert video_contract.layout_contract_problem(REPO_ROOT, 'portrait-presenter') is None
    assert video_contract.layout_contract_problem(REPO_ROOT, 'portrait-3x4-presenter') is None
    assert video_contract.template_contract_problem(REPO_ROOT, None) is None
    assert video_contract.template_contract_problem(REPO_ROOT, 'github-trending') is None
    assert "got 'nope'" in video_contract.template_contract_problem(REPO_ROOT, 'nope')

    layouts = tmp_path / 'empty_lib' / 'modules' / 'layouts'
    layouts.mkdir(parents=True)
    (layouts / 'orphan.json').write_text('{}', encoding='utf-8')
    (layouts / 'orphan-family.md').write_text('# nope', encoding='utf-8')
    assert video_contract.available_layouts(tmp_path / 'empty_lib') == []

    # portrait.md only backs portrait and portrait-3x4 — not undocumented
    # portrait-orphan.json or portrait-3x4-presenter.json without portrait-presenter.md.
    (layouts / 'portrait.md').write_text('# portrait', encoding='utf-8')
    (layouts / 'portrait-3x4.json').write_text('{}', encoding='utf-8')
    (layouts / 'portrait-orphan.json').write_text('{}', encoding='utf-8')
    (layouts / 'portrait-3x4-presenter.json').write_text('{}', encoding='utf-8')
    assert video_contract.available_layouts(tmp_path / 'empty_lib') == ['portrait-3x4']
    (layouts / 'portrait-presenter.md').write_text('# portrait-presenter', encoding='utf-8')
    assert video_contract.available_layouts(tmp_path / 'empty_lib') == ['portrait-3x4', 'portrait-3x4-presenter']

    template = tmp_path / 'bare_lib' / 'modules' / 'templates' / 'bare'
    template.mkdir(parents=True)
    (template / 'bare.md').write_text('# bare', encoding='utf-8')
    (template / 'bare.json').write_text('{"template": "bare"}', encoding='utf-8')
    assert video_contract.template_contract_problem(tmp_path / 'bare_lib', 'bare') is None

    skill = tmp_path / 'skill'
    ws = tmp_path / 'ws'
    (skill / 'modules' / 'layouts').mkdir(parents=True)
    (skill / 'modules' / 'layouts' / 'landscape-presenter.json').write_text('lib', encoding='utf-8')
    relpath = 'modules/layouts/landscape-presenter.json'
    assert video_contract.effective_resource(skill, ws, relpath, refresh=False) == skill / relpath
    (ws / 'modules' / 'layouts').mkdir(parents=True)
    copy = ws / relpath
    copy.write_text('copy', encoding='utf-8')
    assert video_contract.effective_resource(skill, ws, relpath, refresh=False) == copy
    assert video_contract.effective_resource(skill, ws, relpath, refresh=True) == skill / relpath


# --- layout files on disk & narration offsets --------------------------------------


def test_shipped_and_malformed_layout_files(tmp_path: Path):
    for layout in video_contract.available_layouts(REPO_ROOT):
        path = REPO_ROOT / 'modules' / 'layouts' / f'{layout}.json'
        canvas = json.loads(path.read_text(encoding='utf-8'))['canvas']
        orientation = next(
            name for name, size in video_contract.ORIENTATION_CANVAS.items()
            if size == (canvas['width'], canvas['height'])
        )
        assert video_contract.layout_file_problem(path, orientation, layout) is None

    good = {'layout': 'landscape', 'canvas': {'width': 1920, 'height': 1080},
            'regions': [{'id': 'main'}], 'caption': {'width_px': 100, 'font_size_px': 40, 'max_lines': 1}}
    path = tmp_path / 'landscape.json'
    path.write_text(json.dumps(good), encoding='utf-8')
    assert video_contract.layout_file_problem(path, 'landscape', 'landscape') is None

    for broken, expected in (
        ({**good, 'layout': 'other'}, 'declares layout'),
        ({**good, 'regions': []}, 'regions'),
        ({**good, 'caption': {}}, 'caption'),
        ({**good, 'caption': {'width_px': 0, 'font_size_px': 40, 'max_lines': 1}}, 'must be positive'),
    ):
        path.write_text(json.dumps(broken), encoding='utf-8')
        assert expected in video_contract.layout_file_problem(path, 'landscape', 'landscape')

    path.write_text('{not json', encoding='utf-8')
    assert 'cannot be read' in video_contract.layout_file_problem(path, 'landscape', 'landscape')


def offsets(**overrides) -> dict:
    payload = {
        'version': 1,
        'script_length': len('甲。'),
        'narration_length': len('甲。'),
        'segments': [{'narration_start': 0, 'narration_end': 2, 'script_start': 0, 'script_end': 2}],
    }
    payload.update(overrides)
    return payload


def test_narration_offsets_contract(tmp_path: Path):
    script, narration = tmp_path / 'script.txt', tmp_path / 'narration.txt'
    script.write_text('甲。', encoding='utf-8')
    narration.write_text('甲。', encoding='utf-8')
    assert video_contract.offsets_problem(offsets(), script_path=script, narration_path=narration) is None

    assert 'version' in video_contract.offsets_problem(offsets(version=2))
    assert 'segments' in video_contract.offsets_problem(offsets(segments=[]))
    for field in ('script_length', 'narration_length'):
        assert 'integer' in video_contract.offsets_problem(offsets(**{field: 2.5}))

    script.write_text('甲。乙', encoding='utf-8')
    assert 'script_length' in video_contract.offsets_problem(offsets(), script_path=script, narration_path=narration)
    script.write_text('甲。', encoding='utf-8')
    narration.write_text('甲。乙', encoding='utf-8')
    assert 'narration_length' in video_contract.offsets_problem(offsets(), script_path=script, narration_path=narration)


def test_parse_ref_ambiguity_deduplication_and_unreadable_offset_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    status_mod = load_script_module('pipeline-status.py', 'status_contract_unit')

    # Ambiguous overlapping clip windows fail regardless of list order.
    index = status_mod.CatalogIndex({'a/video'}, {'a/video': [(12, 18.5), (12.015, 18.515)]})
    for order in (index.clips['a/video'], list(reversed(index.clips['a/video']))):
        index.clips['a/video'] = order
        with pytest.raises(ValueError, match='ambiguous'):
            status_mod.parse_ref('a/video:12.009-18.509', index)

    base_catalog = {
        'topic_name': 'demo',
        'entries': [{
            'slug': 'example',
            'images': [{'id': 'img_001', 'semantic_description': '图'}],
            'videos': [{
                'id': 'vid_001',
                'semantic_description': '录屏',
                'selected_clips': [{
                    'start': 12.0, 'end': 18.5, 'reason': '关键操作',
                    'frame_paths': [], 'clip_path': 'clips/vid_001_12.00-18.50.mp4',
                }],
            }],
        }],
    }
    dup_cat = copy.deepcopy(base_catalog)
    dup_cat['entries'][0]['images'].append(dict(dup_cat['entries'][0]['images'][0]))
    with pytest.raises(ValueError, match='ambiguous'):
        status_mod.parse_ref('example/img_001', status_mod.catalog_index_from_data(dup_cat))

    dup_req = copy.deepcopy(base_catalog)
    dup_req['required_material_refs'] = ['example/vid_001:12-18.5', 'example/vid_001:12.00-18.50']
    req_res = status_mod.check_required_refs(dup_req)
    assert not req_res.ok and 'repeats' in req_res.detail

    # Unreadable script.txt during offset check is reported cleanly without ffmpeg.
    (tmp_path / 'script.txt').write_text('甲。', encoding='utf-8')
    (tmp_path / 'narration.txt').write_text('甲。', encoding='utf-8')
    (tmp_path / 'narration-offsets.json').write_text(json.dumps(offsets()), encoding='utf-8')
    real_read_text = Path.read_text

    def denied(path, *args, **kwargs):
        if path == tmp_path / 'script.txt':
            raise PermissionError('injected unreadable script.txt')
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', denied)
    offset_res = status_mod.check_narration_offsets(tmp_path, 'narration-offsets.json')
    assert not offset_res.ok and 'unreadable script.txt' in offset_res.detail
