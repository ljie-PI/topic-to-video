#!/usr/bin/env python3
"""Prepare the handoff of a delegated step: materialize its package, fill the handoff.

The main agent delegates the script (Phase 6) and composition (Phase 8) steps
to a coding agent, which reads a handoff file. The handoff is deterministic,
so this script generates it instead of the main agent filling a prose
template by hand. Per call it does three things:

  1. Materialize: copy references/delegation/conventions.md and
     references/delegation/<step>/ into <ws>/references/delegation/; the
     composition step also copies modules/ (without examples/) into
     <ws>/modules/. A file that already exists in the workspace is kept
     (the copy may have been edited); --refresh overwrites it.
  2. Fonts (composition only): install the selected design's vendored WOFF2
     fonts into <ws>/composition/assets/fonts/ with scripts/fonts-download.sh
     (no network). Runs on every call.
  3. Handoff: read the markdown code block of
     references/delegation/<step>/handoff-template.md, replace its {{name}}
     placeholders and write <ws>/<step>-handoff.md. All paths in it are
     absolute; commands run the skill's scripts from the skill root. A
     placeholder left unreplaced, or an input or reference file that does not
     exist, is an error.

Usage:
  python3 scripts/prepare-handoff.py <workspace_dir> <script|composition> [--refresh]

Output: one JSON document on stdout,
  {"success": true, "handoff_path": "...", "materialized": [...],
   "fonts": null | {fonts-download output},
   "dispatch_prompt": "读取 <handoff> 并按它执行；完成后报告产物路径。"}
materialized lists the package paths this call wrote files into. The main
agent dispatches dispatch_prompt verbatim. If fonts-download fails the output
is {"success": false, "error": "...", "fonts": {fonts-download's error JSON}}.
Exit codes: 0 = success, 1 = runtime error, 2 = invalid arguments.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cli

TOOL_NAME = 'prepare-handoff'

SKILL_ROOT = Path(__file__).resolve().parent.parent

STEPS = ['script', 'composition']

DELEGATION = Path('references') / 'delegation'

PLACEHOLDER = re.compile(r'\{\{\s*([a-z_]+)\s*\}\}')
TEMPLATE_BLOCK = re.compile(r'^```markdown\n(.*?)^```$', re.MULTILINE | re.DOTALL)
NAME = re.compile(r'^[\w-]+$')

INPUTS_FIELDS = ['coding_agent', 'duration', 'language', 'input_mode', 'template', 'design', 'layout', 'orientation', 'fetch_materials']

log = cli.make_logger(TOOL_NAME)


class FontsError(Exception):
    """fonts-download.sh failed; payload is its JSON (or a stand-in for it)."""

    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__(str(payload.get('error') or 'fonts-download failed'))
        self.payload = payload


def parse_args() -> argparse.Namespace:
    parser = cli.JsonArgumentParser(
        TOOL_NAME,
        description='Materialize the delegation package of a step and generate its handoff.',
    )
    parser.add_argument('workspace', help='Project workspace directory ({work_dir}/{topic_name}).')
    parser.add_argument('step', choices=STEPS, help='Delegated step to prepare.')
    parser.add_argument(
        '--refresh',
        action='store_true',
        help='Overwrite package files that already exist in the workspace.',
    )
    return parser.parse_args()


# --- inputs ---------------------------------------------------------------------


def load_inputs(ws: Path) -> dict[str, Any]:
    path = ws / 'inputs.json'
    if not path.is_file():
        raise FileNotFoundError(f'inputs.json not found in {ws}')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'inputs.json is not valid JSON: {exc}') from exc
    if not isinstance(data, dict):
        raise ValueError('inputs.json root is not an object')
    missing = [name for name in INPUTS_FIELDS if name not in data]
    if missing:
        raise ValueError(f'inputs.json is missing fields: {", ".join(missing)}')
    for name in ('design', 'layout', 'template'):
        value = data[name]
        if value is not None and not (isinstance(value, str) and NAME.match(value)):
            raise ValueError(f'inputs.json field {name} must be a plain name, got {value!r}')
    return data


def duration_text(duration: Any) -> str:
    return f'{duration} 分钟' if isinstance(duration, (int, float)) else str(duration)


# --- materialize ------------------------------------------------------------------


def copy_missing(source: Path, target: Path, refresh: bool, skip: tuple[str, ...] = ()) -> bool:
    """Copy a file or directory tree; existing files are kept unless refresh.

    skip names top-level entries of a directory source that are left out.
    Returns whether any file was written.
    """
    if source.is_file():
        pairs = [(source, target)]
    else:
        pairs = [
            (file, target / file.relative_to(source))
            for file in sorted(source.rglob('*'))
            if file.is_file() and file.relative_to(source).parts[0] not in skip
        ]
    wrote = False
    for file, destination in pairs:
        if destination.exists() and not refresh:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, destination)
        wrote = True
    return wrote


def materialize(ws: Path, step: str, refresh: bool) -> list[str]:
    """Copy the step's package into the workspace; returns the paths written into."""
    units: list[tuple[Path, Path, tuple[str, ...]]] = [
        (SKILL_ROOT / DELEGATION / 'conventions.md', ws / DELEGATION / 'conventions.md', ()),
        (SKILL_ROOT / DELEGATION / step, ws / DELEGATION / step, ()),
    ]
    if step == 'composition':
        units.append((SKILL_ROOT / 'modules', ws / 'modules', ('examples',)))
    written = []
    for source, target, skip in units:
        if copy_missing(source, target, refresh, skip):
            written.append(str(target))
            log(f'materialized {target}')
    return written


def install_fonts(ws: Path, design: str) -> dict[str, Any]:
    """Run fonts-download.sh for the selected design; returns its JSON output."""
    target = ws / 'composition' / 'assets' / 'fonts'
    proc = subprocess.run(
        [
            'bash',
            str(SKILL_ROOT / 'scripts' / 'fonts-download.sh'),
            str(target),
            '--theme',
            str(SKILL_ROOT / 'modules' / 'designs' / design),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.stderr:
        print(proc.stderr, end='', file=sys.stderr)
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        payload = {'success': False, 'error': proc.stderr.strip()[-500:] or 'fonts-download printed no JSON'}
    if proc.returncode != 0 or payload.get('success') is not True:
        raise FontsError(payload)
    return payload


# --- handoff ----------------------------------------------------------------------


@dataclass
class Plan:
    """What a step contributes to its handoff.

    values fill the step's placeholders; inputs are workspace files the
    handoff reads (they must exist before anything is written); references
    are the package and module files it points at (they must exist once the
    package is materialized).
    """

    values: dict[str, str]
    inputs: list[Path] = field(default_factory=list)
    references: list[Path] = field(default_factory=list)


Reference = tuple[str, list[Path]]


def numbered(items: list[str]) -> str:
    return '\n'.join(f'{number}. {item}' for number, item in enumerate(items, 1))


def instruction_list(ws: Path, *names: str) -> str:
    files = [ws / name for name in names if (ws / name).is_file()]
    return '\n'.join(f'- {file}' for file in files) if files else 'None'


def script_plan(ws: Path, inputs: dict[str, Any]) -> Plan:
    template = inputs['template']
    delegation = ws / DELEGATION
    base = delegation / 'script' / 'base-instructions.md'
    references: list[Reference] = [(f'{base}（基础指令：叙事结构、写法要求、产物 schema）', [base])]
    if template:
        template_dir = SKILL_ROOT / 'modules' / 'templates' / template
        if not template_dir.is_dir():
            raise FileNotFoundError(f'template {template!r} not found: {template_dir}')
        # A template without narration requirements contributes no item.
        narration = template_dir / 'narration.md'
        if narration.is_file():
            references.append((f'{narration}（所选模板 {template} 的旁白要求）', [narration]))
    plan = Plan(
        values={
            'required_references': numbered([text for text, _ in references]),
            'additional_instructions': instruction_list(ws, 'narration-instructions.md'),
        },
        inputs=[ws / 'inputs.json', ws / 'research-brief.md'],
        references=[delegation / 'conventions.md', *(path for _, paths in references for path in paths)],
    )
    if inputs['fetch_materials']:
        catalog_doc = SKILL_ROOT / 'references' / 'phases' / '05-material-catalog.md'
        plan.values['material_catalog'] = f'{ws / "material-catalog.json"}（素材 id 引用格式的定义见 {catalog_doc}）'
        plan.inputs.append(ws / 'material-catalog.json')
        plan.references.append(catalog_doc)
    else:
        plan.values['material_catalog'] = '无（fetch_materials = false，没有素材）'
    return plan


def composition_plan(ws: Path, inputs: dict[str, Any]) -> Plan:
    design, layout, template = inputs['design'], inputs['layout'], inputs['template']
    delegation = ws / DELEGATION
    modules = ws / 'modules'
    base = delegation / 'composition' / 'base-instructions.md'
    modules_doc = modules / 'modules.md'
    design_doc = modules / 'designs' / design / f'{design}.md'
    design_contract = modules / 'designs' / 'designs.md'
    layout_json = modules / 'layouts' / f'{layout}.json'
    layout_doc = modules / 'layouts' / f'{layout}.md'
    references: list[Reference] = [
        (f'{base}（基础指令：输入契约、design、layout 区域、工作顺序）', [base]),
        (f'{modules_doc}（模块库入口与组装约定）', [modules_doc]),
        (f'{design_doc}（所选 design；token 契约见 {design_contract}）', [design_doc, design_contract]),
        (f'{layout_json} + {layout_doc}（所选 layout 的区域定义）', [layout_json, layout_doc]),
    ]
    if template:
        template_doc = modules / 'templates' / template / f'{template}.md'
        references.append((f'{template_doc}（所选模板的组装说明，及其场景 / 组件文档）', [template_doc]))
    patterns, components = modules / 'patterns', modules / 'components'
    references.append((f'按 storyboard 需要，自行阅读 {patterns}/、{components}/ 下的文档', [patterns, components]))
    plan = Plan(
        values={
            'required_references': numbered([text for text, _ in references]),
            'additional_instructions': instruction_list(ws, 'composition-instructions.md', 'style-prompt.md'),
            'design': design,
            'layout': layout,
            'orientation': str(inputs['orientation']),
        },
        inputs=[
            ws / 'inputs.json',
            ws / 'voice_clone' / 'narration.mp3',
            ws / 'transcribe' / 'subtitle-units.json',
            ws / 'transcribe' / 'timeline.json',
            ws / 'scene-plan.json',
            ws / 'script.txt',
        ],
        references=[
            delegation / 'conventions.md',
            ws / 'composition' / 'assets' / 'fonts',
            *(path for _, paths in references for path in paths),
        ],
    )
    if inputs['fetch_materials']:
        plan.values['material_catalog'] = str(ws / 'material-catalog.json')
        plan.inputs.append(ws / 'material-catalog.json')
    else:
        plan.values['material_catalog'] = '无（无素材，画面用纯排版）'
    return plan


STEP_PLANS = {'script': script_plan, 'composition': composition_plan}


def read_template(step: str) -> str:
    path = SKILL_ROOT / DELEGATION / step / 'handoff-template.md'
    match = TEMPLATE_BLOCK.search(path.read_text(encoding='utf-8'))
    if not match:
        raise ValueError(f'{path} has no ```markdown code block')
    return match.group(1)


def fill(template: str, values: dict[str, str]) -> str:
    text = PLACEHOLDER.sub(lambda match: values.get(match.group(1), match.group(0)), template)
    unreplaced = sorted(set(PLACEHOLDER.findall(text)))
    if unreplaced:
        raise ValueError(f'handoff template has unreplaced placeholders: {", ".join(unreplaced)}')
    return text


def render_handoff(ws: Path, step: str, inputs: dict[str, Any], plan: Plan) -> str:
    values = {
        'topic_name': ws.name,
        'ws': str(ws),
        'skill_root': str(SKILL_ROOT),
        'coding_agent': str(inputs['coding_agent']),
        'duration': duration_text(inputs['duration']),
        'language': str(inputs['language']),
        'input_mode': str(inputs['input_mode']),
        'template': str(inputs['template'] or '无'),
        **plan.values,
    }
    return fill(read_template(step), values)


def require_files(paths: list[Path], what: str) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f'{what} do not exist: {", ".join(missing)}')


def main() -> int:
    args = parse_args()
    ws = Path(args.workspace).resolve()
    if not ws.is_dir():
        raise NotADirectoryError(f'workspace is not a directory: {ws}')
    inputs = load_inputs(ws)
    plan = STEP_PLANS[args.step](ws, inputs)
    text = render_handoff(ws, args.step, inputs, plan)
    require_files(plan.inputs, f'inputs of the {args.step} step')
    materialized = materialize(ws, args.step, args.refresh)
    fonts = None
    if args.step == 'composition':
        try:
            fonts = install_fonts(ws, inputs['design'])
        except FontsError as exc:
            log(f'error: {exc}')
            cli.print_json({'success': False, 'error': str(exc), 'fonts': exc.payload})
            return 1
    require_files(plan.references, f'files the {args.step} handoff points at')
    handoff = ws / f'{args.step}-handoff.md'
    handoff.write_text(text, encoding='utf-8')
    log(f'wrote {handoff}')
    cli.print_json({
        'success': True,
        'handoff_path': str(handoff),
        'materialized': materialized,
        'fonts': fonts,
        'dispatch_prompt': f'读取 {handoff} 并按它执行；完成后报告产物路径。',
    })
    return 0


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
