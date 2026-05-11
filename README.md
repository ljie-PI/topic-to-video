# topic-to-video

A Copilot CLI skill that turns a topic, article URL, or text into a short narrated video (60-120 s) using **HyperFrames** + **CosyVoice** cloned-voice TTS.

## Prerequisites

| Tool | Notes |
|------|-------|
| Node.js + `hyperframes` | `npm install --no-save --ignore-scripts hyperframes` |
| Python 3 + venv | `source .venv/bin/activate` before any Python script |
| `dashscope` | In the venv — powers CosyVoice TTS and Paraformer ASR |
| `ffmpeg` / `ffprobe` | Audio probing and frame extraction |
| `DASHSCOPE_API_KEY` | Set in env (e.g. `~/.zshrc`) — required for TTS/ASR |
| `VLM_*` (optional) | `VLM_API_KEY` + `VLM_BASE_URL` + `VLM_MODEL` to enable explicit vision; otherwise `vision-analyze.py` delegates back to the agent's own `view` tool |

## Quick Start

```bash
# 1. Scaffold a new project
./node_modules/.bin/hyperframes init my-video --example blank --non-interactive

# 2. Download fonts (dawn = default handdrawn, moon = serious/dark)
bash scripts/fonts-download.sh my-video/fonts dawn

# 3. Tell the agent what you want
#    "Make a 90-second video about <topic>"
#    The skill handles: research → script → TTS → ASR → compose → render
```

## Visual Styles

| Style | Template | Fonts | When to use |
|-------|----------|-------|-------------|
| **Rosé Pine Dawn** (default) | `templates/design.md` | Caveat, PatrickHand, MaShanZheng, LongCang | Warm, handdrawn explainer |
| **Rosé Pine Moon** | `templates/design-moon.md` | NotoSerifSC, NotoSansSC, IBMPlexMono | Dark, serious technical/editorial |

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/voice-clone-template.py` | CosyVoice TTS template (`speech_rate=1.5`) |
| `scripts/transcribe-paraformer.py` | Paraformer ASR — word-level timestamps |
| `scripts/vision-analyze.py` | Model-agnostic vision analysis — calls any OpenAI-compatible VLM via `VLM_*` env vars, or delegates to the agent's `view` tool when unset |
| `scripts/scene-anchor.py` | Anchor scenes to ASR word stream |
| `scripts/extract-frames.py` | Extract JPEG frames with ffmpeg / ffprobe |
| `scripts/subtitle-parse.py` | Parse SRT/VTT subtitles with keyword filtering |
| `scripts/fonts-download.sh` | Download WOFF2 fonts (`dawn` / `moon` / `all`) |
| `scripts/check-cjk-fonts.py` | Flag Chinese text inside Latin-only font contexts |

## Key Gotchas

- **TTS = CosyVoice**, not Kokoro. **ASR = Paraformer**, not Whisper.
- Paraformer `sample_rate` must be `22050` for CosyVoice MP3.
- Render with `--workers 1` (multi-worker crashes on this machine).
- Caveat / PatrickHand have **no CJK glyphs** — split mixed text into `.zh` / `.latin` spans.
- Audio clip precision must be **6 decimals** to avoid overlap lint errors.

See `references/gotchas.md` for the full pitfall catalog (18 items).

## Project Layout

```
SKILL.md                          # Full workflow (9 phases) + iron rules
templates/
  design.md                       # Dawn palette + typography
  design-moon.md                  # Moon palette + typography
  composition-skeleton.html       # Annotated index.html starting point
scripts/                          # TTS, ASR, fonts, CJK checker
references/
  gotchas.md                      # Pitfall catalog with reproductions
  image-animations.md             # GSAP + CSS patterns for animating still images
  palettes.md                     # Style routing rules
  script-templates.md             # Narration genre templates
```
