// Builds data/video-data.js for this example: tabs, captions, tile-wipe cuts, the trending scene and Jay's acting script.
// usage (from this folder): node tools/build-data.mjs
// Sources inside this project: the narration cues (data/narration.json) and the voice track (assets/audio/narration.m4a),
// whose loudness becomes Jay's mouth through the skill's modules/components/jay/make-envelope.mjs (override with MAKE_ENVELOPE=<path>).
import { readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";

const END = 27.2; // length of this example in seconds
const FPS = 30;

const narration = JSON.parse(readFileSync("data/narration.json", "utf8"));
const captions = (narration.cues || narration)
  .filter((c) => c.start < END)
  .map((c) => ({ start: c.start, end: Math.min(c.end, END), text: c.text }));

const envelope = JSON.parse(execFileSync("node", [process.env.MAKE_ENVELOPE || "../../components/jay/make-envelope.mjs", "assets/audio/narration.m4a"], { maxBuffer: 1 << 26 }).toString())
  .slice(0, Math.ceil(END * FPS) + 1);

const repos = [
  { rank: 1, owner: "storytold", repo: "artcraft", desc: "先构图，再交给模型生成", stars: "20,267", readme: "assets/readme/artcraft.png", cue: 1.467 },
  { rank: 2, owner: "debpalash", repo: "VoiceStudio", desc: "本地完成声音克隆与配音", stars: "14,708", readme: "assets/readme/voicestudio.png", cue: 5.7 },
  { rank: 3, owner: "LibreSpark", repo: "LibreTV", desc: "集中搜索、播放多源影视", stars: "4,775", readme: "assets/readme/libretv.png", cue: 9.2 },
  { rank: 4, owner: "mksglu", repo: "context-mode", desc: "在执行侧过滤日志，降低开销", stars: "4,207", readme: "assets/readme/contextmode.png", cue: 12.567 },
  { rank: 5, owner: "K-Dense-AI", repo: "scientific-agent-skills", desc: "为智能体提供科研流程规范", stars: "3,170", readme: "assets/readme/sciskills.png", cue: 16.667 },
];

// Jay, per templates/github/github.md section 5 (video seconds; the trending scene starts at 0)
const COVER_AT = 20.7, STARS_AT = 4.3, TAGLINE_AT = 2.4;
const glances = [];
for (const r of repos) {
  glances.push([r.cue, 1.0, "U"]);
  glances.push([+(r.cue + 1.7).toFixed(3), 1.0, "L"]);
}
glances.push([+(COVER_AT + TAGLINE_AT + 0.05).toFixed(3), 1.0, "L"]);
const jay = {
  acts: [[0.45, "wave", 3000], [COVER_AT + STARS_AT, "eureka", 2700]],
  thoughts: [],
  typing: [[+(COVER_AT - 0.85).toFixed(3), +(COVER_AT + 0.05).toFixed(3)]],
  glances,
  envelopeFps: FPS,
  envelope,
};

const VIDEO = {
  tabs: [
    { label: "概览", at: 0 }, { label: "#1", at: 20.7 }, { label: "#2", at: 45.5 }, { label: "#3", at: 68.4 },
    { label: "#4", at: 93.3 }, { label: "#5", at: 120.3 }, { label: "趋势", at: 146.4 },
  ],
  captions,
  // tile-wipe cards: label = rank, title + emphasis = owner / repo, meta = language dot + weekly stars
  cuts: [
    { at: COVER_AT, label: "#1", title: "storytold / ", emphasis: "artcraft", meta: [{ dot: "#dea584", text: "Rust" }, { strong: "+20,267", text: "star 本周" }] },
  ],
  trending: { title: "GitHub 本周热榜", date: "10/12 — 10/18", range: "本周", repos },
  jay,
};

// one item per line, written with JSON.stringify only, so numbers are never reformatted by hand
const list = (a, pad) => "[\n" + a.map((x) => pad + "  " + JSON.stringify(x)).join(",\n") + "\n" + pad + "]";
const out = [
  "// Data for this video, read by the components and the templates/github scenes. Built by tools/build-data.mjs.",
  "// Times are video seconds, except trending.repos[].cue, which is seconds into the trending-overview scene.",
  "window.VIDEO = {",
  `  tabs: ${list(VIDEO.tabs, "  ")},`,
  `  captions: ${list(VIDEO.captions, "  ")},`,
  `  cuts: ${list(VIDEO.cuts, "  ")},`,
  "  trending: {",
  `    title: ${JSON.stringify(VIDEO.trending.title)},`,
  `    date: ${JSON.stringify(VIDEO.trending.date)},`,
  `    range: ${JSON.stringify(VIDEO.trending.range)},`,
  `    repos: ${list(VIDEO.trending.repos, "    ")},`,
  "  },",
  "  jay: {",
  `    acts: ${JSON.stringify(jay.acts)},`,
  `    thoughts: ${JSON.stringify(jay.thoughts)},`,
  `    typing: ${JSON.stringify(jay.typing)},`,
  `    glances: ${JSON.stringify(jay.glances)},`,
  "    // mouth: loudness of the voice track, 0–100, 30 values a second",
  `    envelopeFps: ${jay.envelopeFps},`,
  `    envelope: ${JSON.stringify(jay.envelope)},`,
  "  },",
  "};",
  "",
].join("\n");
writeFileSync("data/video-data.js", out);

// read it back and compare with what was meant to be written
const window = {};
new Function("window", out)(window);
const same = JSON.stringify(window.VIDEO) === JSON.stringify(VIDEO);
console.log(`wrote data/video-data.js: ${captions.length} captions, ${envelope.length} mouth values (max ${Math.max(...envelope)}), read-back ${same ? "identical" : "DIFFERENT"}`);
if (!same) process.exit(1);
