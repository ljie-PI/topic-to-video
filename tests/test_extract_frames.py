"""CLI integration tests for scripts/extract-frames.py."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.usefixtures('require_ffmpeg')

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'extract-frames.py'
FRAME_NAME = re.compile(r'frame_t(\d{4}\.\d{2})s\.jpg')


def test_frames_have_timestamped_names_and_absolute_timed_paths(tmp_path: Path):
    video = tmp_path / 'input.mp4'
    subprocess.run(
        [
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', 'testsrc=duration=4:size=160x120:rate=25',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output_dir = tmp_path / 'frames'

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(video), str(output_dir), '--max-frames', '4'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result['frame_count'] == 4
    assert result['interval_s'] > 0
    timestamps = []
    for frame in result['frames']:
        path = Path(frame['path'])
        assert path.is_absolute()
        assert path.is_file()
        match = FRAME_NAME.fullmatch(path.name)
        assert match is not None
        assert frame['t_s'] == pytest.approx(float(match.group(1)))
        timestamps.append(frame['t_s'])
    assert timestamps == sorted(timestamps)
    assert len(set(timestamps)) == len(timestamps)


@pytest.mark.parametrize(
    ('start_time', 'end_time'),
    [('00:00:01.50', '00:00:03.50'), ('00:01.50', '00:03.50')],
)
def test_frame_timestamps_include_the_start_time(tmp_path: Path, start_time: str, end_time: str):
    video = tmp_path / 'input.mp4'
    subprocess.run(
        [
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', 'testsrc=duration=4:size=160x120:rate=25',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    proc = subprocess.run(
        [
            sys.executable, str(SCRIPT), str(video), str(tmp_path / 'frames'),
            '--start-time', start_time, '--end-time', end_time,
            '--max-frames', '2',
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert [frame['t_s'] for frame in result['frames']] == [1.5, 2.5]
    assert result['interval_s'] == 1.0


@pytest.mark.parametrize('binary_env', ['FFMPEG_BIN', 'FFPROBE_BIN'])
def test_missing_media_binary_preserves_existing_frames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, binary_env: str
):
    video = tmp_path / 'input.mp4'
    subprocess.run(
        [
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', 'testsrc=duration=4:size=160x120:rate=25',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output_dir = tmp_path / 'frames'
    output_dir.mkdir()
    existing = output_dir / 'frame_existing.jpg'
    existing.write_bytes(b'pre-existing frame')
    monkeypatch.setenv(binary_env, '/nonexistent')

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(video), str(output_dir)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert proc.returncode == 1
    assert existing.read_bytes() == b'pre-existing frame'
