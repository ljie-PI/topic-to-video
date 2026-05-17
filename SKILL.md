---
name: topic-to-video
description: Use when the user provides a topic, article URL, or text and asks to make a narrated video (typically 3-10 minutes). Covers the full pipeline — topic research with web search, optional visual material search and processing, video understanding, script writing, CosyVoice cloned-voice TTS via DashScope, Paraformer ASR for word-level timestamps, scene timing, HyperFrames composition with GSAP image animation, lint/inspect, and rendering. Avoids 17+ pitfalls discovered in baseline testing.
---

# Topic → Video (HyperFrames + CosyVoice Workflow)

## What This Skill Builds

A narrated video (3-10 minutes) using:
- **Web research** to ground the script in facts before writing
- **HyperFrames** for HTML composition + render
- **CosyVoice** (via Aliyun DashScope) for cloned-voice TTS — Chinese default
- **Paraformer** (via DashScope) for word-level ASR timestamps
- A configurable visual style: default Rosé Pine Dawn handdrawn × Notion minimalism, or optional Rosé Pine Moon Serious for darker technical/editorial videos

**Output:** `{work_dir}/{topic_name}/composition/renders/final.mp4` ready to publish (produced by the Phase 8 coding sub-agent).

## Rules & Troubleshooting

These rules each prevent a specific bug a baseline agent hit. **Do not "improve" past them without re-running the gauntlet** in `references/gotchas.md`.

### Research & Script
0. **Research before writing.** Phase 2 is mandatory. Ground every claim via Gemini Deep Research + web_search.
   ↳ Don't: write script before research; skip Gemini without explicit condition; skip Phase 2a when user gave PDF; use training data to describe a paper.
1. **Material selection in Phase 4, not Phase 5.** Run vision-analyze before writing narration.
   ↳ Don't: write narration before building catalog; skip vision-analyze.

### TTS / ASR
2. **TTS = CosyVoice via DashScope.** Use cloned voice. NEVER use `npx hyperframes tts`.
3. **ASR = Paraformer-realtime-v2.** Probe sample_rate with ffprobe first.
   ↳ Don't: use Whisper / `npx hyperframes transcribe`; hardcode 16000.
   ↳ Fix: pass actual `sample_rate` to Recognition(). Symptom: `status_code=44`.

### Fonts & Text
4. **Use Google Fonts woff2, never `fc-match`.** Download with `scripts/fonts-download.sh`.
   ↳ Don't: pick system Chinese fonts.
   ↳ Fix: `[Compiler] No deterministic font mapping` → point brief at `fonts/`.
5. **`Caveat`/`PatrickHand` have NO CJK glyphs.** Split mixed text by script.
   ↳ Fix: Chinese garbage in render → check font-family on that element.

### Materials
6. **Every asset traces to `material-catalog.json`.** No catalog citation → no asset on screen.
   ↳ Don't: design scene without `material_ref`; embed full source video; cut clips without `-an`.
   ↳ Fix: clip audio bleeding → re-cut with `ffmpeg -c:v copy -an`.
7. **Material search is optional but recommended.** Skip if user says "skip materials" or provides all visuals.

### Composition
8. **Composition is delegated to sub-agent.** Main agent writes brief only.
   ↳ Don't: hand-write `index.html`; skip `composition-brief.md`.
9. **Don't `cover`-crop info-dense images.** Use `object-fit: contain` for screenshots/charts.
10. **No plain-text scenes.** Use designed info structures (cards, timelines, diagrams).
    ↳ Don't: paste `display_text` as paragraph; reveal all cards at scene start.

### Environment & Tools
11. **Always `source .venv/bin/activate` before Python.** Use `python3`.
    ↳ Fix: `playwright` import error → `pip install playwright`. `mineru` not found → `pip install "mineru[pipeline]"`.
12. **Chrome over CDP.** Shared profile at `{work_dir}/chrome_profile/`.
    ↳ Fix: Chrome exits immediately → close other Chrome using that profile. Missing `$DISPLAY` → `--headless on`. Sandbox error → `--no-sandbox` (auto-enabled as root). Cookie banner → accept once in profile.
13. **Video downloads sequential.** yt-dlp gets rate-limited when parallel.
    ↳ Fix: download fails → leave `download_required: true`, Phase 4 ignores it.

### Troubleshooting
| Symptom | Fix |
|---|---|
| `WARN: anchor not found for X` | Check case mismatch; pick anchor from actual ASR text |
| `vision-analyze.py` returns `delegate_to_agent` | Set `VLM_API_KEY`/`VLM_BASE_URL`/`VLM_MODEL`, or use `view` tool |
| `harvest-pages.py` returns 0 images | Raise `--page-load-timeout` |
| `parse-pdf.py` cloud returns `-60007` | Auto-fallback to local `mineru` CLI |
| `parse-pdf.py` cloud timeout on URL | Use `--pdf` with local file instead of `--url` |
| CDP port 9222 busy | Pass `--cdp-url http://localhost:9223` |

## Checkpoint & Resume

Before running any tool, check if its output already exists. If it does, skip and reuse.

| Phase | Skip if exists |
|-------|---------------|
| 2 | `gemini_deep_research.md` |
| 2a | `harvest_page/main-paper/metadata.json` |
| 2c | `harvest_page/related-*/metadata.json` |
| 3 | `harvest_page/manifest.json` with non-empty `entries[]` |
| 3.b | Video exists in `harvest_page/<slug>/videos/` AND `download_required: false` |
| 4 | `extract_frames/<slug>/<video>/` has ≥1 JPEG; or `material-catalog.json` has `selected_clips` |
| 5 | `narration.txt` (non-empty) |
| 6 | `voice_clone/narration.mp3` |
| 7 | `transcribe/transcript.json` |
| 7 | `transcribe/scene-timing.json` |
| 7.5 | `fonts/` has ≥1 `.woff2` |
| 8 | `composition/renders/final.mp4` |
| 9 | `composition/renders/final_with_bgm.mp4` |

Workspace discovery happens in Phase 1: check if `{work_dir}/{topic_name}/` exists, scan outputs, ask user to resume or start fresh. If a file exists but is corrupt (0-byte, truncated JSON), delete and re-run. User can force re-run with "redo phase N".

## Output Conventions

All scripts emit JSON to stdout, human-readable logs to stderr, and use exit codes: `0`=success, `1`=runtime error, `2`=invalid arguments.

**Workspace layout:** outputs live under `{work_dir}/{topic_name}/` with standard subdirectories:
`harvest_page/`, `extract_frames/`, `vision_analyze/`, `material-catalog.json`, `voice_clone/`, `transcribe/`, `fonts/`, `composition/`, `narration.txt`, `composition-brief.md`.

Shared Chrome profile: `{work_dir}/chrome_profile/` — do NOT delete.

## Workflow (9 Phases)

Execute each phase by reading its dedicated file before acting.

| Phase | File | What |
|-------|------|------|
| 1 | `references/phases/gather-inputs.md` | Gather inputs (topic, orientation, style, length) |
| 2 | `references/phases/research.md` | Topic research (Gemini Deep Research + web search) |
| 3 | `references/phases/material-harvest.md` | Harvest images/videos from URLs |
| 4 | `references/phases/material-selection.md` | Vision analysis + material catalog |
| 5 | `references/phases/narration-script.md` | Write narration script |
| 6 | `references/phases/tts-generation.md` | Generate TTS audio with CosyVoice |
| 7 | `references/phases/asr-scene-anchoring.md` | ASR + scene anchoring + fonts |
| 8 | `references/phases/composition-render.md` | Composition brief + sub-agent render |
| 9 | `references/phases/bgm-mix.md` | Mix background music |

## Tools & Dependencies

| Script | Purpose | Requires |
|--------|---------|----------|
| `fonts-download.sh` | Font download + WOFF2 conversion | — |
| `voice-clone-template.py` | CosyVoice TTS | `DASHSCOPE_API_KEY` |
| `transcribe-paraformer.py` | Paraformer ASR | `DASHSCOPE_API_KEY` |
| `scene-anchor.py` | Anchor scenes to ASR word stream | — |
| `extract-frames.py` | FFmpeg frame extraction | `ffmpeg` |
| `subtitle-parse.py` | SRT/VTT parser with keyword filter | — |
| `vision-analyze.py` | VLM analysis (or delegates to agent `view`) | `VLM_*` (optional) |
| `gemini-deep-research.py` | Gemini Deep Research automation | `playwright`, logged-in Chrome |
| `parse-pdf.py` | PDF parsing via MinerU cloud/local | `MINERU_API_TOKEN` or `mineru[pipeline]` |
| `harvest-pages.py` | Batch URL harvest (images/videos/scroll) | `playwright`, system Chrome |
| `video-download.py` | YouTube/Bilibili download | `yt-dlp` |
| `mix-bgm.py` | BGM mix onto video | `ffmpeg` |
| `check-cjk-fonts.py` | Flag CJK text in Latin-only fonts | — |

**System deps:** `ffmpeg`, `playwright` (`pip install playwright`, NO `playwright install chromium`), system Chrome (auto-detected), `yt-dlp`, `python3` with venv.
