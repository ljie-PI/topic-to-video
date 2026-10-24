#!/usr/bin/env python3
"""Pipeline status driver: scan a project workspace and report pipeline progress.

The script is the single resume entry point of the topic-to-video pipeline.
It validates every phase's products in the workspace (existence, non-empty,
JSON parseability, required fields) and reports the completed phases, the
next phase to run, the phase doc to read for it, and any missing or corrupt
products. A phase whose product was deleted or corrupted falls back to that
phase.

Usage:
  python3 scripts/pipeline-status.py [workspace_dir]

workspace_dir defaults to the current working directory. Project workspaces
live outside this repo; only the doc paths in the output are repo-relative.

Output: one JSON document on stdout.
Exit codes: 0 = success (a next phase exists, or the pipeline is complete),
1 = runtime error (workspace unreadable), 2 = invalid arguments.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

TOOL_NAME = 'pipeline-status'

SKILL_ROOT = Path(__file__).resolve().parent.parent

INPUTS_REQUIRED_FIELDS = [
    'source',
    'input_mode',
    'duration',
    'language',
    'orientation',
    'template',
    'design',
    'layout',
    'coding_agent',
    'fetch_materials',
    'qa_level',
]

PAPER_MODES = {'paper'}
VALID_INPUT_MODES = {'standard', 'topic', 'article', 'text', 'paper'}


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        log(f'bad arguments: {message}')
        print_json({'success': False, 'error': message})
        raise SystemExit(2)


def log(message: str) -> None:
    print(f'[{TOOL_NAME}] {message}', file=sys.stderr)


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = JsonArgumentParser(
        description='Scan a topic-to-video workspace and report the next pipeline phase.'
    )
    parser.add_argument(
        'workspace',
        nargs='?',
        default='.',
        help='Project workspace directory (default: current working directory).',
    )
    return parser.parse_args()


# --- product checkers ----------------------------------------------------------
#
# Each checker receives the workspace root and returns None when the product is
# valid, or a human-readable reason string when it is missing or corrupt.


def check_file(path: Path) -> str | None:
    if not path.exists():
        return 'missing'
    if not path.is_file():
        return 'not a regular file'
    if path.stat().st_size == 0:
        return 'empty file'
    return None


def check_json(path: Path) -> tuple[str | None, Any]:
    reason = check_file(path)
    if reason is not None:
        return reason, None
    try:
        return None, json.loads(path.read_text(encoding='utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return f'invalid JSON: {exc}', None


def rel(ws: Path, path: Path) -> str:
    return path.relative_to(ws).as_posix()


def check_inputs(ws: Path) -> tuple[str | None, dict[str, Any] | None]:
    reason, data = check_json(ws / 'inputs.json')
    if reason is not None:
        return reason, None
    if not isinstance(data, dict):
        return 'JSON root is not an object', None
    missing = [field for field in INPUTS_REQUIRED_FIELDS if field not in data]
    if missing:
        return f'missing required fields: {", ".join(missing)}', None
    if not isinstance(data['fetch_materials'], bool):
        return 'field fetch_materials is not a boolean', None
    return None, data


def check_paper_metadata(ws: Path) -> str | None:
    path = ws / 'harvest_page' / 'main-paper' / 'metadata.json'
    reason, data = check_json(path)
    if reason is not None:
        return reason
    if not isinstance(data, dict):
        return 'JSON root is not an object'
    if data.get('source_type') != 'paper_pdf':
        return 'field source_type is not "paper_pdf"'
    paper_metadata = data.get('paper_metadata')
    if not isinstance(paper_metadata, dict):
        return 'missing paper_metadata'
    # full_markdown_path is written as an absolute machine-local path by
    # parse-pdf.py; workspaces move between machines, so only require the
    # key to be present with a string or null value.
    if 'full_markdown_path' not in paper_metadata or not (
        isinstance(paper_metadata['full_markdown_path'], str)
        or paper_metadata['full_markdown_path'] is None
    ):
        return 'missing paper_metadata.full_markdown_path'
    return None


def check_research_brief(ws: Path) -> str | None:
    path = ws / 'research-brief.md'
    reason = check_file(path)
    if reason is not None:
        return reason
    if not path.read_text(encoding='utf-8', errors='replace').strip():
        return 'file has no content'
    return None


def check_harvest_manifest(ws: Path) -> str | None:
    reason, data = check_json(ws / 'harvest_page' / 'manifest.json')
    if reason is not None:
        return reason
    if not isinstance(data, dict):
        return 'JSON root is not an object'
    entries = data.get('entries')
    if not isinstance(entries, list) or not entries:
        return 'entries is not a non-empty list'
    return None


def check_material_catalog(ws: Path) -> str | None:
    reason, data = check_json(ws / 'material-catalog.json')
    if reason is not None:
        return reason
    if not isinstance(data, dict):
        return 'JSON root is not an object'
    entries = data.get('entries')
    if not isinstance(entries, list) or not entries:
        return 'entries is not a non-empty list'
    return None


def check_narration(ws: Path) -> str | None:
    path = ws / 'narration.txt'
    reason = check_file(path)
    if reason is not None:
        return reason
    if not path.read_text(encoding='utf-8', errors='replace').strip():
        return 'file has no content'
    return None


def check_json_list(path: Path, label: str) -> str | None:
    reason, data = check_json(path)
    if reason is not None:
        return reason
    if not isinstance(data, list) or not data:
        return f'{label} is not a non-empty list'
    return None


def check_scene_suggestions(ws: Path) -> str | None:
    return check_json_list(ws / 'scene-material-suggestions.json', 'JSON root')


def check_scene_text_plan(ws: Path) -> str | None:
    return check_json_list(ws / 'scene-text-plan.json', 'JSON root')


def check_transcript(ws: Path) -> str | None:
    path = ws / 'transcribe' / 'transcript.json'
    reason, data = check_json(path)
    if reason is not None:
        return reason
    if not isinstance(data, list) or not data:
        return 'transcript is not a non-empty sentence list'
    for index, sentence in enumerate(data):
        if not isinstance(sentence, dict):
            return f'sentence {index} is not an object'
        missing = [
            field
            for field in ('begin', 'end', 'text', 'words')
            if field not in sentence
        ]
        if missing:
            return f'sentence {index} missing fields: {", ".join(missing)}'
        if not isinstance(sentence['words'], list):
            return f'sentence {index} words is not a list'
    return None


def check_subtitle_units(ws: Path) -> str | None:
    reason, data = check_json(ws / 'transcribe' / 'subtitle-units.json')
    if reason is not None:
        return reason
    if not isinstance(data, dict):
        return 'JSON root is not an object'
    units = data.get('units')
    if not isinstance(units, list) or not units:
        return 'units is not a non-empty list'
    return None


def check_final_mp4(ws: Path) -> str | None:
    return check_file(ws / 'composition' / 'renders' / 'final.mp4')


def check_final_with_bgm(ws: Path) -> str | None:
    return check_file(ws / 'composition' / 'renders' / 'final_with_bgm.mp4')


# --- phase definitions ---------------------------------------------------------

# Each product maps its workspace-relative path to a checker.
PHASES: list[dict[str, Any]] = [
    {
        'id': '1-gather-inputs',
        'title': '收集输入',
        'doc': 'references/phases/01-gather-inputs.md',
        'products': {'inputs.json': check_inputs},
    },
    {
        'id': '2-paper-parse',
        'title': '解析论文（仅论文模式）',
        'doc': 'references/phases/02-paper-parse.md',
        'conditional': 'paper',
        'products': {'harvest_page/main-paper/metadata.json': check_paper_metadata},
    },
    {
        'id': '3-research',
        'title': '主题调研',
        'doc': 'references/phases/03-research.md',
        'products': {'research-brief.md': check_research_brief},
    },
    {
        'id': '4-material-harvest',
        'title': '素材抓取（可选）',
        'doc': 'references/phases/04-material-harvest.md',
        'conditional': 'fetch',
        'products': {'harvest_page/manifest.json': check_harvest_manifest},
    },
    {
        'id': '5-material-catalog',
        'title': '素材 catalog',
        'doc': 'references/phases/05-material-catalog.md',
        'conditional': 'fetch',
        'products': {'material-catalog.json': check_material_catalog},
    },
    {
        'id': '6-script-scene-plan',
        'title': '脚本与场景规划（委派）',
        'doc': 'references/phases/06-script-scene-plan.md',
        'products': {
            'narration.txt': check_narration,
            'scene-material-suggestions.json': check_scene_suggestions,
            'scene-text-plan.json': check_scene_text_plan,
        },
    },
    {
        'id': '7-tts',
        'title': 'TTS 配音',
        'doc': 'references/phases/07-tts.md',
        'products': {'voice_clone/narration.mp3': check_file},
    },
    {
        'id': '8-align-subtitles',
        'title': '对齐与字幕',
        'doc': 'references/phases/08-align-subtitles.md',
        'products': {
            'transcribe/transcript.json': check_transcript,
            'transcribe/subtitle-units.json': check_subtitle_units,
        },
    },
    {
        'id': '9-composition',
        'title': 'composition（委派）',
        'doc': 'references/phases/09-composition.md',
        'products': {'composition/renders/final.mp4': check_final_mp4},
    },
    {
        'id': '10-check-mix',
        'title': '检查与混音',
        'doc': 'references/phases/10-check-mix.md',
        'products': {'composition/renders/final_with_bgm.mp4': check_final_with_bgm},
    },
]


def phase_applies(phase: dict[str, Any], inputs: dict[str, Any] | None) -> bool:
    conditional = phase.get('conditional')
    if conditional is None:
        return True
    if inputs is None:
        # inputs.json unreadable: report the full default sequence (standard,
        # with fetching). The next phase will be 1-gather-inputs anyway.
        return conditional == 'fetch'
    if conditional == 'paper':
        return inputs.get('input_mode') in PAPER_MODES
    if conditional == 'fetch':
        return bool(inputs.get('fetch_materials'))
    return True


def validate_phase(ws: Path, phase: dict[str, Any]) -> dict[str, str]:
    problems: dict[str, str] = {}
    for relpath, checker in phase['products'].items():
        if checker is check_file:
            reason = checker(ws / relpath)
        elif checker is check_inputs:
            reason, _ = checker(ws)
        else:
            reason = checker(ws)
        if reason is not None:
            problems[relpath] = reason
    return problems


def scan_workspace(ws: Path) -> dict[str, Any]:
    inputs_reason, inputs = check_inputs(ws)

    completed: list[str] = []
    skipped: list[str] = []
    missing: list[str] = []
    corrupt: list[str] = []
    next_phase: dict[str, Any] | None = None

    for phase in PHASES:
        if not phase_applies(phase, inputs):
            skipped.append(phase['id'])
            continue
        problems = validate_phase(ws, phase)
        if not problems:
            completed.append(phase['id'])
            continue
        for relpath, reason in problems.items():
            if reason == 'missing':
                missing.append(relpath)
            else:
                corrupt.append(relpath)
        if next_phase is None:
            next_phase = {
                'id': phase['id'],
                'title': phase['title'],
                'doc': phase['doc'],
                'problems': problems,
            }

    return {
        'success': True,
        'workspace': str(ws.resolve()),
        'input_mode': inputs.get('input_mode') if inputs else None,
        'fetch_materials': inputs.get('fetch_materials') if inputs else None,
        'completed_phases': completed,
        'skipped_phases': skipped,
        'next_phase': next_phase,
        'missing_products': missing,
        'corrupt_products': corrupt,
    }


def main() -> int:
    args = parse_args()
    ws = Path(args.workspace)
    try:
        if not ws.exists():
            raise FileNotFoundError(f'workspace does not exist: {ws}')
        if not ws.is_dir():
            raise NotADirectoryError(f'workspace is not a directory: {ws}')
        result = scan_workspace(ws)
        print_json(result)
        if result['next_phase'] is None:
            log('all phases complete')
        else:
            log(f"next phase: {result['next_phase']['id']} -> {result['next_phase']['doc']}")
        return 0
    except (OSError, FileNotFoundError, NotADirectoryError) as exc:
        log(f'error: {exc}')
        print_json({'success': False, 'error': str(exc)})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
