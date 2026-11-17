// Snapshot collection for scripts/check-composition.py.
// Loaded by the Python script and passed to Playwright's page.evaluate;
// it must stay a single async function expression: async (args) => {...}
async ({ checks }) => {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  async function seekTo(seconds) {
    const time = Math.max(0, Number(seconds) || 0);
    let didSeek = false;

    if (window.__layoutQA && typeof window.__layoutQA.seek === 'function') {
      try { await window.__layoutQA.seek(time); didSeek = true; } catch (_) {}
    }
    for (const media of Array.from(document.querySelectorAll('video,audio'))) {
      try {
        media.pause();
        // Not actually seekable without a finite duration: don't count it.
        if (!Number.isFinite(media.duration)) continue;
        media.currentTime = Math.max(0, Math.min(time, media.duration || time));
        didSeek = true;
      } catch (_) {}
    }
    // Test seam: compositions may toggle scene visibility on this event; the
    // built-in seek hooks above drive real animation timelines.
    window.__checkTime = time;
    try { document.dispatchEvent(new CustomEvent('check-time', { detail: { time } })); } catch (_) {}
    await sleep(didSeek ? 80 : 120);
    return didSeek;
  }

  function hasBox(rect) {
    return rect && rect.width > 3 && rect.height > 3;
  }

  function visible(el) {
    let current = el;
    while (current && current.nodeType === Node.ELEMENT_NODE) {
      const style = getComputedStyle(current);
      if (style.display === 'none' || ['hidden', 'collapse'].includes(style.visibility)
          || Number(style.opacity || 1) < 0.03) return false;
      current = current.parentElement;
    }
    return hasBox(el.getBoundingClientRect());
  }

  function labelOf(el) {
    return `${el.tagName || ''} ${el.id || ''} ${typeof el.className === 'string' ? el.className : ''}`.toLowerCase();
  }

  function hasOwnText(el) {
    return Array.from(el.childNodes).some(
      (node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim().length > 0);
  }

  function textContent(el) {
    return (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function textLineCount(el, fontSize) {
    if (!hasOwnText(el)) return 1;
    try {
      const range = document.createRange();
      range.selectNodeContents(el);
      const tops = Array.from(range.getClientRects())
        .filter((rect) => rect.width > 0 && rect.height > 0)
        .map((rect) => Math.round(rect.top));
      if (tops.length) return new Set(tops).size;
    } catch (_) {}
    return Math.max(1, Math.ceil(el.scrollHeight / Math.max(1, fontSize * 1.15) - 0.05));
  }

  function hasVisibleSurface(el) {
    const style = getComputedStyle(el);
    return (
      style.backgroundImage !== 'none' ||
      (style.backgroundColor && !['rgba(0, 0, 0, 0)', 'transparent'].includes(style.backgroundColor)) ||
      parseFloat(style.borderTopWidth || '0') > 0
    );
  }

  function selectorFor(el) {
    if (el.id) return `#${el.id}`;
    const raw = typeof el.className === 'string' ? el.className : (el.getAttribute?.('class') || '');
    const classes = raw.trim().split(/\s+/).filter(Boolean).slice(0, 3);
    if (classes.length) return `${el.tagName.toLowerCase()}.${classes.join('.')}`;
    return el.tagName.toLowerCase();
  }

  const CLIP_OVERFLOWS = new Set(['hidden', 'clip', 'scroll', 'auto']);
  const clean0 = (n) => (Object.is(n, -0) ? 0 : n);
  const clamp01 = (v) => Math.max(0, Math.min(1, v));

  function resolveOffset(token, free) {
    const t = String(token || '50%').trim().toLowerCase();
    if (t === 'left' || t === 'top') return 0;
    if (t === 'right' || t === 'bottom') return clean0(free);
    if (!t || t === 'center') return clean0(free * 0.5);
    if (t.startsWith('calc(')) {
      const terms = t.slice(5, -1).match(/[+-]?\s*\d+(?:\.\d+)?(?:%|px)/g);
      if (terms) return clean0(terms.reduce((acc, raw) => {
        const s = raw.replace(/\s+/g, '');
        return acc + (s.endsWith('%') ? free * (parseFloat(s) / 100) : parseFloat(s));
      }, 0));
    }
    const n = parseFloat(t);
    return Number.isFinite(n) ? clean0(t.endsWith('%') ? free * (n / 100) : n) : clean0(free * 0.5);
  }

  function computePaintedRect(box, iw, ih, fit, objectPosition) {
    if (iw <= 0 || ih <= 0 || box.width <= 0 || box.height <= 0 || fit === 'fill') return { ...box };
    let r = 1;
    if (fit === 'contain' || fit === 'scale-down') {
      r = Math.min(box.width / iw, box.height / ih, fit === 'scale-down' ? 1 : Infinity);
    } else if (fit === 'cover') {
      r = Math.max(box.width / iw, box.height / ih);
    } else if (fit !== 'none') {
      return { ...box };
    }
    const pw = iw * r, ph = ih * r;
    const parts = String(objectPosition || '50% 50%').trim().match(/calc\([^)]*\)|\S+/g) || ['50%', '50%'];
    if (parts.length === 1) {
      parts.push('50%');
      if (/^(top|bottom)$/i.test(parts[0])) parts.reverse();
    } else if (/^(top|bottom)$/i.test(parts[0]) || /^(left|right)$/i.test(parts[1])) {
      [parts[0], parts[1]] = [parts[1], parts[0]];
    }
    return {
      x: clean0(box.x + resolveOffset(parts[0], box.width - pw)),
      y: clean0(box.y + resolveOffset(parts[1], box.height - ph)),
      width: pw, height: ph,
    };
  }

  function clipAxis(r, b, cx, cy) {
    const x1 = cx ? Math.max(r.x, b.x) : r.x, x2 = cx ? Math.min(r.x + r.width, b.x + b.width) : r.x + r.width;
    const y1 = cy ? Math.max(r.y, b.y) : r.y, y2 = cy ? Math.min(r.y + r.height, b.y + b.height) : r.y + r.height;
    return (x2 <= x1 || y2 <= y1)
      ? { x: clean0(x1), y: clean0(y1), width: 0, height: 0 }
      : { x: clean0(x1), y: clean0(y1), width: x2 - x1, height: y2 - y1 };
  }

  function clipByAncestors(el, startRect) {
    let vis = { ...startRect };
    for (let cur = el.parentElement; cur && cur.nodeType === Node.ELEMENT_NODE; cur = cur.parentElement) {
      const atDocRoot = cur === document.body || cur === document.documentElement;
      const st = getComputedStyle(cur);
      const cx = CLIP_OVERFLOWS.has(st.overflowX), cy = CLIP_OVERFLOWS.has(st.overflowY);
      if (cx || cy) {
        const ar = cur.getBoundingClientRect();
        vis = clipAxis(vis, { x: ar.left, y: ar.top, width: ar.width, height: ar.height }, cx, cy);
      }
      if (atDocRoot) break;
    }
    return vis;
  }

  function buildMediaInfo(el, style, boxRect) {
    const tag = el.tagName === 'IMG' ? 'img' : (el.tagName === 'VIDEO' ? 'video' : null);
    if (!tag) return null;
    const intrinsicWidth = tag === 'img' ? (el.naturalWidth || 0) : (el.videoWidth || 0);
    const intrinsicHeight = tag === 'img' ? (el.naturalHeight || 0) : (el.videoHeight || 0);
    const objectFit = (style.objectFit || 'fill').trim().toLowerCase();
    const objectPosition = (style.objectPosition || '50% 50%').trim();
    const paintedRect = computePaintedRect(boxRect, intrinsicWidth, intrinsicHeight, objectFit, objectPosition);
    const scale = (intrinsicWidth > 0 && intrinsicHeight > 0)
      ? Math.max(paintedRect.width / intrinsicWidth, paintedRect.height / intrinsicHeight) : null;
    const visibleRect = clipByAncestors(el, clipAxis(paintedRect, boxRect, true, true));
    const cropBox = (paintedRect.width > 0 && paintedRect.height > 0 && visibleRect.width > 0 && visibleRect.height > 0)
      ? {
          x: clamp01((visibleRect.x - paintedRect.x) / paintedRect.width),
          y: clamp01((visibleRect.y - paintedRect.y) / paintedRect.height),
          w: clamp01(visibleRect.width / paintedRect.width),
          h: clamp01(visibleRect.height / paintedRect.height),
        } : null;
    const base = tag === 'img'
      ? { tag: 'img', complete: el.complete, naturalWidth: el.naturalWidth, src: el.getAttribute('src') || '' }
      : { tag: 'video', readyState: el.readyState, error: Boolean(el.error), src: el.getAttribute('src') || '' };
    return {
      ...base, intrinsicWidth, intrinsicHeight, objectFit, objectPosition,
      mediaRole: (el.getAttribute('data-media-role') || '').trim().toLowerCase(),
      materialRef: (el.getAttribute('data-material-ref') || '').trim(),
      resolvedSrc: el.currentSrc || el.src || '',
      paintedRect, scale, visibleRect, cropBox,
    };
  }

  function effectiveZLayer(el) {
    for (let cur = el; cur && cur.nodeType === Node.ELEMENT_NODE; cur = cur.parentElement) {
      if (cur === document.body || cur === document.documentElement || cur.hasAttribute('data-scene-id')) break;
      const st = getComputedStyle(cur);
      if (st.position !== 'static' && st.zIndex && st.zIndex !== 'auto') {
        const z = parseInt(st.zIndex, 10);
        if (Number.isFinite(z)) return z;
      }
    }
    return 0;
  }

  function findSvgGroupRect(el, tag) {
    const g = tag === 'text' && el.namespaceURI?.includes('svg') ? el.parentElement : null;
    if (!g || g.tagName.toLowerCase() !== 'g') return null;
    const rects = Array.from(g.children).filter(
      (c) => c.tagName.toLowerCase() === 'rect' && hasBox(c.getBoundingClientRect()) && visible(c));
    if (rects.length !== 1) return null;
    const r = rects[0].getBoundingClientRect();
    return { x: r.left, y: r.top, width: r.width, height: r.height };
  }

  function collectSnapshot(time, sought) {
    const elements = [];
    const domIds = new Map();
    let nextDomId = 1;
    const getDomId = (node) => {
      if (!domIds.has(node)) domIds.set(node, nextDomId++);
      return domIds.get(node);
    };

    for (const el of Array.from(document.querySelectorAll('*'))) {
      if (el.nodeType !== Node.ELEMENT_NODE) continue;
      const rect = el.getBoundingClientRect();
      if (!hasBox(rect) || !visible(el)) continue;
      const style = getComputedStyle(el);
      const tag = el.tagName.toLowerCase();
      const boxRect = { x: rect.left, y: rect.top, width: rect.width, height: rect.height };
      const isSceneRoot = el.hasAttribute('data-scene-id');
      const layoutIgnore = el.hasAttribute('data-layout-ignore');
      const ancestors = [];
      const ancestorDomIds = [];
      for (let cur = el.parentElement; cur; cur = cur.parentElement) {
        ancestorDomIds.push(getDomId(cur));
        if (cur.id) ancestors.push(cur.id);
        const compId = cur.getAttribute?.('data-composition-id');
        if (compId) ancestors.push(compId);
      }
      elements.push({
        domId: getDomId(el),
        parentDomId: el.parentElement ? getDomId(el.parentElement) : null,
        ancestorDomIds,
        selector: selectorFor(el),
        id: el.id || '',
        compositionId: el.getAttribute('data-composition-id') || '',
        tag,
        display: style.display || '',
        zLayer: effectiveZLayer(el),
        label: labelOf(el),
        rect: boxRect,
        svgGroupRect: findSvgGroupRect(el, tag),
        ownText: hasOwnText(el),
        text: textContent(el),
        fontSize: parseFloat(style.fontSize || '0') || 0,
        isCaption: /subtitle|caption|closed-caption/.test(labelOf(el)) || Boolean(el.closest(
          '[data-composition-id="caption-bar"], [data-track-kind="captions"]'
        )),
        isUiText: Boolean(el.closest('[data-text-role="ui"]')),
        isSceneRoot,
        sceneId: el.closest('[data-scene-id]')?.getAttribute('data-scene-id') || null,
        lineCount: textLineCount(el, parseFloat(style.fontSize || '0')),
        layoutIgnore,
        surface: hasVisibleSurface(el),
        media: buildMediaInfo(el, style, boxRect),
        ancestors,
        overflowStyle: [style.overflowX, style.overflowY].join(' '),
        clientWidth: el.clientWidth,
        clientHeight: el.clientHeight,
        scrollWidth: el.scrollWidth,
        scrollHeight: el.scrollHeight,
      });
    }
    const captionTexts = elements
      .filter((el) => el.isCaption && el.ownText && el.text)
      .map((el) => el.text);
    const captionDetails = elements
      .filter((el) => el.isCaption && el.ownText && el.text)
      .map((el) => ({ text: el.text, fontSize: el.fontSize, lineCount: el.lineCount, rect: el.rect }));
    const presenterStage = document.querySelector('#presenter-stage');
    const presenterHost = document.querySelector('#presenter, [data-composition-id="presenter"]');
    const presenterVisible = Boolean(presenterStage ? visible(presenterStage) : (presenterHost && visible(presenterHost)));
    return {
      time,
      sought,
      fontsStatus: document.fonts ? document.fonts.status : 'loaded',
      presenterVisible,
      elements,
      captionTexts,
      captionDetails,
    };
  }

  const results = [];
  for (const check of checks) {
    const sought = await seekTo(check.time);
    await sleep(150);
    results.push({ scene_id: check.scene_id, ...collectSnapshot(check.time, sought) });
  }
  return results;
}
