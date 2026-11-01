#!/usr/bin/env python3
"""composition 的渲染前检查（通过 Chrome + Playwright 保证 DOM 一致性）。

为 composition 步骤跑渲染期检查：在每个 scene 的起点 / 中点 / 终点加载
composition/index.html，seek 到该秒，然后测量 DOM。检查项：

  - outside_content_regions : 某个可见内容元素没有完全落在 layout 的内容区域内；
  - reserved_region_intrusion : 某个元素侵入保留区域，却不属于该区域的组件；
  - text_overflow : 被裁剪 / 滚动的溢出使某元素的 scroll 尺寸超出 client 尺寸；
  - media_load_failure : 某个 img/video 加载失败；
  - fonts_not_loaded        : document.fonts 尚未完成加载；
  - font_size_below_min     : 可见文本小于 design 的最小字号：正文最小字号，或
    [data-text-role="ui"] 内元素（面板标题栏、按钮、小标签）的 UI 最小字号。
    字幕文本不计入；它遵循 layout 的 caption 规格；
  - caption_mismatch        : 屏幕上的字幕与该秒生效的字幕单元不一致。

输入：
  <composition>   composition 目录、包含 composition/ 的项目目录，
                  或 index.html 路径。
  --layout        layout 区域定义 JSON（modules/layouts/*.json）：regions
                  （kind 为 content/reserved、rect、component）以及 caption
                  规格。
  --min-font-size design 的最小正文字号，单位 px；UI 文本可用
                  --min-ui-font-size（默认：与正文相同）。另一种方式是
                  --design 从某个主题的 design JSON 读取 min_font_px.reading
                  与 min_font_px.ui。二者必居其一。
  --subtitle-units 用于字幕检查的 subtitle-units.json（可选）。
  --timeline      timeline.json；其 scenes 列表（{scene_id, begin_s, end_s}）
                  决定场景时间。没有它时，scene 根节点由带 data-scene-start /
                  data-scene-end 的 [data-scene-id] 发现；两者都没有时，只检查
                  一个全局场景。

输出约定：
  stdout: 单个 JSON 对象
    success: {"success": true, "verdict": "pass"|"fail",
              "scenes_checked": [...], "findings": [...],
              "sources_sha256": "..."}
      每条发现：{scene_id, check, issue, time_s, frame}
      sources_sha256: 运行时对可检查源文件（index.html、compositions/、
              assets/ 去掉 fonts）的指纹；pipeline-status 会在后续扫描中比对它，
              因此即使文件 mtime 未被保留，任何编辑也会让已保存的 pass 报告失效
    error:   {"success": false, "error": "..."}
  stderr: 带 [check-composition] 前缀的人类可读进度
  exit:   0 = 运行完成（verdict 字段给出 pass/fail），
          1 = 运行时错误，2 = 参数非法
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chrome_cdp
import cli
from composition_hash import composition_sources_fingerprint
from timeline_scenes import normalize_scenes

TOOL_NAME = 'check-composition'

RECT_TOLERANCE_PX = 2.0
# 元素算作侵入保留区域所需的最小重叠面积（px^2）。
MIN_INTRUSION_AREA_PX2 = 4.0
# covered_by() 中剩余面积的下限（px^2）：低于它，即使不完全精确重叠也算被包含
# （抗锯齿 / 亚像素边缘）。
COVERED_LEFTOVER_FLOOR_PX2 = 4.0
OVERFLOW_TOLERANCE_PX = 2.0

SCRIPT_DIR = Path(__file__).resolve().parent
SNAPSHOT_JS_PATH = SCRIPT_DIR / 'check-composition-snapshot.js'


log = cli.make_logger(TOOL_NAME)


def parse_viewport(value: str) -> Tuple[int, int]:
    match = re.match(r'^(\d+)x(\d+)$', value.strip())
    if not match:
        raise ValueError(f'Invalid viewport {value!r}; expected WxH, e.g. 1920x1080')
    width, height = int(match.group(1)), int(match.group(2))
    if width < 320 or height < 320:
        raise ValueError(f'Viewport is too small: {value!r}')
    return width, height


def parse_args() -> argparse.Namespace:
    parser = cli.JsonArgumentParser(TOOL_NAME, description='Pre-render DOM checks for a composition.')
    parser.add_argument(
        'composition',
        nargs='?',
        default='.',
        help='Composition directory, project directory containing composition/, or index.html path.',
    )
    parser.add_argument('--viewport', default=None,
                        help='Viewport WxH used for measurement (default: layout canvas).')
    parser.add_argument('--layout', required=True,
                        help='Layout region definition JSON (modules/layouts/*.json).')
    font = parser.add_argument_group('design minimum font size (one required)')
    font.add_argument('--min-font-size', type=int, default=None,
                      help='Design minimum reading-text font size in px.')
    font.add_argument('--min-ui-font-size', type=int, default=None,
                      help='Minimum for text inside [data-text-role="ui"] (default: --min-font-size).')
    font.add_argument('--design', default=None,
                      help='Theme design JSON (modules/designs/<theme>/<theme>.json); the reading-text '
                           'and UI-text minimums come from min_font_px.')
    parser.add_argument('--subtitle-units', default=None,
                        help='subtitle-units.json used for the caption check (optional).')
    parser.add_argument('--timeline', default=None,
                        help='timeline.json whose scenes list drives scene timing (optional).')
    parser.add_argument('--output', default=None,
                        help='Optional path to also write the JSON report.')
    parser.add_argument('--chrome-path', default=None,
                        help='Path to Chrome executable. Auto-detected if unset.')
    snapshots = parser.add_mutually_exclusive_group()
    snapshots.add_argument(
        '--snapshots-from',
        default=None,
        metavar='FILE.JSON',
        help='test/debug seam: analyze a recorded snapshot list; skips Chrome.',
    )
    snapshots.add_argument(
        '--dump-snapshots',
        default=None,
        metavar='FILE.JSON',
        help='Write the raw Chrome-collected snapshot list for fixtures or debugging.',
    )
    args = parser.parse_args()
    if args.min_font_size is None and args.design is None:
        parser.error('design minimum font size required: pass --min-font-size or --design')
    if args.min_font_size is not None and args.min_font_size <= 0:
        parser.error('--min-font-size must be positive')
    if args.min_ui_font_size is not None and args.min_ui_font_size <= 0:
        parser.error('--min-ui-font-size must be positive')
    return args


# --- 输入加载 ----------------------------------------------------------------


def load_font_floors(args: argparse.Namespace) -> Tuple[int, int]:
    """(正文字号下限, UI 字号下限)，单位 px。"""
    if args.min_font_size is not None:
        return args.min_font_size, args.min_ui_font_size or args.min_font_size
    design = json.loads(Path(args.design).read_text(encoding='utf-8'))
    floors = design.get('min_font_px') if isinstance(design, dict) else None
    if not isinstance(floors, dict):
        raise ValueError(f'design {args.design}: min_font_px must be an object')
    reading_min, ui_min = floors.get('reading'), floors.get('ui')
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in (reading_min, ui_min)):
        raise ValueError(f'design {args.design}: min_font_px.reading and min_font_px.ui must be positive integers')
    return reading_min, args.min_ui_font_size or ui_min


def load_layout(path: str) -> Dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('regions'), list):
        raise ValueError(f'layout file {path} has no regions list')
    return data


def layout_viewport(layout: Dict[str, Any]) -> Tuple[int, int]:
    canvas = layout.get('canvas')
    if not isinstance(canvas, dict):
        raise ValueError('layout has no canvas width / height')
    width, height = canvas.get('width'), canvas.get('height')
    if not isinstance(width, int) or not isinstance(height, int) or width < 320 or height < 320:
        raise ValueError('layout canvas width / height must be integers of at least 320px')
    return width, height


def load_snapshot_list(path: str) -> List[Dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, list) or not all(isinstance(snapshot, dict) for snapshot in data):
        raise ValueError(f'{path} must contain a JSON list of snapshot objects')
    return data


def scenes_from_snapshots(snapshots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scenes: List[Dict[str, Any]] = []
    seen = set()
    for snapshot in snapshots:
        scene_id = str(snapshot['scene_id'])
        if scene_id not in seen:
            scenes.append({'scene_id': scene_id})
            seen.add(scene_id)
    return scenes


def load_json_object_list(path: Optional[str], key: str, *, required: bool) -> List[Dict[str, Any]]:
    """对「在 ``key`` 下持有列表的 JSON 文件」共用的加载-校验形状。

    当 path 未设置时返回 []；且（除非 required）当该键不存在或不是列表时也返回
    [] —— 缺少可选段落不是错误。
    """
    if not path:
        return []
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    items = data.get(key) if isinstance(data, dict) else None
    if not isinstance(items, list):
        if required:
            raise ValueError(f'{path} has no {key} list')
        return []
    return [item for item in items if isinstance(item, dict)]


def load_subtitle_units(path: Optional[str]) -> List[Dict[str, Any]]:
    units = []
    for unit in load_json_object_list(path, 'units', required=True):
        if not isinstance(unit.get('text'), str):
            continue
        units.append(
            {
                'text': unit['text'],
                'begin_s': float(unit.get('begin_s', unit.get('begin_ms', 0) / 1000)),
                'end_s': float(unit.get('end_s', unit.get('end_ms', 0) / 1000)),
            }
        )
    units.sort(key=lambda unit: unit['begin_s'])
    return units


def resolve_composition_path(raw_path: str) -> Tuple[Path, Path]:
    path = Path(raw_path).expanduser().resolve()
    if path.is_file() and path.name.lower() == 'index.html':
        return path.parent, path
    if path.is_dir() and (path / 'index.html').is_file():
        return path, path / 'index.html'
    if path.is_dir() and (path / 'composition' / 'index.html').is_file():
        composition_dir = path / 'composition'
        return composition_dir, composition_dir / 'index.html'
    raise ValueError(f'Could not find composition/index.html from {raw_path!r}')


# --- 区域几何 ----------------------------------------------------------------

Rect = Dict[str, float]  # 矩形：{x, y, width, height}


def region_tokens(region: Dict[str, Any]) -> List[str]:
    """元素可用来匹配、从而归属某个保留区域的标识符。"""
    tokens = [str(region.get('id') or '')]
    component = str(region.get('component') or '')
    match = re.match(r'^[\w-]+', component)
    if match:
        tokens.append(match.group(0))
    return [token.lower() for token in tokens if token]


def rects_intersect(a: Rect, b: Rect) -> bool:
    return (
        a['x'] < b['x'] + b['width']
        and b['x'] < a['x'] + a['width']
        and a['y'] < b['y'] + b['height']
        and b['y'] < a['y'] + a['height']
    )


def intersection_area(a: Rect, b: Rect) -> float:
    if not rects_intersect(a, b):
        return 0.0
    width = min(a['x'] + a['width'], b['x'] + b['width']) - max(a['x'], b['x'])
    height = min(a['y'] + a['height'], b['y'] + b['height']) - max(a['y'], b['y'])
    return max(0.0, width) * max(0.0, height)


def subtract_rect(target: Rect, cut: Rect) -> List[Rect]:
    """target 减去 cut，表示为一组 rect（最多 4 个）。"""
    if not rects_intersect(target, cut):
        return [target]
    left = cut['x'] - target['x']
    right = target['x'] + target['width'] - (cut['x'] + cut['width'])
    top = cut['y'] - target['y']
    bottom = target['y'] + target['height'] - (cut['y'] + cut['height'])
    remainders: List[Rect] = []
    if left > RECT_TOLERANCE_PX:
        remainders.append({'x': target['x'], 'y': target['y'], 'width': left, 'height': target['height']})
    if right > RECT_TOLERANCE_PX:
        remainders.append(
            {'x': cut['x'] + cut['width'], 'y': target['y'], 'width': right, 'height': target['height']}
        )
    mid_x = max(cut['x'], target['x'])
    mid_w = min(cut['x'] + cut['width'], target['x'] + target['width']) - mid_x
    if top > RECT_TOLERANCE_PX:
        remainders.append({'x': mid_x, 'y': target['y'], 'width': mid_w, 'height': top})
    if bottom > RECT_TOLERANCE_PX:
        remainders.append(
            {
                'x': mid_x,
                'y': cut['y'] + cut['height'],
                'width': mid_w,
                'height': bottom,
            }
        )
    return [rect for rect in remainders if rect['width'] > 0 and rect['height'] > 0]


def covered_by(rect: Rect, allowed: List[Rect]) -> bool:
    """当 rect 减去各 allowed 的并集后面积可忽略时返回 True。"""
    remainders = [rect]
    for allowed_rect in allowed:
        next_remainders: List[Rect] = []
        for remainder in remainders:
            next_remainders.extend(subtract_rect(remainder, allowed_rect))
        remainders = next_remainders
        if not remainders:
            return True
    leftover = sum(r['width'] * r['height'] for r in remainders)
    return leftover <= max(COVERED_LEFTOVER_FLOOR_PX2, 0.005 * rect['width'] * rect['height'])


# --- 浏览器测量 --------------------------------------------------------------

def load_snapshot_js() -> str:
    """在页面中求值的快照采集函数表达式。

    放在 scripts/check-composition-snapshot.js 中，以便这份 JavaScript 可被
    审阅和 lint；它必须保持为单个 async 函数表达式。
    """
    return SNAPSHOT_JS_PATH.read_text(encoding='utf-8')


DISCOVER_SCENES_JS = r"""
() => {
  const scenes = [];
  for (const el of Array.from(document.querySelectorAll('[data-scene-id]'))) {
    const id = el.getAttribute('data-scene-id');
    const start = parseFloat(el.getAttribute('data-scene-start') || '0') || 0;
    const end = parseFloat(el.getAttribute('data-scene-end') || String(start + 1)) || start + 1;
    if (id) scenes.push({ scene_id: id, begin_s: start, end_s: end });
  }
  return scenes;
}
"""

DURATION_PROBE_JS = r"""
() => {
  let max = 0;
  for (const el of Array.from(document.querySelectorAll('[data-duration]'))) {
    const end = parseFloat(el.getAttribute('data-start') || '0') + parseFloat(el.getAttribute('data-duration') || '0');
    if (Number.isFinite(end)) max = Math.max(max, end);
  }
  return max;
}
"""


# --- 分析 --------------------------------------------------------------------


def element_owner_region(element: Dict[str, Any], reserved_tokens: Dict[str, List[str]]) -> Optional[str]:
    """该元素归属的保留区域 id，经由 id / data-composition-id 链判定。"""
    candidates = {element['id'].lower()} | {a.lower() for a in element['ancestors']}
    for region_id, tokens in reserved_tokens.items():
        if candidates & set(tokens):
            return region_id
    return None


def is_content_element(element: Dict[str, Any]) -> bool:
    if element['isSceneRoot'] or element['layoutIgnore']:
        return False
    if element['media'] or element['ownText']:
        return True
    return bool(element['surface'])


def element_in_ignored_subtree(element: Dict[str, Any], elements: List[Dict[str, Any]]) -> bool:
    """当该元素位于 [data-layout-ignore] 子树内时返回 True。"""
    by_id: Dict[str, Dict[str, Any]] = {el['id']: el for el in elements if el['id']}
    return any(
        by_id[ancestor_id]['layoutIgnore']
        for ancestor_id in element['ancestors']
        if ancestor_id in by_id
    )


def normalize_text(text: str) -> str:
    return re.sub(r'\s+', '', text)


def active_subtitle_unit(units: List[Dict[str, Any]], time_s: float) -> Optional[Dict[str, Any]]:
    for unit in units:
        if unit['begin_s'] - 0.05 <= time_s <= unit['end_s'] + 0.05:
            return unit
    return None


class RegionIndex:
    def __init__(self, layout: Dict[str, Any]):
        self.content: List[Dict[str, Any]] = []
        self.reserved: List[Dict[str, Any]] = []
        for region in layout['regions']:
            if not isinstance(region, dict) or not isinstance(region.get('rect'), dict):
                continue
            entry = {
                'id': str(region.get('id') or ''),
                'rect': {key: float(value) for key, value in region['rect'].items()},
                'component': str(region.get('component') or ''),
            }
            if region.get('kind') == 'reserved':
                self.reserved.append(entry)
            else:
                self.content.append(entry)
        # 'ground' 是画布底色：它覆盖一切，且不拥有任何可检查的东西。
        self.reserved = [r for r in self.reserved if r['id'] != 'ground']
        self.reserved_tokens = {r['id']: region_tokens(r) for r in self.reserved}
        # 按 component token 给保留区域分组（例如 caption-bar + caption-text）
        self.component_groups: Dict[str, List[str]] = {}
        for region in self.reserved:
            for token in region_tokens(region):
                self.component_groups.setdefault(token, []).append(region['id'])

    def allowed_rects_for(self, owner: Optional[str]) -> List[Rect]:
        allowed = [region['rect'] for region in self.content]
        if owner is not None:
            owner_region = next((r for r in self.reserved if r['id'] == owner), None)
            if owner_region is not None:
                allowed.append(owner_region['rect'])
        return allowed

    def reserved_region_by_id(self, region_id: str) -> Optional[Dict[str, Any]]:
        return next((r for r in self.reserved if r['id'] == region_id), None)


def check_region_containment(
    element: Dict[str, Any], owner: Optional[str], regions: RegionIndex
) -> Optional[str]:
    """元素 bbox 必须被内容区域（或它自己所属的区域）包含。"""
    if covered_by(element['rect'], regions.allowed_rects_for(owner)):
        return None
    rect = element['rect']
    return (
        f'{element["selector"]} ({element["tag"]}) at ({rect["x"]:.0f},{rect["y"]:.0f}) '
        f'{rect["width"]:.0f}x{rect["height"]:.0f} is not contained in any content region'
    )


def check_reserved_intrusion(
    element: Dict[str, Any], owner: Optional[str], regions: RegionIndex
) -> List[str]:
    """只有该区域自己的组件才能落在保留区域内。

    layout 区域之间可能互相重叠（例如 presenter 人像 x 字幕条），因此某个组件
    完全落在它自己的保留区域内，是 layout 自己的事。
    """
    owner_tokens = set(regions.reserved_tokens.get(owner, [])) if owner else set()
    owner_region = regions.reserved_region_by_id(owner) if owner else None
    if owner_region is not None and covered_by(element['rect'], [owner_region['rect']]):
        return []
    details = []
    for region in regions.reserved:
        tokens = set(regions.reserved_tokens[region['id']])
        if tokens & owner_tokens:
            continue  # 同一个组件组
        overlap = intersection_area(element['rect'], region['rect'])
        if overlap > MIN_INTRUSION_AREA_PX2:
            details.append(
                f'{element["selector"]} ({element["tag"]}) intrudes into reserved region '
                f'{region["id"]} ({overlap:.0f}px^2)'
            )
    return details


def check_text_overflow(element: Dict[str, Any]) -> Optional[str]:
    if not element['ownText'] or not any(
        style in element['overflowStyle'] for style in ('hidden', 'clip', 'scroll', 'auto')
    ):
        return None
    overflow_h = element['scrollHeight'] - element['clientHeight']
    overflow_w = element['scrollWidth'] - element['clientWidth']
    if overflow_h <= OVERFLOW_TOLERANCE_PX and overflow_w <= OVERFLOW_TOLERANCE_PX:
        return None
    return (
        f'{element["selector"]} text overflows its box '
        f'(scroll {element["scrollWidth"]}x{element["scrollHeight"]} vs '
        f'client {element["clientWidth"]}x{element["clientHeight"]})'
    )


def check_media_load(element: Dict[str, Any]) -> Optional[str]:
    media = element['media']
    if not media:
        return None
    if media['tag'] == 'img' and media['complete'] and media['naturalWidth'] == 0:
        return f'{element["selector"]} image failed to load: {media["src"]}'
    if media['tag'] == 'video' and media['src'] and (media['error'] or media['readyState'] == 0):
        return f'{element["selector"]} video failed to load: {media["src"]}'
    return None


def check_font_size(
    element: Dict[str, Any],
    owner: Optional[str],
    regions: RegionIndex,
    font_floors: Tuple[float, float],
) -> Optional[str]:
    """文本小于 design 下限（[data-text-role="ui"] 内用 UI 下限）；
    字幕文本遵循 caption 规格。"""
    is_ui = bool(element.get('isUiText'))
    minimum = font_floors[1] if is_ui else font_floors[0]
    if not element['ownText'] or not (0 < element['fontSize'] < minimum):
        return None
    owner_tokens = regions.reserved_tokens.get(owner, []) if owner else []
    if element['isCaption'] or 'caption' in ' '.join(owner_tokens):
        return None
    kind = 'UI-text' if is_ui else 'reading-text'
    return (
        f'{element["selector"]} font size {element["fontSize"]:.0f}px is below the design '
        f'{kind} minimum {minimum:.0f}px'
    )


def check_fonts_loaded(snapshot: Dict[str, Any]) -> Optional[str]:
    if snapshot['fontsStatus'] == 'loaded':
        return None
    return f'document.fonts status is {snapshot["fontsStatus"]}'


def check_caption(snapshot: Dict[str, Any], subtitle_units: List[Dict[str, Any]]) -> Optional[str]:
    unit = active_subtitle_unit(subtitle_units, snapshot['time'])
    if unit is None:
        return None
    on_screen = normalize_text(' '.join(snapshot['captionTexts']))
    expected = normalize_text(unit['text'])
    if not on_screen:
        return (
            f'no visible caption at {snapshot["time"]:.1f}s '
            f'but subtitle unit {unit["text"]!r} is active'
        )
    if on_screen != expected:
        return (
            f'on-screen caption {on_screen!r} does not match subtitle unit {expected!r} '
            f'at {snapshot["time"]:.1f}s'
        )
    return None


def analyze_snapshot(
    snapshot: Dict[str, Any],
    regions: RegionIndex,
    font_floors: Tuple[float, float],
    subtitle_units: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    scene_id = snapshot['scene_id']
    findings: List[Dict[str, Any]] = []

    def add(check: str, issue: Optional[str]) -> None:
        if issue:
            findings.append(
                {
                    'scene_id': scene_id,
                    'check': check,
                    'issue': issue,
                    'time_s': float(snapshot['time']),
                    'frame': None,
                }
            )

    elements = snapshot['elements']

    for element in elements:
        if element['tag'] in ('html', 'body'):
            continue  # document 根节点是容器，不是内容
        if not is_content_element(element):
            continue
        if element_in_ignored_subtree(element, elements):
            continue
        owner = element_owner_region(element, regions.reserved_tokens)

        add('outside_content_regions', check_region_containment(element, owner, regions))
        for detail in check_reserved_intrusion(element, owner, regions):
            add('reserved_region_intrusion', detail)
        add('text_overflow', check_text_overflow(element))
        add('media_load_failure', check_media_load(element))
        add('font_size_below_min', check_font_size(element, owner, regions, font_floors))

    add('fonts_not_loaded', check_fonts_loaded(snapshot))
    add('caption_mismatch', check_caption(snapshot, subtitle_units))

    return findings


# --- 报告 --------------------------------------------------------------------


def dedup_findings(findings: List[Dict[str, Any]], scene_order: List[str]) -> List[Dict[str, Any]]:
    seen = set()
    unique: List[Dict[str, Any]] = []
    for finding in findings:
        key = (finding['scene_id'], finding['check'], finding['issue'])
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    order = {scene_id: index for index, scene_id in enumerate(scene_order)}
    unique.sort(key=lambda f: (order.get(f['scene_id'], len(order)), f['check'], f['issue']))
    return unique


def scene_check_times(scene: Dict[str, Any]) -> List[float]:
    begin, end = scene['begin_s'], scene['end_s']
    duration = max(end - begin, 0.3)
    epsilon = min(0.1, duration / 10)
    return [
        round(begin + epsilon, 3),
        round(begin + duration / 2, 3),
        round(end - epsilon, 3),
    ]


def resolve_scenes(page: Any, timeline_scenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """场景时间优先级：

    1. 通过 --timeline 传入的 timeline.json scenes；
    2. 带 data-scene-start / data-scene-end 的 [data-scene-id] DOM 根节点；
    3. 一个全局场景，跨度取自探测到的 [data-duration] 总时长（兜底 10s）。
    """
    if timeline_scenes:
        return timeline_scenes
    dom_scenes = page.evaluate(DISCOVER_SCENES_JS)
    scenes = [
        {
            'scene_id': str(scene['scene_id']),
            'begin_s': float(scene['begin_s']),
            'end_s': float(scene['end_s']),
        }
        for scene in dom_scenes
    ]
    if scenes:
        return scenes
    total = page.evaluate(DURATION_PROBE_JS) or 10.0
    return [{'scene_id': 'global', 'begin_s': 0.0, 'end_s': float(total)}]


def build_report(
    composition_dir: Path,
    layout_path: str,
    scenes: List[Dict[str, Any]],
    snapshots: List[Dict[str, Any]],
    regions: RegionIndex,
    font_floors: Tuple[int, int],
    subtitle_units: List[Dict[str, Any]],
    viewport: Tuple[int, int],
    warnings: List[str],
    viewport_mismatch: bool,
) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    checked: List[Dict[str, Any]] = []
    snapshot_by_scene: Dict[str, List[Dict[str, Any]]] = {}
    for snapshot in snapshots:
        snapshot_by_scene.setdefault(snapshot['scene_id'], []).append(snapshot)
    for scene in scenes:
        scene_snapshots = snapshot_by_scene.get(scene['scene_id'], [])
        checked.append(
            {
                'scene_id': scene['scene_id'],
                'check_times': [snapshot['time'] for snapshot in scene_snapshots],
            }
        )
        for snapshot in scene_snapshots:
            findings.extend(analyze_snapshot(snapshot, regions, font_floors, subtitle_units))

    scene_order = [scene['scene_id'] for scene in scenes]
    findings = dedup_findings(findings, scene_order)
    return {
        'success': True,
        'verdict': 'fail' if findings else 'pass',
        'composition_dir': str(composition_dir),
        'layout': str(layout_path),
        'viewport': {'width': viewport[0], 'height': viewport[1]},
        'viewport_mismatch': viewport_mismatch,
        'min_font_size': font_floors[0],
        'min_ui_font_size': font_floors[1],
        'scenes_checked': checked,
        'findings': findings,
        'sources_sha256': composition_sources_fingerprint(composition_dir),
        'warnings': warnings,
    }


def main() -> None:
    args = parse_args()
    try:
        explicit_viewport = parse_viewport(args.viewport) if args.viewport is not None else None
    except ValueError as exc:
        cli.fail(TOOL_NAME, str(exc), exit_code=2)  # 参数值非法
    try:
        if args.snapshots_from:
            composition_dir = Path(args.composition).expanduser().resolve()
            index_path = None
        else:
            composition_dir, index_path = resolve_composition_path(args.composition)
    except (ValueError, OSError) as exc:
        cli.fail(TOOL_NAME, str(exc), exit_code=1)
    try:
        layout = load_layout(args.layout)
        canvas_viewport = layout_viewport(layout)
        viewport = explicit_viewport or canvas_viewport
        viewport_mismatch = explicit_viewport is not None and explicit_viewport != canvas_viewport
        warnings: List[str] = []
        if viewport_mismatch:
            warning = (
                f'explicit viewport {viewport[0]}x{viewport[1]} differs from layout canvas '
                f'{canvas_viewport[0]}x{canvas_viewport[1]}; using the explicit viewport'
            )
            warnings.append(warning)
            log(f'warning: {warning}')
        font_floors = load_font_floors(args)
        subtitle_units = load_subtitle_units(args.subtitle_units)
        timeline_data = json.loads(Path(args.timeline).read_text(encoding='utf-8')) if args.timeline else {}
        timeline_scenes, timeline_warnings = normalize_scenes(timeline_data)
        warnings.extend(timeline_warnings)
        for warning in timeline_warnings:
            log(f'timeline scenes: {warning}')
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        cli.fail(TOOL_NAME, str(exc), exit_code=1)

    try:
        if args.snapshots_from:
            snapshots = load_snapshot_list(args.snapshots_from)
            scenes = timeline_scenes or scenes_from_snapshots(snapshots)
        else:
            # DOM 发现与检查快照共用同一个隔离的浏览器会话。
            index_url = index_path.as_uri()
            log(f'Loading {index_url}')
            with chrome_cdp.launch_isolated(args.chrome_path) as chrome_session:
                browser = chrome_session.browser
                page = browser.new_page(viewport={'width': viewport[0], 'height': viewport[1]})
                page.goto(index_url, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(300)
                scenes = resolve_scenes(page, timeline_scenes)
                checks = [
                    {'scene_id': scene['scene_id'], 'time': time}
                    for scene in scenes
                    for time in scene_check_times(scene)
                ]
                snapshots = page.evaluate(load_snapshot_js(), {'checks': checks})
            if args.dump_snapshots:
                dump_path = Path(args.dump_snapshots).expanduser().resolve()
                dump_path.parent.mkdir(parents=True, exist_ok=True)
                dump_path.write_text(json.dumps(snapshots, ensure_ascii=False, indent=2), encoding='utf-8')
                log(f'Wrote {dump_path}')

        regions = RegionIndex(layout)
        report = build_report(
            composition_dir,
            args.layout,
            scenes,
            snapshots,
            regions,
            font_floors,
            subtitle_units,
            viewport,
            warnings,
            viewport_mismatch,
        )
        if args.output:
            output_path = Path(args.output).expanduser().resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            log(f'Wrote {output_path}')
        cli.print_json(report)
    except Exception as exc:
        cli.fail(TOOL_NAME, str(exc), exit_code=1)


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
