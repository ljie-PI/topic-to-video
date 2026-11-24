// topology-graph.mjs — layered architecture & dependency graph motion module
// (docs: topology-graph.md). Explicit init per modules/modules.md.

import {
  addProgressTween, appendCraftCard, appendPortRing, appendTextBlock, clamp, createSvg,
  cueTime, ensureHatchPattern, fitTextBlock, num, prepareStage,
} from "./motion-utils.mjs";

const EMP = {
  done: ["var(--c-done)", "--c-card", 88, "1.75"], positive: ["var(--c-positive-solid)", "--c-positive-tint", 86, "1.75"],
  warning: ["var(--c-warning)", "--c-card", 88, "1.75"], danger: ["var(--c-danger)", "--c-card", 88, "1.75"],
};
const emphasisStyle = (emp) => {
  if (!emp) return { stroke: "var(--c-ink2)", fill: "color-mix(in srgb, var(--c-card) 86%, transparent)", sw: "1.3" };
  const [stroke, tint, pct, sw] = EMP[String(emp).toLowerCase()] || ["var(--c-focus)", "--c-focus-tint", 88, "1.85"];
  return { stroke, fill: `color-mix(in srgb, var(${tint}) ${pct}%, transparent)`, sw };
};

function normalizeTopology(data) {
  const meta = new Map(), order = [], flat = [];
  const ensure = (id, label = "") => {
    const k = String(id);
    if (!meta.has(k)) { meta.set(k, { id: k, label: label ? String(label) : "" }); order.push(k); }
    else if (label && !meta.get(k).label) meta.get(k).label = String(label);
    return k;
  };
  (Array.isArray(data?.layers) ? data.layers : []).forEach((l, i) => {
    const lid = ensure(l.id ?? `layer-${i}`, l.label || l.title || "");
    (Array.isArray(l.nodes) ? l.nodes : []).forEach((n) => flat.push({ ...n, layer: lid, at: n.at ?? l.at }));
  });
  (Array.isArray(data?.nodes) ? data.nodes : []).forEach((n) => flat.push(n));
  const nodes = flat.map((n, i) => ({
    id: String(n.id ?? `mod-${i + 1}`), index: i, label: String(n.label || `模块 ${i + 1}`), detail: n.detail ? String(n.detail) : "",
    layer: (n.layer ?? n.group) != null ? ensure(n.layer ?? n.group) : null,
    x: Number.isFinite(Number(n.x)) && n.x != null ? Number(n.x) : null,
    y: Number.isFinite(Number(n.y)) && n.y != null ? Number(n.y) : null,
    at: cueTime(n.at, i * 0.35), emphasis: n.emphasis || false,
  }));
  if (!order.length && nodes.length) nodes.forEach((n, i) => { n.layer = ensure(`tier-${Math.floor(i / (nodes.length <= 4 ? 2 : 3))}`); });
  else nodes.forEach((n) => { if (n.layer == null) n.layer = order[0] || ensure("tier-0"); });
  return { layers: order.map((id) => ({ ...meta.get(id), nodes: nodes.filter((n) => n.layer === id) })).filter((l) => l.nodes.length), nodes, links: Array.isArray(data?.links) ? data.links : [], focusSequence: Array.isArray(data?.focusSequence) ? data.focusSequence : [] };
}

const cubicPt = (p0, p1, p2, p3, t) => {
  const u = 1 - t;
  return { x: u ** 3 * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t ** 3 * p3.x, y: u ** 3 * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t ** 3 * p3.y };
};

function linkCurve(a, b) {
  const ax = a.x + a.w / 2, ay = a.y + a.h / 2, bx = b.x + b.w / 2, by = b.y + b.h / 2, r = (v) => Math.round(v * 10) / 10;
  if (Math.abs(by - ay) >= Math.abs(bx - ax) * 0.45) {
    const down = by >= ay, tip = down ? b.y - 1 : b.y + b.h + 1;
    const p0 = { x: ax, y: down ? a.y + a.h : a.y }, p3 = { x: bx, y: down ? b.y - 7 : b.y + b.h + 7 }, my = (p0.y + p3.y) / 2;
    return { d: `M ${r(p0.x)} ${r(p0.y)} C ${r(p0.x)} ${r(my)}, ${r(p3.x)} ${r(my)}, ${r(p3.x)} ${r(p3.y)}`, p0, p1: { x: p0.x, y: my }, p2: { x: p3.x, y: my }, p3, arrowPts: `${bx},${tip} ${bx - 5},${tip + (down ? -8 : 8)} ${bx + 5},${tip + (down ? -8 : 8)}` };
  }
  const right = bx >= ax, tip = right ? b.x - 1 : b.x + b.w + 1;
  const p0 = { x: right ? a.x + a.w : a.x, y: ay }, p3 = { x: right ? b.x - 7 : b.x + b.w + 7, y: by }, mx = (p0.x + p3.x) / 2;
  return { d: `M ${r(p0.x)} ${r(p0.y)} C ${r(mx)} ${r(p0.y)}, ${r(mx)} ${r(p3.y)}, ${r(p3.x)} ${r(p3.y)}`, p0, p1: { x: mx, y: p0.y }, p2: { x: mx, y: p3.y }, p3, arrowPts: `${tip},${by} ${tip + (right ? -8 : 8)},${by - 5} ${tip + (right ? -8 : 8)},${by + 5}` };
}

export function init(root, { params = {}, data = {}, duration = 0, gsap }) {
  return prepareStage(root, params, gsap, {
    prefix: "tg", padX: 26, baseTop: 24, backdrop: { step: 22 }, title: params.title || data?.title || "",
  }, ({ tl, uid, svg, defs, width: W, height: H, isPortrait, enterDuration, easing, padX, contentTop }) => {
    const { layers, nodes, links, focusSequence } = normalizeTopology(data);
    if (!nodes.length) return;
    const bandHatch = ensureHatchPattern(defs, `${uid}-band-hatch`, { opacity: 0.14, step: 10 });
    const bandsLayer = createSvg("g", { class: "tg-bands" }, svg), linksLayer = createSvg("g", { class: "tg-links" }, svg), nodesLayer = createSvg("g", { class: "tg-nodes" }, svg);
    const railW = !isPortrait && W >= 880 && layers.some((l) => Boolean(l.label)) ? 136 : 0;
    const graphX = padX + railW, graphW = W - graphX - padX, availH = H - contentTop - 20, boxes = new Map();
    const fitNode = (n, iw, sz = 27) => {
      const lbl = fitTextBlock(n.label, { maxWidth: iw, preferredSize: sz, minSize: 26, preferredLines: 2, svg, weight: 700 });
      const det = n.detail ? fitTextBlock(n.detail, { maxWidth: iw, preferredSize: 22, minSize: 22, preferredLines: 2, svg, weight: 500 }) : null;
      return { node: n, lbl, det, iw, h: Math.max(66, 26 + lbl.height + (det ? 6 + det.height : 0)) };
    };

    if (nodes.every((n) => n.x != null && n.y != null)) {
      const baseW = clamp(Math.floor(graphW / Math.min(3, Math.max(2, Math.ceil(Math.sqrt(nodes.length)))) - 28), 200, 310);
      nodes.forEach((n) => {
        let w = baseW, m = fitNode(n, w - 32, 27);
        if ((m.lbl.lines.length > 2 || (m.det && m.det.lines.length > 2)) && graphW > w) { w = Math.min(440, graphW); m = fitNode(n, w - 32, 26); }
        const cx = n.x <= 1.05 ? graphX + n.x * graphW : n.x, cy = n.y <= 1.05 ? contentTop + n.y * availH : n.y;
        boxes.set(n.id, { ...m, x: clamp(Math.round(cx - w / 2), graphX, Math.max(graphX, graphX + graphW - w)), y: clamp(Math.round(cy - m.h / 2), contentTop, Math.max(contentTop, H - 16 - m.h)), w });
      });
    } else {
      const maxCols = isPortrait ? 2 : 4, rows = [];
      layers.forEach((layer) => { for (let i = 0; i < layer.nodes.length; i += maxCols) rows.push({ layer, first: i === 0, list: layer.nodes.slice(i, i + maxCols) }); });
      const rowData = rows.map((r) => {
        const cnt = r.list.length, gapX = cnt >= 3 ? 20 : 28, shareW = Math.floor((graphW - (cnt - 1) * gapX) / cnt);
        const colW = cnt === 1 ? Math.min(shareW, Math.max(480, Math.round(graphW * 0.85))) : shareW, iw = Math.max(76, colW - 32);
        const items = r.list.map((n) => fitNode(n, iw, colW >= 260 ? 28 : 26));
        const tag = r.first && railW === 0 && r.layer.label ? fitTextBlock(r.layer.label, { maxWidth: graphW - 24, preferredSize: 22, minSize: 22, preferredLines: 1, svg, weight: 600 }) : null;
        const rail = r.first && railW > 0 && r.layer.label ? fitTextBlock(r.layer.label, { maxWidth: railW - 28, preferredSize: 22, minSize: 22, preferredLines: 2, svg, weight: 600 }) : null;
        const tagH = tag ? Math.max(28, tag.height + 8) : 0, railH = rail ? rail.height + 16 : 0;
        return { ...r, colW, gapX, items, tag, tagH, rail, railH, rowH: Math.max(...items.map((x) => x.h), railH) };
      });
      const sumH = rowData.reduce((s, r) => s + r.rowH + (r.tag ? r.tagH + 5 : 0), 0);
      const gapY = rowData.length > 1 ? clamp(Math.floor((availH - sumH) / (rowData.length - 1)), 12, rowData.length >= 4 ? 28 : 40) : 0;
      let curY = contentTop + Math.max(0, Math.round((availH - (sumH + Math.max(0, rowData.length - 1) * gapY)) / 2));

      rowData.forEach((r) => {
        if (r.tag) {
          const tw = clamp(r.tag.width + 24, 68, graphW), tg = createSvg("g", { class: "tg-layer-tag", "data-text-role": "ui" }, bandsLayer);
          createSvg("rect", { x: graphX, y: curY, width: tw, height: r.tagH, rx: Math.min(14, Math.round(r.tagH / 2)), fill: "var(--c-surface)", stroke: "var(--c-border)", "stroke-width": "1.1" }, tg);
          appendTextBlock(tg, r.tag, { x: graphX + Math.round(tw / 2), topY: curY + Math.round((r.tagH - r.tag.height) / 2), maxWidth: tw - 16, anchor: "middle", fill: "var(--c-ink2)", weight: 600 });
          curY += r.tagH + 5;
        }
        if (r.rail) {
          const py = clamp(Math.round(curY + (r.rowH - r.railH) / 2), contentTop, Math.max(contentTop, H - 12 - r.railH));
          const rg = createSvg("g", { class: "tg-layer-rail", "data-text-role": "ui" }, bandsLayer);
          createSvg("rect", { x: padX, y: py, width: railW - 16, height: r.railH, rx: 10, fill: "color-mix(in srgb, var(--c-surface) 88%, transparent)", stroke: "var(--c-border)", "stroke-width": "1.15" }, rg);
          appendTextBlock(rg, r.rail, { x: padX + Math.round((railW - 16) / 2), topY: py + 8, maxWidth: railW - 28, anchor: "middle", fill: "var(--c-ink2)", weight: 600 });
        }
        createSvg("rect", { x: graphX - 6, y: Math.max(4, curY - 5), width: graphW + 12, height: Math.max(12, Math.min(H - 4, curY + r.rowH + 5) - Math.max(4, curY - 5)), rx: 12, fill: bandHatch, stroke: "var(--c-border)", "stroke-width": "1", "stroke-dasharray": "5 5", opacity: "0.52", "data-layout-ignore": "true" }, bandsLayer);
        const sx = graphX + Math.round((graphW - (r.items.length * r.colW + (r.items.length - 1) * r.gapX)) / 2);
        r.items.forEach((it, ci) => boxes.set(it.node.id, { ...it, x: sx + ci * (r.colW + r.gapX), y: curY, w: r.colW, h: r.rowH }));
        curY += r.rowH + gapY;
      });
    }

    const records = new Map();
    nodes.forEach((node, idx) => {
      const b = boxes.get(node.id), emp = emphasisStyle(node.emphasis);
      const fill = node.emphasis ? emp.fill : "color-mix(in srgb, var(--c-card) 86%, transparent)";
      const stroke = node.emphasis ? emp.stroke : "var(--c-border)", sw = node.emphasis ? "1.7" : "1.35";
      const g = createSvg("g", { class: "tg-node", id: `${uid}-n-${idx}` }, nodesLayer);
      g.style.setProperty("--node-fill", fill); g.style.setProperty("--node-stroke", stroke); g.style.setProperty("--node-sw", sw); g.style.setProperty("--node-title", "var(--c-ink)");
      appendCraftCard(g, { x: b.x, y: b.y, width: b.w, height: b.h, rx: 10, fill: "var(--node-fill)", stroke: "var(--node-stroke)", strokeWidth: "var(--node-sw)", accent: node.emphasis ? "var(--node-stroke)" : null });
      appendPortRing(g, { cx: Math.round(b.x + b.w / 2), cy: b.y, r: 4, color: "var(--node-stroke)" });
      appendPortRing(g, { cx: Math.round(b.x + b.w / 2), cy: b.y + b.h, r: 4, color: "var(--node-stroke)" });
      const th = b.lbl.height + (b.det ? 6 + b.det.height : 0), ty = Math.round(b.y + (b.h - th) / 2);
      appendTextBlock(g, b.lbl, { x: Math.round(b.x + b.w / 2), topY: ty, maxWidth: b.iw, anchor: "middle", fill: "var(--node-title)", weight: 700 });
      if (b.det) appendTextBlock(g, b.det, { x: Math.round(b.x + b.w / 2), topY: ty + b.lbl.height + 6, maxWidth: b.iw, anchor: "middle", fill: "var(--c-ink2)", weight: 500, ui: true });
      if (node.at > 0) { tl.set(g, { opacity: 0, y: 12 }, 0); tl.fromTo(g, { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: enterDuration, ease: easing }, node.at); }
      else tl.set(g, { opacity: 1, y: 0 }, 0);
      records.set(node.id, { node, box: b, group: g, fill });
    });

    const pillMaxW = clamp(Math.round(graphW * 0.34), 132, 260);
    links.forEach((link) => {
      const f = records.get(String(link.from)), t = records.get(String(link.to));
      if (!f || !t) return;
      const c = linkCurve(f.box, t.box), emp = emphasisStyle(link.emphasis || "focus");
      const col = link.emphasis ? emp.stroke : "var(--c-ink2)", sw = link.emphasis ? emp.sw : "1.3";
      const at = cueTime(link.at, Math.max(f.node.at, t.node.at) + 0.08), dur = Math.max(0.28, enterDuration);
      createSvg("path", { d: c.d, fill: "none", stroke: "var(--c-border)", "stroke-width": "1", "stroke-dasharray": "3 4", opacity: "0.45" }, linksLayer);
      const path = createSvg("path", { d: c.d, fill: "none", stroke: col, "stroke-width": sw, "stroke-linecap": "round", pathLength: "1", style: "stroke-dasharray:1;stroke-dashoffset:1;opacity:0" }, linksLayer);
      const arrow = createSvg("polygon", { points: c.arrowPts, fill: col, style: "opacity:0" }, linksLayer);
      const dot = createSvg("circle", { cx: Math.round(c.p0.x), cy: Math.round(c.p0.y), r: "4.5", fill: "var(--c-focus)", style: "opacity:0" }, linksLayer);
      if (at > 0) { tl.set(path, { strokeDashoffset: 1, opacity: 0 }, 0); tl.set(arrow, { opacity: 0 }, 0); tl.set(dot, { opacity: 0 }, 0); }
      tl.fromTo(path, { strokeDashoffset: 1, opacity: 1 }, { strokeDashoffset: 0, opacity: 1, duration: dur, ease: easing }, at);
      tl.fromTo(arrow, { opacity: 0 }, { opacity: 1, duration: 0.14, ease: easing }, at + dur * 0.72);
      addProgressTween(tl, { at, duration: dur, ease: easing, onUpdate: (p) => {
        const pt = cubicPt(c.p0, c.p1, c.p2, c.p3, p);
        dot.setAttribute("cx", pt.x.toFixed(1)); dot.setAttribute("cy", pt.y.toFixed(1));
        dot.style.opacity = p > 0.02 && p < 0.98 ? "1" : "0";
      } });
      const txt = link.label ? String(link.label).trim() : "";
      if (txt) {
        const mid = cubicPt(c.p0, c.p1, c.p2, c.p3, 0.5);
        const fit = fitTextBlock(txt, { maxWidth: pillMaxW - 20, preferredSize: 22, minSize: 22, preferredLines: 1, svg, weight: 600 });
        const pw = clamp(fit.width + 22, 48, pillMaxW), ph = Math.max(28, fit.height + 8);
        const px = clamp(Math.round(mid.x - pw / 2), graphX, Math.max(graphX, W - padX - pw)), py = clamp(Math.round(mid.y - ph / 2), contentTop, Math.max(contentTop, H - 16 - ph));
        const lg = createSvg("g", { class: "tg-link-label", "data-text-role": "ui", style: "opacity:0" }, linksLayer);
        createSvg("rect", { x: px, y: py, width: pw, height: ph, rx: Math.min(14, Math.round(ph / 2)), fill: "color-mix(in srgb, var(--c-card) 94%, transparent)", stroke: "var(--c-border)", "stroke-width": "1.15" }, lg);
        appendTextBlock(lg, fit, { x: px + Math.round(pw / 2), topY: py + Math.round((ph - fit.height) / 2), maxWidth: pw - 14, anchor: "middle", fill: "var(--c-ink2)", weight: 600 });
        if (at > 0) tl.set(lg, { opacity: 0 }, 0);
        tl.fromTo(lg, { opacity: 0 }, { opacity: 1, duration: 0.18, ease: easing }, at + dur * 0.4);
      }
    });

    focusSequence.filter((s) => Array.isArray(s?.nodeIds) && s.nodeIds.length).slice().sort((a, b) => num(a.at, 0) - num(b.at, 0)).forEach((step) => {
      const at = cueTime(step.at, 0), active = new Set(step.nodeIds.map(String));
      records.forEach((rec, id) => {
        if (rec.node.at > at) return;
        tl.set(rec.group, active.has(id)
          ? { opacity: 1, "--node-fill": "color-mix(in srgb, var(--c-focus-tint) 90%, transparent)", "--node-stroke": "var(--c-focus)", "--node-sw": "1.85" }
          : { opacity: 0.56, "--node-fill": rec.fill, "--node-stroke": "var(--c-border)", "--node-sw": "1.35" }, at);
      });
    });
  });
}
