"""Integration tests for scripts/pipeline-status.py.

The test seam is the script's command line (repo convention: stdout = one
JSON, exit codes 0 / 1 / 2). Fixture workspaces are built in tmp dirs.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'pipeline-status.py'

INPUTS = {
    'source': 'https://example.com/article',
    'input_mode': 'standard',
    'duration': '5min',
    'language': 'zh',
    'orientation': 'landscape',
    'template': None,
    'design': 'default',
    'layout': 'stage',
    'coding_agent': 'claude-code',
    'fetch_materials': True,
    'qa_level': 'standard',
}

RESEARCH_BRIEF = '# research brief\n\n## Key facts (verified)\n- fact [source]\n'

# duration '5min' -> 5 * 60 * 7.5 = 2250 characters, here as two paragraphs.
SCRIPT_TXT = '甲' * 1125 + '\n\n' + '乙' * 1125 + '\n'

CATALOG = {
    'topic_name': 'demo',
    'entries': [
        {
            'slug': 'example',
            'images': [{'id': 'img_001', 'semantic_description': '架构图，适合讲整体结构'}],
            'videos': [
                {
                    'id': 'vid_001',
                    'semantic_description': '演示录屏',
                    'selected_clips': [{'start': 12.0, 'end': 18.5, 'reason': '关键操作', 'frame_paths': []}],
                }
            ],
        }
    ],
}

NARRATION_OFFSETS = {'version': 1, 'segments': []}


def script_of(chars: int) -> str:
    """A two-paragraph display draft of exactly `chars` non-blank characters."""
    first = chars // 2
    return '甲' * first + '\n\n' + '乙' * (chars - first) + '\n'

SCENE_PLAN = [
    {
        'scene_id': 'scene_1',
        'paragraphs': [1, 2],
        'intent': '开场与背景',
        'facts': [],
        'material_candidates': [{'ref': 'img_001', 'score': 8, 'reason': '对应开场'}],
        'cues': [],
    }
]

# Without fetch_materials there is no catalog to refer to.
SCENE_PLAN_NO_MATERIALS = [{**SCENE_PLAN[0], 'material_candidates': []}]

TRANSCRIPT = [
    {
        'begin': 0,
        'end': 2500,
        'text': '大家好。',
        'words': [{'text': '大', 'begin': 0, 'end': 300}],
    }
]

SUBTITLE_UNITS = {'units': [{'text': '大家好', 'begin_s': 0.0, 'end_s': 2.5}]}

TIMELINE = {
    'version': 1,
    'total_s': 2.5,
    'paragraphs': [{'index': 1, 'begin_s': 0.0, 'end_s': 2.5}],
}


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def write_blob(path: Path, size: int = 128) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'\0' * size)


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def parse_result(proc: subprocess.CompletedProcess) -> dict:
    """stdout must be exactly one parseable JSON document."""
    assert proc.returncode in (0, 1, 2)
    return json.loads(proc.stdout)


def complete_through_inputs(ws: Path, **inputs_overrides) -> None:
    inputs = dict(INPUTS)
    inputs.update(inputs_overrides)
    write_json(ws / 'inputs.json', inputs)


def complete_through_research(ws: Path, **inputs_overrides) -> None:
    complete_through_inputs(ws, **inputs_overrides)
    write_text(ws / 'research-brief.md', RESEARCH_BRIEF)


def complete_through_harvest(ws: Path, **inputs_overrides) -> None:
    complete_through_research(ws, **inputs_overrides)
    write_json(
        ws / 'harvest_page' / 'manifest.json',
        {
            'entries': [{'slug': 'example', 'images': [], 'videos': []}],
            'harvest_batches': [{'at': '2026-01-01T00:00:00Z', 'urls': ['https://example.com'], 'succeeded': 1, 'failed': 0, 'rejected': []}],
        },
    )


def complete_through_catalog(ws: Path, **inputs_overrides) -> None:
    complete_through_harvest(ws, **inputs_overrides)
    write_json(ws / 'material-catalog.json', CATALOG)


def complete_through_script(ws: Path, **inputs_overrides) -> None:
    complete_through_catalog(ws, **inputs_overrides)
    write_text(ws / 'script.txt', SCRIPT_TXT)
    write_json(ws / 'tts-lexicon.json', {'OpenHuman': 'Open Human'})
    write_text(ws / 'narration.txt', '第一段旁白。\n\n第二段旁白。\n')
    write_json(ws / 'narration-offsets.json', NARRATION_OFFSETS)
    fetching = {**INPUTS, **inputs_overrides}['fetch_materials']
    write_json(ws / 'scene-plan.json', SCENE_PLAN if fetching else SCENE_PLAN_NO_MATERIALS)


def complete_through_voice_subtitles(ws: Path, **inputs_overrides) -> None:
    """Phase 7 (配音与字幕) products: narration.mp3 + transcript + units + timeline."""
    complete_through_script(ws, **inputs_overrides)
    write_blob(ws / 'voice_clone' / 'narration.mp3')
    write_json(ws / 'transcribe' / 'transcript.json', TRANSCRIPT)
    write_json(ws / 'transcribe' / 'subtitle-units.json', SUBTITLE_UNITS)
    write_json(ws / 'transcribe' / 'timeline.json', TIMELINE)


def complete_through_composition(ws: Path, **inputs_overrides) -> None:
    complete_through_voice_subtitles(ws, **inputs_overrides)
    write_text(ws / 'composition' / 'storyboard.md', '# storyboard\n\n## scene_1\n内容区域：main\n')
    write_text(ws / 'composition' / 'index.html', '<html></html>')
    write_text(ws / 'composition' / 'compositions' / 'scene_1.html', '<template></template>')
    write_json(ws / 'composition' / 'check-composition.json', {'success': True, 'verdict': 'pass', 'findings': []})
    write_blob(ws / 'composition' / 'renders' / 'final.mp4')


def complete_all(ws: Path, **inputs_overrides) -> None:
    complete_through_composition(ws, **inputs_overrides)
    write_blob(ws / 'composition' / 'renders' / 'final_with_bgm.mp4')
    write_json(ws / 'qa' / 'qa-report.json', {'findings': [], 'verdict': 'pass'})


# --- usage / workspace errors -------------------------------------------------


def test_usage_error_exits_2(tmp_path: Path):
    proc = run_cli('--bogus-flag')
    assert proc.returncode == 2
    result = parse_result(proc)
    assert result['success'] is False


def test_missing_workspace_argument_exits_2():
    # The default used to be the cwd, which is the skill root for every command in SKILL.md.
    proc = run_cli()
    assert proc.returncode == 2
    result = parse_result(proc)
    assert result['success'] is False
    assert 'workspace' in result['error']


def test_nonexistent_workspace_exits_1(tmp_path: Path):
    proc = run_cli(str(tmp_path / 'nope'))
    assert proc.returncode == 1
    result = parse_result(proc)
    assert result['success'] is False


# --- four acceptance fixtures ---------------------------------------------------


def test_empty_workspace_points_at_phase_1(tmp_path: Path):
    proc = run_cli(str(tmp_path))
    assert proc.returncode == 0
    result = parse_result(proc)
    assert result['success'] is True
    assert result['completed_phases'] == []
    assert result['next_phase']['id'] == '1-gather-inputs'
    assert result['next_phase']['doc'] == 'references/phases/01-gather-inputs.md'
    assert 'inputs.json' in result['missing_products']


def test_half_done_workspace(tmp_path: Path):
    complete_through_research(tmp_path)
    proc = run_cli(str(tmp_path))
    assert proc.returncode == 0
    result = parse_result(proc)
    assert result['completed_phases'] == ['1-gather-inputs', '3-research']
    assert result['next_phase']['id'] == '4-material-harvest'
    assert result['next_phase']['doc'] == 'references/phases/04-material-harvest.md'


def test_corrupt_product_falls_back(tmp_path: Path):
    complete_through_script(tmp_path)
    write_text(tmp_path / 'narration.txt', '')  # 写坏：空文件
    proc = run_cli(str(tmp_path))
    assert proc.returncode == 0
    result = parse_result(proc)
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'narration.txt' in result['corrupt_products']
    assert '6-script-scene-plan' not in result['completed_phases']


# --- phase 5 product: material-catalog.json items ------------------------------


def catalog_with(**changes) -> dict:
    """The default catalog with its first image replaced by {**image, **changes}."""
    catalog = json.loads(json.dumps(CATALOG))
    catalog['entries'][0]['images'][0].update(changes)
    return catalog


def assert_catalog_corrupt(tmp_path: Path, catalog, *detail_parts: str) -> None:
    complete_through_harvest(tmp_path)
    write_json(tmp_path / 'material-catalog.json', catalog)
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '5-material-catalog'
    assert 'material-catalog.json' in result['corrupt_products']
    detail = result['next_phase']['problems']['material-catalog.json']
    for part in detail_parts:
        assert part in detail, detail


def test_catalog_item_without_semantic_description_is_corrupt(tmp_path: Path):
    assert_catalog_corrupt(tmp_path, catalog_with(semantic_description=''), 'img_001', 'semantic_description')


def test_catalog_item_without_id_is_corrupt(tmp_path: Path):
    catalog = catalog_with()
    del catalog['entries'][0]['images'][0]['id']
    assert_catalog_corrupt(tmp_path, catalog, 'example', 'id')


def test_catalog_item_with_non_string_id_is_corrupt(tmp_path: Path):
    assert_catalog_corrupt(tmp_path, catalog_with(id=7), 'example', 'id')


def test_catalog_video_without_description_is_corrupt(tmp_path: Path):
    catalog = catalog_with()
    del catalog['entries'][0]['videos'][0]['semantic_description']
    assert_catalog_corrupt(tmp_path, catalog, 'vid_001', 'semantic_description')


def test_catalog_ids_repeating_across_entries_are_accepted(tmp_path: Path):
    # harvest-pages.py numbers each page's images img_001, img_002, ... from 1,
    # so two pages of one project legitimately both hold an img_001.
    catalog = catalog_with()
    other = json.loads(json.dumps(catalog['entries'][0]))
    other['slug'] = 'other'
    catalog['entries'].append(other)
    complete_through_harvest(tmp_path)
    write_json(tmp_path / 'material-catalog.json', catalog)
    result = parse_result(run_cli(str(tmp_path)))
    assert '5-material-catalog' in result['completed_phases']


def test_catalog_images_that_are_not_a_list_are_corrupt(tmp_path: Path):
    catalog = catalog_with()
    catalog['entries'][0]['images'] = {'id': 'img_001'}
    assert_catalog_corrupt(tmp_path, catalog, 'example', 'images')


def test_catalog_entry_that_is_not_an_object_is_corrupt(tmp_path: Path):
    assert_catalog_corrupt(tmp_path, {'entries': ['example']}, 'entry 0')


def test_catalog_entry_with_no_items_is_allowed(tmp_path: Path):
    complete_through_harvest(tmp_path)
    write_json(tmp_path / 'material-catalog.json', {'entries': [{'slug': 'text-only', 'images': [], 'videos': []}]})
    result = parse_result(run_cli(str(tmp_path)))
    assert '5-material-catalog' in result['completed_phases']


# --- phase 6 products: script.txt + tts-lexicon.json + narration.txt ------------


def test_missing_script_txt_falls_back_to_phase_6(tmp_path: Path):
    complete_through_script(tmp_path)
    (tmp_path / 'script.txt').unlink()
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'script.txt' in result['missing_products']


def test_blank_script_txt_is_corrupt(tmp_path: Path):
    complete_through_script(tmp_path)
    write_text(tmp_path / 'script.txt', '  \n')
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'script.txt' in result['corrupt_products']


def test_corrupt_lexicon_json_falls_back_to_phase_6(tmp_path: Path):
    complete_through_script(tmp_path)
    write_text(tmp_path / 'tts-lexicon.json', '{"OpenHuman": ')  # 截断 JSON
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'tts-lexicon.json' in result['corrupt_products']


def test_lexicon_wrong_shape_falls_back_to_phase_6(tmp_path: Path):
    complete_through_script(tmp_path)
    write_json(tmp_path / 'tts-lexicon.json', ['OpenHuman'])  # 不是 map
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'tts-lexicon.json' in result['corrupt_products']


def test_empty_lexicon_falls_back_to_phase_6(tmp_path: Path):
    complete_through_script(tmp_path)
    write_json(tmp_path / 'tts-lexicon.json', {})
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'tts-lexicon.json' in result['corrupt_products']


def test_missing_narration_txt_falls_back_to_phase_6(tmp_path: Path):
    complete_through_script(tmp_path)
    (tmp_path / 'narration.txt').unlink()
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'narration.txt' in result['missing_products']


def test_missing_narration_offsets_falls_back_to_phase_6(tmp_path: Path):
    # Phase 7's align-narration needs the offset table, so Phase 6 owns it.
    complete_through_script(tmp_path)
    (tmp_path / 'narration-offsets.json').unlink()
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'narration-offsets.json' in result['missing_products']


@pytest.mark.parametrize(
    'offsets',
    [
        ['segments'],
        {'version': 2, 'segments': []},
        {'segments': []},
        {'version': 1, 'segments': {}},
        {'version': 1},
    ],
)
def test_narration_offsets_wrong_shape_falls_back_to_phase_6(tmp_path: Path, offsets):
    complete_through_script(tmp_path)
    write_json(tmp_path / 'narration-offsets.json', offsets)
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'narration-offsets.json' in result['corrupt_products']


def test_truncated_narration_offsets_fall_back_to_phase_6(tmp_path: Path):
    complete_through_script(tmp_path)
    write_text(tmp_path / 'narration-offsets.json', '{"version": 1, "segments": [')
    result = parse_result(run_cli(str(tmp_path)))
    assert 'narration-offsets.json' in result['corrupt_products']


# --- phase 6 check: script.txt length against the target duration ---------------
#
# duration 5 min -> 5 * 60 s * 7.5 chars/s = 2250 characters, +-15% = 1912.5 .. 2587.5.


@pytest.mark.parametrize('chars', [2700, 1800])
def test_script_20_percent_off_target_is_corrupt(tmp_path: Path, chars: int):
    complete_through_script(tmp_path)
    write_text(tmp_path / 'script.txt', script_of(chars))
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'script.txt' in result['corrupt_products']
    detail = result['next_phase']['problems']['script.txt']
    assert str(chars) in detail and '2250' in detail and '20.0%' in detail, detail


@pytest.mark.parametrize('chars', [2565, 1935])
def test_script_14_percent_off_target_is_accepted(tmp_path: Path, chars: int):
    complete_through_script(tmp_path)
    write_text(tmp_path / 'script.txt', script_of(chars))
    result = parse_result(run_cli(str(tmp_path)))
    assert '6-script-scene-plan' in result['completed_phases']


def test_script_length_ignores_whitespace(tmp_path: Path):
    complete_through_script(tmp_path)
    # 2250 characters, padded with spaces, full-width spaces and extra blank lines.
    padded = '甲 ' * 1125 + '\n\n\n　　' + '乙\t' * 1125 + '\n\n'
    write_text(tmp_path / 'script.txt', padded)
    result = parse_result(run_cli(str(tmp_path)))
    assert '6-script-scene-plan' in result['completed_phases']


def test_script_length_target_follows_numeric_duration(tmp_path: Path):
    complete_through_script(tmp_path, duration=1)  # 1 min -> 450 characters
    result = parse_result(run_cli(str(tmp_path)))
    assert 'script.txt' in result['corrupt_products']
    assert '450' in result['next_phase']['problems']['script.txt']


def test_script_length_is_not_checked_while_duration_is_invalid(tmp_path: Path):
    complete_through_script(tmp_path, duration='soon')
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '1-gather-inputs'
    assert result['corrupt_products'] == ['inputs.json']


# --- phase 6 product: scene-plan.json -------------------------------------------


def test_missing_scene_plan_falls_back_to_phase_6(tmp_path: Path):
    complete_through_script(tmp_path)
    (tmp_path / 'scene-plan.json').unlink()
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'scene-plan.json' in result['missing_products']


def test_corrupt_scene_plan_falls_back_to_phase_6(tmp_path: Path):
    complete_through_script(tmp_path)
    write_text(tmp_path / 'scene-plan.json', '{"scene_id": ')  # 截断 JSON
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'scene-plan.json' in result['corrupt_products']


def test_scene_plan_missing_paragraphs_falls_back_to_phase_6(tmp_path: Path):
    complete_through_script(tmp_path)
    write_json(tmp_path / 'scene-plan.json', [{'scene_id': 'scene_1'}])
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'scene-plan.json' in result['corrupt_products']


# --- phase 6 check: scene-plan paragraphs cover script.txt exactly --------------

THREE_PARAGRAPH_SCRIPT = '甲' * 750 + '\n\n' + '乙' * 750 + '\n\n' + '丙' * 750 + '\n'  # 2250 characters


def scene(scene_id: str, paragraphs, candidates=()) -> dict:
    return {
        'scene_id': scene_id,
        'paragraphs': paragraphs,
        'intent': scene_id,
        'facts': [],
        'material_candidates': list(candidates),
        'cues': [],
    }


def scene_plan_problem(tmp_path: Path, scenes, *, script: str = SCRIPT_TXT, **inputs_overrides) -> tuple[dict, str | None]:
    """Run a Phase 6 workspace whose scene-plan.json is `scenes`; returns (result, scene-plan detail)."""
    complete_through_script(tmp_path, **inputs_overrides)
    write_text(tmp_path / 'script.txt', script)
    write_json(tmp_path / 'scene-plan.json', scenes)
    result = parse_result(run_cli(str(tmp_path)))
    problems = (result['next_phase'] or {}).get('problems', {})
    return result, problems.get('scene-plan.json')


def test_scene_plan_missing_a_paragraph_is_corrupt(tmp_path: Path):
    result, detail = scene_plan_problem(
        tmp_path, [scene('s1', [1]), scene('s2', [2])], script=THREE_PARAGRAPH_SCRIPT
    )
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'scene-plan.json' in result['corrupt_products']
    assert 'missing paragraphs [3]' in detail, detail


def test_scene_plan_paragraph_beyond_the_script_is_corrupt(tmp_path: Path):
    result, detail = scene_plan_problem(tmp_path, [scene('s1', [1, 2]), scene('s2', [3, 4])])
    assert 'scene-plan.json' in result['corrupt_products']
    assert 'out-of-range paragraphs [3, 4]' in detail, detail
    assert 'missing' not in detail


def test_scene_plan_reports_missing_and_out_of_range_together(tmp_path: Path):
    _, detail = scene_plan_problem(tmp_path, [scene('s1', [1, 5])], script=THREE_PARAGRAPH_SCRIPT)
    assert 'missing paragraphs [2, 3]' in detail and 'out-of-range paragraphs [5]' in detail, detail


def test_scene_plan_paragraph_zero_is_out_of_range(tmp_path: Path):
    _, detail = scene_plan_problem(tmp_path, [scene('s1', [0, 1, 2])])
    assert 'out-of-range paragraphs [0]' in detail, detail


@pytest.mark.parametrize('paragraphs', [['1', '2'], [1.5, 2], [True, 2], [None, 1, 2]])
def test_scene_plan_paragraphs_must_be_integers(tmp_path: Path, paragraphs):
    result, detail = scene_plan_problem(tmp_path, [scene('s1', paragraphs)])
    assert 'scene-plan.json' in result['corrupt_products']
    assert 'scene 0' in detail and 'integer' in detail, detail


def test_scene_plan_scenes_may_share_a_paragraph(tmp_path: Path):
    result, detail = scene_plan_problem(tmp_path, [scene('s1', [1, 2]), scene('s2', [2])])
    assert detail is None
    assert '6-script-scene-plan' in result['completed_phases']


def test_scene_plan_paragraph_types_are_checked_without_script_txt(tmp_path: Path):
    complete_through_script(tmp_path)
    (tmp_path / 'script.txt').unlink()
    write_json(tmp_path / 'scene-plan.json', [scene('s1', ['1', 2.5])])
    result = parse_result(run_cli(str(tmp_path)))
    assert 'scene-plan.json' in result['corrupt_products']
    assert 'integer' in result['next_phase']['problems']['scene-plan.json']


def test_scene_plan_is_not_judged_against_a_missing_script(tmp_path: Path):
    complete_through_script(tmp_path)
    (tmp_path / 'script.txt').unlink()
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert set(result['next_phase']['problems']) == {'script.txt'}


# --- phase 6 check: scene-plan material refs resolve in the catalog ---------------
#
# CATALOG holds image img_001 and video vid_001 with one selected clip 12.0-18.5.


def candidates(*refs) -> list[dict]:
    return [{'ref': ref, 'score': 7, 'reason': 'test'} for ref in refs]


@pytest.mark.parametrize(
    'ref',
    ['img_001', 'vid_001', 'vid_001:12.0-18.5', 'vid_001:12-18.5', 'vid_001:12.005-18.495'],
)
def test_scene_plan_accepts_refs_that_resolve(tmp_path: Path, ref: str):
    result, detail = scene_plan_problem(tmp_path, [scene('s1', [1, 2], candidates(ref))])
    assert detail is None
    assert '6-script-scene-plan' in result['completed_phases']


def test_scene_plan_ref_missing_from_catalog_is_corrupt(tmp_path: Path):
    result, detail = scene_plan_problem(tmp_path, [scene('s1', [1, 2], candidates('img_001', 'img_999'))])
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'scene-plan.json' in result['corrupt_products']
    assert "'img_999'" in detail and "'img_001'" not in detail, detail


@pytest.mark.parametrize(
    'ref',
    [
        'vid_001:13.0-18.5',  # start differs by 1.0
        'vid_001:12.0-18.6',  # end differs by 0.1
        'vid_999:12.0-18.5',  # no such video
        'img_001:12.0-18.5',  # an image has no clips
        'vid_001:abc-def',
        'vid_001:12.0',
        'vid_001:12.0-18.5-20',
        'vid_001:',
        ':12.0-18.5',
        'vid_001:12.0 - 18.5',  # float() would accept these; the documented form has no spaces
        'vid_001: 12-18.5',
        'vid_001:+12-18.5',
        'vid_001:1_2-18.5',
    ],
)
def test_scene_plan_clip_ref_that_matches_no_selected_clip_is_corrupt(tmp_path: Path, ref: str):
    result, detail = scene_plan_problem(tmp_path, [scene('s1', [1, 2], candidates(ref))])
    assert 'scene-plan.json' in result['corrupt_products']
    assert repr(ref) in detail, detail


def test_scene_plan_lists_every_invalid_ref(tmp_path: Path):
    scenes = [scene('s1', [1], candidates('nope_1')), scene('s2', [2], candidates('img_001', 'nope_2'))]
    _, detail = scene_plan_problem(tmp_path, scenes)
    assert "'nope_1'" in detail and "'nope_2'" in detail, detail


def test_scene_plan_without_catalog_phase_must_have_no_candidates(tmp_path: Path):
    result, detail = scene_plan_problem(
        tmp_path, [scene('s1', [1, 2], candidates('img_001'))], fetch_materials=False
    )
    assert 'scene-plan.json' in result['corrupt_products']
    assert 'fetch_materials' in detail and "'img_001'" in detail, detail


def test_scene_plan_without_catalog_phase_and_no_candidates_is_accepted(tmp_path: Path):
    result, detail = scene_plan_problem(tmp_path, [scene('s1', [1, 2])], fetch_materials=False)
    assert detail is None
    assert '6-script-scene-plan' in result['completed_phases']


def test_scene_plan_refs_are_not_judged_against_a_missing_catalog(tmp_path: Path):
    complete_through_script(tmp_path)
    (tmp_path / 'material-catalog.json').unlink()
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '5-material-catalog'
    assert 'scene-plan.json' not in result['corrupt_products']


def test_scene_plan_refs_are_not_judged_against_a_corrupt_catalog(tmp_path: Path):
    complete_through_script(tmp_path)
    write_json(tmp_path / 'material-catalog.json', catalog_with(semantic_description=''))
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '5-material-catalog'
    assert 'scene-plan.json' not in result['corrupt_products']


@pytest.mark.parametrize('bad', ['img_001', {'ref': 'img_001'}, [{'score': 8}], [{'ref': ''}], [{'ref': 7}], ['img_001']])
def test_scene_plan_malformed_material_candidates_are_corrupt(tmp_path: Path, bad):
    scenes = [scene('s1', [1, 2])]
    scenes[0]['material_candidates'] = bad
    result, detail = scene_plan_problem(tmp_path, scenes)
    assert 'scene-plan.json' in result['corrupt_products']
    assert 'scene 0' in detail and 'material_candidates' in detail, detail


# --- phase 7 products (配音与字幕): narration.mp3 + transcript + units + timeline


def test_missing_narration_mp3_falls_back_to_phase_7(tmp_path: Path):
    complete_through_voice_subtitles(tmp_path)
    (tmp_path / 'voice_clone' / 'narration.mp3').unlink()
    proc = run_cli(str(tmp_path))
    assert proc.returncode == 0
    result = parse_result(proc)
    assert result['next_phase']['id'] == '7-voice-subtitles'
    assert result['next_phase']['doc'] == 'references/phases/07-voice-subtitles.md'
    assert 'voice_clone/narration.mp3' in result['missing_products']
    assert '7-voice-subtitles' not in result['completed_phases']


def test_missing_transcript_falls_back_to_phase_7(tmp_path: Path):
    complete_through_voice_subtitles(tmp_path)
    (tmp_path / 'transcribe' / 'transcript.json').unlink()
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '7-voice-subtitles'
    assert 'transcribe/transcript.json' in result['missing_products']


def test_corrupt_transcript_falls_back_to_phase_7(tmp_path: Path):
    complete_through_voice_subtitles(tmp_path)
    write_json(tmp_path / 'transcribe' / 'transcript.json', [{'begin': 0}])  # 缺字段
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '7-voice-subtitles'
    assert 'transcribe/transcript.json' in result['corrupt_products']


def test_missing_subtitle_units_falls_back_to_phase_7(tmp_path: Path):
    complete_through_voice_subtitles(tmp_path)
    (tmp_path / 'transcribe' / 'subtitle-units.json').unlink()
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '7-voice-subtitles'
    assert 'transcribe/subtitle-units.json' in result['missing_products']


def test_missing_timeline_falls_back_to_phase_7(tmp_path: Path):
    complete_through_voice_subtitles(tmp_path)
    (tmp_path / 'transcribe' / 'timeline.json').unlink()
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '7-voice-subtitles'
    assert 'transcribe/timeline.json' in result['missing_products']
    assert '7-voice-subtitles' not in result['completed_phases']


def test_corrupt_timeline_falls_back_to_phase_7(tmp_path: Path):
    complete_through_voice_subtitles(tmp_path)
    write_json(tmp_path / 'transcribe' / 'timeline.json', {'paragraphs': []})
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '7-voice-subtitles'
    assert 'transcribe/timeline.json' in result['corrupt_products']


def test_truncated_timeline_json_falls_back_to_phase_7(tmp_path: Path):
    complete_through_voice_subtitles(tmp_path)
    write_text(tmp_path / 'transcribe' / 'timeline.json', '{"paragraphs": [')  # 截断 JSON
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '7-voice-subtitles'
    assert 'transcribe/timeline.json' in result['corrupt_products']


def test_corrupt_subtitle_units_falls_back_to_phase_7(tmp_path: Path):
    complete_through_voice_subtitles(tmp_path)
    write_json(tmp_path / 'transcribe' / 'subtitle-units.json', {'units': []})
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '7-voice-subtitles'
    assert 'transcribe/subtitle-units.json' in result['corrupt_products']


# --- phase 8 products: composition index.html + final.mp4 ------------------------


def test_missing_composition_index_falls_back_to_phase_8(tmp_path: Path):
    complete_through_composition(tmp_path)
    (tmp_path / 'composition' / 'index.html').unlink()
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '8-composition'
    assert result['next_phase']['doc'] == 'references/phases/08-composition.md'
    assert 'composition/index.html' in result['missing_products']
    assert '8-composition' not in result['completed_phases']


def test_missing_storyboard_falls_back_to_phase_8(tmp_path: Path):
    complete_through_composition(tmp_path)
    (tmp_path / 'composition' / 'storyboard.md').unlink()
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '8-composition'
    assert 'composition/storyboard.md' in result['missing_products']


def test_blank_storyboard_falls_back_to_phase_8(tmp_path: Path):
    complete_through_composition(tmp_path)
    write_text(tmp_path / 'composition' / 'storyboard.md', ' \n')
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '8-composition'
    assert 'composition/storyboard.md' in result['corrupt_products']


def test_missing_compositions_dir_falls_back_to_phase_8(tmp_path: Path):
    complete_through_composition(tmp_path)
    (tmp_path / 'composition' / 'compositions' / 'scene_1.html').unlink()
    (tmp_path / 'composition' / 'compositions').rmdir()
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '8-composition'
    assert 'composition/compositions' in result['missing_products']


def test_empty_compositions_dir_falls_back_to_phase_8(tmp_path: Path):
    complete_through_composition(tmp_path)
    (tmp_path / 'composition' / 'compositions' / 'scene_1.html').unlink()
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '8-composition'
    assert 'composition/compositions' in result['corrupt_products']
    assert 'no files' in result['next_phase']['problems']['composition/compositions']


def test_compositions_dir_with_only_hidden_files_falls_back_to_phase_8(tmp_path: Path):
    complete_through_composition(tmp_path)
    (tmp_path / 'composition' / 'compositions' / 'scene_1.html').unlink()
    write_text(tmp_path / 'composition' / 'compositions' / '.DS_Store', 'junk')
    result = parse_result(run_cli(str(tmp_path)))
    assert 'composition/compositions' in result['corrupt_products']


def test_compositions_that_is_a_file_falls_back_to_phase_8(tmp_path: Path):
    complete_through_composition(tmp_path)
    (tmp_path / 'composition' / 'compositions' / 'scene_1.html').unlink()
    (tmp_path / 'composition' / 'compositions').rmdir()
    write_text(tmp_path / 'composition' / 'compositions', 'not a directory')
    result = parse_result(run_cli(str(tmp_path)))
    assert 'composition/compositions' in result['corrupt_products']


def test_compositions_dir_with_a_nested_file_is_accepted(tmp_path: Path):
    complete_through_composition(tmp_path)
    (tmp_path / 'composition' / 'compositions' / 'scene_1.html').unlink()
    write_text(tmp_path / 'composition' / 'compositions' / 'scene_1' / 'index.html', '<template></template>')
    result = parse_result(run_cli(str(tmp_path)))
    assert '8-composition' in result['completed_phases']


def test_missing_check_composition_report_falls_back_to_phase_8(tmp_path: Path):
    complete_through_composition(tmp_path)
    (tmp_path / 'composition' / 'check-composition.json').unlink()
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '8-composition'
    assert 'composition/check-composition.json' in result['missing_products']


def test_failing_check_composition_report_falls_back_to_phase_8(tmp_path: Path):
    complete_through_composition(tmp_path)
    write_json(
        tmp_path / 'composition' / 'check-composition.json',
        {'success': True, 'verdict': 'fail', 'findings': [{'scene_id': 's1', 'check': 'overflow'}]},
    )
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '8-composition'
    assert 'composition/check-composition.json' in result['corrupt_products']
    assert "'fail'" in result['next_phase']['problems']['composition/check-composition.json']


@pytest.mark.parametrize('report', [['pass'], {'success': True}, {'verdict': 'PASS'}])
def test_malformed_check_composition_report_falls_back_to_phase_8(tmp_path: Path, report):
    complete_through_composition(tmp_path)
    write_json(tmp_path / 'composition' / 'check-composition.json', report)
    result = parse_result(run_cli(str(tmp_path)))
    assert 'composition/check-composition.json' in result['corrupt_products']


def test_truncated_check_composition_report_falls_back_to_phase_8(tmp_path: Path):
    complete_through_composition(tmp_path)
    write_text(tmp_path / 'composition' / 'check-composition.json', '{"verdict": ')
    result = parse_result(run_cli(str(tmp_path)))
    assert 'composition/check-composition.json' in result['corrupt_products']


def test_missing_final_mp4_falls_back_to_phase_8(tmp_path: Path):
    complete_through_composition(tmp_path)
    (tmp_path / 'composition' / 'renders' / 'final.mp4').unlink()
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '8-composition'
    assert 'composition/renders/final.mp4' in result['missing_products']


def test_truncated_json_falls_back(tmp_path: Path):
    complete_through_research(tmp_path)
    write_text(tmp_path / 'research-brief.md', RESEARCH_BRIEF)
    write_text(tmp_path / 'harvest_page' / 'manifest.json', '{"entries": [')  # 截断 JSON
    proc = run_cli(str(tmp_path))
    assert proc.returncode == 0
    result = parse_result(proc)
    assert result['next_phase']['id'] == '4-material-harvest'
    assert 'harvest_page/manifest.json' in result['corrupt_products']


def test_all_complete(tmp_path: Path):
    complete_all(tmp_path)
    proc = run_cli(str(tmp_path))
    assert proc.returncode == 0
    result = parse_result(proc)
    assert result['completed_phases'] == [
        '1-gather-inputs',
        '3-research',
        '4-material-harvest',
        '5-material-catalog',
        '6-script-scene-plan',
        '7-voice-subtitles',
        '8-composition',
        '9-check-mix',
    ]
    assert result['next_phase'] is None
    assert result['missing_products'] == []
    assert result['corrupt_products'] == []


# --- conditional phases ---------------------------------------------------------


def test_paper_mode_includes_paper_parse(tmp_path: Path):
    complete_through_inputs(tmp_path, input_mode='paper')
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '2-paper-parse'
    assert result['next_phase']['doc'] == 'references/phases/02-paper-parse.md'


def test_paper_parse_product_validated(tmp_path: Path):
    complete_through_inputs(tmp_path, input_mode='paper')
    metadata = {
        'slug': 'main-paper',
        'success': True,
        'source_type': 'paper_pdf',
        'paper_metadata': {'full_markdown_path': 'main-paper/full.md'},
    }
    write_json(tmp_path / 'harvest_page' / 'main-paper' / 'metadata.json', metadata)
    write_text(tmp_path / 'harvest_page' / 'main-paper' / 'full.md', '# paper\n')
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert '2-paper-parse' in result['completed_phases']
    assert result['next_phase']['id'] == '3-research'


def test_paper_only_manifest_without_harvest_batches_does_not_complete_phase_4(tmp_path: Path):
    complete_through_research(tmp_path, input_mode='paper', fetch_materials=True)
    paper = {
        'slug': 'main-paper', 'success': True, 'source_type': 'paper_pdf',
        'paper_metadata': {'full_markdown_path': 'main-paper/mineru/full.md'},
        'images': [], 'videos': [],
    }
    write_json(tmp_path / 'harvest_page' / 'main-paper' / 'metadata.json', paper)
    write_json(tmp_path / 'harvest_page' / 'manifest.json', {'version': 2, 'entries': [paper]})

    result = parse_result(run_cli(str(tmp_path)))

    assert '2-paper-parse' in result['completed_phases']
    assert result['next_phase']['id'] == '4-material-harvest'
    assert '4-material-harvest' not in result['completed_phases']


def test_standard_mode_skips_paper_parse(tmp_path: Path):
    complete_through_research(tmp_path)
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '4-material-harvest'
    assert '2-paper-parse' not in result['completed_phases']
    assert '2-paper-parse' in result['skipped_phases']


def test_no_fetch_skips_harvest_and_catalog(tmp_path: Path):
    complete_through_research(tmp_path, fetch_materials=False)
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['completed_phases'] == ['1-gather-inputs', '3-research']
    assert '4-material-harvest' in result['skipped_phases']
    assert '5-material-catalog' in result['skipped_phases']
    assert result['next_phase']['id'] == '6-script-scene-plan'


def test_no_fetch_full_run(tmp_path: Path):
    complete_all(tmp_path, fetch_materials=False)
    proc = run_cli(str(tmp_path))
    assert proc.returncode == 0
    result = parse_result(proc)
    assert result['next_phase'] is None
    assert '4-material-harvest' not in result['completed_phases']
    assert '5-material-catalog' not in result['completed_phases']


# --- inputs.json validation -----------------------------------------------------


def test_inputs_json_missing_required_field_falls_back(tmp_path: Path):
    complete_through_research(tmp_path)
    inputs = dict(INPUTS)
    del inputs['design']
    write_json(tmp_path / 'inputs.json', inputs)
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '1-gather-inputs'
    assert 'inputs.json' in result['corrupt_products']


def test_removed_design_falls_back_to_phase_1(tmp_path: Path):
    complete_through_research(tmp_path)
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'design': 'moon'})
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '1-gather-inputs'
    assert 'inputs.json' in result['corrupt_products']
    detail = result['next_phase']['problems']['inputs.json']
    assert "'moon'" in detail and 'default' in detail and 'github' in detail


def test_removed_design_keeps_mode_flags(tmp_path: Path):
    complete_through_research(tmp_path)
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'design': 'moon', 'input_mode': 'paper', 'fetch_materials': False})
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '1-gather-inputs'
    assert result['input_mode'] == 'paper'
    assert result['fetch_materials'] is False
    assert '4-material-harvest' in result['skipped_phases']


def test_removed_design_accepted_from_workspace_copy(tmp_path: Path):
    complete_through_research(tmp_path)
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'design': 'moon'})
    copy = tmp_path / 'modules' / 'designs' / 'moon'
    copy.mkdir(parents=True)
    (copy / 'moon.md').write_text('# moon', encoding='utf-8')
    write_json(copy / 'fonts.json', {'css_filename': 'moon-fonts.css', 'css2_families': ['X']})
    result = parse_result(run_cli(str(tmp_path)))
    assert 'inputs.json' not in result['corrupt_products']
    assert result['next_phase']['id'] != '1-gather-inputs'


@pytest.mark.parametrize('duration', [5, 7.5, '5min', ' 10 分钟', '3.5', '5 minutes', '2 mins', '4分'])
def test_duration_in_minutes_is_accepted(tmp_path: Path, duration):
    complete_through_research(tmp_path, duration=duration)
    result = parse_result(run_cli(str(tmp_path)))
    assert 'inputs.json' not in result['corrupt_products']
    assert result['next_phase']['id'] == '4-material-harvest'


@pytest.mark.parametrize(
    'duration',
    ['five minutes', '', 'min5', 0, -5, '0min', True, None, [5], '90s', '30秒', '1h', '3-5 min', '5 min left'],
)
def test_duration_without_a_minutes_number_is_corrupt_inputs(tmp_path: Path, duration):
    complete_through_research(tmp_path, duration=duration)
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '1-gather-inputs'
    assert 'inputs.json' in result['corrupt_products']
    detail = result['next_phase']['problems']['inputs.json']
    assert 'duration' in detail and '分钟' in detail


def test_missing_qa_level_defaults_to_standard(tmp_path: Path):
    complete_through_research(tmp_path)
    inputs = dict(INPUTS)
    del inputs['qa_level']
    write_json(tmp_path / 'inputs.json', inputs)
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '4-material-harvest'
    assert 'inputs.json' not in result['corrupt_products']


def test_invalid_qa_level_is_corrupt_inputs(tmp_path: Path):
    complete_through_research(tmp_path, qa_level='exhaustive')
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '1-gather-inputs'
    assert 'inputs.json' in result['corrupt_products']


# --- phase 9 products: final_with_bgm.mp4 + qa/qa-report.json ------------------


def test_missing_qa_report_falls_back_to_phase_9(tmp_path: Path):
    complete_through_composition(tmp_path)
    write_blob(tmp_path / 'composition' / 'renders' / 'final_with_bgm.mp4')
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '9-check-mix'
    assert 'qa/qa-report.json' in result['missing_products']


def test_fail_verdict_qa_report_falls_back_to_phase_9(tmp_path: Path):
    complete_through_composition(tmp_path)
    write_blob(tmp_path / 'composition' / 'renders' / 'final_with_bgm.mp4')
    write_json(
        tmp_path / 'qa' / 'qa-report.json',
        {
            'findings': [{'scene_id': 's1', 'check': 'black_screen', 'issue': 'black', 'frame': None}],
            'verdict': 'fail',
        },
    )
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '9-check-mix'
    assert 'qa/qa-report.json' in result['corrupt_products']


def test_handed_off_qa_report_completes_phase_9(tmp_path: Path):
    complete_through_composition(tmp_path)
    write_blob(tmp_path / 'composition' / 'renders' / 'final_with_bgm.mp4')
    write_json(
        tmp_path / 'qa' / 'qa-report.json',
        {
            'findings': [{'scene_id': 's1', 'check': 'freeze', 'issue': 'frozen', 'frame': 'sheet_001'}],
            'verdict': 'handed_off',
        },
    )
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert '9-check-mix' in result['completed_phases']
    assert result['next_phase'] is None


def test_qa_report_with_extra_keys_is_corrupt(tmp_path: Path):
    complete_through_composition(tmp_path)
    write_blob(tmp_path / 'composition' / 'renders' / 'final_with_bgm.mp4')
    write_json(
        tmp_path / 'qa' / 'qa-report.json',
        {'findings': [], 'verdict': 'pass', 'qa_level': 'standard'},
    )
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '9-check-mix'
    assert 'qa/qa-report.json' in result['corrupt_products']


def test_qa_report_finding_missing_frame_is_corrupt(tmp_path: Path):
    complete_through_composition(tmp_path)
    write_blob(tmp_path / 'composition' / 'renders' / 'final_with_bgm.mp4')
    write_json(
        tmp_path / 'qa' / 'qa-report.json',
        {'findings': [{'scene_id': 's1', 'check': 'freeze', 'issue': 'frozen'}], 'verdict': 'pass'},
    )
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '9-check-mix'
    assert 'qa/qa-report.json' in result['corrupt_products']


def test_corrupt_inputs_json_falls_back_to_phase_1(tmp_path: Path):
    write_text(tmp_path / 'inputs.json', 'not json {')
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '1-gather-inputs'
    assert 'inputs.json' in result['corrupt_products']


def test_unreadable_file_is_corrupt_not_missing(tmp_path: Path):
    # research-brief.md 存在但是只有空白 → corrupt（存在但不合格）
    complete_through_inputs(tmp_path)
    write_text(tmp_path / 'research-brief.md', '   \n')
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '3-research'
    assert 'research-brief.md' in result['corrupt_products']
