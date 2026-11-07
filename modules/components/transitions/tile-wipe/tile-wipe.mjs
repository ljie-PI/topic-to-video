// tile-wipe — a transition between scenes (docs: tile-wipe.md). Square tiles
// light up outward from a point, cover the frame at the cut, optionally show a
// card for what comes next, then drain back to the point.
//
// Explicit init per modules/modules.md: the caller passes the root element,
// mount params, data, slot duration and GSAP; this module never reads
// HyperFrames globals, never infers params from a host, and never registers
// timelines globally. The caller owns the returned timeline.
//
//   init(root, { params, data, duration, gsap })
//     params: { originX, originY, cardX, cardY, top, bottom }
//     data:   [{ at, label, title, emphasis, meta: [{ dot, strong, text }] }]
//             — "at" is the cut in local seconds
//     All times are local seconds: 0 = the mount's start, i.e. video seconds
//     for a full-length transition layer mounted at data-start="0".
//   returns { timeline, destroy }: a paused GSAP timeline plus a teardown that
//     kills it, so destroying/remounting leaves no driver behind.

export function init(root, { params = {}, data = [], duration = 0, gsap }) {
  const tl = gsap.timeline({ paused: true });
  const C = (n) => getComputedStyle(root).getPropertyValue(n).trim();
  const num = (v, d) => (v !== "" && v != null && Number.isFinite(Number(v)) ? Number(v) : d);
  // defaults are the presenter layout: tiles between the two 72 px bars, spreading from the character's laptop
  const OX = num(params.originX, 1504), OY = num(params.originY, 968);
  const CX = num(params.cardX, 240), CY = num(params.cardY, 410);
  const TOP = num(params.top, 72), BOTTOM = num(params.bottom, 1080), SPEED = 6500;
  const PITCH = 56, CELL = 48, COLS = Math.ceil(1920 / PITCH), X0 = Math.round((1920 - COLS * PITCH) / 2) + (PITCH - CELL) / 2;
  const ROWS = Math.ceil((BOTTOM - TOP) / PITCH), Y0 = TOP + (PITCH - CELL) / 2;
  const PALETTE = [0, 1, 2, 3, 4].map((i) => C(`--c-tile${i}`));
  const plate = root.querySelector("#tw-plate");
  plate.style.top = TOP + "px";
  plate.style.height = BOTTOM - TOP + "px";
  const disc = (r) => `circle(${r}px at ${OX}px ${OY - TOP}px)`;
  plate.style.clipPath = disc(0);

  // tiles: denser near the origin; seeded so every render is the same
  let seed = 1018;
  const rand = () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const host = root.querySelector("#tw-tiles");
  const tiles = [], dist = [], jit = [];
  let far = 0;
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const x = X0 + c * PITCH, y = Y0 + r * PITCH;
      const d = Math.hypot(x + CELL / 2 - OX, y + CELL / 2 - OY);
      far = Math.max(far, d);
      const score = rand() * 0.85 + (1 - d / 1800) * 0.45;
      const lvl = score < 0.3 ? 0 : score < 0.52 ? 1 : score < 0.72 ? 2 : score < 0.88 ? 3 : 4;
      const el = document.createElement("i");
      el.style.left = x + "px";
      el.style.top = y + "px";
      el.style.background = PALETTE[lvl];
      host.appendChild(el);
      tiles.push(el);
      dist.push(d);
      jit.push(rand());
    }
  }
  const R = far + 60;

  // a card: big label | title + emphasis, then a meta line of { dot, strong, text } parts
  const makeCard = (cut, i) => {
    const card = document.createElement("div");
    card.className = "tw-card";
    card.id = `tw-card${i + 1}`;
    card.style.left = CX + "px";
    card.style.top = CY + "px";
    const lb = document.createElement("div");
    lb.className = "lb";
    lb.textContent = cut.label;
    card.appendChild(lb);
    if (cut.title || cut.emphasis || (cut.meta && cut.meta.length)) {
      const col = document.createElement("div");
      col.className = "col";
      const ti = document.createElement("div");
      ti.className = "ti";
      ti.append(cut.title || "");
      if (cut.emphasis) { const b = document.createElement("b"); b.textContent = cut.emphasis; ti.append(b); }
      col.appendChild(ti);
      if (cut.meta && cut.meta.length) {
        const meta = document.createElement("div");
        meta.className = "meta";
        for (const m of cut.meta) {
          const s = document.createElement("span");
          if (m.dot) { const d = document.createElement("i"); d.style.background = m.dot; s.appendChild(d); }
          if (m.strong) { const b = document.createElement("b"); b.textContent = m.strong; s.appendChild(b); }
          if (m.text) s.append(m.text);
          meta.appendChild(s);
        }
        col.appendChild(meta);
      }
      card.appendChild(col);
    }
    root.appendChild(card);
    return card;
  };

  const cuts = (Array.isArray(data) ? data : []).slice().sort((a, b) => a.at - b.at);
  cuts.forEach((cut, i) => {
    // covered at the cut, open again 0.55 s after it
    const s = cut.at - 0.45, e = s + 1.0;
    tl.fromTo(tiles, { opacity: 0, scale: 0.2 }, {
      opacity: 1, scale: 1, duration: 0.12, ease: "power2.out",
      stagger: (k) => dist[k] / SPEED + jit[k] * 0.04,
    }, s);
    tl.fromTo(plate, { clipPath: disc(0) }, { clipPath: disc(R), duration: R / SPEED, ease: "none" }, s + 0.16);
    if (cut.label) {
      const card = makeCard(cut, i);
      tl.fromTo(card, { opacity: 0, scale: 0.94 }, { opacity: 1, scale: 1, duration: 0.25, ease: "power2.out" }, s + 0.42);
      tl.to(card, { opacity: 0, scale: 0.97, duration: 0.15, ease: "power2.in" }, e - 0.1);
    }
    // the tiles drain back toward the origin
    tl.to(plate, { clipPath: disc(0), duration: R / SPEED, ease: "none" }, e);
    tl.to(tiles, {
      opacity: 0, scale: 0.2, duration: 0.12, ease: "power2.in",
      stagger: (k) => (far - dist[k]) / SPEED + jit[k] * 0.03,
    }, e);
  });

  return {
    timeline: tl,
    destroy() { tl.kill(); },
  };
}
