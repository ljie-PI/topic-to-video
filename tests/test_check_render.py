"""Integration tests for scripts/check-render.py.

The test seam is the script's command line (repo convention: stdout = one
JSON, exit codes 0 / 1 / 2). Tiny synthetic videos are generated with ffmpeg
in tmp dirs: testsrc plus an injected black segment (concat) for black
detection, and tpad stop_mode=clone for freeze detection. ffmpeg / ffprobe
are required dependencies, without them these tests fail via the
require_ffmpeg fixture, never skip.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from cli_helpers import parse_stdout as parse_result

pytestmark = pytest.mark.usefixtures('require_ffmpeg')

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'check-render.py'

TIMELINE = {
    'total_s': 7.5,
    'scenes': [
        {'scene_id': 'intro', 'begin_s': 0.0, 'end_s': 4.0},
        {'scene_id': 'middle', 'begin_s': 4.0, 'end_s': 5.5},
        {'scene_id': 'outro', 'begin_s': 5.5, 'end_s': 7.5},
    ],
}


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


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
        '-f', 'lavfi', '-i', f'testsrc=duration={duration}:size=1920x1080:rate=10',
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


def test_clean_video_passes_landscape_and_reports_orientation_mismatch(workspace: Path):
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

    portrait_inputs = workspace / 'inputs_portrait.json'
    write_json(portrait_inputs, {'orientation': 'portrait'})
    mismatch = parse_result(run_cli(
        '--video', str(video),
        '--inputs', str(portrait_inputs),
        '--timeline', str(workspace / 'timeline.json'),
    ))
    orientation = [f for f in mismatch['findings'] if f['check'] == 'orientation']
    assert len(orientation) == 1
    assert 'portrait' in orientation[0]['issue']


def test_black_segment_maps_to_timeline_scene_or_null_without_timeline(workspace: Path):
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
    # qa-report schema requires the frame key on every finding; deterministic
    # findings carry frame null alongside time_s.
    assert black[0]['frame'] is None

    no_timeline = parse_result(run_cli(
        '--video', str(video),
        '--inputs', str(workspace / 'inputs.json'),
    ))
    black_without_timeline = [f for f in no_timeline['findings'] if f['check'] == 'black_screen']
    assert len(black_without_timeline) == 1
    assert black_without_timeline[0]['scene_id'] is None


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


def test_freeze_threshold_and_nearest_scene_mapping(workspace: Path):
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
    raised = parse_result(run_cli(
        '--video', str(video),
        '--inputs', str(workspace / 'inputs.json'),
        '--timeline', str(workspace / 'timeline.json'),
        '--freeze-threshold', '5',
    ))
    assert [f for f in raised['findings'] if f['check'] == 'freeze'] == []

    # Shift scenes so the freeze at ~2s falls in a gap: nearest midpoint wins.
    timeline = json.loads(json.dumps(TIMELINE))
    timeline['scenes'] = [
        {'scene_id': 'a', 'begin_s': 0.0, 'end_s': 1.0},
        {'scene_id': 'b', 'begin_s': 2.0, 'end_s': 3.5},
    ]
    timeline_path = workspace / 'timeline_gap.json'
    write_json(timeline_path, timeline)
    gap_result = parse_result(run_cli(
        '--video', str(video),
        '--inputs', str(workspace / 'inputs.json'),
        '--timeline', str(timeline_path),
    ))
    assert [f['scene_id'] for f in gap_result['findings'] if f['check'] == 'freeze'] == ['b']


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


def test_exact_three_by_four_and_nine_by_sixteen_canvases_do_not_interchange(tmp_path: Path):
    three_by_four = tmp_path / 'portrait_3x4.mp4'
    ffmpeg(
        '-f', 'lavfi', '-i', 'testsrc2=duration=1:size=1080x1440:rate=10',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
        str(three_by_four),
    )
    write_json(tmp_path / 'inputs.json', {'orientation': 'portrait-3:4'})
    assert parse_result(run_cli('--video', str(three_by_four), '--inputs', str(tmp_path / 'inputs.json')))['verdict'] == 'pass'
    write_json(tmp_path / 'inputs.json', {'orientation': 'portrait'})
    mismatch_3x4 = parse_result(run_cli('--video', str(three_by_four), '--inputs', str(tmp_path / 'inputs.json')))
    assert mismatch_3x4['verdict'] == 'fail'
    assert any('1080x1920' in f['issue'] and '1080x1440' in f['issue'] for f in mismatch_3x4['findings'])

    nine_by_sixteen = tmp_path / 'portrait_9x16.mp4'
    ffmpeg(
        '-f', 'lavfi', '-i', 'testsrc2=duration=1:size=1080x1920:rate=10',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
        str(nine_by_sixteen),
    )
    write_json(tmp_path / 'inputs.json', {'orientation': 'portrait'})
    assert parse_result(run_cli('--video', str(nine_by_sixteen), '--inputs', str(tmp_path / 'inputs.json')))['verdict'] == 'pass'
    write_json(tmp_path / 'inputs.json', {'orientation': 'portrait-3:4'})
    mismatch_9x16 = parse_result(run_cli('--video', str(nine_by_sixteen), '--inputs', str(tmp_path / 'inputs.json')))
    assert mismatch_9x16['verdict'] == 'fail'
    assert any('1080x1440' in f['issue'] and '1080x1920' in f['issue'] for f in mismatch_9x16['findings'])


def test_missing_video_exits_1(workspace: Path):
    proc = run_cli(
        '--video', str(workspace / 'nope.mp4'),
        '--inputs', str(workspace / 'inputs.json'),
    )
    assert proc.returncode == 1
    result = parse_result(proc)
    assert result['success'] is False
