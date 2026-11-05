"""Integration tests for scripts/pipeline-status.py.

The test seam is the script's command line (repo convention: stdout = one
JSON, exit codes 0 / 1 / 2). Fixture workspaces are built in tmp dirs.
"""
from __future__ import annotations

import hashlib
import importlib.util
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
    'coding_agent': 'pi-coding-agent',
    'fetch_materials': True,
    'qa_level': 'standard',
}

RESEARCH_BRIEF = (
    '# research brief\n\n'
    '## Key facts (verified)\n'
    '- fact [source]\n\n'
    '## Quotes (verbatim if possible)\n'
    '- "quote" — Person, [source]\n\n'
    '## Numbers / dates\n'
    '- 1, unit, [source]\n\n'
    '## Source URLs (for Phase 4 harvest)\n'
    '- https://example.com/article — official site\n'
)

# duration '5min' -> 5 * 60 * 7 = 2100 characters, here as two paragraphs.
SCRIPT_TXT = '甲' * 1050 + '\n\n' + '乙' * 1050 + '\n'

# cut-clips.py writes this flat, two-decimal path and records it as clip_path.
CLIP_PATH = 'clips/vid_001_12.00-18.50.mp4'

# A real silent mp4, built once per session for clip-file fixtures.
_CLIP_BYTES: bytes | None = None


def clip_bytes() -> bytes:
    global _CLIP_BYTES
    if _CLIP_BYTES is None:
        import subprocess

        proc = subprocess.run(
            [
                'ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
                '-i', 'testsrc=duration=1:size=64x48:rate=10', '-an',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', 'frag_keyframe+empty_moov',
                '-f', 'mp4', 'pipe:1',
            ],
            capture_output=True,
            check=True,
            timeout=60,
        )
        _CLIP_BYTES = proc.stdout
    return _CLIP_BYTES


def write_clip(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(clip_bytes())

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
                    'selected_clips': [
                        {'start': 12.0, 'end': 18.5, 'reason': '关键操作', 'frame_paths': [], 'clip_path': CLIP_PATH}
                    ],
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
        'content_plan': '先用结论开场，再按背景、对比、限制的顺序展开。',
        'facts': [],
        'material_candidates': [{'ref': 'example/img_001', 'score': 8, 'reason': '对应开场'}],
        'cues': [],
    }
]

SCENE_PLAN_PAPER = [
    {**SCENE_PLAN[0], 'material_candidates': [{'ref': 'main-paper/img_001', 'score': 8, 'reason': '论文图'}]}
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


@pytest.mark.parametrize('delegation, expected_phase', [
    ({'catalog': {'agent': 'pi-coding-agent', 'model': 'provider/model'}}, '3-research'),
    ({'catalog': {'model': ''}}, '1-gather-inputs'),
    ({'catlog': {'agent': 'pi-coding-agent'}}, '1-gather-inputs'),
    ([], '1-gather-inputs'),
])
def test_stage_delegation_is_validated_at_phase1(tmp_path: Path, delegation, expected_phase):
    ws = tmp_path / 'ws'
    complete_through_inputs(ws, delegation=delegation)
    proc = run_cli(str(ws))
    result = parse_result(proc)

    assert proc.returncode == 0
    assert result['next_phase']['id'] == expected_phase
    if expected_phase == '1-gather-inputs':
        assert 'delegation' in json.dumps(result['next_phase']['problems'])


def complete_through_research(ws: Path, *, approved: bool = True, **inputs_overrides) -> None:
    complete_through_inputs(ws, **inputs_overrides)
    if inputs_overrides.get('input_mode') == 'paper':
        write_paper_metadata(ws)
    write_text(ws / 'research-brief.md', RESEARCH_BRIEF)
    if approved and 'research-brief' in inputs_overrides.get('approval_gates', []):
        approve(ws, 'research-brief')


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
    manifest: dict = {'version': 2, 'entries': entries}
    if inputs['fetch_materials']:
        manifest['harvest_batches'] = [{'at': '2026-01-01T00:00:00Z', 'urls': ['https://example.com'], 'succeeded': 1, 'failed': 0, 'rejected': []}]
    write_json(ws / 'harvest_page' / 'manifest.json', manifest)


def complete_through_catalog(ws: Path, **inputs_overrides) -> None:
    complete_through_harvest(ws, **inputs_overrides)
    inputs = {**INPUTS, **inputs_overrides}
    entries = []
    catalog: dict = {'topic_name': 'demo'}
    if inputs['input_mode'] == 'paper':
        entries.append(PAPER_CATALOG_ENTRY)
        # 论文模式必须显式声明必用清单（没有适用图时写 []）。
        catalog['required_material_refs'] = []
    if inputs['fetch_materials']:
        entries.extend(CATALOG['entries'])
    catalog['entries'] = entries
    write_json(ws / 'material-catalog.json', catalog)
    if inputs['fetch_materials']:
        write_clip(ws / CLIP_PATH)


def complete_through_script(ws: Path, *, approved: bool = True, **inputs_overrides) -> None:
    complete_through_catalog(ws, **inputs_overrides)
    write_script(ws, SCRIPT_TXT)
    write_json(ws / 'tts-lexicon.json', {'OpenHuman': 'Open Human'})
    inputs = {**INPUTS, **inputs_overrides}
    has_catalog = inputs['fetch_materials'] or inputs['input_mode'] == 'paper'
    scene_plan = SCENE_PLAN_PAPER if inputs['input_mode'] == 'paper' else SCENE_PLAN
    write_json(ws / 'scene-plan.json', scene_plan if has_catalog else SCENE_PLAN_NO_MATERIALS)
    if approved and 'script' in inputs_overrides.get('approval_gates', []):
        approve(ws, 'script')


def complete_through_voice_subtitles(ws: Path, **inputs_overrides) -> None:
    """Phase 7 products: narration.mp3 + fresh transcript + timeline.

    Final subtitle units belong to Phase 8 now (they depend on the layout), so this
    phase never writes them.
    """
    complete_through_script(ws, **inputs_overrides)
    write_blob(ws / 'voice_clone' / 'narration.mp3')
    write_json(ws / 'transcribe' / 'transcript.json', TRANSCRIPT)
    write_json(ws / 'transcribe' / 'timeline.json', TIMELINE)


def complete_through_composition(ws: Path, **inputs_overrides) -> None:
    complete_through_voice_subtitles(ws, **inputs_overrides)
    write_json(ws / 'composition' / 'assets' / 'subtitle-units.json', SUBTITLE_UNITS)
    write_text(ws / 'composition' / 'storyboard.md', '# storyboard\n\n## scene_1\n内容区域：main\n')
    write_text(ws / 'composition' / 'index.html', '<html></html>')
    write_text(ws / 'composition' / 'compositions' / 'scene_1.html', '<template></template>')
    # 报告必须写上当前 composition 的源指纹：没有指纹的报告不再靠 mtime 降级验收。
    write_json(
        ws / 'composition' / 'check-composition.json',
        {
            'success': True,
            'verdict': 'pass',
            'findings': [],
            'sources_sha256': composition_sources_fingerprint(ws / 'composition'),
        },
    )
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
    assert '2-paper-parse' in result['skipped_phases']
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
    other['videos'][0]['selected_clips'][0]['clip_path'] = CLIP_PATH
    catalog['entries'].append(other)
    complete_through_harvest(tmp_path)
    write_json(tmp_path / 'material-catalog.json', catalog)
    write_clip(tmp_path / CLIP_PATH)
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


# --- phase 5 product: every selected clip is cut to a silent file (cut-clips.py) -------


def catalog_clip(catalog: dict) -> dict:
    return catalog['entries'][0]['videos'][0]['selected_clips'][0]


def assert_clip_problem(tmp_path: Path, catalog: dict, *detail_parts: str) -> None:
    complete_through_harvest(tmp_path)
    write_json(tmp_path / 'material-catalog.json', catalog)
    write_clip(tmp_path / CLIP_PATH)
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '5-material-catalog'
    assert 'material-catalog.json' in result['corrupt_products']
    detail = result['next_phase']['problems']['material-catalog.json']
    for part in detail_parts:
        assert part in detail, detail


def test_catalog_with_every_clip_cut_is_complete(tmp_path: Path):
    complete_through_catalog(tmp_path)
    result = parse_result(run_cli(str(tmp_path)))
    assert '5-material-catalog' in result['completed_phases']


def test_catalog_clip_without_clip_path_is_corrupt(tmp_path: Path):
    catalog = catalog_with()
    del catalog_clip(catalog)['clip_path']
    assert_clip_problem(tmp_path, catalog, 'vid_001', 'selected_clips[0]', 'clip_path', 'cut-clips')


def test_catalog_clip_with_non_string_clip_path_is_corrupt(tmp_path: Path):
    catalog = catalog_with()
    catalog_clip(catalog)['clip_path'] = 7
    assert_clip_problem(tmp_path, catalog, 'vid_001', 'clip_path')


def test_catalog_clip_that_is_not_an_object_is_corrupt(tmp_path: Path):
    catalog = catalog_with()
    catalog['entries'][0]['videos'][0]['selected_clips'] = ['12.0-18.5']
    assert_clip_problem(tmp_path, catalog, 'vid_001', 'selected_clips[0]')


def test_catalog_clip_whose_file_is_missing_is_corrupt(tmp_path: Path):
    complete_through_catalog(tmp_path)
    (tmp_path / CLIP_PATH).unlink()
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '5-material-catalog'
    assert 'material-catalog.json' in result['corrupt_products']
    assert 'material-catalog.json' not in result['missing_products']  # the catalog itself exists
    detail = result['next_phase']['problems']['material-catalog.json']
    assert CLIP_PATH in detail and 'cut-clips' in detail, detail


def test_catalog_clip_whose_file_is_empty_is_corrupt(tmp_path: Path):
    complete_through_catalog(tmp_path)
    (tmp_path / CLIP_PATH).write_bytes(b'')
    result = parse_result(run_cli(str(tmp_path)))
    assert 'material-catalog.json' in result['corrupt_products']
    assert CLIP_PATH in result['next_phase']['problems']['material-catalog.json']


@pytest.mark.parametrize('clip_path', ['../outside.mp4', 'clips/../../outside.mp4', '/etc/hosts', 'clips'])
def test_catalog_clip_path_must_be_a_file_inside_the_workspace(tmp_path: Path, clip_path: str):
    # Both files live under this test's own tmp dir, not the shared parent.
    outside = tmp_path / 'outside.mp4'
    outside.write_bytes(b'\0' * 128)
    ws = tmp_path / 'ws'
    catalog = catalog_with()
    catalog_clip(catalog)['clip_path'] = clip_path
    (ws / 'clips').mkdir(parents=True)
    complete_through_harvest(ws)
    write_json(ws / 'material-catalog.json', catalog)
    result = parse_result(run_cli(str(ws)))
    assert 'material-catalog.json' in result['corrupt_products']
    assert clip_path in result['next_phase']['problems']['material-catalog.json']


def test_catalog_clip_with_a_mismatched_clip_path_is_corrupt(tmp_path: Path):
    # The window was edited after cutting without re-running cut-clips: the
    # recorded clip_path names the OLD window's file.
    complete_through_catalog(tmp_path)
    catalog = json.loads((tmp_path / 'material-catalog.json').read_text(encoding='utf-8'))
    catalog['entries'][0]['videos'][0]['selected_clips'][0]['start'] = 13.0
    write_json(tmp_path / 'material-catalog.json', catalog)

    result = parse_result(run_cli(str(tmp_path)))

    assert 'material-catalog.json' in result['corrupt_products']
    detail = result['next_phase']['problems']['material-catalog.json']
    assert 'current window' in detail and 'cut-clips' in detail, detail


def test_catalog_clip_checker_only_requires_a_nonempty_file(tmp_path: Path):
    complete_through_catalog(tmp_path)
    (tmp_path / CLIP_PATH).write_bytes(b'not a probed video')

    proc = run_cli(str(tmp_path))

    assert proc.returncode == 0, proc.stderr
    result = parse_result(proc)
    assert '5-material-catalog' in result['completed_phases']


def test_catalog_video_without_selected_clips_needs_no_clip_files(tmp_path: Path):
    catalog = catalog_with()
    del catalog['entries'][0]['videos'][0]['selected_clips']
    complete_through_harvest(tmp_path)
    write_json(tmp_path / 'material-catalog.json', catalog)
    result = parse_result(run_cli(str(tmp_path)))
    assert '5-material-catalog' in result['completed_phases']


# --- phase 6 products: script.txt + tts-lexicon.json + narration.txt ------------


@pytest.mark.parametrize(
    'product',
    ['script.txt', 'narration.txt', 'narration-offsets.json', 'scene-plan.json'],
)
def test_missing_phase_6_product_falls_back_to_phase_6(tmp_path: Path, product: str):
    complete_through_script(tmp_path)
    (tmp_path / product).unlink()
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert product in result['missing_products']


def test_blank_script_txt_is_corrupt(tmp_path: Path):
    complete_through_script(tmp_path)
    write_text(tmp_path / 'script.txt', '  \n')
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'script.txt' in result['corrupt_products']


@pytest.mark.parametrize(
    'content',
    [
        pytest.param('{"OpenHuman": ', id='truncated-json'),
        pytest.param('["OpenHuman"]', id='not-a-map'),
        pytest.param('{}', id='empty-map'),
    ],
)
def test_invalid_lexicon_falls_back_to_phase_6(tmp_path: Path, content: str):
    complete_through_script(tmp_path)
    write_text(tmp_path / 'tts-lexicon.json', content)
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'tts-lexicon.json' in result['corrupt_products']


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
# duration 5 min -> 5 * 60 s * 7 chars/s = 2100 characters, +-15% = 1785 .. 2415.


@pytest.mark.parametrize('chars', [2520, 1680])
def test_script_20_percent_off_target_is_corrupt(tmp_path: Path, chars: int):
    complete_through_script(tmp_path)
    write_text(tmp_path / 'script.txt', script_of(chars))
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'script.txt' in result['corrupt_products']
    detail = result['next_phase']['problems']['script.txt']
    assert str(chars) in detail and '2100' in detail and '20.0%' in detail, detail


@pytest.mark.parametrize('chars', [2394, 1806])
def test_script_14_percent_off_target_is_accepted(tmp_path: Path, chars: int):
    complete_through_script(tmp_path)
    write_script(tmp_path, script_of(chars))
    approve(tmp_path, 'script')
    result = parse_result(run_cli(str(tmp_path)))
    assert '6-script-scene-plan' in result['completed_phases']


def test_script_length_ignores_whitespace(tmp_path: Path):
    complete_through_script(tmp_path)
    # 2100 characters, padded with spaces, full-width spaces and extra blank lines.
    padded = '甲 ' * 1050 + '\n\n\n　　' + '乙\t' * 1050 + '\n\n'
    write_script(tmp_path, padded)
    approve(tmp_path, 'script')
    result = parse_result(run_cli(str(tmp_path)))
    assert '6-script-scene-plan' in result['completed_phases']


def test_script_length_target_follows_numeric_duration(tmp_path: Path):
    complete_through_script(tmp_path, approved=False, duration=1)  # 1 min -> 420 characters
    result = parse_result(run_cli(str(tmp_path)))
    assert 'script.txt' in result['corrupt_products']
    assert '420' in result['next_phase']['problems']['script.txt']


def test_script_length_is_not_checked_while_duration_is_invalid(tmp_path: Path):
    complete_through_script(tmp_path, duration='soon')
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '1-gather-inputs'
    assert result['corrupt_products'] == ['inputs.json']


# --- phase 6 product: scene-plan.json -------------------------------------------


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

THREE_PARAGRAPH_SCRIPT = '甲' * 700 + '\n\n' + '乙' * 700 + '\n\n' + '丙' * 700 + '\n'  # 2100 characters


def scene(scene_id: str, paragraphs, candidates=()) -> dict:
    return {
        'scene_id': scene_id,
        'paragraphs': paragraphs,
        'intent': scene_id,
        'content_plan': f'{scene_id} 的内容与演绎方式',
        'facts': [],
        'material_candidates': list(candidates),
        'cues': [],
    }


def scene_plan_problem(
    tmp_path: Path,
    scenes,
    *,
    script: str = SCRIPT_TXT,
    approve_script: bool = False,
    catalog: dict | None = None,
    **inputs_overrides,
) -> tuple[dict, str | None]:
    """Run a Phase 6 workspace whose scene-plan.json is `scenes`; returns (result, scene-plan detail)."""
    if approve_script:
        inputs_overrides.setdefault('approval_gates', ['script'])
    complete_through_script(tmp_path, approved=False, **inputs_overrides)
    if catalog is not None:
        write_json(tmp_path / 'material-catalog.json', catalog)
    write_script(tmp_path, script)
    write_json(tmp_path / 'scene-plan.json', scenes)
    if approve_script:
        approve(tmp_path, 'script')
    result = parse_result(run_cli(str(tmp_path)))
    problems = (result['next_phase'] or {}).get('problems', {})
    return result, problems.get('scene-plan.json')


def test_scene_plan_with_content_plan_passes_and_can_be_approved(tmp_path: Path):
    result, detail = scene_plan_problem(
        tmp_path, [scene('s1', [1, 2])], approve_script=True
    )

    assert detail is None
    assert 'scene-plan.json' not in result['corrupt_products']
    assert '6-script-scene-plan' in result['completed_phases']
    approval = read_approvals(tmp_path)['gates']['script']
    assert 'scene-plan.json' in approval['products']


@pytest.mark.parametrize('field', ['intent', 'content_plan'])
@pytest.mark.parametrize('value', [None, '', '   ', 7])
def test_scene_plan_requires_a_non_empty_intent_and_content_plan(
    tmp_path: Path, field: str, value
):
    planned = scene('s1', [1, 2])
    planned[field] = value

    result, detail = scene_plan_problem(tmp_path, [planned])

    assert 'scene-plan.json' in result['corrupt_products']
    assert f'scene 0 {field}' in detail, detail


@pytest.mark.parametrize('field', ['intent', 'content_plan'])
def test_scene_plan_requires_the_planning_fields(tmp_path: Path, field: str):
    planned = scene('s1', [1, 2])
    del planned[field]

    result, detail = scene_plan_problem(tmp_path, [planned])

    assert 'scene-plan.json' in result['corrupt_products']
    assert field in detail, detail


@pytest.mark.parametrize(
    'removed, value',
    [
        ('template_scene', 'project-cover'),
        ('template_scene', None),
        ('pattern_hints', ['leaderboard']),
        ('pattern_hints', []),
        ('beats', [{'type': 'idea', 'text': '甲' * 8}]),
        ('beats', []),
    ],
)
def test_scene_plan_rejects_fields_that_belong_to_composition(
    tmp_path: Path, removed: str, value
):
    planned = scene('s1', [1, 2])
    planned[removed] = value

    result, detail = scene_plan_problem(tmp_path, [planned])

    assert 'scene-plan.json' in result['corrupt_products']
    assert removed in detail and 'scene 0' in detail, detail


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
    result, detail = scene_plan_problem(tmp_path, [scene('s1', [1, 2]), scene('s2', [2])], approve_script=True)
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
    [
        'example/img_001',
        'example/vid_001',
        'example/vid_001:12.0-18.5',
        'example/vid_001:12-18.5',
        'example/vid_001:12.005-18.495',
    ],
)
def test_scene_plan_accepts_refs_that_resolve(tmp_path: Path, ref: str):
    result, detail = scene_plan_problem(tmp_path, [scene('s1', [1, 2], candidates(ref))], approve_script=True)
    assert detail is None
    assert '6-script-scene-plan' in result['completed_phases']


def test_scene_plan_duplicate_image_ids_resolve_by_entry_slug(tmp_path: Path):
    catalog = catalog_with()
    other = json.loads(json.dumps(catalog['entries'][0]))
    other['slug'] = 'other'
    other['videos'] = []
    catalog['entries'].append(other)

    result, detail = scene_plan_problem(
        tmp_path,
        [scene('s1', [1, 2], candidates('example/img_001', 'other/img_001'))],
        approve_script=True,
        catalog=catalog,
    )

    assert detail is None
    assert '6-script-scene-plan' in result['completed_phases']


@pytest.mark.parametrize('ref', ['missing/img_001', 'example/img_999'])
def test_scene_plan_ref_with_nonexistent_slug_or_id_is_corrupt(tmp_path: Path, ref: str):
    result, detail = scene_plan_problem(
        tmp_path, [scene('s1', [1, 2], candidates('example/img_001', ref))]
    )

    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'scene-plan.json' in result['corrupt_products']
    assert repr(ref) in detail and "'example/img_001'" not in detail, detail


def test_scene_plan_bare_material_id_is_corrupt(tmp_path: Path):
    result, detail = scene_plan_problem(
        tmp_path, [scene('s1', [1, 2], candidates('example/img_001', 'img_001'))]
    )

    assert 'scene-plan.json' in result['corrupt_products']
    assert "'img_001'" in detail and "'example/img_001'" not in detail, detail


def test_scene_plan_duplicate_video_ids_and_clip_windows_are_scoped_by_slug(tmp_path: Path):
    catalog = catalog_with()
    other = json.loads(json.dumps(catalog['entries'][0]))
    other['slug'] = 'other'
    other_clip = other['videos'][0]['selected_clips'][0]
    other_clip['start'], other_clip['end'] = 20.0, 22.0
    other_clip['clip_path'] = 'clips/vid_001_20.00-22.00.mp4'
    catalog['entries'].append(other)
    write_clip(tmp_path / other_clip['clip_path'])
    valid_refs = (
        'example/vid_001',
        'other/vid_001',
        'example/vid_001:12.0-18.5',
        'other/vid_001:20.0-22.0',
    )
    wrong_entry_window = 'other/vid_001:12.0-18.5'

    result, detail = scene_plan_problem(
        tmp_path,
        [scene('s1', [1, 2], candidates(*valid_refs, wrong_entry_window))],
        catalog=catalog,
    )

    assert 'scene-plan.json' in result['corrupt_products']
    assert repr(wrong_entry_window) in detail, detail
    for ref in valid_refs:
        assert repr(ref) not in detail, detail


@pytest.mark.parametrize(
    'ref',
    [
        'example/vid_001:13.0-18.5',  # start differs by 1.0
        'example/vid_001:12.0-18.6',  # end differs by 0.1
        'example/vid_999:12.0-18.5',  # no such video
        'example/img_001:12.0-18.5',  # an image has no clips
        'example/vid_001:abc-def',
        'example/vid_001:12.0',
        'example/vid_001:12.0-18.5-20',
        'example/vid_001:',
        ':12.0-18.5',
        'example/vid_001:12.0 - 18.5',  # float() would accept these; the documented form has no spaces
        'example/vid_001: 12-18.5',
        'example/vid_001:+12-18.5',
        'example/vid_001:1_2-18.5',
    ],
)
def test_scene_plan_clip_ref_that_matches_no_selected_clip_is_corrupt(tmp_path: Path, ref: str):
    result, detail = scene_plan_problem(tmp_path, [scene('s1', [1, 2], candidates(ref))])
    assert 'scene-plan.json' in result['corrupt_products']
    assert repr(ref) in detail, detail


def test_scene_plan_lists_every_invalid_ref(tmp_path: Path):
    scenes = [
        scene('s1', [1], candidates('example/nope_1')),
        scene('s2', [2], candidates('example/img_001', 'example/nope_2')),
    ]
    _, detail = scene_plan_problem(tmp_path, scenes)
    assert "'example/nope_1'" in detail and "'example/nope_2'" in detail, detail


def test_scene_plan_without_catalog_phase_must_have_no_candidates(tmp_path: Path):
    result, detail = scene_plan_problem(
        tmp_path, [scene('s1', [1, 2], candidates('example/img_001'))], fetch_materials=False
    )
    assert 'scene-plan.json' in result['corrupt_products']
    assert 'fetch_materials' in detail and "'example/img_001'" in detail, detail


def test_scene_plan_without_catalog_phase_and_no_candidates_is_accepted(tmp_path: Path):
    result, detail = scene_plan_problem(
        tmp_path, [scene('s1', [1, 2])], fetch_materials=False, approve_script=True
    )
    assert detail is None
    assert '6-script-scene-plan' in result['completed_phases']


@pytest.mark.parametrize('catalog_state', ['missing', 'corrupt'])
def test_scene_plan_refs_are_not_judged_against_an_unusable_catalog(
    tmp_path: Path, catalog_state: str
):
    complete_through_script(tmp_path)
    if catalog_state == 'missing':
        (tmp_path / 'material-catalog.json').unlink()
    else:
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


def test_missing_subtitle_units_falls_back_to_phase_8(tmp_path: Path):
    complete_through_composition(tmp_path)
    (tmp_path / 'composition' / 'assets' / 'subtitle-units.json').unlink()
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    # 最终字幕依赖 layout，所以它属于 Phase 8，而不是 Phase 7。
    assert result['next_phase']['id'] == '8-composition'
    assert 'composition/assets/subtitle-units.json' in result['missing_products']
    assert '7-voice-subtitles' in result['completed_phases']


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


def test_corrupt_subtitle_units_falls_back_to_phase_8(tmp_path: Path):
    complete_through_composition(tmp_path)
    write_json(tmp_path / 'composition' / 'assets' / 'subtitle-units.json', {'units': []})
    proc = run_cli(str(tmp_path))
    result = parse_result(proc)
    assert result['next_phase']['id'] == '8-composition'
    assert 'composition/assets/subtitle-units.json' in result['corrupt_products']


def write_timeline_with(ws: Path, **fields) -> None:
    write_json(ws / 'transcribe' / 'timeline.json', {**TIMELINE, **fields})


def test_timeline_without_optional_scenes_or_cues_passes(tmp_path: Path):
    complete_through_voice_subtitles(tmp_path)

    result = parse_result(run_cli(str(tmp_path)))

    assert '7-voice-subtitles' in result['completed_phases']


@pytest.mark.parametrize('beats', [[], [{'begin_s': 0, 'end_s': 1}]])
def test_timeline_with_beats_is_rejected(tmp_path: Path, beats):
    complete_through_voice_subtitles(tmp_path)
    write_timeline_with(tmp_path, beats=beats)

    result = parse_result(run_cli(str(tmp_path)))

    assert 'transcribe/timeline.json' in result['corrupt_products']
    detail = result['next_phase']['problems']['transcribe/timeline.json']
    assert 'beats' in detail


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
    # 内容变了就要重新检查：报告里嵌入的源指纹必须覆盖现在这份 composition。
    write_json(
        tmp_path / 'composition' / 'check-composition.json',
        {'success': True, 'verdict': 'pass', 'findings': [],
         'sources_sha256': composition_sources_fingerprint(tmp_path / 'composition')},
    )
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


def test_paper_mode_without_fetch_full_run(tmp_path: Path):
    complete_all(tmp_path, input_mode='paper', fetch_materials=False)
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase'] is None
    assert result['skipped_phases'] == ['4-material-harvest']
    assert '5-material-catalog' in result['completed_phases']


def test_paper_mode_without_fetch_scene_plan_refs_resolve_against_the_catalog(tmp_path: Path):
    result, detail = scene_plan_problem(
        tmp_path, [scene('s1', [1, 2], candidates('main-paper/img_001'))],
        input_mode='paper', fetch_materials=False, approve_script=True,
    )
    assert detail is None
    assert '6-script-scene-plan' in result['completed_phases']


def test_paper_mode_without_fetch_scene_plan_ref_missing_from_catalog_is_corrupt(tmp_path: Path):
    result, detail = scene_plan_problem(
        tmp_path, [scene('s1', [1, 2], candidates('main-paper/nope_1'))],
        input_mode='paper', fetch_materials=False,
    )
    assert 'scene-plan.json' in result['corrupt_products']
    assert "'main-paper/nope_1'" in detail, detail


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


def test_a_design_removed_from_the_library_is_rejected_even_with_a_workspace_copy(tmp_path: Path):
    """库里已删除的 design 不再靠工作区里的历史副本变相存续。"""
    complete_through_research(tmp_path)
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'design': 'moon'})
    copy = tmp_path / 'modules' / 'designs' / 'moon'
    copy.mkdir(parents=True)
    (copy / 'moon.md').write_text('# moon', encoding='utf-8')
    write_json(copy / 'moon.json', {
        'design': 'moon',
        'fonts': {'css_filename': 'moon-fonts.css', 'css2_families': ['X']},
    })
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '1-gather-inputs'
    assert 'inputs.json' in result['corrupt_products']
    assert "design 'moon' is not an available design" in result['next_phase']['problems']['inputs.json']
    # 工作区的历史副本没被删掉，只是不再被当作可用资源。
    assert (copy / 'moon.md').is_file()


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
    assert script['upstream']['material-catalog.json'] == sha256_of((tmp_path / 'material-catalog.json').read_bytes())
    assert script['upstream']['inputs.json#narration_requests'] == field_sha256([])  # 缺省与 [] 等价


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
    '5-material-catalog': ['harvest_page/manifest.json', 'research-brief.md', 'catalog-instructions.md'],
    '6-script-scene-plan': [
        'research-brief.md', 'material-catalog.json', 'inputs.json#duration', 'inputs.json#language',
        'inputs.json#input_mode', 'inputs.json#narration_requests',
    ],
    '7-voice-subtitles': [
        'narration.txt', 'narration-offsets.json', 'script.txt', 'scene-plan.json',
    ],
    '8-composition': [
        'voice_clone/narration.mp3', 'transcribe/transcript.json', 'narration.txt',
        'narration-offsets.json', 'transcribe/timeline.json', 'material-catalog.json',
        'scene-plan.json', 'script.txt', 'inputs.json#design', 'inputs.json#layout',
        'inputs.json#template', 'inputs.json#orientation', 'inputs.json#composition_requests',
        'modules/designs/default/default.json', 'modules/layouts/stage.json',
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
    approve(tmp_path, 'research-brief')
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
    assert set(products) == {
        'composition/assets/subtitle-units.json',
        'composition/storyboard.md',
        'composition/index.html',
        'composition/check-composition.json',
        'composition/renders/final.mp4',
    }


def test_phases_that_are_not_completed_get_no_stamp(tmp_path: Path):
    complete_all(tmp_path)
    (tmp_path / 'research-brief.md').unlink()
    assert not (tmp_path / '.pipeline' / 'stamps.json').exists()  # fixtures no longer stamp via approvals
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

EDITED_SCRIPT_TXT = '甲' * 1050 + '\n\n' + '丙' * 1050 + '\n'  # same length as SCRIPT_TXT, other content


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
    write_json(ws / 'transcribe' / 'timeline.json', {**TIMELINE, 'total_s': 2.6})


def rewrite_subtitle_units(ws: Path) -> None:
    """Phase 8's deterministic subtitles regenerated (same audio, new layout)."""
    write_json(
        ws / 'composition' / 'assets' / 'subtitle-units.json',
        {'units': [{'text': '大家好呀', 'begin_s': 0.0, 'end_s': 2.6}]},
    )
    write_json(
        ws / 'composition' / 'check-composition.json',
        {'success': True, 'verdict': 'pass', 'findings': [],
         'sources_sha256': composition_sources_fingerprint(ws / 'composition')},
    )
    write_blob(ws / 'composition' / 'renders' / 'final.mp4', size=256)


def test_a_partial_redo_keeps_the_phase_stale(tmp_path: Path):
    # Only re-running the aligner after a script edit must not clear Phase 7's
    # stale mark: narration.mp3 and transcript.json are still the old build.
    settle(tmp_path)
    write_script(tmp_path, EDITED_SCRIPT_TXT)
    approve(tmp_path, 'script')
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['id'] == '7-voice-subtitles'

    write_json(tmp_path / 'transcribe' / 'timeline.json', {**TIMELINE, 'total_s': 2.6})
    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '7-voice-subtitles'
    assert result['next_phase']['reason'] == 'stale'
    assert result['next_phase']['changed_upstream'] == ['narration.txt', 'narration-offsets.json', 'script.txt']
    # While the phase is stale the stamp keeps the pre-change fingerprints: the
    # rebuilt product is NOT recorded until the redo is complete.
    stamp = read_stamps(tmp_path)['phases']['7-voice-subtitles']
    assert stamp['upstream']['script.txt'] == sha256_of(SCRIPT_TXT)
    assert stamp['products']['transcribe/timeline.json'] == sha256_of(
        json.dumps(TIMELINE, ensure_ascii=False)
    )

    rewrite_voice_subtitles(tmp_path)
    result = parse_result(run_cli(str(tmp_path)))
    assert statuses(result)['7-voice-subtitles'] == 'completed'


def test_an_upstream_key_missing_from_an_old_stamp_makes_the_phase_stale(tmp_path: Path):
    # 新要求不能因为旧戳缺键就永久忽略：缺键就是“不是按当前要求构建”，该阶段要重做。
    settle(tmp_path)
    stamps = read_stamps(tmp_path)
    del stamps['phases']['9-check-mix']['upstream']['inputs.json#qa_level']
    write_json(tmp_path / '.pipeline' / 'stamps.json', stamps)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '9-check-mix'
    assert result['next_phase']['reason'] == 'stale'
    assert result['next_phase']['changed_upstream'] == ['inputs.json#qa_level']
    # 旧戳与旧产物都原样保留，不自动迁移。
    assert (tmp_path / '.pipeline' / 'stamps.json').is_file()
    assert (tmp_path / 'composition' / 'renders' / 'final_with_bgm.mp4').is_file()


def test_an_upstream_key_removed_from_the_contract_makes_the_phase_stale(tmp_path: Path):
    # 旧戳里还留着阶段已不再声明的键：那也是契约变化，不能静默当作没变。
    settle(tmp_path)
    stamps = read_stamps(tmp_path)
    stamps['phases']['7-voice-subtitles']['upstream']['inputs.json#layout'] = 'stale'
    write_json(tmp_path / '.pipeline' / 'stamps.json', stamps)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '7-voice-subtitles'
    assert result['next_phase']['changed_upstream'] == ['inputs.json#layout']


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
    approve(tmp_path, 'script')

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


def test_the_old_instruction_files_are_not_upstreams_any_more(tmp_path: Path):
    # 旧项目里还留着这三个文件时，新建或修改它们都不影响任何阶段。
    settle(tmp_path)
    for name in ('narration-instructions.md', 'composition-instructions.md', 'style-prompt.md'):
        write_text(tmp_path / name, '旧要求\n')
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase'] is None
    assert result['stale_phases'] == []


def test_changing_the_layout_makes_only_phase_8_stale(tmp_path: Path):
    """换布局只重做画面：音频、transcript 与时间轴都不重建。"""
    settle(tmp_path)
    write_json(
        tmp_path / 'inputs.json',
        {**INPUTS, 'layout': 'portrait', 'orientation': 'portrait'},
    )
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '8-composition'
    assert result['next_phase']['reason'] == 'stale'
    assert result['next_phase']['changed_upstream'] == [
        'inputs.json#layout', 'inputs.json#orientation',
        'modules/layouts/portrait.json', 'modules/layouts/stage.json',
    ]
    assert result['stale_phases'] == ['8-composition']
    assert result['pending_phases'] == ['9-check-mix']
    # Phase 7 不依赖 layout，保持完成。
    assert statuses(result)['7-voice-subtitles'] == 'completed'


def test_a_layout_that_does_not_match_the_orientation_blocks_phase_8(tmp_path: Path):
    """3:4 与 9:16 混用、或横竖错配时，问题留在 Phase 8，不回退 Phase 1。"""
    settle(tmp_path)
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'layout': 'portrait'})  # landscape 项目
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '8-composition'
    assert result['next_phase']['reason'] == 'corrupt'
    detail = result['next_phase']['problems']['inputs.json#layout']
    assert 'portrait' in detail and '1080x1920' in detail and 'landscape' in detail
    assert 'inputs.json' not in result['corrupt_products']
    # 视觉配置问题不算产物缺失，也不会让 Phase 1 重做。
    assert statuses(result)['1-gather-inputs'] == 'completed'


def test_a_three_by_four_layout_cannot_stand_in_for_nine_by_sixteen(tmp_path: Path):
    settle(tmp_path, orientation='portrait', layout='portrait')
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'orientation': 'portrait-3:4', 'layout': 'portrait'})
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '8-composition'
    detail = result['next_phase']['problems']['inputs.json#layout']
    assert '1080x1920' in detail and '1080x1440' in detail


def test_a_newly_added_narration_request_makes_phase_6_stale(tmp_path: Path):
    # narration_requests 缺省时是 absent，补上后就变成上游变化。
    settle(tmp_path)
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'narration_requests': ['结尾不要 CTA']})
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert result['next_phase']['changed_upstream'] == ['inputs.json#narration_requests']
    assert result['stale_phases'] == ['6-script-scene-plan']


def test_a_newly_added_composition_request_makes_phase_8_stale(tmp_path: Path):
    settle(tmp_path)
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'composition_requests': ['不要人物区']})
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '8-composition'
    assert result['next_phase']['changed_upstream'] == ['inputs.json#composition_requests']


@pytest.mark.parametrize('change', ['create', 'edit', 'delete'])
def test_catalog_instruction_changes_stale_catalog_and_stop_downstream(tmp_path: Path, change: str):
    instructions = tmp_path / 'catalog-instructions.md'
    if change != 'create':
        write_text(instructions, '优先展示 UI 操作。')
    settle(tmp_path)
    original_stamp = read_stamps(tmp_path)['phases']['5-material-catalog']

    if change == 'delete':
        instructions.unlink()
    else:
        write_text(instructions, '不要使用当前 img_001，只选择流程图。')
    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '5-material-catalog'
    assert result['next_phase']['reason'] == 'stale'
    assert result['next_phase']['changed_upstream'] == ['catalog-instructions.md']
    assert '5-material-catalog' not in result['completed_phases']
    assert result['pending_phases'] == ['6-script-scene-plan', '7-voice-subtitles', '8-composition', '9-check-mix']
    assert read_stamps(tmp_path)['phases']['5-material-catalog'] == original_stamp


def test_unchanged_catalog_instructions_keep_the_pipeline_current(tmp_path: Path):
    write_text(tmp_path / 'catalog-instructions.md', '优先展示 UI 操作。')
    settle(tmp_path)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase'] is None
    assert result['stale_phases'] == []


def test_old_catalog_stamp_without_instruction_dependency_is_stale(tmp_path: Path):
    settle(tmp_path)
    stamps = read_stamps(tmp_path)
    del stamps['phases']['5-material-catalog']['upstream']['catalog-instructions.md']
    write_json(tmp_path / '.pipeline' / 'stamps.json', stamps)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '5-material-catalog'
    assert result['next_phase']['reason'] == 'stale'
    assert result['next_phase']['changed_upstream'] == ['catalog-instructions.md']
    assert read_stamps(tmp_path) == stamps


def test_reapproving_an_edited_product_stales_the_next_phase(tmp_path: Path):
    settle(tmp_path, approval_gates=['research-brief'])
    edited = RESEARCH_BRIEF + '- one more fact [source]\n'
    write_text(tmp_path / 'research-brief.md', edited)
    waiting = parse_result(run_cli(str(tmp_path)))
    assert waiting['next_phase']['reason'] == 'awaiting_approval'

    result = approve(tmp_path, 'research-brief')

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
    approve(tmp_path, 'script')
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['id'] == '7-voice-subtitles'

    rewrite_voice_subtitles(tmp_path)
    result = parse_result(run_cli(str(tmp_path)))

    assert statuses(result)['7-voice-subtitles'] == 'completed'
    assert result['next_phase']['id'] == '8-composition'
    assert result['next_phase']['reason'] == 'stale'
    assert result['next_phase']['changed_upstream'] == [
        'voice_clone/narration.mp3',
        'transcribe/transcript.json',
        'narration.txt',
        'narration-offsets.json',
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
    approve(tmp_path, 'script')

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
    approve(tmp_path, 'script')
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


def test_quarantined_stamps_keep_every_phase_unverified_until_it_is_accepted(tmp_path: Path):
    complete_all(tmp_path)
    write_text(tmp_path / '.pipeline' / 'stamps.json', 'garbage')

    for _ in range(2):
        result = parse_result(run_cli(str(tmp_path)))
        assert result['stamps_reset'] is True
        # Nothing was accepted yet, so there is nothing to record as built.
        assert not (tmp_path / '.pipeline' / 'stamps.json').exists()
        assert result['next_phase']['id'] == '1-gather-inputs'
        assert result['next_phase']['reason'] == 'unverified'
        assert result['completed_phases'] == []


def test_accepting_every_phase_resolves_the_quarantined_stamps(tmp_path: Path):
    settle(tmp_path)
    write_text(tmp_path / '.pipeline' / 'stamps.json', 'garbage')

    # Accepting one phase is not enough: the other phases stay unknown.
    first = parse_result(run_cli(str(tmp_path), '--restamp', '1-gather-inputs'))
    assert first['stamps_reset'] is True
    assert list(read_stamps(tmp_path)['phases']) == ['1-gather-inputs']
    assert first['next_phase']['id'] == '3-research'
    assert first['next_phase']['reason'] == 'unverified'

    for phase_id in (phase for phase in PHASE_IDS if phase != '2-paper-parse'):
        proc = run_cli(str(tmp_path), '--restamp', phase_id)
        assert proc.returncode == 0, proc.stderr

    resolved = parse_result(run_cli(str(tmp_path)))
    assert resolved['stamps_reset'] is False
    assert not (tmp_path / '.pipeline' / 'stamps.json.quarantined').exists()
    assert (tmp_path / '.pipeline' / 'stamps.json').is_file()
    assert resolved['next_phase'] is None


def test_last_acceptance_keeps_quarantine_if_saving_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settle(tmp_path)
    write_text(tmp_path / '.pipeline' / 'stamps.json', 'garbage')
    parse_result(run_cli(str(tmp_path)))  # Quarantine the unusable stamps.
    for phase_id in PHASE_IDS:
        if phase_id not in ('2-paper-parse', '9-check-mix'):
            proc = run_cli(str(tmp_path), '--restamp', phase_id)
            assert proc.returncode == 0, proc.stderr

    spec = importlib.util.spec_from_file_location('pipeline_status_recovery_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # @dataclass resolves its module here.
    spec.loader.exec_module(module)
    stamps = module.Stamps(tmp_path)
    phase = module.PHASES_BY_ID['9-check-mix']
    fingerprints = module.Fingerprinter(tmp_path)
    stamps.put(phase['id'], fingerprints.upstream(phase), fingerprints.products(phase))
    before = (tmp_path / '.pipeline' / 'stamps.json').read_bytes()

    def fail_save():
        raise OSError('simulated stamps write failure')

    monkeypatch.setattr(stamps, 'save', fail_save)
    with pytest.raises(OSError, match='simulated stamps write failure'):
        stamps.resolve_quarantine()

    # The marker must survive until the full record is on disk; another run
    # cannot quietly treat the last phase as a new, implicitly trusted phase.
    assert stamps.reset is True
    assert (tmp_path / '.pipeline' / 'stamps.json.quarantined').exists()
    assert (tmp_path / '.pipeline' / 'stamps.json').read_bytes() == before
    retry = parse_result(run_cli(str(tmp_path)))
    assert retry['next_phase']['id'] == '9-check-mix'
    assert retry['next_phase']['reason'] == 'unverified'

    recovered = parse_result(run_cli(str(tmp_path), '--restamp', '9-check-mix'))
    assert recovered['next_phase'] is None
    assert recovered['stamps_reset'] is False
    assert not (tmp_path / '.pipeline' / 'stamps.json.quarantined').exists()


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
    write_text(tmp_path / 'script.txt', '甲' * 1050 + '\n\n' + '乙' * 1055 + '\n')  # 5 characters longer
    detail = offsets_problem(tmp_path)
    assert 'script_length' in detail and 'script.txt' in detail and '2103' in detail and '2108' in detail, detail
    assert 'make-narration' in detail


def test_script_edited_to_the_same_length_is_caught_by_the_hash(tmp_path: Path):
    # The character counts cannot see it, but make-narration records content
    # hashes in the offset table exactly for this case.
    settle(tmp_path)
    write_text(tmp_path / 'script.txt', EDITED_SCRIPT_TXT)
    detail = offsets_problem(tmp_path)
    assert 'script_sha256' in detail and 'script.txt' in detail and 'make-narration' in detail, detail


def test_offsets_without_content_hashes_are_rejected_even_at_the_same_length(tmp_path: Path):
    # 没有内容哈希就只能比字数，而等长编辑看不出文字变了。这种偏移表属于旧格式，
    # 明确判损坏并要求重新生成，不降级验收。
    settle(tmp_path)
    offsets = json.loads((tmp_path / 'narration-offsets.json').read_text(encoding='utf-8'))
    for field in ('script_sha256', 'narration_sha256'):
        offsets.pop(field, None)
    write_json(tmp_path / 'narration-offsets.json', offsets)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert result['next_phase']['reason'] == 'corrupt'
    assert 'narration-offsets.json' in result['corrupt_products']
    detail = result['next_phase']['problems']['narration-offsets.json']
    assert 'script_sha256' in detail and 'make-narration' in detail
    # 不改完就没法审稿过关：缺证据的产物不是“可接受的旧格式”。
    approve_proc = run_cli(str(tmp_path), '--approve', 'script')
    assert approve_proc.returncode == 2
    # 旧文件与下游产物都还在，只是不再被当成合格的验收证据。
    assert (tmp_path / 'narration-offsets.json').is_file()
    assert (tmp_path / 'voice_clone' / 'narration.mp3').is_file()


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
    approve(tmp_path, 'script')
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
    assert 'sources_sha256 does not match' in detail and 'check-composition' in detail, detail
    assert result['pending_phases'] == ['9-check-mix']


def test_nested_composition_file_edited_after_the_report_sends_phase_8_back(tmp_path: Path):
    settle(tmp_path)
    write_text(tmp_path / 'composition' / 'compositions' / 'extra' / 'scene_2.html', '<template></template>')
    touch_after_report(tmp_path, 'composition/compositions/extra/scene_2.html')
    result = parse_result(run_cli(str(tmp_path)))
    assert result['corrupt_products'] == [REPORT]
    # 报告里只有一份聚合指纹，所以只能报“composition 变了”，具体改哪个文件要看 diff。
    assert 'sources_sha256 does not match' in result['next_phase']['problems'][REPORT]


def test_rerunning_check_composition_brings_phase_8_back(tmp_path: Path):
    settle(tmp_path)
    touch_after_report(tmp_path, 'composition/compositions/scene_1.html')
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['id'] == '8-composition'

    write_report_with_sources_hash(tmp_path)
    # 重新渲染，使成片不早于任何源文件（含被推到期时间之后的那份 scene）。
    newest = max(
        path.stat().st_mtime_ns
        for path in (tmp_path / 'composition').rglob('*')
        if path.is_file() and path.name != 'final.mp4'
    )
    os.utime(tmp_path / 'composition' / 'renders' / 'final.mp4', ns=(newest + 10**9, newest + 10**9))
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


# --- opt-in user approval gates: inputs.json + .pipeline/approvals.json -----------


def approve(ws: Path, gate: str) -> dict:
    proc = run_cli(str(ws), '--approve', gate)
    assert proc.returncode == 0, proc.stderr
    return parse_result(proc)


def read_approvals(ws: Path) -> dict:
    return json.loads((ws / '.pipeline' / 'approvals.json').read_text(encoding='utf-8'))


def test_requested_research_waits_for_approval_and_later_phases_are_pending(tmp_path: Path):
    complete_through_research(tmp_path, approved=False, approval_gates=['research-brief'])

    result = parse_result(run_cli(str(tmp_path)))

    assert result['completed_phases'] == ['1-gather-inputs']
    assert result['next_phase'] == {
        'id': '3-research',
        'title': '主题调研',
        'doc': 'references/phases/03-research.md',
        'reason': 'awaiting_approval',
        'gate': 'research-brief',
        'instruction': (
            '把 research-brief.md 给用户过目；用户确认后运行 '
            '`python3 scripts/pipeline-status.py <ws> --approve research-brief`'
        ),
        'problems': {},
    }
    assert statuses(result)['3-research'] == 'awaiting_approval'
    assert result['pending_phases'] == PHASE_IDS[3:]


def test_approving_research_records_product_hash_and_completes_the_gate(tmp_path: Path):
    complete_through_research(tmp_path, approved=False, approval_gates=['research-brief'])

    result = approve(tmp_path, 'research-brief')

    assert '3-research' in result['completed_phases']
    assert result['next_phase']['id'] == '4-material-harvest'
    approvals = read_approvals(tmp_path)
    assert approvals['version'] == 1
    assert set(approvals['gates']) == {'research-brief'}
    approval = approvals['gates']['research-brief']
    assert set(approval) == {'approved_at', 'products'}
    datetime.fromisoformat(approval['approved_at'])
    assert approval['products'] == {'research-brief.md': sha256_of(RESEARCH_BRIEF)}
    # Approval is durable, not a one-shot transition in this invocation.
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['id'] == '4-material-harvest'


def test_changing_an_approved_research_brief_requires_confirmation_again(tmp_path: Path):
    complete_through_research(tmp_path, approved=False, approval_gates=['research-brief'])
    approve(tmp_path, 'research-brief')
    write_text(tmp_path / 'research-brief.md', RESEARCH_BRIEF + '- another verified fact [source]\n')

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '3-research'
    assert result['next_phase']['reason'] == 'awaiting_approval'
    assert result['next_phase']['gate'] == 'research-brief'


def test_script_gate_records_only_its_contract_products(tmp_path: Path):
    complete_through_script(tmp_path, approved=False, approval_gates=['script'])
    waiting = parse_result(run_cli(str(tmp_path)))
    assert waiting['next_phase']['id'] == '6-script-scene-plan'
    assert waiting['next_phase']['reason'] == 'awaiting_approval'
    assert waiting['next_phase']['gate'] == 'script'
    assert waiting['next_phase']['instruction'] == (
        '把旁白和每个 scene 的 scene_id + intent + content_plan 摘要交给用户确认；确认后运行 '
        '`python3 scripts/pipeline-status.py <ws> --approve script`'
    )
    assert waiting['pending_phases'] == ['7-voice-subtitles', '8-composition', '9-check-mix']

    result = approve(tmp_path, 'script')

    assert '6-script-scene-plan' in result['completed_phases']
    assert result['next_phase']['id'] == '7-voice-subtitles'
    products = read_approvals(tmp_path)['gates']['script']['products']
    assert products == {
        'script.txt': sha256_of(SCRIPT_TXT),
        'tts-lexicon.json': sha256_of((tmp_path / 'tts-lexicon.json').read_bytes()),
        'scene-plan.json': sha256_of((tmp_path / 'scene-plan.json').read_bytes()),
    }


@pytest.mark.parametrize('product', ['script.txt', 'tts-lexicon.json', 'scene-plan.json'])
def test_changing_script_gate_products_after_approval_returns_to_the_gate(tmp_path: Path, product: str):
    complete_through_script(tmp_path, approved=False, approval_gates=['script'])
    approve(tmp_path, 'script')
    if product == 'script.txt':
        write_script(tmp_path, EDITED_SCRIPT_TXT)
    elif product == 'tts-lexicon.json':
        write_json(tmp_path / product, {'OpenHuman': '欧鹏休曼'})
    else:
        write_json(tmp_path / product, [{**SCENE_PLAN[0], 'intent': '更新后的开场'}])

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert result['next_phase']['reason'] == 'awaiting_approval'
    assert result['next_phase']['gate'] == 'script'
    assert statuses(result)['6-script-scene-plan'] == 'awaiting_approval'
    assert result['pending_phases'] == ['7-voice-subtitles', '8-composition', '9-check-mix']


def test_approve_rejects_products_that_do_not_pass_with_exit_2(tmp_path: Path):
    complete_through_research(tmp_path, approved=False)
    write_text(tmp_path / 'research-brief.md', '  \n')

    proc = run_cli(str(tmp_path), '--approve', 'research-brief')

    assert proc.returncode == 2
    result = parse_result(proc)
    assert result['success'] is False
    assert 'research-brief' in result['error']
    assert result['problems']['research-brief.md']
    assert not (tmp_path / '.pipeline' / 'approvals.json').exists()


def test_approve_rejects_an_unknown_gate_with_exit_2(tmp_path: Path):
    proc = run_cli(str(tmp_path), '--approve', 'unknown')

    assert proc.returncode == 2
    assert 'unknown' in parse_result(proc)['error']


@pytest.mark.parametrize('policy', [{}, {'approval_gates': []}])
def test_default_and_explicit_auto_complete_without_approval_records(tmp_path: Path, policy: dict):
    complete_all(tmp_path, **policy)

    for _ in range(2):  # Resume also stays automatic, including legacy inputs.
        proc = run_cli(str(tmp_path))
        assert proc.returncode == 0, proc.stderr
        result = parse_result(proc)
        assert result['approval_gates'] == []
        assert result['next_phase'] is None
        assert not result['pending_phases']
        assert not result['stale_phases']
    assert not (tmp_path / '.pipeline' / 'approvals.json').exists()


@pytest.mark.parametrize('record', [
    'not json',
    json.dumps({'version': 99, 'gates': {}}),
    json.dumps({'version': 1, 'gates': {'research-brief': {'products': {}}}}),
])
@pytest.mark.parametrize('requested', [False, True])
def test_unusable_approval_records_only_block_requested_review(tmp_path: Path, record: str, requested: bool):
    gates = ['research-brief'] if requested else []
    complete_through_research(tmp_path, approved=False, approval_gates=gates)
    write_text(tmp_path / '.pipeline' / 'approvals.json', record)

    proc = run_cli(str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    result = parse_result(proc)
    assert result['approval_gates'] == gates
    if requested:
        assert result['next_phase']['reason'] == 'awaiting_approval'
        assert result['next_phase']['gate'] == 'research-brief'
    else:
        assert result['next_phase']['id'] == '4-material-harvest'
        assert '3-research' in result['completed_phases']
    assert (tmp_path / '.pipeline' / 'approvals.json').read_text(encoding='utf-8') == record


@pytest.mark.parametrize('gates', [
    None, True, 'script', {}, ['unknown'], ['SCRIPT'], [1], [[]], [{}],
    ['script', 'script'],
])
def test_invalid_approval_gates_are_corrupt_inputs(tmp_path: Path, gates):
    complete_through_inputs(tmp_path, approval_gates=gates)

    proc = run_cli(str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    result = parse_result(proc)
    assert result['next_phase']['id'] == '1-gather-inputs'
    assert result['next_phase']['reason'] == 'corrupt'
    assert 'approval_gates' in result['next_phase']['problems']['inputs.json']


def test_enabling_review_and_authorizing_auto_do_not_stale_existing_products(tmp_path: Path):
    settle(tmp_path)
    before = read_stamps(tmp_path)['phases']
    assert not (tmp_path / '.pipeline' / 'approvals.json').exists()
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'approval_gates': ['research-brief', 'script']})

    waiting = parse_result(run_cli(str(tmp_path)))
    assert waiting['next_phase']['gate'] == 'research-brief'
    assert waiting['next_phase']['reason'] == 'awaiting_approval'
    assert waiting['pending_phases'] == PHASE_IDS[3:]
    assert waiting['stale_phases'] == []

    # Approving this draft must not cancel the separate request to review the script.
    waiting = approve(tmp_path, 'research-brief')
    assert waiting['next_phase']['gate'] == 'script'
    assert waiting['next_phase']['reason'] == 'awaiting_approval'
    assert waiting['pending_phases'] == PHASE_IDS[6:]
    assert waiting['stale_phases'] == []
    approvals_before_auto = read_approvals(tmp_path)

    # Explicit user authorization to finish automatically changes policy, not approvals.
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'approval_gates': []})
    for _ in range(2):
        resumed = parse_result(run_cli(str(tmp_path)))
        assert resumed['approval_gates'] == []
        assert resumed['next_phase'] is None
        assert resumed['stale_phases'] == []
    assert read_approvals(tmp_path) == approvals_before_auto
    assert set(approvals_before_auto['gates']) == {'research-brief'}
    after = read_stamps(tmp_path)['phases']
    assert {key: value for key, value in after.items() if key != '1-gather-inputs'} == {
        key: value for key, value in before.items() if key != '1-gather-inputs'
    }


def test_disabling_unapproved_review_resumes_without_manufacturing_approval(tmp_path: Path):
    complete_through_script(tmp_path, approved=False, approval_gates=['script'])
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['reason'] == 'awaiting_approval'

    write_json(tmp_path / 'inputs.json', {**INPUTS, 'approval_gates': []})
    resumed = parse_result(run_cli(str(tmp_path)))
    assert resumed['next_phase']['id'] == '7-voice-subtitles'
    assert '6-script-scene-plan' in resumed['completed_phases']
    assert not (tmp_path / '.pipeline' / 'approvals.json').exists()


def test_corrupt_products_take_precedence_over_requested_approval(tmp_path: Path):
    complete_through_research(tmp_path, approved=False, approval_gates=['research-brief'])
    write_text(tmp_path / 'research-brief.md', '   \n')
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['reason'] == 'corrupt'

    write_text(tmp_path / 'research-brief.md', RESEARCH_BRIEF)
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['reason'] == 'awaiting_approval'


def test_restamp_does_not_bypass_requested_review(tmp_path: Path):
    complete_through_research(tmp_path, approved=False, approval_gates=['research-brief'])
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['reason'] == 'awaiting_approval'
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'language': 'en', 'approval_gates': ['research-brief']})
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['reason'] == 'stale'

    proc = run_cli(str(tmp_path), '--restamp', '3-research')
    assert proc.returncode == 0, proc.stderr
    assert parse_result(proc)['next_phase']['reason'] == 'awaiting_approval'
    assert not (tmp_path / '.pipeline' / 'approvals.json').exists()


# --- redo requests: products that pass can still be asked to be redone -----------
#
# A user or the agent itself can find a phase's content wrong while every file is
# still in place. Files alone cannot express that, and deleting shared products
# (the harvest manifest, the catalog) to force a rollback loses other phases' work.


def redo(ws: Path, phase_id: str, reason: str = '内容不合格，需要重做') -> dict:
    proc = run_cli(str(ws), '--redo', phase_id, '--reason', reason)
    assert proc.returncode == 0, proc.stderr
    return parse_result(proc)


def finish(ws: Path, phase_id: str) -> subprocess.CompletedProcess:
    return run_cli(str(ws), '--finish', phase_id)


def read_redos(ws: Path) -> dict:
    return json.loads((ws / '.pipeline' / 'redos.json').read_text(encoding='utf-8'))


def test_a_redo_request_stops_the_phase_from_counting_as_completed(tmp_path: Path):
    settle(tmp_path)
    before = (tmp_path / 'script.txt').read_bytes()

    result = redo(tmp_path, '6-script-scene-plan', '第三段重复，合并后重写')

    assert result['next_phase'] == {
        'id': '6-script-scene-plan',
        'title': '脚本与场景规划（委派）',
        'doc': 'references/phases/06-script-scene-plan.md',
        'reason': 'redo',
        'redo_reason': '第三段重复，合并后重写',
        'problems': {},
    }
    assert statuses(result)['6-script-scene-plan'] == 'redo_requested'
    assert result['redo_phases'] == ['6-script-scene-plan']
    assert result['pending_phases'] == PHASE_IDS[6:]
    assert '6-script-scene-plan' not in result['completed_phases']
    assert result['stale_phases'] == []
    # The products stay in place: a redo is a request, not a deletion.
    assert (tmp_path / 'script.txt').read_bytes() == before
    assert read_redos(tmp_path)['requests']['6-script-scene-plan']['reason'] == '第三段重复，合并后重写'


def test_a_redo_request_survives_plain_runs_and_product_edits(tmp_path: Path):
    settle(tmp_path)
    redo(tmp_path, '6-script-scene-plan')

    # Rewriting the products is not the signal that ends a redo: only --finish is.
    write_script(tmp_path, EDITED_SCRIPT_TXT)

    for _ in range(2):
        result = parse_result(run_cli(str(tmp_path)))
        assert result['next_phase']['reason'] == 'redo'
        assert result['next_phase']['id'] == '6-script-scene-plan'
    # Even a file rewritten to the very same bytes cannot clear the request.
    write_script(tmp_path, SCRIPT_TXT)
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['reason'] == 'redo'


def test_finish_accepts_a_redo_once_its_products_pass(tmp_path: Path):
    settle(tmp_path)
    redo(tmp_path, '6-script-scene-plan')
    write_script(tmp_path, EDITED_SCRIPT_TXT)

    proc = finish(tmp_path, '6-script-scene-plan')

    assert proc.returncode == 0, proc.stderr
    result = parse_result(proc)
    assert result['redo_phases'] == []
    assert statuses(result)['6-script-scene-plan'] == 'completed'
    assert not (tmp_path / '.pipeline' / 'redos.json').exists()
    # The redo changed script.txt, so the phases built from it must be redone.
    assert result['next_phase']['id'] == '7-voice-subtitles'
    assert result['next_phase']['reason'] == 'stale'
    assert set(result['next_phase']['changed_upstream']) == {'script.txt', 'narration.txt', 'narration-offsets.json'}


def test_finish_does_not_skip_the_phase_novelty_check(tmp_path: Path):
    settle(tmp_path)
    # An input changed before the redo was requested: the products are the old build.
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'qa_level': 'strict'})
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['reason'] == 'stale'
    redo(tmp_path, '9-check-mix')

    # The rerun is deterministic and produces the very same bytes.
    for relpath in ('qa/qa-report.json', 'composition/renders/final_with_bgm.mp4'):
        product = tmp_path / relpath
        product.write_bytes(product.read_bytes())

    proc = finish(tmp_path, '9-check-mix')

    # Finishing clears the request but still refuses to accept the old build.
    assert proc.returncode == 2
    result = parse_result(proc)
    assert result['success'] is False
    assert 'restamp' in result['error']
    assert result['changed_upstream'] == ['inputs.json#qa_level']
    assert not (tmp_path / '.pipeline' / 'redos.json').exists()
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['reason'] == 'stale'

    # Accepting a byte-identical rerun is what --restamp is for.
    accepted = parse_result(run_cli(str(tmp_path), '--restamp', '9-check-mix'))
    assert statuses(accepted)['9-check-mix'] == 'completed'
    assert accepted['next_phase'] is None


def test_finishing_a_redo_does_not_accept_the_other_unverified_phases(tmp_path: Path):
    settle(tmp_path)
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'qa_level': 'strict'})  # Phase 9 goes stale
    redo(tmp_path, '3-research', '核对简报')
    write_text(tmp_path / '.pipeline' / 'stamps.json', 'garbage')  # none of the stamps are usable

    proc = finish(tmp_path, '3-research')

    assert proc.returncode == 0, proc.stderr
    result = parse_result(proc)
    # Only the finished phase was accepted, and only it was recorded.
    assert result['completed_phases'] == []
    assert result['stamps_reset'] is True
    assert result['next_phase']['id'] == '1-gather-inputs'
    assert result['next_phase']['reason'] == 'unverified'
    assert statuses(result)['9-check-mix'] == 'pending'
    recorded = read_stamps(tmp_path)['phases']
    assert list(recorded) == ['3-research']
    # The old table is still quarantined until every phase is accepted again.
    assert (tmp_path / '.pipeline' / 'stamps.json.quarantined').exists()


def test_finish_refuses_products_that_do_not_pass(tmp_path: Path):
    settle(tmp_path)
    redo(tmp_path, '6-script-scene-plan')
    (tmp_path / 'script.txt').unlink()

    proc = finish(tmp_path, '6-script-scene-plan')

    assert proc.returncode == 2
    result = parse_result(proc)
    assert result['success'] is False
    assert '6-script-scene-plan' in result['error']
    assert 'script.txt' in result['problems']
    # The request is cleared first (as agreed), and the phase still has to be redone:
    # the plain scan reports the missing product.
    assert not (tmp_path / '.pipeline' / 'redos.json').exists()
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['reason'] == 'missing'


def test_finish_without_a_pending_redo_is_refused(tmp_path: Path):
    settle(tmp_path)
    proc = finish(tmp_path, '6-script-scene-plan')
    assert proc.returncode == 2
    result = parse_result(proc)
    assert result['success'] is False
    assert 'no redo is pending' in result['error']


def test_redo_requests_are_worked_off_earliest_first(tmp_path: Path):
    settle(tmp_path)
    redo(tmp_path, '3-research', '事实需要重核')
    redo(tmp_path, '6-script-scene-plan', '叙事重复')

    first = parse_result(run_cli(str(tmp_path)))
    assert first['next_phase']['id'] == '3-research'
    assert first['next_phase']['redo_reason'] == '事实需要重核'
    # Phases after the next one are pending, never inspected: only the earliest
    # request is reported, and the later one is not lost.
    assert first['redo_phases'] == ['3-research']
    assert first['pending_phases'] == PHASE_IDS[3:]

    assert finish(tmp_path, '3-research').returncode == 0
    second = parse_result(run_cli(str(tmp_path)))
    assert second['next_phase']['id'] == '6-script-scene-plan'
    assert second['next_phase']['reason'] == 'redo'
    assert second['next_phase']['redo_reason'] == '叙事重复'


def test_restamp_and_approve_do_not_bypass_a_pending_redo(tmp_path: Path):
    complete_through_research(tmp_path, approved=False, approval_gates=['research-brief'])
    redo(tmp_path, '3-research')
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'language': 'en', 'approval_gates': ['research-brief']})

    restamp = run_cli(str(tmp_path), '--restamp', '3-research')
    assert restamp.returncode == 1
    assert 'redo is pending' in parse_result(restamp)['error']

    approve_proc = run_cli(str(tmp_path), '--approve', 'research-brief')
    assert approve_proc.returncode == 2
    assert 'redo is pending' in parse_result(approve_proc)['error']
    assert not (tmp_path / '.pipeline' / 'approvals.json').exists()


def test_a_redo_of_a_skipped_phase_is_refused(tmp_path: Path):
    settle(tmp_path)  # standard mode: Phase 2 does not apply
    proc = run_cli(str(tmp_path), '--redo', '2-paper-parse', '--reason', '重做')
    assert proc.returncode == 1
    result = parse_result(proc)
    assert result['success'] is False
    assert 'skipped' in result['error']


@pytest.mark.parametrize(
    'args',
    [
        ('--redo',),  # no phase
        ('--redo', '6-script-scene-plan'),  # no reason
        ('--redo', '6-script-scene-plan', '--reason', '   '),  # blank reason
        ('--reason', '重做'),  # reason without --redo
        ('--finish',),  # no phase
        ('--redo', '6-script-scene-plan', '--reason', 'x', '--finish', '6-script-scene-plan'),
        ('--redo', '10-publish', '--reason', 'x'),  # unknown phase
        ('--finish', '10-publish'),
        ('--restamp', '6-script-scene-plan', '--reason', 'x'),  # reason only applies to --redo
    ],
)
def test_redo_and_finish_usage_errors_exit_2(tmp_path: Path, args: tuple[str, ...]):
    settle(tmp_path)
    proc = run_cli(str(tmp_path), *args)
    assert proc.returncode == 2
    assert parse_result(proc)['success'] is False


# --- optional material_search_requests: a platform search the user asked for ------


def test_adding_a_material_search_request_restales_only_the_harvest(tmp_path: Path):
    settle(tmp_path)

    write_json(
        tmp_path / 'inputs.json',
        {**INPUTS, 'material_search_requests': ['去 Google 图片搜 Roblox 的界面截图']},
    )
    result = parse_result(run_cli(str(tmp_path)))

    # Recording the request alone changes nothing: whether a redo is needed is not
    # inferred from the files or the inputs, only from an explicit request.
    assert result['next_phase'] is None
    assert result['stale_phases'] == []

    scheduled = redo(tmp_path, '4-material-harvest', '执行用户要求的平台搜索')
    assert scheduled['next_phase']['id'] == '4-material-harvest'
    assert scheduled['next_phase']['reason'] == 'redo'
    assert scheduled['next_phase']['redo_reason'] == '执行用户要求的平台搜索'


@pytest.mark.parametrize(
    'content',
    [
        '{broken',  # truncated
        '[]',
        '{"version": 2, "requests": {}}',
        '{"version": 1}',  # no requests object
    ],
)
def test_an_unusable_redo_file_fails_the_run_instead_of_dropping_the_request(
    tmp_path: Path, content: str
):
    settle(tmp_path)
    redo(tmp_path, '6-script-scene-plan')
    write_text(tmp_path / '.pipeline' / 'redos.json', content)

    proc = run_cli(str(tmp_path))

    assert proc.returncode == 1
    result = parse_result(proc)
    assert result['success'] is False
    assert 'redos.json' in result['error']
    # Every action refuses as well: a pending request must never be lost quietly.
    for args in (('--finish', '6-script-scene-plan'), ('--redo', '6-script-scene-plan', '--reason', 'x')):
        failing = run_cli(str(tmp_path), *args)
        assert failing.returncode == 1
        assert parse_result(failing)['success'] is False
    # The evidence is left in place for inspection.
    assert (tmp_path / '.pipeline' / 'redos.json').read_text(encoding='utf-8') == content


@pytest.mark.parametrize('section', ['## Key facts', '## Quotes', '## Numbers', '## Source URLs'])
def test_research_brief_must_carry_the_sections_downstream_reads(tmp_path: Path, section: str):
    complete_through_inputs(tmp_path, fetch_materials=False)
    without = '\n'.join(
        line for line in RESEARCH_BRIEF.splitlines() if not line.startswith(section)
    )
    write_text(tmp_path / 'research-brief.md', without + '\n')

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '3-research'
    assert result['next_phase']['reason'] == 'corrupt'
    assert f'## {section.lstrip("# ")}' in result['next_phase']['problems']['research-brief.md']


# --- 模板在 Phase 8 定、要求按阶段分开记 ------------------------------------------


def test_template_is_not_a_phase_1_field(tmp_path: Path):
    # Phase 8 才选模板：旧输入不带 template 也要能过 Phase 1。
    inputs = {key: value for key, value in INPUTS.items() if key != 'template'}
    write_json(tmp_path / 'inputs.json', inputs)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['completed_phases'] == ['1-gather-inputs']
    assert result['next_phase']['id'] == '3-research'


@pytest.mark.parametrize('value', ['github/../escape', '', 3])
def test_template_must_be_null_or_a_plain_name_in_phase_8(tmp_path: Path, value):
    complete_through_voice_subtitles(tmp_path, template=value)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '8-composition'
    assert result['next_phase']['reason'] == 'corrupt'
    assert 'inputs.json#template' in result['next_phase']['problems']
    assert '1-gather-inputs' in result['completed_phases']


def test_composition_must_write_the_template_choice(tmp_path: Path):
    """模板选择归 composition：未写回字段时不能以旧行为当作“不用模板”。"""
    complete_through_voice_subtitles(tmp_path)
    inputs = json.loads((tmp_path / 'inputs.json').read_text(encoding='utf-8'))
    inputs.pop('template', None)
    write_json(tmp_path / 'inputs.json', inputs)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '8-composition'
    assert result['next_phase']['reason'] == 'corrupt'
    assert 'inputs.json#template' in result['next_phase']['problems']
    assert 'not set' in result['next_phase']['problems']['inputs.json#template']


@pytest.mark.parametrize('field', ['narration_requests', 'composition_requests'])
@pytest.mark.parametrize('value', ['语气更口语', None, [''], ['ok', 3]])
def test_requests_must_be_lists_of_non_empty_strings(tmp_path: Path, field: str, value):
    complete_through_inputs(tmp_path, **{field: value})

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '1-gather-inputs'
    assert result['next_phase']['reason'] == 'corrupt'
    assert field in result['next_phase']['problems']['inputs.json']


@pytest.mark.parametrize('value', [['语气更口语'], []])
def test_requests_lists_are_accepted_including_empty(tmp_path: Path, value):
    complete_through_inputs(tmp_path, narration_requests=value, composition_requests=value)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['completed_phases'] == ['1-gather-inputs']
    assert result['next_phase']['id'] == '3-research'


# --- catalog 的必用素材（论文关键图） --------------------------------------------


def paper_catalog(**catalog_overrides) -> dict:
    return {
        'topic_name': 'demo',
        'entries': [PAPER_CATALOG_ENTRY],
        **catalog_overrides,
    }


def test_required_material_refs_must_resolve_in_the_catalog(tmp_path: Path):
    complete_through_harvest(tmp_path, input_mode='paper', fetch_materials=False)
    write_json(
        tmp_path / 'material-catalog.json',
        paper_catalog(required_material_refs=['main-paper/img_404']),
    )

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '5-material-catalog'
    assert 'required_material_refs' in result['next_phase']['problems']['material-catalog.json']
    assert 'main-paper/img_404' in result['next_phase']['problems']['material-catalog.json']


def test_required_material_refs_must_not_repeat(tmp_path: Path):
    complete_through_harvest(tmp_path, input_mode='paper', fetch_materials=False)
    write_json(
        tmp_path / 'material-catalog.json',
        paper_catalog(required_material_refs=['main-paper/img_001', 'main-paper/img_001']),
    )

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '5-material-catalog'
    assert 'repeats' in result['next_phase']['problems']['material-catalog.json']


@pytest.mark.parametrize(
    'required_refs',
    [
        pytest.param(['main-paper/img_001'], id='resolved-figure'),
        pytest.param([], id='empty-list'),
    ],
)
def test_declared_paper_required_refs_pass_phase_5(tmp_path: Path, required_refs: list[str]):
    complete_through_harvest(tmp_path, input_mode='paper', fetch_materials=False)
    write_json(
        tmp_path / 'material-catalog.json',
        paper_catalog(required_material_refs=required_refs),
    )

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'material-catalog.json' not in result['corrupt_products']


def test_scene_plan_must_select_every_required_material(tmp_path: Path):
    # 关键图被 catalog 标成必用，但 scene 一个都没选：Phase 6 打回。
    complete_through_catalog(tmp_path, input_mode='paper', fetch_materials=False)
    catalog = json.loads((tmp_path / 'material-catalog.json').read_text(encoding='utf-8'))
    catalog['required_material_refs'] = ['main-paper/img_001']
    write_json(tmp_path / 'material-catalog.json', catalog)
    write_script(tmp_path, SCRIPT_TXT)
    write_json(tmp_path / 'tts-lexicon.json', {'OpenHuman': 'Open Human'})
    unselected = [{**SCENE_PLAN_PAPER[0], 'material_candidates': []}]
    write_json(tmp_path / 'scene-plan.json', unselected)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '6-script-scene-plan'
    detail = result['next_phase']['problems']['scene-plan.json']
    assert 'required_material_refs' in detail and 'main-paper/img_001' in detail


@pytest.mark.parametrize('value', ['https://example.com', [], None, [''], ['  '], ['ok', 3]])
def test_material_search_requests_must_be_a_list_of_non_empty_strings(tmp_path: Path, value):
    complete_through_inputs(tmp_path, material_search_requests=value)
    result = parse_result(run_cli(str(tmp_path)))

    if value == []:
        assert result['completed_phases'] == ['1-gather-inputs']  # an empty list asks for nothing
        return
    assert result['next_phase']['id'] == '1-gather-inputs'
    assert result['next_phase']['reason'] == 'corrupt'
    assert 'material_search_requests' in result['next_phase']['problems']['inputs.json']


# --- 素材策略与必用清单的适用范围 ----------------------------------------------
#
# catalog 阶段不适用时（标准模式 + fetch_materials = false），目录里残留的
# material-catalog.json 不参与任何要求：否则同一版本的项目切换素材策略后自己就
# 推进不下去了。


def test_a_residual_catalog_does_not_block_no_material_mode(tmp_path: Path):
    settle(tmp_path)  # 带素材跑完过一次
    assert (tmp_path / 'material-catalog.json').is_file()

    write_json(tmp_path / 'inputs.json', {**INPUTS, 'fetch_materials': False})
    write_json(tmp_path / 'scene-plan.json', SCENE_PLAN_NO_MATERIALS)
    approve(tmp_path, 'script')
    result = parse_result(run_cli(str(tmp_path)))

    assert '5-material-catalog' in result['skipped_phases']
    # 残留 catalog 不再要求 scene-plan 覆盖它。
    problems = result['next_phase'].get('problems', {})
    assert 'required_material_refs' not in str(problems)
    assert 'scene-plan.json' not in result['corrupt_products']
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert result['next_phase']['reason'] == 'stale'
    # 切换策略会改变依赖集合；核对已按无素材规则重建的结果后可接受同字节产物。
    accepted = parse_result(run_cli(str(tmp_path), '--restamp', '6-script-scene-plan'))
    assert accepted['next_phase']['id'] == '7-voice-subtitles'
    assert (tmp_path / 'material-catalog.json').is_file()  # 旧产物没被删掉


def test_required_refs_of_a_residual_catalog_are_ignored_in_no_material_mode(tmp_path: Path):
    complete_through_catalog(tmp_path)
    catalog = json.loads((tmp_path / 'material-catalog.json').read_text(encoding='utf-8'))
    catalog['required_material_refs'] = ['example/img_001']
    write_json(tmp_path / 'material-catalog.json', catalog)
    write_script(tmp_path, SCRIPT_TXT)
    write_json(tmp_path / 'tts-lexicon.json', {'OpenHuman': 'Open Human'})
    write_json(tmp_path / 'scene-plan.json', SCENE_PLAN_NO_MATERIALS)
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'fetch_materials': False})

    result = parse_result(run_cli(str(tmp_path)))

    assert 'required_material_refs' not in str(result['next_phase'].get('problems', {}))
    assert result['next_phase']['id'] != '6-script-scene-plan'


def test_clip_refs_are_compared_by_identity_not_by_spelling(tmp_path: Path):
    # 必用清单写 12-18.5，候选写 12.00-18.50：指向同一个片段，不算漏选。
    complete_through_catalog(tmp_path)
    catalog = json.loads((tmp_path / 'material-catalog.json').read_text(encoding='utf-8'))
    catalog['required_material_refs'] = ['example/vid_001:12-18.5']
    write_json(tmp_path / 'material-catalog.json', catalog)
    write_script(tmp_path, SCRIPT_TXT)
    write_json(tmp_path / 'tts-lexicon.json', {'OpenHuman': 'Open Human'})
    write_json(tmp_path / 'scene-plan.json', [
        {**SCENE_PLAN[0], 'material_candidates': [{'ref': 'example/vid_001:12.00-18.50', 'score': 8, 'reason': 'x'}]},
    ])

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] != '6-script-scene-plan'
    assert 'scene-plan.json' not in result['corrupt_products']


def test_a_candidate_that_does_not_cover_a_required_clip_is_caught(tmp_path: Path):
    # 要求某条片段，候选却是同一 entry 的图片：不能算覆盖。
    complete_through_catalog(tmp_path)
    catalog = json.loads((tmp_path / 'material-catalog.json').read_text(encoding='utf-8'))
    catalog['required_material_refs'] = ['example/vid_001:12.00-18.50']
    write_json(tmp_path / 'material-catalog.json', catalog)
    write_script(tmp_path, SCRIPT_TXT)
    write_json(tmp_path / 'tts-lexicon.json', {'OpenHuman': 'Open Human'})
    write_json(tmp_path / 'scene-plan.json', [
        {**SCENE_PLAN[0], 'material_candidates': [{'ref': 'example/img_001', 'score': 8, 'reason': 'x'}]},
    ])

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'example/vid_001:12.00-18.50' in result['next_phase']['problems']['scene-plan.json']


def test_a_required_ref_that_does_not_resolve_is_a_catalog_error(tmp_path: Path):
    # 必用清单写了一个 catalog 里不存在的窗口：错在 catalog 本身。
    complete_through_harvest(tmp_path)
    catalog = json.loads(json.dumps(CATALOG))
    catalog['required_material_refs'] = ['example/vid_001:12-19']
    write_json(tmp_path / 'material-catalog.json', catalog)
    write_clip(tmp_path / CLIP_PATH)

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '5-material-catalog'
    assert 'not found in this catalog' in result['next_phase']['problems']['material-catalog.json']


def test_a_clip_candidate_covers_the_material_ref_it_belongs_to(tmp_path: Path):
    # 要求“用这个视频”，候选是一条它的片段：视频确实上镜了，算覆盖。
    complete_through_catalog(tmp_path)
    catalog = json.loads((tmp_path / 'material-catalog.json').read_text(encoding='utf-8'))
    catalog['required_material_refs'] = ['example/vid_001']
    write_json(tmp_path / 'material-catalog.json', catalog)
    write_script(tmp_path, SCRIPT_TXT)
    write_json(tmp_path / 'tts-lexicon.json', {'OpenHuman': 'Open Human'})
    write_json(tmp_path / 'scene-plan.json', [
        {**SCENE_PLAN[0], 'material_candidates': [{'ref': 'example/vid_001:12.00-18.50', 'score': 8, 'reason': 'x'}]},
    ])

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] != '6-script-scene-plan'


# --- 要求列表：缺省与 [] 等价 --------------------------------------------------


@pytest.mark.parametrize('field', ['narration_requests', 'composition_requests'])
def test_switching_a_request_list_between_absent_and_empty_is_not_a_change(tmp_path: Path, field: str):
    settle(tmp_path, **{field: []})
    inputs = json.loads((tmp_path / 'inputs.json').read_text(encoding='utf-8'))
    del inputs[field]
    write_json(tmp_path / 'inputs.json', inputs)
    assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None

    write_json(tmp_path / 'inputs.json', {**INPUTS, field: []})
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase'] is None
    assert result['stale_phases'] == []


# --- 指纹缓存与不可读的持久状态 ------------------------------------------------


def test_an_unreadable_fingerprint_cache_is_ignored_not_fatal(tmp_path: Path):
    settle(tmp_path)
    (tmp_path / '.pipeline' / 'fpcache.json').write_text('{not json', encoding='utf-8')

    result = parse_result(run_cli(str(tmp_path)))

    assert result['success'] is True
    assert result['next_phase'] is None  # 缓存只是加速手段，坏了就重新哈希
    read_json = json.loads((tmp_path / '.pipeline' / 'fpcache.json').read_text(encoding='utf-8'))
    assert read_json['version'] == 1


def test_an_unwritable_fingerprint_cache_does_not_lose_the_scan(tmp_path: Path):
    settle(tmp_path)
    cache = tmp_path / '.pipeline' / 'fpcache.json'
    cache.write_text('{"version": 1, "files": {}}', encoding='utf-8')
    cache.chmod(0o444)
    try:
        proc = run_cli(str(tmp_path))
    finally:
        cache.chmod(0o644)

    result = parse_result(proc)
    assert result['success'] is True
    assert result['next_phase'] is None


def test_paper_catalog_must_declare_the_required_refs_field(tmp_path: Path):
    # 缺省分不清“没有关键图”和“还没看过”：论文模式必须显式声明（可为 []）。
    complete_through_harvest(tmp_path, input_mode='paper', fetch_materials=False)
    write_json(
        tmp_path / 'material-catalog.json',
        {'topic_name': 'demo', 'entries': [PAPER_CATALOG_ENTRY]},
    )

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '5-material-catalog'
    detail = result['next_phase']['problems']['material-catalog.json']
    assert 'required_material_refs' in detail and 'paper' in detail


def test_a_standard_catalog_need_not_declare_the_required_refs_field(tmp_path: Path):
    result = settle(tmp_path)  # 标准模式，catalog 没有这个字段
    assert result['next_phase'] is None
