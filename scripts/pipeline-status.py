#!/usr/bin/env python3
"""流水线状态驱动：扫描项目 workspace 并报告流水线进度。

本脚本是 topic-to-video 流水线唯一的续跑入口。它校验 workspace 中每个阶段的
产物（存在、非空、JSON 可解析、必要字段），并报告已完成的阶段、下一步要跑的
阶段、该阶段要读的文档，以及任何缺失或损坏的产物。产物被删除或损坏的阶段会回退
到该阶段。

Phase 6 的确定性规则也在这里检查，因此不需要 agent 手算：script.txt 长度对照
inputs.json 的 duration、scene-plan 段落对照 script.txt 的段落、scene-plan 的
素材引用对照 catalog、narration-offsets.json 记录的版本 / 字数对照
script.txt 与 narration.txt。

阶段的分工也在这里体现：Phase 7 只产出音频、fresh transcript 与时间轴（不读
layout）；最终字幕是 Phase 8 的产物（`composition/assets/subtitle-units.json`），
按 `composition/scenes.json` 的实际视觉 layouts 生成；旧工程保留 inputs.layout 入口。
Phase 8 校验精确画布与逐 scene 模板兼容，Phase 7 不依赖视觉配置。

本脚本不做内容新鲜度追踪：不比对文件哈希或修改时间，不判断某个阶段是不是
“基于当前上游构建”。上游改动后的影响由主 agent 根据已知修改范围显式登记重做，
不从文件变化推断。各阶段按顺序判定；第一个缺失、损坏、等待用户确认或已登记
重做的阶段成为 next_phase，其后每个适用的阶段都为 pending：它不被检查、也不
被报告为已完成。

用户关卡按需启用：inputs.json 可选的 approval_gates 列出要求审稿的关卡：
research-brief（Phase 3）和/或 script（Phase 6）。缺省或 [] 表示全自动。只有
列出的关卡需要 {workspace}/.pipeline/approvals.json 中匹配的确认。--approve
<gate> 只在该阶段全部产物通过检查之后才记录确认事实与时间，不绑定文件哈希。
显式重做（--redo）一个带审稿 gate 的阶段会撤销该 gate 的旧确认；审稿策略本身
只是政策：启用或停用它不会代替用户批准，也不会取消已登记的确认。

重做请求：产物合格不等于内容合格，而用户或 agent 要求重做时，文件往往还没变。
因此 {workspace}/.pipeline/redos.json 记录这类请求：--redo <phase_id> --reason <text>
登记后，该阶段即使产物合格也不被当完成（next_phase.reason 为 redo），其后的
阶段为 pending；旧产物保留，扫描也不会清掉请求。--finish <phase_id> 先清掉这条
要求，再让该阶段走它平时的产物检查：全部合格才算结束。它不证明内容合格，也不
替用户审批：agent 必须先按阶段文档自检，再执行 --finish。

健壮性：扫描绝不会因状态文件问题而中止。redos.json 是例外：读不出来就无法知道
有没有待重做的阶段，默默当它是空的会丢掉用户的要求，因此那一次运行直接失败
（exit 1）。approvals.json 读不出来时按没有确认处理，原文件原样保留。

用法：
  python3 scripts/pipeline-status.py <workspace_dir> [--approve <gate> | --redo <phase_id> --reason <text> | --finish <phase_id>]

workspace_dir 是必需的：SKILL.md 中的命令从 skill 根目录运行，因此当前目录永远
不是项目 workspace。项目 workspace 位于本仓库之外；输出中只有文档路径是相对本
仓库的。

输出：stdout 上的一份 JSON 文档。除了沿用下来的 completed_phases /
skipped_phases / missing_products / corrupt_products 之外，还带有：
  phases          [{id, status}]，覆盖每个阶段；status 为 completed、
                  skipped、missing、corrupt、redo_requested、
                  awaiting_approval 或 pending
  pending_phases, redo_phases
  approval_gates    inputs.json 中请求用户审稿的关卡（默认：[]）
  next_phase      {id, title, doc, reason, problems}；reason 为 missing、
                  corrupt、redo 或 awaiting_approval。已登记重做的阶段会附加
                  redo_reason；确认关卡会附加 gate 与 instruction。
                  输入前置条件失败的键写作 inputs.json#<field>（例如
                  inputs.json#layout），它算 corrupt，但不进 corrupt_products：
                  那不是产物缺失，而是该阶段要修的配置。
退出码：0 = 成功（存在下一个阶段，或流水线已完成），
1 = 运行时错误（workspace 不可读或不可写、对当前不适用的阶段使用 --redo），
2 = 参数非法，或请求无法被接受（产物无法确认或结束重做、没有待重做的阶段）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import cli
import clip_paths
import harvest_manifest
import media
import script_text
import video_contract
from harvest_manifest import _stage_json as stage_json, stored_path_problem
from delegation_config import validate_delegation

TOOL_NAME = 'pipeline-status'

SKILL_ROOT = Path(__file__).resolve().parent.parent

STATUS_OK = 'ok'
STATUS_MISSING = 'missing'
STATUS_CORRUPT = 'corrupt'

# 输出中的阶段状态：产物缺失或损坏的阶段取对应的 STATUS_ 值；
# 其余状态在此命名。
PHASE_COMPLETED = 'completed'
PHASE_SKIPPED = 'skipped'
PHASE_PENDING = 'pending'
PHASE_AWAITING_APPROVAL = 'awaiting_approval'
PHASE_REDO = 'redo_requested'

# next_phase.reason 的取值：前三个与同名的阶段状态一致，重做请求单独命名。
REASON_REDO = 'redo'

# Phase 1 的基础字段：定义在 video_contract，实际读取也只认那一份。
INPUTS_REQUIRED_FIELDS = video_contract.INPUTS_BASE_FIELDS

# 用户在对话里提出的长期要求，按阶段分开保存；缺省与 [] 等价。
REQUESTS_FIELDS = video_contract.REQUESTS_FIELDS

# qa_level 可选：缺省表示 standard 档。给出时必须是三个枚举值之一。
QA_LEVELS = video_contract.QA_LEVELS

PAPER_MODES = {'paper'}

# {workspace}/.pipeline/ 是本脚本自己的状态；只有本脚本写入它。

# inputs.json#approval_gates 按需启用用户审稿（默认：[]）；这是政策，不是构建输入，
# 因此改变它不得使已经生成的产物失效。
# 用户确认是持久状态：按 gate 记录确认事实与时间，不绑定文件哈希；显式重做
# 对应阶段时撤销该 gate 的旧确认。
APPROVALS_PATH = '.pipeline/approvals.json'
APPROVALS_VERSION = 1

# 重做请求也是持久状态：产物合格不代表内容合格，而要求重做时文件往往还没变。
# 记录在 {workspace}/.pipeline/redos.json，只由本脚本写入。
REDOS_PATH = '.pipeline/redos.json'
REDOS_VERSION = 1
GATES: dict[str, dict[str, Any]] = {
    'research-brief': {
        'phase': '3-research',
        'instruction': (
            '把 research-brief.md 给用户过目；用户确认后运行 '
            '`python3 scripts/pipeline-status.py <ws> --approve research-brief`'
        ),
    },
    'script': {
        'phase': '6-script-scene-plan',
        'instruction': (
            '把旁白和每个 scene 的 scene_id + intent + content_plan 摘要交给用户确认；确认后运行 '
            '`python3 scripts/pipeline-status.py <ws> --approve script`'
        ),
    },
}

# 上游键 "inputs.json#<field>" 指 inputs.json 的某个字段。
INPUTS_FIELD_PREFIX = 'inputs.json#'

# Phase 3 的简报必需的小节（标题按 Phase 3 文档的模板）；Open questions 可选。
RESEARCH_BRIEF_SECTIONS = ('Key facts', 'Quotes', 'Numbers', 'Source URLs')

# Phase 6 的长度规则：展示稿的非空白字符数必须在
# duration x 60 s x 7 字/秒 的 +-15% 之内。这是写稿预算，不是 TTS 语速参数：
# 实际节奏由 TTS 与 transcript 决定，流水线不指定 speech rate。
CHARS_PER_SECOND = 7
SCRIPT_LENGTH_TOLERANCE = 0.15

# 一个 scene-plan 片段引用 "<slug>/<video_id>:<start>-<end>" 必须在两端都
# 与该项 catalog 条目中的某条 selected_clips 匹配到这个秒数范围内。
CLIP_REF_TOLERANCE_S = 0.01

# inputs.json 的 duration 是分钟数：一个数字，或“数字 + 可选分钟单位”的字符串
# （"5min"、"5 分钟"）。其他写法（"90s"、"1h"、"3-5 min"）会被拒绝，而不是被
# 当成那么多分钟。
# 解析与合法性规则共用 video_contract.duration_minutes。

# 片段引用 "<slug>/<video_id>:<start>-<end>" 的时间窗，以秒计，必须精确写成这样。
CLIP_WINDOW = re.compile(r'^(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$')


@dataclass
class CheckResult:
    """一次产物检查的结构化结果。

    status 是 STATUS_OK / STATUS_MISSING / STATUS_CORRUPT 之一；detail 携带
    人类可读的原因，仅在 status 不是 ok 时才有意义。
    """

    status: str
    detail: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK


OK = CheckResult(STATUS_OK)

# 每个产物检查器的签名相同：(workspace, relpath) -> CheckResult。
Checker = Callable[[Path, str], CheckResult]


log = cli.make_logger(TOOL_NAME)
print_json = cli.print_json


def parse_args() -> argparse.Namespace:
    parser = cli.JsonArgumentParser(
        TOOL_NAME,
        description='Scan a topic-to-video workspace and report the next pipeline phase.'
    )
    parser.add_argument('workspace', help='Project workspace directory ({work_dir}/{topic_name}).')
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        '--approve',
        metavar='GATE',
        choices=list(GATES),
        help='Record user approval of a gate (the confirmation fact and time), then report status.',
    )
    action.add_argument(
        '--redo',
        metavar='PHASE_ID',
        choices=[phase['id'] for phase in PHASES],
        help=(
            'Record that a phase must be redone, then report the status as usual. Its products are '
            'kept, but the phase stops counting as completed (reason redo) until --finish accepts it.'
        ),
    )
    action.add_argument(
        '--finish',
        metavar='PHASE_ID',
        choices=[phase['id'] for phase in PHASES],
        help=(
            'End a pending redo: clear the request, then run the phase`s usual product checks. '
            'The products must all pass; finishing does not decide whether the content is good.'
        ),
    )
    parser.add_argument(
        '--reason',
        metavar='TEXT',
        help='Why the phase must be redone; required with --redo and kept for the next turns.',
    )
    args = parser.parse_args()
    reason = (args.reason or '').strip()
    if args.redo is not None and not reason:
        parser.error('--redo needs a non-empty --reason')
    if args.reason is not None and args.redo is None:
        parser.error('--reason only applies to --redo')
    return args


# --- 产物检查器 --------------------------------------------------------------
#
# 每个检查器接收 workspace 根目录加上产物在 workspace 内的相对路径，返回一个
# CheckResult。所有检查器共用一个签名；分发处没有任何特殊分支。


def check_file_product(ws: Path, relpath: str) -> CheckResult:
    path = ws / relpath
    if not path.exists():
        return CheckResult(STATUS_MISSING)
    if not path.is_file():
        return CheckResult(STATUS_CORRUPT, 'not a regular file')
    if path.stat().st_size == 0:
        return CheckResult(STATUS_CORRUPT, 'empty file')
    return OK


def read_json_product(ws: Path, relpath: str) -> tuple[CheckResult, Any]:
    """公用辅助函数：文件检查 + JSON 解析。返回 (result, data)。"""
    result = check_file_product(ws, relpath)
    if not result.ok:
        return result, None
    try:
        data = json.loads((ws / relpath).read_text(encoding='utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return CheckResult(STATUS_CORRUPT, f'invalid JSON: {exc}'), None
    return OK, data


def read_nonempty_text(ws: Path, relpath: str) -> tuple[CheckResult, str | None]:
    """文本产物的公用辅助函数：文件必须存在且有内容。"""
    result = check_file_product(ws, relpath)
    if not result.ok:
        return result, None
    text = (ws / relpath).read_text(encoding='utf-8', errors='replace')
    if not text.strip():
        return CheckResult(STATUS_CORRUPT, 'file has no content'), None
    return OK, text


def check_text_product(ws: Path, relpath: str) -> CheckResult:
    result, _ = read_nonempty_text(ws, relpath)
    return result


def check_script_text(ws: Path, relpath: str) -> CheckResult:
    """script.txt：非空，且其长度在 inputs.json 的 duration 所隐含目标的
    容差范围之内。"""
    result, text = read_nonempty_text(ws, relpath)
    if not result.ok:
        return result
    _, inputs = load_inputs(ws)
    minutes = duration_minutes(inputs['duration']) if inputs else None
    if minutes is None:
        return OK  # 没有可比对的基准；inputs.json 会单独报告
    target = minutes * 60 * CHARS_PER_SECOND
    count = script_text.count_chars(text)
    deviation = (count - target) / target
    if abs(deviation) > SCRIPT_LENGTH_TOLERANCE:
        return CheckResult(
            STATUS_CORRUPT,
            f'{count} characters, target {target:g} ({minutes:g} min x 60 s x {CHARS_PER_SECOND:g} chars/s), '
            f'off by {deviation:+.1%} (limit +-{SCRIPT_LENGTH_TOLERANCE:.0%})',
        )
    return OK


def check_research_brief(ws: Path, relpath: str) -> CheckResult:
    """research-brief.md：非空，且含把调研交给下游的四个小节。

    小节标题按 Phase 3 的模板写（## Key facts / ## Quotes / ## Numbers /
    ## Source URLs）。小节内容是否可信由 agent 自检，这里只保证下游能按小节取。
    """
    result, text = read_nonempty_text(ws, relpath)
    if not result.ok:
        return result
    headings = [
        match.group(1).strip()
        for match in re.finditer(r'^##\s+(.+?)\s*$', text, flags=re.MULTILINE)
    ]
    missing = [
        name
        for name in RESEARCH_BRIEF_SECTIONS
        if not any(heading.startswith(name) for heading in headings)
    ]
    if missing:
        return CheckResult(
            STATUS_CORRUPT,
            f'missing sections: {", ".join(f"## {name}" for name in missing)}',
        )
    return OK


def check_dict_entries_product(ws: Path, relpath: str) -> CheckResult:
    """用于必须带有非空 `entries` 列表的 JSON 对象
    （harvest manifest、素材 catalog）。"""
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, dict):
        return CheckResult(STATUS_CORRUPT, 'JSON root is not an object')
    entries = data.get('entries')
    if not isinstance(entries, list) or not entries:
        return CheckResult(STATUS_CORRUPT, 'entries is not a non-empty list')
    return OK


CATALOG_ITEM_KINDS = ('images', 'videos')


def entry_label(index: int, entry: Any) -> str:
    slug = entry.get('slug') if isinstance(entry, dict) else None
    return f'entry {slug!r}' if isinstance(slug, str) and slug else f'entry {index}'


def clip_problem(ws: Path, video: Any, clip: Any, *, require_file: bool) -> str | None:
    """某个选中片段的静音文件（scripts/cut-clips.py）不可用的原因，或 None。

    当 require_file=False 时只检查 catalog 侧的契约（clip_path 必须指向该片段
    当前时间窗会产出的那个文件）；为 True 时还要求该文件在磁盘上存在且非空。
    """
    if not isinstance(clip, dict):
        return 'is not an object'
    clip_path = clip.get('clip_path')
    if not isinstance(clip_path, str) or not clip_path.strip():
        return 'has no non-empty string clip_path (run scripts/cut-clips.py)'
    path = Path(clip_path)
    if path.is_absolute() or '..' in path.parts:
        return f'clip_path {clip_path!r} is not a relative path inside the workspace'
    try:
        expected = clip_paths.clip_relpath(
            video.get('id') if isinstance(video, dict) else None,
            clip.get('start'),
            clip.get('end'),
        )
    except ValueError as exc:
        return f'clip window is unusable: {exc}'
    if clip_path != expected:
        return (
            f'clip_path {clip_path!r} does not name the file of this clip\'s current window '
            f'({expected}; re-run scripts/cut-clips.py after editing a clip window)'
        )
    if not require_file:
        return None
    result = check_file_product(ws, clip_path)
    if not result.ok:
        return f'clip file {clip_path!r} is {result.detail or result.status} (run scripts/cut-clips.py)'
    return None


# catalog 的可选字段：必须进入成片的素材（论文模式下是关键图表）。
REQUIRED_MATERIAL_REFS_FIELD = 'required_material_refs'


def _check_catalog(ws: Path, relpath: str, *, require_clip_files: bool) -> CheckResult:
    """material-catalog.json，Phase 5 的契约。

    结构（entries、id、semantic_description、clip_path 契约）总是检查；
    require_clip_files 会额外要求磁盘上每个片段文件都在。两者保持分离，这样缺失
    一个片段文件不会同时让 scene-plan 的引用校验失明（见 check_catalog_structure
    / load_catalog_index）。
    """
    entries_result = check_dict_entries_product(ws, relpath)
    if not entries_result.ok:
        return entries_result
    _, data = read_json_product(ws, relpath)
    problem = harvest_manifest.paths_problem(data, base=ws / 'harvest_page')
    if problem:
        return CheckResult(STATUS_CORRUPT, f'{problem}; regenerate Phase 5')
    for index, entry in enumerate(data['entries']):
        label = entry_label(index, entry)
        if not isinstance(entry, dict):
            return CheckResult(STATUS_CORRUPT, f'{label} is not an object')
        for kind in CATALOG_ITEM_KINDS:
            items = entry.get(kind, [])
            if not isinstance(items, list):
                return CheckResult(STATUS_CORRUPT, f'{label} {kind} is not a list')
            for position, item in enumerate(items):
                where = f'{label} {kind}[{position}]'
                if not isinstance(item, dict):
                    return CheckResult(STATUS_CORRUPT, f'{where} is not an object')
                for field in ('id', 'semantic_description'):
                    value = item.get(field)
                    if not isinstance(value, str) or not value.strip():
                        return CheckResult(
                            STATUS_CORRUPT,
                            f'{where} (id {item.get("id")!r}) has no non-empty string {field}',
                        )
                if kind != 'videos':
                    continue
                clips = item.get('selected_clips')
                for clip_index, clip in enumerate(clips if isinstance(clips, list) else []):
                    problem = clip_problem(ws, item, clip, require_file=require_clip_files)
                    if problem:
                        return CheckResult(
                            STATUS_CORRUPT,
                            f'{where} (id {item["id"]!r}) selected_clips[{clip_index}] {problem}',
                        )
    return check_required_refs(data, ws)


def check_material_catalog(ws: Path, relpath: str) -> CheckResult:
    """material-catalog.json：`entries` 非空；每个 image / video 都有非空字符串
    `id` 与 `semantic_description`（Phase 5 的契约）；每个 video 的选中片段都有
    一个指向 workspace 中非空文件的 `clip_path`（cut-clips.py）。id 不要求唯一：
    harvest-pages 对每个页面从 img_001 开始编号，因此同一个 id 会跨条目重复。"""
    return _check_catalog(ws, relpath, require_clip_files=True)


def check_catalog_structure(ws: Path, relpath: str) -> CheckResult:
    """只检查 catalog 的形状 —— 不检查片段文件是否在磁盘上。"""
    return _check_catalog(ws, relpath, require_clip_files=False)


@dataclass
class CatalogIndex:
    """scene-plan 引用可以指向什么：带 slug 限定的 image / video id，
    以及每个被限定的 video id 的选中片段窗口，形式为 (start_s, end_s)。"""

    ids: set[str]
    clips: dict[str, list[tuple[float, float]]]
    ambiguous_ids: set[str] = field(default_factory=set)


def check_required_refs(data: dict[str, Any], ws: Path | None = None) -> CheckResult:
    """catalog 的 required_material_refs：不重复、能解析到本 catalog 的 ref 列表。
    它记录“必须进入成片”的素材（论文模式下的关键图），Phase 6 的候选引用必须
    覆盖它。

    可选项在标准模式；论文模式下这个字段必须显式声明（没有适用图时明确写
    []）：缺省分不清“没有关键图”和“还没看过”。
    """
    if REQUIRED_MATERIAL_REFS_FIELD not in data:
        if ws is not None:
            _, inputs = load_inputs(ws)
            if inputs is not None and inputs.get('input_mode') in PAPER_MODES:
                return CheckResult(
                    STATUS_CORRUPT,
                    f'{REQUIRED_MATERIAL_REFS_FIELD} must be declared in paper mode: list the key '
                    'figures / tables, or write [] when the paper has no usable figure',
                )
        return OK
    refs = data[REQUIRED_MATERIAL_REFS_FIELD]
    if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref for ref in refs):
        return CheckResult(
            STATUS_CORRUPT,
            f'{REQUIRED_MATERIAL_REFS_FIELD} must be a list of non-empty refs, got {refs!r}',
        )
    index = catalog_index_from_data(data)
    seen: set[tuple[Any, ...]] = set()
    invalid: list[str] = []
    duplicates: list[str] = []
    for ref in refs:
        try:
            identity = parse_ref(ref, index)
        except ValueError as exc:
            return CheckResult(STATUS_CORRUPT, f'{REQUIRED_MATERIAL_REFS_FIELD}: {exc}')
        if identity is None:
            invalid.append(ref)
        elif identity in seen:
            duplicates.append(ref)
        else:
            seen.add(identity)
    if invalid:
        return CheckResult(
            STATUS_CORRUPT, f'{REQUIRED_MATERIAL_REFS_FIELD} refs not found in this catalog: {invalid}'
        )
    if duplicates:
        return CheckResult(
            STATUS_CORRUPT, f'{REQUIRED_MATERIAL_REFS_FIELD} repeats resolved refs: {duplicates}'
        )
    return OK


def required_material_refs(ws: Path) -> list[str]:
    """catalog 声明的必用 ref；catalog 阶段不适用时为空。

    判断看的是当前素材策略，不是目录里剩下什么：项目改成了无素材模式后，残留的
    catalog 不再参与任何要求，否则同一个项目自己就推进不下去了。
    """
    _, inputs = load_inputs(ws)
    if not phase_applies(PHASES_BY_ID['5-material-catalog'], inputs):
        return []
    if not check_catalog_structure(ws, 'material-catalog.json').ok:
        return []
    _, data = read_json_product(ws, 'material-catalog.json')
    refs = data.get(REQUIRED_MATERIAL_REFS_FIELD) if isinstance(data, dict) else None
    return list(refs) if isinstance(refs, list) else []


def load_catalog_index(ws: Path) -> CatalogIndex | None:
    """material-catalog.json 的索引；当它的结构不是合法 catalog 时为 None
    （此时 Phase 5 会单独报告）。刻意只检查结构：缺失片段文件会让 Phase 5 损坏，
    但 scene-plan 的引用仍必须对着已存在的 catalog 校验。"""
    if not check_catalog_structure(ws, 'material-catalog.json').ok:
        return None
    _, data = read_json_product(ws, 'material-catalog.json')
    return catalog_index_from_data(data)


def catalog_index_from_data(data: dict[str, Any]) -> CatalogIndex:
    """已解析的 catalog 数据 → scene-plan 引用可指向的 id 与片段窗口。"""
    ids: set[str] = set()
    counts: dict[str, int] = {}
    clips: dict[str, list[tuple[float, float]]] = {}
    for entry in data['entries']:
        slug = entry.get('slug')
        if not isinstance(slug, str) or not slug:
            continue
        for image in entry.get('images', []):
            image_ref = f'{slug}/{image["id"]}'
            ids.add(image_ref)
            counts[image_ref] = counts.get(image_ref, 0) + 1
        for video in entry.get('videos', []):
            video_ref = f'{slug}/{video["id"]}'
            ids.add(video_ref)
            counts[video_ref] = counts.get(video_ref, 0) + 1
            windows = clips.setdefault(video_ref, [])
            for clip in video.get('selected_clips') or []:
                bounds = [clip.get(key) if isinstance(clip, dict) else None for key in ('start', 'end')]
                if all(isinstance(b, (int, float)) and not isinstance(b, bool) for b in bounds):
                    windows.append((float(bounds[0]), float(bounds[1])))
    return CatalogIndex(ids, clips, {ref for ref, count in counts.items() if count > 1})


def parse_ref(ref: str, index: CatalogIndex) -> tuple[Any, ...] | None:
    """把引用解析成它真正指向的身份；解析不了时为 None。

    身份只有两种：``('material', '<slug>/<id>')`` 表示一项素材，
    ``('clip', '<slug>/<video_id>', start, end)`` 表示该项的一条选中片段。

    引用比对走解析后的身份，不做原始字符串比较：``12-18.5`` 与 ``12.00-18.50``
    指向同一个片段，不应该因为写法不同就报“必用素材未被覆盖”。裸 id 仍视为有
    歧义，无法解析。
    """
    slug, slash, material_ref = ref.partition('/')
    if not slash or not slug or not material_ref or '/' in material_ref:
        return None
    if ref in index.ambiguous_ids:
        raise ValueError(f'ambiguous material ref {ref!r}: multiple catalog items share this slug / id')
    if ref in index.ids:
        return ('material', ref)
    video_id, colon, window = material_ref.rpartition(':')
    if not colon:
        return None
    video_ref = f'{slug}/{video_id}'
    if video_ref in index.ambiguous_ids:
        raise ValueError(f'ambiguous clip ref {ref!r}: multiple videos share this slug / id')
    if video_ref not in index.clips:
        return None
    bounds = CLIP_WINDOW.fullmatch(window)
    if not bounds:
        return None
    start, end = float(bounds.group(1)), float(bounds.group(2))
    matches = [
        (clip_start, clip_end) for clip_start, clip_end in index.clips[video_ref]
        if abs(start - clip_start) <= CLIP_REF_TOLERANCE_S and abs(end - clip_end) <= CLIP_REF_TOLERANCE_S
    ]
    if len(matches) > 1:
        raise ValueError(f'ambiguous clip ref {ref!r}: matches multiple selected_clips within 0.01 seconds')
    return ('clip', video_ref, *matches[0]) if matches else None


def ref_resolves(ref: str, index: CatalogIndex) -> bool:
    """``<slug>/<id>`` 或 ``<slug>/<video_id>:<start>-<end>`` 能否解析。"""
    try:
        return parse_ref(ref, index) is not None
    except ValueError:
        return False


def ref_covers(candidate: tuple[Any, ...], needed: tuple[Any, ...]) -> bool:
    """``candidate`` 是否算用上了 ``needed``。

    同身份即覆盖；一条选中片段的引用也算用上了它所属的那项素材（视频确实上镜
    了），但不反过来：要求用某个片段时，只说“用了这个视频”不算。
    """
    if candidate == needed:
        return True
    return candidate[0] == 'clip' and needed[0] == 'material' and candidate[1] == needed[1]


def uncovered_required_refs(
    required: list[str], candidates: list[str], index: CatalogIndex
) -> list[str]:
    """必用清单里没被任何候选覆盖的条目（原样返回声明的写法）。"""
    covered = [identity for identity in (parse_ref(ref, index) for ref in candidates) if identity]
    missing = []
    for ref in required:
        needed = parse_ref(ref, index)
        if needed is None or not any(ref_covers(candidate, needed) for candidate in covered):
            missing.append(ref)
    return missing


def material_ref_problem(ws: Path, refs: list[str]) -> str | None:
    """scene-plan 的素材引用不可用的原因，或 None。"""
    _, inputs = load_inputs(ws)
    if not phase_applies(PHASES_BY_ID['5-material-catalog'], inputs):
        return (
            'material_candidates must be empty when there is no catalog phase '
            f'(fetch_materials is false and input_mode is not paper), got refs {list(dict.fromkeys(refs))}'
        )
    index = load_catalog_index(ws)
    if index is None:
        return None
    invalid: list[str] = []
    for ref in dict.fromkeys(refs):
        try:
            identity = parse_ref(ref, index)
        except ValueError as exc:
            invalid.append(str(exc))
        else:
            if identity is None:
                invalid.append(ref)
    if invalid:
        return f'material_candidates refs not found in material-catalog.json or ambiguous: {invalid}'
    return None


def check_harvest_manifest(ws: Path, relpath: str) -> CheckResult:
    """Phase 4 需要 entries，以及至少一个真实的网页抓取批次。"""
    entries_result = check_dict_entries_product(ws, relpath)
    if not entries_result.ok:
        return entries_result
    _, data = read_json_product(ws, relpath)
    problem = harvest_manifest.manifest_problem(data, base=ws / 'harvest_page')
    if problem:
        return CheckResult(STATUS_CORRUPT, f'{problem}; regenerate the applicable paper / harvest phase')
    batches = data.get('harvest_batches')
    if not isinstance(batches, list) or not batches:
        return CheckResult(STATUS_CORRUPT, 'harvest_batches is not a non-empty list')
    return OK


duration_minutes = video_contract.duration_minutes


def available_designs() -> list[str]:
    """skill 的 modules/designs/ 下注册的 design 名。"""
    return video_contract.available_designs(SKILL_ROOT)


def design_problem(design: Any) -> str | None:
    """inputs.json 的 design 不可用的原因，或 None。

    只接受当前库 modules/designs/ 下注册的 design：从库里移除的主题不再以工作区
    里的历史副本变相存续，那会让已删除的资源继续驱动新的生成。
    """
    designs = available_designs()
    if isinstance(design, str) and design and '/' not in design and design in designs:
        return None
    return f'field design {design!r} is not an available design (choose one of: {", ".join(designs)})'


def load_inputs(ws: Path) -> tuple[CheckResult, dict[str, Any] | None]:
    """校验 inputs.json 并返回 (result, 解析出的 inputs)。"""
    result, data = read_json_product(ws, 'inputs.json')
    if not result.ok:
        return result, None
    if not isinstance(data, dict):
        return CheckResult(STATUS_CORRUPT, 'JSON root is not an object'), None
    missing_fields = [field for field in INPUTS_REQUIRED_FIELDS if field not in data]
    if missing_fields:
        return CheckResult(
            STATUS_CORRUPT, f'missing required fields: {", ".join(missing_fields)}'
        ), None
    if not isinstance(data['fetch_materials'], bool):
        return CheckResult(STATUS_CORRUPT, 'field fetch_materials is not a boolean'), None
    try:
        validate_delegation(data)
    except ValueError as exc:
        return CheckResult(STATUS_CORRUPT, str(exc)), None
    orientation = video_contract.orientation_problem(data['orientation'])
    if orientation:
        return CheckResult(STATUS_CORRUPT, orientation), None
    if duration_minutes(data['duration']) is None:
        # 与“design 被移除”同理：inputs.json 的其余部分仍可用于
        # 判断阶段适用性，只有 Phase 1 需要重写这个字段。
        return CheckResult(
            STATUS_CORRUPT,
            'field duration must be the target length in minutes (分钟数): a positive number '
            f'such as 5, or a number with a minutes unit such as "5min", got {data["duration"]!r}',
        ), data
    problem = design_problem(data['design'])
    if problem:
        # 例如一个在某主题被移除之前创建的项目：退回 Phase 1
        # 选一个仍然存在的。inputs.json 的其余部分是有效的，因此
        # 它也会被返回，阶段适用性（paper / fetch）依然成立。
        return CheckResult(STATUS_CORRUPT, problem), data
    if 'qa_level' in data and data['qa_level'] not in QA_LEVELS:
        return CheckResult(
            STATUS_CORRUPT,
            f'field qa_level must be one of {" / ".join(QA_LEVELS)}, got {data["qa_level"]!r}',
        ), None
    approval_gates = data.get('approval_gates', [])
    if (
        not isinstance(approval_gates, list)
        or any(not isinstance(gate, str) or gate not in GATES for gate in approval_gates)
        or len(set(approval_gates)) != len(approval_gates)
    ):
        return CheckResult(
            STATUS_CORRUPT,
            f'field approval_gates must be a list of distinct gate names ({", ".join(GATES)}); '
            f'use [] for fully automatic, got {approval_gates!r}',
        ), None
    for field in REQUESTS_FIELDS:
        # 各阶段整理、消费自己的那一条；catalog 没有要求列表。
        if field in data:
            problem = video_contract.requests_problem(field, data[field])
            if problem:
                return CheckResult(STATUS_CORRUPT, problem), None
    if 'material_search_requests' in data:
        # 这是“用户要在哪个平台找素材”的记录，不是重做的触发依据：状态脚本
        # 不看它判断要不要重做，改变它时由主 agent 登记 Phase 4 重做。
        requests = data['material_search_requests']
        if (
            not isinstance(requests, list)
            or any(not isinstance(request, str) or not request.strip() for request in requests)
        ):
            return CheckResult(
                STATUS_CORRUPT,
                'field material_search_requests must be a list of non-empty strings '
                f'(omit it when the user asked for no platform search), got {requests!r}',
            ), None
    return OK, data


def check_inputs_product(ws: Path, relpath: str) -> CheckResult:
    result, _ = load_inputs(ws)
    return result


def load_workspace_visual_scenes(ws: Path) -> tuple[list[dict[str, Any]] | None, str | None]:
    """当前视觉声明；不存在时返回 (None, None)，非法时返回具体原因。"""
    path = ws / video_contract.VISUAL_SCENES_PATH
    if not path.is_file():
        return None, None
    _, inputs = load_inputs(ws)
    if inputs is None:
        return None, 'inputs.json is unavailable for scene canvas validation'
    try:
        duration_s = media.probe_duration(ws / 'voice_clone' / 'narration.mp3')
        scenes = video_contract.load_visual_scenes(
            path, SKILL_ROOT, inputs.get('orientation'), duration_s, ws=ws,
        )
    except (ValueError, OSError, media.MediaToolMissing, media.MediaProbeError) as exc:
        return None, str(exc)
    return scenes, None


def declared_visual_layouts(ws: Path, visual_scenes: list[dict[str, Any]] | None) -> list[str]:
    """scenes.json 声明的合法 layout 名；即使时间覆盖尚未通过，也供模板与指纹读取。"""
    if visual_scenes is not None:
        return sorted({scene['layout'] for scene in visual_scenes})
    _, data = read_json_product(ws, video_contract.VISUAL_SCENES_PATH)
    if not isinstance(data, dict) or not isinstance(data.get('scenes'), list):
        return []
    return sorted({
        scene['layout']
        for scene in data['scenes']
        if isinstance(scene, dict)
        and isinstance(scene.get('layout'), str)
        and video_contract.layout_contract_problem(SKILL_ROOT, scene['layout']) is None
    })


def check_visual_scenes_product(ws: Path, relpath: str) -> CheckResult:
    """新视觉声明存在时严格校验；旧单 layout 工程不要求补写它。"""
    path = ws / relpath
    if not path.exists():
        _, inputs = load_inputs(ws)
        if inputs is not None and inputs.get('layout') is not None:
            return OK
        return CheckResult(STATUS_MISSING, 'visual scene declaration is required before Phase 8 can complete')
    if not path.is_file():
        return CheckResult(STATUS_CORRUPT, 'visual scene declaration is not a file')
    _, problem = load_workspace_visual_scenes(ws)
    return CheckResult(STATUS_CORRUPT, problem) if problem else OK


def check_visual_inputs(ws: Path) -> dict[str, CheckResult]:
    """Phase 8 的输入前置条件：视觉配置由本阶段决定，所以校验也留在本阶段。

    它和输出产物检查分开报告：layout 缺失 / 不在库里 / 与朝向对不上，或选中的
    模板不支持这个 layout，都是本阶段要改的东西，而不是回到 Phase 1。
    """
    _, inputs = load_inputs(ws)
    if inputs is None:
        # inputs.json 本身不合格时由 Phase 1 承担，这里不多报一次。
        return {}
    problems: dict[str, CheckResult] = {}

    def record(field: str, detail: str) -> None:
        problems[f'{INPUTS_FIELD_PREFIX}{field}'] = CheckResult(STATUS_CORRUPT, detail)

    visual_scenes, _ = load_workspace_visual_scenes(ws)
    uses_visual_scenes = (ws / video_contract.VISUAL_SCENES_PATH).exists()
    layout = inputs.get('layout')
    if not uses_visual_scenes and 'layout' in inputs:
        problem = video_contract.layout_contract_problem(SKILL_ROOT, layout)
        if problem:
            record('layout', problem)
        else:
            path = video_contract.effective_resource(SKILL_ROOT, ws, f'modules/layouts/{layout}.json', refresh=False)
            problem = video_contract.layout_file_problem(path, inputs.get('orientation'), str(layout))
            if problem:
                record('layout', problem)
    template = inputs.get('template')
    if 'template' not in inputs:
        # template 缺省表示“还没选”：模板选择归 composition agent，它必须在
        # 完成前写回字段（模板名或 null），否则无法知道它到底用没用模板。
        record(
            'template',
            'field template is not set: composition must write the chosen template name, '
            'or null when it uses no template',
        )
    else:
        problem = video_contract.template_contract_problem(SKILL_ROOT, template)
        if problem:
            record('template', problem)
        elif template is not None:
            supported = video_contract.template_layouts(SKILL_ROOT, str(template), ws=ws)
            if supported is None:
                record(
                    'template',
                    f'template {template!r} has no supported_layouts declaration in '
                    f'modules/templates/{template}/{template}.json',
                )
            else:
                if uses_visual_scenes:
                    used_layouts = declared_visual_layouts(ws, visual_scenes)
                elif 'layout' in inputs:
                    used_layouts = [layout]
                else:
                    used_layouts = []
                incompatible = [name for name in used_layouts if name not in supported]
                if incompatible:
                    record(
                        'template',
                        f'template {template!r} supports layouts {", ".join(supported)}, not '
                        f'{", ".join(map(str, incompatible))}: choose compatible scene layouts or write template: null',
                    )
    return problems


def check_paper_metadata(ws: Path, relpath: str) -> CheckResult:
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, dict):
        return CheckResult(STATUS_CORRUPT, 'JSON root is not an object')
    if data.get('source_type') != 'paper_pdf':
        return CheckResult(STATUS_CORRUPT, 'field source_type is not "paper_pdf"')
    paper_metadata = data.get('paper_metadata')
    if not isinstance(paper_metadata, dict):
        return CheckResult(STATUS_CORRUPT, 'missing paper_metadata')
    # full_markdown_path 相对 harvest 根目录；MinerU 没有产出完整 markdown 时
    # 确实是 null。绝对路径或跨出目录的路径不是当前格式，不接受的版本会被要求
    # 重新解析。
    if 'full_markdown_path' not in paper_metadata:
        return CheckResult(STATUS_CORRUPT, 'missing paper_metadata.full_markdown_path')
    markdown_path = paper_metadata['full_markdown_path']
    if markdown_path is not None:
        problem = stored_path_problem(markdown_path, base=ws / 'harvest_page')
        if problem:
            return CheckResult(
                STATUS_CORRUPT,
                f'paper_metadata.full_markdown_path is not a relative path inside harvest_page: {problem}',
            )
    return OK


def check_paper_manifest(ws: Path, relpath: str) -> CheckResult:
    """paper 模式下的 harvest_page/manifest.json：parse-pdf 把主论文的条目
    upsert 进共享 manifest，Phase 5 再从该 manifest 构建 catalog；否则在
    manifest 存在之前解析的（或 manifest 丢了该条目的）workspace 会带着空空的
    内容直接进入 Phase 5。"""
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, dict):
        return CheckResult(STATUS_CORRUPT, 'JSON root is not an object')
    problem = harvest_manifest.manifest_problem(data, base=ws / 'harvest_page')
    if problem:
        return CheckResult(STATUS_CORRUPT, f'{problem}; regenerate Phase 2 / material harvest')
    entries = data.get('entries')
    if not isinstance(entries, list) or not entries:
        return CheckResult(STATUS_CORRUPT, 'entries is not a non-empty list')
    for entry in entries:
        if isinstance(entry, dict) and entry.get('slug') == 'main-paper':
            if entry.get('source_type') != 'paper_pdf':
                return CheckResult(STATUS_CORRUPT, 'the main-paper entry is not source_type "paper_pdf"')
            return OK
    return CheckResult(
        STATUS_CORRUPT,
        'no entry with slug main-paper: run scripts/parse-pdf.py --slug main-paper before Phase 5 '
        'reads this manifest',
    )


def check_lexicon_product(ws: Path, relpath: str) -> CheckResult:
    """tts-lexicon.json：一个非空 JSON 对象，把展示形式映射到
    读音形式（两者都是非空字符串）。"""
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, dict) or not data:
        return CheckResult(STATUS_CORRUPT, 'JSON root is not a non-empty object')
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str) or not key or not value:
            return CheckResult(
                STATUS_CORRUPT, f'lexicon entries must be non-empty strings, got {key!r}: {value!r}'
            )
    return OK


# 偏移表契约由 video_contract 与直接对齐入口共用。


def check_narration_offsets(ws: Path, relpath: str) -> CheckResult:
    """narration-offsets.json：make-narration 的偏移表，Phase 7 的
    align-narration 的必需输入。外层结构是 {version, script_length,
    narration_length, segments: [...]}。

    版本与两个字数都是必需的：字数抓得到 script.txt 被编辑却没重跑
    make-narration 的情形。等长编辑不再由内容哈希识别——上游改动后的影响由
    主 agent 按已知修改范围显式登记重做。"""
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    try:
        problem = video_contract.offsets_problem(
            data,
            script_path=ws / 'script.txt' if (ws / 'script.txt').is_file() else None,
            narration_path=ws / 'narration.txt' if (ws / 'narration.txt').is_file() else None,
        )
    except (OSError, UnicodeError) as exc:
        return CheckResult(STATUS_CORRUPT, f'cannot read offset-table source: {exc}')
    return CheckResult(STATUS_CORRUPT, problem) if problem else OK


def paragraph_type_problem(scenes: list[dict[str, Any]]) -> str | None:
    """某个 scene 的 `paragraphs` 里含有非整数的原因，或 None。"""
    for index, scene in enumerate(scenes):
        for number in scene['paragraphs']:
            if isinstance(number, bool) or not isinstance(number, int):
                return f'scene {index} paragraphs must be integers, got {number!r}'
    return None


def paragraph_coverage_problem(scenes: list[dict[str, Any]], paragraph_count: int) -> str | None:
    """各 scene 的段落号不恰好是 {1..paragraph_count} 的原因，或 None。

    多个 scene 可以共用同一段落（某 scene 在段落中间被切开）；只统计并集。
    假定 paragraph_type_problem 没有发现问题。
    """
    covered = {number for scene in scenes for number in scene['paragraphs']}
    missing = sorted(set(range(1, paragraph_count + 1)) - covered)
    out_of_range = sorted(number for number in covered if not 1 <= number <= paragraph_count)
    if not missing and not out_of_range:
        return None
    parts = []
    if missing:
        parts.append(f'missing paragraphs {missing}')
    if out_of_range:
        parts.append(f'out-of-range paragraphs {out_of_range}')
    return f'{";".join(parts)} (script.txt has {paragraph_count} paragraphs)'


def check_scene_plan_product(ws: Path, relpath: str) -> CheckResult:
    """scene-plan.json：一个非空的 scene JSON 列表；每个 scene 都有 scene_id、
    非空的 paragraphs 列表，以及描述内容与演绎的 intent / content_plan（来自
    被委派的写脚本 agent 的叙事级规划）。对照 script.txt，所有 scene 的段落
    必须恰好覆盖它的段落。模板 / pattern / 动作选择属于 composition，因此
    已移除的字段出现即视为不符合当前契约。"""
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, list) or not data:
        return CheckResult(STATUS_CORRUPT, 'JSON root is not a non-empty list')
    for index, scene in enumerate(data):
        if not isinstance(scene, dict):
            return CheckResult(STATUS_CORRUPT, f'scene {index} is not an object')
        if not scene.get('scene_id'):
            return CheckResult(STATUS_CORRUPT, f'scene {index} missing scene_id')
        paragraphs = scene.get('paragraphs')
        if not isinstance(paragraphs, list) or not paragraphs:
            return CheckResult(STATUS_CORRUPT, f'scene {index} missing paragraphs')
        for name in ('intent', 'content_plan'):
            value = scene.get(name)
            if not isinstance(value, str) or not value.strip():
                return CheckResult(
                    STATUS_CORRUPT,
                    f'scene {index} {name} must be a non-empty string '
                    f'("what to explain" / "what to cover and how to walk through it")',
                )
    removed = video_contract.removed_scene_fields_problem(data)
    if removed:
        return CheckResult(STATUS_CORRUPT, removed)
    problem = paragraph_type_problem(data)
    if problem:
        return CheckResult(STATUS_CORRUPT, problem)
    script_result, script = read_nonempty_text(ws, 'script.txt')
    if script_result.ok:  # 否则 script.txt 会单独报告
        problem = paragraph_coverage_problem(data, len(script_text.paragraphs(script)))
        if problem:
            return CheckResult(STATUS_CORRUPT, problem)
    refs: list[str] = []
    for index, scene in enumerate(data):
        candidates = scene.get('material_candidates', [])
        if not isinstance(candidates, list):
            return CheckResult(STATUS_CORRUPT, f'scene {index} material_candidates is not a list')
        for position, candidate in enumerate(candidates):
            ref = candidate.get('ref') if isinstance(candidate, dict) else None
            if not isinstance(ref, str) or not ref:
                return CheckResult(
                    STATUS_CORRUPT,
                    f'scene {index} material_candidates[{position}] has no non-empty string ref',
                )
            refs.append(ref)
    problem = material_ref_problem(ws, refs) if refs else None
    if problem:
        return CheckResult(STATUS_CORRUPT, problem)
    # catalog 声明的必用素材（论文模式的关键图）必须至少被某个 scene 选中：
    # 候选覆盖不等于已经出现在成片，但连候选都没有，composition 也拿不到它。
    required = required_material_refs(ws)
    if required:
        index = load_catalog_index(ws)
        missing = uncovered_required_refs(required, refs, index) if index else list(required)
        if missing:
            return CheckResult(
                STATUS_CORRUPT,
                f'material_candidates leaves required_material_refs unselected: {missing} '
                '(put the key figure / table in the scene that explains it)',
            )
    return OK


def check_transcript(ws: Path, relpath: str) -> CheckResult:
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, list) or not data:
        return CheckResult(STATUS_CORRUPT, 'transcript is not a non-empty sentence list')
    for index, sentence in enumerate(data):
        if not isinstance(sentence, dict):
            return CheckResult(STATUS_CORRUPT, f'sentence {index} is not an object')
        missing = [
            field
            for field in ('begin', 'end', 'text', 'words')
            if field not in sentence
        ]
        if missing:
            return CheckResult(
                STATUS_CORRUPT, f'sentence {index} missing fields: {", ".join(missing)}'
            )
        if not isinstance(sentence['words'], list):
            return CheckResult(STATUS_CORRUPT, f'sentence {index} words is not a list')
    return OK


def check_subtitle_units(ws: Path, relpath: str) -> CheckResult:
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, dict):
        return CheckResult(STATUS_CORRUPT, 'JSON root is not an object')
    units = data.get('units')
    if not isinstance(units, list) or not units:
        return CheckResult(STATUS_CORRUPT, 'units is not a non-empty list')
    return OK


def check_timeline(ws: Path, relpath: str) -> CheckResult:
    """timeline.json：{total_s, paragraphs: [{index, begin_s, end_s}]}；scenes / cues 可选。

    语义节拍已从契约中删除：带 beats 的时间轴是旧构建，要按当前场景规划重跑
    Phase 7，而不是把残留字段当作有效输入。"""
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, dict):
        return CheckResult(STATUS_CORRUPT, 'JSON root is not an object')
    paragraphs = data.get('paragraphs')
    if not isinstance(paragraphs, list) or not paragraphs:
        return CheckResult(STATUS_CORRUPT, 'paragraphs is not a non-empty list')
    for index, paragraph in enumerate(paragraphs):
        if not isinstance(paragraph, dict):
            return CheckResult(STATUS_CORRUPT, f'paragraph {index} is not an object')
        missing = [
            field
            for field in ('index', 'begin_s', 'end_s')
            if not isinstance(paragraph.get(field), (int, float))
        ]
        if missing:
            return CheckResult(
                STATUS_CORRUPT, f'paragraph {index} missing numeric fields: {", ".join(missing)}'
            )
    if 'beats' in data:
        return CheckResult(
            STATUS_CORRUPT,
            'beats is not part of the current timeline: semantic beats were removed '
            '(scene-plan beats no longer exist); re-run Phase 7 to rebuild it',
        )
    return OK


def visible_files(directory: Path) -> list[Path]:
    """`directory` 下任意深度的文件；像 .DS_Store 这样的隐藏文件不计入。"""
    return [
        item
        for item in directory.rglob('*')
        if item.is_file() and not any(part.startswith('.') for part in item.relative_to(directory).parts)
    ]


def check_directory_product(ws: Path, relpath: str) -> CheckResult:
    """一个在任意深度至少含有一个可见文件的目录。"""
    path = ws / relpath
    if not path.exists():
        return CheckResult(STATUS_MISSING)
    if not path.is_dir():
        return CheckResult(STATUS_CORRUPT, 'not a directory')
    if not visible_files(path):
        return CheckResult(STATUS_CORRUPT, 'directory has no files')
    return OK


def check_composition_report(ws: Path, relpath: str) -> CheckResult:
    """composition/check-composition.json：composition agent 上一次
    check-composition 运行保存下来的 stdout；其结论必须是 pass。

    报告是否存在、结论是否 pass、以及（视觉模式下）scenes_checked 是否覆盖
    当前视觉声明，就是全部验收：本脚本不比对源文件哈希或修改时间，也不会因为
    composition 后来又改过而自动判这份报告失效——重跑检查由执行流程显式完成，
    需要时按已知修改范围登记重做。"""
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, dict):
        return CheckResult(STATUS_CORRUPT, 'JSON root is not an object')
    if data.get('verdict') != 'pass':
        return CheckResult(STATUS_CORRUPT, f'verdict must be "pass", got {data.get("verdict")!r}')
    visual_scenes, visual_problem = load_workspace_visual_scenes(ws)
    if visual_problem:
        return CheckResult(STATUS_CORRUPT, visual_problem)
    if visual_scenes is not None:
        expected_coverage = [(scene['scene_id'], scene['layout']) for scene in visual_scenes]
        actual_coverage = [
            (scene.get('scene_id'), scene.get('layout'))
            for scene in data.get('scenes_checked', []) if isinstance(scene, dict)
        ]
        if actual_coverage != expected_coverage:
            return CheckResult(
                STATUS_CORRUPT,
                'scenes_checked does not cover the current visual scenes and layouts: re-run check-composition',
            )
    return OK


def check_qa_report(ws: Path, relpath: str) -> CheckResult:
    """qa/qa-report.json：Phase 9 的 QA 结果，在修复轮次收尾之后写入。
    恰好包含 `findings`（[{scene_id, check, issue, frame}]）与 `verdict`；
    verdict 必须是 pass 或 handed_off（fail 表示修复轮次仍在进行，或已用尽却
    没有交给用户处理）。"""
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, dict):
        return CheckResult(STATUS_CORRUPT, 'JSON root is not an object')
    if set(data.keys()) != {'findings', 'verdict'}:
        return CheckResult(STATUS_CORRUPT, 'qa-report must contain exactly findings and verdict')
    if not isinstance(data['findings'], list):
        return CheckResult(STATUS_CORRUPT, 'findings is not a list')
    for index, finding in enumerate(data['findings']):
        if not isinstance(finding, dict):
            return CheckResult(STATUS_CORRUPT, f'finding {index} is not an object')
        for field in ('scene_id', 'check', 'issue', 'frame'):
            if field not in finding:
                return CheckResult(STATUS_CORRUPT, f'finding {index} missing {field}')
    if data['verdict'] not in ('pass', 'handed_off'):
        return CheckResult(
            STATUS_CORRUPT,
            f'verdict must be pass or handed_off once fix rounds conclude, got {data["verdict"]!r}',
        )
    return OK


# --- 阶段定义 ----------------------------------------------------------------

# 每个产物把它在 workspace 内的相对路径映射到某个检查器。只在部分 workspace
# 中适用的阶段带有 `applies(inputs)` 谓词，以及一个供 inputs.json 读不出来时使用
# 的 `applies_by_default` 兜底（那时报告的是默认序列：standard，带抓取 —— 反正
# 下一个阶段就是 1-gather-inputs）。把谓词和兜底放在阶段旁边，这样新加的条件阶段
# 不会与它们漂移。
def _applies_always(inputs: dict[str, Any]) -> bool:
    return True


def _applies_when_paper(inputs: dict[str, Any]) -> bool:
    return inputs.get('input_mode') in PAPER_MODES


def _applies_when_fetch(inputs: dict[str, Any]) -> bool:
    return bool(inputs.get('fetch_materials'))


def _applies_fetch_or_paper(inputs: dict[str, Any]) -> bool:
    # catalog 也收有论文自己的图和表，它们无论是否抓取网络素材
    # 都存在。
    return video_contract.catalog_applies(inputs)


APPLICABILITY: dict[str, tuple[Callable[[dict[str, Any]], bool], bool]] = {
    'always': (_applies_always, True),
    'paper': (_applies_when_paper, False),
    'fetch': (_applies_when_fetch, True),
    'fetch_or_paper': (_applies_fetch_or_paper, True),
}

PHASES: list[dict[str, Any]] = [
    {
        'id': '1-gather-inputs',
        'title': '收集输入',
        'doc': 'references/phases/01-gather-inputs.md',
        'applies': 'always',
        'products': {'inputs.json': check_inputs_product},
    },
    {
        'id': '2-paper-parse',
        'title': '解析论文（仅论文模式）',
        'doc': 'references/phases/02-paper-parse.md',
        'applies': 'paper',
        'products': {
            'harvest_page/main-paper/metadata.json': check_paper_metadata,
            'harvest_page/manifest.json': check_paper_manifest,
        },
    },
    {
        'id': '3-research',
        'title': '主题调研',
        'doc': 'references/phases/03-research.md',
        'applies': 'always',
        'gate': 'research-brief',
        'products': {'research-brief.md': check_research_brief},
    },
    {
        'id': '4-material-harvest',
        'title': '素材抓取（可选）',
        'doc': 'references/phases/04-material-harvest.md',
        'applies': 'fetch',
        'products': {'harvest_page/manifest.json': check_harvest_manifest},
    },
    {
        'id': '5-material-catalog',
        'title': '素材 catalog',
        'doc': 'references/phases/05-material-catalog.md',
        'applies': 'fetch_or_paper',
        'products': {'material-catalog.json': check_material_catalog},
    },
    {
        'id': '6-script-scene-plan',
        'title': '脚本与场景规划（委派）',
        'doc': 'references/phases/06-script-scene-plan.md',
        'applies': 'always',
        'gate': 'script',
        'products': {
            'script.txt': check_script_text,
            'tts-lexicon.json': check_lexicon_product,
            'narration.txt': check_text_product,
            'narration-offsets.json': check_narration_offsets,
            'scene-plan.json': check_scene_plan_product,
        },
    },
    {
        'id': '7-voice-subtitles',
        'title': '配音与时间对齐',
        'doc': 'references/phases/07-voice-subtitles.md',
        'applies': 'always',
        'products': {
            'voice_clone/narration.mp3': check_file_product,
            'transcribe/transcript.json': check_transcript,
            'transcribe/timeline.json': check_timeline,
        },
    },
    {
        'id': '8-composition',
        'title': 'composition（委派）',
        'doc': 'references/phases/08-composition.md',
        'applies': 'always',
        'precondition': check_visual_inputs,
        'products': {
            'composition/scenes.json': check_visual_scenes_product,
            'composition/assets/subtitle-units.json': check_subtitle_units,
            'composition/storyboard.md': check_text_product,
            'composition/index.html': check_file_product,
            'composition/compositions': check_directory_product,
            'composition/check-composition.json': check_composition_report,
            'composition/renders/final.mp4': check_file_product,
        },
    },
    {
        'id': '9-check-mix',
        'title': '检查与混音',
        'doc': 'references/phases/09-check-mix.md',
        'applies': 'always',
        'products': {
            'composition/renders/final_with_bgm.mp4': check_file_product,
            'qa/qa-report.json': check_qa_report,
        },
    },
]


PHASES_BY_ID = {phase['id']: phase for phase in PHASES}


def phase_applies(phase: dict[str, Any], inputs: dict[str, Any] | None) -> bool:
    applies, applies_by_default = APPLICABILITY[phase['applies']]
    if inputs is None:
        # inputs.json 不可读：报告默认 workspace（standard，带抓取）会走的
        # 那段阶段序列。反正下一个阶段就是 1-gather-inputs。
        return applies_by_default
    return applies(inputs)


# --- 持久状态：用户确认与重做请求 --------------------------------------------


class Approvals:
    """持久的用户确认；按 gate 记录确认事实与时间，不绑定文件哈希。

    已确认的内容需要重做时，由 --redo 显式撤销对应 gate 的旧确认；确认本身
    不会仅因为文件内容变化而失效或自动重新打开。
    """

    def __init__(self, ws: Path) -> None:
        self.path = ws / APPROVALS_PATH
        self.gates: dict[str, dict[str, Any]] = {}
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(data, dict) or data.get('version') != APPROVALS_VERSION:
            return
        gates = data.get('gates')
        if isinstance(gates, dict):
            self.gates = {
                gate: approval
                for gate, approval in gates.items()
                if isinstance(gate, str) and isinstance(approval, dict)
            }

    def matches(self, gate: str) -> bool:
        return gate in self.gates

    def approve(self, gate: str) -> None:
        self.gates[gate] = {
            'approved_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        }
        self._save()

    def clear(self, gate: str) -> None:
        if gate in self.gates:
            del self.gates[gate]
            self._save()

    def _save(self) -> None:
        if not self.gates:
            # 没有确认时不留一个空状态文件；下次确认会重新写入。
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
            return
        staged = stage_json(self.path, {'version': APPROVALS_VERSION, 'gates': self.gates})
        os.replace(staged, self.path)


class Redos:
    """{ws}/.pipeline/redos.json：已登记、尚未完成的重做请求。

    请求是持久状态：普通扫描不会清掉它，只有 --finish 在产物通过检查后才移除
    记录，因此中断的重做永远不会被当成完成。
    """

    def __init__(self, ws: Path) -> None:
        self.path = ws / REDOS_PATH
        self.requests: dict[str, dict[str, Any]] = {}
        # 读不出来的重做记录不能当空记录：那会把用户的要求默默丢掉，所以
        # 留下 error，让那一次运行直接失败。
        self.error: str | None = None
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return
        except OSError as exc:
            self.error = f'{REDOS_PATH} cannot be read: {exc}'
            return
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.error = f'{REDOS_PATH} is not valid JSON: {exc}'
            return
        if not isinstance(data, dict) or data.get('version') != REDOS_VERSION:
            self.error = f'{REDOS_PATH} is not a version {REDOS_VERSION} redo file'
            return
        requests = data.get('requests')
        if not isinstance(requests, dict):
            self.error = f'{REDOS_PATH} has no requests object'
            return
        # 单条要求的格式不单独校验：字段只用来回显原因，真正的要求由阶段自己的
        # 检查兑现，所以最多是少显示一句原因，不会让阶段漏过检查。
        self.requests = {
            phase_id: request
            for phase_id, request in requests.items()
            if isinstance(phase_id, str) and isinstance(request, dict)
        }

    def get(self, phase_id: str) -> dict[str, Any] | None:
        return self.requests.get(phase_id)

    def request(self, phase_id: str, reason: str) -> None:
        self.requests[phase_id] = {
            'reason': reason,
            'requested_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        }
        self._save()

    def finish(self, phase_id: str) -> None:
        self.requests.pop(phase_id, None)
        self._save()

    def _save(self) -> None:
        if not self.requests:
            # 没有待处理的请求时不留一个空状态文件；下次请求会重新写入。
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
            return
        staged = stage_json(self.path, {'version': REDOS_VERSION, 'requests': self.requests})
        os.replace(staged, self.path)


def validate_phase(ws: Path, phase: dict[str, Any]) -> dict[str, CheckResult]:
    """运行某阶段的每个产物检查器；返回失败产物的 {relpath: CheckResult}。

    阶段声明的输入前置条件也一并返回，键用 inputs.json#<field>；
    scan_workspace 会把它们和产物问题分开计数。
    """
    problems: dict[str, CheckResult] = {}
    precondition = phase.get('precondition')
    if precondition is not None:
        problems.update(precondition(ws))
    for relpath, checker in phase['products'].items():
        result = checker(ws, relpath)
        if not result.ok:
            problems[relpath] = result
    return problems


def scan_workspace(
    ws: Path, approvals: Approvals, redos: Redos
) -> dict[str, Any]:
    _, inputs = load_inputs(ws)
    approval_gates = inputs.get('approval_gates', []) if inputs else []

    statuses: list[dict[str, str]] = []
    missing: list[str] = []
    corrupt: list[str] = []
    next_phase: dict[str, Any] | None = None

    for phase in PHASES:
        if not phase_applies(phase, inputs):
            statuses.append({'id': phase['id'], 'status': PHASE_SKIPPED})
            continue
        if next_phase is not None:
            # 更早的阶段尚未完成：它之后的任何东西都还不能信任。
            statuses.append({'id': phase['id'], 'status': PHASE_PENDING})
            continue
        problems = validate_phase(ws, phase)
        if not problems:
            redo = redos.get(phase['id'])
            if redo is not None:
                # 用户或 agent 要求重做：产物就算齐全也不再算完成，直到 --finish。
                statuses.append({'id': phase['id'], 'status': PHASE_REDO})
                next_phase = {
                    'id': phase['id'],
                    'title': phase['title'],
                    'doc': phase['doc'],
                    'reason': REASON_REDO,
                    'redo_reason': redo.get('reason'),
                    'problems': {},
                }
                continue
            gate = phase.get('gate')
            if gate in approval_gates:
                if not approvals.matches(gate):
                    statuses.append({'id': phase['id'], 'status': PHASE_AWAITING_APPROVAL})
                    next_phase = {
                        'id': phase['id'],
                        'title': phase['title'],
                        'doc': phase['doc'],
                        'reason': PHASE_AWAITING_APPROVAL,
                        'gate': gate,
                        'instruction': GATES[gate]['instruction'],
                        'problems': {},
                    }
                    continue
            statuses.append({'id': phase['id'], 'status': PHASE_COMPLETED})
            continue
        product_problems = {
            relpath: result for relpath, result in problems.items()
            if not relpath.startswith(INPUTS_FIELD_PREFIX)
        }
        for relpath, result in product_problems.items():
            if result.status == STATUS_MISSING:
                missing.append(relpath)
            else:
                corrupt.append(relpath)
        # 只有完全没有东西可修时才算 missing；任何坏文件或输入前置条件失败都让该
        # 阶段成为 corrupt（输入问题也是本阶段要修的东西）。
        all_missing = all(result.status == STATUS_MISSING for result in problems.values())
        reason = STATUS_MISSING if all_missing else STATUS_CORRUPT
        statuses.append({'id': phase['id'], 'status': reason})
        next_phase = {
            'id': phase['id'],
            'title': phase['title'],
            'doc': phase['doc'],
            'reason': reason,
            'problems': {relpath: result.detail for relpath, result in problems.items()},
        }

    def ids_with(status: str) -> list[str]:
        return [entry['id'] for entry in statuses if entry['status'] == status]

    return {
        'success': True,
        'workspace': str(ws.resolve()),
        'input_mode': inputs.get('input_mode') if inputs else None,
        'fetch_materials': inputs.get('fetch_materials') if inputs else None,
        'approval_gates': approval_gates,
        'phases': statuses,
        'completed_phases': ids_with(PHASE_COMPLETED),
        'skipped_phases': ids_with(PHASE_SKIPPED),
        'pending_phases': ids_with(PHASE_PENDING),
        'redo_phases': ids_with(PHASE_REDO),
        'next_phase': next_phase,
        'missing_products': missing,
        'corrupt_products': corrupt,
    }


def approve_gate(
    ws: Path, gate: str, approvals: Approvals, redos: Redos
) -> dict[str, Any] | None:
    """只在该关卡所属阶段的每个产物都通过、且没有待重做时记录确认事实与时间。"""
    phase = PHASES_BY_ID[GATES[gate]['phase']]
    if redos.get(phase['id']) is not None:
        return {'success': False, 'error': f'cannot approve {gate}: a redo is pending for {phase["id"]}'}
    problems = validate_phase(ws, phase)
    if problems:
        return {
            'success': False,
            'error': f'cannot approve {gate}: its products do not pass their checks',
            'problems': {relpath: result.detail or result.status for relpath, result in problems.items()},
        }
    approvals.approve(gate)
    log(f'approved {gate}')
    return None


def request_redo(
    ws: Path, phase_id: str, reason: str, redos: Redos, approvals: Approvals
) -> dict[str, Any] | None:
    """登记某阶段需要重做，保留旧产物。失败时返回失败载荷（那时什么都不写）。

    该阶段带有审稿 gate 时，一并撤销该 gate 的旧确认：确认的是旧内容，重做后
    需要用户重新确认。"""
    phase = PHASES_BY_ID[phase_id]
    _, inputs = load_inputs(ws)
    if not phase_applies(phase, inputs):
        return {'success': False, 'error': f'cannot redo {phase_id}: the phase is skipped for this workspace'}
    redos.request(phase_id, reason)
    for gate, spec in GATES.items():
        if spec['phase'] == phase_id:
            approvals.clear(gate)
    log(f'redo requested for {phase_id}')
    return None


def finish_redo(ws: Path, phase_id: str, redos: Redos) -> dict[str, Any] | None:
    """结束一次重做：先清掉标记，再让该阶段走它平时的产物检查。

    先清标记是为了不把一次失败的结束留在原地反复重试；产物检查不能跳过：
    全部合格才算结束。它不要求产物字节与上次不同，也不检查上游是否变过——
    上游改动后的影响由主 agent 按已知修改范围显式登记重做。
    """
    if redos.get(phase_id) is None:
        return {'success': False, 'error': f'cannot finish {phase_id}: no redo is pending for this phase'}
    redos.finish(phase_id)
    phase = PHASES_BY_ID[phase_id]
    problems = validate_phase(ws, phase)
    if problems:
        return {
            'success': False,
            'error': f'cannot finish {phase_id}: its products do not pass their checks',
            'problems': {relpath: result.detail or result.status for relpath, result in problems.items()},
        }
    log(f'redo finished for {phase_id}')
    return None


def main() -> int:
    args = parse_args()
    ws = Path(args.workspace)
    try:
        if not ws.exists():
            raise FileNotFoundError(f'workspace does not exist: {ws}')
        if not ws.is_dir():
            raise NotADirectoryError(f'workspace is not a directory: {ws}')
        approvals = Approvals(ws)
        redos = Redos(ws)
        if redos.error is not None:
            log(f'error: {redos.error}; fix or remove {REDOS_PATH}, then run again')
            print_json({'success': False, 'error': redos.error})
            return 1
        if args.approve:
            failure = approve_gate(ws, args.approve, approvals, redos)
            if failure is not None:
                log(f"error: {failure['error']}")
                print_json(failure)
                return 2
        if args.redo:
            failure = request_redo(ws, args.redo, args.reason.strip(), redos, approvals)
            if failure is not None:
                log(f"error: {failure['error']}")
                print_json(failure)
                return 1
        if args.finish:
            failure = finish_redo(ws, args.finish, redos)
            if failure is not None:
                log(f"error: {failure['error']}")
                print_json(failure)
                return 2
        result = scan_workspace(ws, approvals, redos)
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
    raise SystemExit(cli.run(main, TOOL_NAME))
