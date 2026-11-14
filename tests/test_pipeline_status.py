"""Integration tests for scripts/pipeline-status.py.

The test seam is the script's command line (repo convention: stdout = one
JSON, exit codes 0 / 1 / 2). Fixture workspaces are built in tmp dirs.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

import media
import video_contract
from cli_helpers import parse_stdout, write_silent_mp3

pytestmark = pytest.mark.usefixtures('require_ffmpeg')

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
    equal to the script, and an offset table of one whole-text segment."""
    length = len(script)
    write_text(ws / 'narration.txt', script)
    write_json(
        ws / 'narration-offsets.json',
        {
            'version': 1,
            'script_length': length,
            'narration_length': length,
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
    """stdout must be a single-line parseable JSON document."""
    assert proc.returncode in (0, 1, 2)
    return parse_stdout(proc)


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
    write_audio(ws / 'voice_clone' / 'narration.mp3')
    write_json(ws / 'transcribe' / 'transcript.json', TRANSCRIPT)
    write_json(ws / 'transcribe' / 'timeline.json', TIMELINE)


_AUDIO_DURATION: float | None = None


def write_audio(path: Path) -> float:
    """一段真实可探测的静音 mp3（复用共享会话缓存字节，首次探测时长）。"""
    global _AUDIO_DURATION
    write_silent_mp3(path, 2.6)
    if _AUDIO_DURATION is None:
        _AUDIO_DURATION = media.probe_duration(path)
    return _AUDIO_DURATION


def write_scene_config(ws: Path) -> dict:
    """Phase 8 的机器配置产物：两个视觉 scene 借用一个注册 preset。"""
    duration = media.probe_duration(ws / 'voice_clone' / 'narration.mp3')
    landscape = json.loads((REPO_ROOT / 'modules' / 'layouts' / 'landscape.json').read_text(encoding='utf-8'))
    layout = {'preset': 'landscape', 'regions': landscape['regions'], 'caption': landscape['caption']}
    def visual_scene(scene_id: str, begin: float, end: float) -> dict:
        return {
            'scene_id': scene_id, 'source_scene_ids': ['scene_1'],
            'begin_s': begin, 'end_s': end, 'template': None, 'layout': layout,
        }
    config = {
        'version': 1,
        'canvas': {'width': 1920, 'height': 1080},
        'total_s': duration,
        'scenes': [visual_scene('visual_a', 0, duration / 2), visual_scene('visual_b', duration / 2, duration)],
    }
    write_json(ws / 'composition' / 'scene-config.json', config)
    return config


def complete_through_composition(ws: Path, **inputs_overrides) -> None:
    complete_through_voice_subtitles(ws, **inputs_overrides)
    write_json(ws / 'composition' / 'assets' / 'subtitle-units.json', SUBTITLE_UNITS)
    write_text(ws / 'composition' / 'storyboard.md', '# storyboard\n\n## scene_1\n内容区域：main\n')
    write_text(ws / 'composition' / 'index.html', '<html></html>')
    write_text(ws / 'composition' / 'compositions' / 'scene_1.html', '<template></template>')
    write_scene_config(ws)
    preset = video_contract.load_design_preset(REPO_ROOT, 'default')
    write_json(ws / 'composition' / 'design.json', {
        'version': 1,
        'source': 'preset',
        'preset': 'default',
        'tokens': preset['tokens'],
        'min_font_px': preset['min_font_px'],
    })
    write_json(ws / 'composition' / 'check-composition.json', pass_report(ws))
    write_blob(ws / 'composition' / 'renders' / 'final.mp4')


def pass_report(ws: Path) -> dict:
    """一份覆盖当前 scene-config 的 pass 报告（状态脚本验收 scenes_checked）。"""
    config = json.loads((ws / 'composition' / 'scene-config.json').read_text(encoding='utf-8'))
    return {
        'success': True, 'verdict': 'pass', 'findings': [],
        'scenes_checked': [
            {'scene_id': scene['scene_id'], 'layout': scene['layout']['preset'], 'check_times': [scene['begin_s']]}
            for scene in config['scenes']
        ],
    }


def complete_through_check(ws: Path, **inputs_overrides) -> None:
    complete_through_composition(ws, **inputs_overrides)
    write_json(ws / 'qa' / 'qa-report.json', {'findings': [], 'verdict': 'pass'})


def complete_all(ws: Path, **inputs_overrides) -> None:
    complete_through_check(ws, **inputs_overrides)
    inputs = {**INPUTS, **inputs_overrides}
    if inputs.get('bgm', True):
        write_blob(ws / 'composition' / 'renders' / 'final_with_bgm.mp4')


# --- usage / workspace errors -------------------------------------------------


def test_missing_or_nonexistent_workspace_errors(tmp_path: Path):
    missing_arg = run_cli()
    assert missing_arg.returncode == 2
    assert 'workspace' in parse_result(missing_arg)['error']

    nonexistent = run_cli(str(tmp_path / 'nope'))
    assert nonexistent.returncode == 1
    assert parse_result(nonexistent)['success'] is False


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


def test_corrupt_catalog_entries_items_and_persisted_paths_fall_back_to_phase_5(tmp_path: Path):
    complete_through_harvest(tmp_path)
    write_clip(tmp_path / CLIP_PATH)

    no_id = catalog_with()
    del no_id['entries'][0]['images'][0]['id']
    no_vid_desc = catalog_with()
    del no_vid_desc['entries'][0]['videos'][0]['semantic_description']
    not_list = catalog_with()
    not_list['entries'][0]['images'] = {'id': 'img_001'}
    abs_img = catalog_with(local_path='/old-project/file')
    abs_sub = catalog_with()
    abs_sub['entries'][0]['videos'][0]['subtitle_path'] = '/old-project/file'

    for bad_catalog, parts in (
        (catalog_with(semantic_description=''), ('img_001', 'semantic_description')),
        (no_id, ('example', 'id')),
        (catalog_with(id=7), ('example', 'id')),
        (no_vid_desc, ('vid_001', 'semantic_description')),
        (not_list, ('example', 'images')),
        ({'entries': ['example']}, ('entry 0',)),
        (abs_img, ('local_path',)),
        (abs_sub, ('subtitle_path',)),
    ):
        write_json(tmp_path / 'material-catalog.json', bad_catalog)
        result = parse_result(run_cli(str(tmp_path)))
        assert result['next_phase']['id'] == '5-material-catalog'
        assert 'material-catalog.json' in result['corrupt_products']
        detail = result['next_phase']['problems']['material-catalog.json']
        for part in parts:
            assert part in detail, detail


def test_valid_catalog_shapes_and_clip_requirements(tmp_path: Path):
    complete_through_harvest(tmp_path)
    # 1. Empty entry items or videos without selected_clips need no clip files.
    write_json(tmp_path / 'material-catalog.json', {'entries': [{'slug': 'text-only', 'images': [], 'videos': []}]})
    assert '5-material-catalog' in parse_result(run_cli(str(tmp_path)))['completed_phases']

    no_clips = catalog_with()
    del no_clips['entries'][0]['videos'][0]['selected_clips']
    write_json(tmp_path / 'material-catalog.json', no_clips)
    assert '5-material-catalog' in parse_result(run_cli(str(tmp_path)))['completed_phases']

    # 2. Repeating bare IDs across entries and any non-empty target clip file pass Phase 5.
    catalog = catalog_with()
    other = json.loads(json.dumps(catalog['entries'][0]))
    other['slug'] = 'other'
    other['videos'][0]['selected_clips'][0]['clip_path'] = CLIP_PATH
    catalog['entries'].append(other)
    write_json(tmp_path / 'material-catalog.json', catalog)
    (tmp_path / CLIP_PATH).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / CLIP_PATH).write_bytes(b'not a probed video')
    assert '5-material-catalog' in parse_result(run_cli(str(tmp_path)))['completed_phases']


# --- phase 5 product: every selected clip is cut to a silent file (cut-clips.py) -------


def catalog_clip(catalog: dict) -> dict:
    return catalog['entries'][0]['videos'][0]['selected_clips'][0]


def test_corrupt_or_missing_catalog_clips_fall_back_to_phase_5(tmp_path: Path):
    outside = tmp_path / 'outside.mp4'
    outside.write_bytes(b'\0' * 128)
    ws = tmp_path / 'ws'
    complete_through_catalog(ws)

    # Empty or missing clip file on disk
    (ws / CLIP_PATH).write_bytes(b'')
    empty_res = parse_result(run_cli(str(ws)))
    assert 'material-catalog.json' in empty_res['corrupt_products']
    assert CLIP_PATH in empty_res['next_phase']['problems']['material-catalog.json']

    (ws / CLIP_PATH).unlink()
    missing_res = parse_result(run_cli(str(ws)))
    assert missing_res['next_phase']['id'] == '5-material-catalog'
    assert 'material-catalog.json' in missing_res['corrupt_products']
    assert 'material-catalog.json' not in missing_res['missing_products']
    assert 'cut-clips' in missing_res['next_phase']['problems']['material-catalog.json']

    write_clip(ws / CLIP_PATH)
    no_path = catalog_with()
    del catalog_clip(no_path)['clip_path']
    non_str = catalog_with()
    catalog_clip(non_str)['clip_path'] = 7
    not_obj = catalog_with()
    not_obj['entries'][0]['videos'][0]['selected_clips'] = ['12.0-18.5']
    mismatched = catalog_with()
    catalog_clip(mismatched)['start'] = 13.0

    cases = [
        (no_path, ('vid_001', 'selected_clips[0]', 'clip_path', 'cut-clips')),
        (non_str, ('vid_001', 'clip_path')),
        (not_obj, ('vid_001', 'selected_clips[0]')),
        (mismatched, ('current window', 'cut-clips')),
    ]
    for bad_path in ('../outside.mp4', 'clips/../../outside.mp4', '/etc/hosts', 'clips'):
        escaped = catalog_with()
        catalog_clip(escaped)['clip_path'] = bad_path
        cases.append((escaped, (bad_path,)))

    for bad_catalog, parts in cases:
        write_json(ws / 'material-catalog.json', bad_catalog)
        result = parse_result(run_cli(str(ws)))
        assert result['next_phase']['id'] == '5-material-catalog'
        assert 'material-catalog.json' in result['corrupt_products']
        detail = result['next_phase']['problems']['material-catalog.json']
        for part in parts:
            assert part in detail, detail


# --- phase 6 products: script.txt + tts-lexicon.json + narration.txt ------------


def test_missing_or_corrupt_phase_6_products_fall_back_to_phase_6(tmp_path: Path):
    complete_through_script(tmp_path)

    for product in ('script.txt', 'narration.txt', 'narration-offsets.json', 'scene-plan.json'):
        saved = (tmp_path / product).read_bytes()
        (tmp_path / product).unlink()
        res = parse_result(run_cli(str(tmp_path)))
        assert res['next_phase']['id'] == '6-script-scene-plan'
        assert product in res['missing_products']
        (tmp_path / product).write_bytes(saved)

    saved_script = (tmp_path / 'script.txt').read_bytes()
    write_text(tmp_path / 'script.txt', '  \n')
    assert 'script.txt' in parse_result(run_cli(str(tmp_path)))['corrupt_products']
    (tmp_path / 'script.txt').write_bytes(saved_script)

    saved_lexicon = (tmp_path / 'tts-lexicon.json').read_bytes()
    for bad_lexicon in ('{"OpenHuman": ', '["OpenHuman"]', '{}'):
        write_text(tmp_path / 'tts-lexicon.json', bad_lexicon)
        assert 'tts-lexicon.json' in parse_result(run_cli(str(tmp_path)))['corrupt_products']
    (tmp_path / 'tts-lexicon.json').write_bytes(saved_lexicon)

    for bad_offsets in (
        ['segments'],
        {'version': 2, 'segments': []},
        {'segments': []},
        {'version': 1, 'segments': {}},
        {'version': 1},
    ):
        write_json(tmp_path / 'narration-offsets.json', bad_offsets)
        assert 'narration-offsets.json' in parse_result(run_cli(str(tmp_path)))['corrupt_products']
    write_text(tmp_path / 'narration-offsets.json', '{"version": 1, "segments": [')
    assert 'narration-offsets.json' in parse_result(run_cli(str(tmp_path)))['corrupt_products']


def test_script_length_tolerance_whitespace_and_duration_coupling(tmp_path: Path):
    complete_through_script(tmp_path)
    for chars in (2520, 1680):
        write_text(tmp_path / 'script.txt', script_of(chars))
        result = parse_result(run_cli(str(tmp_path)))
        assert result['next_phase']['id'] == '6-script-scene-plan'
        detail = result['next_phase']['problems']['script.txt']
        assert str(chars) in detail and '2100' in detail and '20.0%' in detail, detail

    for accepted_text in (
        script_of(2394),
        script_of(1806),
        '甲 ' * 1050 + '\n\n\n　　' + '乙\t' * 1050 + '\n\n',
    ):
        write_script(tmp_path, accepted_text)
        approve(tmp_path, 'script')
        assert '6-script-scene-plan' in parse_result(run_cli(str(tmp_path)))['completed_phases']

    # Numeric duration sets target (1 min -> 420 chars); invalid duration fails at Phase 1 first.
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'duration': 1})
    assert '420' in parse_result(run_cli(str(tmp_path)))['next_phase']['problems']['script.txt']

    write_json(tmp_path / 'inputs.json', {**INPUTS, 'duration': 'soon'})
    bad_dur = parse_result(run_cli(str(tmp_path)))
    assert bad_dur['next_phase']['id'] == '1-gather-inputs'
    assert bad_dur['corrupt_products'] == ['inputs.json']


# --- phase 6 product: scene-plan.json -------------------------------------------

THREE_PARAGRAPH_SCRIPT = '甲' * 700 + '\n\n' + '乙' * 700 + '\n\n' + '丙' * 700 + '\n'  # 2100 characters


def scene(scene_id: str, paragraphs, candidates=()) -> dict:
    return {
        'scene_id': scene_id,
        'paragraphs': paragraphs,
        'intent': scene_id,
        'content_plan': f'{scene_id} 的内容与演绎方式',
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


def test_scene_plan_schema_planning_fields_and_removed_fields(tmp_path: Path):
    complete_through_script(tmp_path)

    for raw in ('{"scene_id": ', json.dumps([{'scene_id': 'scene_1'}])):
        write_text(tmp_path / 'scene-plan.json', raw)
        res = parse_result(run_cli(str(tmp_path)))
        assert res['next_phase']['id'] == '6-script-scene-plan'
        assert 'scene-plan.json' in res['corrupt_products']

    for field in ('intent', 'content_plan'):
        missing = scene('s1', [1, 2])
        del missing[field]
        write_json(tmp_path / 'scene-plan.json', [missing])
        assert field in parse_result(run_cli(str(tmp_path)))['next_phase']['problems']['scene-plan.json']

        for bad_val in (None, '', '   ', 7):
            invalid = scene('s1', [1, 2])
            invalid[field] = bad_val
            write_json(tmp_path / 'scene-plan.json', [invalid])
            detail = parse_result(run_cli(str(tmp_path)))['next_phase']['problems']['scene-plan.json']
            assert f'scene 0 {field}' in detail, detail

    for removed, value in (
        ('template_scene', 'project-cover'),
        ('pattern_hints', []),
        ('beats', []),
    ):
        planned = scene('s1', [1, 2])
        planned[removed] = value
        write_json(tmp_path / 'scene-plan.json', [planned])
        detail = parse_result(run_cli(str(tmp_path)))['next_phase']['problems']['scene-plan.json']
        assert removed in detail and 'scene 0' in detail, detail


def test_scene_plan_paragraph_coverage_types_and_missing_script(tmp_path: Path):
    _, detail = scene_plan_problem(tmp_path, [scene('s1', [1]), scene('s2', [2])], script=THREE_PARAGRAPH_SCRIPT)
    assert 'missing paragraphs [3]' in detail

    _, detail = scene_plan_problem(tmp_path, [scene('s1', [1, 2]), scene('s2', [3, 4])])
    assert 'out-of-range paragraphs [3, 4]' in detail and 'missing' not in detail

    _, detail = scene_plan_problem(tmp_path, [scene('s1', [1, 5])], script=THREE_PARAGRAPH_SCRIPT)
    assert 'missing paragraphs [2, 3]' in detail and 'out-of-range paragraphs [5]' in detail

    _, detail = scene_plan_problem(tmp_path, [scene('s1', [0, 1, 2])])
    assert 'out-of-range paragraphs [0]' in detail

    for bad_paragraphs in (['1', '2'], [1.5, 2], [True, 2], [None, 1, 2]):
        write_json(tmp_path / 'scene-plan.json', [scene('s1', bad_paragraphs)])
        bad_detail = parse_result(run_cli(str(tmp_path)))['next_phase']['problems']['scene-plan.json']
        assert 'scene 0' in bad_detail and 'integer' in bad_detail

    # Scenes may share a paragraph.
    shared_res, shared_detail = scene_plan_problem(
        tmp_path, [scene('s1', [1, 2]), scene('s2', [2])], approve_script=True
    )
    assert shared_detail is None and '6-script-scene-plan' in shared_res['completed_phases']

    # Without script.txt: valid scene-plan is not blamed, while non-integer paragraph types still fail.
    (tmp_path / 'script.txt').unlink()
    assert set(parse_result(run_cli(str(tmp_path)))['next_phase']['problems']) == {'script.txt'}
    write_json(tmp_path / 'scene-plan.json', [scene('s1', ['1', 2.5])])
    assert 'integer' in parse_result(run_cli(str(tmp_path)))['next_phase']['problems']['scene-plan.json']


# --- phase 6 check: scene-plan material refs resolve in the catalog ---------------


def candidates(*refs) -> list[dict]:
    return [{'ref': ref, 'score': 7, 'reason': 'test'} for ref in refs]


def test_scene_plan_accepts_all_valid_ref_forms_and_slug_scoping(tmp_path: Path):
    catalog = catalog_with()
    other = json.loads(json.dumps(catalog['entries'][0]))
    other['slug'] = 'other'
    other['videos'] = []
    catalog['entries'].append(other)

    valid_refs = (
        'example/img_001',
        'other/img_001',
        'example/vid_001',
        'example/vid_001:12.0-18.5',
        'example/vid_001:12-18.5',
        'example/vid_001:12.005-18.495',
    )
    result, detail = scene_plan_problem(
        tmp_path,
        [scene('s1', [1, 2], candidates(*valid_refs))],
        approve_script=True,
        catalog=catalog,
    )
    assert detail is None
    assert '6-script-scene-plan' in result['completed_phases']
    assert 'approved_at' in read_approvals(tmp_path)['gates']['script']


def test_scene_plan_collects_every_invalid_material_and_clip_ref(tmp_path: Path):
    catalog = catalog_with()
    other = json.loads(json.dumps(catalog['entries'][0]))
    other['slug'] = 'other'
    other_clip = other['videos'][0]['selected_clips'][0]
    other_clip['start'], other_clip['end'] = 20.0, 22.0
    other_clip['clip_path'] = 'clips/vid_001_20.00-22.00.mp4'
    catalog['entries'].append(other)
    write_clip(tmp_path / other_clip['clip_path'])

    valid_refs = ('example/img_001', 'example/vid_001', 'other/vid_001', 'other/vid_001:20.0-22.0')
    invalid_refs = (
        'missing/img_001',
        'example/img_999',
        'img_001',
        'other/vid_001:12.0-18.5',
        'example/vid_001:13.0-18.5',
        'example/vid_001:12.0-18.6',
        'example/vid_999:12.0-18.5',
        'example/img_001:12.0-18.5',
        'example/vid_001:abc-def',
        'example/vid_001:12.0',
        'example/vid_001:12.0-18.5-20',
        'example/vid_001:',
        ':12.0-18.5',
        'example/vid_001:12.0 - 18.5',
        'example/vid_001: 12-18.5',
        'example/vid_001:+12-18.5',
        'example/vid_001:1_2-18.5',
    )
    result, detail = scene_plan_problem(
        tmp_path,
        [
            scene('s1', [1], candidates(*valid_refs, *invalid_refs[:8])),
            scene('s2', [2], candidates(*invalid_refs[8:])),
        ],
        catalog=catalog,
    )
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert 'scene-plan.json' in result['corrupt_products']
    for bad_ref in invalid_refs:
        assert repr(bad_ref) in detail, (bad_ref, detail)
    for ok_ref in valid_refs:
        assert repr(ok_ref) not in detail, (ok_ref, detail)


def test_scene_plan_malformed_candidates_no_catalog_mode_and_unusable_catalog(tmp_path: Path):
    complete_through_script(tmp_path)
    for bad in ('img_001', ['img_001'], {'ref': 'img_001'}, [{'score': 8}], [{'ref': ''}], [{'ref': 7}]):
        planned = scene('s1', [1, 2])
        planned['material_candidates'] = bad
        write_json(tmp_path / 'scene-plan.json', [planned])
        detail = parse_result(run_cli(str(tmp_path)))['next_phase']['problems']['scene-plan.json']
        assert 'scene 0' in detail and 'material_candidates' in detail, detail

    # Unusable or missing catalog stops at Phase 5 without blaming scene-plan.json.
    write_json(tmp_path / 'scene-plan.json', SCENE_PLAN)
    write_json(tmp_path / 'material-catalog.json', catalog_with(semantic_description=''))
    corrupt_cat = parse_result(run_cli(str(tmp_path)))
    assert corrupt_cat['next_phase']['id'] == '5-material-catalog'
    assert 'scene-plan.json' not in corrupt_cat['corrupt_products']

    (tmp_path / 'material-catalog.json').unlink()
    missing_cat = parse_result(run_cli(str(tmp_path)))
    assert missing_cat['next_phase']['id'] == '5-material-catalog'
    assert 'scene-plan.json' not in missing_cat['corrupt_products']

    # Without a catalog phase (fetch_materials=False), candidates must be empty.
    no_cat_ws = tmp_path / 'no_cat'
    _, bad_no_cat = scene_plan_problem(
        no_cat_ws, [scene('s1', [1, 2], candidates('example/img_001'))], fetch_materials=False
    )
    assert 'fetch_materials' in bad_no_cat and "'example/img_001'" in bad_no_cat
    ok_res, ok_detail = scene_plan_problem(
        no_cat_ws, [scene('s1', [1, 2])], fetch_materials=False, approve_script=True
    )
    assert ok_detail is None and '6-script-scene-plan' in ok_res['completed_phases']


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


def test_missing_or_corrupt_transcript_falls_back_to_phase_7(tmp_path: Path):
    complete_through_voice_subtitles(tmp_path)
    write_json(tmp_path / 'transcribe' / 'transcript.json', [{'begin': 0}])  # 缺字段
    corrupt = parse_result(run_cli(str(tmp_path)))
    assert corrupt['next_phase']['id'] == '7-voice-subtitles'
    assert 'transcribe/transcript.json' in corrupt['corrupt_products']

    (tmp_path / 'transcribe' / 'transcript.json').unlink()
    missing = parse_result(run_cli(str(tmp_path)))
    assert missing['next_phase']['id'] == '7-voice-subtitles'
    assert 'transcribe/transcript.json' in missing['missing_products']


def test_missing_or_corrupt_subtitle_units_falls_back_to_phase_8(tmp_path: Path):
    complete_through_composition(tmp_path)
    write_json(tmp_path / 'composition' / 'assets' / 'subtitle-units.json', {'units': []})
    corrupt = parse_result(run_cli(str(tmp_path)))
    assert corrupt['next_phase']['id'] == '8-composition'
    assert 'composition/assets/subtitle-units.json' in corrupt['corrupt_products']

    (tmp_path / 'composition' / 'assets' / 'subtitle-units.json').unlink()
    missing = parse_result(run_cli(str(tmp_path)))
    # 最终字幕依赖 layout，所以它属于 Phase 8，而不是 Phase 7。
    assert missing['next_phase']['id'] == '8-composition'
    assert 'composition/assets/subtitle-units.json' in missing['missing_products']
    assert '7-voice-subtitles' in missing['completed_phases']


def test_missing_or_corrupt_timeline_falls_back_to_phase_7(tmp_path: Path):
    complete_through_voice_subtitles(tmp_path)
    for writer in (
        lambda p: write_json(p, {'paragraphs': []}),
        lambda p: write_text(p, '{"paragraphs": ['),
    ):
        writer(tmp_path / 'transcribe' / 'timeline.json')
        corrupt = parse_result(run_cli(str(tmp_path)))
        assert corrupt['next_phase']['id'] == '7-voice-subtitles'
        assert 'transcribe/timeline.json' in corrupt['corrupt_products']

    (tmp_path / 'transcribe' / 'timeline.json').unlink()
    missing = parse_result(run_cli(str(tmp_path)))
    assert missing['next_phase']['id'] == '7-voice-subtitles'
    assert 'transcribe/timeline.json' in missing['missing_products']
    assert '7-voice-subtitles' not in missing['completed_phases']


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


def test_missing_or_blank_storyboard_falls_back_to_phase_8(tmp_path: Path):
    complete_through_composition(tmp_path)
    write_text(tmp_path / 'composition' / 'storyboard.md', ' \n')
    blank = parse_result(run_cli(str(tmp_path)))
    assert blank['next_phase']['id'] == '8-composition'
    assert 'composition/storyboard.md' in blank['corrupt_products']

    (tmp_path / 'composition' / 'storyboard.md').unlink()
    missing = parse_result(run_cli(str(tmp_path)))
    assert missing['next_phase']['id'] == '8-composition'
    assert 'composition/storyboard.md' in missing['missing_products']


def test_missing_empty_hidden_only_or_non_dir_compositions_falls_back_to_phase_8(tmp_path: Path):
    complete_through_composition(tmp_path)
    comp_dir = tmp_path / 'composition' / 'compositions'
    (comp_dir / 'scene_1.html').unlink()
    empty = parse_result(run_cli(str(tmp_path)))
    assert empty['next_phase']['id'] == '8-composition'
    assert 'composition/compositions' in empty['corrupt_products']
    assert 'no files' in empty['next_phase']['problems']['composition/compositions']

    hidden = comp_dir / '.DS_Store'
    write_text(hidden, 'junk')
    assert 'composition/compositions' in parse_result(run_cli(str(tmp_path)))['corrupt_products']

    hidden.unlink()
    comp_dir.rmdir()
    missing = parse_result(run_cli(str(tmp_path)))
    assert missing['next_phase']['id'] == '8-composition'
    assert 'composition/compositions' in missing['missing_products']

    write_text(comp_dir, 'not a directory')
    assert 'composition/compositions' in parse_result(run_cli(str(tmp_path)))['corrupt_products']


def test_compositions_dir_with_a_nested_file_is_accepted(tmp_path: Path):
    complete_through_composition(tmp_path)
    (tmp_path / 'composition' / 'compositions' / 'scene_1.html').unlink()
    write_text(tmp_path / 'composition' / 'compositions' / 'scene_1' / 'index.html', '<template></template>')
    # 内容变了需要 composition agent 重跑检查并保存新报告，但状态脚本只验收
    # 报告数据本身：一份结论为 pass 的报告不因为没有源哈希而被判不合格。
    write_json(tmp_path / 'composition' / 'check-composition.json', pass_report(tmp_path))
    result = parse_result(run_cli(str(tmp_path)))
    assert '8-composition' in result['completed_phases']


def test_missing_failing_or_malformed_check_composition_report_falls_back_to_phase_8(tmp_path: Path):
    complete_through_composition(tmp_path)
    report_path = tmp_path / 'composition' / 'check-composition.json'

    write_json(
        report_path,
        {'success': True, 'verdict': 'fail', 'findings': [{'scene_id': 's1', 'check': 'overflow'}]},
    )
    failing = parse_result(run_cli(str(tmp_path)))
    assert failing['next_phase']['id'] == '8-composition'
    assert 'composition/check-composition.json' in failing['corrupt_products']
    assert "'fail'" in failing['next_phase']['problems']['composition/check-composition.json']

    for bad_report in (['pass'], {'success': True}, {'verdict': 'PASS'}):
        write_json(report_path, bad_report)
        assert 'composition/check-composition.json' in parse_result(run_cli(str(tmp_path)))['corrupt_products']

    write_text(report_path, '{"verdict": ')
    assert 'composition/check-composition.json' in parse_result(run_cli(str(tmp_path)))['corrupt_products']

    report_path.unlink()
    missing = parse_result(run_cli(str(tmp_path)))
    assert missing['next_phase']['id'] == '8-composition'
    assert 'composition/check-composition.json' in missing['missing_products']


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
        '9-check',
        '10-mix',
    ]
    assert result['next_phase'] is None
    assert result['missing_products'] == []
    assert result['corrupt_products'] == []


# --- conditional phases ---------------------------------------------------------


def test_paper_parse_progression_and_manifest_version_requirements(tmp_path: Path):
    complete_through_inputs(tmp_path, input_mode='paper')
    initial = parse_result(run_cli(str(tmp_path)))
    assert initial['next_phase']['id'] == '2-paper-parse'
    assert initial['next_phase']['doc'] == 'references/phases/02-paper-parse.md'

    # Metadata without manifest entry stays at Phase 2.
    write_json(tmp_path / 'harvest_page' / 'main-paper' / 'metadata.json', PAPER_METADATA)
    no_manifest = parse_result(run_cli(str(tmp_path)))
    assert no_manifest['next_phase']['id'] == '2-paper-parse'
    assert 'harvest_page/manifest.json' in no_manifest['missing_products']

    # Manifest without main-paper entry is corrupt at Phase 2.
    write_json(
        tmp_path / 'harvest_page' / 'manifest.json',
        {'version': 2, 'entries': [{'slug': 'unrelated', 'images': [], 'videos': []}]},
    )
    wrong_entry = parse_result(run_cli(str(tmp_path)))
    assert wrong_entry['next_phase']['id'] == '2-paper-parse'
    assert 'main-paper' in wrong_entry['next_phase']['problems']['harvest_page/manifest.json']

    # Valid main-paper entry completes Phase 2; without harvest_batches, Phase 4 stays incomplete when fetching.
    write_json(tmp_path / 'harvest_page' / 'manifest.json', {'version': 2, 'entries': [PAPER_ENTRY]})
    write_text(tmp_path / 'harvest_page' / 'main-paper' / 'full.md', '# paper\n')
    after_parse = parse_result(run_cli(str(tmp_path)))
    assert '2-paper-parse' in after_parse['completed_phases']
    assert after_parse['next_phase']['id'] == '3-research'

    write_text(tmp_path / 'research-brief.md', RESEARCH_BRIEF)
    need_harvest = parse_result(run_cli(str(tmp_path)))
    assert need_harvest['next_phase']['id'] == '4-material-harvest'

    # Old or non-v2 manifest versions are rejected at Phase 4.
    web_ws = tmp_path / 'web_ws'
    complete_through_catalog(web_ws)
    for bad_version in (None, 1, 3):
        manifest = json.loads((web_ws / 'harvest_page/manifest.json').read_text(encoding='utf-8'))
        if bad_version is None:
            manifest.pop('version', None)
        else:
            manifest['version'] = bad_version
        write_json(web_ws / 'harvest_page/manifest.json', manifest)
        bad_ver_res = parse_result(run_cli(str(web_ws)))
        assert bad_ver_res['next_phase']['id'] == '4-material-harvest'
        assert 'version' in bad_ver_res['next_phase']['problems']['harvest_page/manifest.json']


def test_conditional_material_phases_by_mode_and_fetch_flag(tmp_path: Path):
    # Standard + fetch_materials=False skips Phases 4 & 5 through full run.
    no_fetch = tmp_path / 'no_fetch'
    complete_through_research(no_fetch, fetch_materials=False)
    mid = parse_result(run_cli(str(no_fetch)))
    assert mid['skipped_phases'] == ['2-paper-parse', '4-material-harvest', '5-material-catalog']
    assert mid['next_phase']['id'] == '6-script-scene-plan'

    complete_all(no_fetch, fetch_materials=False)
    done_no_fetch = parse_result(run_cli(str(no_fetch)))
    assert done_no_fetch['next_phase'] is None
    assert not {'4-material-harvest', '5-material-catalog'} & set(done_no_fetch['completed_phases'])

    # Paper + fetch_materials=False skips Phase 4 but builds and validates Phase 5 catalog.
    paper_ws = tmp_path / 'paper'
    complete_through_harvest(paper_ws, input_mode='paper', fetch_materials=False)
    paper_mid = parse_result(run_cli(str(paper_ws)))
    assert '4-material-harvest' in paper_mid['skipped_phases']
    assert paper_mid['next_phase']['id'] == '5-material-catalog'

    _, bad_ref = scene_plan_problem(
        paper_ws, [scene('s1', [1, 2], candidates('main-paper/nope_1'))],
        input_mode='paper', fetch_materials=False,
    )
    assert "'main-paper/nope_1'" in bad_ref
    ok_res, ok_detail = scene_plan_problem(
        paper_ws, [scene('s1', [1, 2], candidates('main-paper/img_001'))],
        input_mode='paper', fetch_materials=False, approve_script=True,
    )
    assert ok_detail is None and '6-script-scene-plan' in ok_res['completed_phases']

    complete_all(paper_ws, input_mode='paper', fetch_materials=False)
    paper_done = parse_result(run_cli(str(paper_ws)))
    assert paper_done['next_phase'] is None
    assert paper_done['skipped_phases'] == ['4-material-harvest']
    assert '5-material-catalog' in paper_done['completed_phases']


# --- inputs.json validation -----------------------------------------------------


def test_inputs_json_validation_defaults_and_legacy_design_preservation(tmp_path: Path):
    # Unreadable inputs.json falls back to Phase 1 without skipping fetch/catalog.
    write_text(tmp_path / 'inputs.json', 'not json {')
    unreadable = parse_result(run_cli(str(tmp_path)))
    assert unreadable['next_phase']['id'] == '1-gather-inputs'
    assert 'inputs.json' in unreadable['corrupt_products']
    assert not {'4-material-harvest', '5-material-catalog'} & set(unreadable['skipped_phases'])

    complete_through_research(tmp_path)
    missing_lang = dict(INPUTS)
    del missing_lang['language']
    write_json(tmp_path / 'inputs.json', missing_lang)
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['id'] == '1-gather-inputs'

    write_json(tmp_path / 'inputs.json', {**INPUTS, 'qa_level': 'exhaustive'})
    assert 'inputs.json' in parse_result(run_cli(str(tmp_path)))['corrupt_products']

    # Missing qa_level or missing/legacy design passes Phase 1 without mutating inputs.json.
    no_qa_or_design = {k: v for k, v in INPUTS.items() if k not in ('qa_level', 'design')}
    write_json(tmp_path / 'inputs.json', no_qa_or_design)
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['id'] == '4-material-harvest'

    write_json(tmp_path / 'inputs.json', {**INPUTS, 'design': 'moon'})
    before = (tmp_path / 'inputs.json').read_bytes()
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['id'] == '4-material-harvest'
    assert (tmp_path / 'inputs.json').read_bytes() == before

    for bad_bgm in ('none', 0, 1, None, []):
        write_json(tmp_path / 'inputs.json', {**INPUTS, 'bgm': bad_bgm})
        bgm_res = parse_result(run_cli(str(tmp_path)))
        assert bgm_res['next_phase']['id'] == '1-gather-inputs'
        assert 'bgm' in bgm_res['next_phase']['problems']['inputs.json']


def test_a_design_removed_from_the_library_is_rejected_at_phase_8_even_with_a_workspace_copy(tmp_path: Path):
    """库里已删除的 design 不能通过工作区历史副本通过 Phase 8 的 design.json 验收。"""
    complete_all(tmp_path)
    copy = tmp_path / 'modules' / 'designs' / 'moon'
    copy.mkdir(parents=True)
    (copy / 'moon.md').write_text((REPO_ROOT / 'modules/designs/default/default.md').read_text(encoding='utf-8'), encoding='utf-8')
    preset = video_contract.load_design_preset(REPO_ROOT, 'default')
    write_json(tmp_path / 'composition' / 'design.json', {
        'version': 1,
        'source': 'preset',
        'preset': 'moon',
        'tokens': preset['tokens'],
        'min_font_px': preset['min_font_px'],
    })

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '8-composition'
    assert 'composition/design.json' in result['corrupt_products']
    assert 'preset must be a registered design' in result['next_phase']['problems']['composition/design.json']
    assert (copy / 'moon.md').is_file()


def test_duration_accepts_minute_forms_and_rejects_non_minute_values(tmp_path: Path):
    complete_through_research(tmp_path)
    for valid in (5, 7.5, '5min', ' 10 分钟', '3.5', '5 minutes', '2 mins', '4分'):
        write_json(tmp_path / 'inputs.json', {**INPUTS, 'duration': valid})
        res = parse_result(run_cli(str(tmp_path)))
        assert 'inputs.json' not in res['corrupt_products'], valid
        assert res['next_phase']['id'] == '4-material-harvest', valid

    for invalid in ('five minutes', '', 'min5', 0, -5, '0min', True, None, [5], '90s', '30秒', '1h', '3-5 min', '5 min left'):
        write_json(tmp_path / 'inputs.json', {**INPUTS, 'duration': invalid})
        res = parse_result(run_cli(str(tmp_path)))
        assert res['next_phase']['id'] == '1-gather-inputs', invalid
        detail = res['next_phase']['problems']['inputs.json']
        assert 'duration' in detail and '分钟' in detail, invalid


# --- phase 9 (check) & phase 10 (mix): qa/qa-report.json gates final_with_bgm.mp4 ---


def test_phase_9_check_and_phase_10_mix_progression_and_bgm_flag(tmp_path: Path):
    complete_through_composition(tmp_path)
    qa_path = tmp_path / 'qa' / 'qa-report.json'

    missing = parse_result(run_cli(str(tmp_path)))
    assert missing['next_phase']['id'] == '9-check'
    assert missing['next_phase']['doc'] == 'references/phases/09-check.md'
    assert missing['missing_products'] == ['qa/qa-report.json']
    assert statuses(missing)['10-mix'] == 'pending'

    for bad_qa in (
        {'findings': [{'scene_id': 's1', 'check': 'black_screen', 'issue': 'black', 'frame': None}], 'verdict': 'fail'},
        {'findings': [], 'verdict': 'pass', 'qa_level': 'standard'},
        {'findings': [{'scene_id': 's1', 'check': 'freeze', 'issue': 'frozen'}], 'verdict': 'pass'},
    ):
        write_json(qa_path, bad_qa)
        res = parse_result(run_cli(str(tmp_path)))
        assert res['next_phase']['id'] == '9-check'
        assert 'qa/qa-report.json' in res['corrupt_products']
        assert statuses(res)['10-mix'] == 'pending'

    # Passing or handed_off qa-report completes Phase 9 and advances to Phase 10 when bgm is enabled.
    for ok_qa in (
        {'findings': [], 'verdict': 'pass'},
        {'findings': [{'scene_id': 's1', 'check': 'freeze', 'issue': 'frozen', 'frame': 'sheet_001'}], 'verdict': 'handed_off'},
    ):
        write_json(qa_path, ok_qa)
        advanced = parse_result(run_cli(str(tmp_path)))
        assert '9-check' in advanced['completed_phases']
        assert advanced['next_phase']['id'] == '10-mix'
        assert advanced['next_phase']['doc'] == 'references/phases/10-mix.md'
        assert advanced['missing_products'] == ['composition/renders/final_with_bgm.mp4']

    # bgm=False skips Phase 10 and completes immediately after Phase 9; redoing skipped 10-mix is refused.
    no_bgm_ws = tmp_path / 'no_bgm'
    complete_through_check(no_bgm_ws, bgm=False)
    no_bgm = parse_result(run_cli(str(no_bgm_ws)))
    assert '9-check' in no_bgm['completed_phases']
    assert '10-mix' in no_bgm['skipped_phases']
    assert no_bgm['next_phase'] is None
    assert not (no_bgm_ws / 'composition' / 'renders' / 'final_with_bgm.mp4').exists()
    redo_proc = run_cli(str(no_bgm_ws), '--redo', '10-mix', '--reason', '换音乐')
    assert redo_proc.returncode == 1 and 'skipped' in parse_result(redo_proc)['error']


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
    '9-check',
    '10-mix',
]


def statuses(result: dict) -> dict[str, str]:
    return {phase['id']: phase['status'] for phase in result['phases']}


def test_phase_statuses_mark_later_phases_pending_without_inspecting_them(tmp_path: Path):
    complete_all(tmp_path)
    done = parse_result(run_cli(str(tmp_path)))
    assert done['next_phase'] is None and done['pending_phases'] == []
    assert statuses(done) == {**{phase_id: 'completed' for phase_id in PHASE_IDS}, '2-paper-parse': 'skipped'}

    # Corrupt Phase 3 marks later phases pending.
    write_text(tmp_path / 'research-brief.md', '   \n')
    corrupt_res = parse_result(run_cli(str(tmp_path)))
    assert corrupt_res['next_phase']['reason'] == 'corrupt'
    assert statuses(corrupt_res)['3-research'] == 'corrupt'
    assert corrupt_res['completed_phases'] == ['1-gather-inputs']

    # Missing Phase 3 leaves broken Phase 7 transcript uninspected.
    (tmp_path / 'research-brief.md').unlink()
    write_text(tmp_path / 'transcribe' / 'transcript.json', 'not json')
    missing_res = parse_result(run_cli(str(tmp_path)))
    assert missing_res['missing_products'] == ['research-brief.md']
    assert missing_res['corrupt_products'] == []
    assert missing_res['pending_phases'] == PHASE_IDS[3:]
    assert [phase['id'] for phase in missing_res['phases']] == PHASE_IDS
    assert statuses(missing_res) == {
        '1-gather-inputs': 'completed',
        '2-paper-parse': 'skipped',
        '3-research': 'missing',
        **{phase_id: 'pending' for phase_id in PHASE_IDS[3:]},
    }


def test_a_phase_with_both_missing_and_corrupt_products_is_corrupt(tmp_path: Path):
    complete_through_script(tmp_path)
    (tmp_path / 'script.txt').unlink()
    write_text(tmp_path / 'narration.txt', '')
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert result['next_phase']['reason'] == 'corrupt'
    assert statuses(result)['6-script-scene-plan'] == 'corrupt'


# --- 没有自动新鲜度追踪：上游改动不使任何阶段过期 -------------------------
#
# 状态脚本不比对文件哈希或修改时间。改了上游之后要不要重做、重做哪些阶段，
# 由主 agent 按已知修改范围显式登记（--redo）；这里验证脚本确实不从文件
# 变化推断任何失效，也不需要任何指纹状态文件。

EDITED_SCRIPT_TXT = '甲' * 1050 + '\n\n' + '丙' * 1050 + '\n'  # same length as SCRIPT_TXT, other content


def settle(ws: Path, **inputs_overrides) -> dict:
    """A complete workspace accepted by a first run."""
    complete_all(ws, **inputs_overrides)
    result = parse_result(run_cli(str(ws)))
    assert result['next_phase'] is None
    return result


def rewrite_voice_subtitles(ws: Path) -> None:
    """Phase 7 regenerated: same shape, other bytes."""
    write_audio(ws / 'voice_clone' / 'narration.mp3')
    write_json(ws / 'transcribe' / 'transcript.json', [{**TRANSCRIPT[0], 'text': '大家好呀。'}])
    write_json(ws / 'transcribe' / 'timeline.json', {**TIMELINE, 'total_s': 2.6})


def test_same_length_script_edit_and_phase_6_7_regeneration_keep_settled_workspace_current(tmp_path: Path):
    settle(tmp_path)

    # 1. 等长编辑不再由内容哈希识别。
    write_text(tmp_path / 'script.txt', EDITED_SCRIPT_TXT)
    assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None

    # 2. 重跑偏移表并批准后一切照常完成。
    write_script(tmp_path, EDITED_SCRIPT_TXT)
    approve(tmp_path, 'script')
    after_script = parse_result(run_cli(str(tmp_path)))
    assert after_script['next_phase'] is None
    assert after_script['completed_phases'] == [
        phase_id for phase_id in PHASE_IDS if phase_id != '2-paper-parse'
    ]

    # 3. 重跑 Phase 7 后下游也不会被自动登记重做。
    rewrite_voice_subtitles(tmp_path)
    after_voice = parse_result(run_cli(str(tmp_path)))
    assert statuses(after_voice)['7-voice-subtitles'] == 'completed'
    assert after_voice['next_phase'] is None


def test_non_gating_input_and_instruction_edits_do_not_invalidate_settled_workspace(tmp_path: Path):
    settle(tmp_path)

    write_json(tmp_path / 'inputs.json', {**INPUTS, 'layout': 'portrait'})
    layout_res = parse_result(run_cli(str(tmp_path)))
    assert layout_res['next_phase'] is None
    assert statuses(layout_res)['7-voice-subtitles'] == 'completed'

    write_json(tmp_path / 'inputs.json', {**INPUTS, 'qa_level': 'strict'})
    qa_res = parse_result(run_cli(str(tmp_path)))
    assert qa_res['next_phase'] is None and '9-check' in qa_res['completed_phases']

    for field, req in (('narration_requests', ['结尾不要 CTA']), ('composition_requests', ['不要人物区'])):
        write_json(tmp_path / 'inputs.json', {**INPUTS, field: req})
        assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None
        write_json(tmp_path / 'inputs.json', {**INPUTS, field: []})
        assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None
        without = dict(INPUTS)
        without.pop(field, None)
        write_json(tmp_path / 'inputs.json', without)
        assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None

    for name in ('narration-instructions.md', 'composition-instructions.md', 'style-prompt.md'):
        write_text(tmp_path / name, '旧要求\n')
    assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None

    write_text(tmp_path / 'catalog-instructions.md', '优先展示 UI 操作。')
    assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None
    write_text(tmp_path / 'catalog-instructions.md', '不要使用当前 img_001，只选择流程图。')
    assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None


def test_deleting_phase_6_products_makes_6_next_and_the_rest_pending_until_restored(tmp_path: Path):
    settle(tmp_path)
    phase_6 = ['script.txt', 'tts-lexicon.json', 'narration.txt', 'narration-offsets.json', 'scene-plan.json']
    saved = {name: (tmp_path / name).read_bytes() for name in phase_6}
    for name in phase_6:
        (tmp_path / name).unlink()

    result = parse_result(run_cli(str(tmp_path)))

    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert result['next_phase']['reason'] == 'missing'
    assert result['pending_phases'] == ['7-voice-subtitles', '8-composition', '9-check', '10-mix']
    assert result['completed_phases'] == ['1-gather-inputs', '3-research', '4-material-harvest', '5-material-catalog']

    # 相同的字节写回去：一切照旧。
    for name, data in saved.items():
        (tmp_path / name).write_bytes(data)
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase'] is None
    assert result['pending_phases'] == []


def test_changed_upstream_of_a_pending_phase_is_not_looked_at(tmp_path: Path):
    settle(tmp_path)
    (tmp_path / 'research-brief.md').unlink()
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'qa_level': 'strict'})
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '3-research'
    assert statuses(result)['9-check'] == 'pending'
    assert statuses(result)['10-mix'] == 'pending'


# --- phase 6 check: script.txt / narration.txt still match the offset table ---------
#
# make-narration records the character counts of the script.txt it read and the
# narration.txt it wrote. A script.txt edited afterwards without re-running it
# leaves a narration.txt and offset table that no longer belong together, which
# align-narration would only reject in Phase 7, after the TTS has already run.

MAKE_NARRATION = REPO_ROOT / 'scripts' / 'make-narration.py'


def offsets_problem(ws: Path) -> str:
    result = parse_result(run_cli(str(ws)))
    assert result['next_phase']['id'] == '6-script-scene-plan'
    assert result['next_phase']['reason'] == 'corrupt'
    assert 'narration-offsets.json' in result['corrupt_products']
    return result['next_phase']['problems']['narration-offsets.json']


def test_offsets_mismatch_and_non_integer_lengths_send_phase_6_back(tmp_path: Path):
    complete_through_script(tmp_path)
    saved_offsets = json.loads((tmp_path / 'narration-offsets.json').read_text(encoding='utf-8'))

    write_text(tmp_path / 'script.txt', '甲' * 1050 + '\n\n' + '乙' * 1055 + '\n')
    detail = offsets_problem(tmp_path)
    assert 'script_length' in detail and 'script.txt' in detail and '2103' in detail and '2108' in detail
    assert 'make-narration' in detail
    write_text(tmp_path / 'script.txt', SCRIPT_TXT)

    write_text(tmp_path / 'narration.txt', SCRIPT_TXT + '多出来的一句。\n')
    detail = offsets_problem(tmp_path)
    assert 'narration_length' in detail and 'narration.txt' in detail
    write_text(tmp_path / 'narration.txt', SCRIPT_TXT)

    write_json(tmp_path / 'narration-offsets.json', {**saved_offsets, 'segments': []})
    assert 'segments' in offsets_problem(tmp_path)

    for field in ('script_length', 'narration_length'):
        for value in ('missing', '2252', 2252.0, None, True):
            mutated = dict(saved_offsets)
            if value == 'missing':
                del mutated[field]
            else:
                mutated[field] = value
            write_json(tmp_path / 'narration-offsets.json', mutated)
            bad_detail = offsets_problem(tmp_path)
            assert field in bad_detail and 'integer' in bad_detail, bad_detail

    write_json(tmp_path / 'narration-offsets.json', saved_offsets)
    (tmp_path / 'narration.txt').unlink()
    assert set(parse_result(run_cli(str(tmp_path)))['next_phase']['problems']) == {'narration.txt'}


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


def test_missing_composition_design_is_a_phase_8_product(tmp_path: Path):
    settle(tmp_path)
    # Editing composition source after report does not auto-invalidate Phase 8.
    scene_html = tmp_path / 'composition' / 'compositions' / 'scene_1.html'
    scene_html.write_text(scene_html.read_text(encoding='utf-8') + '\n<!-- edited -->', encoding='utf-8')
    assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None

    (tmp_path / 'composition' / 'design.json').unlink()
    result = parse_result(run_cli(str(tmp_path)))
    assert result['next_phase']['id'] == '8-composition'
    assert 'composition/design.json' in result['missing_products']


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


def test_approving_research_records_the_confirmation_fact_and_completes_the_gate(tmp_path: Path):
    complete_through_research(tmp_path, approved=False, approval_gates=['research-brief'])

    result = approve(tmp_path, 'research-brief')

    assert '3-research' in result['completed_phases']
    assert result['next_phase']['id'] == '4-material-harvest'
    approvals = read_approvals(tmp_path)
    assert approvals['version'] == 1
    assert set(approvals['gates']) == {'research-brief'}
    approval = approvals['gates']['research-brief']
    # 确认事实与时间，不绑定文件哈希。
    assert set(approval) == {'approved_at'}
    datetime.fromisoformat(approval['approved_at'])
    # Approval is durable, not a one-shot transition in this invocation.
    assert parse_result(run_cli(str(tmp_path)))['next_phase']['id'] == '4-material-harvest'


def test_changing_an_approved_product_keeps_the_gate_until_an_explicit_redo(tmp_path: Path):
    # 确认不绑定文件哈希：编辑已确认的产物不会自动撤销确认……
    complete_through_research(tmp_path, approved=False, approval_gates=['research-brief'])
    approve(tmp_path, 'research-brief')
    write_text(tmp_path / 'research-brief.md', RESEARCH_BRIEF + '- another verified fact [source]\n')

    result = parse_result(run_cli(str(tmp_path)))

    assert '3-research' in result['completed_phases']
    assert result['next_phase']['id'] == '4-material-harvest'

    # ……但显式重做该阶段会撤销对应 gate 的旧确认。
    redo(tmp_path, '3-research', '事实需要重核')
    assert not (tmp_path / '.pipeline' / 'approvals.json').exists()


def test_script_gate_records_the_confirmation_fact(tmp_path: Path):
    complete_through_script(tmp_path, approved=False, approval_gates=['script'])
    waiting = parse_result(run_cli(str(tmp_path)))
    assert waiting['next_phase']['id'] == '6-script-scene-plan'
    assert waiting['next_phase']['reason'] == 'awaiting_approval'
    assert waiting['next_phase']['gate'] == 'script'
    assert waiting['next_phase']['instruction'] == (
        '把旁白和每个 scene 的 scene_id + intent + content_plan 摘要交给用户确认；确认后运行 '
        '`python3 scripts/pipeline-status.py <ws> --approve script`'
    )
    assert waiting['pending_phases'] == ['7-voice-subtitles', '8-composition', '9-check', '10-mix']

    result = approve(tmp_path, 'script')

    assert '6-script-scene-plan' in result['completed_phases']
    assert result['next_phase']['id'] == '7-voice-subtitles'
    approval = read_approvals(tmp_path)['gates']['script']
    assert set(approval) == {'approved_at'}


def test_changing_script_gate_products_after_approval_keeps_it_until_a_redo(tmp_path: Path):
    complete_through_script(tmp_path, approved=False, approval_gates=['script'])
    approve(tmp_path, 'script')
    write_json(tmp_path / 'scene-plan.json', [{**SCENE_PLAN[0], 'intent': '更新后的开场'}])

    result = parse_result(run_cli(str(tmp_path)))

    # 编辑不撤销确认；显式重做才会。
    assert '6-script-scene-plan' in result['completed_phases']

    redo(tmp_path, '6-script-scene-plan', '开场重写')
    rerequested = parse_result(run_cli(str(tmp_path)))
    assert rerequested['next_phase']['id'] == '6-script-scene-plan'
    assert rerequested['next_phase']['reason'] == 'redo'


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
    assert not (tmp_path / '.pipeline' / 'approvals.json').exists()


@pytest.mark.parametrize('record', [
    'not json',
    json.dumps({'version': 99, 'gates': {}}),
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


def test_invalid_approval_gates_are_corrupt_inputs(tmp_path: Path):
    for gates in (None, True, 'script', {}, ['unknown'], ['SCRIPT'], [1], [[]], [{}], ['script', 'script']):
        complete_through_inputs(tmp_path, approval_gates=gates)
        result = parse_result(run_cli(str(tmp_path)))
        assert result['next_phase']['id'] == '1-gather-inputs'
        assert result['next_phase']['reason'] == 'corrupt'
        assert 'approval_gates' in result['next_phase']['problems']['inputs.json']


def test_enabling_review_and_authorizing_auto_keep_existing_products(tmp_path: Path):
    settle(tmp_path)
    assert not (tmp_path / '.pipeline' / 'approvals.json').exists()
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'approval_gates': ['research-brief', 'script']})

    waiting = parse_result(run_cli(str(tmp_path)))
    assert waiting['next_phase']['gate'] == 'research-brief'
    assert waiting['next_phase']['reason'] == 'awaiting_approval'
    assert waiting['pending_phases'] == PHASE_IDS[3:]

    # Approving this draft must not cancel the separate request to review the script.
    waiting = approve(tmp_path, 'research-brief')
    assert waiting['next_phase']['gate'] == 'script'
    assert waiting['next_phase']['reason'] == 'awaiting_approval'
    assert waiting['pending_phases'] == PHASE_IDS[6:]
    approvals_before_auto = read_approvals(tmp_path)

    # Explicit user authorization to finish automatically changes policy, not approvals.
    write_json(tmp_path / 'inputs.json', {**INPUTS, 'approval_gates': []})
    for _ in range(2):
        resumed = parse_result(run_cli(str(tmp_path)))
        assert resumed['approval_gates'] == []
        assert resumed['next_phase'] is None
    assert read_approvals(tmp_path) == approvals_before_auto
    assert set(approvals_before_auto['gates']) == {'research-brief'}


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
    # 没有自动失效：下游阶段保持完成，直到主 agent 按已知修改范围显式登记重做。
    assert result['next_phase'] is None
    follow_up = redo(tmp_path, '7-voice-subtitles', '旁白已改，需要重新对齐')
    assert follow_up['next_phase']['id'] == '7-voice-subtitles'
    assert follow_up['next_phase']['reason'] == 'redo'


def test_finishing_phase_9_and_phase_10_redos_keep_independent_completion(tmp_path: Path):
    # --finish 不要求产物字节与上次不同；重做 10-mix 时 9-check 保持完成。
    settle(tmp_path)
    redo(tmp_path, '9-check', '重新核对 QA 结论')
    product = tmp_path / 'qa/qa-report.json'
    product.write_bytes(product.read_bytes())

    proc = finish(tmp_path, '9-check')
    assert proc.returncode == 0, proc.stderr
    result = parse_result(proc)
    assert statuses(result)['9-check'] == 'completed'
    assert statuses(result)['10-mix'] == 'completed'
    assert result['next_phase'] is None

    mix_redo = redo(tmp_path, '10-mix', '调低背景音乐音量')
    assert statuses(mix_redo)['9-check'] == 'completed'
    assert mix_redo['next_phase']['id'] == '10-mix'
    assert mix_redo['next_phase']['reason'] == 'redo'

    mix_done = finish(tmp_path, '10-mix')
    assert mix_done.returncode == 0, mix_done.stderr
    assert parse_result(mix_done)['next_phase'] is None


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


def test_approve_does_not_bypass_a_pending_redo(tmp_path: Path):
    complete_through_research(tmp_path, approved=False, approval_gates=['research-brief'])
    redo(tmp_path, '3-research')

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


def test_redo_and_finish_usage_errors_exit_2(tmp_path: Path):
    settle(tmp_path)
    for args in (
        ('--redo',),
        ('--redo', '6-script-scene-plan'),
        ('--redo', '6-script-scene-plan', '--reason', '   '),
        ('--reason', '重做'),
        ('--finish',),
        ('--redo', '6-script-scene-plan', '--reason', 'x', '--finish', '6-script-scene-plan'),
        ('--redo', '10-publish', '--reason', 'x'),
        ('--finish', '10-publish'),
    ):
        proc = run_cli(str(tmp_path), *args)
        assert proc.returncode == 2, args
        assert parse_result(proc)['success'] is False


# --- optional material_search_requests: a platform search the user asked for ------


def test_adding_a_material_search_request_requires_an_explicit_redo(tmp_path: Path):
    settle(tmp_path)

    write_json(
        tmp_path / 'inputs.json',
        {**INPUTS, 'material_search_requests': ['去 Google 图片搜 Roblox 的界面截图']},
    )
    result = parse_result(run_cli(str(tmp_path)))

    # Recording the request alone changes nothing: whether a redo is needed is not
    # inferred from the files or the inputs, only from an explicit request.
    assert result['next_phase'] is None

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


def test_absent_or_legacy_global_template_values_never_gate_any_phase(tmp_path: Path):
    # Phase 1 without template passes.
    phase1_ws = tmp_path / 'phase1'
    write_json(phase1_ws / 'inputs.json', {k: v for k, v in INPUTS.items() if k != 'template'})
    phase1_res = parse_result(run_cli(str(phase1_ws)))
    assert phase1_res['completed_phases'] == ['1-gather-inputs']
    assert phase1_res['next_phase']['id'] == '3-research'

    # Through Phase 7: absent template or any legacy value never creates inputs.json#template problem.
    ws = tmp_path / 'ws'
    complete_through_voice_subtitles(ws)
    for sentinel in ('__absent__', 'github/../escape', '../escape', '', 3, {}, []):
        inputs = json.loads((ws / 'inputs.json').read_text(encoding='utf-8'))
        if sentinel == '__absent__':
            inputs.pop('template', None)
        else:
            inputs['template'] = sentinel
        write_json(ws / 'inputs.json', inputs)
        result = parse_result(run_cli(str(ws)))
        assert '1-gather-inputs' in result['completed_phases']
        assert '7-voice-subtitles' in result['completed_phases']
        assert result['next_phase']['id'] == '8-composition'
        assert 'inputs.json#template' not in result['next_phase']['problems']


def test_request_lists_validation_at_phase_1(tmp_path: Path):
    for value in (['语气更口语'], []):
        complete_through_inputs(
            tmp_path,
            narration_requests=value,
            composition_requests=value,
            material_search_requests=value,
        )
        ok = parse_result(run_cli(str(tmp_path)))
        assert ok['completed_phases'] == ['1-gather-inputs']
        assert ok['next_phase']['id'] == '3-research'

    for field in ('narration_requests', 'composition_requests', 'material_search_requests'):
        for bad_val in ('语气更口语', None, [''], ['  '], ['ok', 3]):
            complete_through_inputs(tmp_path, **{field: bad_val})
            res = parse_result(run_cli(str(tmp_path)))
            assert res['next_phase']['id'] == '1-gather-inputs'
            assert field in res['next_phase']['problems']['inputs.json']


# --- catalog 的必用素材（论文关键图）与内部边界契约 -------------------------------


def paper_catalog(**catalog_overrides) -> dict:
    return {
        'topic_name': 'demo',
        'entries': [PAPER_CATALOG_ENTRY],
        **catalog_overrides,
    }


def test_required_material_refs_catalog_and_scene_plan_contracts(tmp_path: Path):
    # 1. Paper mode requires explicit required_material_refs (may be []), resolved & non-repeating.
    paper_ws = tmp_path / 'paper'
    complete_through_harvest(paper_ws, input_mode='paper', fetch_materials=False)
    write_json(paper_ws / 'material-catalog.json', {'topic_name': 'demo', 'entries': [PAPER_CATALOG_ENTRY]})
    missing_field = parse_result(run_cli(str(paper_ws)))
    assert missing_field['next_phase']['id'] == '5-material-catalog'
    assert 'required_material_refs' in missing_field['next_phase']['problems']['material-catalog.json']

    for bad_refs, expected in (
        (['main-paper/img_404'], 'main-paper/img_404'),
        (['main-paper/img_001', 'main-paper/img_001'], 'repeats'),
    ):
        write_json(paper_ws / 'material-catalog.json', paper_catalog(required_material_refs=bad_refs))
        bad_res = parse_result(run_cli(str(paper_ws)))
        assert bad_res['next_phase']['id'] == '5-material-catalog'
        assert expected in bad_res['next_phase']['problems']['material-catalog.json']

    for ok_refs in (['main-paper/img_001'], []):
        write_json(paper_ws / 'material-catalog.json', paper_catalog(required_material_refs=ok_refs))
        assert parse_result(run_cli(str(paper_ws)))['next_phase']['id'] == '6-script-scene-plan'

    # 2. Scene-plan coverage of required refs (missing vs identity match vs clip covering parent video).
    std_ws = tmp_path / 'std'
    complete_through_catalog(std_ws)
    write_script(std_ws, SCRIPT_TXT)
    write_json(std_ws / 'tts-lexicon.json', {'OpenHuman': 'Open Human'})

    cat = json.loads((std_ws / 'material-catalog.json').read_text(encoding='utf-8'))
    cat['required_material_refs'] = ['example/vid_001:12-19']
    write_json(std_ws / 'material-catalog.json', cat)
    assert 'not found in this catalog' in parse_result(run_cli(str(std_ws)))['next_phase']['problems']['material-catalog.json']

    cat['required_material_refs'] = ['example/vid_001:12-18.5']
    write_json(std_ws / 'material-catalog.json', cat)
    # Wrong candidate (image instead of required clip) fails Phase 6.
    write_json(std_ws / 'scene-plan.json', [
        {**SCENE_PLAN[0], 'material_candidates': [{'ref': 'example/img_001', 'score': 8, 'reason': 'x'}]},
    ])
    uncovered = parse_result(run_cli(str(std_ws)))
    assert uncovered['next_phase']['id'] == '6-script-scene-plan'
    assert 'example/vid_001:12-18.5' in uncovered['next_phase']['problems']['scene-plan.json']

    # Spelling-different clip ref ('12.00-18.50') covers '12-18.5' by identity, and also covers parent 'example/vid_001'.
    write_json(std_ws / 'scene-plan.json', [
        {**SCENE_PLAN[0], 'material_candidates': [{'ref': 'example/vid_001:12.00-18.50', 'score': 8, 'reason': 'x'}]},
    ])
    assert parse_result(run_cli(str(std_ws)))['next_phase']['id'] == '7-voice-subtitles'
    cat['required_material_refs'] = ['example/vid_001']
    write_json(std_ws / 'material-catalog.json', cat)
    assert parse_result(run_cli(str(std_ws)))['next_phase']['id'] == '7-voice-subtitles'


def test_residual_or_corrupt_catalog_is_ignored_in_no_material_mode(tmp_path: Path):
    settle(tmp_path)  # 标准模式默认 catalog 无需声明 required_material_refs
    catalog_path = tmp_path / 'material-catalog.json'
    assert catalog_path.is_file()
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    catalog['required_material_refs'] = ['example/img_001']
    write_json(catalog_path, catalog)

    write_json(tmp_path / 'inputs.json', {**INPUTS, 'fetch_materials': False})
    write_json(tmp_path / 'scene-plan.json', SCENE_PLAN_NO_MATERIALS)
    approve(tmp_path, 'script')
    result = parse_result(run_cli(str(tmp_path)))

    assert '5-material-catalog' in result['skipped_phases']
    assert result['corrupt_products'] == []
    assert result['next_phase'] is None
    assert catalog_path.is_file()

    for broken_contents in ('{broken', ''):
        catalog_path.write_text(broken_contents, encoding='utf-8')
        assert parse_result(run_cli(str(tmp_path)))['next_phase'] is None
