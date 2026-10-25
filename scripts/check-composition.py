#!/usr/bin/env python3
"""Pre-render composition checks (DOM determinism via Chrome + Playwright).

Runs the render-time checks for the composition step: at each scene's
start / midpoint / end it loads composition/index.html, seeks to that
second, and measures the DOM. Checks:

  - outside_content_regions : a visible content element is not fully
    contained in the layout's content regions;
  - reserved_region_intrusion : an element intrudes into a reserved
    region without belonging to that region's component;
  - text_overflow : an element with clipped/scrolled overflow has
    scroll size beyond its client size;
  - media_load_failure : an img/video failed to load;
  - fonts_not_loaded        : document.fonts has not finished loading;
  - font_size_below_min     : visible reading text below the design
    minimum font size (excludes caption text, which follows the layout
    caption spec);
  - caption_mismatch        : the on-screen caption does not match the
    subtitle unit active at that second.

Inputs:
  <composition>   composition dir, project dir containing composition/,
                  or index.html path.
  --layout        layout region definition JSON (modules/layouts/*.json):
                  regions (kind content/reserved, rect, component) and the
                  caption spec.
  --min-font-size design minimum reading-text size in px. Alternatively
                  --design-doc parses the first "不小于 <N>px" from a
                  theme doc. One of the two is required.
  --subtitle-units subtitle-units.json for the caption check (optional).
  --timeline      timeline.json; its scenes list ({scene_id, begin_s,
                  end_s}) drives scene timing. Without it, scene roots are
                  discovered from [data-scene-id] with data-scene-start /
                  data-scene-end; without either, one global scene is
                  checked.

Output convention:
  stdout: single JSON object
    success: {"success": true, "verdict": "pass"|"fail",
              "scenes_checked": [...], "findings": [...]}
      each finding: {scene_id, check, detail}
    error:   {"success": false, "error": "..."}
  stderr: human-readable progress prefixed with [check-composition]
  exit:   0 = run completed (verdict field carries pass/fail),
          1 = runtime error, 2 = invalid arguments
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TOOL_NAME = 'check-composition'

CHROME_CANDIDATES_LINUX = [
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
]
CHROME_CANDIDATES_MAC = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary',
]
CHROME_CANDIDATES_WIN = [
    os.path.expandvars(r'%ProgramFiles%\Google\Chrome\Application\chrome.exe'),
    os.path.expandvars(r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe'),
    os.path.expandvars(r'%LocalAppData%\Google\Chrome\Application\chrome.exe'),
]

DEFAULT_VIEWPORT = '1920x1080'
RECT_TOLERANCE_PX = 2.0
# Minimum overlap (px^2) before an element counts as intruding into a reserved region.
MIN_INTRUSION_AREA_PX2 = 4.0
# Floor (px^2) for the leftover area in covered_by(): below this, a rect is
# considered contained even if not exactly (antialiasing / sub-pixel edges).
COVERED_LEFTOVER_FLOOR_PX2 = 4.0
OVERFLOW_TOLERANCE_PX = 2.0

SCRIPT_DIR = Path(__file__).resolve().parent
SNAPSHOT_JS_PATH = SCRIPT_DIR / 'check-composition-snapshot.js'


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        log(f'Argument error: {message}')
        print(json.dumps({'success': False, 'error': message}, ensure_ascii=False))
        self.exit(2)


def log(message: str) -> None:
    print(f'[{TOOL_NAME}] {message}', file=sys.stderr)


def fail(message: str, exit_code: int = 1) -> None:
    log(message)
    print(json.dumps({'success': False, 'error': message}, ensure_ascii=False))
    raise SystemExit(exit_code)


def parse_viewport(value: str) -> Tuple[int, int]:
    match = re.match(r'^(\d+)x(\d+)$', value.strip())
    if not match:
        raise ValueError(f'Invalid viewport {value!r}; expected WxH, e.g. 1920x1080')
    width, height = int(match.group(1)), int(match.group(2))
    if width < 320 or height < 320:
        raise ValueError(f'Viewport is too small: {value!r}')
    return width, height


def parse_args() -> argparse.Namespace:
    parser = ArgumentParser(description='Pre-render DOM checks for a composition.')
    parser.add_argument(
        'composition',
        nargs='?',
        default='.',
        help='Composition directory, project directory containing composition/, or index.html path.',
    )
    parser.add_argument('--viewport', default=DEFAULT_VIEWPORT,
                        help=f'Viewport WxH used for measurement (default {DEFAULT_VIEWPORT}).')
    parser.add_argument('--layout', required=True,
                        help='Layout region definition JSON (modules/layouts/*.json).')
    font = parser.add_argument_group('design minimum font size (one required)')
    font.add_argument('--min-font-size', type=int, default=None,
                      help='Design minimum reading-text font size in px.')
    font.add_argument('--design-doc', default=None,
                      help='Theme doc (modules/designs/<theme>/<theme>.md); the first '
                           '"不小于 <N>px" under 字号下限 is parsed.')
    parser.add_argument('--subtitle-units', default=None,
                        help='subtitle-units.json used for the caption check (optional).')
    parser.add_argument('--timeline', default=None,
                        help='timeline.json whose scenes list drives scene timing (optional).')
    parser.add_argument('--output', default=None,
                        help='Optional path to also write the JSON report.')
    parser.add_argument('--chrome-path', default=None,
                        help='Path to Chrome executable. Auto-detected if unset.')
    args = parser.parse_args()
    if args.min_font_size is None and args.design_doc is None:
        parser.error('design minimum font size required: pass --min-font-size or --design-doc')
    if args.min_font_size is not None and args.min_font_size <= 0:
        parser.error('--min-font-size must be positive')
    return args


# --- input loading -----------------------------------------------------------------


def load_min_font_size(args: argparse.Namespace) -> int:
    if args.min_font_size is not None:
        return args.min_font_size
    text = Path(args.design_doc).read_text(encoding='utf-8')
    section = text.split('字号下限', 1)
    haystack = section[1] if len(section) > 1 else text
    match = re.search(r'不小于\s*(\d+)\s*px', haystack)
    if not match:
        raise ValueError(f'could not find a "不小于 <N>px" font size floor in {args.design_doc}')
    return int(match.group(1))


def load_layout(path: str) -> Dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('regions'), list):
        raise ValueError(f'layout file {path} has no regions list')
    return data


def load_json_object_list(path: Optional[str], key: str, *, required: bool) -> List[Dict[str, Any]]:
    """Shared load-validate shape for JSON files holding a list under ``key``.

    Returns [] when path is unset, and (unless required) when the key is
    absent or not a list — a missing optional section is not an error.
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


def load_timeline_scenes(path: Optional[str]) -> List[Dict[str, Any]]:
    scenes = []
    for scene in load_json_object_list(path, 'scenes', required=False):
        if 'scene_id' not in scene:
            continue
        scenes.append(
            {
                'scene_id': str(scene['scene_id']),
                'begin_s': float(scene['begin_s']),
                'end_s': float(scene['end_s']),
            }
        )
    return scenes


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


def find_chrome(explicit: Optional[str]) -> Optional[str]:
    if explicit:
        return explicit if Path(explicit).is_file() else None
    env_path = os.environ.get('CHROME_PATH')
    if env_path and Path(env_path).is_file():
        return env_path
    import platform

    system = platform.system()
    candidates = (
        CHROME_CANDIDATES_MAC
        if system == 'Darwin'
        else CHROME_CANDIDATES_WIN
        if system == 'Windows'
        else CHROME_CANDIDATES_LINUX
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


# --- region geometry ----------------------------------------------------------------

Rect = Dict[str, float]  # {x, y, width, height}


def region_tokens(region: Dict[str, Any]) -> List[str]:
    """Identifiers an element may match to belong to a reserved region."""
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
    """target minus cut, as a list of rects (up to 4)."""
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
    """True when rect minus the union of allowed has negligible area."""
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


# --- browser measurement ------------------------------------------------------------

def load_snapshot_js() -> str:
    """The snapshot-collection function expression evaluated in the page.

    Kept in scripts/check-composition-snapshot.js so the JavaScript is
    reviewable and lintable; must remain a single async function expression.
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


# --- analysis ------------------------------------------------------------------------


def element_owner_region(element: Dict[str, Any], reserved_tokens: Dict[str, List[str]]) -> Optional[str]:
    """Reserved region id this element belongs to, via id / data-composition-id chain."""
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
    """True when the element sits inside a [data-layout-ignore] subtree."""
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
        # 'ground' is the canvas backdrop: it covers everything and owns nothing checkable.
        self.reserved = [r for r in self.reserved if r['id'] != 'ground']
        self.reserved_tokens = {r['id']: region_tokens(r) for r in self.reserved}
        # group reserved regions by component token (e.g. caption-bar + caption-text)
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
    """Element bbox must be contained in the content regions (or its own region)."""
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
    """Only the region's own component may sit in a reserved region.

    Layout regions may overlap each other (e.g. presenter person x caption-bar),
    so a component fully inside its own reserved region is the layout's business.
    """
    owner_tokens = set(regions.reserved_tokens.get(owner, [])) if owner else set()
    owner_region = regions.reserved_region_by_id(owner) if owner else None
    if owner_region is not None and covered_by(element['rect'], [owner_region['rect']]):
        return []
    details = []
    for region in regions.reserved:
        tokens = set(regions.reserved_tokens[region['id']])
        if tokens & owner_tokens:
            continue  # same component group
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
    min_font_size: float,
) -> Optional[str]:
    """Reading text below the design minimum; caption text follows the caption spec."""
    if not element['ownText'] or not (0 < element['fontSize'] < min_font_size):
        return None
    owner_tokens = regions.reserved_tokens.get(owner, []) if owner else []
    if element['isCaption'] or 'caption' in ' '.join(owner_tokens):
        return None
    return (
        f'{element["selector"]} font size {element["fontSize"]:.0f}px is below the design '
        f'minimum {min_font_size:.0f}px'
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
    min_font_size: float,
    subtitle_units: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    scene_id = snapshot['scene_id']
    findings: List[Dict[str, str]] = []

    def add(check: str, detail: Optional[str]) -> None:
        if detail:
            findings.append({'scene_id': scene_id, 'check': check, 'detail': detail})

    elements = snapshot['elements']

    for element in elements:
        if element['tag'] in ('html', 'body'):
            continue  # document roots are containers, not content
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
        add('font_size_below_min', check_font_size(element, owner, regions, min_font_size))

    add('fonts_not_loaded', check_fonts_loaded(snapshot))
    add('caption_mismatch', check_caption(snapshot, subtitle_units))

    return findings


# --- report --------------------------------------------------------------------------


def dedup_findings(findings: List[Dict[str, str]], scene_order: List[str]) -> List[Dict[str, str]]:
    seen = set()
    unique: List[Dict[str, str]] = []
    for finding in findings:
        key = (finding['scene_id'], finding['check'], finding['detail'])
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    order = {scene_id: index for index, scene_id in enumerate(scene_order)}
    unique.sort(key=lambda f: (order.get(f['scene_id'], len(order)), f['check'], f['detail']))
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
    """Scene timing precedence:

    1. timeline.json scenes passed via --timeline;
    2. [data-scene-id] DOM roots with data-scene-start / data-scene-end;
    3. one global scene spanning the probed [data-duration] total (10s fallback).
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
    min_font_size: int,
    subtitle_units: List[Dict[str, Any]],
    viewport: Tuple[int, int],
) -> Dict[str, Any]:
    findings: List[Dict[str, str]] = []
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
            findings.extend(analyze_snapshot(snapshot, regions, min_font_size, subtitle_units))

    scene_order = [scene['scene_id'] for scene in scenes]
    findings = dedup_findings(findings, scene_order)
    return {
        'success': True,
        'verdict': 'fail' if findings else 'pass',
        'composition_dir': str(composition_dir),
        'layout': str(layout_path),
        'viewport': {'width': viewport[0], 'height': viewport[1]},
        'min_font_size': min_font_size,
        'scenes_checked': checked,
        'findings': findings,
    }


def main() -> None:
    args = parse_args()
    try:
        viewport = parse_viewport(args.viewport)
    except ValueError as exc:
        fail(str(exc), exit_code=2)  # invalid argument value
    try:
        composition_dir, index_path = resolve_composition_path(args.composition)
    except (ValueError, OSError) as exc:
        fail(str(exc), exit_code=1)
    try:
        layout = load_layout(args.layout)
        min_font_size = load_min_font_size(args)
        subtitle_units = load_subtitle_units(args.subtitle_units)
        timeline_scenes = load_timeline_scenes(args.timeline)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        fail(str(exc), exit_code=1)

    try:
        # DOM discovery and check snapshots share one browser session.
        from playwright.sync_api import sync_playwright

        executable_path = find_chrome(args.chrome_path)
        if not executable_path:
            raise RuntimeError('Chrome executable not found; set CHROME_PATH or pass --chrome-path')
        index_url = index_path.as_uri()
        log(f'Loading {index_url}')
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=executable_path,
                headless=True,
                args=['--allow-file-access-from-files'],
            )
            try:
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
            finally:
                browser.close()

        regions = RegionIndex(layout)
        report = build_report(
            composition_dir,
            args.layout,
            scenes,
            snapshots,
            regions,
            min_font_size,
            subtitle_units,
            viewport,
        )
        if args.output:
            output_path = Path(args.output).expanduser().resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            log(f'Wrote {output_path}')
        print(json.dumps(report, ensure_ascii=False))
    except Exception as exc:
        fail(str(exc), exit_code=1)


if __name__ == '__main__':
    main()
