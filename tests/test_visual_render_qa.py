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


def write_json(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


def visual_workspace(tmp_path: Path, duration: float, *, strict: bool = False, overlap: bool = False) -> Path:
    write_json(tmp_path / 'inputs.json', {
        'orientation': 'landscape', 'qa_level': 'strict' if strict else 'standard',
    })
    audio = tmp_path / 'voice_clone/narration.mp3'
    audio.parent.mkdir(parents=True)
    subprocess.run([
        'ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono',
        '-t', str(duration), '-c:a', 'libmp3lame', str(audio),
    ], capture_output=True, check=True)
    # Phase 9 通过 --timeline 复用 timeline_scenes 的宽松字段读取：scene-config
    # 与旧 timeline.json 都只取 scene_id / begin_s / end_s。
    mid = duration * 0.5
    before_end, after_begin = (duration * 0.6, mid) if overlap else (mid, mid)
    write_json(tmp_path / 'composition/scene-config.json', {
        'version': 1,
        'canvas': {'width': 1920, 'height': 1080},
        'total_s': duration,
        'scenes': [
            {'scene_id': 'visual_before', 'source_scene_ids': ['scene_1'],
             'begin_s': 0, 'end_s': before_end, 'template': None,
             'layout': {'preset': 'landscape-presenter', 'regions': [], 'caption': {'width_px': 1, 'font_size_px': 1, 'max_lines': 1}}},
            {'scene_id': 'visual_after', 'source_scene_ids': ['scene_2'],
             'begin_s': after_begin, 'end_s': duration, 'template': None,
             'layout': {'preset': None, 'regions': [], 'caption': {'width_px': 1, 'font_size_px': 1, 'max_lines': 1}}},
        ],
    })
    return tmp_path


def test_check_render_maps_overlap_to_later_visual_scene(tmp_path: Path):
    ws = visual_workspace(tmp_path, 7.5, overlap=True)
    video = ws / 'black.mp4'
    make_black_video(video)

    proc = subprocess.run([
        sys.executable, str(ROOT / 'scripts/check-render.py'),
        '--video', str(video), '--inputs', str(ws / 'inputs.json'),
        '--timeline', str(ws / 'composition/scene-config.json'),
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
        '--timeline', str(ws / 'composition/scene-config.json'), '--output-dir', str(ws / 'qa'),
    ], capture_output=True, text=True)
    result = parse_stdout(proc)

    assert proc.returncode == 0, proc.stderr
    assert {frame['scene_id'] for frame in result['frames']} == {
        'visual_before', 'visual_after', 'visual_before->visual_after',
    }
    cuts = {frame['kind']: frame['time_s'] for frame in result['frames'] if frame['kind'].startswith('cut_')}
    assert cuts == {'cut_before': 4.6, 'cut_mid': 5.0, 'cut_after': 5.4}


def test_contact_sheet_reads_scene_config_scenes_leniently(tmp_path: Path):
    # --timeline 的宽松读取只认 scene_id / begin_s / end_s：即便 scene-config
    # 缺可选细节（如自由布局的 regions 留待排版），Phase 9 的场景映射仍可用。
    ws = visual_workspace(tmp_path, 10)
    path = ws / 'composition/scene-config.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    for scene in data['scenes']:
        scene['layout'] = {'preset': None}
    path = write_json(path, data)
    video = ws / 'final.mp4'
    make_video(video)

    proc = subprocess.run([
        sys.executable, str(ROOT / 'scripts/make-contact-sheet.py'),
        '--video', str(video), '--inputs', str(ws / 'inputs.json'),
        '--timeline', str(path), '--output-dir', str(ws / 'qa'),
    ], capture_output=True, text=True)
    result = parse_stdout(proc)

    assert proc.returncode == 0, proc.stderr
    assert {frame['scene_id'] for frame in result['frames']} >= {'visual_before', 'visual_after'}


def test_phase9_uses_split_and_merged_visual_scene_ids(tmp_path: Path):
    """拆并后的最终视觉 scene_id 是 Phase 9 的唯一归属依据（#151 验收）。

    叙事 scene_1 被拆成 intro_part_1 / intro_part_2，scene_2 + scene_3 合并成
    demo_merged；黑屏 / 抽帧标注必须落在视觉 scene_id 上，不得冒出叙事 id。
    """
    write_json(tmp_path / 'inputs.json', {'orientation': 'landscape', 'qa_level': 'strict'})
    audio = tmp_path / 'voice_clone/narration.mp3'
    audio.parent.mkdir(parents=True)
    subprocess.run([
        'ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono',
        '-t', '10', '-c:a', 'libmp3lame', str(audio),
    ], capture_output=True, check=True)
    write_json(tmp_path / 'composition/scene-config.json', {
        'version': 1,
        'canvas': {'width': 1920, 'height': 1080},
        'total_s': 10,
        'scenes': [
            {'scene_id': 'intro_part_1', 'source_scene_ids': ['scene_1'],
             'begin_s': 0, 'end_s': 3, 'template': None,
             'layout': {'preset': None, 'regions': [], 'caption': {'width_px': 1, 'font_size_px': 1, 'max_lines': 1}}},
            {'scene_id': 'intro_part_2', 'source_scene_ids': ['scene_1'],
             'begin_s': 3, 'end_s': 6, 'template': None,
             'layout': {'preset': None, 'regions': [], 'caption': {'width_px': 1, 'font_size_px': 1, 'max_lines': 1}}},
            {'scene_id': 'demo_merged', 'source_scene_ids': ['scene_2', 'scene_3'],
             'begin_s': 6, 'end_s': 10, 'template': None,
             'layout': {'preset': None, 'regions': [], 'caption': {'width_px': 1, 'font_size_px': 1, 'max_lines': 1}}},
        ],
    })

    video = tmp_path / 'black.mp4'
    make_black_video(video)
    proc = subprocess.run([
        sys.executable, str(ROOT / 'scripts/check-render.py'),
        '--video', str(video), '--inputs', str(tmp_path / 'inputs.json'),
        '--timeline', str(tmp_path / 'composition/scene-config.json'),
    ], capture_output=True, text=True)
    result = parse_stdout(proc)
    assert proc.returncode == 0, proc.stderr
    black = next(f for f in result['findings'] if f['check'] == 'black_screen')
    assert black['scene_id'] == 'intro_part_2'  # 黑屏段 4.0–5.5s 落在 [3, 6)
    assert not {'scene_1', 'scene_2', 'scene_3'} & {f['scene_id'] for f in result['findings']}

    video = tmp_path / 'final.mp4'
    make_video(video)
    proc = subprocess.run([
        sys.executable, str(ROOT / 'scripts/make-contact-sheet.py'),
        '--video', str(video), '--inputs', str(tmp_path / 'inputs.json'),
        '--timeline', str(tmp_path / 'composition/scene-config.json'),
        '--output-dir', str(tmp_path / 'qa'),
    ], capture_output=True, text=True)
    result = parse_stdout(proc)
    assert proc.returncode == 0, proc.stderr
    ids = {frame['scene_id'] for frame in result['frames']}
    assert {'intro_part_1', 'intro_part_2', 'demo_merged'} <= ids
    assert not {'scene_1', 'scene_2', 'scene_3'} & ids
