---
name: topic-to-video
description: Use when the user provides a topic, article URL, or text and asks to make a short narrated video (typically 60-120s). Covers the full pipeline — topic research with web search, optional visual material search and processing, video understanding, script writing, CosyVoice cloned-voice TTS via DashScope, Paraformer ASR for word-level timestamps, scene timing, HyperFrames composition with GSAP image animation, lint/inspect, and rendering. Avoids 17+ pitfalls discovered in baseline testing.
---

# Topic → Video (HyperFrames + CosyVoice Workflow)

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
11. **Material search is optional but recommended.** Phase 3-4 can be skipped if user says "skip materials" or provides all visual content. But for most topics, searched images make scenes 10x more engaging than text-only.
12. **Image animations = GSAP in HTML, not FFmpeg.** Never pre-render Ken Burns clips with FFmpeg for HyperFrames compositions. Use GSAP zoompan/pan/fade animations on `<img>` elements directly. See `references/image-animations.md`.
13. **Downloaded assets go in the unified workspace tree, and every asset that reaches `index.html` must be cited by `material-catalog.json`.** Keep tool outputs under `~/.hermes/workspace/{topic_name}/` using the standard subdirectories (`extract_frames/`, `vision_analyze/`, `fonts/`, `verify/`, `renders/`). Copy needed files into the HyperFrames project dir before composing — but only files referenced by a `material_ref` in scenes-config. No catalog citation → no asset on screen.
14. **Material selection happens in Phase 4, not Phase 5.** The agent picks 3-6 URLs in Phase 3 and passes them as one array to `harvest-pages.py`. In Phase 4, run vision-analyze on every image and every video's extracted frames, then write `material-catalog.json` with `selected_clips`. The narration script (Phase 5) only references catalog entries — never a raw harvest result. Prevents writing a scene around a video span that turns out to be a transition or an ad.

## Output Conventions

All scripts in this skill follow a unified output protocol:

### Workspace Layout

Each video project lives under `~/.hermes/workspace/{topic_name}/`, where `topic_name` is a 2-5 word slug derived from the topic (e.g., `claude-code-review`, `gpu-ai-training`). Tool outputs go into per-tool subdirectories:

```
~/.hermes/workspace/{topic_name}/
├── harvest_page/               # Phase 3: per-URL harvest results (one call to harvest-pages.py)
│   ├── manifest.json
│   └── <url-slug>/
│       ├── metadata.json
│       ├── images/
│       ├── videos/
│       ├── recording/          # only for scroll-record mode
│       └── page-source.html
├── extract_frames/             # Phase 4: per-video frame extracts (one subdir per video)
│   └── <url-slug>/<video-name>/frame_*.jpg
├── vision_analyze/             # Phase 4: per-URL vision results
│   └── <url-slug>/analysis.json
├── material-catalog.json       # Phase 4: filtered, scored material catalog
├── voice_clone/                # Phase 6: TTS audio
│   └── narration.mp3
├── transcribe/                 # Phase 7: ASR transcript and scene timing
│   ├── transcript.json
│   └── scene-timing.json
├── fonts/                      # Phase 9: Downloaded font assets
│   ├── *.woff2
│   └── rose-pine-moon-fonts.css
├── narration.txt               # Phase 5: Narration script (written by agent)
├── scenes-config.json          # Phase 7: Scene config (written by agent)
├── index.html                  # Phase 10: HyperFrames composition
├── images/                     # Phase 10: Images copied for composition
├── verify/                     # Phase 11: Verification frames
│   └── f-*s.jpg
└── renders/                    # Phase 11: Final video output
    ├── draft.mp4
    └── {topic_name}-final.mp4
```

Plus one shared (cross-topic) browser profile reused across the `harvest-pages.py` tool and TuberUp's `gemini-deep-research`:

`~/.hermes/workspace/chrome_profile/` — do NOT delete; cookies, logins, and site preferences accumulate here.

### Script I/O Protocol

Every script emits **JSON to stdout** and **human-readable logs to stderr**:

- **stdout** (machine-readable): `{"success": true, ...}` or `{"success": false, "error": "..."}`
- **stderr** (human-readable): Progress and errors prefixed with `[tool-name]`, e.g., `[extract-frames] Probing duration...`
- **Exit codes**: `0` = success, `1` = runtime error, `2` = invalid arguments

Parse script results with: `result=$(python3 script.py ... 2>/dev/null)` or capture both channels separately.

## Workflow (11 Phases)

### Phase 1 — Gather Inputs (ask user, ONE question at a time)

1. Source: URL to fetch, pasted text, or just a topic.
2. Orientation: `1920×1080` (horizontal), `1080×1920` (vertical), or `1080×1440` (3:4 portrait).
3. Style: read `style-prompt.md` if it exists in cwd, else infer from user wording:
   - Default: Rosé Pine Dawn handdrawn (`templates/design.md`)
   - Use Rosé Pine Moon Serious (`templates/design-moon.md`) when the user says "moon", "严肃", "深色", "技术感", "技术评论", "AI", "SaaS", or "编程" and wants a serious tone
   - If topic is AI/SaaS/programming but style is not explicit, ask whether they want Dawn warm explainer or Moon serious technical editorial
4. Length: usually 60-120s — derive from user's request or default to 75-90s.
5. Language: default Chinese. Ask if user wants a different language.
6. Ask whether to search for visual materials (images/video clips) to enrich scenes. Default: yes.

**If a sister project already exists** (e.g. user says "same style as `claude-code-video/`"), copy `design.md` + `fonts/` from it and skip phase 9.

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

### Phase 3 — Material Harvest

The agent (LLM) produces a short list of URLs likely to yield rich visual material, then runs `harvest-pages.py` ONCE with the whole list. The tool decides per-URL whether to extract images/videos or screen-record a top-to-bottom scroll.

#### URL selection rules (use these to build the array)

Aim for **3-6 URLs**. INCLUDE pages of these types:

| Page type                                | Why it's a good source                              | Typical mode  |
|------------------------------------------|-----------------------------------------------------|---------------|
| Official product/project homepage         | Hero shots, screenshots, product video             | media         |
| GitHub repository main page               | README screenshots, demo gifs, social preview      | media         |
| Official documentation landing page       | Diagrams, architecture; OR long text               | media or scroll-record |
| Official blog post / launch announcement  | Inline images, embedded YouTube                    | media         |
| Wikipedia article (for established topics)| Infobox images, well-edited prose                  | scroll-record |
| Conference talk / keynote YouTube page    | Downloaded via yt-dlp                              | media         |
| Author's personal site / about page       | Headshots, banners                                 | media         |

EXCLUDE (low yield, often bot-blocked):

- Search result pages (Google, Bing) — not destinations
- Social media feeds (Twitter/X timelines, LinkedIn feeds) — login walls
- Aggregator listicles ("Top 10 AI tools…") — stock images
- Paywalled news article body pages — blocked content
- App store listings — small thumbnails only
- PDFs — not supported; download with `curl` and treat as a flat material

Sources for picking URLs (in order of preference):

1. The URL the user provided (always include if they gave one).
2. URLs surfaced during Phase 2 research (web_search results) matching the page types above. Prefer official-domain URLs over secondary coverage.
3. If still <3 URLs, run one more web_search like `"{topic} official site"`, `"{topic} github"`, `"{topic} documentation"`.

#### Running harvest-pages.py

```bash
scripts/harvest-pages.py \
  --urls https://anthropic.com/news/claude-code \
         https://github.com/anthropics/claude-code \
         https://docs.anthropic.com/claude-code \
         https://www.youtube.com/watch?v=... \
  --output-dir ~/.hermes/workspace/{topic_name}/harvest_page/
```

The first invocation launches Chrome at `~/.hermes/workspace/chrome_profile`; subsequent invocations reuse it over CDP (`http://localhost:9222`). Chrome stays running between calls. Per-URL failures don't sink the batch.

Outputs: `harvest_page/manifest.json` + `harvest_page/<url-slug>/` directories (one per URL). See the `manifest.entries[]` shape — each entry has `page_type`, `mode`, `text_excerpt`, `images[]`, `videos[]`, and optional `scroll_recording`.

### Phase 4 — Material Understanding & Selection

Iterate over `harvest_page/manifest.json["entries"]` from Phase 3. For each entry, build a "material entry" in `~/.hermes/workspace/{topic_name}/material-catalog.json`.

**Per harvested entry (one per URL):**

1. **Extract frames** from every video in `entry.videos` AND from `entry.scroll_recording` (if present):
   ```bash
   scripts/extract-frames.py <video> \
     ~/.hermes/workspace/{topic_name}/extract_frames/<slug>/<video-name>/ \
     --max-frames 16
   ```
   Frames are timestamp-named (`frame_t00.5s.jpg` etc.) so we can map back to clip ranges.

2. **Parse subtitles** for every downloaded video that has a sidecar subtitle file:
   ```bash
   scripts/subtitle-parse.py <subtitle> --keywords '<terms from research brief>'
   ```

3. **Vision analysis** with `scripts/vision-analyze.py`:
   - For images: one batch per URL (max 10 per call). Prompt asks for subject, visual style, suitability score 1-10.
   - For each video: one batch on the extracted frames. Prompt additionally asks for start/end timestamp of the most relevant span.
   - **Mode 1 (explicit VLM):** if `VLM_API_KEY` + `VLM_BASE_URL` + `VLM_MODEL` are set → direct OpenAI-compatible call.
   - **Mode 2 (delegate):** otherwise → script returns `delegate_to_agent` with image paths; the agent uses its own `view` tool.

4. **Combine** `entry.text_excerpt` + image descriptions + per-frame descriptions into the catalog entry. **CRITICAL:** for each video, write a `selected_clips` list of `{start, end, reason, frame_paths[]}` — these are the spans Phase 5 (narration) and Phase 10 (compose) draw from.

5. **Filter:** drop assets the VLM rated <5/10 or that are off-topic. Don't carry junk into the narration phase.

**`material-catalog.json` shape:**

```json
{
  "topic_name": "...",
  "entries": [
    {
      "url": "...", "slug": "...", "title": "...", "page_type": "...",
      "text_excerpt": "...",
      "images": [
        {"id": "img_001", "local_path": ".../images/img_001.webp", "semantic_description": "...", "score": 8}
      ],
      "videos": [
        {
          "id": "2MJDdzSXL74",
          "local_path": ".../videos/2MJDdzSXL74.webm",
          "semantic_description": "...",
          "selected_clips": [
            {"start": 12.0, "end": 18.5, "reason": "...", "frame_paths": [...]}
          ]
        }
      ]
    }
  ]
}
```

- `entries[*].slug` is unique per URL and matches the harvest output directory name.
- Each image/video gets an `id` (the file stem the harvester already wrote, e.g. `img_001` or the YouTube video id). Scenes in Phase 7 reference materials by `{entry_slug, asset_id}` — never by raw `local_path`, which is brittle.
- `semantic_description` is the VLM-generated caption; Phase 10 uses it to pick the best GSAP effect.

**Outputs:** `extract_frames/<slug>/<video-name>/`, `vision_analyze/<slug>/`, `material-catalog.json`.

### Phase 5 — Write Narration Script

**Inputs:** the research brief from Phase 2 + `material-catalog.json` from Phase 4 + the user's preferred angle/length. Reference specific catalog entries when annotating each scene's recommended visual — cite them as `{entry_slug, asset_id}` (and `clip_index` for video chunks); the actual `local_path` resolution happens in Phase 10.

Goals:
- Use **only facts from the research brief** — every number, name, date, and quote must be traceable.
- Reference the collected materials where helpful, and annotate each scene with recommended visual material.
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
python3 voice-clone.py --output-dir ~/.hermes/workspace/{topic_name}/voice_clone
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 ~/.hermes/workspace/{topic_name}/voice_clone/narration.mp3
```

If duration is much longer than user wanted, retry with higher `speech_rate` (1.5 default; try 1.7 for shorter, 1.2 for slower).

### Phase 7 — ASR + Scene Anchoring

Run `scripts/transcribe-paraformer.py ~/.hermes/workspace/{topic_name}/voice_clone/narration.mp3 ~/.hermes/workspace/{topic_name}/transcribe/transcript.json`.

Then design 8-10 scenes, each with:
- `id` (e.g. `s1-hook`, `s2-stat`)
- `anchor` (a 4-8 char substring that appears uniquely in the ASR text, signalling this scene starts when this phrase is spoken)
- `display_text` (what shows on screen — usually different from spoken text, much shorter)
- `material_ref` (required) — `{ entry_slug, kind: "image" | "video_clip", asset_id, clip_index?: int }`. Picks one asset from `~/.hermes/workspace/{topic_name}/material-catalog.json`: locate the entry where `entries[*].slug == entry_slug`, then locate the image (`kind=image`) or video (`kind=video_clip`) where `id == asset_id`. When `kind = video_clip`, `clip_index` (0-based) points at the chosen item inside that video's `selected_clips`.

**Every scene must cite at least one catalog entry.** If no harvested material fits a scene, go back to Phase 3 and harvest more URLs — never invent assets or fall back to a generic stock image. This is the structural guarantee that the materials gathered by `harvest-pages.py` actually reach the final video.

Run `scripts/scene-anchor.py ~/.hermes/workspace/{topic_name}/transcribe/transcript.json scenes-config.json ~/.hermes/workspace/{topic_name}/transcribe/scene-timing.json` to get exact `begin_ms`/`duration_ms` per scene.

### Phase 8 — Scaffold + Install

```bash
# Run from a parent directory that already has hyperframes installed
./node_modules/.bin/hyperframes init <project-name> --example blank --non-interactive

# If hyperframes not installed, install with --ignore-scripts
# (onnxruntime-node postinstall fails on this network)
npm install --no-save --ignore-scripts hyperframes
```

### Phase 9 — Fonts (one-time per project)

Download the fonts for the selected style as local deterministic WOFF2 assets:

```bash
# Dawn default handdrawn style
bash scripts/fonts-download.sh ~/.hermes/workspace/{topic_name}/fonts dawn

# Moon serious technical/editorial style
bash scripts/fonts-download.sh ~/.hermes/workspace/{topic_name}/fonts moon

# If creating a reusable project template that may switch styles later
bash scripts/fonts-download.sh ~/.hermes/workspace/{topic_name}/fonts all
```

### Phase 10 — Compose `index.html`

Read `templates/composition-skeleton.html` for the skeleton. Key conventions:

- Root: `<div id="root" data-composition-id="main" data-start="0" data-duration="<TOTAL_S>" data-width="<W>" data-height="<H>">`
- Background ambient div: `class="clip"`, full-duration, contains grain + drifting doodles.
- One `<audio class="clip">` for narration on a high track-index.
- One `<div class="scene clip s<N>">` per scene, with exact `data-start` / `data-duration` from scene-timing.json.
- **Resolve each scene's `material_ref` against `material-catalog.json` BEFORE writing the `<img>` / `<video>` tags:**
  - Look up `entries[*]` where `slug == material_ref.entry_slug`, then look up the image / video where `id == material_ref.asset_id`.
  - `kind = image` → copy the resolved asset's `local_path` into the project's `images/` directory, embed as `<img>` inside the scene div, and pick a GSAP animation effect from `references/image-animations.md` using the catalog asset's `semantic_description` plus the scene's intent (table below).
  - `kind = video_clip` → resolve the same way, then cut the chosen item from `selected_clips[clip_index]` (use `ffmpeg -ss <start> -to <end> -i <local_path> -c copy ...`) into the project's `videos/` directory, embed as `<video class="clip" data-start="..." data-duration="..." muted>` instead of `<img>`, and **skip the GSAP image-animation step** for that scene — the clip itself carries the motion.
  - Never reference `local_path` values that aren't reachable through a `material_ref → entry_slug → asset_id` lookup. If a scene's recommended visual doesn't exist in the catalog, go back to Phase 3 (harvest more URLs) or Phase 4 (re-run vision-analyze and re-filter).
- **13 GSAP image animation effects available** — see `references/image-animations.md` for complete code templates. Quick selection guide:

  | Scene type | Recommended effect |
  |------------|-------------------|
  | One strong image + documentary / emotional | Ken Burns |
  | Panorama / dashboard | Pan |
  | 2-4 related stills in progression | Slideshow Fade |
  | Compare multiple sources at once | Grid Layout |
  | Rapid walk-through of many examples | Montage |
  | Depth feel (subject + background) | Parallax |
  | Suspense reveal / before-after | Reveal/Wipe |
  | Highlight a specific region | Zoom to Detail |
  | Long screenshot / code / webpage | Vertical Pan |
  | A vs B comparison | Split Screen |
  | Main image + auxiliary context | Picture-in-Picture |
  | Suspenseful opening / focus shift | Blur-to-Sharp |
  | Energetic entrance / product showcase | Scale Bounce |
  | A harvested video clip from `material-catalog.json` | *(none — use `<video class="clip">`, not `<img>`; the clip carries its own motion)* |

- Use `object-fit: cover` + `overflow: hidden` on image containers.
- Layer text over images with `z-index` + a semi-transparent overlay for readability.
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

### Phase 11 — Verify + Render

```bash
cd <project>
../node_modules/.bin/hyperframes lint        # MUST: 0 errors
../node_modules/.bin/hyperframes inspect     # MUST: 0 layout issues
python3 /home_ext/ljie/.copilot/skills/topic-to-video/scripts/check-cjk-fonts.py index.html
# Optionally: validate (WCAG contrast — Rosé Pine Dawn is muted, expect informational warnings)

# Draft render to verify visually before committing to high-quality
../node_modules/.bin/hyperframes render --quality draft --workers 1 --output renders/draft.mp4

# Extract sample frames at scene boundaries (every ~10s)
mkdir -p verify
for t in 2 13 24 33 42 52 60 68 73; do
  ffmpeg -y -ss $t -i renders/draft.mp4 -frames:v 1 -q:v 2 verify/f-${t}s.jpg 2>/dev/null
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
| `vision-analyze.py` returns `mode: "delegate_to_agent"` | `VLM_API_KEY` not set — this is **not** an error | Either set `VLM_API_KEY`/`VLM_BASE_URL`/`VLM_MODEL` for explicit VLM, OR honor the directive: use your `view` tool on each path in `images.local` |
| `vision-analyze.py` errors with "VLM_API_KEY is set but missing required config" | Partial VLM_* setup | Set both `VLM_BASE_URL` and `VLM_MODEL` (or pass `--model`) |
| Images don't render in HyperFrames | Image path not relative to project dir | Copy images into project dir; use relative paths in `<img src>` |
| Ken Burns animation jitters | Image too small, upscaled poorly | Use source images ≥1920px wide; `object-fit: cover` |
| `harvest-pages.py` blocked by cookie banner | EU/cookie wall absorbs scroll/clicks | Re-run after accepting the banner once in the shared profile (`~/.hermes/workspace/chrome_profile`) — cookie state persists across CDP sessions |
| `harvest-pages.py` returns 0 images on a real gallery | Lazy-loaded images need scroll | Already handled (auto-scroll-to-bottom); if still 0, raise `--page-load-timeout` |
| YouTube download fails with 410 / geoblock | yt-dlp upstream issue | Skip that video; pick a re-uploaded mirror via web_search |
| Playwright import error | venv missing playwright | `pip install playwright` — NO `playwright install chromium` (we use system Chrome over CDP) |
| `Chrome exited immediately` from `harvest-pages.py` | Profile dir already locked by another Chrome | Close other Chrome instances using `~/.hermes/workspace/chrome_profile`, or pass a different `--profile-dir` |
| Chrome exits with `Missing X server or $DISPLAY` | No display in container/SSH session | `harvest-pages.py` auto-detects this (`--headless auto` checks `DISPLAY`). Force with `--headless on` if auto-detect misfires |
| Chrome exits with sandbox errors as root | Running inside a container | `--no-sandbox` is auto-enabled when running as root or inside Docker; pass explicitly with `--no-sandbox` if needed |
| CDP port 9222 busy with the wrong Chrome | Another tool launched Chrome on that port | If it's a Chrome we WANT, that's fine (reuse). If not, pass `--cdp-url http://localhost:9223` |
| `harvest-pages.py` picks search-result pages | Agent included google.com/bing.com in `--urls` | Re-read Phase 3 URL selection rules; exclude search/feed/aggregator pages |
| Scene references an asset not in `material-catalog.json` | Phase 7 wrote a `material_ref` whose `entry_slug`/`asset_id` pair doesn't resolve in the catalog, or skipped `material_ref` entirely | Re-run Phase 4 vision-analyze and re-build the catalog; every scene must have a `material_ref` that resolves via `entry_slug → asset_id` (and `clip_index` for videos). If no entry fits, harvest more URLs (Phase 3) — do not invent or borrow generic stock assets |
| HyperFrames scene shows nothing where a video clip was planned | Embedded the full source video instead of cutting `selected_clips[clip_index]`, OR added a GSAP image animation on top of a `<video>` element | Use `ffmpeg -ss <start> -to <end>` to cut the clip into the project's `videos/` dir; embed as `<video class="clip">` with no GSAP animation — the clip carries its own motion |

## Resources Bundled With This Skill

> All scripts follow the unified I/O protocol: JSON stdout, `[tool-name]` stderr logs, exit codes 0/1/2. See "Output Conventions" above.

- `scripts/fonts-download.sh` — bulletproof font download + WOFF2 conversion
- `scripts/voice-clone-template.py` — CosyVoice template (replace `input_text`)
- `scripts/transcribe-paraformer.py` — Paraformer ASR (handles sample_rate auto-detect)
- `scripts/scene-anchor.py` — anchor scenes to ASR word stream
- `scripts/check-cjk-fonts.py` — flags Chinese text inside Caveat/PatrickHand contexts before render
- `scripts/extract-frames.py` — FFmpeg frame extraction (uniform sampling or time window)
- `scripts/subtitle-parse.py` — SRT/VTT parser with keyword filtering
- `scripts/vision-analyze.py` — model-agnostic vision analysis: calls any OpenAI-compatible VLM via `VLM_API_KEY` + `VLM_BASE_URL` + `VLM_MODEL`, or delegates to the agent's `view` tool when no VLM is configured
- `scripts/harvest-pages.py` — Playwright/CDP batch URL harvester: takes an array of URLs (official sites, GitHub, docs, etc.), extracts ≥512px images and embedded videos per URL, OR records a scroll-through video for text-heavy pages. Reuses one Chrome process across the whole batch.
- `scripts/video-download.py` — yt-dlp wrapper used by `harvest-pages.py` to download YouTube/Bilibili videos with subtitles
- `templates/design.md` — Rosé Pine Dawn boilerplate
- `templates/design-moon.md` — Rosé Pine Moon Serious boilerplate for dark technical/editorial videos
- `templates/composition-skeleton.html` — annotated index.html starting point
- `references/gotchas.md` — full pitfall catalog with reproductions
- `references/palettes.md` — style routing for Rosé Pine Dawn, Rosé Pine Moon Serious, warm-editorial, and dark-premium
- `references/script-templates.md` — narration patterns (interview-recap, news, tutorial, story)
- `references/image-animations.md` — GSAP image animation patterns (Ken Burns, pan, slideshow, grid, montage)

## Dependencies for Material Tools

The material processing scripts require additional dependencies beyond the base skill:

- **ffmpeg/ffprobe** (for frame extraction): usually pre-installed on Linux
- **playwright** (Python bindings only, ~3 MB) for `harvest-pages.py`: `pip install playwright`. NO `playwright install chromium` — we attach to system Chrome over CDP.
- **system Chrome** (already at `/usr/bin/google-chrome` on this machine): auto-launched on demand with `--remote-debugging-port=9222 --user-data-dir=~/.hermes/workspace/chrome_profile`. Shared with the `gemini-deep-research` agent so cookies/logins persist.
- **yt-dlp** (for `video-download.py`): on PATH (`/home/jieliu1/.local/bin/yt-dlp`).
- **vision model** (optional): set `VLM_API_KEY` + `VLM_BASE_URL` + `VLM_MODEL` to enable `vision-analyze.py` Mode 1 (e.g. point at DashScope's OpenAI-compatible endpoint with `qwen-vl-max`). When unset, the script delegates to the calling agent's own `view` tool — no extra dependency required.

## Red Flags — STOP if you see any of these

You are about to make a known mistake if you find yourself:

- **Writing the script without doing Phase 2 research first** (or skipping web_search/web_fetch)
- **Pre-rendering Ken Burns clips with FFmpeg** instead of using GSAP in HyperFrames HTML
- **Skipping vision-analyze** when you have 20+ frames and need to pick the best 3-4
- Writing narration before running vision-analyze on harvested videos and building `material-catalog.json`
- **Designing a scene without a `material_ref`** into `material-catalog.json`, or referencing an `<img src>` / `<video src>` whose path is not a catalog entry
- **Adding a GSAP image animation on top of a `<video>` clip** — clips already carry motion; pick one or the other
- **Embedding the full source video** instead of an ffmpeg-cut `selected_clips[i]` range
- **Using absolute paths** for images in index.html (breaks HyperFrames render)
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
