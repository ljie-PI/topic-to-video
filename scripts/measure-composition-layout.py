#!/usr/bin/env python3
"""Measure HyperFrames composition layout geometry.

Loads composition/index.html, seeks each scene to a peak-state time, measures DOM
bounding boxes, and reports layout findings that are hard to catch reliably from
sampled frame QA alone.

Output convention:
  stdout: single JSON object
    success: {"success": true, "verdict": "pass"|"fail", "scenes": [...],
              "findings": [...], "affected_scenes": [...]}
    error:   {"success": false, "error": "..."}
  stderr: human-readable progress prefixed with `[measure-composition-layout]`
  exit:   0 successful execution, 1 runtime error, 2 invalid arguments
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TOOL_NAME = 'measure-composition-layout'

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
FINDING_ORDER = {
    'underfilled_content_area': 1,
    'center_clustered_layout': 2,
    'oversized_gutter': 3,
    'undersized_text': 4,
    'tight_text_gap': 5,
    'underfilled_container': 6,
    'uneven_vertical_distribution': 7,
}

MAX_INTERIOR_VOID_RATIO = 0.16
MAX_EDGE_VOID_RATIO = 0.30


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
    parser = ArgumentParser(description='Measure composition DOM layout geometry.')
    parser.add_argument(
        'composition',
        nargs='?',
        default='.',
        help='Composition directory, project directory containing composition/, or index.html path.',
    )
    parser.add_argument(
        '--viewport',
        default=DEFAULT_VIEWPORT,
        help=f'Viewport WxH used for measurement (default {DEFAULT_VIEWPORT}).',
    )
    parser.add_argument(
        '--affected-scenes',
        default='',
        help='Comma-separated scene ids to measure. Default measures all scenes.',
    )
    parser.add_argument(
        '--output',
        default=None,
        help='Optional path to also write the JSON report.',
    )
    parser.add_argument(
        '--chrome-path',
        default=None,
        help='Path to Chrome executable. Auto-detected if unset.',
    )
    return parser.parse_args()


def _chrome_candidates() -> List[str]:
    import platform

    system = platform.system()
    if system == 'Darwin':
        return CHROME_CANDIDATES_MAC
    if system == 'Windows':
        return CHROME_CANDIDATES_WIN
    return CHROME_CANDIDATES_LINUX


def find_chrome(explicit: Optional[str]) -> Optional[str]:
    if explicit:
        return explicit if Path(explicit).is_file() else None
    env_path = os.environ.get('CHROME_PATH')
    if env_path and Path(env_path).is_file():
        return env_path
    for candidate in _chrome_candidates():
        if candidate and Path(candidate).is_file():
            return candidate
    return None


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


def affected_scene_set(value: str) -> Optional[List[str]]:
    scene_ids = [part.strip() for part in value.split(',') if part.strip()]
    return scene_ids or None


def content_thresholds(width: float, height: float, has_material: bool) -> Dict[str, float]:
    is_portrait = height > width
    if has_material:
        return {
            'min_width_coverage': 0.52 if is_portrait else 0.55,
            'min_height_coverage': 0.50,
            'max_horizontal_gutter': 0.28,
            'max_vertical_gutter': 0.24,
            'main_text_min': 30 if is_portrait else 28,
        }
    return {
        'min_width_coverage': 0.62 if is_portrait else 0.68,
        'min_height_coverage': 0.62 if is_portrait else 0.55,
        'max_horizontal_gutter': 0.24,
        'max_vertical_gutter': 0.22,
        'main_text_min': 38 if is_portrait else 36,
    }


def add_finding(
    findings: List[Dict[str, Any]],
    scene_id: str,
    issue: str,
    detail: str,
    metrics: Dict[str, Any],
) -> None:
    findings.append({
        'scene_id': scene_id,
        'issue': issue,
        'detail': detail,
        'metrics': metrics,
    })


def analyze_scene(scene: Dict[str, Any], viewport: Tuple[int, int]) -> List[Dict[str, Any]]:
    scene_id = scene['scene_id']
    findings: List[Dict[str, Any]] = []
    content = scene['content_area']
    union = scene.get('content_union')
    if not union:
        add_finding(
            findings,
            scene_id,
            'underfilled_content_area',
            'No visible non-subtitle content was found in the scene peak state.',
            {'content_area': content},
        )
        return findings

    cw, ch = max(content['width'], 1), max(content['height'], 1)
    has_material = bool(scene.get('has_material'))
    layout_exception = scene.get('layout_exception') or ''
    allows_whitespace = layout_exception in {'hero', 'quote', 'title-card'}
    thresholds = content_thresholds(viewport[0], viewport[1], has_material)

    width_coverage = union['width'] / cw
    height_coverage = union['height'] / ch
    area_coverage = (union['width'] * union['height']) / (cw * ch)
    left_gutter = max(union['left'] - content['left'], 0) / cw
    right_gutter = max(content['right'] - union['right'], 0) / cw
    top_gutter = max(union['top'] - content['top'], 0) / ch
    bottom_gutter = max(content['bottom'] - union['bottom'], 0) / ch
    union_center_x = (union['left'] + union['right']) / 2
    union_center_y = (union['top'] + union['bottom']) / 2
    content_center_x = (content['left'] + content['right']) / 2
    content_center_y = (content['top'] + content['bottom']) / 2
    center_offset_x = abs(union_center_x - content_center_x) / cw
    center_offset_y = abs(union_center_y - content_center_y) / ch

    coverage_metrics = {
        'width_coverage': round(width_coverage, 3),
        'height_coverage': round(height_coverage, 3),
        'area_coverage': round(area_coverage, 3),
        'min_width_coverage': thresholds['min_width_coverage'],
        'min_height_coverage': thresholds['min_height_coverage'],
    }
    if (
        not allows_whitespace
        and (
            width_coverage < thresholds['min_width_coverage']
            or height_coverage < thresholds['min_height_coverage']
        )
    ):
        add_finding(
            findings,
            scene_id,
            'underfilled_content_area',
            'Visible non-subtitle content does not occupy enough of the safe content area.',
            coverage_metrics,
        )

    if (
        not allows_whitespace
        and width_coverage < 0.55
        and height_coverage < 0.45
        and center_offset_x < 0.12
        and center_offset_y < 0.12
    ):
        add_finding(
            findings,
            scene_id,
            'center_clustered_layout',
            'Content is small and clustered near the center of the safe content area.',
            {
                **coverage_metrics,
                'center_offset_x': round(center_offset_x, 3),
                'center_offset_y': round(center_offset_y, 3),
            },
        )

    max_horizontal_gutter = max(left_gutter, right_gutter)
    max_vertical_gutter = max(top_gutter, bottom_gutter)
    if (
        not allows_whitespace
        and width_coverage < thresholds['min_width_coverage']
        and max_horizontal_gutter > thresholds['max_horizontal_gutter']
    ):
        add_finding(
            findings,
            scene_id,
            'oversized_gutter',
            'Horizontal gutter is too large for the measured content width.',
            {
                'left_gutter': round(left_gutter, 3),
                'right_gutter': round(right_gutter, 3),
                'max_allowed': thresholds['max_horizontal_gutter'],
                'width_coverage': round(width_coverage, 3),
            },
        )
    if (
        not allows_whitespace
        and height_coverage < thresholds['min_height_coverage']
        and max_vertical_gutter > thresholds['max_vertical_gutter']
    ):
        add_finding(
            findings,
            scene_id,
            'oversized_gutter',
            'Vertical gutter is too large for the measured content height.',
            {
                'top_gutter': round(top_gutter, 3),
                'bottom_gutter': round(bottom_gutter, 3),
                'max_allowed': thresholds['max_vertical_gutter'],
                'height_coverage': round(height_coverage, 3),
            },
        )

    main_text_min = thresholds['main_text_min']
    text_metrics = scene.get('text_metrics') or {}
    max_font_size = text_metrics.get('max_font_size') or 0
    min_main_font_size = text_metrics.get('min_main_font_size') or 0
    if not has_material and max_font_size and max_font_size < main_text_min:
        add_finding(
            findings,
            scene_id,
            'undersized_text',
            'No-material scene uses text that is too small for the available canvas.',
            {
                'max_font_size': round(max_font_size, 1),
                'required_main_text_min': main_text_min,
            },
        )
    elif min_main_font_size and min_main_font_size < (30 if viewport[1] > viewport[0] else 28):
        add_finding(
            findings,
            scene_id,
            'undersized_text',
            'Main information text falls below the readable body-size floor.',
            {
                'min_main_font_size': round(min_main_font_size, 1),
                'required_body_min': 30 if viewport[1] > viewport[0] else 28,
            },
        )

    min_gap = scene.get('min_positive_gap')
    gap_floor = max(min(cw, ch) * 0.018, 18)
    if min_gap is not None and min_gap < gap_floor:
        add_finding(
            findings,
            scene_id,
            'tight_text_gap',
            'Main content blocks are too close together for the measured content area.',
            {
                'min_positive_gap': round(min_gap, 1),
                'required_min_gap': round(gap_floor, 1),
            },
        )

    voids = scene.get('vertical_voids')
    if not allows_whitespace and voids:
        interior_ratio = (voids.get('interior') or 0) / ch
        edge_top_ratio = (voids.get('edge_top') or 0) / ch
        edge_bottom_ratio = (voids.get('edge_bottom') or 0) / ch
        single_sided_edge = (
            (edge_top_ratio > MAX_EDGE_VOID_RATIO and edge_bottom_ratio <= MAX_EDGE_VOID_RATIO)
            or (edge_bottom_ratio > MAX_EDGE_VOID_RATIO and edge_top_ratio <= MAX_EDGE_VOID_RATIO)
        )
        if interior_ratio > MAX_INTERIOR_VOID_RATIO or single_sided_edge:
            add_finding(
                findings,
                scene_id,
                'uneven_vertical_distribution',
                'Content leaves a large empty vertical band; vertical fill is under-used or unevenly distributed.',
                {
                    'interior_void_ratio': round(interior_ratio, 3),
                    'edge_top_ratio': round(edge_top_ratio, 3),
                    'edge_bottom_ratio': round(edge_bottom_ratio, 3),
                    'max_interior_ratio': MAX_INTERIOR_VOID_RATIO,
                    'max_edge_ratio': MAX_EDGE_VOID_RATIO,
                },
            )

    for container in scene.get('container_metrics') or []:
        if (
            not allows_whitespace
            and (
                container['width_occupancy'] < 0.60
            or container['height_occupancy'] < 0.55
            or container['area_occupancy'] < 0.35
            )
        ):
            add_finding(
                findings,
                scene_id,
                'underfilled_container',
                'Nested container has too much empty space between the outer box and inner content.',
                {
                    'selector': container.get('selector'),
                    'container': container.get('container'),
                    'inner_union': container.get('inner_union'),
                    'width_occupancy': round(container['width_occupancy'], 3),
                    'height_occupancy': round(container['height_occupancy'], 3),
                    'area_occupancy': round(container['area_occupancy'], 3),
                    'min_width_occupancy': 0.60,
                    'min_height_occupancy': 0.55,
                    'min_area_occupancy': 0.35,
                },
            )

    return findings


MEASURE_JS = r"""
async ({ sceneIds }) => {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  async function seekTo(seconds) {
    const time = Math.max(0, Number(seconds) || 0);
    const timeMs = time * 1000;
    let didSeek = false;

    if (window.__layoutQA && typeof window.__layoutQA.seek === 'function') {
      try {
        await window.__layoutQA.seek(time);
        didSeek = true;
      } catch (_) {}
    }

    const timelines = window.__timelines ? Object.values(window.__timelines).filter(Boolean) : [];
    for (const timeline of timelines) {
      try {
        if (typeof timeline.pause === 'function') timeline.pause();
        if (typeof timeline.seek === 'function') {
          timeline.seek(time, false);
          didSeek = true;
        } else if (typeof timeline.totalTime === 'function') {
          timeline.totalTime(time, false);
          didSeek = true;
        }
      } catch (_) {}
    }

    const animeInstances = Array.isArray(window.__hfAnime) ? window.__hfAnime : [];
    for (const entry of animeInstances) {
      const animation = entry && (entry.animation || entry.instance || entry);
      try {
        if (typeof animation.pause === 'function') animation.pause();
        if (typeof animation.seek === 'function') {
          animation.seek(timeMs);
          didSeek = true;
        }
      } catch (_) {}
    }

    const lottieInstances = Array.isArray(window.__hfLottie) ? window.__hfLottie : [];
    for (const entry of lottieInstances) {
      const animation = entry && (entry.animation || entry.instance || entry.lottie || entry);
      try {
        if (typeof animation.pause === 'function') animation.pause();
        if (typeof animation.stop === 'function') animation.stop();
        const duration = typeof animation.getDuration === 'function' ? animation.getDuration(false) : 0;
        const totalFrames = Number(animation.totalFrames || animation.frames || 0);
        const frame = duration && totalFrames ? Math.max(0, Math.min(totalFrames - 1, (time / duration) * totalFrames)) : timeMs;
        if (typeof animation.goToAndStop === 'function') {
          animation.goToAndStop(frame, Boolean(duration && totalFrames));
          didSeek = true;
        } else if (typeof animation.seek === 'function') {
          animation.seek(timeMs);
          didSeek = true;
        } else if (typeof animation.setCurrentRawFrameValue === 'function') {
          animation.setCurrentRawFrameValue(frame);
          didSeek = true;
        }
      } catch (_) {}
    }

    for (const media of Array.from(document.querySelectorAll('video,audio'))) {
      try {
        media.pause();
        if (Number.isFinite(media.duration)) {
          media.currentTime = Math.max(0, Math.min(time, media.duration || time));
        }
        didSeek = true;
      } catch (_) {}
    }
    await sleep(didSeek ? 80 : 120);
  }

  function rectObject(rect) {
    return {
      left: rect.left,
      top: rect.top,
      right: rect.right,
      bottom: rect.bottom,
      width: rect.width,
      height: rect.height,
      area: rect.width * rect.height,
    };
  }

  function hasBox(rect) {
    return rect && rect.width > 3 && rect.height > 3;
  }

  function labelOf(el) {
    return `${el.tagName || ''} ${el.id || ''} ${typeof el.className === 'string' ? el.className : ''} ${Object.keys(el.dataset || {}).join(' ')}`.toLowerCase();
  }

  function isSubtitle(el) {
    const label = labelOf(el);
    return label.includes('subtitle') || label.includes('caption') || label.includes('closed-caption') || label.includes('subtitles');
  }

  function visible(el, boundary = null) {
    let current = el;
    while (current && current.nodeType === Node.ELEMENT_NODE) {
      const style = getComputedStyle(current);
      if (style.display === 'none' || ['hidden', 'collapse'].includes(style.visibility) || Number(style.opacity || 1) < 0.03) return false;
      if (current === boundary) break;
      current = current.parentElement;
    }
    const rect = el.getBoundingClientRect();
    return hasBox(rect);
  }

  function hasOwnText(el) {
    return Array.from(el.childNodes).some((node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim().length > 0);
  }

  function textContent(el) {
    return (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function isMedia(el) {
    return ['IMG', 'VIDEO', 'SVG', 'CANVAS', 'PICTURE'].includes(el.tagName);
  }

  function hasVisibleSurface(el) {
    const style = getComputedStyle(el);
    return (
      style.backgroundImage !== 'none' ||
      (style.backgroundColor && !['rgba(0, 0, 0, 0)', 'transparent'].includes(style.backgroundColor)) ||
      parseFloat(style.borderTopWidth || '0') > 0 ||
      parseFloat(style.borderRightWidth || '0') > 0 ||
      parseFloat(style.borderBottomWidth || '0') > 0 ||
      parseFloat(style.borderLeftWidth || '0') > 0
    );
  }

  function hasMaterialMarker(el) {
    const label = labelOf(el);
    return Boolean(
      el.dataset.materialRef ||
      el.dataset.materialId ||
      el.getAttribute('data-material-ref') ||
      el.getAttribute('data-material-id') ||
      label.includes('material') ||
      label.includes('media') ||
      label.includes('asset') ||
      label.includes('figure') ||
      label.includes('screenshot')
    );
  }

  function hasMaterialBackgroundImage(el) {
    return getComputedStyle(el).backgroundImage.includes('url(') && hasMaterialMarker(el);
  }

  function layoutException(sceneRoot) {
    const raw = sceneRoot.dataset.layoutException || sceneRoot.dataset.qaLayoutException || sceneRoot.dataset.geometryException || '';
    const normalized = raw.trim().toLowerCase().replace(/_/g, '-');
    return ['hero', 'quote', 'title-card'].includes(normalized) ? normalized : '';
  }

  function isContentElement(el, sceneRoot) {
    if (el === sceneRoot || isSubtitle(el) || !visible(el, sceneRoot)) return false;
    const text = textContent(el);
    if (isMedia(el)) return true;
    if (hasMaterialBackgroundImage(el)) return true;
    if (hasOwnText(el) && text.length > 0) return true;
    if (text.length > 0 && hasVisibleSurface(el)) return true;
    return false;
  }

  function leafContentElements(root, sceneRoot, pierceBackgroundImage = false) {
    return Array.from(root.querySelectorAll('*')).filter((el) => {
      if (!isContentElement(el, sceneRoot)) return false;
      const hasContentDescendant = Array.from(el.querySelectorAll('*')).some((child) => isContentElement(child, sceneRoot));
      if (isMedia(el) || hasOwnText(el)) return true;
      if (hasMaterialBackgroundImage(el)) return !pierceBackgroundImage || !hasContentDescendant;
      return !hasContentDescendant;
    });
  }

  function unionRect(rects) {
    if (!rects.length) return null;
    const left = Math.min(...rects.map((r) => r.left));
    const top = Math.min(...rects.map((r) => r.top));
    const right = Math.max(...rects.map((r) => r.right));
    const bottom = Math.max(...rects.map((r) => r.bottom));
    return { left, top, right, bottom, width: right - left, height: bottom - top, area: (right - left) * (bottom - top) };
  }

  function contains(a, b) {
    return a.left <= b.left + 1 && a.top <= b.top + 1 && a.right >= b.right - 1 && a.bottom >= b.bottom - 1;
  }

  function majorRects(rects) {
    const sorted = rects.slice().sort((a, b) => b.area - a.area);
    const keep = [];
    for (const rect of sorted) {
      if (rect.area < 500) continue;
      if (keep.some((larger) => contains(larger, rect) && larger.area > rect.area * 1.25)) continue;
      keep.push(rect);
    }
    return keep;
  }

  function minPositiveGap(rects) {
    const blocks = majorRects(rects);
    if (blocks.length < 2) return null;
    let best = Infinity;
    for (let i = 0; i < blocks.length; i += 1) {
      for (let j = i + 1; j < blocks.length; j += 1) {
        const a = blocks[i];
        const b = blocks[j];
        const horizontalGap = Math.max(0, Math.max(a.left, b.left) - Math.min(a.right, b.right));
        const verticalGap = Math.max(0, Math.max(a.top, b.top) - Math.min(a.bottom, b.bottom));
        const overlapsX = a.left < b.right && b.left < a.right;
        const overlapsY = a.top < b.bottom && b.top < a.bottom;
        if (overlapsY && horizontalGap > 0) best = Math.min(best, horizontalGap);
        if (overlapsX && verticalGap > 0) best = Math.min(best, verticalGap);
      }
    }
    return Number.isFinite(best) ? best : null;
  }

  function verticalVoids(rects, contentArea) {
    const top = contentArea.top;
    const bottom = contentArea.bottom;
    const intervals = rects
      .map((r) => [Math.max(r.top, top), Math.min(r.bottom, bottom)])
      .filter((iv) => iv[1] - iv[0] > 1)
      .sort((p, q) => p[0] - q[0]);
    if (!intervals.length) return null;
    const merged = [intervals[0].slice()];
    for (let i = 1; i < intervals.length; i += 1) {
      const last = merged[merged.length - 1];
      if (intervals[i][0] <= last[1]) {
        last[1] = Math.max(last[1], intervals[i][1]);
      } else {
        merged.push(intervals[i].slice());
      }
    }
    let interior = 0;
    for (let i = 1; i < merged.length; i += 1) {
      interior = Math.max(interior, merged[i][0] - merged[i - 1][1]);
    }
    return {
      interior: Math.max(interior, 0),
      edge_top: Math.max(merged[0][0] - top, 0),
      edge_bottom: Math.max(bottom - merged[merged.length - 1][1], 0),
    };
  }

  function selectorFor(el) {
    if (el.id) return `#${el.id}`;
    const classes = typeof el.className === 'string'
      ? el.className.trim().split(/\s+/).filter(Boolean).slice(0, 3)
      : [];
    if (classes.length) return `${el.tagName.toLowerCase()}.${classes.join('.')}`;
    return el.tagName.toLowerCase();
  }

  function containerMetrics(sceneRoot) {
    const candidates = Array.from(sceneRoot.querySelectorAll('*')).filter((el) => {
      if (isSubtitle(el) || !visible(el, sceneRoot) || isMedia(el)) return false;
      const rect = el.getBoundingClientRect();
      if (rect.width < 180 || rect.height < 120 || rect.width * rect.height < 30000) return false;
      return leafContentElements(el, sceneRoot, true).length > 0;
    });
    return candidates.map((el) => {
      const container = rectObject(el.getBoundingClientRect());
      if (hasMaterialBackgroundImage(el)) {
        return {
          selector: selectorFor(el),
          container,
          inner_union: container,
          width_occupancy: 1,
          height_occupancy: 1,
          area_occupancy: 1,
        };
      }
      const childRects = leafContentElements(el, sceneRoot, true)
        .map((child) => rectObject(child.getBoundingClientRect()))
        .filter((rect) => hasBox(rect) && rect.area < container.area * 0.98);
      const innerUnion = unionRect(childRects);
      if (!innerUnion) return null;
      const majorChildRects = majorRects(childRects);
      const childArea = majorChildRects.reduce((sum, rect) => sum + Math.min(rect.area, container.area), 0);
      return {
        selector: selectorFor(el),
        container,
        inner_union: innerUnion,
        width_occupancy: innerUnion.width / Math.max(container.width, 1),
        height_occupancy: innerUnion.height / Math.max(container.height, 1),
        area_occupancy: Math.min(childArea / Math.max(container.area, 1), 1),
      };
    }).filter(Boolean);
  }

  function contentAreaFor(sceneRoot, subtitleCandidates) {
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const sceneStyle = getComputedStyle(sceneRoot);
    const paddingLeft = parseFloat(sceneStyle.paddingLeft || '0') || 0;
    const paddingRight = parseFloat(sceneStyle.paddingRight || '0') || 0;
    const paddingTop = parseFloat(sceneStyle.paddingTop || '0') || 0;
    const paddingBottom = parseFloat(sceneStyle.paddingBottom || '0') || 0;
    const subtitleRects = subtitleCandidates
      .filter((el) => visible(el))
      .map((el) => rectObject(el.getBoundingClientRect()))
      .filter((rect) => rect.top > viewportHeight * 0.45);
    let subtitleSafeHeight;
    if (subtitleRects.length) {
      const safeTop = Math.min(...subtitleRects.map((rect) => rect.top));
      subtitleSafeHeight = Math.max(0, viewportHeight - safeTop);
    } else {
      subtitleSafeHeight = viewportHeight > viewportWidth ? viewportHeight * 0.14 : viewportHeight * 0.12;
    }
    const left = paddingLeft;
    const top = paddingTop;
    const right = viewportWidth - paddingRight;
    const bottom = viewportHeight - subtitleSafeHeight - paddingBottom;
    return { left, top, right, bottom, width: right - left, height: bottom - top, subtitleSafeHeight };
  }

  function textMetrics(elements) {
    const metrics = [];
    for (const el of elements) {
      if (!hasOwnText(el)) continue;
      const text = textContent(el);
      if (!text || text.length < 2) continue;
      const style = getComputedStyle(el);
      const fontSize = parseFloat(style.fontSize || '0') || 0;
      const lineHeightRaw = parseFloat(style.lineHeight || '0') || fontSize * 1.2;
      const rect = el.getBoundingClientRect();
      metrics.push({
        textLength: text.length,
        fontSize,
        lineHeight: lineHeightRaw,
        lineCount: Math.max(1, Math.round(rect.height / Math.max(lineHeightRaw, 1))),
        area: rect.width * rect.height,
      });
    }
    const main = metrics.filter((m) => m.textLength >= 4 && m.area >= 300);
    return {
      count: metrics.length,
      max_font_size: metrics.length ? Math.max(...metrics.map((m) => m.fontSize)) : 0,
      min_main_font_size: main.length ? Math.min(...main.map((m) => m.fontSize)) : 0,
    };
  }

  async function measureSceneAt(sceneRoot, sceneId, start, end, peakTime, subtitleCandidates) {
    await seekTo(peakTime);

    const contentElements = Array.from(sceneRoot.querySelectorAll('*')).filter((el) => isContentElement(el, sceneRoot));
    const rects = contentElements.map((el) => rectObject(el.getBoundingClientRect())).filter(hasBox);
    const contentUnion = unionRect(rects);
    const contentArea = contentAreaFor(sceneRoot, subtitleCandidates);
    const leafRects = leafContentElements(sceneRoot, sceneRoot, false)
      .map((el) => rectObject(el.getBoundingClientRect()))
      .filter(hasBox);
    const hasMaterial = contentElements.some((el) => ['IMG', 'VIDEO', 'PICTURE', 'CANVAS'].includes(el.tagName) || hasMaterialBackgroundImage(el));
    return {
      scene_id: sceneId,
      start,
      end,
      peak_time: peakTime,
      layout_exception: layoutException(sceneRoot),
      has_material: hasMaterial,
      content_area: contentArea,
      content_union: contentUnion,
      content_element_count: contentElements.length,
      text_metrics: textMetrics(contentElements),
      min_positive_gap: minPositiveGap(rects),
      vertical_voids: verticalVoids(leafRects, contentArea),
      container_metrics: containerMetrics(sceneRoot),
    };
  }

  function scoreSceneMeasure(scene) {
    const unionArea = scene.content_union ? scene.content_union.area : 0;
    const textCount = scene.text_metrics ? scene.text_metrics.count : 0;
    return unionArea + scene.content_element_count * 1000 + textCount * 500;
  }

  function explicitPeakTimes(sceneRoot, start, end) {
    const raw = sceneRoot.dataset.qaPeakTimes || sceneRoot.dataset.peakTimes || sceneRoot.dataset.qaPeakTime || sceneRoot.dataset.peakTime || '';
    return raw.split(',')
      .map((part) => parseFloat(part.trim()))
      .filter((time) => Number.isFinite(time) && time >= start && time <= end);
  }

  const sceneRoots = Array.from(document.querySelectorAll('[data-scene-id]'));
  const wanted = sceneIds && sceneIds.length ? new Set(sceneIds) : null;
  const subtitleCandidates = Array.from(document.querySelectorAll('*')).filter((el) => isSubtitle(el));
  const scenes = [];

  for (const sceneRoot of sceneRoots) {
    const sceneId = sceneRoot.dataset.sceneId || sceneRoot.getAttribute('data-scene-id') || '';
    if (!sceneId || (wanted && !wanted.has(sceneId))) continue;
    const start = parseFloat(sceneRoot.dataset.sceneStart || sceneRoot.getAttribute('data-scene-start') || '0') || 0;
    const end = parseFloat(sceneRoot.dataset.sceneEnd || sceneRoot.getAttribute('data-scene-end') || String(start + 1)) || start + 1;
    const duration = Math.max(end - start, 0.2);
    const candidateTimes = explicitPeakTimes(sceneRoot, start, end).concat([0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
      .map((fraction) => start + duration * fraction)
      .map((time) => Math.max(start + 0.1, Math.min(time, end - 0.1))));
    const measurements = [];
    for (const peakTime of Array.from(new Set(candidateTimes.map((time) => Number(time.toFixed(3)))))) {
      measurements.push(await measureSceneAt(sceneRoot, sceneId, start, end, peakTime, subtitleCandidates));
    }
    measurements.sort((a, b) => scoreSceneMeasure(b) - scoreSceneMeasure(a));
    scenes.push(measurements[0]);
  }

  return {
    viewport: { width: window.innerWidth, height: window.innerHeight },
    scene_count: scenes.length,
    scenes,
  };
}
"""


def measure_with_playwright(
    composition_dir: Path,
    index_path: Path,
    viewport: Tuple[int, int],
    chrome_path: Optional[str],
    scene_ids: Optional[List[str]],
) -> Dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - depends on runtime env
        raise RuntimeError('Python Playwright package is not installed; run: pip install playwright. The script launches system Chrome; do not run playwright install chromium.') from exc

    executable_path = find_chrome(chrome_path)
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
            measured = page.evaluate(MEASURE_JS, {'sceneIds': scene_ids})
        finally:
            browser.close()

    measured['composition_dir'] = str(composition_dir)
    measured['index_path'] = str(index_path)
    return measured


def build_report(measured: Dict[str, Any], viewport: Tuple[int, int], requested_scene_ids: Optional[List[str]]) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    measured_scene_ids = {scene.get('scene_id') for scene in measured.get('scenes', [])}
    missing_scene_ids = [scene_id for scene_id in requested_scene_ids or [] if scene_id not in measured_scene_ids]
    if not measured.get('scenes'):
        add_finding(
            findings,
            'global',
            'scene_measurement_failed',
            'No scene roots were measured from composition/index.html.',
            {'requested_scene_ids': requested_scene_ids or []},
        )
    if missing_scene_ids:
        add_finding(
            findings,
            'global',
            'scene_measurement_failed',
            'Requested affected scenes were not found in composition/index.html.',
            {'missing_scene_ids': missing_scene_ids},
        )
    for scene in measured.get('scenes', []):
        findings.extend(analyze_scene(scene, viewport))

    findings.sort(key=lambda item: (item.get('scene_id', ''), FINDING_ORDER.get(item.get('issue', ''), 99)))
    scene_order = [scene.get('scene_id') for scene in measured.get('scenes', []) if scene.get('scene_id')]
    affected_seen = set()
    affected: List[str] = []
    for scene_id in scene_order:
        if scene_id != 'global' and any(finding.get('scene_id') == scene_id for finding in findings):
            affected.append(scene_id)
            affected_seen.add(scene_id)
    for finding in findings:
        scene_id = finding.get('scene_id')
        if scene_id and scene_id != 'global' and scene_id not in affected_seen:
            affected.append(scene_id)
            affected_seen.add(scene_id)
    if any(finding.get('scene_id') == 'global' for finding in findings):
        affected.append('global')
    return {
        'success': True,
        'verdict': 'fail' if findings else 'pass',
        'composition_dir': measured.get('composition_dir'),
        'index_path': measured.get('index_path'),
        'viewport': {'width': viewport[0], 'height': viewport[1]},
        'scene_count': measured.get('scene_count', 0),
        'scenes': measured.get('scenes', []),
        'findings': findings,
        'affected_scenes': affected,
    }


def main() -> None:
    args = parse_args()
    try:
        viewport = parse_viewport(args.viewport)
        composition_dir, index_path = resolve_composition_path(args.composition)
    except ValueError as exc:
        fail(str(exc), exit_code=2)

    try:
        scene_ids = affected_scene_set(args.affected_scenes)
        measured = measure_with_playwright(
            composition_dir=composition_dir,
            index_path=index_path,
            viewport=viewport,
            chrome_path=args.chrome_path,
            scene_ids=scene_ids,
        )
        report = build_report(measured, viewport, scene_ids)
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
