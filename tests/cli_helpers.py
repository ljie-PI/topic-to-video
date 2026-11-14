"""Small subprocess, module-loading, and cached-media helpers shared by CLI test suites."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / 'scripts'
_SILENT_MP3_CACHE: dict[tuple[float, int], bytes] = {}


def load_script_module(script_filename: str, module_alias: str | None = None) -> ModuleType:
    """Import a hyphenated script under scripts/ without spawning a subprocess."""
    name = module_alias or ('script_' + script_filename.replace('-', '_').replace('.py', ''))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / script_filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def silent_mp3_bytes(duration_s: float, sample_rate: int = 48000) -> bytes:
    """Build a silent MP3 once per (duration_s, sample_rate) in the test session."""
    key = (float(duration_s), sample_rate)
    if key not in _SILENT_MP3_CACHE:
        missing = [tool for tool in ('ffmpeg', 'ffprobe') if shutil.which(tool) is None]
        if missing:
            pytest.fail(f'missing required dependency: {", ".join(missing)} (system package)', pytrace=False)
        proc = subprocess.run(
            [
                'ffmpeg', '-hide_banner', '-loglevel', 'error',
                '-f', 'lavfi', '-i', f'anullsrc=r={sample_rate}:cl=mono',
                '-t', str(duration_s), '-c:a', 'libmp3lame', '-f', 'mp3', 'pipe:1',
            ],
            capture_output=True,
            check=True,
            timeout=30,
        )
        _SILENT_MP3_CACHE[key] = proc.stdout
    return _SILENT_MP3_CACHE[key]


def write_silent_mp3(path: Path, duration_s: float, sample_rate: int = 48000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(silent_mp3_bytes(duration_s, sample_rate=sample_rate))


def run_cli(
    script: Path,
    *args: str,
    env: dict[str, str],
    blocked: tuple[str, ...] = (),
    blocked_prefixes: tuple[str, ...] = (),
    timeout: int = 60,
) -> subprocess.CompletedProcess:
    clean = {
        key: value for key, value in os.environ.items()
        if key not in blocked and not key.startswith(blocked_prefixes)
    }
    clean.update(env)
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        env=clean,
        timeout=timeout,
    )


def parse_stdout(proc: subprocess.CompletedProcess) -> dict:
    """Require exactly one JSON result line, matching the CLI contract."""
    assert len(proc.stdout.splitlines()) == 1, proc.stdout
    return json.loads(proc.stdout)
