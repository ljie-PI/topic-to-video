// motion-utils.mjs — shared 1:1 SVG stage setup, CJK/ASCII & loaded-font text
// wrapping, font-readiness relayout, and reversible tween helpers for motions/*.

const SVG_NS = "http://www.w3.org/2000/svg";
let uidCounter = 0;
export const nextUid = (prefix = "m") => `${prefix}-${(uidCounter = (uidCounter + 1) % 1000000)}`;
export const num = (v, d) => (v !== "" && v != null && Number.isFinite(Number(v)) ? Number(v) : d);
export const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
export const cueTime = (v, d = 0) => Math.max(0, num(v, d));

export function createSvg(tag, attrs = {}, parent = null) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null && v !== false) el.setAttribute(k, String(v));
  if (parent) parent.appendChild(el);
  return el;
}

const charEm = (ch) => /[\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef]/.test(ch) ? 1.02 : /[MW@#%&]/.test(ch) ? 0.82 : /[A-Z]/.test(ch) ? 0.66 : /\s/.test(ch) ? 0.32 : 0.58;
const estimateWidth = (text, size) => [...String(text || "")].reduce((w, ch) => w + charEm(ch), 0) * size;

function withMeasurer(size, opts, fn) {
  const svg = opts?.svg || (opts?.isConnected ? opts : null);
  const fallback = () => fn((s) => estimateWidth(s, size), false);
  if (!svg?.isConnected || typeof document === "undefined" || (document.fonts && document.fonts.status !== "loaded")) return fallback();
  const probe = createSvg("text", {
    x: "-9999", y: "-9999", "aria-hidden": "true",
    style: `font-size:${size}px;font-weight:${opts?.weight ?? 600};font-family:var(${opts?.mono ? "--font-mono" : "--font-sans"})${opts?.tabular ? ";font-variant-numeric:tabular-nums" : ""};visibility:hidden;pointer-events:none`,
  }, svg);
  try {
    probe.textContent = "MW";
    const ref = probe.getComputedTextLength?.();
    if (!Number.isFinite(ref) || ref <= 0 || (document.fonts && document.fonts.status !== "loaded")) return fallback();
    const cache = new Map();
    return fn((str) => {
      const s = String(str || "");
      if (!s) return 0;
      if (!cache.has(s)) {
        probe.textContent = s;
        const len = probe.getComputedTextLength();
        cache.set(s, Number.isFinite(len) && len >= 0 ? len : estimateWidth(s, size));
      }
      return cache.get(s);
    }, true);
  } catch (_) { return fallback(); } finally { probe.remove(); }
}

export const measureTextWidth = (text, size, opts = null) => withMeasurer(size, opts, (m) => m(String(text || "")));

export function wrapLines(text, maxWidth, size, opts = null) {
  const clean = String(text ?? "").replace(/\s+/g, " ").trim();
  if (!clean) return [];
  return withMeasurer(size, opts, (measure, exact) => {
    const limit = exact ? Math.max(12, Math.floor(maxWidth) - 2) : Math.max(size * 1.05, maxWidth * 0.91);
    const tokens = [];
    for (const p of clean.match(/[\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef]|\s+|[^\s\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef]+/g) || []) {
      if (p === " " || measure(p) <= limit) { tokens.push(p); continue; }
      for (const sub of p.match(/[^/\-_.:]+[/\-_.:]*|[/\-_.:]+/g) || [p]) {
        if (measure(sub) <= limit) { tokens.push(sub); continue; }
        let cur = "";
        for (const ch of sub) { if (cur && measure(cur + ch) > limit) { tokens.push(cur); cur = ch; } else cur += ch; }
        if (cur) tokens.push(cur);
      }
    }
    const lines = [];
    let line = "";
    for (const tok of tokens) {
      if (tok === " " && !line) continue;
      const next = line + tok;
      if (line && measure(next.trimEnd()) > limit) { lines.push(line.trimEnd()); line = tok === " " ? "" : tok; }
      else line = next;
    }
    if (line.trim()) lines.push(line.trimEnd());
    return lines;
  });
}

export function fitTextBlock(text, {
  maxWidth, preferredSize = 28, minSize = 26, preferredLines = 2,
  lineHeightRatio = 1.28, svg = null, weight = 600, mono = false, tabular = false,
}) {
  const clean = String(text ?? "").replace(/\s+/g, " ").trim();
  const hi = Math.max(minSize, Math.round(preferredSize)), lo = Math.round(minSize);
  if (!clean) return { fontSize: hi, lines: [], lineHeight: Math.round(hi * lineHeightRatio), height: 0, width: 0 };
  const opts = svg ? { svg, weight, mono, tabular } : null;
  let fontSize = lo, lines = [];
  for (let sz = hi; sz >= lo; sz--) {
    const wrapped = wrapLines(clean, maxWidth, sz, opts);
    if (wrapped.length <= preferredLines || sz === lo) { fontSize = sz; lines = wrapped; break; }
  }
  const lineHeight = Math.round(fontSize * lineHeightRatio);
  const height = (lines.length - 1) * lineHeight + Math.ceil(fontSize * 1.14);
  const width = withMeasurer(fontSize, opts, (m) => Math.max(...lines.map((l) => Math.ceil(m(l)))));
  return { fontSize, lines, lineHeight, height, width };
}

export function appendTextBlock(parent, fit, {
  x, topY, maxWidth, anchor = "start", fill = "var(--c-ink)", weight = 600, ui = false, mono = false, tabular = false,
}) {
  if (!fit?.lines?.length) return null;
  const host = ui ? createSvg("g", { "data-text-role": "ui" }, parent) : parent;
  const textNode = createSvg("text", {
    x: Math.round(x), y: Math.round(topY + fit.fontSize * 0.84), fill, "text-anchor": anchor, ...(ui ? { "data-text-role": "ui" } : {}),
    style: `font-size:${fit.fontSize}px;font-weight:${weight};font-family:var(${mono ? "--font-mono" : "--font-sans"})${tabular ? ";font-variant-numeric:tabular-nums" : ""}`,
  }, host);
  const mw = maxWidth > 0 ? Math.max(12, Math.floor(maxWidth)) : undefined;
  const tspans = fit.lines.map((line, i) => {
    const ts = createSvg("tspan", { x: Math.round(x), y: Math.round(topY + fit.fontSize * 0.84 + i * fit.lineHeight), "data-max-width": mw }, textNode);
    ts.textContent = line;
    return ts;
  });
  return { textNode, tspans };
}

const hasOverflow = (svg) => svg?.isConnected && Array.from(svg.querySelectorAll("tspan[data-max-width]"))
  .some((ts) => (ts.getComputedTextLength?.() || 0) > Number(ts.getAttribute("data-max-width")) + 1);

export const inferDecimals = (v) => (!Number.isFinite(v) || !String(v).includes(".")) ? 0 : Math.min(2, String(v).split(".")[1].length);

const parseSec = (raw, fallback) => {
  const s = String(raw || "").trim(), n = parseFloat(s);
  return Number.isFinite(n) && n > 0 ? (s.endsWith("ms") ? n / 1000 : n) : fallback;
};

export function readThemeTokens(el = typeof document !== "undefined" ? document.documentElement : null) {
  const cs = el && typeof getComputedStyle === "function" ? getComputedStyle(el) : null;
  const get = (k, d = "") => (cs ? cs.getPropertyValue(k).trim() || d : d);
  return {
    canvas: get("--c-canvas", "#f3f1ec"), card: get("--c-card", "#faf9f6"), surface: get("--c-surface", "#efede7"),
    border: get("--c-border", "#d8d4ca"), ink: get("--c-ink", "#222428"), ink2: get("--c-ink2", "#595d64"),
    muted: get("--c-muted", "#8b8f96"), focus: get("--c-focus", "#4f5d95"), focusTint: get("--c-focus-tint", "#eaecf5"),
    info: get("--c-info", "#2d6a9f"), warning: get("--c-warning", "#9a6700"), danger: get("--c-danger", "#c93b3b"),
    positive: get("--c-positive", "#2f7a52"), positiveSolid: get("--c-positive-solid", "#39865c"),
    positiveTint: get("--c-positive-tint", "#e4f1ea"), positiveText: get("--c-positive-text", "#235c3e"),
    highlight: get("--c-highlight", "#b5892e"), done: get("--c-done", "#6b5ca5"),
    chrome: get("--c-chrome", "#25272c"), chromeInk: get("--c-chrome-ink", "#f5f4f0"),
    fontSans: get("--font-sans", "sans-serif"), fontMono: get("--font-mono", "monospace"),
    enterDuration: parseSec(get("--motion-enter-duration"), 0.4),
    easing: get("--motion-easing", "power2.out"),
    listInterval: parseSec(get("--motion-list-interval"), 0.12),
  };
}

export function ensureHatchPattern(defs, id, { color = "var(--c-border)", opacity = 0.22, step = 8, strokeWidth = 1 } = {}) {
  if (!defs) return "none";
  if (!defs.querySelector(`[id="${id}"]`)) {
    const mid = +(step / 2).toFixed(2);
    const pat = createSvg("pattern", { id, width: step, height: step, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
    createSvg("line", { x1: mid, y1: 0, x2: mid, y2: step, stroke: color, "stroke-width": strokeWidth, "stroke-opacity": opacity }, pat);
  }
  return `url(#${id})`;
}

export function ensureAreaGradient(defs, id, { color = "var(--c-focus)", topOpacity = 0.2, bottomOpacity = 0.02, vertical = true } = {}) {
  if (!defs) return color;
  if (!defs.querySelector(`[id="${id}"]`)) {
    const g = createSvg("linearGradient", { id, x1: 0, y1: 0, x2: vertical ? 0 : 1, y2: vertical ? 1 : 0 }, defs);
    createSvg("stop", { offset: "0%", "stop-color": color, "stop-opacity": topOpacity }, g);
    createSvg("stop", { offset: "100%", "stop-color": color, "stop-opacity": bottomOpacity }, g);
  }
  return `url(#${id})`;
}

export function createCanvasHatchPattern(ctx, { color = "#888", alpha = 0.22, step = 8, lineWidth = 1 } = {}) {
  if (!ctx || typeof document === "undefined") return color;
  const tile = document.createElement("canvas"), s = Math.max(4, Math.round(step));
  tile.width = s; tile.height = s;
  const tc = tile.getContext("2d");
  if (!tc) return color;
  tc.save(); tc.globalAlpha = alpha; tc.strokeStyle = color; tc.lineWidth = lineWidth;
  tc.beginPath();
  tc.moveTo(-s * 0.5, s * 0.5); tc.lineTo(s * 0.5, -s * 0.5);
  tc.moveTo(0, s); tc.lineTo(s, 0);
  tc.moveTo(s * 0.5, s * 1.5); tc.lineTo(s * 1.5, s * 0.5);
  tc.stroke(); tc.restore();
  return ctx.createPattern(tile, "repeat") || color;
}

export function appendCraftCard(parent, {
  x, y, width, height, rx = 12,
  fill = "color-mix(in srgb, var(--c-card) 86%, transparent)",
  stroke = "var(--c-border)", strokeWidth = "1.35",
  accent = null, shadow = true,
}) {
  const defaultShadow = "drop-shadow(0 1px 2px rgba(18,22,28,0.045)) drop-shadow(0 5px 12px rgba(18,22,28,0.032))";
  const rect = createSvg("rect", {
    x, y, width, height, rx, fill, stroke, "stroke-width": strokeWidth,
    ...(shadow ? { style: `filter:var(--card-filter, ${defaultShadow})` } : {}),
  }, parent);
  const trim = createSvg("g", { class: "m-card-trim", "data-layout-ignore": "true" }, parent);
  const insetX = Math.max(4, Math.round(rx * 0.85));
  if (width > insetX * 2 + 4) {
    createSvg("line", {
      x1: x + insetX, y1: (y + 1.25).toFixed(2), x2: x + width - insetX, y2: (y + 1.25).toFixed(2),
      stroke: "#ffffff", "stroke-opacity": "0.68", "stroke-width": "1", "stroke-linecap": "round",
    }, trim);
  }
  if (accent && height >= 28) {
    const ay0 = y + Math.min(10, Math.round(height * 0.22)), ay1 = y + height - Math.min(10, Math.round(height * 0.22));
    if (ay1 > ay0 + 4) {
      createSvg("line", {
        x1: (x + 3.5).toFixed(1), y1: ay0, x2: (x + 3.5).toFixed(1), y2: ay1,
        stroke: accent, "stroke-width": "3.5", "stroke-linecap": "round",
      }, trim);
    }
  }
  return { rect, trim };
}

export function appendPortRing(parent, { cx, cy, r = 4, color = "var(--c-focus)", bg = "var(--c-card)", style = null }) {
  const g = createSvg("g", { class: "m-port", "data-layout-ignore": "true", ...(style ? { style } : {}) }, parent);
  createSvg("circle", { cx: Math.round(cx * 10) / 10, cy: Math.round(cy * 10) / 10, r, fill: bg, stroke: color, "stroke-width": "1.35" }, g);
  createSvg("circle", { cx: Math.round(cx * 10) / 10, cy: Math.round(cy * 10) / 10, r: Math.max(1.4, +(r * 0.42).toFixed(2)), fill: color }, g);
  return g;
}

export function formatMetricValue(v, { decimals = 0, prefix = "", suffix = "" } = {}) {
  const n = Number.isFinite(v) ? v : 0;
  const s = decimals > 0 ? n.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) : Math.round(n).toLocaleString("en-US");
  return `${prefix}${s}${suffix}`;
}

export function addProgressTween(tl, { at = 0, duration = 0.5, ease = "power2.out", onUpdate }) {
  const s = { p: 0 }, t0 = Math.max(0, num(at, 0)), dur = Math.max(0.01, num(duration, 0.4));
  if (t0 > 0) tl.fromTo({ p: 0 }, { p: 0 }, { p: 0, duration: 0, ease: "none", onUpdate: () => onUpdate(0) }, 0);
  tl.fromTo(s, { p: 0 }, { p: 1, duration: dur, ease, onUpdate: () => onUpdate(clamp(s.p, 0, 1)) }, t0);
}

export function prepareStage(root, params = {}, gsap, opts = {}, renderFn = opts.build) {
  const { prefix = "m", padX = 28, baseTop = 26, backdrop = true, title = "" } = opts;
  const tl = gsap.timeline({ paused: true });
  let destroyed = false, sought = false, lastTime = 0;
  const rawSeek = tl.seek?.bind(tl);
  if (rawSeek) tl.seek = (t, ...r) => { sought = true; lastTime = Number(t) || 0; return rawSeek(t, ...r); };

  const buildOnce = () => {
    const uid = nextUid(prefix), cs = getComputedStyle(root);
    const rawDur = cs.getPropertyValue("--motion-enter-duration").trim(), pd = parseFloat(rawDur);
    const enterDuration = Number.isFinite(pd) && pd > 0 ? (rawDur.endsWith("ms") ? pd / 1000 : pd) : 0.4;
    const easing = cs.getPropertyValue("--motion-easing").trim() || "power2.out";
    const stageEl = root.querySelector(`#${prefix}-stage`);
    const svg = root.querySelector(`#${prefix}-svg`) || root.querySelector("svg");
    const defs = root.querySelector(`#${prefix}-defs`) || svg?.querySelector("defs");
    svg?.querySelectorAll(":scope > :not(defs)").forEach((n) => n.remove());
    defs?.replaceChildren();

    const host = root.parentElement, x = Math.round(num(params.x, 0)), y = Math.round(num(params.y, 0));
    const W = Math.max(240, Math.round(num(params.width, root.clientWidth || num(host?.dataset?.width, num(root.dataset?.width, 1048)))));
    const H = Math.max(200, Math.round(num(params.height, root.clientHeight || num(host?.dataset?.height, num(root.dataset?.height, 788)))));
    const isPortrait = H > W * 0.95;
    if (stageEl) Object.assign(stageEl.style, { left: `${x}px`, top: `${y}px`, width: `${W}px`, height: `${H}px` });
    if (svg) { svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("width", W); svg.setAttribute("height", H); }

    if (backdrop && svg && defs) {
      const step = backdrop.step || 24, arm = 3.5, veil = Math.round(clamp(num(backdrop.opacity, 0.38), 0, 0.92) * 100);
      const pat = createSvg("pattern", { id: `${uid}-grid`, width: step, height: step, patternUnits: "userSpaceOnUse" }, defs);
      createSvg("path", { d: `M 0 ${step} L 0 0 L ${step} 0`, fill: "none", stroke: "var(--c-border)", "stroke-width": "1", "stroke-opacity": "0.18" }, pat);
      const half = step / 2;
      createSvg("path", { d: `M ${half - arm} ${half} L ${half + arm} ${half} M ${half} ${half - arm} L ${half} ${half + arm}`, fill: "none", stroke: "var(--c-border)", "stroke-width": "1", "stroke-opacity": "0.34" }, pat);
      const rg = createSvg("radialGradient", { id: `${uid}-grid-fade`, cx: "50%", cy: "50%", r: "68%" }, defs);
      createSvg("stop", { offset: "0%", "stop-color": "#ffffff", "stop-opacity": "0.95" }, rg);
      createSvg("stop", { offset: "72%", "stop-color": "#ffffff", "stop-opacity": "0.62" }, rg);
      createSvg("stop", { offset: "100%", "stop-color": "#ffffff", "stop-opacity": "0.14" }, rg);
      const mask = createSvg("mask", { id: `${uid}-grid-mask` }, defs);
      createSvg("rect", { x: 0, y: 0, width: W, height: H, fill: `url(#${uid}-grid-fade)` }, mask);
      const bg = createSvg("g", { class: "m-backdrop" }, svg);
      createSvg("rect", {
        x: 1, y: 1, width: W - 2, height: H - 2, rx: 14,
        fill: veil > 0 ? `color-mix(in srgb, var(--c-card) ${veil}%, transparent)` : "transparent",
        stroke: "var(--c-border)", "stroke-width": "1.25", "stroke-opacity": "0.78",
      }, bg);
      createSvg("rect", { x: 2, y: 2, width: W - 4, height: H - 4, rx: 13, fill: `url(#${uid}-grid)`, mask: `url(#${uid}-grid-mask)` }, bg);
    }

    let contentTop = baseTop;
    const titleStr = String(title || "").trim();
    if (titleStr && svg) {
      const top = Math.max(16, baseTop - 6);
      const fit = fitTextBlock(titleStr, { maxWidth: W - padX * 2, preferredSize: isPortrait ? 30 : 32, minSize: 26, preferredLines: 1, svg, weight: 700 });
      const hg = createSvg("g", { class: `${prefix}-header` }, svg);
      appendTextBlock(hg, fit, { x: padX, topY: top, maxWidth: W - padX * 2, fill: "var(--c-ink)", weight: 700 });
      const dy = top + fit.height + 13;
      createSvg("line", { x1: padX, y1: dy, x2: W - padX, y2: dy, stroke: "var(--c-border)", "stroke-width": "1" }, hg);
      contentTop = dy + 18;
      tl.fromTo(hg, { opacity: 0, y: 8 }, { opacity: 1, y: 0, duration: enterDuration, ease: easing }, 0);
    }
    renderFn?.({ tl, uid, stageEl, svg, defs, x, y, width: W, height: H, isPortrait, enterDuration, easing, padX, contentTop });
    return svg;
  };

  const fonts = typeof document !== "undefined" ? document.fonts : null;
  let wasUnloaded = Boolean(fonts?.ready && fonts.status !== "loaded");
  const svg = buildOnce();
  if (fonts?.ready && fonts.status !== "loaded") wasUnloaded = true;
  const ready = fonts?.ready
    ? Promise.resolve(fonts.ready).then(() => {
        if (destroyed || (!wasUnloaded && !hasOverflow(svg))) return;
        const cur = typeof tl.time === "function" ? Number(tl.time()) || 0 : lastTime;
        rawSeek?.(0, false); tl.clear?.(); buildOnce();
        if (sought || cur > 0) tl.pause().seek(cur, false);
      }).catch(() => {})
    : Promise.resolve();

  return { timeline: tl, ready, destroy() { destroyed = true; tl.kill(); } };
}
export const mountMotion = prepareStage;
