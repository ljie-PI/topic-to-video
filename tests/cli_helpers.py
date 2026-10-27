"""Small subprocess helpers shared by CLI test suites."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


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
