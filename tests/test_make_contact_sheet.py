"""Integration tests for scripts/make-contact-sheet.py.

The test seam is the script's command line (repo convention: stdout = one
JSON, exit codes 0 / 1 / 2). A tiny testsrc video is generated with ffmpeg in
a tmp dir and paired with fabricated timeline.json and inputs.json files.
ffmpeg / ffprobe are required dependencies, without them these tests fail via
the require_ffmpeg fixture, never skip.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.usefixtures('require_ffmpeg')

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'make-contact-sheet.py'

TIMELINE = {
    'total_s': 10.0,
    'scenes': [
        {'scene_id': 'intro', 'begin_s': 0.0, 'end_s': 2.0},
        {'scene_id': 'middle', 'begin_s': 2.0, 'end_s': 5.0},
        {'scene_id': 'outro', 'begin_s': 5.0, 'end_s': 10.0},
    ],
}


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def parse_result(proc: subprocess.CompletedProcess) -> dict:
    assert proc.returncode in (0, 1, 2)
    return json.loads(proc.stdout)


def make_video(path: Path) -> None:
    subprocess.run(
        [
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', 'testsrc=duration=10:size=320x240:rate=25',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


def run_sheet(workspace: Path, output_dir: str = 'qa') -> subprocess.CompletedProcess:
    return run_cli(
        '--video', str(workspace / 'final.mp4'),
        '--timeline', str(workspace / 'timeline.json'),
        '--inputs', str(workspace / 'inputs.json'),
        '--output-dir', str(workspace / output_dir),
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    video = tmp_path / 'final.mp4'
    make_video(video)
    write_json(tmp_path / 'timeline.json', TIMELINE)
    write_json(tmp_path / 'inputs.json', {'qa_level': 'standard'})
    return tmp_path


def test_standard_extracts_one_midpoint_frame_per_scene(workspace: Path):
    proc = run_sheet(workspace)
    result = parse_result(proc)
    assert proc.returncode == 0
    assert result['success'] is True
    assert result['qa_level'] == 'standard'
    assert result['vision_check_required'] is True
    assert result['frame_count'] == 3
    assert result['sheet_count'] == math.ceil(3 / 4)
    assert len(result['sheets']) == 1
    for frame in result['frames']:
        assert Path(frame['image']).is_file()
        assert Path(frame['sheet']).is_file()
    by_scene = {f['scene_id']: f['time_s'] for f in result['frames']}
    assert by_scene == {'intro': 1.0, 'middle': 3.5, 'outro': 7.5}


def test_quick_uses_standard_frames_and_disables_vision(workspace: Path):
    write_json(workspace / 'inputs.json', {'qa_level': 'quick'})
    result = parse_result(run_sheet(workspace))
    assert result['qa_level'] == 'quick'
    assert result['vision_check_required'] is False
    assert result['frame_count'] == 3


def test_missing_qa_level_defaults_to_standard_with_vision(workspace: Path):
    write_json(workspace / 'inputs.json', {})
    result = parse_result(run_sheet(workspace))
    assert result['qa_level'] == 'standard'
    assert result['vision_check_required'] is True
    assert result['frame_count'] == 3


def test_legacy_qa_level_option_is_rejected(workspace: Path):
    proc = run_cli(
        '--video', str(workspace / 'final.mp4'),
        '--timeline', str(workspace / 'timeline.json'),
        '--inputs', str(workspace / 'inputs.json'),
        '--qa-level', 'standard',
    )
    assert proc.returncode == 2
    result = parse_result(proc)
    assert result['success'] is False
    assert '--qa-level' in result['error']


def test_sheet_count_is_ceil_frames_over_four(workspace: Path):
    timeline = json.loads(json.dumps(TIMELINE))
    timeline['scenes'] = [
        {'scene_id': f's{i}', 'begin_s': float(i), 'end_s': float(i) + 1} for i in range(5)
    ]
    write_json(workspace / 'timeline.json', timeline)
    result = parse_result(run_sheet(workspace))
    assert result['frame_count'] == 5
    assert result['sheet_count'] == 2  # ceil(5/4)
    for sheet in result['sheets']:
        assert Path(sheet).is_file()
        assert Path(sheet).stat().st_size > 0


def test_strict_adds_entrance_and_cut_point_frames(workspace: Path):
    write_json(workspace / 'inputs.json', {'qa_level': 'strict'})
    result = parse_result(run_sheet(workspace, 'qa_strict'))
    assert result['qa_level'] == 'strict'
    assert result['vision_check_required'] is True
    kinds = [f['kind'] for f in result['frames']]
    # 3 midpoints + 3 entrances + 2 cut points x (before/mid/after)
    assert kinds.count('peak') == 3
    assert kinds.count('entrance') == 3
    assert kinds.count('cut_before') == 2
    assert kinds.count('cut_mid') == 2
    assert kinds.count('cut_after') == 2
    assert result['frame_count'] == 3 + 3 + 6
    assert result['sheet_count'] == math.ceil(12 / 4)
    cut_frames = [f for f in result['frames'] if f['kind'].startswith('cut_')]
    assert all('->' in f['scene_id'] for f in cut_frames)


def test_contact_sheet_uses_high_quality_jpeg(workspace: Path):
    from PIL import Image

    result = parse_result(run_sheet(workspace))
    for sheet in result['sheets']:
        with Image.open(sheet) as image:
            assert image.quantization[0][0] <= 10


def test_annotations_present_on_frames(workspace: Path):
    """Annotated frames carry a non-empty annotation strip at the top."""
    from PIL import Image

    result = parse_result(run_sheet(workspace))
    for frame in result['frames']:
        with Image.open(frame['image']) as image:
            width, height = image.size
            strip = image.convert('RGB').crop((0, 0, width, max(8, height // 12)))
        # The strip is black...
        colors = strip.getcolors(maxcolors=1_000_000) or []
        darkest = min(band for _, rgb in colors for band in rgb)
        assert darkest == 0
        # ...and has bright (text) pixels inside it.
        brightest = max(band for _, rgb in colors for band in rgb)
        assert brightest > 200


def test_missing_scenes_in_timeline_is_runtime_error(workspace: Path):
    write_json(
        workspace / 'timeline.json',
        {'total_s': 10.0, 'paragraphs': [{'index': 1, 'begin_s': 0.0, 'end_s': 10.0}]},
    )
    proc = run_sheet(workspace)
    assert proc.returncode == 1
    result = parse_result(proc)
    assert result['success'] is False


def test_usage_error_exits_2(workspace: Path):
    proc = run_cli('--bogus-flag')
    assert proc.returncode == 2
    result = parse_result(proc)
    assert result['success'] is False


def test_missing_video_exits_1(workspace: Path):
    proc = run_cli(
        '--video', str(workspace / 'nope.mp4'),
        '--timeline', str(workspace / 'timeline.json'),
        '--inputs', str(workspace / 'inputs.json'),
    )
    assert proc.returncode == 1
    result = parse_result(proc)
    assert result['success'] is False


def test_missing_inputs_exits_1(workspace: Path):
    proc = run_cli(
        '--video', str(workspace / 'final.mp4'),
        '--timeline', str(workspace / 'timeline.json'),
        '--inputs', str(workspace / 'nope.json'),
    )
    assert proc.returncode == 1
    assert parse_result(proc)['success'] is False


@pytest.mark.parametrize('binary_env', ['FFMPEG_BIN', 'FFPROBE_BIN'])
def test_missing_media_binary_preserves_existing_frames(
    workspace: Path, monkeypatch: pytest.MonkeyPatch, binary_env: str
):
    output_dir = workspace / 'qa'
    frames_dir = output_dir / 'frames'
    frames_dir.mkdir(parents=True)
    existing = frames_dir / 'frame_existing.jpg'
    existing.write_bytes(b'pre-existing frame')
    monkeypatch.setenv(binary_env, '/nonexistent')

    proc = run_sheet(workspace)

    assert proc.returncode == 1
    assert existing.read_bytes() == b'pre-existing frame'
