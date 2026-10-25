"""Integration tests for scripts/check-render.py.

The test seam is the script's command line (repo convention: stdout = one
JSON, exit codes 0 / 1 / 2). Tiny synthetic videos are generated with ffmpeg
in tmp dirs: testsrc plus an injected black segment (concat) for black
detection, and tpad stop_mode=clone for freeze detection. All tests skip when
ffmpeg is not installed.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'check-render.py'

pytestmark = pytest.mark.skipif(
    shutil.which('ffmpeg') is None or shutil.which('ffprobe') is None,
    reason='ffmpeg / ffprobe not installed',
)

TIMELINE = {
    'total_s': 7.5,
    'scenes': [
        {'scene_id': 'intro', 'begin_s': 0.0, 'end_s': 4.0, 'peak_s': 2.0},
        {'scene_id': 'middle', 'begin_s': 4.0, 'end_s': 5.5},
        {'scene_id': 'outro', 'begin_s': 5.5, 'end_s': 7.5, 'peak_s': 6.5},
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


def ffmpeg(*args: str) -> None:
    subprocess.run(
        ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *args],
        check=True,
        capture_output=True,
        text=True,
    )


def make_clean_video(path: Path, duration: float = 7.5) -> None:
    """testsrc + sine tone, no black, no freeze."""
    ffmpeg(
        '-f', 'lavfi', '-i', f'testsrc=duration={duration}:size=320x240:rate=25',
        '-f', 'lavfi', '-i', f'sine=frequency=440:duration={duration}',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
        str(path),
    )


def make_black_video(path: Path) -> None:
    """4s testsrc + 1.5s black + 2s testsrc, with audio."""
    ffmpeg(
        '-f', 'lavfi', '-i', 'testsrc=duration=4:size=320x240:rate=25',
        '-f', 'lavfi', '-i', 'color=black:size=320x240:rate=25:duration=1.5',
        '-f', 'lavfi', '-i', 'testsrc=duration=2:size=320x240:rate=25',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=7.5',
        '-filter_complex',
        '[0:v][1:v][2:v]concat=n=3:v=1:a=0[v];[3:a]anull[a]',
        '-map', '[v]', '-map', '[a]',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
        str(path),
    )


def make_black_tail_video(path: Path) -> None:
    """3s testsrc + 1.2s black tail."""
    ffmpeg(
        '-f', 'lavfi', '-i', 'testsrc=duration=3:size=320x240:rate=25',
        '-f', 'lavfi', '-i', 'color=black:size=320x240:rate=25:duration=1.2',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=4.2',
        '-filter_complex',
        '[0:v][1:v]concat=n=2:v=1:a=0[v];[2:a]anull[a]',
        '-map', '[v]', '-map', '[a]',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
        str(path),
    )


def make_freeze_video(path: Path) -> None:
    """2s testsrc + 4s cloned last frame (tpad stop_mode=clone)."""
    ffmpeg(
        '-f', 'lavfi', '-i', 'testsrc=duration=2:size=320x240:rate=25',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=6',
        '-vf', 'tpad=stop_mode=clone:stop_duration=4',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
        str(path),
    )


def make_silent_video(path: Path) -> None:
    ffmpeg(
        '-f', 'lavfi', '-i', 'testsrc=duration=3:size=320x240:rate=25',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        str(path),
    )


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    write_json(tmp_path / 'inputs.json', {'orientation': 'landscape'})
    write_json(tmp_path / 'timeline.json', TIMELINE)
    return tmp_path


def test_clean_video_passes(workspace: Path):
    video = workspace / 'clean.mp4'
    make_clean_video(video)
    proc = run_cli(
        '--video', str(video),
        '--inputs', str(workspace / 'inputs.json'),
        '--timeline', str(workspace / 'timeline.json'),
    )
    result = parse_result(proc)
    assert proc.returncode == 0
    assert result['success'] is True
    assert result['verdict'] == 'pass'
    assert result['findings'] == []


def test_black_segment_found_and_mapped_to_scene(workspace: Path):
    video = workspace / 'black.mp4'
    make_black_video(video)
    proc = run_cli(
        '--video', str(video),
        '--inputs', str(workspace / 'inputs.json'),
        '--timeline', str(workspace / 'timeline.json'),
    )
    result = parse_result(proc)
    assert proc.returncode == 0
    assert result['verdict'] == 'fail'
    black = [f for f in result['findings'] if f['check'] == 'black_screen']
    assert len(black) == 1
    assert black[0]['scene_id'] == 'middle'  # black starts at 4.0s, inside scene [4.0, 5.5)
    assert black[0]['time_s'] == pytest.approx(4.0, abs=0.2)
    assert '1.5' in black[0]['issue']


def test_black_tail_found(workspace: Path):
    video = workspace / 'tail.mp4'
    make_black_tail_video(video)
    proc = run_cli(
        '--video', str(video),
        '--inputs', str(workspace / 'inputs.json'),
        '--timeline', str(workspace / 'timeline.json'),
    )
    result = parse_result(proc)
    checks = {f['check'] for f in result['findings']}
    assert 'black_screen' in checks
    assert 'black_tail' in checks


def test_freeze_found_with_configurable_threshold(workspace: Path):
    video = workspace / 'freeze.mp4'
    make_freeze_video(video)
    # Default 4s threshold: the 4s cloned segment is reported.
    proc = run_cli(
        '--video', str(video),
        '--inputs', str(workspace / 'inputs.json'),
        '--timeline', str(workspace / 'timeline.json'),
    )
    result = parse_result(proc)
    freezes = [f for f in result['findings'] if f['check'] == 'freeze']
    assert len(freezes) == 1
    assert freezes[0]['scene_id'] == 'intro'
    assert freezes[0]['time_s'] == pytest.approx(2.0, abs=0.2)
    # Raising the threshold above the freeze length: nothing reported.
    proc = run_cli(
        '--video', str(video),
        '--inputs', str(workspace / 'inputs.json'),
        '--timeline', str(workspace / 'timeline.json'),
        '--freeze-threshold', '5',
    )
    result = parse_result(proc)
    assert [f for f in result['findings'] if f['check'] == 'freeze'] == []


def test_freeze_maps_to_nearest_scene_without_exact_containment(workspace: Path):
    video = workspace / 'freeze.mp4'
    make_freeze_video(video)
    # Shift scenes so the freeze at ~2s falls in a gap: nearest midpoint wins.
    timeline = json.loads(json.dumps(TIMELINE))
    timeline['scenes'] = [
        {'scene_id': 'a', 'begin_s': 0.0, 'end_s': 1.0},
        {'scene_id': 'b', 'begin_s': 2.0, 'end_s': 3.5},
    ]
    timeline_path = workspace / 'timeline_gap.json'
    write_json(timeline_path, timeline)
    proc = run_cli(
        '--video', str(video),
        '--inputs', str(workspace / 'inputs.json'),
        '--timeline', str(timeline_path),
    )
    result = parse_result(proc)
    freezes = [f for f in result['findings'] if f['check'] == 'freeze']
    assert freezes[0]['scene_id'] == 'b'


def test_missing_audio_track_found(workspace: Path):
    video = workspace / 'silent.mp4'
    make_silent_video(video)
    proc = run_cli(
        '--video', str(video),
        '--inputs', str(workspace / 'inputs.json'),
        '--timeline', str(workspace / 'timeline.json'),
    )
    result = parse_result(proc)
    audio = [f for f in result['findings'] if f['check'] == 'audio_track']
    assert len(audio) == 1
    assert audio[0]['scene_id'] is None


def test_orientation_mismatch_found(workspace: Path):
    video = workspace / 'clean.mp4'
    make_clean_video(video)
    portrait_inputs = workspace / 'inputs_portrait.json'
    write_json(portrait_inputs, {'orientation': 'portrait'})
    proc = run_cli(
        '--video', str(video),
        '--inputs', str(portrait_inputs),
        '--timeline', str(workspace / 'timeline.json'),
    )
    result = parse_result(proc)
    orientation = [f for f in result['findings'] if f['check'] == 'orientation']
    assert len(orientation) == 1
    assert 'portrait' in orientation[0]['issue']


def test_portrait_orientation_accepted_for_portrait_3x4(tmp_path: Path):
    video = tmp_path / 'portrait.mp4'
    ffmpeg(
        '-f', 'lavfi', '-i', 'testsrc=duration=3:size=240x320:rate=25',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=3',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
        str(video),
    )
    write_json(tmp_path / 'inputs.json', {'orientation': 'portrait-3:4'})
    proc = run_cli('--video', str(video), '--inputs', str(tmp_path / 'inputs.json'))
    result = parse_result(proc)
    assert result['verdict'] == 'pass'


def test_no_timeline_falls_back_to_null_scene_id(workspace: Path):
    video = workspace / 'black.mp4'
    make_black_video(video)
    proc = run_cli(
        '--video', str(video),
        '--inputs', str(workspace / 'inputs.json'),
    )
    result = parse_result(proc)
    black = [f for f in result['findings'] if f['check'] == 'black_screen']
    assert len(black) == 1
    assert black[0]['scene_id'] is None


def test_usage_error_exits_2(workspace: Path):
    proc = run_cli('--bogus-flag')
    assert proc.returncode == 2
    result = parse_result(proc)
    assert result['success'] is False


def test_missing_video_exits_1(workspace: Path):
    proc = run_cli(
        '--video', str(workspace / 'nope.mp4'),
        '--inputs', str(workspace / 'inputs.json'),
    )
    assert proc.returncode == 1
    result = parse_result(proc)
    assert result['success'] is False
