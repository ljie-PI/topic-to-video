"""Unit tests for the single shared pipeline contract module.

The status script, the handoff builder and the aligner all read these definitions,
so drift here shows up as contradictory rules instead of one failing check.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import video_contract

REPO_ROOT = Path(__file__).resolve().parent.parent


# --- Phase 1 fields ---------------------------------------------------------------


def test_phase_1_fields_carry_no_visual_decision():
    # layout / template 是 Phase 8 的决定，不是 Phase 1 的输入。
    assert 'layout' not in video_contract.INPUTS_BASE_FIELDS
    assert 'template' not in video_contract.INPUTS_BASE_FIELDS
    for name in ('source', 'input_mode', 'duration', 'language', 'orientation', 'design',
                 'coding_agent', 'fetch_materials'):
        assert name in video_contract.INPUTS_BASE_FIELDS


def test_only_the_visual_step_reads_the_visual_fields():
    for step in ('catalog', 'script'):
        assert not {'source', 'design', 'layout', 'orientation', 'template'} & set(
            video_contract.STEP_INPUTS_FIELDS[step])
    assert {'design', 'orientation'} <= set(video_contract.STEP_INPUTS_FIELDS['composition'])
    assert 'layout' not in video_contract.STEP_INPUTS_FIELDS['composition']
    assert 'duration' not in video_contract.STEP_INPUTS_FIELDS['catalog']


def test_each_step_reads_at_most_one_request_list():
    assert video_contract.STEP_REQUESTS_FIELD == {
        'catalog': None,
        'script': 'narration_requests',
        'composition': 'composition_requests',
    }


# --- orientation -> canvas ---------------------------------------------------------


@pytest.mark.parametrize('orientation, size', [
    ('landscape', (1920, 1080)),
    ('portrait', (1080, 1920)),
    ('portrait-3:4', (1080, 1440)),
])
def test_canonical_orientations_have_one_canvas_size(orientation: str, size: tuple[int, int]):
    assert video_contract.orientation_canvas(orientation) == size
    assert video_contract.orientation_problem(orientation) is None


@pytest.mark.parametrize('orientation', ['vertical', 'portrait-3x4', '', None, 3])
def test_other_orientations_are_rejected(orientation):
    assert video_contract.orientation_canvas(orientation) is None
    assert 'orientation' in video_contract.orientation_problem(orientation)


def test_the_two_portrait_canvases_are_not_interchangeable():
    nine_by_sixteen = {'width': 1080, 'height': 1920}
    three_by_four = {'width': 1080, 'height': 1440}
    assert video_contract.canvas_problem(nine_by_sixteen, 'portrait', 'portrait') is None
    assert video_contract.canvas_problem(three_by_four, 'portrait-3:4', 'portrait-3x4') is None
    problem = video_contract.canvas_problem(nine_by_sixteen, 'portrait-3:4', 'portrait')
    assert '1080x1920' in problem and '1080x1440' in problem


def test_a_canvas_must_match_the_orientation_exactly():
    problem = video_contract.canvas_problem({'width': 3840, 'height': 2160}, 'landscape', 'stage')
    assert '3840x2160' in problem and '1920x1080' in problem


def test_a_canvas_must_be_usable():
    assert 'no canvas object' in video_contract.canvas_problem(None, 'landscape', 'stage')
    assert 'width' in video_contract.canvas_problem({'width': 'wide'}, 'landscape', 'stage')


# --- requests ----------------------------------------------------------------------


def test_requests_are_lists_of_non_empty_strings():
    assert video_contract.requests_problem('narration_requests', []) is None
    assert video_contract.requests_problem('narration_requests', ['语气更口语']) is None
    for bad in ('语气更口语', [''], ['  '], ['ok', 3], None, {'a': 1}):
        assert video_contract.requests_problem('narration_requests', bad) is not None


def test_absent_and_empty_requests_read_the_same():
    assert video_contract.request_items({}, 'narration_requests') == []
    assert video_contract.request_items({'narration_requests': []}, 'narration_requests') == []
    assert video_contract.request_items({}, None) == []
    assert video_contract.request_items({'composition_requests': ['不要人物区']}, 'composition_requests') == ['不要人物区']


# --- scene-plan.json ---------------------------------------------------------------


def test_removed_scene_fields_are_rejected_even_when_empty():
    # 模板 / pattern / 动作属于 composition：旧字段不是被忽略，而是明确报错。
    assert video_contract.removed_scene_fields_problem([]) is None
    assert video_contract.removed_scene_fields_problem([
        {'scene_id': 's1', 'paragraphs': [1], 'cues': ['句子']}
    ]) is None
    for name in video_contract.REMOVED_SCENE_FIELDS:
        for value in ([], None, 'x'):
            problem = video_contract.removed_scene_fields_problem(
                [{'scene_id': 's1', 'paragraphs': [1], name: value}]
            )
            assert problem and name in problem and 'scene 0' in problem


def test_removed_scene_field_message_points_at_composition():
    problem = video_contract.removed_scene_fields_problem([{'beats': []}])
    assert 'composition' in problem


# --- library discovery -------------------------------------------------------------


def test_the_library_registers_the_shipped_modules():
    assert video_contract.available_designs(REPO_ROOT) == ['default', 'github', 'producthunt']
    # portrait-3x4 has only a .json; portrait.md documents both portrait canvases.
    assert video_contract.available_layouts(REPO_ROOT) == ['portrait', 'portrait-3x4', 'presenter', 'stage']
    assert video_contract.available_templates(REPO_ROOT) == ['github']


def test_a_layout_without_its_own_or_shared_doc_is_not_registered(tmp_path: Path):
    layouts = tmp_path / 'modules' / 'layouts'
    layouts.mkdir(parents=True)
    (layouts / 'orphan.json').write_text('{}', encoding='utf-8')
    (layouts / 'orphan-family.md').write_text('# nope', encoding='utf-8')
    assert video_contract.available_layouts(tmp_path) == []


def test_unknown_names_are_rejected_with_the_available_ones():
    problem = video_contract.layout_contract_problem(REPO_ROOT, 'portrait-3:4')
    assert 'not an available layout' in problem and 'presenter' in problem
    assert video_contract.layout_contract_problem(REPO_ROOT, 'presenter') is None
    assert video_contract.template_contract_problem(REPO_ROOT, None) is None
    assert video_contract.template_contract_problem(REPO_ROOT, 'github') is None
    assert "got 'nope'" in video_contract.template_contract_problem(REPO_ROOT, 'nope')


def test_a_template_declares_the_layouts_it_supports():
    assert video_contract.template_layouts(REPO_ROOT, 'github') == ['presenter']
    assert video_contract.template_layouts(REPO_ROOT, 'no-such-template') is None


def test_a_template_without_a_declaration_has_no_layouts(tmp_path: Path):
    template = tmp_path / 'modules' / 'templates' / 'bare'
    template.mkdir(parents=True)
    (template / 'bare.md').write_text('# bare', encoding='utf-8')
    (template / 'bare.json').write_text('{"template": "bare"}', encoding='utf-8')
    assert video_contract.template_layouts(tmp_path, 'bare') is None


def test_the_effective_resource_follows_the_copy_then_refresh_policy(tmp_path: Path):
    skill = tmp_path / 'skill'
    ws = tmp_path / 'ws'
    (skill / 'modules' / 'layouts').mkdir(parents=True)
    (skill / 'modules' / 'layouts' / 'presenter.json').write_text('lib', encoding='utf-8')
    relpath = 'modules/layouts/presenter.json'
    assert video_contract.effective_resource(skill, ws, relpath, refresh=False) == skill / relpath

    (ws / 'modules' / 'layouts').mkdir(parents=True)
    copy = ws / relpath
    copy.write_text('copy', encoding='utf-8')
    assert video_contract.effective_resource(skill, ws, relpath, refresh=False) == copy
    # --refresh 会把副本换成库文件，所以校验库文件。
    assert video_contract.effective_resource(skill, ws, relpath, refresh=True) == skill / relpath


# --- layout files on disk -----------------------------------------------------------


def test_every_shipped_layout_satisfies_the_contract():
    for layout in video_contract.available_layouts(REPO_ROOT):
        path = REPO_ROOT / 'modules' / 'layouts' / f'{layout}.json'
        canvas = json.loads(path.read_text(encoding='utf-8'))['canvas']
        orientation = next(
            name for name, size in video_contract.ORIENTATION_CANVAS.items()
            if size == (canvas['width'], canvas['height'])
        )
        assert video_contract.layout_file_problem(path, orientation, layout) is None


def test_a_layout_file_must_carry_its_own_name_regions_and_caption(tmp_path: Path):
    good = {'layout': 'stage', 'canvas': {'width': 1920, 'height': 1080},
            'regions': [{'id': 'main'}], 'caption': {'width_px': 100, 'font_size_px': 40, 'max_lines': 1}}
    path = tmp_path / 'stage.json'
    path.write_text(json.dumps(good), encoding='utf-8')
    assert video_contract.layout_file_problem(path, 'landscape', 'stage') is None

    for broken, expected in (
        ({**good, 'layout': 'other'}, 'declares layout'),
        ({**good, 'regions': []}, 'regions'),
        ({**good, 'caption': {}}, 'caption'),
        ({**good, 'caption': {'width_px': 0, 'font_size_px': 40, 'max_lines': 1}}, 'must be positive'),
    ):
        path.write_text(json.dumps(broken), encoding='utf-8')
        problem = video_contract.layout_file_problem(path, 'landscape', 'stage')
        assert expected in problem, problem


def test_an_unreadable_layout_file_is_reported(tmp_path: Path):
    path = tmp_path / 'stage.json'
    path.write_text('{not json', encoding='utf-8')
    assert 'cannot be read' in video_contract.layout_file_problem(path, 'landscape', 'stage')


# --- narration offsets --------------------------------------------------------------


def offsets(**overrides) -> dict:
    payload = {
        'version': 1,
        'script_length': len('甲。'),
        'narration_length': len('甲。'),
        'segments': [{'narration_start': 0, 'narration_end': 2, 'script_start': 0, 'script_end': 2}],
    }
    payload.update(overrides)
    return payload


def test_a_current_offsets_table_passes(tmp_path: Path):
    script, narration = tmp_path / 'script.txt', tmp_path / 'narration.txt'
    script.write_text('甲。', encoding='utf-8')
    narration.write_text('甲。', encoding='utf-8')
    assert video_contract.offsets_problem(offsets(), script_path=script, narration_path=narration) is None


def test_offsets_require_the_version_lengths_and_segments():
    assert 'version' in video_contract.offsets_problem(offsets(version=2))
    assert 'segments' in video_contract.offsets_problem(offsets(segments=[]))
    for field in ('script_length', 'narration_length'):
        assert 'integer' in video_contract.offsets_problem(offsets(**{field: 2.5}))


def test_offsets_are_compared_against_the_source_files(tmp_path: Path):
    script, narration = tmp_path / 'script.txt', tmp_path / 'narration.txt'
    script.write_text('甲。乙', encoding='utf-8')
    narration.write_text('甲。', encoding='utf-8')
    problem = video_contract.offsets_problem(offsets(), script_path=script, narration_path=narration)
    assert 'script_length' in problem
    script.write_text('甲。', encoding='utf-8')
    narration.write_text('甲。乙', encoding='utf-8')
    problem = video_contract.offsets_problem(offsets(), script_path=script, narration_path=narration)
    assert 'narration_length' in problem