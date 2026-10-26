"""Direct-import tests for the shared ffmpeg/ffprobe helpers."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import cli
import media


pytestmark = pytest.mark.usefixtures('require_ffmpeg')


@pytest.fixture(scope='module')
def clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp('media') / 'clip.mp4'
    subprocess.run(
        [
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', 'testsrc=duration=1:size=320x240:rate=25',
            '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
            '-shortest', str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return path


def failing_ffmpeg(path: Path) -> Path:
    path.write_text(
        f'#!{sys.executable}\n'
        'import sys\n'
        "sys.stderr.write('x' * 2500)\n"
        'raise SystemExit(7)\n',
        encoding='utf-8',
    )
    path.chmod(0o755)
    return path


def test_probe_returns_container_video_and_audio_metadata(clip: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv('FFPROBE_BIN', raising=False)

    result = media.probe(clip)

    assert set(result) == {
        'duration_seconds', 'width', 'height', 'has_audio', 'audio_duration_seconds',
    }
    assert result['duration_seconds'] == pytest.approx(1.0, abs=0.1)
    assert result['width'] == 320
    assert result['height'] == 240
    assert result['has_audio'] is True
    assert result['audio_duration_seconds'] == pytest.approx(1.0, abs=0.1)
    assert media.probe_duration(clip) == pytest.approx(1.0, abs=0.1)


def test_probe_nonexistent_file_raises_media_probe_error(tmp_path: Path):
    missing = tmp_path / 'nonexistent.mp4'
    with pytest.raises(media.MediaProbeError):
        media.probe(missing)
    with pytest.raises(media.MediaProbeError):
        media.probe_duration(missing)


def test_ffprobe_environment_override_missing_raises_media_tool_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('FFPROBE_BIN', '/nonexistent')
    with pytest.raises(media.MediaToolMissing):
        media.probe(tmp_path / 'clip.mp4')


def test_explicit_ffprobe_overrides_environment(clip: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('FFPROBE_BIN', '/nonexistent')
    result = media.probe(clip, ffprobe=shutil.which('ffprobe'))
    assert result['width'] == 320


def test_run_ffmpeg_returns_completed_process(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('FFMPEG_BIN', '/nonexistent')
    result = media.run_ffmpeg(['-version'], ffmpeg=shutil.which('ffmpeg'), timeout=30)
    assert isinstance(result, subprocess.CompletedProcess)
    assert result.returncode == 0


def test_run_ffmpeg_failure_raises_with_stderr_tail(tmp_path: Path):
    executable = failing_ffmpeg(tmp_path / 'ffmpeg-fail')
    with pytest.raises(media.FfmpegError) as caught:
        media.run_ffmpeg([], ffmpeg=str(executable), timeout=30)
    assert caught.value.stderr_tail == 'x' * 2000


def test_cli_run_includes_ffmpeg_stderr_tail_in_error_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    executable = failing_ffmpeg(tmp_path / 'ffmpeg-fail')

    def main() -> None:
        media.run_ffmpeg([], ffmpeg=str(executable), timeout=30)

    assert cli.run(main, 'media-test') == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload['success'] is False
    assert payload['stderr_tail'] == 'x' * 2000
