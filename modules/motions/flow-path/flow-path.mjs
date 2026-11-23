// flow-path.mjs — directed process / timeline / state-machine motion module
// (docs: flow-path.md). Explicit init per modules/modules.md.

import {
  appendCraftCard, appendPortRing, appendTextBlock, clamp, createSvg, cueTime,
  fitTextBlock, measureTextWidth, prepareStage,
} from "./motion-utils.mjs";

function statusStyle(status) {
  const s = String(status || "").toLowerCase();
  if (s === "positive") return { stroke: "var(--c-positive-solid)", fill: "color-mix(in srgb, var(--c-positive-tint) 88%, transparent)", bf: "var(--c-positive-tint)", bs: "var(--c-positive-solid)", bt: "var(--c-positive-text)" };
  if (s === "warning") return { stroke: "var(--c-warning)", fill: "color-mix(in srgb, var(--c-card) 88%, transparent)", bf: "var(--c-surface)", bs: "var(--c-warning)", bt: "var(--c-warning)" };
  if (s === "danger") return { stroke: "var(--c-danger)", fill: "color-mix(in srgb, var(--c-card) 88%, transparent)", bf: "var(--c-surface)", bs: "var(--c-danger)", bt: "var(--c-danger)" };
  if (s === "done") return { stroke: "var(--c-done)", fill: "color-mix(in srgb, var(--c-card) 86%, transparent)", bf: "var(--c-surface)", bs: "var(--c-done)", bt: "var(--c-done)" };
  return { stroke: "var(--c-focus)", fill: "color-mix(in srgb, var(--c-focus-tint) 88%, transparent)", bf: "var(--c-focus-tint)", bs: "var(--c-focus)", bt: "var(--c-focus)" };
}

function connectPorts(a, b) {
  const ax = a.x + a.w / 2, ay = a.y + a.h / 2, bx = b.x + b.w / 2, by = b.y + b.h / 2;
  const dx = bx - ax, dy = by - ay;
  if (Math.abs(dx) >= Math.abs(dy) * 0.9) {
    const dir = dx >= 0 ? 1 : -1;
    const sx = dir > 0 ? a.x + a.w : a.x, sy = Math.round(ay);
    const tx = dir > 0 ? b.x - 7 : b.x + b.w + 7, ty = Math.round(by), mx = Math.round((sx + tx) / 2);
    const d = Math.abs(sy - ty) < 4 ? `M ${sx} ${sy} L ${tx} ${ty}` : `M ${sx} ${sy} C ${mx} ${sy}, ${mx} ${ty}, ${tx} ${ty}`;
    const tip = dir > 0 ? b.x - 1 : b.x + b.w + 1;
    const arrowPts = dir > 0 ? `${tip},${ty} ${tip - 9},${ty - 5} ${tip - 9},${ty + 5}` : `${tip},${ty} ${tip + 9},${ty - 5} ${tip + 9},${ty + 5}`;
    return { d, arrowPts, sx, sy, lx: mx, ly: Math.round((sy + ty) / 2) - 18 };
  }
  const dir = dy >= 0 ? 1 : -1;
  const sx = Math.round(ax), sy = dir > 0 ? a.y + a.h : a.y;
  const tx = Math.round(bx), ty = dir > 0 ? b.y - 7 : b.y + b.h + 7, my = Math.round((sy + ty) / 2);
  const d = Math.abs(sx - tx) < 4 ? `M ${sx} ${sy} L ${tx} ${ty}` : `M ${sx} ${sy} C ${sx} ${my}, ${tx} ${my}, ${tx} ${ty}`;
  const tip = dir > 0 ? b.y - 1 : b.y + b.h + 1;
  const arrowPts = dir > 0 ? `${tx},${tip} ${tx - 5},${tip - 9} ${tx + 5},${tip - 9}` : `${tx},${tip} ${tx - 5},${tip + 9} ${tx + 5},${tip + 9}`;
  return { d, arrowPts, sx, sy, lx: Math.round((sx + tx) / 2), ly: my, vertical: true };
}

export function init(root, { params = {}, data = {}, duration = 0, gsap }) {
  const title = params.title || (!Array.isArray(data) && data?.title) || "";
  return prepareStage(root, params, gsap, { prefix: "fp", padX: 28, baseTop: 26, title }, ({
    tl, uid, svg, width: W, height: H, isPortrait, enterDuration, easing, padX, contentTop,
  }) => {
    const raw = Array.isArray(data) ? data : Array.isArray(data?.nodes) ? data.nodes : [];
    if (!raw.length) return;
    const nodes = raw.map((n, idx) => ({
      id: String(n.id != null ? n.id : `step-${idx + 1}`), index: idx,
      label: String(n.label || `步骤 ${idx + 1}`), detail: n.detail ? String(n.detail) : "",
      at: cueTime(n.at, idx * 0.6), status: n.status || "default",
    }));
    const edges = Array.isArray(data?.edges) && data.edges.length ? data.edges : nodes.slice(0, -1).map((n, i) => ({
      from: n.id, to: nodes[i + 1].id, at: Math.max(n.at, nodes[i + 1].at - Math.min(0.32, enterDuration * 0.85)),
    }));

    const availW = W - padX * 2, pillMaxW = clamp(Math.round(availW * 0.34), 140, 260);
    const edgeFits = edges.map((e) => {
      const t = e?.label ? String(e.label).trim() : "";
      if (!t) return null;
      const fit = fitTextBlock(t, { maxWidth: pillMaxW - 20, preferredSize: 22, minSize: 22, preferredLines: 1, svg, weight: 600 });
      return { fit, w: clamp(fit.width + 24, 52, pillMaxW), h: Math.max(28, fit.height + 10) };
    });
    const maxPillH = Math.max(0, ...edgeFits.map((e) => e?.h || 0));
    const badgeW = Math.max(48, Math.ceil(measureTextWidth("88", 22, { svg, weight: 700, mono: true, tabular: true })) + 16);

    const dir = String(params.direction || "auto").toLowerCase();
    const isVert = dir === "vertical" || (dir === "auto" && (isPortrait || W < 760));
    const N = nodes.length, boxes = [];

    if (isVert) {
      const availH = H - contentTop - 20, boxW = W < 680 ? availW : Math.round(availW * 0.92), boxX = Math.round((W - boxW) / 2);
      const badgeH = 32, textXOff = 16 + badgeW + 14, innerW = Math.max(80, boxW - textXOff - 16), detGap = 6;
      const measured = nodes.map((n) => {
        const lbl = fitTextBlock(n.label, { maxWidth: innerW, preferredSize: 28, minSize: 26, preferredLines: 2, svg, weight: 700 });
        const det = n.detail ? fitTextBlock(n.detail, { maxWidth: innerW, preferredSize: 22, minSize: 22, preferredLines: 2, svg, weight: 500 }) : null;
        return { lbl, det, th: lbl.height + (det ? detGap + det.height : 0) };
      });
      const minGap = maxPillH ? maxPillH + 6 : 10;
      const padV = measured.reduce((s, m) => s + Math.max(72, m.th + 28), 0) + (N - 1) * minGap > availH ? 10 : 14;
      const cards = measured.map((m) => ({ ...m, h: Math.max(58, m.th + padV * 2) }));
      const sumH = cards.reduce((s, c) => s + c.h, 0);
      const gapY = N > 1 ? clamp(Math.floor((availH - sumH) / (N - 1)), minGap, maxPillH ? Math.max(34, maxPillH + 10) : 26) : 0;
      let y = contentTop + Math.max(0, Math.round((availH - (sumH + (N - 1) * gapY)) / 2));
      cards.forEach((c) => {
        boxes.push({ x: boxX, y, w: boxW, h: c.h, vert: true, badgeH, textXOff, innerW, detGap, lbl: c.lbl, det: c.det });
        y += c.h + gapY;
      });
    } else {
      const effTop = contentTop + (maxPillH ? maxPillH + 8 : 0), availH = H - effTop - 20;
      const gapX = N >= 4 ? 26 : 34, rows = N >= 5 || Math.floor((availW - (N - 1) * gapX) / N) < 210 ? 2 : 1;
      const cols = Math.ceil(N / rows), colW = Math.floor((availW - (cols - 1) * gapX) / cols);
      const padSide = 16, badgeH = 30, detGap = 7, innerW = Math.max(76, colW - padSide * 2);
      const measured = nodes.map((n) => {
        const lbl = fitTextBlock(n.label, { maxWidth: innerW, preferredSize: cols <= 3 ? 28 : 26, minSize: 26, preferredLines: 2, svg, weight: 700 });
        const det = n.detail ? fitTextBlock(n.detail, { maxWidth: innerW, preferredSize: 22, minSize: 22, preferredLines: 2, svg, weight: 500 }) : null;
        return { lbl, det, h: Math.max(114, 14 + badgeH + 10 + lbl.height + (det ? detGap + det.height : 0) + 16) };
      });
      const rowH = Array.from({ length: rows }, (_, r) => Math.max(...measured.slice(r * cols, (r + 1) * cols).map((m) => m.h)));
      const sumH = rowH.reduce((a, b) => a + b, 0);
      const rowGap = rows > 1 ? clamp(availH - sumH, maxPillH + 14, 48) : 0;
      let ry = effTop + Math.max(0, Math.round((availH - (sumH + (rows - 1) * rowGap)) / 2));
      for (let r = 0; r < rows; r++) {
        const cnt = Math.min(cols, N - r * cols), sx = Math.round((W - (cnt * colW + (cnt - 1) * gapX)) / 2);
        for (let c = 0; c < cnt; c++) {
          const vc = r % 2 === 1 ? cnt - 1 - c : c, idx = r * cols + c, m = measured[idx];
          boxes[idx] = { x: sx + vc * (colW + gapX), y: ry, w: colW, h: rowH[r], vert: false, padSide, badgeH, innerW, detGap, lbl: m.lbl, det: m.det };
        }
        ry += rowH[r] + rowGap;
      }
    }

    const edgesLayer = createSvg("g", { class: "fp-edges" }, svg), nodesLayer = createSvg("g", { class: "fp-nodes" }, svg), portsLayer = createSvg("g", { class: "fp-ports" }, svg);
    const byId = new Map(), byTime = nodes.slice().sort((a, b) => a.at - b.at || a.index - b.index);

    nodes.forEach((node, idx) => {
      const b = boxes[idx], pal = statusStyle(node.status);
      const g = createSvg("g", { class: "fp-node", id: `${uid}-node-${idx}` }, nodesLayer);
      g.style.setProperty("--node-fill", "color-mix(in srgb, var(--c-card) 87%, transparent)");
      g.style.setProperty("--node-stroke", "var(--c-border)");
      g.style.setProperty("--node-sw", "1.35");
      g.style.setProperty("--node-title", "var(--c-ink)");
      appendCraftCard(g, { x: b.x, y: b.y, width: b.w, height: b.h, rx: 12, fill: "var(--node-fill)", stroke: "var(--node-stroke)", strokeWidth: "var(--node-sw)", accent: "var(--node-stroke)" });

      const bg = createSvg("g", { class: "fp-badge", "data-text-role": "ui" }, g);
      bg.style.setProperty("--badge-fill", "var(--c-surface)");
      bg.style.setProperty("--badge-stroke", "var(--c-border)");
      bg.style.setProperty("--badge-text", "var(--c-ink2)");
      const bx = b.x + 16, by = b.vert ? Math.round(b.y + (b.h - b.badgeH) / 2) : b.y + 14;
      createSvg("rect", { x: bx, y: by, width: badgeW, height: b.badgeH, rx: Math.round(b.badgeH / 2), fill: "var(--badge-fill)", stroke: "var(--badge-stroke)", "stroke-width": "1.25" }, bg);
      appendTextBlock(bg, { fontSize: 22, lines: [String(idx + 1).padStart(2, "0")], lineHeight: 26, height: 24 }, { x: bx + Math.round(badgeW / 2), topY: by + Math.round((b.badgeH - 24) / 2), maxWidth: badgeW - 10, anchor: "middle", fill: "var(--badge-text)", weight: 700, mono: true, tabular: true });

      const tx = b.vert ? b.x + b.textXOff : b.x + b.padSide;
      const th = b.lbl.height + (b.det ? b.detGap + b.det.height : 0);
      const ty = b.vert ? Math.round(b.y + (b.h - th) / 2) : by + b.badgeH + 10;
      appendTextBlock(g, b.lbl, { x: tx, topY: ty, maxWidth: b.innerW, fill: "var(--node-title)", weight: 700 });
      if (b.det) appendTextBlock(g, b.det, { x: tx, topY: ty + b.lbl.height + b.detGap, maxWidth: b.innerW, fill: "var(--c-ink2)", weight: 500, ui: true });

      if (node.at > 0) {
        tl.set(g, { opacity: 0, y: 12 }, 0);
        tl.fromTo(g, { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: enterDuration, ease: easing }, node.at);
      } else tl.set(g, { opacity: 1, y: 0 }, 0);
      tl.set(g, { "--node-fill": pal.fill, "--node-stroke": pal.stroke, "--node-sw": "1.75", "--node-title": "var(--c-ink)" }, node.at);
      tl.set(bg, { "--badge-fill": pal.bf, "--badge-stroke": pal.bs, "--badge-text": pal.bt }, node.at);

      const next = byTime[byTime.findIndex((n) => n.id === node.id) + 1];
      if (next && node.status === "default" && next.at > node.at) {
        tl.set(g, {
          "--node-fill": "color-mix(in srgb, var(--c-surface) 74%, transparent)",
          "--node-stroke": "var(--c-done)",
          "--node-sw": "1.2", "--node-title": "var(--c-ink2)", "--card-filter": "none",
        }, next.at);
        tl.set(bg, { "--badge-fill": "var(--c-surface)", "--badge-stroke": "var(--c-done)", "--badge-text": "var(--c-done)" }, next.at);
      }
      byId.set(node.id, { node, box: b });
    });

    edges.forEach((edge, idx) => {
      const f = byId.get(String(edge.from)), t = byId.get(String(edge.to));
      if (!f || !t) return;
      const g = connectPorts(f.box, t.box), at = cueTime(edge.at, Math.max(f.node.at, t.node.at - 0.25)), dur = Math.max(0.24, enterDuration * 0.9);
      createSvg("path", { d: g.d, fill: "none", stroke: "var(--c-border)", "stroke-width": "1.15", "stroke-dasharray": "4 4", opacity: "0.55" }, edgesLayer);
      const path = createSvg("path", { d: g.d, fill: "none", stroke: "var(--c-focus)", "stroke-width": "1.75", "stroke-linecap": "round", pathLength: "1", style: "stroke-dasharray:1;stroke-dashoffset:1;opacity:0" }, edgesLayer);
      const port = appendPortRing(portsLayer, { cx: g.sx, cy: g.sy, r: 4, color: "var(--c-focus)", style: "opacity:0" });
      const arrow = createSvg("polygon", { points: g.arrowPts, fill: "var(--c-focus)", style: "opacity:0" }, edgesLayer);
      if (at > 0) { tl.set(path, { strokeDashoffset: 1, opacity: 0 }, 0); tl.set(port, { opacity: 0 }, 0); tl.set(arrow, { opacity: 0 }, 0); }
      tl.fromTo(port, { opacity: 0 }, { opacity: 1, duration: 0.14, ease: easing }, at);
      tl.fromTo(path, { strokeDashoffset: 1, opacity: 1 }, { strokeDashoffset: 0, opacity: 1, duration: dur, ease: easing }, at);
      tl.fromTo(arrow, { opacity: 0 }, { opacity: 1, duration: Math.max(0.12, dur * 0.35), ease: easing }, at + dur * 0.65);

      const info = edgeFits[idx];
      if (info) {
        const sameRow = !f.box.vert && Math.abs(f.box.y - t.box.y) < 16;
        const px = clamp(g.vertical ? g.lx + 14 : Math.round(g.lx - info.w / 2), 12, Math.max(12, W - info.w - 12));
        const py = clamp(sameRow ? Math.min(f.box.y, t.box.y) - info.h - 6 : Math.round(g.ly - info.h / 2), contentTop, Math.max(contentTop, H - info.h - 12));
        const pg = createSvg("g", { class: "fp-edge-label", "data-text-role": "ui", style: "opacity:0" }, edgesLayer);
        createSvg("rect", { x: px, y: py, width: info.w, height: info.h, rx: Math.min(16, Math.round(info.h / 2)), fill: "color-mix(in srgb, var(--c-card) 92%, transparent)", stroke: "var(--c-border)", "stroke-width": "1.2" }, pg);
        appendTextBlock(pg, info.fit, { x: px + Math.round(info.w / 2), topY: py + Math.round((info.h - info.fit.height) / 2), maxWidth: info.w - 16, anchor: "middle", fill: "var(--c-ink2)", weight: 600 });
        if (at > 0) tl.set(pg, { opacity: 0 }, 0);
        tl.fromTo(pg, { opacity: 0 }, { opacity: 1, duration: 0.2, ease: easing }, at + dur * 0.35);
      }
    });
  });
}
