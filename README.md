# topic-to-video

A Copilot CLI skill that turns a topic, article URL, or text into a narrated video (3-10 minutes) using **HyperFrames** + **CosyVoice** cloned-voice TTS.

The main agent owns research, narration scripting, TTS, ASR, and material harvesting. The final composition + render step is delegated to a **coding sub-agent** (GitHub Copilot CLI by default; Claude Code as an alternative) that has the `hyperframes` skill loaded.

## Prerequisites

| Tool | Notes |
|------|-------|
| Python 3 + venv | `source .venv/bin/activate` before any Python script |
| `dashscope` | In the venv — powers CosyVoice TTS and Paraformer ASR |
| `ffmpeg` / `ffprobe` | Audio probing and frame extraction |
| `playwright` (Python only) | `pip install playwright` — NO `playwright install chromium` step; we use system Chrome over CDP |
| System Google Chrome       | Auto-detected per platform (Linux, macOS, Windows); or set `CHROME_PATH` env var / pass `--chrome-path`. Auto-launched with shared profile at `{work_dir}/chrome_profile` |
| `yt-dlp` | On PATH — required by `scripts/video-download.py` (the agent calls it in Phase 3.b on every `pending_downloads[]` entry produced by `harvest-pages.py`) |
| `DASHSCOPE_API_KEY` | Set in env (e.g. `~/.zshrc`) — required for TTS/ASR |
| `VLM_*` (optional) | `VLM_API_KEY` + `VLM_BASE_URL` + `VLM_MODEL` to enable explicit vision; otherwise `vision-analyze.py` delegates back to the agent's own `view` tool |
| `copilot` CLI (Phase 8) | GitHub Copilot CLI on PATH. The composition sub-agent. Fallback: `claude` CLI. |
| `hyperframes` skill (Phase 8) | Discoverable by the sub-agent's CLI (Copilot CLI / Claude Code) through its own skill/plugin loader — the main agent does not need to know the install path. Node.js is required transitively for the sub-agent's `hyperframes` CLI; the main agent never invokes it directly. |

## Quick Start

```bash
# Just tell the main agent what you want, e.g.:
#   "Make a 90-second video about <topic>"
#
# The skill drives:
#   Phase 1 inputs → Phase 2 research → Phase 3-4 material harvest + vision-analyze
#   → Phase 5 narration → Phase 6 CosyVoice TTS → Phase 7 Paraformer ASR + scene anchor
#   → Phase 7.5 pre-stage fonts
#   → Phase 8 writes {work_dir}/{topic_name}/composition-brief.md
#            and invokes `copilot -p` from that workspace
# The sub-agent then runs `hyperframes init`, designs DESIGN.md, composes
# index.html, lints, and renders to composition/renders/final.mp4.
```

## Visual Styles

The Phase 8 brief MAY point at one of these references; the sub-agent is also free to ignore both and design from scratch.

| Style | Reference | Fonts | When to use |
|-------|-----------|-------|-------------|
| **Rosé Pine Dawn** (default suggestion) | `references/design-dawn.md` | Caveat, PatrickHand, MaShanZheng, LongCang | Warm, handdrawn explainer |
| **Rosé Pine Moon** | `references/design-moon.md` | NotoSerifSC, NotoSansSC, IBMPlexMono | Dark, serious technical/editorial |

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/voice-clone-template.py` | CosyVoice TTS template (`speech_rate=1.3`) |
| `scripts/transcribe-paraformer.py` | Paraformer ASR — word-level timestamps |
| `scripts/vision-analyze.py` | Model-agnostic vision analysis — calls any OpenAI-compatible VLM via `VLM_*` env vars, or delegates to the agent's `view` tool when unset |
| `scripts/gemini-deep-research.py` | Gemini Deep Research automation — submits a research prompt via Playwright over CDP and returns the full report + cited sources; primary research backbone for Phase 2 |
| `scripts/scene-anchor.py` | Anchor scenes to ASR word stream |
| `scripts/extract-frames.py` | Extract JPEG frames with ffmpeg / ffprobe |
| `scripts/subtitle-parse.py` | Parse SRT/VTT subtitles with keyword filtering |
| `scripts/harvest-pages.py` | Batch URL → material: extracts raster images meeting the configurable size filter (default ≥500px wide and ≥300px tall), SVGs, inline SVGs, and native `<video>` clips per rendered page; records a scroll-through video by default (Playwright over CDP, shared profile with gemini-deep-research). YouTube/Bilibili URLs are listed in `manifest.pending_downloads[]` — the agent invokes `video-download.py` on each in Phase 3.b. |
| `scripts/video-download.py` | yt-dlp wrapper for YouTube/Bilibili download with subtitles; called by the agent (Phase 3.b) on every `pending_downloads[]` URL produced by `harvest-pages.py` |
| `scripts/mix-bgm.py` | Phase 9 — loop the bundled `assets/bgm.mp3` (or `--bgm /path/to/your.mp3`) under the narration at low volume (default 0.03) and write `final_with_bgm.mp4` |
| `scripts/fonts-download.sh` | Download WOFF2 fonts (`dawn` / `moon` / `all`) — run by the main agent in Phase 7.5 |
| `scripts/check-cjk-fonts.py` | Flag Chinese text inside Latin-only font contexts (Phase 8 sanity check on the sub-agent's output) |

## Key Gotchas

- **TTS = CosyVoice**, not Kokoro. **ASR = Paraformer**, not Whisper.
- Paraformer `sample_rate` must be `22050` for CosyVoice MP3.
- Caveat / PatrickHand have **no CJK glyphs** — the Phase 8 brief must tell the sub-agent to split mixed runs into `.zh` / `.latin` spans.
- Pin `--workers 1` for `hyperframes render` in the brief (multi-worker crashes on this machine).
- Never hand-write `composition/index.html` from the main agent — delegate to the sub-agent via `composition-brief.md`.

See `references/gotchas.md` for the full pitfall catalog.

## Project Layout

```
SKILL.md                          # Full workflow (9 phases) + iron rules
assets/                           # Bundled binary assets (e.g. bgm.mp3 for Phase 9)
scripts/                          # TTS, ASR, fonts, CJK checker, material harvest (Playwright+CDP), video-download, vision-analyze, frame extract, subtitle parse, scene anchor, mix-bgm
references/
  design-dawn.md                  # Optional style reference — Dawn handdrawn warm
  design-moon.md                  # Optional style reference — Moon dark technical/editorial
  gotchas.md                      # Pitfall catalog with reproductions
  image-animations.md             # Suggestive GSAP image-animation catalog the Phase 8 sub-agent MAY consult
  palettes.md                     # Style routing rules
  script-templates.md             # Narration genre templates
```
