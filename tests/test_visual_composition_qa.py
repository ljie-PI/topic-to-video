"""Scene-level composition QA through the recorded-snapshot CLI seam."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from cli_helpers import load_script_module, parse_stdout, write_silent_mp3

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'scripts/check-composition.py'


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def element(scene_id: str, *, caption: bool = False, font_size: int = 30) -> dict:
    return {
        'selector': 'span.caption-text' if caption else 'div.shared',
        'id': 'caption-text' if caption else 'shared',
        'tag': 'span' if caption else 'div',
        'label': 'caption text' if caption else 'div shared',
        'rect': {'x': 96, 'y': 1008, 'width': 200, 'height': 40} if caption else
                {'x': 1200, 'y': 700, 'width': 400, 'height': 100},
        'ownText': True,
        'text': '字幕' if caption else 'shared element',
        'fontSize': font_size,
        'isCaption': caption,
        'isUiText': False,
        'isSceneRoot': False,
        'sceneId': None if caption else scene_id,
        'lineCount': 1,
        'layoutIgnore': False,
        'surface': False,
        'media': None,
        'ancestors': ['caption-bar'] if caption else [],
        'overflowStyle': 'visible visible',
        'clientWidth': 200 if caption else 400,
        'clientHeight': 40 if caption else 100,
        'scrollWidth': 200 if caption else 400,
        'scrollHeight': 40 if caption else 100,
    }


def snapshot(scene_id: str, time: float, *, caption_font: int | None = None) -> dict:
    captions = caption_font is not None
    return {
        'scene_id': scene_id, 'time': time, 'fontsStatus': 'loaded', 'presenterVisible': scene_id == 'b',
        'elements': [element(scene_id), *([element(scene_id, caption=True, font_size=caption_font)] if captions else [])],
        'captionTexts': ['字幕'] if captions else [],
        'captionDetails': [{
            'text': '字幕', 'fontSize': caption_font, 'lineCount': 1,
            'rect': {'x': 96, 'y': 1008, 'width': 200, 'height': 40},
        }] if captions else [],
    }


def borrowed_layout(name: str) -> dict:
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


def workspace(tmp_path: Path, snapshots: list[dict]) -> tuple[Path, Path]:
    ws = tmp_path / 'ws'
    write_json(ws / 'inputs.json', {'orientation': 'landscape'})
    write_json(ws / 'composition/scene-config.json', {
        'version': 1,
        'canvas': {'width': 1920, 'height': 1080},
        'total_s': 10,
        'scenes': [
            visual_scene('a', 0, 5, borrowed_layout('landscape')),
            visual_scene('b', 5, 10, borrowed_layout('landscape-presenter')),
        ],
    })
    write_silent_mp3(ws / 'voice_clone/narration.mp3', 10.0)
    path = tmp_path / 'snapshots.json'
    write_json(path, snapshots)
    return ws, path


def run(ws: Path, snapshots: Path, *extra: str) -> tuple[subprocess.CompletedProcess, dict]:
    proc = subprocess.run([
        sys.executable, str(SCRIPT), str(ws / 'composition'),
        '--scene-config', str(ws / 'composition/scene-config.json'),
        '--min-font-size', '22', '--snapshots-from', str(snapshots), *extra,
    ], capture_output=True, text=True)
    return proc, parse_stdout(proc)


@pytest.mark.usefixtures('require_ffmpeg')
def test_scene_layouts_and_active_caption_specs_are_checked_per_scene(tmp_path: Path):
    ws, snapshots = workspace(tmp_path, [snapshot('a', 2, caption_font=36), snapshot('b', 7, caption_font=30)])
    units = tmp_path / 'units.json'
    write_json(units, {'units': [{'text': '字幕', 'begin_s': 0, 'end_s': 10}]})

    proc, result = run(ws, snapshots, '--subtitle-units', str(units))

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert result['verdict'] == 'fail'
    assert {(f['scene_id'], f['check']) for f in result['findings']} == {
        ('b', 'outside_content_regions'),
        ('b', 'reserved_region_intrusion'),
        ('b', 'caption_mismatch'),
    }
    assert [s['layout'] for s in result['scenes_checked']] == ['landscape', 'landscape-presenter']
    mismatch = [f for f in result['findings'] if f['check'] == 'caption_mismatch']
    assert len(mismatch) == 1
    assert mismatch[0]['scene_id'] == 'b'
    assert '30px' in mismatch[0]['issue'] and '36px' in mismatch[0]['issue']


@pytest.mark.usefixtures('require_ffmpeg')
def test_missing_visual_scene_snapshot_cannot_pass(tmp_path: Path):
    ws, snapshots = workspace(tmp_path, [snapshot('a', 2)])
    proc, result = run(ws, snapshots)
    assert proc.returncode == 0
    assert result['verdict'] == 'fail'
    assert any(f['check'] == 'scene_coverage' and f['scene_id'] == 'b' for f in result['findings'])


@pytest.mark.usefixtures('require_ffmpeg')
def test_scene_mount_must_exist_at_each_start_middle_and_end_snapshot(tmp_path: Path):
    start = snapshot('a', 0.2)
    middle = snapshot('a', 2.5)
    end = snapshot('a', 4.8)
    for boundary in (start, end):
        boundary['elements'][0]['sceneId'] = None
    ws, snapshots = workspace(tmp_path, [start, middle, end, snapshot('b', 7)])

    proc, result = run(ws, snapshots)

    assert proc.returncode == 0
    missing = [f for f in result['findings'] if f['check'] == 'scene_mount_missing']
    assert [f['time_s'] for f in missing] == [0.2, 4.8]


@pytest.mark.usefixtures('require_ffmpeg')
def test_adjacent_subtitle_units_and_scene_mode_exact_bounds_do_not_false_positive(tmp_path: Path):
    before_switch = snapshot('a', 4.98, caption_font=36)
    after_unit_end = snapshot('b', 5.1)
    ws, snapshots = workspace(tmp_path, [before_switch, after_unit_end])
    units = tmp_path / 'units.json'
    write_json(units, {'units': [
        {'text': '字幕', 'begin_s': 0.0, 'end_s': 5.0},
        {'text': '下一句', 'begin_s': 5.0, 'end_s': 5.06},
    ]})

    proc, result = run(ws, snapshots, '--subtitle-units', str(units))

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert [f for f in result['findings'] if f['check'] == 'caption_mismatch'] == []


def test_short_scene_sampling_stays_inside_its_range():
    module = load_script_module('check-composition.py', 'check_composition')
    times = module.scene_check_times({'begin_s': 2.0, 'end_s': 2.1})
    assert len(times) == 3
    assert all(2.0 < time < 2.1 for time in times)


def free_layout() -> dict:
    return {
        'preset': None,
        'regions': [
            {'id': 'main', 'kind': 'content', 'rect': {'x': 96, 'y': 80, 'width': 1728, 'height': 820}},
            {'id': 'caption', 'kind': 'reserved', 'component': 'caption-bar',
             'rect': {'x': 96, 'y': 930, 'width': 1728, 'height': 120}},
        ],
        'caption': {'width_px': 1728, 'font_size_px': 36, 'max_lines': 2},
    }


def mixed_workspace(tmp_path: Path, snapshots: list[dict]) -> tuple[Path, Path]:
    """模板场景 + 自由回退场景同片共存的工作区（验收要求的两种正常路径）。"""
    ws = tmp_path / 'ws'
    write_json(ws / 'inputs.json', {'orientation': 'landscape'})
    write_json(ws / 'composition/scene-config.json', {
        'version': 1,
        'canvas': {'width': 1920, 'height': 1080},
        'total_s': 10,
        'scenes': [
            {**visual_scene('tpl', 0, 5, borrowed_layout('landscape-presenter')),
             'template': {'name': 'github-trending', 'scene': 'project-cover'}},
            visual_scene('free', 5, 10, free_layout()),
        ],
    })
    write_silent_mp3(ws / 'voice_clone/narration.mp3', 10.0)
    path = tmp_path / 'snapshots.json'
    write_json(path, snapshots)
    return ws, path


def mixed_snapshot(scene_id: str, time: float, *, presenter: bool) -> dict:
    item = snapshot(scene_id, time, caption_font=36)
    if scene_id == 'tpl':
        # presenter 的 content 区：side (1184,100,640x522)
        item['elements'][0]['rect'] = {'x': 1200, 'y': 120, 'width': 400, 'height': 100}
    else:
        # 自由布局的 main content 区 (96,80,1728x820)，caption 在 reserved caption-bar 区
        item['elements'][0]['rect'] = {'x': 200, 'y': 120, 'width': 400, 'height': 100}
        item['elements'][1]['rect'] = {'x': 96, 'y': 930, 'width': 200, 'height': 40}
        item['captionDetails'][0]['rect'] = {'x': 96, 'y': 930, 'width': 200, 'height': 40}
    item['presenterVisible'] = presenter
    return item


@pytest.mark.usefixtures('require_ffmpeg')
def test_template_and_free_scenes_pass_and_check_current_subtitle_units(tmp_path: Path):
    """模板场景与自由回退场景同片通过区域检查，且以当前（含手改）字幕文件为准。"""
    ws, snapshots_path = mixed_workspace(tmp_path, [
        mixed_snapshot('tpl', 2, presenter=True),
        mixed_snapshot('free', 7, presenter=False),
    ])
    snapshots = json.loads(snapshots_path.read_text(encoding='utf-8'))
    for snap in snapshots:
        snap['captionTexts'] = ['改过的字幕']
        snap['captionDetails'][0]['text'] = '改过的字幕'
    units = tmp_path / 'units.json'
    write_json(units, {'units': [{'text': '改过的字幕', 'begin_s': 0, 'end_s': 10}]})
    edited_path = tmp_path / 'edited-snapshots.json'
    write_json(edited_path, snapshots)

    proc, result = run(ws, edited_path, '--subtitle-units', str(units))

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert result['verdict'] == 'pass', result['findings']
    assert [(s['scene_id'], s['layout']) for s in result['scenes_checked']] == [
        ('tpl', 'landscape-presenter'), ('free', None),
    ]

    # 反向对照：屏幕若仍是初稿文本，与当前（已编辑）单元不符，必须报 mismatch
    proc, result = run(ws, snapshots_path, '--subtitle-units', str(units))

    assert proc.returncode == 0
    mismatch = [f for f in result['findings'] if f['check'] == 'caption_mismatch']
    assert len(mismatch) == 2
    assert all('改过的字幕' in f['issue'] for f in mismatch)


@pytest.mark.usefixtures('require_ffmpeg')
def test_presenter_visibility_mismatch_against_person_region_is_reported(tmp_path: Path):
    ws, snapshots = mixed_workspace(tmp_path, [
        mixed_snapshot('tpl', 2, presenter=False),
        mixed_snapshot('free', 7, presenter=True),
    ])
    units = tmp_path / 'units.json'
    write_json(units, {'units': [{'text': '字幕', 'begin_s': 0, 'end_s': 10}]})

    proc, result = run(ws, snapshots, '--subtitle-units', str(units))

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert result['verdict'] == 'fail'
    assert [(f['scene_id'], f['check'], f['issue']) for f in result['findings']] == [
        ('tpl', 'presenter_component', 'visual scene layout has a presenter region but presenter is not visible'),
        ('free', 'presenter_component', 'presenter is visible in a visual scene whose layout has no presenter region'),
    ]

