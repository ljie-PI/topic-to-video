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
      const step = backdrop.step || 24, pat = createSvg("pattern", { id: `${uid}-grid`, width: step, height: step, patternUnits: "userSpaceOnUse" }, defs);
      createSvg("path", { d: `M ${step} 0 L 0 0 0 ${step}`, fill: "none", stroke: "var(--c-border)", "stroke-width": "1", "stroke-opacity": "0.26" }, pat);
      createSvg("circle", { cx: step / 2, cy: step / 2, r: "1", fill: "var(--c-border)", "fill-opacity": "0.28" }, pat);
      const bg = createSvg("g", { class: "m-backdrop" }, svg);
      createSvg("rect", { x: 1, y: 1, width: W - 2, height: H - 2, rx: 14, fill: "color-mix(in srgb, var(--c-card) 82%, transparent)", stroke: "var(--c-border)", "stroke-width": "1.5" }, bg);
      createSvg("rect", { x: 2, y: 2, width: W - 4, height: H - 4, rx: 13, fill: `url(#${uid}-grid)` }, bg);
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
