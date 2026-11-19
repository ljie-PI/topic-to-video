#!/usr/bin/env python3
"""封面确定性渲染、DOM 机器自检与 400px 缩略图生成（Phase 11）。

对封面目录下的每套目标尺寸（默认 1080x1440、1440x1080、1920x1080）：
  1. 静态检查 HTML/CSS：禁止 vw/vh 视口单位，禁止未限定类名/ID/属性的裸 img 选择器；
  2. 在隔离的系统 Chrome 中以 deviceScaleFactor=2 渲染并截取 2W×2H (@2x) 母版，
     用 Pillow LANCZOS 下采样生成 W×H (1x) 成品；
  3. 在同一页面上下文执行机器自检：
     - 文档无滚动溢出（scrollWidth/scrollHeight 精确等于画布 W×H）；
     - 字体与图片全部加载完成；
     - 禁止顶部信息条 .bar；
     - 视觉块 [data-block] 数量 1..5；
     - 重要数字 [data-num] 数量 1..3（仅 --allow-zero-num 时允许 0..3）；
     - 主标题 h1 固定 2 行、声明 white-space: nowrap、按行非空白字符数 <= 10；
     - 单一主体区 [data-subject] 占画布面积 45%–65%（1080x1440 建议 55%–65%）；
     - 招手主持人 .presenter 必须存在、使用 presenter-wave.png，且严格落在各尺寸固定像素槽位；
     - 横版左右分栏时标题行与主体图区水平间距 >= 40px；
     - .presenter、.stats、h1 互不重叠碰撞；
     - 16:9（如 1920x1080）右下角预留 >=190×80px 时长角标避让区；
     - 主标题文字与所压背景明度差 >= 60%；
  4. 生成 400px 宽缩略图 cover/qa/thumb_{W}x{H}_400w.png 供视觉验收。

输出约定：
  stdout: 单个 JSON 对象
    success: {"success": true, "verdict": "pass"|"fail", "cover_dir": "...",
              "sizes": [...], "covers": [...], "findings": [...], "warnings": [...]}
    error:   {"success": false, "error": "..."}
  stderr: 带 [render-cover] 前缀的人类可读进度
  退出码：0 = 运行完成（verdict 给出 pass/fail），1 = 运行时错误，2 = 参数非法
"""
from __future__ import annotations

import argparse
import json
import math
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import chrome_cdp
import cli
import video_contract

TOOL_NAME = 'render-cover'

THUMB_WIDTH_PX = 400
MIN_SUBJECT_RATIO = 0.44
MAX_SUBJECT_RATIO = 0.66
PORTRAIT_3X4_TARGET_MIN_RATIO = 0.55
MIN_TITLE_CONTRAST_DIFF = 0.59   # 60% 明度差（留 1% 8-bit RGB 量化容差）
LANDSCAPE_GAP_PX = 40.0
GAP_TOLERANCE_PX = 1.0
SLOT_TOLERANCE_PX = 2.0
OVERLAP_AREA_FLOOR_PX2 = 4.0
MAX_BLOCKS = 5
MIN_NUMS = 1
MAX_NUMS = 3
MAX_LINE_CHARS = 10
TARGET_LINE_CHARS = 8

VIEWPORT_UNIT_RE = re.compile(
    r'(?<![A-Za-z_-])\d+(?:\.\d+)?(?:[sld]?v[wh]|vmin|vmax)\b',
    re.IGNORECASE,
)
SIZE_RE = re.compile(r'^(\d+)x(\d+)$')

log = cli.make_logger(TOOL_NAME)


def parse_size(raw: str) -> tuple[int, int]:
    match = SIZE_RE.fullmatch(raw.strip())
    if not match:
        raise ValueError(f'Invalid cover size {raw!r}; expected WxH such as 1080x1440')
    width, height = int(match.group(1)), int(match.group(2))
    if width < 320 or height < 320:
        raise ValueError(f'Cover size is too small: {raw!r} (minimum 320x320)')
    return width, height


def parse_args() -> argparse.Namespace:
    parser = cli.JsonArgumentParser(
        TOOL_NAME,
        description='Render HTML covers at @2x/1x, run DOM self-checks, and generate 400px thumbnails.',
    )
    parser.add_argument(
        'cover_dir',
        nargs='?',
        default='cover',
        help='Cover directory (e.g. <workspace>/cover) or workspace directory containing cover/.',
    )
    parser.add_argument(
        '--sizes',
        nargs='+',
        default=list(video_contract.COVER_DEFAULT_SIZES),
        help='Target WxH cover sizes (default: 1080x1440 1440x1080 1920x1080).',
    )
    parser.add_argument(
        '--output',
        default=None,
        help='Optional path to write the JSON report (e.g. <workspace>/cover/cover-report.json).',
    )
    parser.add_argument(
        '--chrome-path',
        default=None,
        help='Path to Chrome executable. Auto-detected if unset.',
    )
    parser.add_argument(
        '--allow-zero-num',
        action='store_true',
        help='Allow 0 [data-num] elements when the research brief has no verified numeric facts.',
    )
    args = parser.parse_args()
    try:
        parsed_sizes = []
        seen_sizes: set[str] = set()
        for item in args.sizes:
            w, h = parse_size(item)
            canonical = f'{w}x{h}'
            if canonical not in seen_sizes:
                seen_sizes.add(canonical)
                parsed_sizes.append((canonical, w, h))
        args.parsed_sizes = parsed_sizes
    except ValueError as exc:
        parser.error(str(exc))
    return args


def resolve_cover_dir(raw_path: str) -> Path:
    path = Path(raw_path).expanduser().resolve()
    if path.is_dir():
        if (path / 'cover').is_dir() and not any(path.glob('cover_*.html')):
            return (path / 'cover').resolve()
        return path
    raise FileNotFoundError(f'Cover directory not found: {raw_path!r}')


# --- 静态 HTML / CSS 检查 ----------------------------------------------------


class _StyleCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_style = False
        self._buf: list[str] = []
        self.style_blocks: list[str] = []
        self.inline_styles: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == 'style':
            self._in_style = True
            self._buf = []
        for key, value in attrs:
            if key.lower() == 'style' and value:
                self.inline_styles.append(value)

    def handle_data(self, data: str) -> None:
        if self._in_style:
            self._buf.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == 'style' and self._in_style:
            self._in_style = False
            self.style_blocks.append(''.join(self._buf))
            self._buf = []


def _strip_css_comments_and_urls(css: str) -> str:
    without_comments = re.sub(r'/\*.*?\*/', ' ', css, flags=re.DOTALL)
    without_urls = re.sub(r'url\([^)]*\)', 'url()', without_comments, flags=re.IGNORECASE)
    without_strings = re.sub(r'"[^"\n]*"|\'[^\'\n]*\'', '""', without_urls)
    return without_strings


def _iter_css_rule_selectors(css: str) -> list[str]:
    cleaned = _strip_css_comments_and_urls(css)
    selectors: list[str] = []
    i = 0
    n = len(cleaned)
    skip_block_depth: int | None = None
    depth = 0
    token_start = 0

    while i < n:
        ch = cleaned[i]
        if ch == '{':
            header = cleaned[token_start:i].strip()
            if skip_block_depth is None:
                if header.lower().startswith(('@keyframes', '@-webkit-keyframes', '@font-face')):
                    skip_block_depth = depth
                elif not header.startswith('@') and header:
                    for sel in header.split(','):
                        s = sel.strip()
                        if s:
                            selectors.append(s)
            depth += 1
            token_start = i + 1
        elif ch == '}':
            depth = max(0, depth - 1)
            if skip_block_depth is not None and depth <= skip_block_depth:
                skip_block_depth = None
            token_start = i + 1
        elif ch == ';' and skip_block_depth is None:
            token_start = i + 1
        i += 1
    return selectors


def _is_bare_img_selector(selector: str) -> bool:
    parts = re.split(r'[\s>+~]+', selector.strip())
    if not parts:
        return False
    target = parts[-1]
    return bool(re.fullmatch(r'img(?::[\w-]+(?:\([^)]*\))?)*', target, flags=re.IGNORECASE))


def check_html_css_source(html_text: str) -> list[tuple[str, str]]:
    parser = _StyleCollector()
    parser.feed(html_text)
    issues: list[tuple[str, str]] = []

    for block in [*parser.style_blocks, *parser.inline_styles]:
        scrubbed = _strip_css_comments_and_urls(block)
        match = VIEWPORT_UNIT_RE.search(scrubbed)
        if match:
            issues.append((
                'vw_vh_forbidden',
                f'CSS uses forbidden viewport unit {match.group(0)!r}; lock fixed px dimensions per size HTML',
            ))
            break

    for block in parser.style_blocks:
        for selector in _iter_css_rule_selectors(block):
            if _is_bare_img_selector(selector):
                issues.append((
                    'bare_img_selector',
                    f'unqualified img selector {selector!r} stretches other image layers; '
                    'use explicit classes such as .hero img.bg and .presenter img.presenter-art',
                ))
                break
        if any(check == 'bare_img_selector' for check, _ in issues):
            break

    return issues


# --- 浏览器 DOM 快照测量 -----------------------------------------------------


MEASURE_COVER_JS = r"""
() => {
  const rectOf = (el) => {
    if (!el) return null;
    const b = el.getBoundingClientRect();
    return {
      x: b.x, y: b.y, width: b.width, height: b.height,
      left: b.left, top: b.top, right: b.right, bottom: b.bottom,
    };
  };
  const visible = (el) => {
    if (!el) return false;
    const cs = window.getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity || '1') <= 0.01) {
      return false;
    }
    const b = el.getBoundingClientRect();
    return b.width > 0.5 && b.height > 0.5;
  };
  const parseRgba = (val) => {
    if (!val) return null;
    const m = val.match(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,/\s]+([\d.]+))?\s*\)/i);
    if (!m) return null;
    return [Number(m[1]), Number(m[2]), Number(m[3]), m[4] === undefined ? 1 : Number(m[4])];
  };

  const h1 = document.querySelector('h1');
  let lines = [];
  let h1PrimaryColor = null;
  let h1Colors = [];
  let h1ChipRects = [];

  if (h1 && visible(h1)) {
    const h1Style = window.getComputedStyle(h1);
    const baseRgba = parseRgba(h1Style.color);
    if (baseRgba) {
      h1PrimaryColor = baseRgba.slice(0, 3);
      h1Colors.push(h1PrimaryColor);
    }

    const directText = [...h1.childNodes]
      .filter((n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim().length > 0);
    const lineEls = h1.querySelectorAll('[data-line]');
    const explicitEls = lineEls.length > 0
      ? [...lineEls]
      : (directText.length === 0 && h1.children.length > 0 ? [...h1.children] : []);
    const explicitSet = new Set(explicitEls);

    for (const sub of h1.querySelectorAll('*')) {
      if (!visible(sub)) continue;
      const subCs = window.getComputedStyle(sub);
      const subRgba = parseRgba(subCs.color);
      if (subRgba) h1Colors.push(subRgba.slice(0, 3));
      const bgRgba = parseRgba(subCs.backgroundColor);
      if (!explicitSet.has(sub) && bgRgba && bgRgba[3] > 0.12) {
        h1ChipRects.push(rectOf(sub));
      }
    }

    if (explicitEls.length > 0) {
      lines = explicitEls.filter(visible).map((el) => {
        const cs = window.getComputedStyle(el);
        const r = rectOf(el);
        const range = document.createRange();
        range.selectNodeContents(el);
        const clientRects = [...range.getClientRects()].filter((cr) => cr.width > 0.5 && cr.height > 0.5);
        const rowTops = [];
        for (const cr of clientRects) {
          const midY = (cr.top + cr.bottom) / 2;
          if (!rowTops.some((y) => Math.abs(y - midY) <= Math.max(6, cr.height * 0.35))) {
            rowTops.push(midY);
          }
        }
        const textLeft = clientRects.length ? Math.min(...clientRects.map((c) => c.left)) : r.left;
        const textRight = clientRects.length ? Math.max(...clientRects.map((c) => c.right)) : r.right;
        const lineColor = parseRgba(cs.color);
        return {
          text: (el.textContent || '').trim(),
          left: Math.round(textLeft),
          right: Math.round(textRight),
          top: Math.round(r.top),
          bottom: Math.round(r.bottom),
          color: lineColor ? lineColor.slice(0, 3) : h1PrimaryColor,
          nowrap: cs.whiteSpace === 'nowrap' || h1Style.whiteSpace === 'nowrap',
          wrappedRows: Math.max(1, rowTops.length),
        };
      });
    } else {
      const range = document.createRange();
      range.selectNodeContents(h1);
      const clientRects = [...range.getClientRects()].filter((cr) => cr.width > 0.5 && cr.height > 0.5);
      const grouped = [];
      for (const cr of clientRects) {
        const midY = (cr.top + cr.bottom) / 2;
        const row = grouped.find((g) => Math.abs(g.midY - midY) <= Math.max(6, cr.height * 0.35));
        if (row) {
          row.left = Math.min(row.left, cr.left);
          row.right = Math.max(row.right, cr.right);
          row.top = Math.min(row.top, cr.top);
          row.bottom = Math.max(row.bottom, cr.bottom);
        } else {
          grouped.push({ midY, left: cr.left, right: cr.right, top: cr.top, bottom: cr.bottom });
        }
      }
      const rawLines = (h1.innerText || h1.textContent || '')
        .split(/\r?\n/)
        .map((s) => s.trim())
        .filter(Boolean);
      lines = grouped.map((g, idx) => ({
        text: rawLines[idx] || '',
        left: Math.round(g.left),
        right: Math.round(g.right),
        top: Math.round(g.top),
        bottom: Math.round(g.bottom),
        color: h1PrimaryColor,
        nowrap: h1Style.whiteSpace === 'nowrap' || h1Style.whiteSpace === 'pre',
        wrappedRows: 1,
      }));
    }
  }

  const brokenImages = [...document.querySelectorAll('img')]
    .filter(visible)
    .filter((img) => !img.complete || img.naturalWidth === 0)
    .map((img) => img.getAttribute('src') || '<inline-img>');

  const barEl = document.querySelector('.bar, [data-bar]');
  const subjectEl = document.querySelector('[data-subject]') || document.querySelector('.subject');
  const presenterEl = document.querySelector('.presenter');
  const presenterImg = presenterEl ? presenterEl.querySelector('img') : null;
  const statsEl = document.querySelector('.stats');
  const ctaEl = document.querySelector('.cta, [data-cta]');
  const numEls = [...document.querySelectorAll('[data-num]')].filter(visible);
  const blockEls = [...document.querySelectorAll('[data-block]')].filter(visible);

  return {
    doc: [document.documentElement.scrollWidth, document.documentElement.scrollHeight],
    fontsStatus: document.fonts ? document.fonts.status : 'loaded',
    brokenImages,
    hasTopBar: Boolean(barEl && visible(barEl)),
    h1: h1 && visible(h1) ? rectOf(h1) : null,
    h1PrimaryColor,
    h1Colors,
    h1ChipRects,
    lines,
    subject: subjectEl && visible(subjectEl) ? rectOf(subjectEl) : null,
    presenter: presenterEl && visible(presenterEl) ? rectOf(presenterEl) : null,
    presenterSrc: presenterImg && visible(presenterImg) ? (presenterImg.getAttribute('src') || '') : '',
    presenterImgRect: presenterImg && visible(presenterImg) ? rectOf(presenterImg) : null,
    stats: statsEl && visible(statsEl) ? rectOf(statsEl) : null,
    cta: ctaEl && visible(ctaEl) ? rectOf(ctaEl) : null,
    nums: numEls.length,
    numRects: numEls.map(rectOf),
    numTexts: numEls.map((el) => (el.textContent || '').trim()),
    blocks: blockEls.length,
  };
}
"""


# --- 几何与明度评估 ----------------------------------------------------------


def _overlap_area(a: dict[str, float] | None, b: dict[str, float] | None) -> float:
    if not a or not b:
        return 0.0
    left = max(float(a['left']), float(b['left']))
    right = min(float(a['right']), float(b['right']))
    top = max(float(a['top']), float(b['top']))
    bottom = min(float(a['bottom']), float(b['bottom']))
    if right <= left or bottom <= top:
        return 0.0
    return (right - left) * (bottom - top)


def _clipped_area_ratio(rect: dict[str, float], width: int, height: int) -> float:
    canvas_rect = {'left': 0.0, 'top': 0.0, 'right': float(width), 'bottom': float(height)}
    return _overlap_area(rect, canvas_rect) / float(width * height)


def _non_space_char_count(text: str) -> int:
    return len(re.sub(r'\s+', '', text))


def _perceived_luma(rgb: list[float] | tuple[int, int, int]) -> float:
    r, g, b = rgb[0], rgb[1], rgb[2]
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def _rgb_distance(a: tuple[int, int, int], b: list[float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def measure_title_contrast(image_1x_path: Path, snapshot: dict[str, Any]) -> float | None:
    """计算主标题文字与实际背景像素的中位明度差（0.0..1.0）。"""
    from PIL import Image

    lines = snapshot.get('lines') or []
    primary_color = snapshot.get('h1PrimaryColor')
    if not lines or not primary_color:
        return None

    text_colors = snapshot.get('h1Colors') or [primary_color]
    chip_rects = snapshot.get('h1ChipRects') or []

    with Image.open(image_1x_path) as raw:
        img = raw.convert('RGB')
        width, height = img.size
        pixels = img.load()

        bg_lumas: list[float] = []
        for line in lines:
            x0 = max(0, min(width, int(line['left'])))
            x1 = max(0, min(width, int(line['right'])))
            y0 = max(0, min(height, int(line['top'])))
            y1 = max(0, min(height, int(line['bottom'])))
            if x1 <= x0 or y1 <= y0:
                continue
            step_x = max(1, (x1 - x0) // 80)
            step_y = max(1, (y1 - y0) // 24)
            for y in range(y0, y1, step_y):
                for x in range(x0, x1, step_x):
                    if any(
                        cr['left'] <= x <= cr['right'] and cr['top'] <= y <= cr['bottom']
                        for cr in chip_rects
                    ):
                        continue
                    px = pixels[x, y]
                    if any(_rgb_distance(px, tc) < 42.0 for tc in text_colors):
                        continue
                    bg_lumas.append(_perceived_luma(px))

    if not bg_lumas:
        return None
    bg_lumas.sort()
    median_bg = bg_lumas[len(bg_lumas) // 2]
    text_luma = _perceived_luma(primary_color)
    return round(abs(text_luma - median_bg), 3)


def evaluate_cover_snapshot(
    *,
    cover_id: str,
    width: int,
    height: int,
    snapshot: dict[str, Any],
    static_issues: list[tuple[str, str]],
    contrast_diff: float | None,
    allow_zero_num: bool,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    warnings: list[str] = []

    def add_finding(check: str, issue: str) -> None:
        findings.append({'cover': cover_id, 'check': check, 'issue': issue})

    for check, issue in static_issues:
        add_finding(check, issue)

    doc_w, doc_h = snapshot['doc']
    if doc_w != width or doc_h != height:
        add_finding(
            'doc_overflow',
            f'document scroll size is {doc_w}x{doc_h}, expected exact {width}x{height}',
        )

    if snapshot['fontsStatus'] != 'loaded':
        add_finding('asset_load_failure', f'document.fonts.status is {snapshot["fontsStatus"]!r}')
    if snapshot['brokenImages']:
        add_finding('asset_load_failure', f'failed image(s): {", ".join(snapshot["brokenImages"])}')

    if snapshot.get('hasTopBar'):
        add_finding(
            'top_bar_forbidden',
            'top info bar (.bar) must be omitted; keep only hook, 1–3 key numbers, subject, and presenter',
        )

    blocks = int(snapshot['blocks'])
    if blocks < 1 or blocks > MAX_BLOCKS:
        add_finding(
            'visual_blocks_count',
            f'[data-block] count is {blocks}, must be between 1 and {MAX_BLOCKS}',
        )

    nums = int(snapshot['nums'])
    min_nums = 0 if allow_zero_num else MIN_NUMS
    if not (min_nums <= nums <= MAX_NUMS):
        add_finding(
            'num_count',
            f'[data-num] count is {nums}, must be between {min_nums} and {MAX_NUMS}',
        )

    h1_rect = snapshot.get('h1')
    lines = snapshot.get('lines') or []
    if not h1_rect or not lines:
        add_finding('h1_missing', 'missing visible <h1> hook title')
    else:
        if len(lines) != 2 or any(int(line.get('wrappedRows', 1)) > 1 for line in lines):
            add_finding(
                'title_line_count',
                f'<h1> must render as fixed 2 non-wrapping lines, got {len(lines)} line(s) '
                f'(wrappedRows={[line.get("wrappedRows", 1) for line in lines]})',
            )
        if not all(bool(line.get('nowrap')) for line in lines):
            add_finding('title_nowrap', 'every <h1> line must declare white-space: nowrap')
        for idx, line in enumerate(lines, 1):
            chars = _non_space_char_count(line.get('text', ''))
            if chars == 0 or chars > MAX_LINE_CHARS:
                add_finding(
                    'title_char_limit',
                    f'<h1> line {idx} ({line.get("text", "")!r}) has {chars} non-space chars '
                    f'(must be 1..{MAX_LINE_CHARS})',
                )
            elif chars > TARGET_LINE_CHARS:
                warnings.append(
                    f'[{cover_id}] title_char_target: line {idx} has {chars} chars '
                    f'(copy target <= {TARGET_LINE_CHARS}, hard limit <= {MAX_LINE_CHARS})'
                )
            if line['left'] < -2 or line['right'] > width + 2:
                add_finding(
                    'title_overflow',
                    f'<h1> line {idx} bounds [{line["left"]}, {line["right"]}] exceed canvas [0, {width}]',
                )

    subject_rect = snapshot.get('subject')
    subject_ratio: float | None = None
    if not subject_rect:
        add_finding('subject_missing', 'missing visible [data-subject] focal element')
    else:
        subject_ratio = round(_clipped_area_ratio(subject_rect, width, height), 3)
        if not (MIN_SUBJECT_RATIO <= subject_ratio <= MAX_SUBJECT_RATIO):
            add_finding(
                'subject_ratio',
                f'subject occupies {subject_ratio:.1%} of canvas, must be within 45%–65%',
            )
        elif width == 1080 and height == 1440 and subject_ratio < PORTRAIT_3X4_TARGET_MIN_RATIO - 0.01:
            warnings.append(
                f'[{cover_id}] portrait_subject_target: 3:4 subject occupies {subject_ratio:.1%} '
                '(recommended 55%–65% for 1080x1440)'
            )

    # 招手主持人固定槽位与资源检查
    expected_slot = video_contract.cover_presenter_slot(width, height)
    presenter_rect = snapshot.get('presenter')
    presenter_src = snapshot.get('presenterSrc') or ''
    presenter_img_rect = snapshot.get('presenterImgRect')
    if not presenter_rect:
        add_finding(
            'presenter_missing',
            f'missing visible .presenter element (required at left={expected_slot["x"]}px, '
            f'top={expected_slot["y"]}px, size={expected_slot["size"]}px)',
        )
    else:
        if 'presenter-wave.png' not in presenter_src:
            add_finding(
                'presenter_asset_invalid',
                f'.presenter must render presenter-wave.png, got src={presenter_src!r}',
            )
        if (
            abs(float(presenter_rect['left']) - expected_slot['x']) > SLOT_TOLERANCE_PX
            or abs(float(presenter_rect['top']) - expected_slot['y']) > SLOT_TOLERANCE_PX
            or abs(float(presenter_rect['width']) - expected_slot['size']) > SLOT_TOLERANCE_PX
            or abs(float(presenter_rect['height']) - expected_slot['size']) > SLOT_TOLERANCE_PX
        ):
            add_finding(
                'presenter_slot_mismatch',
                f'.presenter box is (left={presenter_rect["left"]:.0f}, top={presenter_rect["top"]:.0f}, '
                f'width={presenter_rect["width"]:.0f}, height={presenter_rect["height"]:.0f}), '
                f'expected fixed slot (left={expected_slot["x"]}, top={expected_slot["y"]}, '
                f'width={expected_slot["size"]}, height={expected_slot["size"]})',
            )
        elif presenter_img_rect and (
            abs(float(presenter_img_rect['width']) - expected_slot['size']) > SLOT_TOLERANCE_PX
            or abs(float(presenter_img_rect['height']) - expected_slot['size']) > SLOT_TOLERANCE_PX
        ):
            add_finding(
                'presenter_slot_mismatch',
                '.presenter img must fill the 1:1 square slot without distortion',
            )

    stats_rect = snapshot.get('stats')
    hit_presenter_stats = _overlap_area(presenter_rect, stats_rect) > OVERLAP_AREA_FLOOR_PX2
    if hit_presenter_stats:
        add_finding('presenter_stats_overlap', '.presenter and .stats bounding boxes overlap')
    if _overlap_area(presenter_rect, h1_rect) > OVERLAP_AREA_FLOOR_PX2:
        add_finding('presenter_title_overlap', '.presenter and <h1> bounding boxes overlap')
    if _overlap_area(h1_rect, stats_rect) > OVERLAP_AREA_FLOOR_PX2:
        add_finding('title_stats_overlap', '<h1> and .stats bounding boxes overlap')

    # 横版（4:3 / 16:9）左右分栏：标题行与主体图区水平间距 >= 40px
    if width > height and h1_rect and subject_rect and lines:
        vertical_overlap = min(h1_rect['bottom'], subject_rect['bottom']) - max(h1_rect['top'], subject_rect['top'])
        if vertical_overlap > 20:
            h1_cx = (h1_rect['left'] + h1_rect['right']) / 2.0
            sub_cx = (subject_rect['left'] + subject_rect['right']) / 2.0
            if h1_cx < sub_cx:
                max_right = max(line['right'] for line in lines)
                limit = subject_rect['left'] - (LANDSCAPE_GAP_PX - GAP_TOLERANCE_PX)
                if max_right > limit:
                    add_finding(
                        'landscape_text_gap',
                        f'left-text/right-subject gap too small: max line right={max_right}px, '
                        f'subject left={subject_rect["left"]:.0f}px (need >= 40px gap)',
                    )
            else:
                min_left = min(line['left'] for line in lines)
                limit = subject_rect['right'] + (LANDSCAPE_GAP_PX - GAP_TOLERANCE_PX)
                if min_left < limit:
                    add_finding(
                        'landscape_text_gap',
                        f'left-subject/right-text gap too small: min line left={min_left}px, '
                        f'subject right={subject_rect["right"]:.0f}px (need >= 40px gap)',
                    )

    # 16:9 右下角平台时长角标避让（1920 宽至少 190×80px）
    if abs((width / height) - (16.0 / 9.0)) < 0.03:
        safe_w = max(190.0, round(width * 190.0 / 1920.0))
        safe_h = max(80.0, round(height * 80.0 / 1080.0))
        badge_zone = {
            'left': width - safe_w,
            'top': height - safe_h,
            'right': float(width),
            'bottom': float(height),
        }
        for label, rect in (
            ('h1', h1_rect),
            ('presenter', presenter_rect),
            ('stats', stats_rect),
            ('cta', snapshot.get('cta')),
            *(('data-num', nr) for nr in (snapshot.get('numRects') or [])),
        ):
            if _overlap_area(rect, badge_zone) > OVERLAP_AREA_FLOOR_PX2:
                add_finding(
                    'badge_safe_zone_intrusion',
                    f'{label} intrudes into 16:9 bottom-right duration badge zone '
                    f'({safe_w:.0f}x{safe_h:.0f}px)',
                )

    if contrast_diff is not None and contrast_diff < MIN_TITLE_CONTRAST_DIFF:
        add_finding(
            'title_contrast_low',
            f'<h1> luminance diff vs background is {contrast_diff:.0%}, must be >= 60%',
        )

    metrics = {
        'doc': snapshot['doc'],
        'blocks': blocks,
        'nums': nums,
        'num_texts': snapshot.get('numTexts', []),
        'lines': [
            {'text': line.get('text', ''), 'left': line['left'], 'right': line['right']}
            for line in lines
        ],
        'subject_ratio': subject_ratio,
        'presenter_slot': expected_slot,
        'hit_presenter_stats': hit_presenter_stats,
        'title_contrast_diff': contrast_diff,
    }
    return findings, warnings, metrics


# --- 400px 缩略图生成 --------------------------------------------------------


def build_thumbnail(image_1x_path: Path, thumb_path: Path) -> None:
    """将 1x 成品缩到 400px 宽，供缩略图三问验收。"""
    from PIL import Image

    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_1x_path) as src:
        rgb = src.convert('RGB')
        thumb_h = max(1, round(rgb.height * THUMB_WIDTH_PX / rgb.width))
        thumb = rgb.resize((THUMB_WIDTH_PX, thumb_h), Image.Resampling.LANCZOS)
        thumb.save(thumb_path, format='PNG')


# --- 主流程 ------------------------------------------------------------------


def render_and_check_all(args: argparse.Namespace, cover_dir: Path) -> dict[str, Any]:
    from PIL import Image

    all_findings: list[dict[str, Any]] = []
    all_warnings: list[str] = []
    covers_report: list[dict[str, Any]] = []

    targets: list[tuple[str, int, int, Path]] = [
        (size_str, width, height, cover_dir / f'cover_{size_str}.html')
        for size_str, width, height in args.parsed_sizes
    ]

    need_browser = any(html_path.is_file() for *_, html_path in targets)
    session = chrome_cdp.launch_isolated(args.chrome_path) if need_browser else None
    try:
        for size_str, width, height, html_path in targets:
            rel_html = html_path.name
            rel_1x = f'cover_{size_str}.png'
            rel_2x = f'cover_{size_str}@2x.png'
            rel_thumb = f'qa/thumb_{size_str}_400w.png'

            if not html_path.is_file():
                finding = {
                    'cover': size_str,
                    'check': 'html_missing',
                    'issue': f'missing HTML source {rel_html}',
                }
                all_findings.append(finding)
                covers_report.append({
                    'size': size_str,
                    'width': width,
                    'height': height,
                    'html': rel_html,
                    'image': rel_1x,
                    'image_2x': rel_2x,
                    'thumb_400w': rel_thumb,
                    'metrics': None,
                    'findings': [finding],
                })
                continue

            html_text = html_path.read_text(encoding='utf-8')
            static_issues = check_html_css_source(html_text)

            out_2x_path = cover_dir / rel_2x
            out_1x_path = cover_dir / rel_1x
            thumb_path = cover_dir / rel_thumb

            log(f'Rendering {rel_html} ({width}x{height} @2x)...')
            assert session is not None
            context = session.browser.new_context(
                viewport={'width': width, 'height': height},
                device_scale_factor=2,
            )
            try:
                page = context.new_page()
                page.goto(html_path.as_uri(), wait_until='networkidle', timeout=30000)
                page.evaluate('() => document.fonts ? document.fonts.ready.then(() => true) : true')
                page.wait_for_timeout(120)
                snapshot = page.evaluate(MEASURE_COVER_JS)
                page.screenshot(path=str(out_2x_path), full_page=False)
            finally:
                context.close()

            with Image.open(out_2x_path) as img_2x:
                if img_2x.size != (width * 2, height * 2):
                    raise RuntimeError(
                        f'{rel_2x} expected {width * 2}x{height * 2}, got {img_2x.size[0]}x{img_2x.size[1]}'
                    )
                img_1x = img_2x.resize((width, height), Image.Resampling.LANCZOS)
                img_1x.save(out_1x_path, format='PNG')

            build_thumbnail(out_1x_path, thumb_path)
            contrast_diff = measure_title_contrast(out_1x_path, snapshot)

            findings, warnings, metrics = evaluate_cover_snapshot(
                cover_id=size_str,
                width=width,
                height=height,
                snapshot=snapshot,
                static_issues=static_issues,
                contrast_diff=contrast_diff,
                allow_zero_num=args.allow_zero_num,
            )
            all_findings.extend(findings)
            all_warnings.extend(warnings)
            covers_report.append({
                'size': size_str,
                'width': width,
                'height': height,
                'html': rel_html,
                'image': rel_1x,
                'image_2x': rel_2x,
                'thumb_400w': rel_thumb,
                'metrics': metrics,
                'findings': findings,
            })
    finally:
        if session is not None:
            session.close()

    return {
        'success': True,
        'verdict': 'fail' if all_findings else 'pass',
        'cover_dir': str(cover_dir),
        'sizes': [size_str for size_str, *_ in args.parsed_sizes],
        'covers': covers_report,
        'findings': all_findings,
        'warnings': all_warnings,
    }


def main() -> int:
    args = parse_args()
    cover_dir = resolve_cover_dir(args.cover_dir)
    report = render_and_check_all(args, cover_dir)
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        log(f'Wrote {output_path}')
    cli.print_json(report)
    return 0


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
