"""Integration tests for scripts/pipeline-status.py.

The test seam is the script's command line (repo convention: stdout = one
JSON, exit codes 0 / 1 / 2). Fixture workspaces are built in tmp dirs.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from composition_hash import composition_sources_fingerprint

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

# What parse-pdf.py writes for the main paper: a manifest entry (slug
# main-paper, source_type paper_pdf) plus the synced metadata file. Paper-mode
# fixtures use this shape instead of the web-harvest one.
PAPER_ENTRY = {
    'slug': 'main-paper',
    'success': True,
    'source_type': 'paper_pdf',
    'title': 'Demo Paper',
    'text_excerpt': 'abstract ...',
    'paper_metadata': {
        'full_markdown_path': 'main-paper/mineru/full.md',
        'abstract': 'abstract ...',
        'figure_captions': {'img_001': '图 1：总体架构'},
        'table_captions': {},
    },
    'images': [{'id': 'img_001', 'local_path': 'main-paper/images/img_001.png', 'caption': '图 1：总体架构'}],
    'videos': [],
}

PAPER_METADATA = {key: value for key, value in PAPER_ENTRY.items() if key != 'images'}

PAPER_CATALOG_ENTRY = {
    'slug': 'main-paper',
    'images': [{'id': 'img_001', 'semantic_description': '图 1：总体架构'}],
    'videos': [],
}


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

# Without a catalog phase (no fetch_materials, not a paper) there is nothing to refer to.
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


def write_narration(ws: Path, script: str) -> None:
    """What make-narration produces for `script` with nothing to replace: narration.txt
    equal to the script, and an offset table of one whole-text segment, including
    the content hashes make-narration records."""
    length = len(script)
    write_text(ws / 'narration.txt', script)
    write_json(
        ws / 'narration-offsets.json',
        {
            'version': 1,
            'script_length': length,
            'narration_length': length,
            'script_sha256': hashlib.sha256(script.encode('utf-8')).hexdigest(),
            'narration_sha256': hashlib.sha256(script.encode('utf-8')).hexdigest(),
            'segments': [{'narration_start': 0, 'narration_end': length, 'script_start': 0, 'script_end': length}],
        },
    )


def write_script(ws: Path, script: str) -> None:
    """script.txt plus the narration.txt / narration-offsets.json derived from it."""
    write_text(ws / 'script.txt', script)
    write_narration(ws, script)


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


def write_paper_metadata(ws: Path) -> None:
    """Phase 2's product: the parsed main paper."""
    write_json(
        ws / 'harvest_page' / 'main-paper' / 'metadata.json',
        {
            'slug': 'main-paper',
            'success': True,
            'source_type': 'paper_pdf',
            'paper_metadata': {'full_markdown_path': 'main-paper/mineru/full.md'},
        },
    )


def complete_through_research(ws: Path, **inputs_overrides) -> None:
    complete_through_inputs(ws, **inputs_overrides)
    if inputs_overrides.get('input_mode') == 'paper':
        write_paper_metadata(ws)
    write_text(ws / 'research-brief.md', RESEARCH_BRIEF)


def complete_through_harvest(ws: Path, **inputs_overrides) -> None:
    complete_through_research(ws, **inputs_overrides)
    inputs = {**INPUTS, **inputs_overrides}
    # The real manifest shape: paper entries (Phase 2/3) plus web page entries
    # (Phase 4); harvest_batches only exist when fetching actually ran.
    entries = []
    if inputs['input_mode'] == 'paper':
        # Phase 2 products: the synced metadata file and the manifest entry.
        write_json(ws / 'harvest_page' / 'main-paper' / 'metadata.json', PAPER_METADATA)
        entries.append(PAPER_ENTRY)
    if inputs['fetch_materials']:
        entries.append({'slug': 'example', 'images': [], 'videos': []})
    manifest: dict = {'entries': entries}
    if inputs['fetch_materials']:
        manifest['harvest_batches'] = [{'at': '2026-01-01T00:00:00Z', 'urls': ['https://example.com'], 'succeeded': 1, 'failed': 0, 'rejected': []}]
    write_json(ws / 'harvest_page' / 'manifest.json', manifest)


def complete_through_catalog(ws: Path, **inputs_overrides) -> None:
    complete_through_harvest(ws, **inputs_overrides)
    inputs = {**INPUTS, **inputs_overrides}
    entries = []
    if inputs['input_mode'] == 'paper':
        entries.append(PAPER_CATALOG_ENTRY)
    if inputs['fetch_materials']:
        entries.extend(CATALOG['entries'])
    write_json(ws / 'material-catalog.json', {'topic_name': 'demo', 'entries': entries})


def complete_through_script(ws: Path, **inputs_overrides) -> None:
    complete_through_catalog(ws, **inputs_overrides)
    write_script(ws, SCRIPT_TXT)
    write_json(ws / 'tts-lexicon.json', {'OpenHuman': 'Open Human'})
    inputs = {**INPUTS, **inputs_overrides}
    has_catalog = inputs['fetch_materials'] or inputs['input_mode'] == 'paper'
    write_json(ws / 'scene-plan.json', SCENE_PLAN if has_catalog else SCENE_PLAN_NO_MATERIALS)


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
    write_script(tmp_path, script_of(chars))
    result = parse_result(run_cli(str(tmp_path)))
    assert '6-script-scene-plan' in result['completed_phases']


def test_script_length_ignores_whitespace(tmp_path: Path):
    complete_through_script(tmp_path)
    # 2250 characters, padded with spaces, full-width spaces and extra blank lines.
    padded = '甲 ' * 1125 + '\n\n\n　　' + '乙\t' * 1125 + '\n\n'
    write_script(tmp_path, padded)
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
    write_script(tmp_path, script)
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
    os.utime(tmp_path / 'composition' / 'check-composition.json')  # check-composition ran after the edit
    # And the render ran after the check.
    mtime = (tmp_path / 'composition' / 'check-composition.json').stat().st_mtime_ns + 10**9
    os.utime(tmp_path / 'composition' / 'renders' / 'final.mp4', ns=(mtime, mtime))
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
    write_json(tmp_path / 'harvest_page' / 'main-paper' / 'metadata.json', PAPER_METADATA)
    write_json(tmp_path / 'harvest_page' / 'manifest.json', {'version': 2, 'entries': [PAPER_ENTRY]})
    write_text(tmp_path / 'harvest_page' / 'main-paper' / 'full.md', '# paper\n')
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert '2-paper-parse' in result['completed_phases']
    assert result['next_phase']['id'] == '3-research'


def test_paper_parse_requires_the_main_paper_manifest_entry(tmp_path: Path):
    # Workspaces parsed before parse-pdf upserted into the manifest have a
    # metadata file but no manifest entry; Phase 5 would find nothing to
    # catalog, so Phase 2 stays open until parse-pdf re-runs.
    complete_through_inputs(tmp_path, input_mode='paper')
    write_json(tmp_path / 'harvest_page' / 'main-paper' / 'metadata.json', PAPER_METADATA)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '2-paper-parse'
    assert 'harvest_page/manifest.json' in result['missing_products']


def test_paper_parse_manifest_without_the_main_paper_entry_is_corrupt(tmp_path: Path):
    complete_through_inputs(tmp_path, input_mode='paper')
    write_json(tmp_path / 'harvest_page' / 'main-paper' / 'metadata.json', PAPER_METADATA)
    write_json(
        tmp_path / 'harvest_page' / 'manifest.json',
        {'version': 2, 'entries': [{'slug': 'unrelated', 'images': [], 'videos': []}]},
    )

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '2-paper-parse'
    assert 'harvest_page/manifest.json' in result['corrupt_products']
    detail = result['next_phase']['problems']['harvest_page/manifest.json']
    assert 'main-paper' in detail


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


def test_paper_mode_without_fetch_skips_harvest_but_builds_the_catalog(tmp_path: Path):
    complete_through_harvest(tmp_path, input_mode='paper', fetch_materials=False)
    result = parse_result(run_cli(str(tmp_path)))
    assert '4-material-harvest' in result['skipped_phases']
    assert '5-material-catalog' not in result['skipped_phases']
    assert result['next_phase']['id'] == '5-material-catalog'
    assert result['next_phase']['doc'] == 'references/phases/05-material-catalog.md'


def test_standard_mode_without_fetch_skips_harvest_and_catalog(tmp_path: Path):
    complete_through_research(tmp_path, input_mode='standard', fetch_materials=False)
    result = parse_result(run_cli(str(tmp_path)))
    assert {'4-material-harvest', '5-material-catalog'} <= set(result['skipped_phases'])
    assert result['next_phase']['id'] == '6-script-scene-plan'


def test_paper_mode_without_fetch_full_run(tmp_path: Path):
    complete_all(tmp_path, input_mode='paper', fetch_materials=False)
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase'] is None
    assert result['skipped_phases'] == ['4-material-harvest']
    assert '5-material-catalog' in result['completed_phases']


def test_paper_mode_without_fetch_scene_plan_refs_resolve_against_the_catalog(tmp_path: Path):
    result, detail = scene_plan_problem(
        tmp_path, [scene('s1', [1, 2], candidates('img_001'))], input_mode='paper', fetch_materials=False
    )
    assert detail is None
    assert '6-script-scene-plan' in result['completed_phases']


def test_paper_mode_without_fetch_scene_plan_ref_missing_from_catalog_is_corrupt(tmp_path: Path):
    result, detail = scene_plan_problem(
        tmp_path, [scene('s1', [1, 2], candidates('nope_1'))], input_mode='paper', fetch_materials=False
    )
    assert 'scene-plan.json' in result['corrupt_products']
    assert "'nope_1'" in detail, detail


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


def test_unreadable_inputs_still_list_fetch_and_catalog_as_applicable(tmp_path: Path):
    # inputs.json cannot say whether the workspace fetches or parses a paper:
    # the default sequence (standard, with fetching) applies, so Phases 4 and 5
    # are reported as upcoming, never silently skipped.
    write_text(tmp_path / 'inputs.json', 'not json {')
    result = parse_result(run_cli(str(tmp_path)))
    assert '4-material-harvest' not in result['skipped_phases']
    assert '5-material-catalog' not in result['skipped_phases']


def test_unreadable_file_is_corrupt_not_missing(tmp_path: Path):
    # research-brief.md 存在但是只有空白 → corrupt（存在但不合格）
    complete_through_inputs(tmp_path)
    write_text(tmp_path / 'research-brief.md', '   \n')
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '3-research'
    assert 'research-brief.md' in result['corrupt_products']


# --- phase statuses: everything after the first unfinished phase is pending -------

PHASE_IDS = [
    '1-gather-inputs',
    '2-paper-parse',
    '3-research',
    '4-material-harvest',
    '5-material-catalog',
    '6-script-scene-plan',
    '7-voice-subtitles',
    '8-composition',
    '9-check-mix',
]


def statuses(result: dict) -> dict[str, str]:
    return {phase['id']: phase['status'] for phase in result['phases']}


def test_phases_after_a_missing_product_are_pending_not_completed(tmp_path: Path):
    complete_all(tmp_path)
    (tmp_path / 'research-brief.md').unlink()
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '3-research'
    assert result['next_phase']['reason'] == 'missing'
    assert 'changed_upstream' not in result['next_phase']  # only a stale phase has one
    assert result['completed_phases'] == ['1-gather-inputs']
    assert result['pending_phases'] == PHASE_IDS[3:]
    assert result['stale_phases'] == []
    assert [phase['id'] for phase in result['phases']] == PHASE_IDS
    assert statuses(result) == {
        '1-gather-inputs': 'completed',
        '2-paper-parse': 'skipped',
        '3-research': 'missing',
        **{phase_id: 'pending' for phase_id in PHASE_IDS[3:]},
    }


def test_pending_phases_are_not_checked(tmp_path: Path):
    # Phase 7's transcript is broken too, but Phase 3 comes first: it is not even looked at.
    complete_all(tmp_path)
    (tmp_path / 'research-brief.md').unlink()
    write_text(tmp_path / 'transcribe' / 'transcript.json', 'not json')
    result = parse_result(run_cli(str(tmp_path)))
    assert result['missing_products'] == ['research-brief.md']
    assert result['corrupt_products'] == []


def test_a_corrupt_product_makes_the_phase_corrupt_and_the_rest_pending(tmp_path: Path):
    complete_all(tmp_path)
    write_text(tmp_path / 'research-brief.md', '   \n')
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['reason'] == 'corrupt'
    assert statuses(result)['3-research'] == 'corrupt'
    assert result['completed_phases'] == ['1-gather-inputs']


def test_a_phase_with_both_missing_and_corrupt_products_is_corrupt(tmp_path: Path):
    complete_through_script(tmp_path)
    (tmp_path / 'script.txt').unlink()
    write_text(tmp_path / 'narration.txt', '')
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert result['next_phase']['reason'] == 'corrupt'
    assert statuses(result)['6-script-scene-plan'] == 'corrupt'


def test_complete_workspace_has_no_pending_or_stale_phases(tmp_path: Path):
    complete_all(tmp_path)
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase'] is None
    assert result['pending_phases'] == [] and result['stale_phases'] == []
    assert statuses(result) == {**{phase_id: 'completed' for phase_id in PHASE_IDS}, '2-paper-parse': 'skipped'}


# --- stamps: .pipeline/stamps.json records which upstream each phase was built from ---


def sha256_of(data: str | bytes) -> str:
    return hashlib.sha256(data.encode('utf-8') if isinstance(data, str) else data).hexdigest()


def field_sha256(value) -> str:
    """The fingerprint of one inputs.json field, as the issue defines it."""
    return sha256_of(json.dumps(value, sort_keys=True, ensure_ascii=False))


def read_stamps(ws: Path) -> dict:
    return json.loads((ws / '.pipeline' / 'stamps.json').read_text(encoding='utf-8'))


def test_first_run_writes_a_stamp_for_every_completed_phase(tmp_path: Path):
    complete_all(tmp_path)
    parse_result(run_cli(str(tmp_path)))
    stamps = read_stamps(tmp_path)
    assert stamps['version'] == 1
    assert set(stamps['phases']) == set(PHASE_IDS) - {'2-paper-parse'}  # a skipped phase has no stamp
    for stamp in stamps['phases'].values():
        assert set(stamp) == {'upstream', 'products', 'stamped_at'}
        datetime.fromisoformat(stamp['stamped_at'])


def test_stamp_records_upstream_and_product_fingerprints(tmp_path: Path):
    complete_all(tmp_path)
    parse_result(run_cli(str(tmp_path)))
    phases = read_stamps(tmp_path)['phases']

    assert phases['1-gather-inputs']['upstream'] == {}
    assert phases['1-gather-inputs']['products'] == {'inputs.json': sha256_of((tmp_path / 'inputs.json').read_bytes())}

    script = phases['6-script-scene-plan']
    assert script['products']['script.txt'] == sha256_of(SCRIPT_TXT)
    assert script['upstream']['research-brief.md'] == sha256_of(RESEARCH_BRIEF)
    assert script['upstream']['inputs.json#duration'] == field_sha256(5.0)  # "5min" normalizes to 5
    assert script['upstream']['inputs.json#template'] == field_sha256(None)
    assert script['upstream']['material-catalog.json'] == sha256_of((tmp_path / 'material-catalog.json').read_bytes())
    assert script['upstream']['narration-instructions.md'] == 'absent'  # optional upstream that does not exist


def test_absent_qa_level_fingerprints_like_the_default(tmp_path: Path):
    complete_through_research(tmp_path)
    parse_result(run_cli(str(tmp_path)))
    upstream = read_stamps(tmp_path)['phases']['3-research']['upstream']
    assert 'inputs.json#qa_level' not in upstream  # qa_level is not an upstream of Phase 3
    complete_all(tmp_path)
    without_default = {key: value for key, value in INPUTS.items() if key != 'qa_level'}
    write_json(tmp_path / 'inputs.json', without_default)
    result = parse_result(run_cli(str(tmp_path)))
    assert result['stale_phases'] == []  # absent means the standard tier, spelled out or not
    assert result['next_phase'] is None


def test_duration_spelling_variants_fingerprint_alike(tmp_path: Path):
    settle(tmp_path)  # duration "5min"
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'duration': 5})
    result = parse_result(run_cli(str(tmp_path)))
    assert result['stale_phases'] == []
    assert result['next_phase'] is None


def test_inputs_field_fingerprint_sorts_keys_and_keeps_non_ascii(tmp_path: Path):
    complete_through_research(tmp_path, language='中文', source={'url': 'https://e.com', 'a': 1})
    parse_result(run_cli(str(tmp_path)))
    upstream = read_stamps(tmp_path)['phases']['3-research']['upstream']
    assert upstream['inputs.json#language'] == sha256_of('"中文"')
    assert upstream['inputs.json#source'] == sha256_of('{"a": 1, "url": "https://e.com"}')


# What each phase is built from, as the issue lists it; "inputs.json#x" is the field x of inputs.json.
UPSTREAM_KEYS = {
    '1-gather-inputs': [],
    '3-research': [
        'inputs.json#source', 'inputs.json#input_mode', 'inputs.json#language',
        'harvest_page/main-paper/metadata.json',
    ],
    '4-material-harvest': ['research-brief.md'],
    '5-material-catalog': ['harvest_page/manifest.json', 'research-brief.md'],
    '6-script-scene-plan': [
        'research-brief.md', 'material-catalog.json', 'inputs.json#duration', 'inputs.json#language',
        'inputs.json#input_mode', 'inputs.json#template', 'narration-instructions.md',
    ],
    '7-voice-subtitles': [
        'narration.txt', 'narration-offsets.json', 'script.txt', 'scene-plan.json', 'inputs.json#layout',
    ],
    '8-composition': [
        'voice_clone/narration.mp3', 'transcribe/subtitle-units.json', 'transcribe/timeline.json',
        'material-catalog.json', 'scene-plan.json', 'script.txt', 'inputs.json#design', 'inputs.json#layout',
        'inputs.json#template', 'inputs.json#orientation', 'composition-instructions.md', 'style-prompt.md',
    ],
    '9-check-mix': ['composition/renders/final.mp4', 'inputs.json#qa_level'],
}


@pytest.mark.parametrize('phase_id', list(UPSTREAM_KEYS))
def test_stamp_upstream_keys_of_each_phase(tmp_path: Path, phase_id: str):
    complete_all(tmp_path)
    parse_result(run_cli(str(tmp_path)))
    assert list(read_stamps(tmp_path)['phases'][phase_id]['upstream']) == UPSTREAM_KEYS[phase_id]


def test_paper_parse_stamp_upstream_and_its_metadata_as_upstream_of_research(tmp_path: Path):
    complete_through_inputs(tmp_path, input_mode='paper')
    metadata = {
        'slug': 'main-paper', 'success': True, 'source_type': 'paper_pdf',
        'paper_metadata': {'full_markdown_path': 'main-paper/full.md'},
    }
    write_json(tmp_path / 'harvest_page' / 'main-paper' / 'metadata.json', metadata)
    write_json(tmp_path / 'harvest_page' / 'manifest.json', {'version': 2, 'entries': [PAPER_ENTRY]})
    write_text(tmp_path / 'research-brief.md', RESEARCH_BRIEF)
    result = parse_result(run_cli(str(tmp_path)))
    assert result['completed_phases'] == ['1-gather-inputs', '2-paper-parse', '3-research']
    phases = read_stamps(tmp_path)['phases']
    assert list(phases['2-paper-parse']['upstream']) == ['inputs.json#source', 'inputs.json#input_mode']
    assert phases['3-research']['upstream']['harvest_page/main-paper/metadata.json'] == sha256_of(
        (tmp_path / 'harvest_page' / 'main-paper' / 'metadata.json').read_bytes()
    )

    # Re-parsing the paper changes Phase 2's product, which makes the research stale.
    write_json(
        tmp_path / 'harvest_page' / 'main-paper' / 'metadata.json',
        {**metadata, 'paper_metadata': {'full_markdown_path': 'main-paper/mineru/full.md'}},
    )
    result = parse_result(run_cli(str(tmp_path)))
    assert statuses(result)['2-paper-parse'] == 'completed'
    assert result['next_phase']['id'] == '3-research'
    assert result['next_phase']['changed_upstream'] == ['harvest_page/main-paper/metadata.json']


def test_directory_products_are_not_fingerprinted(tmp_path: Path):
    complete_all(tmp_path)
    parse_result(run_cli(str(tmp_path)))
    products = read_stamps(tmp_path)['phases']['8-composition']['products']
    assert 'composition/compositions' not in products
    assert set(products) == {
        'composition/storyboard.md',
        'composition/index.html',
        'composition/check-composition.json',
        'composition/renders/final.mp4',
    }


def test_phases_that_are_not_completed_get_no_stamp(tmp_path: Path):
    complete_all(tmp_path)
    (tmp_path / 'research-brief.md').unlink()
    parse_result(run_cli(str(tmp_path)))
    assert list(read_stamps(tmp_path)['phases']) == ['1-gather-inputs']


def test_a_workspace_without_inputs_gets_no_pipeline_dir(tmp_path: Path):
    parse_result(run_cli(str(tmp_path)))
    assert not (tmp_path / '.pipeline').exists()


def test_second_run_leaves_the_stamp_file_untouched(tmp_path: Path):
    complete_all(tmp_path)
    parse_result(run_cli(str(tmp_path)))
    stamps_file = tmp_path / '.pipeline' / 'stamps.json'
    before = (stamps_file.read_bytes(), stamps_file.stat().st_mtime_ns)
    result = parse_result(run_cli(str(tmp_path)))
    assert (stamps_file.read_bytes(), stamps_file.stat().st_mtime_ns) == before
    assert result['next_phase'] is None


# --- stale: a phase whose upstream changed after it was built ---------------------

EDITED_SCRIPT_TXT = '甲' * 1125 + '\n\n' + '丙' * 1125 + '\n'  # same length as SCRIPT_TXT, other content


def settle(ws: Path, **inputs_overrides) -> dict:
    """A complete workspace whose stamps have been written by a first run."""
    complete_all(ws, **inputs_overrides)
    result = parse_result(run_cli(str(ws)))
    assert result['next_phase'] is None
    return result


def rewrite_voice_subtitles(ws: Path) -> None:
    """Phase 7 regenerated: same shape, other bytes."""
    write_blob(ws / 'voice_clone' / 'narration.mp3', size=256)
    write_json(ws / 'transcribe' / 'transcript.json', [{**TRANSCRIPT[0], 'text': '大家好呀。'}])
    write_json(ws / 'transcribe' / 'subtitle-units.json', {'units': [{'text': '大家好呀', 'begin_s': 0.0, 'end_s': 2.6}]})
    write_json(ws / 'transcribe' / 'timeline.json', {**TIMELINE, 'total_s': 2.6})


def test_a_partial_redo_keeps_the_phase_stale(tmp_path: Path):
    # Only re-running align-narration after a script edit must not clear Phase 7's
    # stale mark: narration.mp3 and transcript.json are still the old build.
    settle(tmp_path)
    write_script(tmp_path, EDITED_SCRIPT_TXT)
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['id'] == '7-voice-subtitles'

    write_json(tmp_path / 'transcribe' / 'subtitle-units.json', {'units': [{'text': '大家好呀', 'begin_s': 0.0, 'end_s': 2.6}]})
    write_json(tmp_path / 'transcribe' / 'timeline.json', {**TIMELINE, 'total_s': 2.6})
    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '7-voice-subtitles'
    assert result['next_phase']['reason'] == 'stale'
    assert result['next_phase']['changed_upstream'] == ['narration.txt', 'narration-offsets.json', 'script.txt']
    # While the phase is stale the stamp keeps the pre-change fingerprints: the
    # two rebuilt products are NOT recorded until the redo is complete.
    stamp = read_stamps(tmp_path)['phases']['7-voice-subtitles']
    assert stamp['upstream']['script.txt'] == sha256_of(SCRIPT_TXT)
    assert stamp['products']['transcribe/subtitle-units.json'] == sha256_of(
        json.dumps(SUBTITLE_UNITS, ensure_ascii=False)
    )

    rewrite_voice_subtitles(tmp_path)
    result = parse_result(run_cli(str(tmp_path)))
    assert statuses(result)['7-voice-subtitles'] == 'completed'


def test_an_unreadable_optional_upstream_does_not_abort_the_scan(tmp_path: Path):
    complete_all(tmp_path)
    style_prompt = tmp_path / 'style-prompt.md'
    write_text(style_prompt, '## style\n冷色调\n')
    # First scan stamps Phase 8 with the file's hash.
    assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None

    style_prompt.chmod(0)
    # Drop the fingerprint memo so this run must open the file and hit the
    # permission error (with a warm cache the size + mtime check answers first).
    (tmp_path / '.pipeline' / 'fpcache.json').unlink()
    try:
        proc = run_cli(str(tmp_path))
    finally:
        style_prompt.chmod(0o644)

    assert proc.returncode == 0
    result = parse_result(proc)
    assert result['next_phase']['id'] == '8-composition'
    assert result['next_phase']['reason'] == 'stale'
    assert result['next_phase']['changed_upstream'] == ['style-prompt.md']


def test_an_upstream_key_missing_from_an_old_stamp_is_not_a_change(tmp_path: Path):
    # PHASES learned a new upstream key: existing workspaces must not go stale for it.
    settle(tmp_path)
    stamps = read_stamps(tmp_path)
    stamp = stamps['phases']['9-check-mix']
    del stamp['upstream']['inputs.json#qa_level']
    write_json(tmp_path / '.pipeline' / 'stamps.json', stamps)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase'] is None
    assert result['stale_phases'] == []


def test_fingerprint_cache_is_written_and_trusted(tmp_path: Path):
    settle(tmp_path)
    cache = json.loads((tmp_path / '.pipeline' / 'fpcache.json').read_text(encoding='utf-8'))
    assert cache['version'] == 1
    entry = cache['files']['composition/renders/final.mp4']
    assert set(entry) == {'size', 'mtime_ns', 'sha256'}
    # A same-size, same-mtime rewrite is trusted without re-hashing (the accepted
    # trade-off that avoids re-reading every media file on each scan).
    target = tmp_path / 'composition' / 'renders' / 'final.mp4'
    target.write_bytes(b'\1' * entry['size'])
    os.utime(target, ns=(entry['mtime_ns'], entry['mtime_ns']))
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase'] is None


def test_editing_the_script_makes_phase_7_stale_and_later_phases_pending(tmp_path: Path):
    settle(tmp_path)
    write_script(tmp_path, EDITED_SCRIPT_TXT)  # the script agent re-ran make-narration

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '7-voice-subtitles'
    assert result['next_phase']['reason'] == 'stale'
    assert result['next_phase']['changed_upstream'] == ['narration.txt', 'narration-offsets.json', 'script.txt']
    assert result['next_phase']['problems'] == {}
    assert result['stale_phases'] == ['7-voice-subtitles']
    assert result['pending_phases'] == ['8-composition', '9-check-mix']
    assert result['completed_phases'] == [
        '1-gather-inputs', '3-research', '4-material-harvest', '5-material-catalog', '6-script-scene-plan',
    ]
    assert statuses(result)['7-voice-subtitles'] == 'stale'
    assert result['missing_products'] == [] and result['corrupt_products'] == []


def test_changing_only_qa_level_makes_only_phase_9_stale(tmp_path: Path):
    settle(tmp_path)
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'qa_level': 'strict'})

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '9-check-mix'
    assert result['next_phase']['reason'] == 'stale'
    assert result['next_phase']['changed_upstream'] == ['inputs.json#qa_level']
    assert result['stale_phases'] == ['9-check-mix']
    assert result['pending_phases'] == []
    assert result['completed_phases'] == [phase_id for phase_id in PHASE_IDS[:-1] if phase_id != '2-paper-parse']


def test_changing_the_layout_makes_phase_7_stale(tmp_path: Path):
    settle(tmp_path)
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'layout': 'portrait'})
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '7-voice-subtitles'
    assert result['next_phase']['changed_upstream'] == ['inputs.json#layout']
    assert result['pending_phases'] == ['8-composition', '9-check-mix']


def test_a_newly_created_optional_upstream_file_makes_its_phase_stale(tmp_path: Path):
    settle(tmp_path)
    write_text(tmp_path / 'composition-instructions.md', '结尾不要 CTA\n')
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '8-composition'
    assert result['next_phase']['changed_upstream'] == ['composition-instructions.md']


def test_editing_a_product_by_hand_keeps_the_phase_completed_and_stales_the_next(tmp_path: Path):
    settle(tmp_path)
    edited = RESEARCH_BRIEF + '- one more fact [source]\n'
    write_text(tmp_path / 'research-brief.md', edited)

    result = parse_result(run_cli(str(tmp_path)))

    assert statuses(result)['3-research'] == 'completed'
    assert result['next_phase']['id'] == '4-material-harvest'
    assert result['next_phase']['reason'] == 'stale'
    assert result['next_phase']['changed_upstream'] == ['research-brief.md']
    # The stamp now describes the edited file, so the edit is not reported again as a product change.
    phases = read_stamps(tmp_path)['phases']
    assert phases['3-research']['products']['research-brief.md'] == sha256_of(edited)
    assert phases['4-material-harvest']['upstream']['research-brief.md'] == sha256_of(RESEARCH_BRIEF)


def test_regenerating_a_phase_after_its_upstream_changed_makes_it_completed_again(tmp_path: Path):
    settle(tmp_path)
    write_script(tmp_path, EDITED_SCRIPT_TXT)
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['id'] == '7-voice-subtitles'

    rewrite_voice_subtitles(tmp_path)
    result = parse_result(run_cli(str(tmp_path)))

    assert statuses(result)['7-voice-subtitles'] == 'completed'
    assert result['next_phase']['id'] == '8-composition'
    assert result['next_phase']['reason'] == 'stale'
    assert result['next_phase']['changed_upstream'] == [
        'voice_clone/narration.mp3',
        'transcribe/subtitle-units.json',
        'transcribe/timeline.json',
        'script.txt',
    ]
    assert result['pending_phases'] == ['9-check-mix']
    # Phase 7's stamp was rewritten against the new upstream.
    stamp = read_stamps(tmp_path)['phases']['7-voice-subtitles']
    assert stamp['upstream']['script.txt'] == sha256_of(EDITED_SCRIPT_TXT)
    assert stamp['products']['voice_clone/narration.mp3'] == sha256_of(b'\0' * 256)


def test_a_stale_phase_stays_stale_until_it_is_regenerated_or_restamped(tmp_path: Path):
    settle(tmp_path)
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'qa_level': 'strict'})
    first = parse_result(run_cli(str(tmp_path)))
    second = parse_result(run_cli(str(tmp_path)))
    assert first['next_phase'] == second['next_phase']
    assert second['stale_phases'] == ['9-check-mix']


def test_deleting_phase_6_products_makes_6_next_and_the_rest_pending_until_restored(tmp_path: Path):
    settle(tmp_path)
    phase_6 = ['script.txt', 'tts-lexicon.json', 'narration.txt', 'narration-offsets.json', 'scene-plan.json']
    saved = {name: (tmp_path / name).read_bytes() for name in phase_6}
    for name in phase_6:
        (tmp_path / name).unlink()

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert result['next_phase']['reason'] == 'missing'
    assert result['pending_phases'] == ['7-voice-subtitles', '8-composition', '9-check-mix']
    assert result['completed_phases'] == ['1-gather-inputs', '3-research', '4-material-harvest', '5-material-catalog']

    # The same bytes are written back: nothing downstream is stale.
    for name, data in saved.items():
        (tmp_path / name).write_bytes(data)
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase'] is None
    assert result['stale_phases'] == [] and result['pending_phases'] == []


def test_redoing_phase_6_with_new_content_makes_phase_7_stale(tmp_path: Path):
    settle(tmp_path)
    for name in ('script.txt', 'narration.txt', 'narration-offsets.json', 'scene-plan.json', 'tts-lexicon.json'):
        (tmp_path / name).unlink()
    write_script(tmp_path, EDITED_SCRIPT_TXT)
    write_json(tmp_path / 'tts-lexicon.json', {'OpenHuman': 'Open Human'})
    write_json(tmp_path / 'scene-plan.json', SCENE_PLAN)

    result = parse_result(run_cli(str(tmp_path)))

    assert statuses(result)['6-script-scene-plan'] == 'completed'
    assert result['next_phase']['id'] == '7-voice-subtitles'
    assert result['next_phase']['reason'] == 'stale'
    assert result['pending_phases'] == ['8-composition', '9-check-mix']


def test_changed_upstream_of_a_pending_phase_is_not_looked_at(tmp_path: Path):
    settle(tmp_path)
    (tmp_path / 'research-brief.md').unlink()
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'qa_level': 'strict'})
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '3-research'
    assert result['stale_phases'] == []
    assert statuses(result)['9-check-mix'] == 'pending'


# --- --restamp: accept the current files of a phase as built from the current upstream ---


def test_restamp_clears_a_stale_phase(tmp_path: Path):
    settle(tmp_path)
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'qa_level': 'strict'})
    assert parse_result(run_cli(str(tmp_path)))['stale_phases'] == ['9-check-mix']

    proc = run_cli(str(tmp_path), '--restamp', '9-check-mix')

    assert proc.returncode == 0
    result = parse_result(proc)
    assert result['success'] is True
    assert result['next_phase'] is None
    assert result['stale_phases'] == []
    assert statuses(result)['9-check-mix'] == 'completed'
    assert read_stamps(tmp_path)['phases']['9-check-mix']['upstream']['inputs.json#qa_level'] == field_sha256('strict')
    # And it sticks on the next plain run.
    assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None


def test_restamp_only_touches_the_named_phase(tmp_path: Path):
    settle(tmp_path)
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'language': 'en'})  # upstream of Phases 3 and 6

    result = parse_result(run_cli(str(tmp_path), '--restamp', '3-research'))

    assert statuses(result)['3-research'] == 'completed'
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert result['next_phase']['reason'] == 'stale'
    assert result['next_phase']['changed_upstream'] == ['inputs.json#language']


def test_restamp_reads_the_current_files_not_the_old_ones(tmp_path: Path):
    settle(tmp_path)
    write_script(tmp_path, EDITED_SCRIPT_TXT)
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['id'] == '7-voice-subtitles'

    result = parse_result(run_cli(str(tmp_path), '--restamp', '7-voice-subtitles'))

    assert statuses(result)['7-voice-subtitles'] == 'completed'
    assert result['next_phase']['id'] == '8-composition'  # its upstream moved too
    assert read_stamps(tmp_path)['phases']['7-voice-subtitles']['upstream']['script.txt'] == sha256_of(EDITED_SCRIPT_TXT)


def test_restamp_fails_with_exit_1_when_the_products_do_not_pass(tmp_path: Path):
    settle(tmp_path)
    stamps_before = (tmp_path / '.pipeline' / 'stamps.json').read_bytes()
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'qa_level': 'strict'})
    (tmp_path / 'qa' / 'qa-report.json').unlink()

    proc = run_cli(str(tmp_path), '--restamp', '9-check-mix')

    assert proc.returncode == 1
    result = parse_result(proc)
    assert result['success'] is False
    assert '9-check-mix' in result['error']
    assert 'qa/qa-report.json' in result['problems']
    assert (tmp_path / '.pipeline' / 'stamps.json').read_bytes() == stamps_before


def test_restamp_fails_with_exit_1_for_a_phase_that_is_skipped(tmp_path: Path):
    settle(tmp_path)  # standard mode: Phase 2 does not apply
    proc = run_cli(str(tmp_path), '--restamp', '2-paper-parse')
    assert proc.returncode == 1
    result = parse_result(proc)
    assert result['success'] is False
    assert 'skipped' in result['error']


def test_restamp_with_an_unknown_phase_is_a_usage_error(tmp_path: Path):
    proc = run_cli(str(tmp_path), '--restamp', '10-publish')
    assert proc.returncode == 2
    result = parse_result(proc)
    assert result['success'] is False
    assert '10-publish' in result['error']


def test_restamp_without_a_phase_is_a_usage_error(tmp_path: Path):
    proc = run_cli(str(tmp_path), '--restamp')
    assert proc.returncode == 2
    assert parse_result(proc)['success'] is False


# --- a stamps.json that cannot be trusted stops the run instead of resetting it ---


@pytest.mark.parametrize(
    'content',
    [
        '{"version": 1, "phases": ',  # truncated
        '[]',
        '{"version": 2, "phases": {}}',
        '{"phases": {}}',
        '{"version": 1, "phases": []}',
        '{"version": 1, "phases": {"1-gather-inputs": []}}',
        '{"version": 1, "phases": {"1-gather-inputs": {"upstream": {}, "products": []}}}',
        '{"version": 1, "phases": {"1-gather-inputs": {"upstream": {}}}}',
    ],
)
def test_unusable_stamps_file_is_quarantined_and_reported(tmp_path: Path, content: str):
    complete_all(tmp_path)
    write_text(tmp_path / '.pipeline' / 'stamps.json', content)

    proc = run_cli(str(tmp_path))

    assert proc.returncode == 0
    result = parse_result(proc)
    assert result['stamps_reset'] is True
    assert not (tmp_path / '.pipeline' / 'stamps.json').exists()
    # The evidence is kept for inspection, not deleted.
    assert (tmp_path / '.pipeline' / 'stamps.json.quarantined').read_text(encoding='utf-8') == content


def test_quarantined_stamps_are_not_saved_until_they_are_rebuilt(tmp_path: Path):
    complete_all(tmp_path)
    write_text(tmp_path / '.pipeline' / 'stamps.json', 'garbage')

    first = parse_result(run_cli(str(tmp_path)))
    second = parse_result(run_cli(str(tmp_path)))

    for result in (first, second):
        assert result['stamps_reset'] is True
        assert not (tmp_path / '.pipeline' / 'stamps.json').exists()


def test_restamp_rebuilds_quarantined_stamps(tmp_path: Path):
    settle(tmp_path)
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'qa_level': 'strict'})
    write_text(tmp_path / '.pipeline' / 'stamps.json', 'garbage')

    proc = run_cli(str(tmp_path), '--restamp', '9-check-mix')

    assert proc.returncode == 0
    result = parse_result(proc)
    assert result['stamps_reset'] is False
    assert not (tmp_path / '.pipeline' / 'stamps.json.quarantined').exists()
    assert (tmp_path / '.pipeline' / 'stamps.json').is_file()
    assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None


def test_deleting_the_pipeline_dir_starts_over_from_the_current_files(tmp_path: Path):
    settle(tmp_path)
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'qa_level': 'strict'})
    assert parse_result(run_cli(str(tmp_path)))['stale_phases'] == ['9-check-mix']
    (tmp_path / '.pipeline' / 'stamps.json').unlink()
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase'] is None
    assert (tmp_path / '.pipeline' / 'stamps.json').is_file()


# --- phase 6 check: script.txt / narration.txt still match the offset table ---------
#
# make-narration records the character counts of the script.txt it read and the
# narration.txt it wrote. A script.txt edited afterwards without re-running it
# leaves a stale narration.txt and offset table, which align-narration only
# rejects in Phase 7, after the TTS has already run.

MAKE_NARRATION = REPO_ROOT / 'scripts' / 'make-narration.py'


def offsets_problem(ws: Path) -> str:
    result = parse_result(run_cli(str(ws)))
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert result['next_phase']['reason'] == 'corrupt'
    assert 'narration-offsets.json' in result['corrupt_products']
    return result['next_phase']['problems']['narration-offsets.json']


def test_script_edited_after_make_narration_sends_phase_6_back(tmp_path: Path):
    settle(tmp_path)
    write_text(tmp_path / 'script.txt', '甲' * 1125 + '\n\n' + '乙' * 1130 + '\n')  # 5 characters longer
    detail = offsets_problem(tmp_path)
    assert 'script_length' in detail and 'script.txt' in detail and '2253' in detail and '2258' in detail, detail
    assert 'make-narration' in detail


def test_script_edited_to_the_same_length_is_caught_by_the_hash(tmp_path: Path):
    # The character counts cannot see it, but make-narration records content
    # hashes in the offset table exactly for this case.
    settle(tmp_path)
    write_text(tmp_path / 'script.txt', EDITED_SCRIPT_TXT)
    detail = offsets_problem(tmp_path)
    assert 'script_sha256' in detail and 'script.txt' in detail and 'make-narration' in detail, detail


def test_same_length_edit_of_a_legacy_offsets_table_without_hashes_still_passes(tmp_path: Path):
    # Offsets written before the hashes existed only carry the counts; nothing
    # stronger can be checked for them (Phase 7 stales via the script.txt upstream).
    settle(tmp_path)
    offsets = json.loads((tmp_path / 'narration-offsets.json').read_text(encoding='utf-8'))
    for field in ('script_sha256', 'narration_sha256'):
        offsets.pop(field, None)
    write_json(tmp_path / 'narration-offsets.json', offsets)
    write_text(tmp_path / 'script.txt', EDITED_SCRIPT_TXT)

    result = parse_result(run_cli(str(tmp_path)))

    assert statuses(result)['6-script-scene-plan'] == 'completed'
    assert result['next_phase']['id'] == '7-voice-subtitles'
    assert result['next_phase']['reason'] == 'stale'


def test_narration_edited_after_make_narration_sends_phase_6_back(tmp_path: Path):
    complete_through_script(tmp_path)
    write_text(tmp_path / 'narration.txt', SCRIPT_TXT + '多出来的一句。\n')
    detail = offsets_problem(tmp_path)
    assert 'narration_length' in detail and 'narration.txt' in detail, detail


def test_empty_offset_segments_send_phase_6_back(tmp_path: Path):
    complete_through_script(tmp_path)
    offsets = json.loads((tmp_path / 'narration-offsets.json').read_text(encoding='utf-8'))
    write_json(tmp_path / 'narration-offsets.json', {**offsets, 'segments': []})
    assert 'segments' in offsets_problem(tmp_path)


@pytest.mark.parametrize('field', ['script_length', 'narration_length'])
@pytest.mark.parametrize('value', ['missing', '2252', 2252.0, None, True])
def test_offsets_without_an_integer_length_send_phase_6_back(tmp_path: Path, field: str, value):
    complete_through_script(tmp_path)
    offsets = json.loads((tmp_path / 'narration-offsets.json').read_text(encoding='utf-8'))
    if value == 'missing':
        del offsets[field]
    else:
        offsets[field] = value
    write_json(tmp_path / 'narration-offsets.json', offsets)
    detail = offsets_problem(tmp_path)
    assert field in detail and 'integer' in detail, detail


def test_lengths_are_not_compared_against_a_missing_script(tmp_path: Path):
    complete_through_script(tmp_path)
    (tmp_path / 'script.txt').unlink()
    result = parse_result(run_cli(str(tmp_path)))
    assert set(result['next_phase']['problems']) == {'script.txt'}


def test_lengths_are_not_compared_against_a_missing_narration(tmp_path: Path):
    complete_through_script(tmp_path)
    (tmp_path / 'narration.txt').unlink()
    result = parse_result(run_cli(str(tmp_path)))
    assert set(result['next_phase']['problems']) == {'narration.txt'}


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
def test_what_make_narration_writes_is_accepted(tmp_path: Path, newline: str):
    complete_through_catalog(tmp_path)
    script = (SCRIPT_TXT.replace('甲' * 3, 'OpenHuman甲甲甲', 1)).replace('\n', newline)
    (tmp_path / 'script.txt').write_bytes(script.encode('utf-8'))
    write_json(tmp_path / 'tts-lexicon.json', {'OpenHuman': 'Open Human'})
    write_json(tmp_path / 'scene-plan.json', SCENE_PLAN)
    proc = subprocess.run(
        [
            sys.executable, str(MAKE_NARRATION),
            '--script', str(tmp_path / 'script.txt'),
            '--lexicon', str(tmp_path / 'tts-lexicon.json'),
            '--output-dir', str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '7-voice-subtitles', result['next_phase']
    assert statuses(result)['6-script-scene-plan'] == 'completed'


# --- phase 8 check: the saved check-composition report is not older than the composition ---
#
# The report is saved by the composition agent itself. A pass that predates the
# last edit of index.html or compositions/ says nothing about the current files.

REPORT = 'composition/check-composition.json'


def touch_after_report(ws: Path, relpath: str, seconds: int = 5) -> None:
    """Edit a composition file so that its mtime is `seconds` later than the report's."""
    path = ws / relpath
    path.write_text(path.read_text(encoding='utf-8') + '\n<!-- edited -->', encoding='utf-8')
    mtime = (ws / REPORT).stat().st_mtime_ns + seconds * 10**9
    os.utime(path, ns=(mtime, mtime))


@pytest.mark.parametrize(
    'edited',
    ['composition/compositions/scene_1.html', 'composition/index.html'],
)
def test_composition_edited_after_the_report_sends_phase_8_back(tmp_path: Path, edited: str):
    settle(tmp_path)
    touch_after_report(tmp_path, edited)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '8-composition'
    assert result['next_phase']['reason'] == 'corrupt'
    assert result['corrupt_products'] == [REPORT]
    detail = result['next_phase']['problems'][REPORT]
    assert edited in detail and 'check-composition' in detail, detail
    assert result['pending_phases'] == ['9-check-mix']


def test_nested_composition_file_edited_after_the_report_sends_phase_8_back(tmp_path: Path):
    settle(tmp_path)
    write_text(tmp_path / 'composition' / 'compositions' / 'extra' / 'scene_2.html', '<template></template>')
    touch_after_report(tmp_path, 'composition/compositions/extra/scene_2.html')
    result = parse_result(run_cli(str(tmp_path)))
    assert result['corrupt_products'] == [REPORT]
    assert 'extra/scene_2.html' in result['next_phase']['problems'][REPORT]


def test_rerunning_check_composition_brings_phase_8_back(tmp_path: Path):
    settle(tmp_path)
    touch_after_report(tmp_path, 'composition/compositions/scene_1.html')
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['id'] == '8-composition'

    write_json(tmp_path / REPORT, {'success': True, 'verdict': 'pass', 'findings': [], 'scenes_checked': ['scene_1']})
    later = (tmp_path / 'composition' / 'compositions' / 'scene_1.html').stat().st_mtime_ns + 10**9
    os.utime(tmp_path / REPORT, ns=(later, later))
    # The render ran after the re-check.
    os.utime(tmp_path / 'composition' / 'renders' / 'final.mp4', ns=(later + 10**9, later + 10**9))
    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase'] is None


def test_report_with_the_same_mtime_as_the_composition_is_accepted(tmp_path: Path):
    settle(tmp_path)
    mtime = (tmp_path / REPORT).stat().st_mtime_ns
    os.utime(tmp_path / 'composition' / 'index.html', ns=(mtime, mtime))
    assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None


def test_hidden_files_and_the_render_do_not_count_for_the_report_age(tmp_path: Path):
    settle(tmp_path)
    write_text(tmp_path / 'composition' / 'compositions' / '.DS_Store', 'junk')
    touch_after_report(tmp_path, 'composition/compositions/.DS_Store')
    touch_after_report(tmp_path, 'composition/storyboard.md')
    write_blob(tmp_path / 'composition' / 'renders' / 'final.mp4', size=256)  # the render follows the check
    mtime = (tmp_path / REPORT).stat().st_mtime_ns + 10**10
    os.utime(tmp_path / 'composition' / 'renders' / 'final.mp4', ns=(mtime, mtime))
    result = parse_result(run_cli(str(tmp_path)))
    assert result['corrupt_products'] == []
    assert statuses(result)['8-composition'] == 'completed'


def write_report_with_sources_hash(ws: Path) -> None:
    """A pass report as a current check-composition writes it, sources hash included."""
    write_json(
        ws / REPORT,
        {
            'success': True,
            'verdict': 'pass',
            'findings': [],
            'sources_sha256': composition_sources_fingerprint(ws / 'composition'),
        },
    )


def test_report_with_a_sources_hash_ignores_forged_mtime(tmp_path: Path):
    # The check report carries a content fingerprint: an edit whose mtime was
    # pushed back below the report's must still invalidate the pass.
    settle(tmp_path)
    write_report_with_sources_hash(tmp_path)
    report_mtime = (tmp_path / REPORT).stat().st_mtime_ns
    for path in (
        tmp_path / 'composition' / 'index.html',
        tmp_path / 'composition' / 'compositions' / 'scene_1.html',
        tmp_path / 'composition' / 'renders' / 'final.mp4',
    ):
        os.utime(path, ns=(report_mtime, report_mtime))

    index = tmp_path / 'composition' / 'index.html'
    index.write_text(index.read_text(encoding='utf-8') + '\n<!-- edited -->', encoding='utf-8')
    forged = report_mtime - 10**9  # older than the report: the mtime rule is fooled
    os.utime(index, ns=(forged, forged))

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '8-composition'
    assert result['next_phase']['reason'] == 'corrupt'
    assert 'sources_sha256' in result['next_phase']['problems'][REPORT]


def test_report_with_a_matching_sources_hash_passes_despite_newer_source_mtime(tmp_path: Path):
    # A copy that rewrote every mtime does not force a useless re-check.
    settle(tmp_path)
    write_report_with_sources_hash(tmp_path)
    mtime = (tmp_path / REPORT).stat().st_mtime_ns + 5 * 10**9
    for path in (
        tmp_path / 'composition' / 'index.html',
        tmp_path / 'composition' / 'compositions' / 'scene_1.html',
        tmp_path / 'composition' / 'renders' / 'final.mp4',
    ):
        os.utime(path, ns=(mtime, mtime))

    result = parse_result(run_cli(str(tmp_path)))

    assert result['corrupt_products'] == []
    assert statuses(result)['8-composition'] == 'completed'


def test_assets_and_storyboard_edits_send_phase_8_back(tmp_path: Path):
    # Changes under composition/assets/ and to storyboard.md count: the render
    # predating them means the mp4 does not contain them.
    settle(tmp_path)
    asset = tmp_path / 'composition' / 'assets' / 'brand' / 'logo.png'
    write_blob(asset, size=64)
    mtime = (tmp_path / 'composition' / 'renders' / 'final.mp4').stat().st_mtime_ns + 5 * 10**9
    os.utime(asset, ns=(mtime, mtime))
    # The report itself is fresh (its sources hash covers the asset); only the
    # render predates the edit.
    write_report_with_sources_hash(tmp_path)
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '8-composition'
    assert 'final.mp4' in result['next_phase']['problems'][REPORT]

    # Re-render and re-check after the asset edit: back to completed.
    later = mtime + 10**9
    os.utime(tmp_path / 'composition' / 'renders' / 'final.mp4', ns=(later, later))
    write_report_with_sources_hash(tmp_path)
    os.utime(tmp_path / REPORT, ns=(later + 10**9, later + 10**9))
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase'] is None


def test_storyboard_edited_after_the_render_sends_phase_8_back(tmp_path: Path):
    settle(tmp_path)
    storyboard = tmp_path / 'composition' / 'storyboard.md'
    mtime = (tmp_path / 'composition' / 'renders' / 'final.mp4').stat().st_mtime_ns + 5 * 10**9
    os.utime(storyboard, ns=(mtime, mtime))
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '8-composition'
    assert 'storyboard.md' in result['next_phase']['problems'][REPORT]
