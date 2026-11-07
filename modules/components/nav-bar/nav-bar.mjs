// nav-bar — the top chrome of the presenter layout (docs: nav-bar.md).
//
// Explicit init per modules/modules.md: the caller passes the root element,
// mount params, data, slot duration and GSAP; this module never reads
// HyperFrames globals, never infers params from a host, and never registers
// timelines globally. The caller owns the returned timeline.
//
//   init(root, { params, data, duration, gsap })
//     params: { logo, path, tabsX }
//     data:   [{ label, at }] — "at" is the chapter start in local seconds
//     All times are local seconds: 0 = the mount's start, i.e. video seconds
//     for full-length chrome mounted at data-start="0".
//   returns { timeline, destroy }: a paused GSAP timeline plus a teardown that
//     kills it, so destroying/remounting leaves no driver behind.

export function init(root, { params = {}, data = [], duration = 0, gsap }) {
  const tl = gsap.timeline({ paused: true });
  const $ = (selector) => root.querySelector(selector);

  // logo: an image passed in; without one the path moves to the left edge
  const logo = $("#nb-logo");
  if (params.logo) logo.src = params.logo;
  else {
    logo.remove();
    $("#nb-path").style.left = "40px";
  }

  // path: the last "/" segment is the page, the rest is muted
  const path = params.path != null ? String(params.path) : "";
  const cut = path.lastIndexOf("/");
  const box = $("#nb-path");
  if (cut >= 0) {
    const em = document.createElement("em");
    em.textContent = path.slice(0, cut + 1);
    box.append(em, " " + path.slice(cut + 1).trim());
  } else box.textContent = path;

  // tabs: fixed widths from the label so the underline lands the same in every render
  const tabs = (Array.isArray(data) ? data : []).slice().sort((a, b) => a.at - b.at);
  const left = Number(params.tabsX) || 420;
  const row = $("#nb-tabs"), line = $("#nb-line");
  row.style.left = left + "px";
  const widthOf = (s) => Math.max(80, Math.round([...String(s)].reduce((w, ch) => w + (/[⺀-鿿＀-￯]/.test(ch) ? 28 : 17.5), 0)) + 44);
  const X = [], W = [], now = [], idle = [];
  let x = 0;
  tabs.forEach((t, i) => {
    const el = document.createElement("div");
    el.className = "tab";
    el.id = `nb-t${i}`;
    el.style.width = (W[i] = widthOf(t.label)) + "px";
    for (const cls of ["idle", "now"]) {
      const s = document.createElement("span");
      s.className = cls;
      s.textContent = t.label;
      // the first tab starts as the current one
      if (i === 0) s.style.opacity = cls === "now" ? "1" : "0";
      el.appendChild(s);
      (cls === "now" ? now : idle).push(s);
    }
    X[i] = x; x += W[i];
    row.appendChild(el);
  });

  if (tabs.length) {
    line.style.left = left + "px";
    line.style.width = W[0] + "px";
    // the underline is the film's progress bar: it moves while the transition covers the cut
    tabs.forEach((t, i) => {
      if (i === 0) return;
      const at = Math.max(0, t.at - 0.04);
      tl.to(line, { x: X[i], scaleX: W[i] / W[0], duration: 0.32, ease: "power3.inOut" }, Math.max(0, t.at - 0.1));
      tl.to(now[i - 1], { opacity: 0, duration: 0.2 }, at);
      tl.to(idle[i - 1], { opacity: 1, duration: 0.2 }, at);
      tl.to(now[i], { opacity: 1, duration: 0.2 }, at);
      tl.to(idle[i], { opacity: 0, duration: 0.2 }, at);
    });
  } else {
    line.remove();
  }

  return {
    timeline: tl,
    destroy() { tl.kill(); },
  };
}
