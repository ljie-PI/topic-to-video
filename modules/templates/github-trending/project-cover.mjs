// project-cover — the cover of one ranked repo (docs: project-cover.md).
//
// Explicit init per modules/modules.md: the caller passes the root element,
// mount params, data, slot duration and GSAP; this module never reads
// HyperFrames globals, never infers params from a host, and never registers
// timelines globally. The caller owns the returned timeline.
//
//   init(root, { params, data, duration, gsap })
//     params: { rank, owner, repo, eyebrow, visibility, tagline, topics, stars,
//               starsPrefix, starsLabel, lang, langColor, logo, starred,
//               nameAt, taglineAt, starsAt, exitAt }
//     The cue params are spoken scene times in local seconds (0 = the scene's
//     data-start); nameAt is required, the others optional. Nothing here is
//     guessed from a default clock.
//   returns { timeline, destroy }: a paused GSAP timeline plus a teardown that
//     kills it, so destroying/remounting leaves no driver behind.

export function init(root, { params = {}, data = null, duration = 0, gsap }) {
  const tl = gsap.timeline({ paused: true });
  const num = (v, d) => (v !== "" && v != null && Number.isFinite(Number(v)) ? Number(v) : d);
  const $ = (id) => root.querySelector("#" + id);
  const rank = num(params.rank, 1), owner = params.owner || "owner", repo = params.repo || "repo";
  const cue = (value, label, required = false) => {
    if (value == null || value === "") {
      if (required) throw new Error(`${label} requires a spoken cue; do not guess its time`);
      return null;
    }
    if (!["number", "string"].includes(typeof value) || !String(value).trim() || !Number.isFinite(Number(value)) || Number(value) < 0) {
      throw new Error(`${label} must be a non-negative finite scene time`);
    }
    return Number(value);
  };
  const NAME_AT = cue(params.nameAt, "nameAt", true), TAG_AT = cue(params.taglineAt, "taglineAt"),
    STARS_AT = cue(params.starsAt, "starsAt"), EXIT_AT = num(params.exitAt, 0);
  const stars = num(params.stars, 0), prefix = params.starsPrefix != null ? String(params.starsPrefix) : "+";
  const fmt = (v) => prefix + Math.round(v).toLocaleString("en-US");

  // ---- fill
 $("pc-eyebrow-t").textContent = params.eyebrow || `Trending #${rank} · 本周`;
  const p = $("pc-p");
  p.append(`${owner} / `);
  const b = document.createElement("b");
  b.textContent = repo;
  p.append(b);
  if (params.visibility === "" || params.visibility === "none") $("pc-vis").remove();
  else $("pc-vis").textContent = params.visibility || "Public";
  $("pc-tag").textContent = params.tagline || "";
  const topics = String(params.topics || "").split(",").map((t) => t.trim()).filter(Boolean);
  const topicSpans = [];
  if (topics.length) topics.forEach((t) => { const s = document.createElement("span"); s.textContent = t; $("pc-topics").appendChild(s); topicSpans.push(s); });
  else $("pc-topics").remove();
  $("pc-count").textContent = fmt(stars);
  $("pc-stars-label").textContent = params.starsLabel != null ? params.starsLabel : "本周新增 star";
  if (params.lang) {
    $("pc-lang-t").textContent = params.lang;
    $("pc-lang-dot").style.background = params.langColor || "#8b949e";
  } else $("pc-lang").remove();
  const side = $("pc-side");
  if (params.logo) {
    const img = document.createElement("img");
    img.src = params.logo;
    img.alt = `${repo} logo`;
    side.appendChild(img);
  } else {
    // no logo: a monogram from the repo name
    const m = document.createElement("div");
    m.className = "mono";
    m.textContent = (repo.match(/[A-Za-z0-9]/) || ["#"])[0].toUpperCase();
    side.appendChild(m);
  }

  // ---- fit: a long path or tagline steps its font size down to stay inside the main area (1048 px).
  // Width is estimated per character (CJK 1 em, others 0.56 em), so it needs no font metrics and renders the same every time.
  const ems = (t) => [...String(t)].reduce((w, ch) => w + (/[\u2e80-\u9fff\uff00-\uffef]/.test(ch) ? 1 : 0.56), 0);
  const fit = (el, text, size, room) => {
    const w = ems(text) * size;
    if (w > room) el.style.fontSize = Math.max(36, Math.floor((size * room) / w)) + "px";
  };
  fit(p, `${owner} / ${repo}`, 72, 1048 - 76 - ($("pc-vis") ? 150 : 0));
  fit($("pc-tag"), params.tagline || "", 60, 1048);

  // ---- motion, in scene seconds
  const eyebrowEl = $("pc-eyebrow"), pathEl = $("pc-path"), tagEl = $("pc-tag"),
    topicsEl = $("pc-topics"), statsEl = $("pc-stats"), metaEl = $("pc-meta"), sideEl = $("pc-side");
  tl.fromTo(eyebrowEl, { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.4, ease: "power2.out" }, NAME_AT);
  tl.fromTo(pathEl, { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.45, ease: "power2.out" }, NAME_AT + 0.1);
  tl.fromTo(sideEl, { opacity: 0, scale: 0.96 }, { opacity: 1, scale: 1, duration: 0.5, ease: "power2.out" }, NAME_AT + 0.2);
  if (TAG_AT !== null) {
    tl.fromTo(tagEl, { clipPath: "inset(0% 100% 0% 0%)" }, { clipPath: "inset(0% 0% 0% 0%)", duration: 0.55, ease: "power2.out" }, TAG_AT);
    if (topics.length) tl.fromTo(topicSpans, { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.3, ease: "power2.out", stagger: 0.08 }, TAG_AT + 0.4);
  } else {
    tagEl.style.display = "none";
    if (topics.length) topicsEl.style.display = "none";
  }
  if (STARS_AT !== null) {
    tl.fromTo(statsEl, { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.4, ease: "power2.out" }, STARS_AT);
    const n = { v: 0 }, count = $("pc-count");
    tl.fromTo(n, { v: 0 }, { v: stars, duration: 1.4, ease: "power1.out", onUpdate: () => { count.textContent = fmt(n.v); } }, STARS_AT + 0.05);
    tl.fromTo(statsEl, { scale: 1 }, { scale: 1.04, duration: 0.14, ease: "power2.out", yoyo: true, repeat: 1 }, STARS_AT + 1.45);
    tl.fromTo(metaEl, { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.35, ease: "power2.out" }, STARS_AT + 0.4);
    if (params.starred !== "off") {
      const s = STARS_AT + 1.55;
      tl.to($("pc-btn").querySelector(".s0"), { opacity: 0, duration: 0.1 }, s);
      tl.fromTo($("pc-btn").querySelector(".s1"), { opacity: 0, scale: 0.3, transformOrigin: "50% 50%" }, { opacity: 1, scale: 1, duration: 0.35, ease: "back.out(3)" }, s);
      tl.to($("pc-btn").querySelector(".t0"), { opacity: 0, duration: 0.12 }, s);
      tl.to($("pc-btn").querySelector(".t1"), { opacity: 1, duration: 0.12 }, s + 0.05);
    }
  } else {
    statsEl.style.display = "none";
    metaEl.style.display = "none";
  }
  // ---- hand over to whatever follows (exitAt 0 = hold to the end of the slot)
  if (EXIT_AT > 0) {
    tl.to(Array.from($("pc-main").children), { opacity: 0, y: -18, duration: 0.3, ease: "power2.in", stagger: 0.04 }, EXIT_AT);
    tl.to(sideEl, { opacity: 0, duration: 0.25, ease: "power2.in" }, EXIT_AT + 0.05);
  }

  return {
    timeline: tl,
    destroy() { tl.kill(); },
  };
}
