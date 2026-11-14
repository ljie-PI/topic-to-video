// caption-bar — bottom chrome with one subtitle line (docs: caption-bar.md).
//
// Explicit init per modules/modules.md: the caller passes the root element,
// mount params, data, slot duration and GSAP; this module never reads
// HyperFrames globals, never infers params from a host, and never registers
// timelines globally. The caller owns the returned timeline.
//
//   init(root, { params, data, duration, gsap })
//     params: { x, width, y, height, fontSize, bar: "on" | "off" }
//     data:   { captions: [{ start, end, text }],
//               captionSegments?: [{ scene_id, begin_s, end_s, caption_rect, caption_bar_rect?, caption }] }
//     All times are local seconds: 0 = the mount's start, i.e. video seconds
//     for full-length chrome mounted at data-start="0".
//   returns { timeline, destroy }: a paused GSAP timeline plus a teardown that
//     kills it, so destroying/remounting leaves no driver behind.

export function init(root, { params = {}, data = {}, duration = 0, gsap }) {  const tl = gsap.timeline({ paused: true });
  const num = (v, d) => (v !== "" && v != null && Number.isFinite(Number(v)) ? Number(v) : d);
  // position defaults are the landscape-presenter layout's caption region
  const X = num(params.x, 96), WIDTH = num(params.width, 1166),
    Y = num(params.y, 1008), H = num(params.height, 72), FS = num(params.fontSize, 36);
  const bar = root.querySelector("#cb-bar");
  bar.style.top = Y + "px";
  bar.style.height = H + "px";
  const barOff = params.bar === "off";
  if (barOff) bar.remove();

  const cues = (data.captions || []).slice().sort((a, b) => a.start - b.start);
  const segments = (data.captionSegments || []).slice().sort((a, b) => a.begin_s - b.begin_s);
  const dynamic = segments.length > 0;
  if (!barOff && dynamic) {
    for (const segment of segments) {
      if (!("caption_bar_rect" in segment)) continue;
      const barRect = segment.caption_bar_rect;
      if (barRect) {
        tl.set(bar, {
          display: "block",
          left: num(barRect.x, 0) + "px",
          top: num(barRect.y, Y) + "px",
          width: barRect.width != null ? num(barRect.width, 1920) + "px" : "100%",
          height: num(barRect.height, H) + "px",
        }, segment.begin_s);
      } else {
        tl.set(bar, { display: "none" }, segment.begin_s);
      }
    }
  }
  const ctx = document.createElement("canvas").getContext("2d");
  const family = getComputedStyle(root).fontFamily;
  cues.forEach((c, i) => {
    const line = document.createElement("div");
    line.className = "cb-line";
    line.id = `cb-${i + 1}`;
    Object.assign(line.style, { left: X + "px", top: Y + "px", width: WIDTH + "px", height: H + "px" });
    const span = document.createElement("span");
    span.textContent = c.text;
    span.style.fontSize = FS + "px";
    line.appendChild(span);
    root.appendChild(line);

    // Legacy callers retain the original single-line shrink-to-fit behavior.
    // Scene-level captions instead use the deterministic layout contract verbatim.
    if (!dynamic) {
      ctx.font = `500 ${FS}px ${family}`;
      const w = ctx.measureText(c.text).width * 1.02;
      if (w > WIDTH) span.style.fontSize = Math.max(28, Math.floor((FS * WIDTH) / w)) + "px";
    }

    const start = dynamic ? c.start : Math.max(c.start, 0.15);
    const next = cues[i + 1] ? cues[i + 1].start : c.end;
    const end = dynamic ? Math.min(c.end, next) : Math.max(start + 0.3, Math.min(c.end + 0.1, next));
    if (dynamic) {
      for (const segment of segments) {
        if (segment.end_s <= start || segment.begin_s >= end) continue;
        const at = Math.max(start, segment.begin_s);
        const rect = segment.caption_rect || {};
        const spec = segment.caption;
        const fontSize = num(spec.font_size_px, FS);
        const lineUpdate = {
          left: num(rect.x, X) + "px", top: num(rect.y, Y) + "px",
          width: num(rect.width, spec.width_px) + "px", height: num(rect.height, H) + "px",
        };
        const spanUpdate = {
          fontSize: fontSize + "px", whiteSpace: spec.max_lines > 1 ? "normal" : "nowrap",
          lineHeight: "1.15", width: "100%", overflow: "hidden",
          maxHeight: (spec.max_lines * fontSize * 1.15) + "px",
        };
        if ("caption_bar_rect" in segment) {
          const hasBar = Boolean(segment.caption_bar_rect) && !barOff;
          const centered = !hasBar && spec.max_lines > 1;
          lineUpdate["--cb-justify"] = centered ? "center" : "flex-start";
          lineUpdate["--cb-ink"] = hasBar ? "var(--c-chrome-ink)" : "var(--c-ink)";
          lineUpdate["--cb-align"] = centered ? "center" : "left";
        }
        tl.set(line, lineUpdate, at);
        tl.set(span, spanUpdate, at);
      }
    }
    const fadeIn = dynamic ? Math.min(0.18, (end - start) / 3) : 0.18;
    const fadeOut = dynamic ? Math.min(0.12, (end - start) / 3) : 0.12;
    tl.fromTo(line, { opacity: 0 }, { opacity: 1, duration: Math.min(0.01, (end - start) / 3) }, start);
    tl.fromTo(span, { opacity: 0, y: 8 }, { opacity: 1, y: 0, duration: fadeIn, ease: "power2.out" }, start);
    tl.to(span, { opacity: 0, duration: fadeOut, ease: "power2.in" }, end - fadeOut);
    tl.set(line, { opacity: 0 }, end);
  });

  return {
    timeline: tl,
    destroy() { tl.kill(); },
  };
}
