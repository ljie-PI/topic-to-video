#!/usr/bin/env python3
"""准备一个委派步骤的交接：落地其包，并填好 handoff。

主 agent 把 catalog（Phase 5）、script（Phase 6）和 composition（Phase 8）三个
步骤委派给 coding agent，由后者读取一份 handoff 文件。handoff 是确定性的，因此由
本脚本生成，而不是让主 agent 手填散文模板。每次调用做三件事：

  0. 校验（在写任何东西之前）：composition 步骤要求 design 是当前库注册的；
     旧 inputs.json 若仍带 layout / template，也校验 layout 的结构与画布尺寸、
     模板声明及其兼容性。新流程不要求预选 layout，也不要求 scenes.json 已存在：
     最终视觉 scenes 与各自 layout 由 composition agent 决定。校验的就是 handoff
     之后会引用的那份文件（不 --refresh 时是工作区副本）。非法时就地失败，
     workspace 完全未被改动。
  1. 落地：把 references/delegation/conventions.md 和
     references/delegation/<step>/ 复制到 <ws>/references/delegation/；
     composition 步骤还复制 modules/（不含 examples/）到 <ws>/modules/。workspace
     中已存在的文件会被保留（该副本可能被编辑过）；--refresh 会覆盖它。
  2. 字体（仅 composition）：用 scripts/fonts-download.sh --theme 把所选 design
     自带的 WOFF2 字体安装到 <ws>/composition/assets/fonts/。每次调用都执行。
  3. Handoff：读取 references/delegation/<step>/handoff-template.md 中的 markdown
     代码块，给模板自己声明的 {{name}} 占位符填值（一次替换，不扫描写入的值），
     写出 <ws>/<step>-handoff.md。其中所有路径都是绝对路径；命令从 skill 根目录
     运行本 skill 的脚本。缺值或不存在的输入 / 引用文件，都算错误。

用法：
  python3 scripts/prepare-handoff.py <workspace_dir> <catalog|script|composition>
      [--refresh] [--resolved-model <实际原生标识>]

输出：stdout 上的一份 JSON 文档，
  {"success": true, "coding_agent": "...", "coding_model": null | "<实际原生标识>",
   "requested_model": null | "<原始请求>", "handoff_path": "...",
   "materialized": [...],
   "fonts": null | {"success": true, "output_dir": "...", "installed": N},
   "dispatch_prompt": "读取 <handoff> 并按它执行；完成后报告产物路径。"}
materialized 列出本次调用写入了文件的那些包路径。fonts 是一份摘要（文件清单有
100 多条路径，对主 agent 没有用处；完整的 fonts-download JSON 会随 handoff 交给
被委派的 agent）。主 agent 原样派发 dispatch_prompt。若 fonts-download 失败，输出
为 {"success": false, "error": "...", "fonts": {fonts-download 的错误 JSON}}。
退出码：0 = 成功，1 = 运行时错误（含请求了模型但未解析就传 --resolved-model），
2 = 参数非法。

模型请求与解析：inputs.json 里的 model 请求是原始请求，留在输入中。用户请求了
模型时，主 agent 先按 references/delegation/conventions.md 经目标 coding agent 的
CLI 查询、选出真实原生标识，再带 --resolved-model 调用本脚本；没有请求时不要传。
handoff 的 Coding Agent 小节同时展示请求与实际值，JSON 的 coding_model 是实际值，
requested_model 是原始请求；无请求时二者都是 null。
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
import harvest_manifest
import video_contract
from delegation_config import STEPS, resolve_delegation, resolve_models, validate_delegation

TOOL_NAME = 'prepare-handoff'

SKILL_ROOT = Path(__file__).resolve().parent.parent

DELEGATION = Path('references') / 'delegation'

PLACEHOLDER = re.compile(r'\{\{\s*([a-zA-Z0-9_-]+)\s*\}\}')
TEMPLATE_BLOCK = re.compile(r'^```markdown\n(.*?)^```$', re.MULTILINE | re.DOTALL)
# 每个步骤只校验和读取自己声明的字段，不附加整份 Phase 1 输入表。
STEP_INPUTS_FIELDS = video_contract.STEP_INPUTS_FIELDS

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
    parser.add_argument(
        '--resolved-model',
        help='实际派发的原生模型标识：主 agent 按统一约定经目标 CLI 查询得到。'
        '仅当本阶段在 inputs.json 里有 model 请求时才能传；未请求时省略。',
    )
    return parser.parse_args()


# --- 输入 --------------------------------------------------------------------


def load_inputs(ws: Path, step: str) -> dict[str, Any]:
    path = ws / 'inputs.json'
    if not path.is_file():
        raise FileNotFoundError(f'inputs.json not found in {ws}')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'inputs.json is not valid JSON: {exc}') from exc
    if not isinstance(data, dict):
        raise ValueError('inputs.json root is not an object')
    required = STEP_INPUTS_FIELDS[step]
    missing = [name for name in required if name not in data]
    if missing:
        raise ValueError(f'inputs.json is missing fields: {", ".join(missing)}')
    optional = [video_contract.STEP_REQUESTS_FIELD[step]]
    if step == 'composition':
        # 旧单 layout 工程可带 layout；新流程由 agent 写入 composition/scenes.json。
        optional.extend(('layout', 'template'))
    selected = {name: data[name] for name in (*required, *optional) if name in data}
    for name, value in selected.items():
        problem = video_contract.input_field_problem(name, value)
        if problem:
            raise ValueError(f'inputs.json {problem}')
    validate_delegation(data)
    if 'delegation' in data:
        selected['delegation'] = data['delegation']
    return selected


def duration_text(duration: Any) -> str:
    return f'{duration} 分钟' if isinstance(duration, (int, float)) else str(duration)


def template_text(inputs: dict[str, Any]) -> str:
    """template 的三种状态：未选择 / 明确不用（null） / 具体模板名。

    缺省不等于“不用”：模板选择是 composition agent 在自己的执行中作出的决定，
    缺省时 handoff 必须告诉它还没选，而不是替它写 null。
    """
    if 'template' not in inputs:
        return '未选择（由本阶段决定）'
    template = inputs['template']
    return str(template) if template is not None else '无（不使用模板）'


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

    theme 只能是当前库里的 design 目录：从库里删掉的 design 不再靠工作区里的旧
    副本继续装字体。
    """
    target = ws / 'composition' / 'assets' / 'fonts'
    theme = SKILL_ROOT / 'modules' / 'designs' / design
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


def request_list(data: dict[str, Any], step: str) -> str:
    """该步骤要看的用户要求，逐条写成列表；没有要求写 None。

    多行要求整体缩进成同一个列表项，因此用户文字里的换行不会变成新的 handoff
    顶级小节。
    """
    requests = video_contract.request_items(data, video_contract.STEP_REQUESTS_FIELD[step])
    if not requests:
        return 'None'
    lines: list[str] = []
    for request in requests:
        first, *rest = request.splitlines() or ['']
        lines.append(f'- {first.strip()}')
        lines.extend(f'  {line.strip()}' for line in rest if line.strip())
    return '\n'.join(lines)


def catalog_instruction_list(ws: Path) -> str:
    path = ws / 'catalog-instructions.md'
    return f'- {path}' if path.is_file() else 'None'


def catalog_plan(ws: Path, inputs: dict[str, Any], *, refresh: bool = False) -> Plan:
    delegation = ws / DELEGATION
    base = delegation / 'catalog' / 'base-instructions.md'
    return Plan(
        values={
            'required_references': numbered([f'{base}（基础指令：素材处理、catalog schema、仅论文素材路径、切片段）']),
            'additional_instructions': catalog_instruction_list(ws),
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


def script_plan(ws: Path, inputs: dict[str, Any], *, refresh: bool = False) -> Plan:
    """旁白与场景规划：只依赖基础输入，不读模板（模板是 Phase 8 的画面选择）。"""
    delegation = ws / DELEGATION
    base = delegation / 'script' / 'base-instructions.md'
    references: list[Reference] = [(f'{base}（基础指令：叙事结构、写法要求、产物 schema）', [base])]
    plan = Plan(
        values={
            'required_references': numbered([text for text, _ in references]),
            'additional_instructions': request_list(inputs, 'script'),
        },
        inputs=[ws / 'inputs.json', ws / 'research-brief.md'],
        references=[delegation / 'conventions.md', *(path for _, paths in references for path in paths)],
        sources=[SKILL_ROOT / DELEGATION / 'conventions.md', SKILL_ROOT / DELEGATION / 'script'],
    )
    if video_contract.catalog_applies(inputs):
        plan.values['material_catalog'] = str(ws / 'material-catalog.json')
        plan.inputs.append(ws / 'material-catalog.json')
    else:
        plan.values['material_catalog'] = '无（fetch_materials = false，没有素材）'
    return plan


# inputs.json 的 orientation -> 画布应当满足的宽高关系在 video_contract：
# “哪个朝向对应哪个画布”只定义一份，字幕规格、handoff 与渲染检查都读它。


def require_registered_visuals(ws: Path, inputs: dict[str, Any], *, refresh: bool) -> None:
    """校验固定 design，以及旧 inputs.json 中仍存在的单 layout 默认值。

    新流程没有 inputs.json.layout；最终 scene layout 在 agent 写出 scenes.json 后，
    由字幕与检查工具校验。旧字段存在时仍按工作区实际使用的副本校验。
    """
    designs = video_contract.available_designs(SKILL_ROOT)
    if inputs['design'] not in designs:
        raise ValueError(
            f'inputs.json field design {inputs["design"]!r} is not an available design '
            f'(choose one of: {", ".join(designs)})'
        )
    if 'layout' not in inputs or (ws / video_contract.VISUAL_SCENES_PATH).exists():
        return
    layout = inputs['layout']
    problem = video_contract.layout_contract_problem(SKILL_ROOT, layout)
    if problem:
        raise ValueError(f'inputs.json {problem}')
    effective = video_contract.effective_resource(
        SKILL_ROOT, ws, f'modules/layouts/{layout}.json', refresh=refresh
    )
    problem = video_contract.layout_file_problem(effective, inputs['orientation'], layout)
    if problem:
        raise ValueError(problem)


def require_compatible_template(ws: Path, inputs: dict[str, Any], *, refresh: bool) -> None:
    """校验已选模板；旧 layout 存在时也保留单 layout 兼容性检查。

    新流程的实际 layout 集合要到 scenes.json 写出后才知道，composition agent 必须
    确认模板支持每一个用到的 layout，状态与检查脚本再作确定性校验。
    """
    template = inputs.get('template')
    problem = video_contract.template_contract_problem(SKILL_ROOT, template)
    if problem:
        raise ValueError(f'inputs.json {problem}')
    if template is None:
        return
    supported = video_contract.template_layouts(SKILL_ROOT, template, ws=ws, refresh=refresh)
    if supported is None:
        raise ValueError(
            f'template {template!r} has no supported_layouts declaration in '
            f'modules/templates/{template}/{template}.json'
        )
    if (
        'layout' in inputs
        and not (ws / video_contract.VISUAL_SCENES_PATH).exists()
        and inputs['layout'] not in supported
    ):
        raise ValueError(
            f'template {template!r} supports layouts {", ".join(supported)}, not {inputs["layout"]!r}: '
            'choose a compatible layout or write template: null'
        )


def composition_plan(ws: Path, inputs: dict[str, Any], *, refresh: bool) -> Plan:
    design, template = inputs['design'], inputs.get('template')
    delegation = ws / DELEGATION
    modules = ws / 'modules'
    base = delegation / 'composition' / 'base-instructions.md'
    modules_doc = modules / 'modules.md'
    design_doc = modules / 'designs' / design / f'{design}.md'
    design_json = modules / 'designs' / design / f'{design}.json'
    design_contract = modules / 'designs' / 'designs.md'
    require_registered_visuals(ws, inputs, refresh=refresh)
    require_compatible_template(ws, inputs, refresh=refresh)
    layouts_doc = modules / 'layouts' / 'layouts.md'
    templates_doc = modules / 'templates' / 'templates.md'

    sources: list[Path] = [
        SKILL_ROOT / DELEGATION / 'conventions.md',
        SKILL_ROOT / DELEGATION / 'composition',
        SKILL_ROOT / 'modules',
    ]
    references: list[Reference] = [
        (f'{base}（基础指令：输入契约、design、视觉 scenes 与 layout 区域、工作顺序）', [base]),
        (f'{modules_doc}（模块库入口与组装约定）', [modules_doc]),
        (
            f'{design_doc} + {design_json}（所选 design；token 契约见 {design_contract}）',
            [design_doc, design_json, design_contract],
        ),
        (f'{layouts_doc}（layout 目录：为每个视觉 scene 选择布局并读取对应 JSON / 文档）', [layouts_doc]),
        # 模板由本阶段的 agent 自己选：目录始终要给出，已选模板的文档另外列。
        (f'{templates_doc}（模板目录：读它决定用哪个模板或不用，并确认 supported_layouts 覆盖全部已用 layout）', [templates_doc]),
    ]
    if template:
        template_doc = modules / 'templates' / template / f'{template}.md'
        template_json = modules / 'templates' / template / f'{template}.json'
        references.append(
            (f'{template_doc} + {template_json}（inputs.json 已选的模板；按内容与用户要求核对）',
             [template_doc, template_json])
        )
        sources.append(SKILL_ROOT / 'modules' / 'templates' / template / f'{template}.md')
        sources.append(SKILL_ROOT / 'modules' / 'templates' / template / f'{template}.json')
    sources.append(SKILL_ROOT / 'modules' / 'layouts' / 'layouts.md')
    sources.append(SKILL_ROOT / 'modules' / 'templates' / 'templates.md')
    components = modules / 'components'
    references.append((f'{components}/（组件目录：按需读要挂载的组件文档）', [components]))
    plan = Plan(
        values={
            'required_references': numbered([text for text, _ in references]),
            'additional_instructions': request_list(inputs, 'composition'),
            'design': design,
            'orientation': str(inputs['orientation']),
        },
        inputs=[
            ws / 'inputs.json',
            ws / 'voice_clone' / 'narration.mp3',
            # 确定性字幕生成用的上游：agent 先写视觉 scenes，再按各 scene layout 现算。
            ws / 'transcribe' / 'transcript.json',
            ws / 'transcribe' / 'timeline.json',
            ws / 'narration.txt',
            ws / 'narration-offsets.json',
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
    if video_contract.catalog_applies(inputs):
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
    """先校验模板自己要的占位符，再一次性替换。

    只扫描模板本身：替换进去的值（例如用户原话里的 `{{name}}`）不再被当成占位
    符，因此字面量花括号能原样进入 handoff。缺值直接报错，不留下未替换的占位符。
    """
    missing = sorted(set(PLACEHOLDER.findall(template)) - set(values))
    if missing:
        raise ValueError(f'handoff template needs values the step does not provide: {", ".join(missing)}')
    return PLACEHOLDER.sub(lambda match: values[match.group(1)], template)


def render_handoff(
    ws: Path, step: str, inputs: dict[str, Any], plan: Plan, *, resolved_model: str | None
) -> str:
    # _q 开头的值是供命令中使用的、经 shell 引用的完整路径：带空格的 topic 名或
    # skill 根目录（例如 "AI Agents 2026"）不能把该行拆开。散文里仍用普通的
    # {{ws}} / {{skill_root}}。
    design = inputs.get('design') or ''
    coding_agent, requested_model = resolve_delegation(inputs, step)
    coding_model, requested_model = resolve_models(requested_model, resolved_model)
    values = {
        'topic_name': ws.name,
        'ws': str(ws),
        'ws_q': shlex.quote(str(ws)),
        'skill_root': str(SKILL_ROOT),
        'skill_root_q': shlex.quote(str(SKILL_ROOT)),
        'venv_activate_q': shlex.quote(str(SKILL_ROOT / '.venv' / 'bin' / 'activate')),
        'composition_dir_q': shlex.quote(str(ws / 'composition')),
        'scenes_json_q': shlex.quote(str(ws / 'composition' / 'scenes.json')),
        'narration_audio_q': shlex.quote(str(ws / 'voice_clone' / 'narration.mp3')),
        'design_json_q': shlex.quote(
            str(ws / 'modules' / 'designs' / design / f'{design}.json')
        ),
        'transcript_q': shlex.quote(str(ws / 'transcribe' / 'transcript.json')),
        'subtitle_units_q': shlex.quote(str(ws / 'composition' / 'assets' / 'subtitle-units.json')),
        'template_cues_q': shlex.quote(str(ws / 'composition' / 'assets' / 'template-cues.json')),
        'template_timeline_q': shlex.quote(
            str(ws / 'composition' / 'assets' / 'template-timeline.json')
        ),
        'timeline_q': shlex.quote(str(ws / 'transcribe' / 'timeline.json')),
        'check_report_q': shlex.quote(str(ws / 'composition' / 'check-composition.json')),
        'script_txt_q': shlex.quote(str(ws / 'script.txt')),
        'narration_q': shlex.quote(str(ws / 'narration.txt')),
        'offsets_q': shlex.quote(str(ws / 'narration-offsets.json')),
        'lexicon_q': shlex.quote(str(ws / 'tts-lexicon.json')),
        'output_dir_q': shlex.quote(str(ws)),
        'coding_agent': coding_agent,
        'coding_model_instruction': (
            f'请求模型：{requested_model}；实际模型：{coding_model}'
            '（必须按实际模型派发，不得仅作为 prompt 要求）'
            if coding_model
            else ''
        ),
        **({'duration': duration_text(inputs['duration'])} if 'duration' in inputs else {}),
        **({'language': str(inputs['language'])} if 'language' in inputs else {}),
        'input_mode': str(inputs['input_mode']),
        'template': template_text(inputs),
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
    inputs = load_inputs(ws, args.step)
    plan = STEP_PLANS[args.step](ws, inputs, refresh=args.refresh)
    text = render_handoff(ws, args.step, inputs, plan, resolved_model=args.resolved_model)
    require_files(plan.inputs, f'inputs of the {args.step} step')
    if args.step == 'catalog':
        harvest_manifest.load(ws / 'harvest_page')
    catalog_path = ws / 'material-catalog.json'
    if catalog_path in plan.inputs:
        catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
        problem = harvest_manifest.paths_problem(catalog, base=ws / 'harvest_page')
        if problem:
            raise ValueError(f'material-catalog.json: {problem}; regenerate Phase 5')
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
    coding_agent, requested_model = resolve_delegation(inputs, args.step)
    coding_model, requested_model = resolve_models(requested_model, args.resolved_model)
    cli.print_json({
        'success': True,
        'coding_agent': coding_agent,
        'coding_model': coding_model,
        'requested_model': requested_model,
        'handoff_path': str(handoff),
        'materialized': materialized,
        'fonts': fonts,
        'dispatch_prompt': f'读取 {handoff} 并按它执行；完成后报告产物路径。',
    })
    return 0


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
