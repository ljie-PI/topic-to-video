"""Phase 9 consumes final visual scenes rather than narrative timeline scenes."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from cli_helpers import parse_stdout
from test_check_render import make_black_video
from test_make_contact_sheet import make_video

pytestmark = pytest.mark.usefixtures('require_ffmpeg')
ROOT = Path(__file__).resolve().parent.parent


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding='utf-8')


def visual_workspace(tmp_path: Path, duration: float, *, strict: bool = False) -> Path:
    write_json(tmp_path / 'inputs.json', {
        'orientation': 'landscape', 'qa_level': 'strict' if strict else 'standard',
    })
    audio = tmp_path / 'voice_clone/narration.mp3'
    audio.parent.mkdir(parents=True)
    subprocess.run([
        'ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono',
        '-t', str(duration), '-c:a', 'libmp3lame', str(audio),
    ], capture_output=True, check=True)
    write_json(tmp_path / 'composition/scenes.json', {'version': 1, 'scenes': [
        {'scene_id': 'visual_before', 'begin_s': 0, 'end_s': duration * 0.6, 'layout': 'presenter'},
        {'scene_id': 'visual_after', 'begin_s': duration * 0.5, 'end_s': duration, 'layout': 'stage'},
    ]})
    return tmp_path


def test_check_render_maps_overlap_to_later_visual_scene(tmp_path: Path):
    ws = visual_workspace(tmp_path, 7.5)
    video = ws / 'black.mp4'
    make_black_video(video)

    proc = subprocess.run([
        sys.executable, str(ROOT / 'scripts/check-render.py'),
        '--video', str(video), '--inputs', str(ws / 'inputs.json'),
        '--scenes', str(ws / 'composition/scenes.json'),
    ], capture_output=True, text=True)
    result = parse_stdout(proc)

    assert proc.returncode == 0, proc.stderr
    black = next(f for f in result['findings'] if f['check'] == 'black_screen')
    assert black['scene_id'] == 'visual_after'


def test_final_end_maps_to_long_active_scene_not_already_ended_later_item():
    spec = importlib.util.spec_from_file_location('check_render_visual', ROOT / 'scripts/check-render.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ranges = [('long', 0, 20), ('short', 5, 19)]

    assert module.map_time_to_scene(ranges, 20) == 'long'


def test_contact_sheet_uses_visual_ids_and_real_transition_start(tmp_path: Path):
    ws = visual_workspace(tmp_path, 10, strict=True)
    video = ws / 'final.mp4'
    make_video(video)

    proc = subprocess.run([
        sys.executable, str(ROOT / 'scripts/make-contact-sheet.py'),
        '--video', str(video), '--inputs', str(ws / 'inputs.json'),
        '--scenes', str(ws / 'composition/scenes.json'), '--output-dir', str(ws / 'qa'),
    ], capture_output=True, text=True)
    result = parse_stdout(proc)

    assert proc.returncode == 0, proc.stderr
    assert {frame['scene_id'] for frame in result['frames']} == {
        'visual_before', 'visual_after', 'visual_before->visual_after',
    }
    cuts = {frame['kind']: frame['time_s'] for frame in result['frames'] if frame['kind'].startswith('cut_')}
    assert cuts == {'cut_before': 4.6, 'cut_mid': 5.0, 'cut_after': 5.4}


def test_visual_scene_cli_rejects_invalid_contract(tmp_path: Path):
    ws = visual_workspace(tmp_path, 10)
    path = ws / 'composition/scenes.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['scenes'][0]['scene_id'] = data['scenes'][1]['scene_id']
    write_json(path, data)
    video = ws / 'final.mp4'
    make_video(video)

    proc = subprocess.run([
        sys.executable, str(ROOT / 'scripts/make-contact-sheet.py'),
        '--video', str(video), '--inputs', str(ws / 'inputs.json'),
        '--scenes', str(path), '--output-dir', str(ws / 'qa'),
    ], capture_output=True, text=True)
    result = parse_stdout(proc)
    assert proc.returncode == 1
    assert 'duplicate' in result['error']
