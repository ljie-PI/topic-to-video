"""Shared ffmpeg/ffprobe invocation and metadata helpers."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any


class MediaToolMissing(FileNotFoundError):
    """A required media binary cannot be found."""


class MediaProbeError(RuntimeError):
    """A media file could not be probed."""


class FfmpegError(RuntimeError):
    """An ffmpeg process exited unsuccessfully."""

    def __init__(self, command: Sequence[str], returncode: int, stderr: str | None) -> None:
        self.command = list(command)
        self.returncode = returncode
        self.stderr_tail = (stderr or '')[-2000:]
        detail = self.stderr_tail.strip() or '(no stderr)'
        super().__init__(f'ffmpeg failed (exit={returncode}): {detail}')


def ensure_binary(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise MediaToolMissing(f'{name} is not installed or not available on PATH')
    return executable


def _executable(override: str | None, env_name: str, default: str) -> str:
    name = override if override is not None else os.environ.get(env_name, default)
    return ensure_binary(name)


def ensure_media_binaries() -> None:
    _executable(None, 'FFMPEG_BIN', 'ffmpeg')
    _executable(None, 'FFPROBE_BIN', 'ffprobe')


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def probe(
    path: str | Path,
    *,
    timeout: float = 30,
    ffprobe: str | None = None,
) -> dict[str, object]:
    executable = _executable(ffprobe, 'FFPROBE_BIN', 'ffprobe')
    command = [
        executable,
        '-v', 'error',
        '-show_entries', 'format=duration:stream=codec_type,width,height,duration',
        '-of', 'json',
        os.fspath(path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise MediaToolMissing(f'{executable} is not installed or not available on PATH') from exc
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise MediaProbeError(f'ffprobe failed for {path}: {exc}') from exc
    if result.returncode != 0:
        detail = (result.stderr or '').strip()[-2000:]
        raise MediaProbeError(f'ffprobe failed for {path}: {detail or "unknown error"}')
    try:
        data = json.loads(result.stdout or '{}')
    except json.JSONDecodeError as exc:
        raise MediaProbeError(f'ffprobe returned invalid JSON for {path}: {exc}') from exc
    if not isinstance(data, dict):
        raise MediaProbeError(f'ffprobe returned invalid metadata for {path}')

    streams = data.get('streams') or []
    video_stream = next((s for s in streams if s.get('codec_type') == 'video'), {})
    audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    return {
        'duration_seconds': _float_or_none((data.get('format') or {}).get('duration')),
        'width': _int_or_none(video_stream.get('width')),
        'height': _int_or_none(video_stream.get('height')),
        'has_audio': audio_stream is not None,
        'audio_duration_seconds': (
            _float_or_none(audio_stream.get('duration')) if audio_stream is not None else None
        ),
    }


def probe_duration(
    path: str | Path,
    *,
    timeout: float = 30,
    ffprobe: str | None = None,
) -> float:
    duration = probe(path, timeout=timeout, ffprobe=ffprobe)['duration_seconds']
    if duration is None or duration <= 0:
        raise MediaProbeError(f'invalid or unavailable media duration for {path}: {duration}')
    return duration


def run_ffmpeg(
    args: Sequence[str | os.PathLike[str]],
    *,
    timeout: float,
    ffmpeg: str | None = None,
) -> subprocess.CompletedProcess[str]:
    executable = _executable(ffmpeg, 'FFMPEG_BIN', 'ffmpeg')
    command = [executable, *(os.fspath(arg) for arg in args)]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise MediaToolMissing(f'{executable} is not installed or not available on PATH') from exc
    if result.returncode != 0:
        raise FfmpegError(command, result.returncode, result.stderr)
    return result
