// focus-callout.mjs — focal viewport pan/zoom & non-occluding exterior callouts
// (docs: focus-callout.md). Explicit init per modules/modules.md.

import {
  addProgressTween, appendTextBlock, clamp, createSvg, cueTime,
  fitTextBlock, measureTextWidth, num, prepareStage,
} from "./motion-utils.mjs";

function pickSide(vp, W, H, top, pref) {
  const m = { right: W - (vp.x + vp.w), bottom: H - (vp.y + vp.h), left: vp.x, top: vp.y - top };
  return pref && pref !== "auto" && m[pref] >= 180 ? pref : Object.entries(m).sort((a, b) => b[1] - a[1])[0][0];
}

function bandFor(side, vp, W, H, top, pad, gap) {
  if (side === "left") return { x: pad, y: top, w: Math.max(160, vp.x - pad - gap), h: H - top - pad };
  if (side === "top") return { x: vp.x, y: top, w: vp.w, h: Math.max(110, vp.y - top - gap) };
  if (side === "bottom") return { x: vp.x, y: vp.y + vp.h + gap, w: vp.w, h: Math.max(110, H - pad - (vp.y + vp.h + gap)) };
  return { x: vp.x + vp.w + gap, y: top, w: Math.max(160, W - pad - (vp.x + vp.w + gap)), h: H - top - pad };
}

function extAnchor(side, anchor, vp) {
  const rx = num(anchor?.x, 0.5), ry = num(anchor?.y, 0.5);
  const nx = clamp(rx > 1.05 ? (rx - vp.x) / Math.max(1, vp.w) : rx, 0.08, 0.92);
  const ny = clamp(ry > 1.05 ? (ry - vp.y) / Math.max(1, vp.h) : ry, 0.08, 0.92);
  return side === "left" ? { x: vp.x - 4, y: Math.round(vp.y + ny * vp.h) }
    : side === "top" ? { x: Math.round(vp.x + nx * vp.w), y: vp.y - 4 }
    : side === "bottom" ? { x: Math.round(vp.x + nx * vp.w), y: vp.y + vp.h + 4 }
    : { x: vp.x + vp.w + 4, y: Math.round(vp.y + ny * vp.h) };
}

function normCrop(crop, natW, natH) {
  if (!crop) return { nx: 0, ny: 0, nw: 1, nh: 1 };
  const rx = num(crop.x, 0), ry = num(crop.y, 0), rw = num(crop.w ?? crop.width, 1), rh = num(crop.h ?? crop.height, 1);
  const px = rw > 1.05 || rh > 1.05 || rx > 1.05 || ry > 1.05;
  const nx = clamp(px ? rx / Math.max(1, natW) : rx, 0, 0.92), ny = clamp(px ? ry / Math.max(1, natH) : ry, 0, 0.92);
  return { nx, ny, nw: clamp(px ? rw / Math.max(1, natW) : rw, 0.15, 1 - nx), nh: clamp(px ? rh / Math.max(1, natH) : rh, 0.15, 1 - ny) };
}

const pct = (v) => (clamp(v, 0, 0.95) * 100).toFixed(2);
const viewBoxCss = ({ nx, ny, nw, nh }) => `inset(${pct(ny)}% ${pct(1 - nx - nw)}% ${pct(1 - ny - nh)}% ${pct(nx)}%)`;

function measureStops(stops, cardW, svg) {
  const badgeW = Math.max(46, Math.ceil(measureTextWidth("88", 22, { svg, weight: 700, mono: true, tabular: true })) + 16);
  const badgeTop = cardW < badgeW + 184, padX = 16, padV = 13, detGap = 6;
  const textX = badgeTop ? padX : 16 + badgeW + 12, innerW = Math.max(68, cardW - textX - padX);
  return stops.map((stop) => {
    const lbl = fitTextBlock(stop.label, { maxWidth: innerW, preferredSize: 27, minSize: 26, preferredLines: 2, svg, weight: 700 });
    const det = stop.detail ? fitTextBlock(stop.detail, { maxWidth: innerW, preferredSize: 22, minSize: 22, preferredLines: 2, svg, weight: 500 }) : null;
    const th = lbl.height + (det ? detGap + det.height : 0);
    return { stop, lbl, det, badgeW, badgeTop, padX, detGap, textX, innerW, h: badgeTop ? 48 + th + padV : Math.max(70, padV * 2 + th) };
  });
}

export function init(root, { params = {}, data = {}, duration = 0, gsap }) {
  const hasTarget = Boolean(data?.targetRect && typeof data.targetRect === "object");
  return prepareStage(root, params, gsap, {
    prefix: "fc", padX: 22, baseTop: 22, backdrop: !hasTarget, title: params.title || data?.title || "",
  }, ({ tl, uid, svg, width: W, height: H, isPortrait, enterDuration, easing, padX: pad, contentTop }) => {
    const vpEl = root.querySelector("#fc-viewport"), imgEl = root.querySelector("#fc-img");
    const src = String(params.src || data?.src || "").trim();
    const raw = Array.isArray(data) ? data : Array.isArray(data?.stops) ? data.stops : [];
    const stops = raw.map((s, idx) => ({
      index: idx, crop: s.crop || null, anchor: s.anchor || { x: 0.78, y: 0.25 + (idx * 0.25) % 0.6 },
      label: String(s.label || `重点 ${idx + 1}`), detail: s.detail ? String(s.detail) : "",
      side: s.side ? String(s.side).toLowerCase() : null, at: cueTime(s.at, idx * 1.1),
    }));

    const availW = W - pad * 2, availH = H - contentTop - pad, gap = 40;
    const reqSide = String(params.side || stops[0]?.side || "auto").toLowerCase();
    const side0 = reqSide !== "auto" ? reqSide : isPortrait || W < 760 ? "bottom" : "right";

    let vp;
    if (hasTarget) {
      const tr = data.targetRect, tx = clamp(Math.round(num(tr.x, pad)), 8, W - 120), ty = clamp(Math.round(num(tr.y, contentTop)), contentTop, H - 120);
      vp = { x: tx, y: ty, w: clamp(Math.round(num(tr.width ?? tr.w, availW * 0.58)), 120, W - tx - 8), h: clamp(Math.round(num(tr.height ?? tr.h, availH)), 120, H - ty - 8) };
    } else if (side0 === "left" || side0 === "right") {
      let cw = clamp(Math.round(availW * 0.36), 250, 360);
      const wideW = Math.max(cw, Math.min(Math.round(availW * 0.48), availW - 220 - gap));
      if (stops.length && wideW > cw) {
        const pre = measureStops(stops, cw, svg);
        const sumH = pre.reduce((s, m) => s + m.h, 0) + (pre.length - 1) * 14;
        if (sumH > availH || pre.some((m) => m.lbl.lines.length > 2 || (m.det && m.det.lines.length > 2))) cw = wideW;
      }
      const vw = Math.max(220, availW - cw - gap);
      vp = { x: side0 === "left" ? pad + cw + gap : pad, y: contentTop, w: vw, h: availH };
    } else {
      const pre = stops.length ? measureStops(stops, availW, svg) : [];
      const maxH = pre.length ? Math.max(...pre.map((m) => m.h)) : 168;
      const capH = Math.max(140, availH - 140 - gap);
      const ch = clamp(Math.max(Math.round(availH * 0.34), maxH + 8), Math.min(172, capH), capH);
      const vh = Math.max(140, availH - ch - gap);
      vp = { x: pad, y: side0 === "top" ? contentTop + ch + gap : contentTop, w: availW, h: vh };
    }

    if (src) {
      Object.assign(vpEl.style, { display: "block", left: `${vp.x}px`, top: `${vp.y}px`, width: `${vp.w}px`, height: `${vp.h}px` });
      imgEl.src = src;
      const natW = num(params.intrinsicWidth, vp.w), natH = num(params.intrinsicHeight, vp.h);
      const boxes = stops.map((s) => ({ at: s.at, box: normCrop(s.crop, natW, natH) }));
      const first = boxes[0]?.box || normCrop(null, natW, natH);
      imgEl.style.objectViewBox = viewBoxCss(first);
      if (boxes.length) tl.set(imgEl, { objectViewBox: viewBoxCss(first) }, 0);
      for (let i = 1; i < boxes.length; i++) {
        const a = boxes[i - 1].box, b = boxes[i].box;
        addProgressTween(tl, {
          at: boxes[i].at, duration: Math.max(0.42, enterDuration * 1.3), ease: easing,
          onUpdate: (p) => { imgEl.style.objectViewBox = viewBoxCss({ nx: a.nx + (b.nx - a.nx) * p, ny: a.ny + (b.ny - a.ny) * p, nw: a.nw + (b.nw - a.nw) * p, nh: a.nh + (b.nh - a.nh) * p }); },
        });
      }
    } else {
      vpEl.style.display = "none";
      imgEl.removeAttribute("src");
      createSvg("rect", {
        x: vp.x, y: vp.y, width: vp.w, height: vp.h, rx: 12,
        fill: hasTarget ? "none" : "color-mix(in srgb, var(--c-surface) 45%, transparent)",
        stroke: "var(--c-border)", "stroke-width": "1.5", ...(hasTarget ? { "stroke-dasharray": "6 4" } : {}),
      }, createSvg("g", { class: "fc-target-frame" }, svg));
    }
    if (!stops.length) return;

    const bySide = new Map();
    for (const s of stops) {
      const side = hasTarget ? pickSide(vp, W, H, contentTop, s.side || side0) : side0;
      bySide.set(side, [...(bySide.get(side) || []), s]);
    }
    const leadersLayer = createSvg("g", { class: "fc-leaders" }, svg), cardsLayer = createSvg("g", { class: "fc-cards" }, svg);

    bySide.forEach((list, side) => {
      const band = bandFor(side, vp, W, H, contentTop, pad, hasTarget ? 34 : gap);
      const measured = measureStops(list, band.w, svg), stackGap = 14;
      const stackH = measured.reduce((s, m) => s + m.h, 0) + Math.max(0, measured.length - 1) * stackGap;
      const canStack = (side === "left" || side === "right") && measured.length > 1 && stackH <= band.h;
      let curY = band.y + Math.max(0, Math.round((band.h - stackH) / 2));
      const ordered = measured.slice().sort((a, b) => a.stop.at - b.stop.at || a.stop.index - b.stop.index);

      measured.forEach(({ stop, lbl, det, h, badgeW, badgeTop, padX, detGap, textX, innerW }) => {
        const cy = clamp(canStack ? curY : band.y + Math.max(0, Math.round((band.h - h) / 2)), contentTop, Math.max(contentTop, H - pad - h));
        if (canStack) curY += h + stackGap;
        const box = { x: band.x, y: cy, w: band.w, h }, a = extAnchor(side, stop.anchor, vp);
        const p = side === "left" ? { x: box.x + box.w, y: Math.round(box.y + h / 2) } : side === "top" ? { x: Math.round(box.x + box.w / 2), y: box.y + h } : side === "bottom" ? { x: Math.round(box.x + box.w / 2), y: box.y } : { x: box.x, y: Math.round(box.y + h / 2) };
        const mx = Math.round((a.x + p.x) / 2), my = Math.round((a.y + p.y) / 2);
        const d = side === "left" || side === "right" ? `M ${a.x} ${a.y} L ${mx} ${a.y} L ${mx} ${p.y} L ${p.x} ${p.y}` : `M ${a.x} ${a.y} L ${a.x} ${my} L ${p.x} ${my} L ${p.x} ${p.y}`;

        const lg = createSvg("g", { class: "fc-leader-item" }, leadersLayer);
        const pin = createSvg("circle", { cx: a.x, cy: a.y, r: "4.5", fill: "var(--c-focus)", style: stop.at > 0 ? "opacity:0" : "opacity:1" }, lg);
        const path = createSvg("path", { d, fill: "none", stroke: "var(--c-focus)", "stroke-width": "1.65", "stroke-linecap": "round", "stroke-linejoin": "round", pathLength: "1", style: stop.at > 0 ? "stroke-dasharray:1;stroke-dashoffset:1;opacity:0" : "stroke-dasharray:1;stroke-dashoffset:0;opacity:1" }, lg);

        const cg = createSvg("g", { class: "fc-card", id: `${uid}-c-${stop.index}` }, cardsLayer);
        cg.style.setProperty("--card-fill", "color-mix(in srgb, var(--c-focus-tint) 88%, transparent)");
        cg.style.setProperty("--card-stroke", "var(--c-focus)"); cg.style.setProperty("--card-sw", "1.7");
        createSvg("rect", { x: box.x, y: box.y, width: box.w, height: h, rx: 12, fill: "var(--card-fill)", stroke: "var(--card-stroke)", "stroke-width": "var(--card-sw)" }, cg);

        const bg = createSvg("g", { class: "fc-badge", "data-text-role": "ui" }, cg);
        const bh = badgeTop ? 30 : 32, bx = box.x + (badgeTop ? padX : 16), by = badgeTop ? box.y + 10 : Math.round(box.y + (h - bh) / 2);
        createSvg("rect", { x: bx, y: by, width: badgeW, height: bh, rx: Math.round(bh / 2), fill: "var(--c-surface)", stroke: "var(--card-stroke)", "stroke-width": "1.2" }, bg);
        appendTextBlock(bg, { fontSize: 22, lines: [String(stop.index + 1).padStart(2, "0")], lineHeight: 26, height: 24 }, { x: bx + Math.round(badgeW / 2), topY: by + Math.round((bh - 24) / 2), maxWidth: badgeW - 8, anchor: "middle", fill: "var(--c-focus)", weight: 700, mono: true, tabular: true });

        const tx = box.x + textX, ty = badgeTop ? by + bh + 8 : Math.round(box.y + (h - (lbl.height + (det ? detGap + det.height : 0))) / 2);
        appendTextBlock(cg, lbl, { x: tx, topY: ty, maxWidth: innerW, fill: "var(--c-ink)", weight: 700 });
        if (det) appendTextBlock(cg, det, { x: tx, topY: ty + lbl.height + detGap, maxWidth: innerW, fill: "var(--c-ink2)", weight: 500, ui: true });

        const drawDur = Math.max(0.24, enterDuration * 0.8);
        if (stop.at > 0) {
          tl.set(pin, { opacity: 0 }, 0); tl.set(path, { strokeDashoffset: 1, opacity: 0 }, 0); tl.set(cg, { opacity: 0, y: 10 }, 0);
          tl.fromTo(pin, { opacity: 0 }, { opacity: 1, duration: 0.14, ease: easing }, stop.at);
          tl.fromTo(path, { strokeDashoffset: 1, opacity: 1 }, { strokeDashoffset: 0, opacity: 1, duration: drawDur, ease: easing }, stop.at);
          tl.fromTo(cg, { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: enterDuration, ease: easing }, stop.at + drawDur * 0.35);
        } else tl.set(cg, { opacity: 1, y: 0 }, 0);

        const next = ordered[ordered.findIndex((x) => x.stop.index === stop.index) + 1];
        if (next && next.stop.at > stop.at) {
          if (canStack) {
            tl.set(cg, { "--card-fill": "color-mix(in srgb, var(--c-card) 86%, transparent)", "--card-stroke": "var(--c-done)", "--card-sw": "1.3" }, next.stop.at);
            tl.set(path, { opacity: 0.32 }, next.stop.at); tl.set(pin, { opacity: 0.45 }, next.stop.at);
          } else {
            tl.set(cg, { opacity: 0 }, next.stop.at); tl.set(path, { opacity: 0 }, next.stop.at); tl.set(pin, { opacity: 0 }, next.stop.at);
          }
        }
      });
    });
  });
}
