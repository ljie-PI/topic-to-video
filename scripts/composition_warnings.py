"""composition 渲染前检查的非阻塞启发式画面质量 warnings 分析模块。"""
from __future__ import annotations

import math
import posixpath
import re
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import Any

Rect = dict[str, float]
WarningEntry = tuple[str, str, Any, str]  # (scene_id, check, dedup_key, detail)

def _discover_transition_tokens() -> frozenset[str]:
    root = Path(__file__).resolve().parent.parent / 'modules' / 'transitions'
    discovered = {p.name.lower() for p in root.iterdir() if p.is_dir()} if root.is_dir() else set()
    return frozenset({'tile-wipe', *discovered})


MEDIA_MIN_CONTENT_INTRINSIC_W = 400
DEFAULT_LONG_SVG_LINE_PX = 520
EXEMPT_MEDIA_ROLES = frozenset({'logo', 'icon'})
TRANSITION_TOKENS = _discover_transition_tokens()
_DUP_STRIP_RE = re.compile(r'[\s，。；：！？、,;:!?\-—–•·|()（）【】\[\]"\'“”‘’`]+|(?<!\d)\.(?!\d)')
_CLAUSE_SPLIT_RE = re.compile(r'[，。；：！？、,;:!?\n\r•·|—–]+|(?<!\d)\.(?!\d)|\s{2,}')


def rects_intersect(a: Rect, b: Rect) -> bool:
    return a['x'] < b['x'] + b['width'] and b['x'] < a['x'] + a['width'] and a['y'] < b['y'] + b['height'] and b['y'] < a['y'] + a['height']


def intersection_area(a: Rect, b: Rect) -> float:
    w = min(a['x'] + a['width'], b['x'] + b['width']) - max(a['x'], b['x'])
    h = min(a['y'] + a['height'], b['y'] + b['height']) - max(a['y'], b['y'])
    return w * h if w > 0 and h > 0 else 0.0


def assign_content_region(rect: Rect, regions: Any) -> dict[str, Any] | None:
    area, _, best = max(((intersection_area(rect, r['rect']), -i, r) for i, r in enumerate(regions.content)), default=(0.0, 0, None))
    return best if area > 0 else None


def element_owner_region(element: dict[str, Any], reserved_tokens: dict[str, list[str]]) -> str | None:
    candidates = {element['id'].lower(), *(a.lower() for a in element['ancestors'])}
    return next((rid for rid, toks in reserved_tokens.items() if candidates.intersection(toks)), None)


def element_in_ignored_subtree(element: dict[str, Any], elements: list[dict[str, Any]]) -> bool:
    anc_dom = element.get('ancestorDomIds')
    if isinstance(anc_dom, list) and {el['domId'] for el in elements if el.get('layoutIgnore') and el.get('domId') is not None}.intersection(anc_dom):
        return True
    return bool({el['id'] for el in elements if el.get('layoutIgnore') and el.get('id')}.intersection(element['ancestors']))


def normalize_text(text: str) -> str:
    return re.sub(r'\s+', '', text)


def media_load_error(element: dict[str, Any]) -> str | None:
    media = element['media']
    if not media:
        return None
    if media['tag'] == 'img' and media['complete'] and media['naturalWidth'] == 0:
        return f'{element["selector"]} image failed to load: {media["src"]}'
    if media['tag'] == 'video' and media['src'] and (media['error'] or media['readyState'] == 0):
        return f'{element["selector"]} video failed to load: {media["src"]}'
    return None


def _as_rect(r: dict[str, Any]) -> Rect:
    return {k: float(r[k]) for k in ('x', 'y', 'width', 'height')}


def _is_ancestor_of(anc: dict[str, Any], desc: dict[str, Any]) -> bool:
    anc_dom, desc_ancs = anc.get('domId'), desc.get('ancestorDomIds')
    return anc_dom in desc_ancs if anc_dom is not None and isinstance(desc_ancs, list) else (bool(anc.get('id')) and anc['id'] in (desc.get('ancestors') or ()))


def _collect_candidates(
    snapshot: dict[str, Any], scene_regions: Any, caption_regions: Any | None,
    filter_scene: bool, template_scene_id: str | None,
) -> list[dict[str, Any]]:
    sid, elements = snapshot['scene_id'], snapshot.get('elements') or []
    tpl = template_scene_id.lower() if template_scene_id else None
    out: list[dict[str, Any]] = []
    for el in elements:
        if el.get('tag') in ('html', 'body') or (filter_scene and el.get('sceneId') not in (None, sid)):
            continue
        if el.get('isSceneRoot') or el.get('layoutIgnore') or el.get('isCaption') or element_in_ignored_subtree(el, elements):
            continue
        toks = {str(el.get('id') or '').lower(), str(el.get('compositionId') or '').lower(), *(str(a).lower() for a in (el.get('ancestors') or ()))} - {''}
        if (toks & TRANSITION_TOKENS) or (tpl and tpl in toks):
            continue
        if element_owner_region(el, scene_regions.reserved_tokens) or (caption_regions and element_owner_region(el, caption_regions.reserved_tokens)):
            continue
        out.append(el)
    return out


def content_media_metrics(element: dict[str, Any]) -> dict[str, Any] | None:
    info = element.get('media')
    if not isinstance(info, dict) or media_load_error(element) is not None:
        return None
    if str(info.get('mediaRole') or '').strip().lower() in EXEMPT_MEDIA_ROLES:
        return None
    raw_iw = info.get('intrinsicWidth')
    iw = float(raw_iw if raw_iw is not None else (info.get('naturalWidth') or 0))
    ih = float(info.get('intrinsicHeight') or 0)
    vis_rect = _as_rect(info.get('visibleRect') or element['rect'])
    if vis_rect['width'] <= 3.0 or vis_rect['height'] <= 3.0:
        return None
    painted = _as_rect(info.get('paintedRect') or element['rect'])
    scale = info.get('scale')
    if scale is None and iw > 0 and ih > 0:
        scale = max(painted['width'] / iw, painted['height'] / ih)
    scale_val = float(scale) if isinstance(scale, (int, float)) and not isinstance(scale, bool) and math.isfinite(scale) else None
    crop = info.get('cropBox')
    if isinstance(crop, dict) and {'x', 'y', 'w', 'h'} <= set(crop):
        crop_box = {k: float(crop[k]) for k in ('x', 'y', 'w', 'h')}
    else:
        pw, ph = max(painted['width'], 1.0), max(painted['height'], 1.0)
        clamp = lambda v: max(0.0, min(1.0, v))  # noqa: E731
        crop_box = {'x': clamp((vis_rect['x'] - painted['x']) / pw), 'y': clamp((vis_rect['y'] - painted['y']) / ph),
                    'w': clamp(vis_rect['width'] / pw), 'h': clamp(vis_rect['height'] / ph)}
    return {
        'element': element, 'media': info, 'tag': str(info.get('tag') or element.get('tag') or 'img').lower(),
        'intrinsicWidth': iw, 'intrinsicHeight': ih, 'visibleRect': vis_rect, 'scale': scale_val, 'cropBox': crop_box,
    }


def is_non_icon_content_media(media_item: dict[str, Any], *, allow_zero_video: bool = False) -> bool:
    """非 logo/icon 内容媒体谓词：要求固有宽 >= 400px；遮挡与复用额外接纳未探测宽高的 <video>。"""
    if str(media_item.get('media', {}).get('mediaRole') or '').strip().lower() in EXEMPT_MEDIA_ROLES:
        return False
    iw = float(media_item['intrinsicWidth'])
    return iw >= MEDIA_MIN_CONTENT_INTRINSIC_W or (allow_zero_video and media_item.get('tag') == 'video' and iw <= 0)


def canonical_media_key(media_info: dict[str, Any], composition_dir: Path) -> str | None:
    if ref := str(media_info.get('materialRef') or '').strip():
        return f'ref:{ref}'
    raw = str(media_info.get('resolvedSrc') or media_info.get('src') or '').strip()
    if not raw or raw.startswith(('data:', 'about:', 'blob:')):
        return None
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme in ('http', 'https'):
        return f'{parsed.scheme}://{parsed.netloc}{posixpath.normpath(urllib.parse.unquote(parsed.path or "/"))}'
    rel_or_abs = urllib.parse.unquote(parsed.path)
    if not rel_or_abs:
        return None
    fs_path = Path(rel_or_abs).resolve() if parsed.scheme == 'file' else (composition_dir / rel_or_abs).resolve()
    try:
        return fs_path.relative_to(composition_dir.resolve().parent).as_posix()
    except ValueError:
        return fs_path.as_posix()


def _check_snapshot_entries(
    sid: str, candidates: list[dict[str, Any]], scene_regions: Any, *, long_line_px: int = DEFAULT_LONG_SVG_LINE_PX,
) -> list[WarningEntry]:
    out: list[WarningEntry] = []
    related = lambda a, b: a is b or _is_ancestor_of(a, b) or _is_ancestor_of(b, a)  # noqa: E731
    for el in candidates:
        tag = el.get('tag')
        if tag in ('text', 'tspan') and el.get('ownText') and (txt := str(el.get('text') or '').strip()):
            ascii_ratio = sum(1 for ch in txt if ord(ch) < 128) / max(1, len(txt))
            if ascii_ratio > 0.7 and el['rect']['width'] > long_line_px:
                out.append((
                    sid, 'long_svg_text_line', (el['selector'], txt[:32]),
                    f'{el["selector"]} ({txt[:32]!r}) renders {el["rect"]["width"]:.0f}px wide (> {long_line_px}px); '
                    'wrap or place code/long English lines inside a bounded HTML IDE/terminal panel',
                ))
        if tag != 'text' or not isinstance(el.get('svgGroupRect'), dict) or not (txt := str(el.get('text') or '').strip()):
            continue
        tr, rr = el['rect'], _as_rect(el['svgGroupRect'])
        if rr['width'] * rr['height'] > tr['width'] * tr['height'] and intersection_area(tr, rr) > 0 and (
            tr['x'] < rr['x'] - 4.0 or tr['y'] < rr['y'] - 4.0
            or tr['x'] + tr['width'] > rr['x'] + rr['width'] + 4.0 or tr['y'] + tr['height'] > rr['y'] + rr['height'] + 4.0
        ):
            out.append((sid, 'svg_text_overflow', (el['selector'], txt[:24]), f'{el["selector"]} ({txt[:24]!r}) overflows its <g> rect ({tr["width"]:.0f}x{tr["height"]:.0f} vs {rr["width"]:.0f}x{rr["height"]:.0f})'))

    media_items = [m for el in candidates if (m := content_media_metrics(el)) is not None]
    sized_media = [m for m in media_items if is_non_icon_content_media(m)]
    target_media = [m for m in media_items if is_non_icon_content_media(m, allow_zero_video=True)]
    non_media = [el for el in candidates if not el.get('media') and (el.get('ownText') or el.get('surface'))]

    by_reg: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for m in sized_media:
        if (reg := assign_content_region(m['visibleRect'], scene_regions)) is not None:
            by_reg.setdefault(reg['id'], []).append((m, reg))
    for rid, group in by_reg.items():
        n = len(group)
        for m, reg in group:
            vis, r = m['visibleRect'], reg['rect']
            if (vis['width'] < (r['width'] / n) * 0.35 and vis['height'] < r['height'] * 0.35) or vis['width'] * vis['height'] < (r['width'] * r['height'] / n) * 0.15:
                sel = m['element']['selector']
                out.append((sid, 'media_too_small', (sel, rid), f'{sel} visible area {vis["width"]:.0f}x{vis["height"]:.0f} is too small in region {rid!r} ({r["width"]:.0f}x{r["height"]:.0f}, N={n})'))

    for m in sized_media:
        scale, iw, sel = m['scale'], m['intrinsicWidth'], m['element']['selector']
        if not scale or scale <= 0 or (scene_regions.content and assign_content_region(m['visibleRect'], scene_regions) is None):
            continue
        min_s = 0.35 if iw > 1920 else 0.45
        if scale < min_s:
            out.append((sid, 'media_blurry_scale', (sel, 'downscale'), f'{sel} downscaled to {scale:.2f}x (< {min_s:.2f}x for {iw:.0f}px source)'))
        elif scale > 1.25:
            out.append((sid, 'media_blurry_scale', (sel, 'upscale'), f'{sel} upscaled to {scale:.2f}x (> 1.25x for {iw:.0f}px source)'))

    for m in target_media:
        vis, media_el = m['visibleRect'], m['element']
        if vis['width'] <= 12.0 or vis['height'] <= 12.0:
            continue
        inner = {'x': vis['x'] + 6.0, 'y': vis['y'] + 6.0, 'width': vis['width'] - 12.0, 'height': vis['height'] - 12.0}
        occluders: list[dict[str, Any]] = []
        for other in non_media:
            if not related(media_el, other) and not any(_is_ancestor_of(p, other) for p in occluders) and (occ := intersection_area(other['rect'], inner)) >= 64.0:
                occluders.append(other)
                out.append((sid, 'material_occlusion', (other['selector'], (other.get('text') or '')[:16], media_el['selector']), f'{other["selector"]} occludes media {media_el["selector"]} ({occ:.0f}px^2)'))

    reported: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for idx, a in enumerate(non_media):
        for b in non_media[idx + 1:]:
            if a.get('zLayer', 0) != b.get('zLayer', 0):
                continue
            if related(a, b) or (
                a.get('tag') != 'text' and b.get('tag') != 'text' and a.get('display') == 'inline' and b.get('display') == 'inline'
                and a.get('parentDomId') is not None and a.get('parentDomId') == b.get('parentDomId')
                and (int(a.get('lineCount') or 1) > 1 or int(b.get('lineCount') or 1) > 1)
            ) or any((pa is a or _is_ancestor_of(pa, a)) and (pb is b or _is_ancestor_of(pb, b)) for pa, pb in reported):
                continue
            ov = intersection_area(a['rect'], b['rect'])
            min_area = min(a['rect']['width'] * a['rect']['height'], b['rect']['width'] * b['rect']['height'])
            if ov >= 64.0 and min_area > 0 and ov >= 0.20 * min_area:
                reported.append((a, b))
                dedup = (
                    a['selector'], (a.get('text') or '')[:16], round(a['rect']['x'], -1) if not a.get('id') and not a.get('text') else 0,
                    b['selector'], (b.get('text') or '')[:16], round(b['rect']['x'], -1) if not b.get('id') and not b.get('text') else 0,
                )
                out.append((sid, 'element_overlap', dedup, f'{a["selector"]} overlaps {b["selector"]} ({ov:.0f}px^2, {ov / min_area * 100:.0f}% of smaller element)'))

    rids = {r['id'] for r in scene_regions.content}
    if 'side' in rids and (rids & {'main', 'header'}):
        raw_els = [el for el in candidates if not el.get('media') and (el.get('ownText') or el.get('tag') == 'text') and str(el.get('text') or '').strip()]
        primary, side_clauses = [], []
        for el in (e for e in raw_els if not any(o is not e and _is_ancestor_of(o, e) for o in raw_els)):
            raw = str(el.get('text') or '')
            cleaned = _DUP_STRIP_RE.sub('', raw.lower())
            if len(normalize_text(raw)) < 8 or len(cleaned) < 8:
                continue
            reg = assign_content_region(el['rect'], scene_regions)
            if reg and reg['id'] in ('main', 'header'):
                primary.append(cleaned)
            elif reg and reg['id'] == 'side':
                side_clauses.extend([c for p in _CLAUSE_SPLIT_RE.split(raw) if len(c := _DUP_STRIP_RE.sub('', p.lower())) >= 6] or [cleaned])
        if primary and (total_side := sum(len(c) for c in side_clauses)) >= 8:
            corpus = '\n'.join(primary)
            matched = [c for c in side_clauses if c in corpus]
            if (ratio := sum(len(c) for c in matched) / total_side) >= 0.50:
                out.append((sid, 'region_text_duplication', 'side', f'side repeats {ratio * 100:.0f}% of clause text from main/header (e.g. {matched[0][:20]!r})'))
    return out


def collect_composition_warnings(
    *, scenes: list[dict[str, Any]], snapshot_by_scene: dict[str, list[dict[str, Any]]],
    default_regions: Any, visual_by_id: dict[str, dict[str, Any]], caption_segments: list[dict[str, Any]],
    composition_dir: Path, region_index_factory: Callable[[dict[str, Any]], Any], filter_scene: bool = False,
    long_line_px: int = DEFAULT_LONG_SVG_LINE_PX,
) -> list[str]:
    """按场景中点优先采样收集全部非阻塞质量 warnings 并按场景顺序去重。"""
    entries: list[WarningEntry] = []
    appearances: dict[str, dict[int, list[list[tuple[str, dict[str, float]]]]]] = {}
    for scene_idx, scene in enumerate(scenes):
        sid = scene['scene_id']
        snaps = snapshot_by_scene.get(sid, [])
        if not snaps:
            continue
        vscene = visual_by_id.get(sid)
        tpl = vscene['template']['scene'] if vscene and isinstance(vscene.get('template'), dict) else None
        s_regions = region_index_factory(vscene['layout']) if vscene else default_regions
        snap_cands = [
            _collect_candidates(
                snap, s_regions,
                region_index_factory(
                    next((s for s in caption_segments if s['begin_s'] <= snap['time'] < s['end_s']), caption_segments[-1])['layout_data']
                ) if caption_segments else None,
                filter_scene, tpl,
            )
            for snap in snaps
        ]
        mid = len(snap_cands) // 2
        for cands in (snap_cands[mid], *snap_cands[:mid], *snap_cands[mid + 1:]):
            entries.extend(_check_snapshot_entries(sid, cands, s_regions, long_line_px=long_line_px))
        if len(scenes) >= 2:
            for cands in snap_cands:
                per_snap: dict[str, list[tuple[str, dict[str, float]]]] = {}
                for el in cands:
                    if (m := content_media_metrics(el)) is None:
                        continue
                    if not str(m['media'].get('materialRef') or '').strip() and not is_non_icon_content_media(m, allow_zero_video=True):
                        continue
                    if s_regions.content and assign_content_region(m['visibleRect'], s_regions) is None:
                        continue
                    if key := canonical_media_key(m['media'], composition_dir):
                        per_snap.setdefault(key, []).append((m['tag'], m['cropBox']))
                for key, items in per_snap.items():
                    appearances.setdefault(key, {}).setdefault(scene_idx, []).append(items)

    for key, by_idx in appearances.items():
        idxs = sorted(by_idx)
        for prev_i, curr_i in zip(idxs, idxs[1:]):
            prev_sid, curr_sid = scenes[prev_i]['scene_id'], scenes[curr_i]['scene_id']
            if curr_i - prev_i > 1:
                entries.append((curr_sid, 'media_reuse', (prev_sid, key), f'non-adjacent reuse of {key} (previously used in {prev_sid})'))
                continue
            prev_snaps, curr_snaps = by_idx[prev_i], by_idx[curr_i]
            if any(tag == 'video' for s in (*prev_snaps, *curr_snaps) for tag, _ in s):
                entries.append((curr_sid, 'media_reuse', (prev_sid, key), f'adjacent reuse of video {key} (previously used in {prev_sid})'))
                continue
            shifted = any(
                max(abs((b2['x'] + b2['w'] * 0.5) - (b1['x'] + b1['w'] * 0.5)), abs((b2['y'] + b2['h'] * 0.5) - (b1['y'] + b1['h'] * 0.5))) >= 0.08
                or max(abs(b2['w'] - b1['w']), abs(b2['h'] - b1['h'])) >= 0.08
                for _, b1 in prev_snaps[len(prev_snaps) // 2]
                for _, b2 in curr_snaps[len(curr_snaps) // 2]
            )
            if not shifted:
                entries.append((curr_sid, 'media_reuse', (prev_sid, key), f'adjacent reuse of image {key} without focal zoom/pan shift (previously used in {prev_sid})'))

    seen_keys, seen_strs = set(), set()
    by_scene: dict[str, list[str]] = {}
    for sid, check, dkey, detail in entries:
        formatted = f'[{sid}] {check}: {detail}'
        if (sid, check, dkey) in seen_keys or formatted in seen_strs:
            continue
        seen_keys.add((sid, check, dkey))
        seen_strs.add(formatted)
        by_scene.setdefault(sid, []).append(formatted)
    return [w for s in scenes for w in by_scene.pop(s['scene_id'], [])] + [w for rest in by_scene.values() for w in rest]
