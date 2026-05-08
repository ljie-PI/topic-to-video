# topic-to-video

A Copilot CLI skill that turns a topic, article URL, or text into a short narrated video (60-120 s) using **HyperFrames** + **CosyVoice** cloned-voice TTS.

## Prerequisites

| Tool | Notes |
|------|-------|
| Node.js + `hyperframes` | `npm install --no-save --ignore-scripts hyperframes` |
| Python 3 + venv | `source .venv/bin/activate` before any Python script |
| `dashscope` | In the venv — powers CosyVoice TTS and Paraformer ASR |
| `ffmpeg` / `ffprobe` | Audio probing and frame extraction |
| `DASHSCOPE_API_KEY` | Set in env (e.g. `~/.zshrc`) |

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
| `scripts/scene-anchor.py` | Anchor scenes to ASR word stream |
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
  palettes.md                     # Style routing rules
  script-templates.md             # Narration genre templates
```
