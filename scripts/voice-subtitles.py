#!/usr/bin/env python3
"""Run Phase 7 voice synthesis and subtitle alignment for one workspace.

Usage:
  python3 scripts/voice-subtitles.py <workspace> [--backend <name>]
  python3 scripts/voice-subtitles.py <workspace> --align-only

The workspace supplies narration.txt, narration-offsets.json, script.txt and
inputs.json (whose layout selects modules/layouts/<layout>.json). An existing
scene-plan.json is passed to the aligner automatically. stdout is one JSON
result; child-process diagnostics remain on stderr and child error JSON is
returned under "child" with failed_step "tts" or "align".
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import cli

TOOL_NAME = 'voice-subtitles'
SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / 'scripts'
log = cli.make_logger(TOOL_NAME)


class ChildFailure(RuntimeError):
    def __init__(self, step: str, child: dict[str, Any]) -> None:
        self.step = step
        self.child = child
        super().__init__(str(child.get('error') or f'{step} subprocess failed'))


def parse_args() -> argparse.Namespace:
    parser = cli.JsonArgumentParser(
        TOOL_NAME,
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('workspace', help='Project workspace directory')
    parser.add_argument('--backend', default=None, help='TTS backend passed to voice-clone.py')
    parser.add_argument(
        '--align-only',
        action='store_true',
        help='Skip TTS and rebuild subtitles/timeline from the existing transcript',
    )
    return parser.parse_args()


def require_nonempty(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f'required input is missing: {path}')
    if not path.read_bytes().strip():
        raise ValueError(f'required input is empty: {path}')


def read_layout(workspace: Path) -> str:
    inputs_path = workspace / 'inputs.json'
    require_nonempty(inputs_path)
    try:
        inputs = json.loads(inputs_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f'cannot read {inputs_path}: {exc}') from exc
    if not isinstance(inputs, dict) or not isinstance(inputs.get('layout'), str):
        raise ValueError(f'{inputs_path} must contain a string layout field')
    layout = inputs['layout'].strip()
    if not layout:
        raise ValueError(f'{inputs_path} has an empty layout field')
    for name in ('narration.txt', 'narration-offsets.json', 'script.txt'):
        require_nonempty(workspace / name)
    return layout


def parse_child_json(stdout: str) -> dict[str, Any] | None:
    """Use the last JSON object, tolerating third-party stray stdout lines."""
    for line in reversed([line for line in stdout.splitlines() if line.strip()]):
        try:
            result = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(result, dict):
            return result
    return None


def run_child(step: str, command: list[str]) -> dict[str, Any]:
    script_name = Path(command[1]).name
    log(f'running {script_name} ({step})')
    proc = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.stderr:
        sys.stderr.write(proc.stderr)
        sys.stderr.flush()
    child = parse_child_json(proc.stdout)
    if proc.returncode != 0 or child is None or child.get('success') is not True:
        if child is None:
            child = {
                'success': False,
                'error': f'{script_name} exited {proc.returncode} without a JSON result',
            }
        raise ChildFailure(step, child)
    return child


def warnings_from(result: dict[str, Any]) -> list[Any]:
    warnings = result.get('warnings')
    if isinstance(warnings, list):
        return warnings
    summary = result.get('summary')
    if isinstance(summary, dict) and isinstance(summary.get('warnings'), list):
        return summary['warnings']
    return []


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    try:
        layout = read_layout(workspace)
    except (OSError, ValueError) as exc:
        cli.fail(
            TOOL_NAME,
            str(exc),
            failed_step='inputs',
            log_message=f'error (inputs): {exc}',
        )

    transcript = workspace / 'transcribe' / 'transcript.json'
    warnings: list[Any] = []
    backend = args.backend or os.environ.get('TTS_BACKEND') or 'auto'
    transcript_method = None
    try:
        if not args.align_only:
            tts_command = [
                sys.executable,
                str(SCRIPTS_DIR / 'voice-clone.py'),
                '--input-file', str(workspace / 'narration.txt'),
                '--output-dir', str(workspace / 'voice_clone'),
                '--transcript-output', str(transcript),
                '--emit-transcript',
            ]
            if args.backend is not None:
                tts_command += ['--backend', args.backend]
            tts = run_child('tts', tts_command)
            backend = tts.get('backend', backend)
            transcript_method = tts.get('transcript_method')
            warnings.extend(warnings_from(tts))

        align_command = [
            sys.executable,
            str(SCRIPTS_DIR / 'align-narration.py'),
            '--transcript', str(transcript),
            '--narration', str(workspace / 'narration.txt'),
            '--offsets', str(workspace / 'narration-offsets.json'),
            '--script', str(workspace / 'script.txt'),
            '--units-output', str(workspace / 'transcribe' / 'subtitle-units.json'),
            '--timeline-output', str(workspace / 'transcribe' / 'timeline.json'),
            '--layout', str(SKILL_ROOT / 'modules' / 'layouts' / f'{layout}.json'),
        ]
        scene_plan = workspace / 'scene-plan.json'
        if scene_plan.is_file():
            align_command += ['--scene-plan', str(scene_plan)]
        aligned = run_child('align', align_command)
        warnings.extend(warnings_from(aligned))
    except ChildFailure as exc:
        cli.fail(
            TOOL_NAME,
            str(exc),
            failed_step=exc.step,
            extra={'child': exc.child},
            log_message=f'error ({exc.step}): {exc}',
        )

    cli.print_json(
        {
            'success': True,
            'backend': backend,
            'transcript_method': transcript_method,
            'products': {
                'audio': str((workspace / 'voice_clone' / 'narration.mp3').resolve()),
                'transcript': str(transcript.resolve()),
                'subtitle_units': str((workspace / 'transcribe' / 'subtitle-units.json').resolve()),
                'timeline': str((workspace / 'transcribe' / 'timeline.json').resolve()),
            },
            'warnings': warnings,
        }
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
