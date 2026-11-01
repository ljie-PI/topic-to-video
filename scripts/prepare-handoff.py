#!/usr/bin/env python3
"""准备一个委派步骤的交接：落地其包，并填好 handoff。

主 agent 把 catalog（Phase 5）、script（Phase 6）和 composition（Phase 8）三个
步骤委派给 coding agent，由后者读取一份 handoff 文件。handoff 是确定性的，因此由
本脚本生成，而不是让主 agent 手填散文模板。每次调用做三件事：

  1. 落地：把 references/delegation/conventions.md 和
     references/delegation/<step>/ 复制到 <ws>/references/delegation/；
     composition 步骤还复制 modules/（不含 examples/）到 <ws>/modules/。workspace
     中已存在的文件会被保留（该副本可能被编辑过）；--refresh 会覆盖它。
  2. 字体（仅 composition）：用 scripts/fonts-download.sh（不联网）把所选 design
     自带的 WOFF2 字体安装到 <ws>/composition/assets/fonts/。每次调用都执行。
  3. Handoff：读取 references/delegation/<step>/handoff-template.md 中的 markdown
     代码块，替换其中的 {{name}} 占位符，写出 <ws>/<step>-handoff.md。其中所有
     路径都是绝对路径；命令从 skill 根目录运行本 skill 的脚本。留下未替换的占位
     符，或不存在的输入 / 引用文件，都算错误。

用法：
  python3 scripts/prepare-handoff.py <workspace_dir> <catalog|script|composition> [--refresh]

输出：stdout 上的一份 JSON 文档，
  {"success": true, "handoff_path": "...", "materialized": [...],
   "fonts": null | {"success": true, "output_dir": "...", "installed": N},
   "dispatch_prompt": "读取 <handoff> 并按它执行；完成后报告产物路径。"}
materialized 列出本次调用写入了文件的那些包路径。fonts 是一份摘要（文件清单有
100 多条路径，对主 agent 没有用处；完整的 fonts-download JSON 会随 handoff 交给
被委派的 agent）。主 agent 原样派发 dispatch_prompt。若 fonts-download 失败，输出
为 {"success": false, "error": "...", "fonts": {fonts-download 的错误 JSON}}。
退出码：0 = 成功，1 = 运行时错误，2 = 参数非法。
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cli

TOOL_NAME = 'prepare-handoff'

SKILL_ROOT = Path(__file__).resolve().parent.parent

STEPS = ['catalog', 'script', 'composition']

DELEGATION = Path('references') / 'delegation'

PLACEHOLDER = re.compile(r'\{\{\s*([a-zA-Z0-9_-]+)\s*\}\}')
TEMPLATE_BLOCK = re.compile(r'^```markdown\n(.*?)^```$', re.MULTILINE | re.DOTALL)
NAME = re.compile(r'[\w-]+')

# 与 pipeline-status.py 接受的时间表述一致；其他写法
# （"90秒"、"1h"、"3-5 min"）在这里也一并拒绝，而不是写进一份
# 会被流水线打回 Phase 1 的 handoff。
DURATION_MINUTES = re.compile(
    r'^\s*(\d+(?:\.\d+)?)\s*(?:min|mins|minute|minutes|分钟|分)?\s*$', re.IGNORECASE
)

INPUTS_FIELDS = ['coding_agent', 'duration', 'language', 'input_mode', 'template', 'design', 'layout', 'orientation', 'fetch_materials']

log = cli.make_logger(TOOL_NAME)


class FontsError(Exception):
    """fonts-download.sh 失败；payload 是它的 JSON（或它的替身）。"""

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


# --- 输入 --------------------------------------------------------------------


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
        if value is not None and not (isinstance(value, str) and NAME.fullmatch(value)):
            raise ValueError(f'inputs.json field {name} must be a plain name, got {value!r}')
    for name in ('coding_agent', 'language', 'input_mode', 'orientation'):
        value = data[name]
        if not isinstance(value, str) or not value:
            raise ValueError(f'inputs.json field {name} must be a non-empty string, got {value!r}')
    if not isinstance(data['fetch_materials'], bool):
        raise ValueError(f"inputs.json field fetch_materials must be a boolean, got {data['fetch_materials']!r}")
    duration = data['duration']
    if isinstance(duration, bool) or not isinstance(duration, (int, float, str)):
        raise ValueError(
            f'inputs.json field duration must be the target length in minutes '
            f'(a number, or a string like "5min"), got {duration!r}'
        )
    if isinstance(duration, str) and not DURATION_MINUTES.match(duration):
        raise ValueError(
            f'inputs.json field duration must be the target length in minutes '
            f'(a number, or a number with a minutes unit such as "5min"), got {duration!r}'
        )
    return data


def duration_text(duration: Any) -> str:
    return f'{duration} 分钟' if isinstance(duration, (int, float)) else str(duration)


# --- 落地包 -------------------------------------------------------------------


def copy_missing(source: Path, target: Path, refresh: bool, skip: tuple[str, ...] = ()) -> bool:
    """复制一个文件或目录树；已存在的文件除非 refresh 否则保留。

    skip 指定目录源中不复制的一级条目。
    返回是否写了任何文件。
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
        # 用 copyfile 而不是 copy2：源文件的权限位（只读安装）不能把 workspace
        # 里的副本也变成只读，从而让 --refresh 失效。
        shutil.copyfile(file, destination)
        wrote = True
    return wrote


def materialize(ws: Path, step: str, refresh: bool) -> list[str]:
    """把该步骤的包复制进 workspace；返回写入了文件的那些路径。"""
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
    """为所选 design 运行 fonts-download.sh；返回一份摘要。

    已从 skill 移除的 design，在 workspace 里存有其副本时仍然可用
    （pipeline-status 接受同样的兜底），因此 theme 路径会退回到
    <ws>/modules/designs/<design>。
    """
    target = ws / 'composition' / 'assets' / 'fonts'
    theme = SKILL_ROOT / 'modules' / 'designs' / design
    if not theme.is_dir() and (ws / 'modules' / 'designs' / design).is_dir():
        theme = ws / 'modules' / 'designs' / design
    proc = subprocess.run(
        [
            'bash',
            str(SKILL_ROOT / 'scripts' / 'fonts-download.sh'),
            str(target),
            '--theme',
            str(theme),
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
    files = payload.get('files')
    return {
        'success': True,
        'output_dir': payload.get('output_dir', str(target)),
        'installed': len(files) if isinstance(files, list) else None,
    }


# --- handoff -------------------------------------------------------------------


@dataclass
class Plan:
    """一个步骤对其 handoff 的贡献。

    values 填该步骤的占位符；inputs 是 handoff 会读取的 workspace 文件（它们必须
    在任何东西被写出之前就存在）；references 是 handoff 指向的包与模块文件（包落地
    之后它们必须存在）；sources 是包复制自的 skill 侧文件——在任何写入之前就校验，
    因此非法的 layout 或 template 名会让 workspace 完全未被改动时就失败。
    """

    values: dict[str, str]
    inputs: list[Path] = field(default_factory=list)
    references: list[Path] = field(default_factory=list)
    sources: list[Path] = field(default_factory=list)


Reference = tuple[str, list[Path]]


def numbered(items: list[str]) -> str:
    return '\n'.join(f'{number}. {item}' for number, item in enumerate(items, 1))


def instruction_list(ws: Path, *names: str) -> str:
    files = [ws / name for name in names if (ws / name).is_file()]
    return '\n'.join(f'- {file}' for file in files) if files else 'None'


def catalog_plan(ws: Path, inputs: dict[str, Any]) -> Plan:
    delegation = ws / DELEGATION
    base = delegation / 'catalog' / 'base-instructions.md'
    return Plan(
        values={
            'required_references': numbered([f'{base}（基础指令：素材处理、catalog schema、仅论文素材路径、切片段）']),
            'additional_instructions': 'None',
        },
        inputs=[
            ws / 'harvest_page' / 'manifest.json',
            ws / 'research-brief.md',
            ws / 'vision_analyze' / 'topic-context.txt',
            ws / 'inputs.json',
        ],
        references=[delegation / 'conventions.md', base],
        sources=[SKILL_ROOT / DELEGATION / 'conventions.md', SKILL_ROOT / DELEGATION / 'catalog'],
    )


def script_plan(ws: Path, inputs: dict[str, Any]) -> Plan:
    template = inputs['template']
    delegation = ws / DELEGATION
    base = delegation / 'script' / 'base-instructions.md'
    sources: list[Path] = [SKILL_ROOT / DELEGATION / 'conventions.md', SKILL_ROOT / DELEGATION / 'script']
    references: list[Reference] = [(f'{base}（基础指令：叙事结构、写法要求、产物 schema）', [base])]
    if template:
        template_dir = SKILL_ROOT / 'modules' / 'templates' / template
        if not template_dir.is_dir():
            raise FileNotFoundError(f'template {template!r} not found: {template_dir}')
        # 没有旁白要求的模板不贡献任何条目。
        narration = template_dir / 'narration.md'
        if narration.is_file():
            references.append((f'{narration}（所选模板 {template} 的旁白要求）', [narration]))
            sources.append(narration)
    plan = Plan(
        values={
            'required_references': numbered([text for text, _ in references]),
            'additional_instructions': instruction_list(ws, 'narration-instructions.md'),
        },
        inputs=[ws / 'inputs.json', ws / 'research-brief.md'],
        references=[delegation / 'conventions.md', *(path for _, paths in references for path in paths)],
        sources=sources,
    )
    if inputs['fetch_materials'] or inputs['input_mode'] == 'paper':
        plan.values['material_catalog'] = str(ws / 'material-catalog.json')
        plan.inputs.append(ws / 'material-catalog.json')
    else:
        plan.values['material_catalog'] = '无（fetch_materials = false，没有素材）'
    return plan


def layout_reference(modules: Path, layout: str) -> Reference:
    """该 layout 的区域定义 json（始终必需）及其文档。

    有些画布共用一份文档：portrait-3x4 只有 .json，portrait.md 同时覆盖两个竖屏
    画布。json 从不兜底——缺少区域定义是错误，而不是“没有文档”。
    """
    layout_json = modules / 'layouts' / f'{layout}.json'
    layout_doc = modules / 'layouts' / f'{layout}.md'
    if not layout_doc.is_file() and '-' in layout:
        shared = modules / 'layouts' / f'{layout.split("-", 1)[0]}.md'
        if shared.is_file():
            layout_doc = shared
    return (f'{layout_json} + {layout_doc}（所选 layout 的区域定义）', [layout_json, layout_doc])


def composition_plan(ws: Path, inputs: dict[str, Any]) -> Plan:
    design, layout, template = inputs['design'], inputs['layout'], inputs['template']
    delegation = ws / DELEGATION
    modules = ws / 'modules'
    base = delegation / 'composition' / 'base-instructions.md'
    modules_doc = modules / 'modules.md'
    design_doc = modules / 'designs' / design / f'{design}.md'
    design_json = modules / 'designs' / design / f'{design}.json'
    design_contract = modules / 'designs' / 'designs.md'
    layout_text, skill_layout_paths = layout_reference(SKILL_ROOT / 'modules', layout)
    layout_paths = [modules / path.relative_to(SKILL_ROOT / 'modules') for path in skill_layout_paths]
    layout_item = ' + '.join(str(path) for path in layout_paths)

    def source(skill_path: Path) -> Path:
        """modules/ 引用按哪个副本校验：优先 skill 里的那份，除非该 design 已从
        skill 移除而只剩 workspace 中的副本（pipeline-status 接受同样的兜底）。"""
        return skill_path if skill_path.exists() else ws / skill_path.relative_to(SKILL_ROOT)

    sources: list[Path] = [
        SKILL_ROOT / DELEGATION / 'conventions.md',
        SKILL_ROOT / DELEGATION / 'composition',
        SKILL_ROOT / 'modules',
    ]
    references: list[Reference] = [
        (f'{base}（基础指令：输入契约、design、layout 区域、工作顺序）', [base]),
        (f'{modules_doc}（模块库入口与组装约定）', [modules_doc]),
        (
            f'{design_doc} + {design_json}（所选 design；token 契约见 {design_contract}）',
            [design_doc, design_json, design_contract],
        ),
        (f'{layout_item}（所选 layout 的区域定义）', layout_paths),
    ]
    sources.extend(
        source(path)
        for path in [
            SKILL_ROOT / 'modules' / 'designs' / design / f'{design}.md',
            SKILL_ROOT / 'modules' / 'designs' / design / f'{design}.json',
            *layout_reference(SKILL_ROOT / 'modules', layout)[1],
        ]
    )
    if template:
        template_doc = modules / 'templates' / template / f'{template}.md'
        references.append((f'{template_doc}（所选模板的组装说明，及其场景 / 组件文档）', [template_doc]))
        sources.append(source(SKILL_ROOT / 'modules' / 'templates' / template / f'{template}.md'))
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
        sources=sources,
    )
    if inputs['fetch_materials'] or inputs['input_mode'] == 'paper':
        plan.values['material_catalog'] = str(ws / 'material-catalog.json')
        plan.inputs.append(ws / 'material-catalog.json')
    else:
        plan.values['material_catalog'] = '无（无素材，画面用纯排版）'
    return plan


STEP_PLANS = {'catalog': catalog_plan, 'script': script_plan, 'composition': composition_plan}


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
    # _q 开头的值是供命令中使用的、经 shell 引用的完整路径：带空格的 topic 名或
    # skill 根目录（例如 "AI Agents 2026"）不能把该行拆开。散文里仍用普通的
    # {{ws}} / {{skill_root}}。
    design, layout = inputs['design'], inputs['layout']
    values = {
        'topic_name': ws.name,
        'ws': str(ws),
        'ws_q': shlex.quote(str(ws)),
        'skill_root': str(SKILL_ROOT),
        'skill_root_q': shlex.quote(str(SKILL_ROOT)),
        'venv_activate_q': shlex.quote(str(SKILL_ROOT / '.venv' / 'bin' / 'activate')),
        'composition_dir_q': shlex.quote(str(ws / 'composition')),
        'layout_json_q': shlex.quote(str(ws / 'modules' / 'layouts' / f'{layout}.json')),
        'design_json_q': shlex.quote(
            str(ws / 'modules' / 'designs' / design / f'{design}.json')
        ),
        'subtitle_units_q': shlex.quote(str(ws / 'transcribe' / 'subtitle-units.json')),
        'timeline_q': shlex.quote(str(ws / 'transcribe' / 'timeline.json')),
        'check_report_q': shlex.quote(str(ws / 'composition' / 'check-composition.json')),
        'script_txt_q': shlex.quote(str(ws / 'script.txt')),
        'lexicon_q': shlex.quote(str(ws / 'tts-lexicon.json')),
        'output_dir_q': shlex.quote(str(ws)),
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
    # 在任何东西被写出之前校验 skill 侧的源文件：非法的 layout 或 design 名必须
    # 在 workspace 完全未被改动时就失败，就像缺少输入那样 —— 而不是等 modules/
    # 已被复制进去之后才失败。
    require_files(plan.sources, f'skill files the {args.step} handoff is built from')
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
