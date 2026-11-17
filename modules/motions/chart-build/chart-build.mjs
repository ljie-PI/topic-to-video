// chart-build.mjs — quantitative bar / line-area / hero-metric motion module (docs: chart-build.md).
import { addProgressTween, appendTextBlock, clamp, createSvg, cueTime, fitTextBlock, formatMetricValue, inferDecimals, measureTextWidth, num, prepareStage } from "./motion-utils.mjs";

const niceMax = (v) => {
  if (!Number.isFinite(v) || v <= 0) return 100;
  const e = 10 ** Math.floor(Math.log10(v)), f = v / e;
  return Math.max(v * 1.06, (f <= 1.2 ? 1.2 : f <= 1.5 ? 1.5 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * e);
};

function normSeries(data) {
  const list = Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : Array.isArray(data?.points) ? data.points : data?.value != null ? [data] : [];
  return list.map((it, i) => {
    const v = num(it.value, 0);
    return { index: i, label: String(it.label || `项 ${i + 1}`), detail: it.detail ? String(it.detail) : "", value: v, decimals: it.decimals != null ? Number(it.decimals) : inferDecimals(v), displayValue: it.displayValue != null ? String(it.displayValue) : null, at: cueTime(it.at, i * 0.45), emphasis: it.emphasis || false };
  });
}

function drawAxisGrid(svg, plotX, plotW, topY, plotBottom, maxVal, horiz = false, yAxisW = 74, unit = "") {
  const g = createSvg("g", { class: "cb-grid", "data-text-role": "ui" }, svg), plotH = plotBottom - topY;
  for (let t = 0; t <= 4; t++) {
    const r = t / 4, pos = Math.round(horiz ? plotX + plotW * r : plotBottom - plotH * r);
    createSvg("line", { x1: horiz ? pos : plotX, y1: horiz ? topY : pos, x2: horiz ? pos : plotX + plotW, y2: horiz ? plotBottom : pos, stroke: "var(--c-border)", "stroke-width": t === 0 ? "1.25" : "1", ...(t > 0 ? { "stroke-dasharray": "4 4", opacity: "0.65" } : {}) }, g);
    const lbl = formatMetricValue(maxVal * r, { decimals: maxVal < 10 ? 1 : 0, suffix: horiz && t === 4 ? unit : "" });
    appendTextBlock(g, { fontSize: 22, lines: [lbl], lineHeight: 26, height: 24 }, { x: horiz ? pos : plotX - 12, topY: horiz ? plotBottom + 10 : pos - 12, maxWidth: horiz ? Math.floor(plotW / 4) + 24 : yAxisW - 14, anchor: horiz ? (t === 0 ? "start" : t === 4 ? "end" : "middle") : "end", fill: "var(--c-ink2)", weight: 500, mono: true, tabular: true });
  }
  return g;
}

const barColors = (emp) => String(emp).toLowerCase() === "positive" ? { stroke: "var(--c-positive-solid)", fill: "color-mix(in srgb, var(--c-positive-tint) 90%, transparent)", val: "var(--c-positive)" }
  : emp ? { stroke: "var(--c-focus)", fill: "color-mix(in srgb, var(--c-focus) 82%, transparent)", val: "var(--c-focus)" }
  : { stroke: "var(--c-border)", fill: "color-mix(in srgb, var(--c-surface) 92%, transparent)", val: "var(--c-ink)" };

const numNode = (parent, x, y, size, weight, fill, anchor = "start", maxW) => {
  const text = createSvg("text", { x, y, fill, ...(anchor !== "start" ? { "text-anchor": anchor } : {}), style: `font-size:${size}px;font-weight:${weight};font-family:var(--font-sans);font-variant-numeric:tabular-nums` }, parent);
  return { text, tspan: createSvg("tspan", { x, y, ...(maxW ? { "data-max-width": Math.floor(maxW) } : {}) }, text) };
};

export function init(root, { params = {}, data = {}, duration = 0, gsap }) {
  const variant = String(params.variant || data?.variant || "bar").toLowerCase(), title = params.title || (variant !== "metric" && data?.title) || "";
  return prepareStage(root, params, gsap, { prefix: "cb", padX: 28, baseTop: 26, title }, ({ tl, uid, svg, defs, width: W, height: H, isPortrait, enterDuration, easing, padX, contentTop }) => {
    const series = normSeries(data), prefix = params.prefix != null ? String(params.prefix) : "", unit = params.unit != null ? String(params.unit) : data?.unit ? String(data.unit) : "";
    const fmt = (v, dec, suf = unit) => formatMetricValue(v, { decimals: dec, prefix, suffix: suf });
    const stepText = (it, p, suf = unit) => p >= 0.995 && it.displayValue != null ? it.displayValue : fmt(it.value * p, it.decimals, suf);
    const fadeIn = (el, at, dur = 0.2, y = 0) => { if (at > 0) { tl.set(el, y ? { opacity: 0, y } : { opacity: 0 }, 0); tl.fromTo(el, y ? { opacity: 0, y } : { opacity: 0 }, y ? { opacity: 1, y: 0, duration: dur, ease: easing } : { opacity: 1, duration: dur, ease: easing }, at); } };
    const summary = data && !Array.isArray(data) && data.summary ? String(data.summary).trim() : "";
    let summaryH = 0;
    if (summary) {
      const iw = W - padX * 2 - 40, fit = fitTextBlock(summary, { maxWidth: iw, preferredSize: 26, minSize: 26, preferredLines: 2, svg, weight: 500 });
      const bh = fit.height + 24, by = H - 20 - bh, sg = createSvg("g", { class: "cb-summary" }, svg);
      createSvg("rect", { x: padX, y: by, width: W - padX * 2, height: bh, rx: 10, fill: "color-mix(in srgb, var(--c-surface) 88%, transparent)", stroke: "var(--c-border)", "stroke-width": "1.25" }, sg);
      createSvg("rect", { x: padX, y: by, width: 5, height: bh, rx: 2.5, fill: "var(--c-focus)" }, sg);
      appendTextBlock(sg, fit, { x: padX + 22, topY: by + 12, maxWidth: iw, fill: "var(--c-ink)", weight: 500 });
      fadeIn(sg, cueTime(data?.summaryAt, (series.length ? Math.max(...series.map((s) => s.at)) : 0) + Math.max(0.4, enterDuration)), enterDuration, 10);
      summaryH = bh + 16;
    }
    const availW = W - padX * 2, availH = Math.max(180, H - contentTop - 20 - summaryH);
    if (variant === "metric") {
      const hero = series[0] || { label: String(data?.label || title || "核心指标"), detail: String(data?.detail || ""), value: num(data?.value, 0), decimals: inferDecimals(num(data?.value, 0)), displayValue: data?.displayValue ?? null, at: cueTime(data?.at, 0.1), emphasis: data?.emphasis || "focus" };
      const suf = unit ? ` ${unit}` : "", finalStr = hero.displayValue ?? fmt(hero.value, hero.decimals, suf);
      let cw = Math.min(availW, isPortrait ? availW : 880), cpx = 28, iw = cw - cpx * 2;
      const fitPair = (sz) => [fitTextBlock(hero.label, { maxWidth: iw, preferredSize: sz, minSize: 26, preferredLines: 2, svg, weight: 600 }), hero.detail ? fitTextBlock(hero.detail, { maxWidth: iw, preferredSize: 26, minSize: 26, preferredLines: 2, svg, weight: 500 }) : null];
      let [lbl, det] = fitPair(isPortrait ? 30 : 32);
      if ((lbl.lines.length > 2 || (det && det.lines.length > 2)) && availW > cw) { cw = availW; iw = cw - cpx * 2; [lbl, det] = fitPair(28); }
      let nf = isPortrait ? 100 : 120;
      while (nf > 36 && measureTextWidth(finalStr, nf, { svg, weight: 800, tabular: true }) > iw * 0.92) nf -= 2;
      const blockH = () => lbl.height + 16 + Math.round(nf * 1.06) + 28 + (det ? 16 + det.height : 0);
      while (nf > 44 && blockH() + 32 > availH) nf -= 2;
      const bh = blockH(), ch = Math.max(bh + 32, Math.min(clamp(availH - 16, 220, 460), availH)), cx = Math.round((W - cw) / 2), cy = contentTop + Math.max(0, Math.round((availH - ch) / 2));
      const cg = createSvg("g", { class: "cb-metric-card" }, svg);
      createSvg("rect", { x: cx, y: cy, width: cw, height: ch, rx: 16, fill: "color-mix(in srgb, var(--c-card) 88%, transparent)", stroke: "var(--c-border)", "stroke-width": "1.5" }, cg);
      let y = cy + Math.max(16, Math.round((ch - bh) / 2));
      appendTextBlock(cg, lbl, { x: cx + cpx, topY: y, maxWidth: iw, fill: "var(--c-ink2)", weight: 600 }); y += lbl.height + 16;
      const col = String(hero.emphasis).toLowerCase() === "positive" ? "var(--c-positive)" : "var(--c-focus)";
      const { tspan: nts } = numNode(cg, cx + cpx, Math.round(y + nf * 0.84), nf, 800, col, "start", iw);
      nts.textContent = fmt(0, hero.decimals, suf); y += Math.round(nf * 1.06) + 18;
      createSvg("rect", { x: cx + cpx, y, width: iw, height: 10, rx: 5, fill: "var(--c-surface)", stroke: "var(--c-border)", "stroke-width": "1" }, cg);
      const ref = num(data?.maxValue, hero.value > 0 && hero.value <= 100 && unit === "%" ? 100 : hero.value || 1), ratio = clamp(ref > 0 ? hero.value / ref : 1, 0.12, 1);
      const gf = createSvg("rect", { x: cx + cpx, y, width: 0, height: 10, rx: 5, fill: col }, cg);
      if (det) appendTextBlock(cg, det, { x: cx + cpx, topY: y + 26, maxWidth: iw, fill: "var(--c-ink2)", weight: 500 });
      fadeIn(cg, hero.at, enterDuration, 14);
      addProgressTween(tl, { at: hero.at, duration: Math.max(0.75, enterDuration * 2.2), ease: "power2.out", onUpdate: (p) => { nts.textContent = stepText(hero, p, suf); gf.setAttribute("width", Math.round(iw * ratio * p)); } });
      return;
    }
    if (!series.length) return;
    const N = series.length, maxVal = num(data?.maxValue, niceMax(Math.max(...series.map((s) => Math.abs(s.value)), 1)));
    const yAxisW = Math.max(74, Math.ceil(measureTextWidth(formatMetricValue(maxVal, { decimals: maxVal < 10 ? 1 : 0 }), 22, { svg, weight: 500, mono: true, tabular: true })) + 22);
    if (variant === "line") {
      const plotX = padX + yAxisW, plotW = Math.max(160, availW - yAxisW - 20), suf = unit ? ` ${unit}` : "";
      const valW = Math.max(96, ...series.map((s) => Math.ceil(measureTextWidth(s.displayValue ?? fmt(s.value, s.decimals, suf), 28, { svg, weight: 800, tabular: true })) + 24));
      const rFits = series.map((s) => fitTextBlock(s.label, { maxWidth: Math.max(80, availW - valW - 52), preferredSize: 22, minSize: 22, preferredLines: 1, svg, weight: 600 }));
      const rw = clamp(Math.max(60, ...rFits.map((f) => f.width)) + valW + 52, Math.min(340, availW), availW), rh = Math.max(44, Math.max(25, ...rFits.map((f) => f.height)) + 18);
      const stride = N > 6 ? Math.ceil(N / 5) : 1, ticks = series.map((_, i) => i).filter((i) => i % stride === 0 || i === N - 1), stepPx = ticks.length > 1 ? Math.floor(plotW / (ticks.length - 1)) : plotW;
      const tickMaxW = (i) => ticks.length === 1 ? plotW : (i === 0 || i === N - 1) ? Math.max(72, Math.floor(stepPx * 0.56)) : Math.max(72, stepPx - 14);
      const xFits = new Map(ticks.map((i) => [i, fitTextBlock(series[i].label, { maxWidth: tickMaxW(i), preferredSize: 22, minSize: 22, preferredLines: 1, svg, weight: 600 })]));
      const xBandH = Math.max(58, Math.max(26, ...Array.from(xFits.values()).map((f) => f.height)) + 20), plotTop = contentTop + rh + 12, plotH = Math.max(120, availH - rh - 12 - xBandH), plotBottom = plotTop + plotH;
      const rg = createSvg("g", { class: "cb-readout" }, svg), rx = W - padX - rw, ry = contentTop;
      createSvg("rect", { x: rx, y: ry, width: rw, height: rh, rx: Math.min(22, Math.round(rh / 2)), fill: "color-mix(in srgb, var(--c-focus-tint) 88%, transparent)", stroke: "var(--c-focus)", "stroke-width": "1.35" }, rg);
      const rlEl = createSvg("text", { x: rx + 20, y: ry + 29, fill: "var(--c-ink2)", "data-text-role": "ui", style: "font-size:22px;font-weight:600;font-family:var(--font-sans)" }, createSvg("g", { "data-text-role": "ui" }, rg));
      const rlMax = Math.max(80, rw - valW - 44), setRl = (fit) => {
        rlEl.replaceChildren(); const ty = ry + Math.round((rh - fit.height) / 2);
        fit.lines.forEach((l, li) => { const ts = createSvg("tspan", { x: rx + 20, y: Math.round(ty + fit.fontSize * 0.84 + li * fit.lineHeight), "data-max-width": Math.floor(rlMax) }, rlEl); ts.textContent = l; });
      };
      let curIdx = 0; setRl(rFits[0]);
      const { tspan: rvTs } = numNode(rg, rx + rw - 20, ry + Math.round(rh / 2 + 9), 28, 800, "var(--c-focus)", "end");
      rvTs.textContent = fmt(series[0].value, series[0].decimals, suf);
      const grid = drawAxisGrid(svg, plotX, plotW, plotTop, plotBottom, maxVal, false, yAxisW);
      const pts = series.map((it, i) => ({ ...it, px: Math.round((N === 1 ? plotX + plotW / 2 : plotX + (i / (N - 1)) * plotW) * 10) / 10, py: Math.round((plotBottom - clamp(it.value / maxVal, 0, 1) * plotH) * 10) / 10 }));
      const grad = createSvg("linearGradient", { id: `${uid}-grad`, x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
      createSvg("stop", { offset: "0%", "stop-color": "var(--c-focus)", "stop-opacity": "0.22" }, grad); createSvg("stop", { offset: "100%", "stop-color": "var(--c-focus)", "stop-opacity": "0.02" }, grad);
      const clipRect = createSvg("rect", { x: plotX - 2, y: plotTop - 16, width: 0, height: plotH + 24 }, createSvg("clipPath", { id: `${uid}-clip` }, defs));
      const d = pts.map((p, i) => `${i ? "L" : "M"} ${p.px} ${p.py}`).join(" "), sl = createSvg("g", { class: "cb-line-series" }, svg);
      createSvg("path", { d: `${d} L ${pts[N - 1].px} ${plotBottom} L ${pts[0].px} ${plotBottom} Z`, fill: `url(#${uid}-grad)`, "clip-path": `url(#${uid}-clip)` }, sl);
      const curve = createSvg("path", { d, fill: "none", stroke: "var(--c-focus)", "stroke-width": "2", "stroke-linecap": "round", "stroke-linejoin": "round", pathLength: "1", style: "stroke-dasharray:1;stroke-dashoffset:1" }, sl);
      pts.forEach((pt, i) => {
        if (xFits.has(i)) appendTextBlock(grid, xFits.get(i), { x: pt.px, topY: plotBottom + 12, maxWidth: tickMaxW(i), anchor: i === 0 ? "start" : i === N - 1 ? "end" : "middle", fill: "var(--c-ink2)", weight: 600 });
        const dg = createSvg("g", { class: "cb-point", style: "opacity:0" }, sl);
        if (pt.emphasis) createSvg("circle", { cx: pt.px, cy: pt.py, r: 11, fill: "var(--c-focus-tint)", stroke: "var(--c-highlight)", "stroke-width": "1.4" }, dg);
        createSvg("circle", { cx: pt.px, cy: pt.py, r: pt.emphasis ? 6 : 5, fill: "var(--c-card)", stroke: "var(--c-focus)", "stroke-width": "2" }, dg);
        fadeIn(dg, pt.at);
      });
      const t0 = pts[0].at, dur = Math.max(0.65, pts[N - 1].at - t0 + enterDuration);
      if (t0 > 0) tl.set(curve, { strokeDashoffset: 1 }, 0);
      fadeIn(rg, t0, 0.22); tl.fromTo(curve, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: dur, ease: "none" }, t0);
      addProgressTween(tl, { at: t0, duration: dur, ease: "none", onUpdate: (p) => {
        clipRect.setAttribute("width", Math.round((plotW + 8) * p));
        const ex = p * (N - 1), lo = clamp(Math.floor(ex), 0, N - 1), hi = clamp(Math.ceil(ex), 0, N - 1), fr = ex - lo, ai = fr > 0.5 ? hi : lo;
        if (ai !== curIdx) { curIdx = ai; setRl(rFits[ai]); }
        rvTs.textContent = p >= 0.995 && pts[N - 1].displayValue != null ? pts[N - 1].displayValue : fmt(pts[lo].value + (pts[hi].value - pts[lo].value) * fr, pts[ai].decimals, suf);
      } });
      return;
    }
    const orient = String(params.orientation || "auto").toLowerCase();
    const useHoriz = orient === "horizontal" || (orient === "auto" && (isPortrait || N >= 5 || series.some((s) => measureTextWidth(s.label, 26, { svg, weight: 700 }) > Math.floor((availW - 88) / N) - 18)));
    if (useHoriz) {
      const valW = clamp(Math.max(130, ...series.map((s) => Math.ceil(measureTextWidth(s.displayValue ?? fmt(s.value, s.decimals), 27, { svg, weight: 700, tabular: true })) + 26)), 130, Math.round(availW * 0.32)), maxPlotH = Math.max(120, availH - 38);
      let lw = clamp(Math.round(availW * (isPortrait ? 0.36 : 0.32)), 185, 320);
      let fits = series.map((s) => fitTextBlock(s.label, { maxWidth: lw - 8, preferredSize: 27, minSize: 26, preferredLines: 2, svg, weight: 700 }));
      const wideLw = Math.max(lw, Math.min(Math.round(availW * 0.56), availW - valW - 132));
      if ((fits.some((f) => f.lines.length > 2) || fits.reduce((s, f) => s + Math.max(36, f.height + 10), 0) > maxPlotH) && wideLw > lw) { lw = wideLw; fits = series.map((s) => fitTextBlock(s.label, { maxWidth: lw - 8, preferredSize: 26, minSize: 26, preferredLines: 2, lineHeightRatio: 1.22, svg, weight: 700 })); }
      const rawH = fits.map((f) => Math.max(34, f.height + 8)), minH = rawH.reduce((a, b) => a + b, 0), plotH = Math.max(minH, maxPlotH);
      const plotX = padX + lw + 18, plotW = Math.max(120, availW - lw - 18 - valW), plotBottom = Math.round(contentTop + plotH);
      drawAxisGrid(svg, plotX, plotW, contentTop, plotBottom, maxVal, true, yAxisW, unit);
      const bars = createSvg("g", { class: "cb-bars" }, svg);
      let sy = contentTop;
      series.forEach((it, i) => {
        const sh = rawH[i] + (plotH - minH) / N, cy = Math.round(sy + sh / 2), bh = clamp(Math.round(sh * 0.52), 26, 54), c = barColors(it.emphasis); sy += sh;
        const rg = createSvg("g", { class: "cb-bar-row" }, bars), tw = Math.max(6, Math.round((Math.max(0, it.value) / maxVal) * plotW));
        appendTextBlock(rg, fits[i], { x: padX + lw, topY: Math.round(cy - fits[i].height / 2), maxWidth: lw - 8, anchor: "end", fill: it.emphasis ? "var(--c-ink)" : "var(--c-ink2)", weight: it.emphasis ? 700 : 600 });
        const br = createSvg("rect", { x: plotX, y: Math.round(cy - bh / 2), width: 0, height: bh, rx: 7, fill: c.fill, stroke: c.stroke, "stroke-width": it.emphasis ? "1.6" : "1.35" }, createSvg("g", { class: "cb-bar-shape" }, rg));
        const { tspan: vts } = numNode(rg, plotX + plotW + 16, Math.round(cy + 9), 27, 700, c.val);
        vts.textContent = fmt(0, it.decimals); fadeIn(rg, it.at);
        addProgressTween(tl, { at: it.at, duration: Math.max(0.45, enterDuration * 1.4), ease: easing, onUpdate: (p) => { br.setAttribute("width", Math.round(tw * p)); vts.textContent = stepText(it, p); } });
      });
    } else {
      const plotX = padX + yAxisW, plotW = availW - yAxisW - 12, slotW = Math.floor(plotW / N);
      const fits = series.map((it) => fitTextBlock(it.label, { maxWidth: Math.max(56, slotW - 14), preferredSize: 26, minSize: 26, preferredLines: 2, svg, weight: 700 }));
      const xBandH = Math.max(68, Math.max(48, ...fits.map((f) => f.height)) + 20), plotTop = contentTop + 42, plotH = Math.max(120, availH - 42 - xBandH), plotBottom = plotTop + plotH;
      drawAxisGrid(svg, plotX, plotW, plotTop, plotBottom, maxVal, false, yAxisW);
      const bars = createSvg("g", { class: "cb-bars" }, svg), barW = clamp(Math.round(slotW * 0.52), 38, 108);
      series.forEach((it, i) => {
        const cx = Math.round(plotX + i * slotW + slotW / 2), th = Math.max(6, Math.round((Math.max(0, it.value) / maxVal) * plotH)), c = barColors(it.emphasis);
        const cg = createSvg("g", { class: "cb-bar-col" }, bars);
        const br = createSvg("rect", { x: Math.round(cx - barW / 2), y: plotBottom, width: barW, height: 0, rx: 8, fill: c.fill, stroke: c.stroke, "stroke-width": it.emphasis ? "1.65" : "1.35" }, createSvg("g", { class: "cb-bar-shape" }, cg));
        const { text: vt, tspan: vts } = numNode(cg, cx, plotBottom - 12, 26, 700, c.val, "middle");
        vts.textContent = fmt(0, it.decimals); fadeIn(cg, it.at);
        appendTextBlock(cg, fits[i], { x: cx, topY: plotBottom + 12, maxWidth: Math.max(56, slotW - 14), anchor: "middle", fill: it.emphasis ? "var(--c-ink)" : "var(--c-ink2)", weight: it.emphasis ? 700 : 500 });
        addProgressTween(tl, { at: it.at, duration: Math.max(0.45, enterDuration * 1.4), ease: easing, onUpdate: (p) => {
          const h = Math.round(th * p), vy = Math.max(contentTop + 26, plotBottom - h - 12);
          br.setAttribute("y", plotBottom - h); br.setAttribute("height", h); vt.setAttribute("y", vy); vts.setAttribute("y", vy); vts.textContent = stepText(it, p);
        } });
      });
    }
  });
}
