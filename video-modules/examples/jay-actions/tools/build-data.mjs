// Builds data/video-data.js for the Jay action demo: every action once, in order, with its name on the label bar.
// usage (from this folder): node tools/build-data.mjs   — prints the total length; set it as data-duration in index.html
import { writeFileSync } from "node:fs";

const GAP = 0.9; // seconds of rest between two actions
// [action, duration ms, label]; "typing" and "glance:X" are not acts but use the same slot
const SHOW = [
  ["wave", 3000, "wave · 挥手 — 开场欢迎、结尾告别"],
  ["nod", 1500, "nod · 点头 — 确认、讲完一个要点"],
  ["nod-small", 1000, "nod-small · 小点头 — 边讲边认同"],
  ["shake", 1600, "shake · 摇头 — 否定、不推荐"],
  ["tilt", 2000, "tilt · 歪头好奇 — 提出问题"],
  ["question", 2400, "question · 疑问（?） — 抛出问题"],
  ["startle", 1800, "startle · 惊讶后仰 — 意外的信息"],
  ["eureka", 2700, "eureka · 惊喜（!） — 亮出关键数字"],
  ["idea", 2400, "idea · 灵感（灯泡） — 关键思路"],
  ["smile", 2200, "smile · 微笑（嘴角上扬） — 温和的认可"],
  ["laugh", 2200, "laugh · 大笑（嘴角上扬、张嘴） — 轻松的点评"],
  ["think", 2400, "think · 思考（气泡） — 讲注意事项"],
  ["sigh", 2600, "sigh · 叹气 — 遗憾、限制条件"],
  ["lean", 2400, "lean · 凑近看 — 仔细看这里（配合看向左边）"],
  ["doubletake", 2400, "doubletake · 回头再看 — 反转、意外的细节"],
  ["typing", 2400, "typing · 打字 — 换章节前"],
  ["glance:L", 1500, "glance L · 看左边（主展示区）"],
  ["glance:U", 1500, "glance U · 看上方（副展示区）"],
  ["glance:R", 1500, "glance R · 看右边"],
  ["glance:D", 1500, "glance D · 低头看笔记本"],
];

const acts = [], thoughts = [], typing = [], glances = [], captions = [];
let t = 0.6;
for (const [name, ms, label] of SHOW) {
  const d = ms / 1000, at = +t.toFixed(3), end = +(t + d).toFixed(3);
  if (name === "typing") typing.push([at, end]);
  else if (name.startsWith("glance:")) glances.push([at, d, name.slice(7)]);
  else acts.push([at, name, ms]);
  if (name === "think") thoughts.push([at, "这是什么？"]);
  if (name === "lean") glances.push([at, d, "L"]);
  captions.push({ start: at, end: +(end + 0.35).toFixed(3), text: label });
  t = end + GAP;
}
const total = +(t + 0.3).toFixed(2);

const VIDEO = { captions, jay: { acts, thoughts, typing, glances, envelopeFps: 30, envelope: [] } };
const list = (a) => "[\n" + a.map((x) => "    " + JSON.stringify(x)).join(",\n") + "\n  ]";
const out = [
  "// Data for the Jay action demo. Built by tools/build-data.mjs; times are video seconds.",
  "window.VIDEO = {",
  `  captions: ${list(VIDEO.captions)},`,
  "  jay: {",
  `    acts: ${JSON.stringify(acts)},`,
  `    thoughts: ${JSON.stringify(thoughts)},`,
  `    typing: ${JSON.stringify(typing)},`,
  `    glances: ${JSON.stringify(glances)},`,
  "    envelopeFps: 30,",
  "    envelope: [],",
  "  },",
  "};",
  "",
].join("\n");
writeFileSync("data/video-data.js", out);
const window = {};
new Function("window", out)(window);
const same = JSON.stringify(window.VIDEO) === JSON.stringify(VIDEO);
console.log(`wrote data/video-data.js: ${SHOW.length} items, total ${total} s, read-back ${same ? "identical" : "DIFFERENT"}`);
if (!same) process.exit(1);
