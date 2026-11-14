// trending-overview — a Trending list walked through one repo at a time
// (docs: trending-overview.md).
//
// Explicit init per modules/modules.md: the caller passes the root element,
// mount params, data, slot duration and GSAP; this module never reads
// HyperFrames globals, never infers params from a host, and never registers
// timelines globally. The caller owns the returned timeline.
//
//   init(root, { params, data, duration, gsap })
//     params: { title, date, range, listAt, scrollSpeed }
//     data:   { title, date, range, repos: [{ rank, owner, repo, desc, stars,
//               readme, cue }] } (an array of repos is also accepted)
//     All cue times are local seconds: 0 = the scene's data-start.
//   returns { timeline, destroy }: a paused GSAP timeline plus a teardown that
//     kills it, so destroying/remounting leaves no driver behind.

export function init(root, { params = {}, data = {}, duration = 0, gsap }) {
  const tl = gsap.timeline({ paused: true });
  const C = (n) => getComputedStyle(root).getPropertyValue(n).trim();
  const num = (v, d) => (v !== "" && v != null && Number.isFinite(Number(v)) ? Number(v) : d);
  const $ = (id) => root.querySelector("#" + id);
  const FOCUS = C("--c-focus"), MUTED = C("--c-muted"), BORDER = C("--c-border");
  const D = data || {};
  const repos = (Array.isArray(D) ? D : D.repos || []).slice(0, 5);
  const cues = repos.map((r, i) => {
    const value = r.cue;
    if (value == null || !["number", "string"].includes(typeof value) || !String(value).trim() || !Number.isFinite(Number(value)) || Number(value) < 0) {
      throw new Error(`repos[${i}].cue requires a non-negative spoken scene time; do not guess`);
    }
    return Number(value);
  });
  if (cues.some((value, i) => i > 0 && value < cues[i - 1])) throw new Error("repo cues must be in chronological order");
  const LIST_AT = num(params.listAt, 0.2), SPEED = num(params.scrollSpeed, 60), VIEW_W = 1044, VIEW_H = 722;

  const titleEl = $("to-title"), listEl = $("to-list"), readmeEl = $("to-readme");
  $("to-h1").textContent = params.title || D.title || "GitHub 本周热榜";
  $("to-date").textContent = params.date || D.date || "";
  $("to-range").textContent = params.range || D.range || "本周";

  // rows and README screenshots, one per repo
  const view = $("to-view"), rbar = $("to-rbar");
  const rows = [], bars = [], tints = [], rks = [], rps = [], imgs = [], wks = [], s0s = [], s1s = [];
  repos.forEach((r, i) => {
    const n = i + 1;
    const row = document.createElement("div");
    row.className = "row";
    row.id = `to-row${n}`;
    row.innerHTML = `<div class="tint"></div><div class="bar"></div><div class="rk"></div>
      <div class="body"><span class="path"></span><span class="desc"></span></div>
      <div class="wk"><span class="ic"><svg class="ico s0" viewBox="0 0 16 16"><use href="#to-ico-star" /></svg><svg class="ico s1" viewBox="0 0 16 16"><use href="#to-ico-starfill" /></svg></span><b></b></div>`;
    row.querySelector(".rk").textContent = r.rank != null ? r.rank : n;
    const path = row.querySelector(".path");
    path.append(`${r.owner} / `);
    const b = document.createElement("b");
    b.textContent = r.repo;
    path.append(b);
    // a long path steps down from 28px so it stays inside the row
    if ((`${r.owner} / ${r.repo}`).length > 32) path.style.fontSize = "26px";
    row.querySelector(".desc").textContent = r.desc || "";
    row.querySelector(".wk b").textContent = r.stars || "";
    listEl.appendChild(row);

    const label = document.createElement("span");
    label.className = "rp";
    label.id = `to-rp${n}`;
    label.textContent = `${r.owner}/${r.repo}`;
    rbar.appendChild(label);

    const img = document.createElement("img");
    img.id = `to-img${n}`;
    img.alt = `${r.repo} README`;
    if (r.readme) img.src = r.readme;
    view.appendChild(img);

    rows.push(row);
    tints.push(row.querySelector(".tint"));
    bars.push(row.querySelector(".bar"));
    rks.push(row.querySelector(".rk"));
    wks.push(row.querySelector(".wk"));
    s0s.push(row.querySelector(".s0"));
    s1s.push(row.querySelector(".s1"));
    rps.push(label);
    imgs.push(img);
  });

  // entrance: title, then the list loads like a feed, then the README panel
  tl.fromTo(titleEl, { opacity: 0, y: -12 }, { opacity: 1, y: 0, duration: 0.4, ease: "power2.out" }, Math.max(0, LIST_AT - 0.2));
  tl.fromTo(listEl, { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.4, ease: "power2.out" }, LIST_AT);
  tl.fromTo(rows, { opacity: 0, y: 22 }, { opacity: 1, y: 0, duration: 0.4, ease: "power2.out", stagger: 0.1 }, LIST_AT + 0.05);
  tl.fromTo(readmeEl, { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.5, ease: "power2.out" }, LIST_AT + 0.1);
  tl.set(bars, { scaleY: 0 }, 0);
  if (repos.length) tl.set(imgs[0], { opacity: 1 }, 0);

  // each repo takes focus as it is named: row highlighted, README swapped and scrolled, then starred
  repos.forEach((r, i) => {
    const c = cues[i];
    const next = i + 1 < cues.length ? cues[i + 1] : null;
    tl.to(tints[i], { opacity: 1, duration: 0.25, ease: "power2.out" }, c);
    tl.to(bars[i], { scaleY: 1, duration: 0.3, ease: "power2.out" }, c);
    tl.to(rks[i], { color: FOCUS, duration: 0.25 }, c);
    tl.to(rps[i], { opacity: 1, duration: 0.12 }, c);
    tl.set(imgs[i], { opacity: 1 }, c);
    if (i > 0) {
      tl.to(tints[i - 1], { opacity: 0, duration: 0.25 }, c);
      tl.to(bars[i - 1], { scaleY: 0, duration: 0.25, ease: "power2.in" }, c);
      tl.to(rks[i - 1], { color: MUTED, duration: 0.25 }, c);
      tl.to(rps[i - 1], { opacity: 0, duration: 0.12 }, c);
      tl.set(imgs[i - 1], { opacity: 0 }, c);
    }
    // README scrolls slowly through this repo's segment: at most scrollSpeed px/s, never past its bottom
    const segEnd = next != null ? next : c + 4;
    const img = imgs[i], p = { v: 0 };
    tl.fromTo(p, { v: 0 }, {
      v: 1, duration: Math.max(0.5, segEnd - c - 0.3), ease: "sine.inOut",
      onUpdate: () => {
        // from the image's own size, not a layout measurement: the panel shows it 1044 px wide
        const room = img.naturalWidth ? Math.max(0, (img.naturalHeight * VIEW_W) / img.naturalWidth - VIEW_H) : 0;
        const dist = Math.min(room, SPEED * (segEnd - c));
        img.style.transform = `translateY(${(-dist * p.v).toFixed(1)}px)`;
      },
    }, c + 0.3);
    // Star → Starred
    tl.to(s0s[i], { opacity: 0, duration: 0.1 }, c + 0.45);
    tl.fromTo(s1s[i], { opacity: 0, scale: 0.3, transformOrigin: "50% 50%" }, { opacity: 1, scale: 1, duration: 0.35, ease: "back.out(3)" }, c + 0.45);
    tl.fromTo(wks[i], { scale: 1 }, { scale: 1.06, duration: 0.125, ease: "power2.out", yoyo: true, repeat: 1 }, c + 0.55);
    // the README frame flashes the focus colour when it switches
    tl.fromTo(readmeEl, { borderColor: FOCUS }, { borderColor: BORDER, duration: 0.6, ease: "power2.in" }, c);
  });

  return {
    timeline: tl,
    destroy() { tl.kill(); },
  };
}
