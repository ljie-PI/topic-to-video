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

SCENE_PLAN = [
    {
        'scene_id': 'scene_1',
        'paragraphs': [1, 2],
        'intent': '开场与背景',
        'facts': [],
        'material_candidates': [],
        'cues': [],
    }
]

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
        {'entries': [{'slug': 'example', 'images': [], 'videos': []}]},
    )


def complete_through_catalog(ws: Path, **inputs_overrides) -> None:
    complete_through_harvest(ws, **inputs_overrides)
    write_json(
        ws / 'material-catalog.json',
        {'topic_name': 'demo', 'entries': [{'slug': 'example', 'images': [], 'videos': []}]},
    )


def complete_through_script(ws: Path, **inputs_overrides) -> None:
    complete_through_catalog(ws, **inputs_overrides)
    write_text(ws / 'script.txt', '第一段显示稿。\n\n第二段显示稿。\n')
    write_json(ws / 'tts-lexicon.json', {'OpenHuman': 'Open Human'})
    write_text(ws / 'narration.txt', '第一段旁白。\n\n第二段旁白。\n')
    write_json(ws / 'scene-plan.json', SCENE_PLAN)


def complete_through_tts(ws: Path, **inputs_overrides) -> None:
    complete_through_script(ws, **inputs_overrides)
    write_blob(ws / 'voice_clone' / 'narration.mp3')


def complete_through_align(ws: Path, **inputs_overrides) -> None:
    complete_through_tts(ws, **inputs_overrides)
    write_json(ws / 'transcribe' / 'transcript.json', TRANSCRIPT)
    write_json(ws / 'transcribe' / 'subtitle-units.json', SUBTITLE_UNITS)
    write_json(ws / 'transcribe' / 'timeline.json', TIMELINE)


def complete_through_composition(ws: Path, **inputs_overrides) -> None:
    complete_through_align(ws, **inputs_overrides)
    write_blob(ws / 'composition' / 'renders' / 'final.mp4')


def complete_all(ws: Path, **inputs_overrides) -> None:
    complete_through_composition(ws, **inputs_overrides)
    write_blob(ws / 'composition' / 'renders' / 'final_with_bgm.mp4')


# --- usage / workspace errors -------------------------------------------------


def test_usage_error_exits_2(tmp_path: Path):
    proc = run_cli('--bogus-flag')
    assert proc.returncode == 2
    result = parse_result(proc)
    assert result['success'] is False


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


def test_deleted_product_falls_back(tmp_path: Path):
    complete_through_tts(tmp_path)
    (tmp_path / 'voice_clone' / 'narration.mp3').unlink()
    proc = run_cli(str(tmp_path))
    assert proc.returncode == 0
    result = parse_result(proc)
    assert result['next_phase']['id'] == '7-tts'
    assert 'voice_clone/narration.mp3' in result['missing_products']


# --- phase 8 products: transcript + subtitle units + timeline --------------------


def test_missing_timeline_falls_back_to_phase_8(tmp_path: Path):
    complete_through_align(tmp_path)
    (tmp_path / 'transcribe' / 'timeline.json').unlink()
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '8-align-subtitles'
    assert 'transcribe/timeline.json' in result['missing_products']
    assert '8-align-subtitles' not in result['completed_phases']


def test_corrupt_timeline_falls_back_to_phase_8(tmp_path: Path):
    complete_through_align(tmp_path)
    write_json(tmp_path / 'transcribe' / 'timeline.json', {'paragraphs': []})
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '8-align-subtitles'
    assert 'transcribe/timeline.json' in result['corrupt_products']


def test_truncated_timeline_json_falls_back_to_phase_8(tmp_path: Path):
    complete_through_align(tmp_path)
    write_text(tmp_path / 'transcribe' / 'timeline.json', '{"paragraphs": [')  # 截断 JSON
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '8-align-subtitles'
    assert 'transcribe/timeline.json' in result['corrupt_products']


def test_corrupt_subtitle_units_falls_back_to_phase_8(tmp_path: Path):
    complete_through_align(tmp_path)
    write_json(tmp_path / 'transcribe' / 'subtitle-units.json', {'units': []})
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '8-align-subtitles'
    assert 'transcribe/subtitle-units.json' in result['corrupt_products']


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
        '7-tts',
        '8-align-subtitles',
        '9-composition',
        '10-check-mix',
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
    del inputs['qa_level']
    write_json(tmp_path / 'inputs.json', inputs)
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '1-gather-inputs'
    assert 'inputs.json' in result['corrupt_products']


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
