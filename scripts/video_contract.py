"""流水线公共契约的唯一来源。

下面这些字段名、枚举与映射被多个脚本读取：pipeline-status.py（阶段检查、上游
指纹）、prepare-handoff.py（handoff 输入与画面前置校验）、align-narration.py
（偏移表契约与字幕规格）。规则只在这里写一份，声明与实际读取就不会各自漂移。

这里只定义“当前契约是什么”，不含任何旧格式迁移或兼容分支：不符合当前契约的
数据由调用方明确报告缺失 / 损坏 / 不支持。
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

# Phase 1 的基础字段：用户输入落地成 inputs.json 时必须齐全的部分。
# layout 与 template 不在这里：它们是 Phase 8 的画面决策。
INPUTS_BASE_FIELDS = (
    'source',
    'input_mode',
    'duration',
    'language',
    'orientation',
    'design',
    'coding_agent',
    'fetch_materials',
)

# 每个委派步骤实际读取的字段。步骤只校验自己用到的部分，不把整份输入表
# 强加给所有步骤。
STEP_INPUTS_FIELDS: dict[str, tuple[str, ...]] = {
    'catalog': ('coding_agent', 'input_mode', 'fetch_materials'),
    'script': ('coding_agent', 'duration', 'language', 'input_mode', 'fetch_materials'),
    'composition': ('coding_agent', 'duration', 'language', 'input_mode', 'fetch_materials',
                    'design', 'orientation'),
}

# 用户在对话里提出的长期要求，按阶段分开保存；catalog 没有要求列表。
NARRATION_REQUESTS_FIELD = 'narration_requests'
COMPOSITION_REQUESTS_FIELD = 'composition_requests'
REQUESTS_FIELDS = (NARRATION_REQUESTS_FIELD, COMPOSITION_REQUESTS_FIELD)
STEP_REQUESTS_FIELD: dict[str, str | None] = {
    'catalog': None,
    'script': NARRATION_REQUESTS_FIELD,
    'composition': COMPOSITION_REQUESTS_FIELD,
}

# qa_level 可选：缺省表示 standard 档，给出时必须是枚举值之一。
QA_LEVELS = ('quick', 'standard', 'strict')
QA_LEVEL_DEFAULT = 'standard'

# 规范朝向 → 画布像素尺寸。一个朝向只有一个尺寸，因此布局、渲染检查与字幕
# 规格不会对同一份项目给出互相矛盾的画布。3:4 是竖屏默认，9:16 仅用户在明确
# 要求时才用。
ORIENTATION_CANVAS: dict[str, tuple[int, int]] = {
    'landscape': (1920, 1080),
    'portrait': (1080, 1920),
    'portrait-3:4': (1080, 1440),
}

# 缺省值与显式空值等价的可选字段：缺省要求列表与 [] 表达同一件事，
# 因此它们也必须得到同一个指纹。
INPUTS_FIELD_DEFAULTS: dict[str, Any] = {
    'qa_level': QA_LEVEL_DEFAULT,
    NARRATION_REQUESTS_FIELD: [],
    COMPOSITION_REQUESTS_FIELD: [],
}


NAME = re.compile(r'[\w-]+')
DURATION_MINUTES = re.compile(
    r'^\s*(\d+(?:\.\d+)?)\s*(?:min|mins|minute|minutes|分钟|分)?\s*$', re.IGNORECASE
)


def duration_minutes(value: Any) -> float | None:
    """正的有限分钟数；字符串只接受分钟单位。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        minutes = float(value)
    elif isinstance(value, str):
        match = DURATION_MINUTES.fullmatch(value)
        minutes = float(match.group(1)) if match else 0.0
    else:
        return None
    return minutes if math.isfinite(minutes) and minutes > 0 else None


def catalog_applies(inputs: dict[str, Any]) -> bool:
    """论文素材不受联网策略影响；标准无素材模式不消费残留 catalog。"""
    return bool(inputs.get('fetch_materials')) or inputs.get('input_mode') == 'paper'


def input_field_problem(field: str, value: Any) -> str | None:
    """字段类型的公共规则；调用方只传入自己声明消费的字段。"""
    if field == 'orientation':
        return orientation_problem(value)
    if field == 'duration':
        if duration_minutes(value) is None:
            return f'field duration must be a positive finite length in minutes (分钟数), got {value!r}'
    elif field == 'fetch_materials':
        if not isinstance(value, bool):
            return f'field fetch_materials must be a boolean, got {value!r}'
    elif field in ('coding_agent', 'language', 'input_mode'):
        if not isinstance(value, str) or not value.strip():
            return f'field {field} must be a non-empty string, got {value!r}'
    elif field in ('design', 'layout', 'template'):
        if field == 'template' and value is None:
            return None
        if not isinstance(value, str) or NAME.fullmatch(value) is None:
            return f'field {field} must be a plain name, got {value!r}'
    elif field in REQUESTS_FIELDS:
        return requests_problem(field, value)
    return None


def orientation_canvas(orientation: Any) -> tuple[int, int] | None:
    """规范朝向对应的画布尺寸；不是三种规范朝向之一时为 None。"""
    return ORIENTATION_CANVAS.get(orientation) if isinstance(orientation, str) else None


def orientation_problem(orientation: Any) -> str | None:
    """orientation 不可用的原因，或 None。"""
    if orientation_canvas(orientation) is not None:
        return None
    names = ', '.join(ORIENTATION_CANVAS)
    return f'field orientation must be one of {names}, got {orientation!r}'


def canvas_problem(canvas: Any, orientation: Any, layout: str) -> str | None:
    """layout 的 canvas 与已确定的朝向不一致的原因，或 None。

    朝向决定画布尺寸，因此这里比对完整宽高，而不只看横竖：9:16 与 3:4 都是竖屏，
    混用会让字幕预算和渲染分辨率悄悄错位。
    """
    problem = orientation_problem(orientation)
    if problem:
        return problem
    if not isinstance(canvas, dict):
        return f'layout {layout!r} has no canvas object'
    try:
        width, height = int(canvas['width']), int(canvas['height'])
    except (KeyError, TypeError, ValueError) as exc:
        return f'layout {layout!r} has no usable canvas width / height: {exc}'
    expected = ORIENTATION_CANVAS[orientation]
    if (width, height) != expected:
        return (
            f'layout {layout!r} is {width}x{height}, but orientation {orientation} is '
            f'{expected[0]}x{expected[1]}'
        )
    return None


def requests_problem(field: str, value: Any) -> str | None:
    """要求列表不可用的原因，或 None：非空字符串组成的列表。

    缺省与 [] 等价；元素为空或只有空白就是损坏，因为它会变成一条空的 handoff
    指令。
    """
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        return (
            f'field {field} must be a list of non-empty strings '
            f'(omit it when the user asked for nothing), got {value!r}'
        )
    return None


def request_items(data: dict[str, Any], field: str | None) -> list[str]:
    """某步骤要看的用户要求；字段缺省时为 []，与显式 [] 等价。"""
    if not field:
        return []
    value = data.get(field, [])
    return list(value) if isinstance(value, list) else []


# --- 模块库资源 --------------------------------------------------------------
#
# “库里有什么”与“用哪个副本校验”只能有一套规则：状态脚本、handoff 准备和
# 渲染检查都从这里取，否则它们会对同一份项目给出互相矛盾的结论。

LAYOUTS_PATH = 'modules/layouts'
TEMPLATES_PATH = 'modules/templates'
DESIGNS_PATH = 'modules/designs'


def _named_doc_dirs(root: Path, *, with_contract: bool) -> list[str]:
    """``root`` 下以 <名>/<名>.md（且可选的 <名>/<名>.json）声明自己的子目录名。"""
    if not root.is_dir():
        return []
    names = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        if not (child / f'{child.name}.md').is_file():
            continue
        if with_contract and not (child / f'{child.name}.json').is_file():
            continue
        names.append(child.name)
    return sorted(names)


def _named_doc_files(root: Path) -> list[str]:
    """``root`` 下的模块名：每份 <名>.json 注册一个模块。

    文档可以是自己的 <名>.md，也可以是同族共享的 <前缀>.md：portrait.md 同时覆盖
    portrait 与 portrait-3x4 两个竖屏画布，因此 portrait-3x4 只有 .json。缺少任何
    可用文档的 .json 不算注册（那是残缺的模块）。
    """
    if not root.is_dir():
        return []
    names = []
    for contract in root.glob('*.json'):
        stem = contract.stem
        if (root / f'{stem}.md').is_file() or (root / f'{stem.split("-", 1)[0]}.md').is_file():
            names.append(stem)
    return sorted(names)


def available_designs(skill_root: Path) -> list[str]:
    """skill 的 modules/designs/ 下注册的 design（文档 + JSON 契约）。"""
    return _named_doc_dirs(skill_root / DESIGNS_PATH, with_contract=True)


def available_layouts(skill_root: Path) -> list[str]:
    """skill 的 modules/layouts/ 下注册的 layout（文档 + 区域定义 JSON）。"""
    return _named_doc_files(skill_root / LAYOUTS_PATH)


def available_templates(skill_root: Path) -> list[str]:
    """skill 的 modules/templates/ 下注册的模板。"""
    return _named_doc_dirs(skill_root / TEMPLATES_PATH, with_contract=True)


def layout_contract_problem(skill_root: Path, layout: Any) -> str | None:
    """layout 名不可用的原因，或 None。只接受当前库注册的 layout。"""
    layouts = available_layouts(skill_root)
    if isinstance(layout, str) and layout in layouts:
        return None
    return f'field layout {layout!r} is not an available layout (choose one of: {", ".join(layouts)})'


def template_contract_problem(skill_root: Path, template: Any) -> str | None:
    """template 名不可用的原因，或 None。None / 缺省表示不使用模板。"""
    if template is None:
        return None
    templates = available_templates(skill_root)
    if isinstance(template, str) and template in templates:
        return None
    return (
        f'field template must be null or one of {", ".join(templates)}, got {template!r}'
    )


def template_layouts(
    skill_root: Path, template: str, *, ws: Path | None = None, refresh: bool = False,
) -> list[str] | None:
    """模板声明它支持的 layout（``<t>/<t>.json`` 的 supported_layouts）。

    模板与 layout 的兼容关系只写在模板自己的声明里：库入口、handoff 准备和
    composition agent 读的是同一份。声明缺失或不合法时返回 None，调用方按错误
    处理，而不是猜一个默认值。
    """
    relpath = f'{TEMPLATES_PATH}/{template}/{template}.json'
    path = effective_resource(skill_root, ws, relpath, refresh=refresh) if ws is not None else skill_root / relpath
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get('template') != template:
        return None
    layouts = data.get('supported_layouts')
    if not isinstance(layouts, list) or not layouts:
        return None
    if any(not isinstance(name, str) or not name for name in layouts):
        return None
    return list(layouts)


def effective_resource(skill_root: Path, ws: Path, relpath: str, *, refresh: bool) -> Path:
    """校验和引用都必须指向的那个文件。

    不 refresh 时工作区副本存在就用副本（那才是 handoff 和 agent 真正读的文件），
    否则用库文件；refresh 会把副本换成库文件，因此直接校验库文件。
    """
    if refresh:
        return skill_root / relpath
    copy = ws / relpath
    return copy if copy.exists() else skill_root / relpath


# --- scene-plan.json ---------------------------------------------------------
#
# script agent 的场景规划只描述内容与叙事：模板、pattern、动作属于 composition
# 的设计空间，因此这些字段已从契约中删除，出现即视为不符合当前契约。完整
# scene-plan 与 composition 自己的 cue 声明共用这条规则，但只有前者要求
# intent / content_plan（那由 pipeline-status 检查，对齐器只读 cues）。

REMOVED_SCENE_FIELDS = ('template_scene', 'pattern_hints', 'beats')


def removed_scene_fields_problem(scenes: list[Any]) -> str | None:
    """scene 列表里出现已移除字段的原因，或 None。"""
    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        for name in REMOVED_SCENE_FIELDS:
            if name in scene:
                return (
                    f'scene {index} has removed field {name!r}: template / pattern / act '
                    'choices belong to composition; rewrite the scene plan without it'
                )
    return None


# --- narration-offsets.json --------------------------------------------------

NARRATION_OFFSETS_VERSION = 1

# make-narration 记录的字数，以及各自统计的文件。
OFFSETS_LENGTH_SOURCES = (('script_length', 'script.txt'), ('narration_length', 'narration.txt'))

# 内容哈希：缺了它们就只能比字数，而等长编辑看不出文字已经变了。
OFFSETS_HASH_SOURCES = (('script_sha256', 'script.txt'), ('narration_sha256', 'narration.txt'))


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def offsets_problem(
    data: Any, *, script_path: Path | None = None, narration_path: Path | None = None,
) -> str | None:
    """偏移表不符合当前契约的原因，或 None。

    版本、两个字数与两个内容哈希都是必需的。给出源文件时，字数按文本模式统计
    （与 make-narration 的字符映射一致），哈希按文件原始字节比对，不能把 CRLF
    转成 LF 再算。pipeline-status 与 align-narration 共用这套规则。
    """
    if not isinstance(data, dict):
        return 'JSON root is not an object'
    if data.get('version') != NARRATION_OFFSETS_VERSION:
        return f'version must be {NARRATION_OFFSETS_VERSION}, got {data.get("version")!r}'
    segments = data.get('segments')
    if not isinstance(segments, list):
        return 'segments is not a list'
    if not segments:
        return 'segments is an empty list'
    paths = {'script.txt': script_path, 'narration.txt': narration_path}
    texts = {
        name: path.read_text(encoding='utf-8') if path is not None else None
        for name, path in paths.items()
    }
    for field, source in OFFSETS_LENGTH_SOURCES:
        recorded = data.get(field)
        if isinstance(recorded, bool) or not isinstance(recorded, int):
            return f'{field} must be an integer, got {recorded!r}'
        text = texts[source]
        if text is not None and len(text) != recorded:
            return (
                f'{field} is {recorded} but {source} has {len(text)} characters: {source} and this '
                'offset table no longer belong together, re-run scripts/make-narration.py'
            )
    for field, source in OFFSETS_HASH_SOURCES:
        recorded = data.get(field)
        if not isinstance(recorded, str) or not recorded:
            return (
                f'{field} is required and must be a non-empty string, got {recorded!r} '
                '(re-run scripts/make-narration.py)'
            )
        path = paths[source]
        if path is not None and hashlib.sha256(path.read_bytes()).hexdigest() != recorded:
            return (
                f'{field} does not match {source}: {source} was edited without re-running '
                'scripts/make-narration.py'
            )
    return None


def layout_file_problem(path: Path, orientation: Any, layout: str) -> str | None:
    """硬盘上那份 layout 区域定义不合法的原因，或 None。"""
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return f'layout {layout!r} at {path} cannot be read: {exc}'
    if not isinstance(data, dict):
        return f'layout {layout!r} at {path} is not a JSON object'
    if data.get('layout') != layout:
        return f'layout {layout!r} at {path} declares layout {data.get("layout")!r}'
    regions = data.get('regions')
    if not isinstance(regions, list) or not regions:
        return f'layout {layout!r} at {path} has no regions list'
    caption = data.get('caption')
    if not isinstance(caption, dict):
        return f'layout {layout!r} at {path} has no caption object'
    try:
        width = int(caption['width_px'])
        font_size = int(caption['font_size_px'])
        max_lines = int(caption['max_lines'])
    except (KeyError, TypeError, ValueError) as exc:
        return f'layout {layout!r} caption must be width_px / font_size_px / max_lines integers: {exc}'
    if width <= 0 or font_size <= 0 or max_lines < 1:
        return f'layout {layout!r} caption width_px / font_size_px must be positive and max_lines >= 1'
    return canvas_problem(data.get('canvas'), orientation, layout)


# --- composition/scenes.json --------------------------------------------------
#
# Phase 8 的最终视觉场景。它与 Phase 6 的叙事 scene-plan 和 Phase 7 的可选
# timeline.scenes 都是不同的东西：后者只提供语音时间锚点，前者决定字幕预算和
# 布局 QA。视觉场景可在转场时重叠，但字幕布局在任一时刻都必须唯一。

VISUAL_SCENES_VERSION = 1
VISUAL_SCENES_PATH = 'composition/scenes.json'
VISUAL_DURATION_TOLERANCE_S = 0.05


def _finite_seconds(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    seconds = float(value)
    return seconds if math.isfinite(seconds) and seconds >= 0 else None


def visual_scenes_problem(
    data: Any,
    skill_root: Path,
    orientation: Any,
    duration_s: Any,
    *,
    ws: Path | None = None,
    refresh: bool = False,
) -> str | None:
    """视觉场景声明不可用的原因，或 None。

    所有布局都按调用方实际会使用的有效副本校验。除了结构错误，这里还验证整个
    音频时长的视觉覆盖，以及转场重叠期间字幕布局是否仍然唯一。
    """
    duration = _finite_seconds(duration_s)
    if duration is None or duration <= 0:
        return f'actual narration duration must be a positive finite number, got {duration_s!r}'
    if not isinstance(data, dict):
        return 'JSON root is not an object'
    if set(data) != {'version', 'scenes'}:
        return 'root must contain exactly version and scenes'
    if data.get('version') != VISUAL_SCENES_VERSION:
        return f'version must be {VISUAL_SCENES_VERSION}, got {data.get("version")!r}'
    raw_scenes = data.get('scenes')
    if not isinstance(raw_scenes, list) or not raw_scenes:
        return 'scenes must be a non-empty list'
    scenes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_scenes):
        if not isinstance(raw, dict):
            return f'scene {index} is not an object'
        if set(raw) != {'scene_id', 'begin_s', 'end_s', 'layout'}:
            return f'scene {index} must contain exactly scene_id, begin_s, end_s and layout'
        scene_id = raw.get('scene_id')
        if not isinstance(scene_id, str) or not scene_id.strip():
            return f'scene {index} scene_id must be a non-empty string'
        if scene_id in seen:
            return f'duplicate scene_id {scene_id!r}'
        seen.add(scene_id)
        begin, end = _finite_seconds(raw.get('begin_s')), _finite_seconds(raw.get('end_s'))
        if begin is None or end is None or end <= begin:
            return f'scene {scene_id!r} must have finite 0 <= begin_s < end_s'
        if end > duration + VISUAL_DURATION_TOLERANCE_S:
            return f'scene {scene_id!r} ends at {end}, beyond narration duration {duration}'
        layout = raw.get('layout')
        problem = layout_contract_problem(skill_root, layout)
        if problem:
            return f'scene {scene_id!r}: {problem}'
        relpath = f'{LAYOUTS_PATH}/{layout}.json'
        path = effective_resource(skill_root, ws, relpath, refresh=refresh) if ws is not None else skill_root / relpath
        problem = layout_file_problem(path, orientation, str(layout))
        if problem:
            return f'scene {scene_id!r}: {problem}'
        try:
            layout_data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return f'scene {scene_id!r}: cannot load layout: {exc}'
        scenes.append({
            'scene_id': scene_id, 'begin_s': begin, 'end_s': min(end, duration),
            'layout': layout, 'layout_path': path, 'layout_data': layout_data,
        })
    scenes.sort(key=lambda scene: (scene['begin_s'], scene['end_s'], scene['scene_id']))
    if abs(scenes[0]['begin_s']) > VISUAL_DURATION_TOLERANCE_S:
        return f'visual scenes must start at 0, got {scenes[0]["begin_s"]}'
    final_end = max(scene['end_s'] for scene in scenes)
    if abs(final_end - duration) > VISUAL_DURATION_TOLERANCE_S:
        return f'visual scenes must cover narration duration {duration}, last end is {final_end}'

    # 在每个原子区间的内部采样。后开始的 scene 接管字幕；同起点不同 layout
    # 无法确定优先级，显式拒绝而不是依赖 JSON 顺序。
    boundaries = sorted({0.0, duration, *(s['begin_s'] for s in scenes), *(s['end_s'] for s in scenes)})
    for begin, end in zip(boundaries, boundaries[1:]):
        if end - begin <= 1e-9:
            continue
        midpoint = (begin + end) / 2
        active = [s for s in scenes if s['begin_s'] <= midpoint < s['end_s']]
        if not active:
            return f'visual scenes leave [{begin}, {end}) uncovered'
        latest_begin = max(s['begin_s'] for s in active)
        selected = [s for s in active if s['begin_s'] == latest_begin]
        layouts = {s['layout'] for s in selected}
        if len(layouts) != 1:
            return f'ambiguous caption layout at {midpoint}: scenes {", ".join(s["scene_id"] for s in selected)}'
    return None


def load_visual_scenes(
    path: Path,
    skill_root: Path,
    orientation: Any,
    duration_s: Any,
    *,
    ws: Path | None = None,
) -> list[dict[str, Any]]:
    """读取并严格校验视觉 scenes；返回带有效 layout 数据的有序场景。"""
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'visual scenes {path} cannot be read: {exc}') from exc
    problem = visual_scenes_problem(data, skill_root, orientation, duration_s, ws=ws)
    if problem:
        raise ValueError(f'visual scenes {path}: {problem}')
    scenes: list[dict[str, Any]] = []
    for raw in data['scenes']:
        layout = raw['layout']
        relpath = f'{LAYOUTS_PATH}/{layout}.json'
        layout_path = effective_resource(skill_root, ws, relpath, refresh=False) if ws is not None else skill_root / relpath
        scenes.append({
            'scene_id': raw['scene_id'],
            'begin_s': float(raw['begin_s']),
            'end_s': min(float(raw['end_s']), float(duration_s)),
            'layout': layout,
            'layout_path': layout_path,
            'layout_data': json.loads(layout_path.read_text(encoding='utf-8')),
        })
    return sorted(scenes, key=lambda scene: (scene['begin_s'], scene['end_s'], scene['scene_id']))


def caption_layout_segments(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把视觉 scenes 投影成无歧义的有效字幕布局区间。

    输入必须已经由 load_visual_scenes 校验。相邻原子区间保持分开，以保留场景来源；
    字幕生成可以对这些区间取约束，QA 也能据此确定边界前后的有效布局。
    """
    boundaries = sorted({value for scene in scenes for value in (scene['begin_s'], scene['end_s'])})
    segments: list[dict[str, Any]] = []
    for begin, end in zip(boundaries, boundaries[1:]):
        if end - begin <= 1e-9:
            continue
        midpoint = (begin + end) / 2
        active = [s for s in scenes if s['begin_s'] <= midpoint < s['end_s']]
        if not active:
            continue
        selected = max(active, key=lambda scene: scene['begin_s'])
        if segments and segments[-1]['scene_id'] == selected['scene_id'] and segments[-1]['end_s'] == begin:
            segments[-1]['end_s'] = end
        else:
            segments.append({
                'scene_id': selected['scene_id'], 'begin_s': begin, 'end_s': end,
                'layout': selected['layout'], 'layout_path': selected['layout_path'],
                'layout_data': selected['layout_data'],
            })
    return segments


def active_visual_scenes(scenes: list[dict[str, Any]], time_s: float) -> list[dict[str, Any]]:
    """转场时可能同时可见的视觉 scenes；末尾允许闭区间采样。"""
    final_end = max(scene['end_s'] for scene in scenes)
    return [
        scene for scene in scenes
        if scene['begin_s'] <= time_s < scene['end_s']
        or (time_s == final_end and scene['end_s'] == final_end)
    ]


def visual_layout_relpaths(scenes: list[dict[str, Any]]) -> list[str]:
    """实际使用的有效 layout 机器契约；未使用布局不参与失效。"""
    return sorted({f'{LAYOUTS_PATH}/{scene["layout"]}.json' for scene in scenes})
