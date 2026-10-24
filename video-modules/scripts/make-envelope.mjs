// Mouth data for Jay from a voice track: loudness 0–100, `fps` values a second (default 30).
// usage: node make-envelope.mjs <voice file: wav / mp3 / m4a / mp4> [--fps 30] > envelope.json
// Paste the array into window.VIDEO.jay.envelope (and set envelopeFps if not 30). Needs ffmpeg on PATH.
import { spawnSync } from "node:child_process";

const args = process.argv.slice(2);
const file = args.find((a, i) => !a.startsWith("--") && args[i - 1] !== "--fps");
const fpsAt = args.indexOf("--fps");
const fps = fpsAt >= 0 ? Number(args[fpsAt + 1]) : 30;
if (!file || !(fps > 0)) {
  console.error("usage: node make-envelope.mjs <voice file> [--fps 30]");
  process.exit(1);
}

const RATE = 24000;
const win = Math.round(RATE / fps);
const r = spawnSync("ffmpeg", ["-nostdin", "-v", "error", "-i", file, "-ac", "1", "-ar", String(RATE), "-f", "s16le", "-"], { maxBuffer: 1 << 30 });
if (r.status !== 0) {
  console.error(String(r.stderr || "ffmpeg failed"));
  process.exit(1);
}
const pcm = new Int16Array(r.stdout.buffer, r.stdout.byteOffset, Math.floor(r.stdout.length / 2));

// loudness per frame in dBFS
const db = [];
for (let i = 0; i < pcm.length; i += win) {
  let sum = 0, n = 0;
  for (let k = i; k < Math.min(i + win, pcm.length); k++) { sum += pcm[k] * pcm[k]; n++; }
  const rms = Math.sqrt(sum / Math.max(1, n)) / 32768;
  db.push(20 * Math.log10(rms + 1e-9));
}

// silence floor at -45 dBFS; full open at the 95th percentile of the voiced frames
const FLOOR = -45;
const voiced = db.filter((d) => d > FLOOR).sort((a, b) => a - b);
const peak = voiced.length ? voiced[Math.floor(voiced.length * 0.95)] : -12;
const span = Math.max(6, peak - FLOOR);
const levels = db.map((d) => Math.round(Math.max(0, Math.min(1, (d - FLOOR) / span)) * 100));

process.stdout.write(JSON.stringify(levels) + "\n");
console.error(`${levels.length} values at ${fps}/s (${(levels.length / fps).toFixed(2)} s), peak ${peak.toFixed(1)} dBFS`);
