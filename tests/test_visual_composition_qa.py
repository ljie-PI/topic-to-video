"""Scene-level composition QA through the recorded-snapshot CLI seam."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from composition_hash import visual_contract_fingerprint

pytestmark = pytest.mark.usefixtures('require_ffmpeg')
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
        'scene_id': scene_id, 'time': time, 'fontsStatus': 'loaded', 'jayVisible': scene_id == 'b',
        'elements': [element(scene_id), *([element(scene_id, caption=True, font_size=caption_font)] if captions else [])],
        'captionTexts': ['字幕'] if captions else [],
        'captionDetails': [{
            'text': '字幕', 'fontSize': caption_font, 'lineCount': 1,
            'rect': {'x': 96, 'y': 1008, 'width': 200, 'height': 40},
        }] if captions else [],
    }


def workspace(tmp_path: Path, snapshots: list[dict]) -> tuple[Path, Path]:
    ws = tmp_path / 'ws'
    write_json(ws / 'inputs.json', {'orientation': 'landscape'})
    write_json(ws / 'composition/scenes.json', {'version': 1, 'scenes': [
        {'scene_id': 'a', 'begin_s': 0, 'end_s': 5, 'layout': 'stage'},
        {'scene_id': 'b', 'begin_s': 5, 'end_s': 10, 'layout': 'presenter'},
    ]})
    (ws / 'voice_clone').mkdir(parents=True)
    subprocess.run([
        'ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono',
        '-t', '10', '-c:a', 'libmp3lame', str(ws / 'voice_clone/narration.mp3'),
    ], capture_output=True, check=True)
    path = tmp_path / 'snapshots.json'
    write_json(path, snapshots)
    return ws, path


def run(ws: Path, snapshots: Path, *extra: str) -> tuple[subprocess.CompletedProcess, dict]:
    proc = subprocess.run([
        sys.executable, str(SCRIPT), str(ws / 'composition'),
        '--scenes', str(ws / 'composition/scenes.json'),
        '--min-font-size', '22', '--snapshots-from', str(snapshots), *extra,
    ], capture_output=True, text=True)
    return proc, json.loads(proc.stdout)


def test_same_element_is_checked_against_each_actual_scene_layout(tmp_path: Path):
    ws, snapshots = workspace(tmp_path, [snapshot('a', 2), snapshot('b', 7)])

    proc, result = run(ws, snapshots)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert result['verdict'] == 'fail'
    assert {(f['scene_id'], f['check']) for f in result['findings']} == {
        ('b', 'outside_content_regions'), ('b', 'reserved_region_intrusion'),
    }
    assert [s['layout'] for s in result['scenes_checked']] == ['stage', 'presenter']
    assert result['visual_contract_sha256'] == visual_contract_fingerprint(
        ws / 'composition/scenes.json', [
            ROOT / 'modules/layouts/presenter.json', ROOT / 'modules/layouts/stage.json',
        ],
    )


def test_active_scene_caption_font_and_lines_are_checked(tmp_path: Path):
    ws, snapshots = workspace(tmp_path, [snapshot('a', 2, caption_font=36), snapshot('b', 7, caption_font=30)])
    units = tmp_path / 'units.json'
    write_json(units, {'units': [{'text': '字幕', 'begin_s': 0, 'end_s': 10}]})

    proc, result = run(ws, snapshots, '--subtitle-units', str(units))

    assert proc.returncode == 0, proc.stdout + proc.stderr
    mismatch = [f for f in result['findings'] if f['check'] == 'caption_mismatch']
    assert len(mismatch) == 1
    assert mismatch[0]['scene_id'] == 'b'
    assert '30px' in mismatch[0]['issue'] and '36px' in mismatch[0]['issue']


def test_missing_visual_scene_snapshot_cannot_pass(tmp_path: Path):
    ws, snapshots = workspace(tmp_path, [snapshot('a', 2)])
    proc, result = run(ws, snapshots)
    assert proc.returncode == 0
    assert result['verdict'] == 'fail'
    assert any(f['check'] == 'scene_coverage' and f['scene_id'] == 'b' for f in result['findings'])


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
    spec = importlib.util.spec_from_file_location('check_composition', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    times = module.scene_check_times({'begin_s': 2.0, 'end_s': 2.1})
    assert len(times) == 3
    assert all(2.0 < time < 2.1 for time in times)
