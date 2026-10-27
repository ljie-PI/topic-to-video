"""End-to-end tests for mix-bgm.py using real ffmpeg streams."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cli_helpers import parse_stdout, run_cli

pytestmark = pytest.mark.usefixtures('require_ffmpeg')

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'mix-bgm.py'


def _ffmpeg(*args: str) -> None:
    subprocess.run(
        ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _streams(path: Path) -> list[dict]:
    proc = subprocess.run(
        [
            'ffprobe', '-v', 'error', '-show_entries',
            'stream=codec_type,codec_name:format=duration', '-of', 'json', str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(proc.stdout)['streams']


def _duration(path: Path) -> float:
    proc = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return float(json.loads(proc.stdout)['format']['duration'])


@pytest.fixture(scope='module')
def media_files(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    root = tmp_path_factory.mktemp('mix-bgm')
    video = root / 'narrated.mp4'
    bgm = root / 'bgm.mp3'
    _ffmpeg(
        '-f', 'lavfi', '-i', 'testsrc=duration=3:size=160x120:rate=25',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=3',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(video),
    )
    _ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=880:duration=1', '-c:a', 'libmp3lame', str(bgm))
    return video, bgm


def run_mix(*args: str) -> subprocess.CompletedProcess:
    return run_cli(SCRIPT, *args, env={})


def test_bgm_is_looped_and_muxed_without_changing_video_duration_or_codec(
    tmp_path: Path, media_files: tuple[Path, Path]
):
    video, bgm = media_files
    output = tmp_path / 'nested' / 'with-bgm.mp4'

    proc = run_mix(
        '--video', str(video), '--bgm', str(bgm), '--bgm-volume', '0.1', '--output', str(output)
    )

    assert proc.returncode == 0, proc.stderr
    result = parse_stdout(proc)
    assert result['success'] is True
    assert result['output_path'] == str(output.resolve())
    assert result['bgm_path'] == str(bgm.resolve())
    assert result['duration_s'] == pytest.approx(3.0, abs=0.15)
    assert _duration(output) == pytest.approx(_duration(video), abs=0.15)

    input_video = next(stream for stream in _streams(video) if stream['codec_type'] == 'video')
    output_streams = _streams(output)
    output_video = next(stream for stream in output_streams if stream['codec_type'] == 'video')
    assert output_video['codec_name'] == input_video['codec_name']
    assert any(stream['codec_type'] == 'audio' for stream in output_streams)


def test_volume_outside_unit_interval_is_a_usage_error(tmp_path: Path, media_files: tuple[Path, Path]):
    video, bgm = media_files
    proc = run_mix(
        '--video', str(video), '--bgm', str(bgm), '--bgm-volume', '1.1',
        '--output', str(tmp_path / 'out.mp4'),
    )

    assert proc.returncode == 2
    assert parse_stdout(proc)['success'] is False


def test_missing_video_is_a_runtime_error(tmp_path: Path, media_files: tuple[Path, Path]):
    _, bgm = media_files
    proc = run_mix(
        '--video', str(tmp_path / 'missing.mp4'), '--bgm', str(bgm),
        '--output', str(tmp_path / 'out.mp4'),
    )

    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert '--video not found' in result['error']


def test_missing_bgm_is_a_runtime_error(tmp_path: Path, media_files: tuple[Path, Path]):
    video, _ = media_files
    proc = run_mix(
        '--video', str(video), '--bgm', str(tmp_path / 'missing.mp3'),
        '--output', str(tmp_path / 'out.mp4'),
    )

    assert proc.returncode == 1
    result = parse_stdout(proc)
    assert result['success'] is False
    assert '--bgm not found' in result['error']
