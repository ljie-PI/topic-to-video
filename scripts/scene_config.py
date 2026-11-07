"""composition/scene-config.json 的公共读取与校验。

Phase 8 的视觉场景唯一机器配置来源。composition agent 逐场景决定 template /
layout 后把它落盘；状态验收（pipeline-status）、字幕（align-narration）与渲染前
检查（check-composition）都经 ``load_scene_config`` 读同一份契约，避免三个脚本
各写一份布局规则。这里只做结构校验，不做视觉选择或渲染。

契约（完整说明与示例见 references/delegation/composition/scene-config.md）：

- 根字段 ``version=1``、``canvas{width,height}``、有限正的 ``total_s``、非空
  ``scenes``；画布等于已确定 orientation 对应的尺寸（调用方传
  ``expected_canvas``）。
- scene 含唯一 ``scene_id``、有效 ``source_scene_ids``、有限
  ``begin_s < end_s``；主场景区间有序、不重叠，按 ``[begin_s, end_s)`` 归属并
  覆盖 ``[0, total_s]``；首末边界在容差内吸附，容忍媒体探测的帧填充尾差。
- ``template`` 为 ``null`` 或 ``{name, scene}``；采用时其模板与场景部分必须在
  模块库中存在（调用方传 ``modules_root``）。
- ``layout`` 含可空 ``preset``、完整 ``regions`` 与 ``caption``；检查一律以
  落盘的实际区域为准，不从 preset 名猜坐标。region 有 id、content/reserved
  kind 与 rect；reserved 区必须写明组件归属；caption 的 width_px /
  font_size_px / max_lines 均为正。
- 不加入哈希、源文件修改时间、构建版本号或“是否最新”的追踪字段。
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import video_contract

SCENE_CONFIG_VERSION = 1
SCENE_CONFIG_PATH = 'composition/scene-config.json'
# 与旧视觉声明一致的首尾边界容差：媒体探测的帧填充尾差不制造毫秒级空隙。
DURATION_TOLERANCE_S = video_contract.VISUAL_DURATION_TOLERANCE_S

REGION_KINDS = ('content', 'reserved')
CAPTION_REGION_ID = 'caption-text'
SCENE_KEYS = {'scene_id', 'source_scene_ids', 'begin_s', 'end_s', 'template', 'layout'}
LAYOUT_KEYS = {'preset', 'regions', 'caption'}
REGION_KEYS = {'id', 'kind', 'rect', 'component'}
RECT_KEYS = {'x', 'y', 'width', 'height'}
CAPTION_KEYS = {'width_px', 'font_size_px', 'max_lines'}
TEMPLATE_KEYS = {'name', 'scene'}
ROOT_KEYS = {'version', 'canvas', 'total_s', 'scenes'}


def _finite_seconds(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    seconds = float(value)
    return seconds if math.isfinite(seconds) and seconds >= 0 else None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _canvas_problem(canvas: Any, expected_canvas: tuple[int, int] | None) -> str | None:
    if not isinstance(canvas, dict) or set(canvas) != {'width', 'height'}:
        return 'canvas must be exactly {width, height}'
    width, height = canvas.get('width'), canvas.get('height')
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 320 for value in (width, height)):
        return f'canvas width / height must be integers of at least 320px, got {canvas!r}'
    if expected_canvas is not None and (width, height) != tuple(expected_canvas):
        return f'canvas is {width}x{height}, expected {expected_canvas[0]}x{expected_canvas[1]}'
    return None


def _rect_problem(rect: Any, canvas: tuple[int, int]) -> str | None:
    if not isinstance(rect, dict) or set(rect) != RECT_KEYS:
        return 'rect must be exactly {x, y, width, height}'
    values: dict[str, float] = {}
    for key in RECT_KEYS:
        value = rect[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return f'rect {key} must be a finite number, got {value!r}'
        values[key] = float(value)
    if values['width'] <= 0 or values['height'] <= 0:
        return f'rect width / height must be positive, got {rect!r}'
    if values['x'] < 0 or values['y'] < 0:
        return f'rect x / y must be >= 0, got {rect!r}'
    if values['x'] + values['width'] > canvas[0] or values['y'] + values['height'] > canvas[1]:
        return f'rect {rect!r} extends beyond the {canvas[0]}x{canvas[1]} canvas'
    return None


def _regions_problem(regions: Any, canvas: tuple[int, int]) -> str | None:
    if not isinstance(regions, list) or not regions:
        return 'regions must be a non-empty list'
    seen: set[str] = set()
    for index, region in enumerate(regions):
        label = f'region {index}'
        if not isinstance(region, dict) or not set(region) <= REGION_KEYS or not {'id', 'kind', 'rect'} <= set(region):
            return f'{label} must contain id, kind, rect and optional component'
        region_id = region['id']
        if not isinstance(region_id, str) or not region_id.strip():
            return f'{label} id must be a non-empty string'
        if region_id in seen:
            return f'duplicate region id {region_id!r}'
        seen.add(region_id)
        label = f'region {region_id!r}'
        kind = region['kind']
        if kind not in REGION_KINDS:
            return f'{label} kind must be one of {", ".join(REGION_KINDS)}, got {kind!r}'
        component = region.get('component')
        if kind == 'reserved':
            if not isinstance(component, str) or not component.strip():
                return f'{label} (reserved) must declare its component'
        elif component is not None and (not isinstance(component, str) or not component.strip()):
            return f'{label} component must be a non-empty string when set'
        problem = _rect_problem(region['rect'], canvas)
        if problem:
            return f'{label}: {problem}'
    return None


def _caption_problem(caption: Any) -> str | None:
    if not isinstance(caption, dict) or set(caption) != CAPTION_KEYS:
        return 'caption must be exactly {width_px, font_size_px, max_lines}'
    width = _positive_int(caption['width_px'])
    font_size = _positive_int(caption['font_size_px'])
    max_lines = _positive_int(caption['max_lines'])
    if width is None or font_size is None or max_lines is None:
        return f'caption width_px / font_size_px / max_lines must be positive integers, got {caption!r}'
    return None


def _template_problem(template: Any, modules_root: Path | None) -> str | None:
    if template is None:
        return None
    if not isinstance(template, dict) or set(template) != TEMPLATE_KEYS:
        return 'template must be null or exactly {name, scene}'
    name, scene = template['name'], template['scene']
    if not isinstance(name, str) or not name.strip():
        return f'template name must be a non-empty string, got {name!r}'
    if not isinstance(scene, str) or not scene.strip():
        return f'template scene must be a non-empty string, got {scene!r}'
    if modules_root is None:
        return None
    problem = video_contract.template_contract_problem(modules_root, name)
    if problem:
        return problem
    path = modules_root / video_contract.TEMPLATES_PATH / name / f'{name}.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return f'template {name!r} declaration cannot be read: {exc}'
    scenes = data.get('scenes') if isinstance(data, dict) else None
    if not isinstance(scenes, list) or scene not in scenes:
        return f'template {name!r} has no scene {scene!r} (declared scenes: {scenes!r})'
    return None


def _normalized_scenes(
    data: Any,
    *,
    expected_canvas: tuple[int, int] | None,
    known_scene_ids: set[str] | frozenset[str] | None,
    modules_root: Path | None,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    """校验并归一化 scenes 列表；成功时把容差内边界吸附到 [0, total_s]。"""
    raw_scenes = data['scenes']
    if not isinstance(raw_scenes, list) or not raw_scenes:
        return None, 'scenes must be a non-empty list'

    scenes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_scenes):
        if not isinstance(raw, dict):
            return None, f'scene {index} is not an object'
        if set(raw) != SCENE_KEYS:
            return None, (
                f'scene {index} must contain exactly {", ".join(sorted(SCENE_KEYS))}; '
                'hash / mtime / build tracking fields are not part of the contract'
            )
        scene_id = raw['scene_id']
        if not isinstance(scene_id, str) or not scene_id.strip():
            return None, f'scene {index} scene_id must be a non-empty string'
        label = f'scene {scene_id!r}'
        if scene_id in seen:
            return None, f'duplicate scene_id {scene_id!r}'
        seen.add(scene_id)
        sources = raw['source_scene_ids']
        if (
            not isinstance(sources, list)
            or not sources
            or any(not isinstance(item, str) or not item.strip() for item in sources)
        ):
            return None, f'{label}: source_scene_ids must be a non-empty list of non-empty strings'
        if known_scene_ids is not None:
            unknown = [item for item in sources if item not in known_scene_ids]
            if unknown:
                return None, f'{label}: source_scene_ids {unknown!r} are not known narrative scene ids'
        begin, end = _finite_seconds(raw['begin_s']), _finite_seconds(raw['end_s'])
        if begin is None or end is None or end <= begin:
            return None, f'{label} must have finite 0 <= begin_s < end_s'
        if end > data['total_s'] + DURATION_TOLERANCE_S:
            return None, f'{label} ends at {end}, beyond total_s {data["total_s"]}'
        problem = _template_problem(raw['template'], modules_root)
        if problem:
            return None, f'{label}: template: {problem}'
        layout = raw['layout']
        if not isinstance(layout, dict) or set(layout) != LAYOUT_KEYS:
            return None, f'{label}: layout must contain exactly preset, regions and caption'
        preset = layout['preset']
        if preset is not None and (not isinstance(preset, str) or not preset.strip()):
            return None, f'{label}: layout preset must be null or a non-empty layout name, got {preset!r}'
        if modules_root is not None and preset is not None:
            problem = video_contract.layout_contract_problem(modules_root, preset)
            if problem:
                return None, f'{label}: layout preset: {problem}'
        canvas = (data['canvas']['width'], data['canvas']['height'])
        problem = _regions_problem(layout['regions'], canvas)
        if problem:
            return None, f'{label}: layout {problem}'
        problem = _caption_problem(layout['caption'])
        if problem:
            return None, f'{label}: layout {problem}'
        scenes.append({
            'scene_id': scene_id,
            'source_scene_ids': list(sources),
            'begin_s': begin,
            'end_s': min(end, data['total_s']),
            'template': dict(template) if isinstance(template := raw['template'], dict) else None,
            'layout': {
                'preset': preset,
                'regions': layout['regions'],
                'caption': layout['caption'],
            },
        })

    # 主区间按 [begin_s, end_s) 有序、不重叠并覆盖 [0, total_s]；边界在容差内
    # 吸附，避免媒体探测的帧填充尾差留下毫秒级空隙。
    for previous, current in zip(scenes, scenes[1:]):
        if current['begin_s'] < previous['begin_s']:
            return None, (
                f'scene {current["scene_id"]!r} begins at {current["begin_s"]}, '
                f'before scene {previous["scene_id"]!r}: scenes must be ordered by begin_s'
            )
        gap = current['begin_s'] - previous['end_s']
        if gap < -DURATION_TOLERANCE_S:
            return None, (
                f'scene {current["scene_id"]!r} overlaps scene {previous["scene_id"]!r} '
                f'by {-gap:.3f}s: main ranges must be disjoint; transitions belong to visuals'
            )
        if gap > DURATION_TOLERANCE_S:
            return None, (
                f'scenes leave [{previous["end_s"]}, {current["begin_s"]}) uncovered: '
                f'scene {current["scene_id"]!r} must begin where the previous scene ends'
            )
        current['begin_s'] = previous['end_s']
    first = scenes[0]
    if abs(first['begin_s']) > DURATION_TOLERANCE_S:
        return None, f'scenes must start at 0, scene {first["scene_id"]!r} begins at {first["begin_s"]}'
    first['begin_s'] = 0.0
    last = scenes[-1]
    if abs(last['end_s'] - data['total_s']) > DURATION_TOLERANCE_S:
        return None, (
            f'scenes must cover total_s {data["total_s"]}, scene {last["scene_id"]!r} ends at {last["end_s"]}'
        )
    last['end_s'] = data['total_s']
    return scenes, None


def scene_config_problem(
    data: Any,
    *,
    expected_canvas: tuple[int, int] | None = None,
    known_scene_ids: set[str] | frozenset[str] | None = None,
    modules_root: Path | None = None,
) -> str | None:
    """scene-config 不符合契约的原因，或 None。错误定位到 scene_id 与字段。"""
    if not isinstance(data, dict):
        return 'JSON root is not an object'
    if set(data) != ROOT_KEYS:
        return 'root must contain exactly version, canvas, total_s and scenes'
    if data['version'] != SCENE_CONFIG_VERSION:
        return f'version must be {SCENE_CONFIG_VERSION}, got {data["version"]!r}'
    problem = _canvas_problem(data['canvas'], expected_canvas)
    if problem:
        return f'canvas: {problem}'
    total = _finite_seconds(data['total_s'])
    if total is None or total <= 0:
        return f'total_s must be a positive finite number of seconds, got {data["total_s"]!r}'
    data = {**data, 'total_s': total}
    _, problem = _normalized_scenes(
        data, expected_canvas=expected_canvas, known_scene_ids=known_scene_ids, modules_root=modules_root,
    )
    return problem


def load_scene_config(
    path: Path,
    *,
    expected_canvas: tuple[int, int] | None = None,
    known_scene_ids: set[str] | frozenset[str] | None = None,
    modules_root: Path | None = None,
) -> dict[str, Any]:
    """读取并严格校验 ``composition/scene-config.json``，返回归一化后的配置。

    返回的 dict 与输入同形（version / canvas / total_s / scenes），scenes 按
    ``begin_s`` 排好序、首末边界已吸附到 ``[0, total_s]``，每个 scene 的
    ``layout`` 带完整 ``regions`` / ``caption``——调用方不做视觉选择，直接消费。
    """
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'scene config {path} cannot be read: {exc}') from exc
    if not isinstance(data, dict):
        raise ValueError(f'scene config {path}: JSON root is not an object')
    if set(data) != ROOT_KEYS:
        raise ValueError(
            f'scene config {path}: root must contain exactly version, canvas, total_s and scenes'
        )
    problem = _canvas_problem(data['canvas'], expected_canvas)
    if problem:
        raise ValueError(f'scene config {path}: canvas: {problem}')
    total = _finite_seconds(data['total_s'])
    if total is None or total <= 0:
        raise ValueError(
            f'scene config {path}: total_s must be a positive finite number of seconds, got {data["total_s"]!r}'
        )
    if data['version'] != SCENE_CONFIG_VERSION:
        raise ValueError(
            f'scene config {path}: version must be {SCENE_CONFIG_VERSION}, got {data["version"]!r}'
        )
    scenes, problem = _normalized_scenes(
        {**data, 'total_s': total},
        expected_canvas=expected_canvas, known_scene_ids=known_scene_ids, modules_root=modules_root,
    )
    if problem or scenes is None:
        raise ValueError(f'scene config {path}: {problem}')
    return {
        'version': data['version'],
        'canvas': data['canvas'],
        'total_s': total,
        'scenes': scenes,
    }


def caption_layout_segments(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把校验过的视觉 scenes 投影成有效字幕布局区间。

    scene-config 的主区间不重叠且 scene_id 唯一，每个 scene 恰好投影为一个
    区间。每个 segment 带 ``layout``（借用的 preset 名，自由布局为 None）与
    ``layout_data``（落盘的实际 regions / caption）。
    """
    return [
        {
            'scene_id': scene['scene_id'],
            'begin_s': scene['begin_s'],
            'end_s': scene['end_s'],
            'layout': scene['layout']['preset'],
            'layout_data': scene['layout'],
        }
        for scene in scenes
    ]


# --- 宿主共用的工作区上下文 ----------------------------------------------------
#
# 状态、字幕与渲染前检查都用同一套「工作区 → 画布 / 时长 / 叙事场景」推断，
# 只写一份，调用方不再各自复制。


def workspace_scene_ids(ws: Path) -> set[str] | None:
    """scene-plan.json 的叙事 scene_id 集合；缺失或损坏时不阻塞调用方。"""
    try:
        plan = json.loads((ws / 'scene-plan.json').read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(plan, list):
        return None
    ids = {
        scene['scene_id'] for scene in plan
        if isinstance(scene, dict) and isinstance(scene.get('scene_id'), str)
    }
    return ids or None


def expected_canvas_for(orientation: Any) -> tuple[int, int]:
    """规范 orientation 对应的精确画布；非规范值给出带字段定位的错误。"""
    canvas = video_contract.orientation_canvas(orientation)
    if canvas is None:
        raise ValueError(
            f'inputs.json field orientation must be a canonical orientation, got {orientation!r}'
        )
    return canvas


def load_workspace_expected_canvas(ws: Path) -> tuple[int, int]:
    """读取 ``<ws>/inputs.json``，返回其 orientation 对应的精确画布。"""
    try:
        inputs = json.loads((ws / 'inputs.json').read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'cannot read {ws / "inputs.json"} for scene-config validation: {exc}') from exc
    if not isinstance(inputs, dict):
        raise ValueError(f'{ws / "inputs.json"} root must be an object')
    return expected_canvas_for(inputs.get('orientation'))


def total_s_problem(total_s: float, duration_s: Any) -> str | None:
    """scene-config total_s 与实际配音时长不一致的原因，或 None。

    total_s 以配音为边界（含语音前后的静音画面），两者超出容差就是配置错误，
    不靠改 Phase 7 时间轴凑时长。
    """
    if isinstance(duration_s, bool) or not isinstance(duration_s, (int, float)):
        return f'narration duration must be a positive finite number, got {duration_s!r}'
    if abs(total_s - float(duration_s)) > DURATION_TOLERANCE_S + 0.05:
        return (
            f'scene-config total_s {total_s} does not match narration duration {duration_s}; '
            'total_s bounds the delivered video at the narration length'
        )
    return None


def caption_region(layout: dict[str, Any]) -> dict[str, Any] | None:
    """layout 中字幕所在的保留区域：优先 id ``caption-text``，否则取组件归属
    以 ``caption`` 开头的 reserved 区（例如 component ``caption-bar``）。"""
    regions = layout.get('regions')
    if not isinstance(regions, list):
        return None
    fallback = None
    for region in regions:
        if not isinstance(region, dict) or region.get('kind') != 'reserved':
            continue
        if region.get('id') == CAPTION_REGION_ID:
            return region
        component = str(region.get('component') or '')
        if fallback is None and component.startswith('caption'):
            fallback = region
    return fallback
