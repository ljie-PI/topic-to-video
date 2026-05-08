---
name: topic-to-video
description: Use when the user provides a topic, article URL, or text and asks to make a short narrated video (typically 60-120s). Covers the full pipeline — topic research with web search, script writing, CosyVoice cloned-voice TTS via DashScope, Paraformer ASR for word-level timestamps, scene timing, HyperFrames composition, lint/inspect, and rendering. Avoids 17+ pitfalls discovered in baseline testing.
---

# Topic → 视频 (HyperFrames + CosyVoice 流水线)

## What This Skill Builds

A short narrated video (60-120s) using:
- **Web research** to ground the script in facts before writing
- **HyperFrames** for HTML composition + render
- **CosyVoice** (via Aliyun DashScope) for cloned-voice TTS — Chinese default
- **Paraformer** (via DashScope) for word-level ASR timestamps
- A configurable visual style: default Rosé Pine Dawn handdrawn × Notion minimalism, or optional Rosé Pine Moon Serious for darker technical/editorial videos

**Output:** `renders/<name>-final.mp4` ready to publish.

## Iron Rules (Non-Negotiable)

These rules each prevent a specific bug a baseline agent hit. **Do not "improve" past them without re-running the gauntlet** in `references/gotchas.md`.

0. **Research before script.** Phase 2 is mandatory. Do not draft a single line of narration before fetching the source URL (if any) and running web_search to verify names, dates, numbers, and quotes. Untruthful video = useless video.
1. **TTS = CosyVoice via DashScope, not Kokoro.** User has a cloned voice. Use `scripts/voice-clone-template.py`. NEVER use `npx hyperframes tts` (Kokoro) for Chinese — it's not their voice.
2. **ASR = DashScope Paraformer-realtime-v2, not Whisper.** `npx hyperframes transcribe` for Chinese fails with empty errors, UTF-8 fragmentation, and slow downloads. Use `scripts/transcribe-paraformer.py`.
3. **Paraformer `sample_rate` MUST match the actual audio sample rate.** CosyVoice MP3 = `22050`. Default 16000 silently fails with `status_code=44 "sample rate 16000 not equals with real 22050"`.
4. **Always `source .venv/bin/activate` before Python.** `dashscope` is in the venv. Use `python3` (no `python` alias).
5. **Use Google Fonts woff2, never `fc-match` system fonts.** System Chinese fonts (e.g. `AR PL UKai CN`) trigger `[Compiler] No deterministic font mapping` at render. Download the selected style's fonts with `scripts/fonts-download.sh`: Dawn = handdrawn fonts; Moon = `NotoSerifSC`/`NotoSansSC`/`IBMPlexMono`.
6. **`Caveat` and `PatrickHand` have NO Chinese glyphs.** They are Dawn-only English/numeric handwriting fonts. For Dawn mixed Chinese + Latin text, split by script: Chinese spans use `MaShanZheng`/`LongCang`; English/numeric spans use `Caveat`/`PatrickHand`. For Moon, use `NotoSerifSC`/`NotoSansSC` for Chinese and `IBMPlexMono` for English/data/code. Do not rely on fallback chains for mixed badges.
7. **Render with `--workers 1`.** Multi-worker render fails on this machine: "FFmpeg exited with code 187 — height not divisible by 2 (1920×993)" from a Chromium fallback bug.
8. **Banned in any `tl.from()`/`tl.to()`:** animating `textContent` on an element with nested `<span>` children (produces NaN). Use `scale`/`opacity` for emphasis on numbers with units.
9. **`class="clip"` is required on every visible timed element.** Or it stays visible the whole video.
10. **Audio clip start/duration must be 6-decimal precision.** 3-decimal rounding causes `30.773 overlaps 30.772` lint errors when chaining 8 segments back-to-back.

## Workflow (9 Phases)

### Phase 1 — Gather Inputs (ask user, ONE question at a time)

1. Source: URL to fetch, pasted text, or just a topic.
2. Orientation: `1920×1080` (horizontal), `1080×1920` (vertical), or `1080×1440` (3:4 portrait).
3. Style: read `style-prompt.md` if it exists in cwd, else infer from user wording:
   - Default: Rosé Pine Dawn handdrawn (`templates/design.md`)
   - Use Rosé Pine Moon Serious (`templates/design-moon.md`) when the user says "moon", "严肃", "深色", "技术感", "技术评论", "AI", "SaaS", or "编程" and wants a serious tone
   - If topic is AI/SaaS/programming but style is not explicit, ask whether they want Dawn warm explainer or Moon serious technical editorial
4. Length: usually 60-120s — derive from user's request or default to 75-90s.
5. Language: default Chinese. Ask if user wants a different language.

**If a sister project already exists** (e.g. user says "same style as `claude-code-video/`"), copy `design.md` + `fonts/` from it and skip phase 4.

### Phase 2 — Topic Research (CRITICAL — do this BEFORE writing)

**Never write a script from your training data alone.** A 60-second video has no room for vague claims, and any factual error becomes a 60-second mistake. Ground every claim in fresh, citeable sources.

**Process:**

1. **If the user gave a URL** → `web_fetch` it FIRST. Read the full content. This is the spine of the video.
2. **Identify what you don't know.** What numbers, names, dates, or technical specifics would make the script concrete? List them.
3. **Run targeted searches.** Use `web_search` for each unknown — typical: 3-6 searches per video. Examples:
   - "Boris Cherny Anthropic interview Sequoia 2026" → confirm names, dates, quotes
   - "Claude Code MCP launch date" → date specifics
   - "GPU vs CPU AI training memory bandwidth" → technical numbers
4. **Synthesize a research brief** in your scratchpad. Format:
   ```
   ## Key facts (verified)
   - [fact, source]
   - [fact, source]

   ## Quotes (verbatim if possible)
   - "..." — Person, source

   ## Numbers / dates
   - [N], [unit], [source]

   ## Open questions / contradictions
   - [thing you couldn't verify cleanly — flag in script as "据报道" or remove]
   ```
5. **Show the research brief to the user before writing the script.** They may add context, correct a misreading, or narrow the angle. ~1 round of feedback typically.

**Skip research only when:**
- The user explicitly says "skip research, use this exact text" + provides full content
- The topic is a re-narration of a piece they already wrote and provided in full

**Anti-pattern:** Searching once, then writing as if the brief is complete. Real research is iterative — you find one fact, it raises a new question, you search again. Plan for 2-3 rounds.

### Phase 3 — Scaffold + Install

```bash
# Run from a parent directory that already has hyperframes installed
./node_modules/.bin/hyperframes init <project-name> --example blank --non-interactive

# If hyperframes not installed, install with --ignore-scripts
# (onnxruntime-node postinstall fails on this network)
npm install --no-save --ignore-scripts hyperframes
```

### Phase 4 — Fonts (one-time per project)

Download the fonts for the selected style as local deterministic WOFF2 assets:

```bash
# Dawn default handdrawn style
bash /home_ext/ljie/.copilot/skills/topic-to-video/scripts/fonts-download.sh fonts dawn

# Moon serious technical/editorial style
bash /home_ext/ljie/.copilot/skills/topic-to-video/scripts/fonts-download.sh fonts moon

# If creating a reusable project template that may switch styles later
bash /home_ext/ljie/.copilot/skills/topic-to-video/scripts/fonts-download.sh fonts all
```

### Phase 5 — Write Narration Script

**Inputs:** the research brief from Phase 2 + the user's preferred angle/length.

Goals:
- Use **only facts from the research brief** — every number, name, date, and quote must be traceable.
- 60-120 seconds at `speech_rate=1.5` ≈ **3.7 chars/sec** → `60s×3.7 ≈ 220 chars`, `90s×3.7 ≈ 330 chars`, `120s×3.7 ≈ 440 chars`.
- 8-10 paragraphs, separated by blank lines (each ≈ one scene = 6-12s of audio).
- Numbers in Chinese characters (`二零二六` not `2026`) — TTS reads them more naturally.
- English proper nouns in original Latin (`Anthropic`, `Claude Code`, `Boris`).
- **Avoid the full-width Chinese colon `：`.** CosyVoice can occasionally insert a 0.5-1 s silence after a full-width colon followed immediately by a long compound sentence, which makes the video feel stuck mid-scene. Use an em dash `——`, split the sentence with commas, or rewrite it. Example: `某品牌：日均消耗一百万` → `某品牌 —— 日均消耗一百万`.
- Last paragraph should be a CTA (`点赞、关注、收藏，下期见`) if user wants social-media style.

**Show the script to the user before generating TTS.** Lets them tweak tone, add/remove a beat, or reject a direction before you spend API budget.

Save to `narration.txt`.

### Phase 6 — Generate TTS

Copy `scripts/voice-clone-template.py` to project root, paste `narration.txt` content into `input_text`, then:

```bash
source .venv/bin/activate  # from parent dir, or wherever the venv is
export DASHSCOPE_API_KEY="sk-..."
python3 voice-clone.py
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 output.mp3
```

Move `output.mp3 → <project>/narration.mp3`.

If duration is much longer than user wanted, retry with higher `speech_rate` (1.5 default; try 1.7 for shorter, 1.2 for slower).

### Phase 7 — ASR + Scene Anchoring

Run `scripts/transcribe-paraformer.py <project>/narration.mp3 <project>/transcript.json`.

Then design 8-10 scenes, each with:
- `id` (e.g. `s1-hook`, `s2-stat`)
- `anchor` (a 4-8 char substring that appears uniquely in the ASR text, signalling this scene starts when this phrase is spoken)
- `display_text` (what shows on screen — usually different from spoken text, much shorter)

Run `scripts/scene-anchor.py <transcript.json> <scenes-config.json> <output: scene-timing.json>` to get exact `begin_ms`/`duration_ms` per scene.

### Phase 8 — Compose `index.html`

Read `templates/composition-skeleton.html` for the skeleton. Key conventions:

- Root: `<div id="root" data-composition-id="main" data-start="0" data-duration="<TOTAL_S>" data-width="<W>" data-height="<H>">`
- Background ambient div: `class="clip"`, full-duration, contains grain + drifting doodles.
- One `<audio class="clip">` for narration on a high track-index.
- One `<div class="scene clip s<N>">` per scene, with exact `data-start` / `data-duration` from scene-timing.json.
- All animations in ONE `gsap.timeline({ paused: true })` registered on `window.__timelines["main"]`.
- For scene-N animations, use absolute time positions (e.g. `tl.from('#s3-title', {...}, 13.5)`).

**Style application:**
- Read the design template selected in Phase 1:
  - Dawn: `templates/design.md`
  - Moon: `templates/design-moon.md`
- If Moon is selected, add `<link rel="stylesheet" href="fonts/rose-pine-moon-fonts.css" />` before the composition `<style>` block, replace the Dawn palette/font variables with the Moon variables from `templates/design-moon.md`, and keep the HyperFrames timing structure unchanged.
- Use accent color sparingly: ONE per scene.
- Headlines 100-160px, body 32-56px (these are video sizes, not web sizes).
- For portrait orientation: stack horizontal layouts vertically; reduce headline to 70-130px.

**Mixed-language typography:**
- Apply the font stack from the selected design template, not a global Dawn-only stack.
- Dawn: Chinese uses `MaShanZheng`/`LongCang`; English and numbers use `Caveat`/`PatrickHand`.
- Moon: Chinese headlines use `NotoSerifSC`; Chinese body/captions use `NotoSansSC`; English, data, and code use `IBMPlexMono`.
- When one line mixes scripts, split into spans and let `.zh` / `.latin` resolve through the selected style's CSS variables:
  ```html
  <div class="mixed-text">
    <span class="zh">效率提升</span>
    <span class="latin">42%</span>
  </div>
  ```
- In Dawn, never put Chinese characters directly inside `.font-latin-emphasis`, `.font-latin-body`, `.corner-mark`, `.scene-num`, or any selector whose `font-family` is `Caveat`/`PatrickHand`.
- In Moon, do not introduce Dawn handwriting fonts unless the user explicitly asks for a handdrawn contrast.

### Phase 9 — Verify + Render

```bash
cd <project>
../node_modules/.bin/hyperframes lint        # MUST: 0 errors
../node_modules/.bin/hyperframes inspect     # MUST: 0 layout issues
python3 /home_ext/ljie/.copilot/skills/topic-to-video/scripts/check-cjk-fonts.py index.html
# Optionally: validate (WCAG contrast — Rosé Pine Dawn is muted, expect informational warnings)

# Draft render to verify visually before committing to high-quality
../node_modules/.bin/hyperframes render --quality draft --workers 1 --output renders/draft.mp4

# Extract sample frames at scene boundaries (every ~10s)
mkdir -p frames
for t in 2 13 24 33 42 52 60 68 73; do
  ffmpeg -y -ss $t -i renders/draft.mp4 -frames:v 1 -q:v 2 frames/f-${t}s.jpg 2>/dev/null
done
# View each frame; look for: NaN/undefined text, garbled Chinese (font fallback),
# overlapping text, missing elements, broken count-ups.

# Once draft looks good, render final:
../node_modules/.bin/hyperframes render --quality high --fps 30 --workers 1 \
  --output renders/<name>-final.mp4
```

## Gotchas Quick Table (read `references/gotchas.md` for details)

| Symptom | Cause | Fix |
|---|---|---|
| `Failed to download model small.en` | Whisper download blocked | Use Paraformer instead |
| `status_code=44 sample rate 16000 not equals with real 22050` | Paraformer sample_rate mismatch | `sample_rate=22050` for CosyVoice MP3 |
| `Conversion failed! Try --docker` | multi-worker chromium fallback bug | `--workers 1` |
| `[Compiler] No deterministic font mapping for: AR PL UKai CN` | Using system Chinese font | Download Google Fonts woff2 |
| Chinese badge shows ★▢□ garbage | Caveat font has no CJK glyphs | Use `MaShanZheng` for the Chinese span |
| Number animates to "NaN%" | `tl.from(textContent: 0)` on element with nested `<span>` | Use `scale`/`opacity` only |
| `Track N: clip ending at X overlaps with clip starting at X` | 3-decimal rounding | 6-decimal precision OR subtract 0.001 |
| Lint: `composition_self_attribute_selector` | CSS uses `[data-composition-id="main"]` | Use `#root` selector |
| Lint: `gsap_repeat_ceil_overshoot` | `repeat: Math.ceil(N/M)-1` | `Math.floor` instead |
| Lint: `overlapping_gsap_tweens` on consecutive same-property tweens | No overwrite | Add `overwrite: 'auto'` |
| Console: `GSAP target #X not found` | Selector matches no elements in some scenes | Filter empty: `if (gsap.utils.toArray(sel).length === 0) return;` |
| Inspect: text overflow on inline highlight | Padding+lineheight too tight for CJK | `padding: 4px 16px 12px; line-height: 1.15;` |
| Paraformer transcript missing capitals (`hugging face` not `Hugging Face`) | Paraformer normalizes English to lowercase | Use case-insensitive anchor matching (shipped script handles this) |
| `WARN: anchor not found for X` from scene-anchor.py | Case mismatch OR audio doesn't say that exact phrase | Run `cat transcript.json` first, pick anchors from the actual ASR text |

## Resources Bundled With This Skill

- `scripts/fonts-download.sh` — bulletproof font download + WOFF2 conversion
- `scripts/voice-clone-template.py` — CosyVoice template (replace `input_text`)
- `scripts/transcribe-paraformer.py` — Paraformer ASR (handles sample_rate auto-detect)
- `scripts/scene-anchor.py` — anchor scenes to ASR word stream
- `scripts/check-cjk-fonts.py` — flags Chinese text inside Caveat/PatrickHand contexts before render
- `templates/design.md` — Rosé Pine Dawn boilerplate
- `templates/design-moon.md` — Rosé Pine Moon Serious boilerplate for dark technical/editorial videos
- `templates/composition-skeleton.html` — annotated index.html starting point
- `references/gotchas.md` — full pitfall catalog with reproductions
- `references/palettes.md` — style routing for Rosé Pine Dawn, Rosé Pine Moon Serious, warm-editorial, and dark-premium
- `references/script-templates.md` — narration patterns (interview-recap, news, tutorial, story)

## Red Flags — STOP if you see any of these

You are about to make a known mistake if you find yourself:

- **Writing the script without doing Phase 2 research first** (or skipping web_search/web_fetch)
- Reaching for `npx hyperframes transcribe` for Chinese audio
- Reaching for `npx hyperframes tts` because you forgot CosyVoice
- Picking system Chinese fonts via `fc-match`
- Adding `tl.from(el, { textContent: 0 })` for a number with units
- Setting Paraformer `sample_rate=16000`
- Running render with default `--workers auto`
- Using `Math.ceil` to compute `repeat:`
- Putting back-to-back audio clips with 3-decimal precision
- Using `[data-composition-id="..."]` as a CSS selector
- Putting Chinese text inside a Caveat/PatrickHand styled badge instead of splitting `.zh` and `.latin` spans

Stop and re-read the relevant Iron Rule above.
