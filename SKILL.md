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

## Iron Rules (Non-Negotiable)

These rules each prevent a specific bug a baseline agent hit. **Do not "improve" past them without re-running the gauntlet** in `references/gotchas.md`.

0. **Research before script.** Phase 2 is mandatory. Do not draft a single line of narration before fetching the source URL (if any) and running web_search to verify names, dates, numbers, and quotes. Untruthful video = useless video.
1. **TTS = CosyVoice via DashScope, not Kokoro.** User has a cloned voice. Use `scripts/voice-clone-template.py`. NEVER use `npx hyperframes tts` (Kokoro) for Chinese — it's not their voice.
2. **ASR = DashScope Paraformer-realtime-v2, not Whisper.** `npx hyperframes transcribe` for Chinese fails with empty errors, UTF-8 fragmentation, and slow downloads. Use `scripts/transcribe-paraformer.py`.
3. **Paraformer `sample_rate` MUST match the actual audio sample rate.** CosyVoice MP3 = `22050`. Default 16000 silently fails with `status_code=44 "sample rate 16000 not equals with real 22050"`.
4. **Always `source .venv/bin/activate` before Python.** `dashscope` is in the venv. Use `python3` (no `python` alias).
5. **Use Google Fonts woff2, never `fc-match` system fonts.** System Chinese fonts (e.g. `AR PL UKai CN`) trigger `[Compiler] No deterministic font mapping` at render. Download the selected style's fonts with `scripts/fonts-download.sh`: Dawn = handdrawn fonts; Moon = `NotoSerifSC`/`NotoSansSC`/`IBMPlexMono`.
6. **`Caveat` and `PatrickHand` have NO Chinese glyphs.** They are Dawn-only English/numeric handwriting fonts. For Dawn mixed Chinese + Latin text, split by script: Chinese spans use `MaShanZheng`/`LongCang`; English/numeric spans use `Caveat`/`PatrickHand`. For Moon, use `NotoSerifSC`/`NotoSansSC` for Chinese and `IBMPlexMono` for English/data/code. Do not rely on fallback chains for mixed badges.
7. **Material search is optional but recommended.** Phase 3-4 can be skipped if user says "skip materials" or provides all visual content. But for most topics, harvested images and clips make scenes 10× more engaging than text-only.
8. **Every on-screen asset must trace to `material-catalog.json`.** Keep tool outputs under `{work_dir}/{topic_name}/` using the standard subdirectories (`harvest_page/`, `extract_frames/`, `vision_analyze/`, `fonts/`, `composition/`). The coding sub-agent in Phase 8 resolves `material_ref` → catalog entry → `local_path`; no catalog citation → no asset on screen. Never invent or borrow generic stock assets.
9. **Material selection happens in Phase 4, not Phase 5.** The agent picks 3-6 URLs in Phase 3 and passes them as one array to `harvest-pages.py`. In Phase 4, run vision-analyze on every image and every video's extracted frames, then write `material-catalog.json` with `selected_clips`. The narration script (Phase 5) only references catalog entries — never a raw harvest result. Prevents writing a scene around a video span that turns out to be a transition or an ad.
10. **Composition + render is delegated.** Phases 8 onward run in a coding sub-agent (Copilot CLI / Claude Code) with the `hyperframes` skill loaded — not in the main agent. The main agent's job ends at producing the inputs the brief points at; the sub-agent owns scaffold / DESIGN.md / composition / lint / render. Do not try to hand-write `index.html` from the main conversation.

## Checkpoint & Resume

**Before running any tool, check if its output already exists in the workspace.** If a previous run (or a previous session) already produced the expected output files, skip the tool and reuse the existing results. This enables resuming from any breakpoint without re-running expensive operations (TTS, ASR, Gemini Deep Research, harvest, etc.).

### Per-Phase Skip Conditions

| Phase | Tool / Action | Skip if these files exist | What to do on skip |
|-------|--------------|--------------------------|-------------------|
| 2 | `gemini-deep-research.py` | `gemini_deep_research.md` (non-empty) | Read the existing report; proceed to gap-filling web_search |
| 3 | `harvest-pages.py` | `harvest_page/manifest.json` with non-empty `entries[]` | Read manifest; proceed to Phase 3.b |
| 3.b | `video-download.py` (per URL) | Target video file exists in `harvest_page/<slug>/videos/` AND `metadata.json` has `download_required: false` | Skip that URL's download |
| 4 | `extract-frames.py` (per video) | `extract_frames/<slug>/<video>/` dir with ≥1 JPEG | Skip extraction for that video |
| 4 | `vision-analyze.py` (per asset) | Asset already has `semantic_description` in `material-catalog.json` | Skip vision analysis for that asset |
| 4 | `material-catalog.json` | File exists with `entries[].selected_clips` populated | Skip entire Phase 4; read catalog directly |
| 5 | narration script | `narration.txt` exists (non-empty) | Read it; still show to user for approval before Phase 6 |
| 6 | `voice-clone-template.py` | `voice_clone/narration.mp3` exists | Skip TTS; verify duration with ffprobe |
| 7 | `transcribe-paraformer.py` | `transcribe/transcript.json` exists (non-empty) | Skip ASR |
| 7 | `scene-anchor.py` | `transcribe/scene-timing.json` exists (non-empty) | Skip anchoring |
| 7.5 | `fonts-download.sh` | `fonts/` dir contains ≥1 `.woff2` file | Skip font download |
| 8 | composition sub-agent | `composition/renders/final.mp4` exists | Skip composition; verify video playability |

### Resume Behavior

1. **Workspace discovery happens in Phase 1** — after the `topic_name` slug is determined. The agent checks if `{work_dir}/{topic_name}/` exists, scans for outputs, and asks the user whether to resume or start fresh. This is the entry point for all checkpoint logic.
2. **At the start of each phase**, check the skip condition. Log what was found: `"Phase 3 checkpoint: harvest_page/manifest.json exists with 5 entries — skipping harvest-pages.py"`
3. **Read existing outputs** as if the tool just produced them. The downstream phases need the data, not the execution.
4. **If an output file exists but is corrupt or incomplete** (e.g., 0-byte file, truncated JSON), delete it and re-run the tool.
5. **User can force re-run** by saying "re-run phase N" or "redo harvest" — in that case, ignore the checkpoint and execute normally.
6. **Phase 1 has no file checkpoint** — it produces in-memory inputs. Phase 2's Gemini Deep Research has a file checkpoint (`gemini_deep_research.md` — see table above), but the web_search gap-filling steps produce in-memory results only. If resuming after a context reset, ask the user if they want to skip research.

## Output Conventions

All scripts in this skill follow a unified output protocol:

### Workspace Layout

`{work_dir}` is the root directory for all project outputs. It defaults to the current working directory (`.`) but can be overridden by the caller via `work_dir` or `workDir` parameter when invoking the skill. All tool `--output-dir` arguments and file paths in this document are relative to `{work_dir}`.

Each video project lives under `{work_dir}/{topic_name}/`, where `topic_name` is a 2-5 word slug derived from the topic (e.g., `claude-code-review`, `gpu-ai-training`). Tool outputs go into per-tool subdirectories:

```
{work_dir}/{topic_name}/
├── harvest_page/               # Phase 3: per-URL harvest results (one call to harvest-pages.py)
│   ├── manifest.json            #   ↳ contains entries[] and pending_downloads[] (Phase 3.b feeds these to video-download.py)
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
├── fonts/                      # Phase 7.5: Downloaded font assets (pre-staged for the sub-agent)
│   ├── *.woff2
│   └── rose-pine-moon-fonts.css
├── narration.txt               # Phase 5: Narration script (written by agent)
├── composition-brief.md        # Phase 8: Brief handed to the coding sub-agent
└── composition/                # Phase 8: HyperFrames project owned by the sub-agent
    ├── index.html              #   ↳ scaffolded via `hyperframes init`
    ├── DESIGN.md               #   ↳ palette/typography/motion gate
    ├── fonts/ images/ videos/  #   ↳ symlinked or copied from the workspace
    └── renders/final.mp4       #   ↳ rendered with --workers 1
```

Plus one shared (cross-topic) browser profile reused across `harvest-pages.py` and `gemini-deep-research.py`:

`{work_dir}/chrome_profile/` — do NOT delete; cookies, logins, and site preferences accumulate here.

### Script I/O Protocol

Every script emits **JSON to stdout** and **human-readable logs to stderr**:

- **stdout** (machine-readable): `{"success": true, ...}` or `{"success": false, "error": "..."}`
- **stderr** (human-readable): Progress and errors prefixed with `[tool-name]`, e.g., `[extract-frames] Probing duration...`
- **Exit codes**: `0` = success, `1` = runtime error, `2` = invalid arguments

Parse script results with: `result=$(python3 script.py ... 2>/dev/null)` or capture both channels separately.

## Workflow (8 Phases)

### Phase 1 — Gather Inputs (ask user, ONE question at a time)

1. Source: URL to fetch, pasted text, or just a topic.
2. Orientation: `1920×1080` (horizontal), `1080×1920` (vertical), or `1080×1440` (3:4 portrait).
3. Style: read `style-prompt.md` if it exists in cwd, else infer from user wording:
   - Default: Rosé Pine Dawn handdrawn (`references/design-dawn.md`)
   - Use Rosé Pine Moon Serious (`references/design-moon.md`) when the user says "moon", "严肃", "深色", "技术感", "技术评论", "AI", "SaaS", or "编程" and wants a serious tone
   - If topic is AI/SaaS/programming but style is not explicit, ask whether they want Dawn warm explainer or Moon serious technical editorial
4. Length: usually 3-10 minutes — derive from user's request or default to 5 minutes.
5. Language: default Chinese. Ask if user wants a different language.
6. Ask whether to search for visual materials (images/video clips) to enrich scenes. Default: yes.

**If a sister project already exists** (e.g. user says "same style as `claude-code-video/`"), copy `composition/DESIGN.md` + `fonts/` from it and note "reuse this DESIGN.md" inside the brief; the sub-agent will skip fresh design and font work.

**Workspace discovery (checkpoint entry point):** After determining the `topic_name` slug, check if `{work_dir}/{topic_name}/` already exists:
```
ls {work_dir}/{topic_name}/ 2>/dev/null
```
If the directory exists and contains output files, scan against the checkpoint table (see "Checkpoint & Resume" section) and report to the user:
> "Found existing workspace for `{topic_name}`. Detected outputs: [harvest (5 URLs), TTS, ASR, scene-timing]. Resume from Phase 5 (narration)? Or start fresh?"

Wait for user confirmation before proceeding. This is the **only** mechanism by which the agent discovers a prior run — without a workspace directory, there is nothing to resume from.

### Phase 2 — Topic Research (CRITICAL — do this BEFORE writing)

**Never write a script from your training data alone.** A 60-second video has no room for vague claims, and any factual error becomes a 60-second mistake. Ground every claim in fresh, citeable sources.

**Process:**

1. **If the user gave a URL** → `web_fetch` it FIRST. Read the full content. This is the spine of the video.
2. **Run Gemini Deep Research** (when available). This is the primary research backbone — it produces a comprehensive, sourced report far richer than manual web searches.
   ```bash
   scripts/gemini-deep-research.py \
     --prompt "Comprehensive overview of [topic]: history, key developments, notable figures, technical details, latest news" \
     --output-dir {work_dir}/{topic_name}/
   ```
   - Outputs: `gemini_deep_research.md` (full report) + `gemini_deep_research_sources.json` (cited URLs)
   - Read the report; it becomes the primary source. The `sources.json` feeds into Phase 3 material harvest.
   - **Skip Gemini Deep Research when:** Gemini login unavailable (not logged in via the shared Chrome profile), user says "skip deep research", or topic is a simple re-narration of user-provided text.
   - **If it fails:** Fall back to manual web_search workflow (steps 3-4 below become the primary research path). Check `failed_step` in the error JSON — you can retry with `--start-from-step N`.
3. **Identify gaps.** Whether Gemini ran or not, check: what numbers, names, dates, or technical specifics are missing or unverified? List them.
4. **Run targeted searches.** Use `web_search` for each gap — typical: 2-4 searches if Gemini ran (filling gaps), 3-6 if it didn't (full research). Examples:
   - "Boris Cherny Anthropic interview Sequoia 2026" → confirm names, dates, quotes
   - "Claude Code MCP launch date" → date specifics
   - "GPU vs CPU AI training memory bandwidth" → technical numbers
5. **Synthesize a research brief** in your scratchpad. Format:
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

   ## Source URLs (for Phase 3 harvest)
   - [url] — [page type: official site / blog / GitHub / docs / YouTube]
   - [url] — [page type]
   ...
   ```
   The **Source URLs** section is critical — it's the explicit handoff to Phase 3. Populate from:
   1. The user-provided URL (always first).
   2. URLs from `gemini_deep_research_sources.json`, filtered to match Phase 3's INCLUDE page types (official sites, GitHub, docs, blogs, YouTube — not aggregators or social feeds).
   3. URLs discovered via `web_search` that match INCLUDE page types.
   Aim for **4-8 source URLs** covering diverse visual material types.
6. **Show the research brief to the user before writing the script.** They may add context, correct a misreading, or narrow the angle. ~1 round of feedback typically.

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
2. URLs listed in the research brief's **Source URLs** section — these were pre-filtered during Phase 2 to match harvest-worthy page types.
3. URLs from `gemini_deep_research_sources.json` (if Gemini Deep Research ran) not already covered above — filter against the INCLUDE/EXCLUDE rules.
4. If still <3 URLs, run one more web_search like `"{topic} official site"`, `"{topic} github"`, `"{topic} documentation"`.

#### Running harvest-pages.py

```bash
scripts/harvest-pages.py \
  --urls https://anthropic.com/news/claude-code \
         https://github.com/anthropics/claude-code \
         https://docs.anthropic.com/claude-code \
         https://www.youtube.com/watch?v=... \
  --output-dir {work_dir}/{topic_name}/harvest_page/
```

The first invocation launches Chrome at `{work_dir}/chrome_profile`; subsequent invocations reuse it over CDP (`http://localhost:9222`). Chrome stays running between calls. Per-URL failures don't sink the batch.

Outputs: `harvest_page/manifest.json` + `harvest_page/<url-slug>/` directories (one per URL). See the `manifest.entries[]` shape — each entry has `page_type`, `mode`, `text_excerpt`, `images[]`, `videos[]`, and optional `scroll_recording`. The manifest also contains a top-level **`pending_downloads[]`** — every YouTube/Bilibili URL the harvester detected (either passed in `--urls` directly or found embedded on a page).

### Phase 3.b — Resolve pending video downloads

`harvest-pages.py` is a pure discovery tool: it downloads native HTML5 `<video>` clips inline (because those need the page's cookies/referer), but for YouTube and Bilibili it only **lists** the URLs. The agent must then call `video-download.py` per `pending_downloads[]` entry to actually fetch them:

```bash
# For each item in manifest.pending_downloads:
scripts/video-download.py \
  --url "<item.url>" \
  --output-dir "<item.suggested_output_dir>"
```

Rules:
- **Sequential**, not parallel — yt-dlp gets rate-limited and IP-throttled when fanning out.
- Use `item.suggested_output_dir` as-is; it is `harvest_page/<source_slug>/videos/` so downloaded files land alongside the native videos.
- After each successful download, **update the corresponding `videos[]` entry** in `harvest_page/<source_slug>/metadata.json` (and `manifest.json`): set `download_required: false`, add `local_path` (and `subtitle_path` if the JSON output lists one), and set `id` to the file stem (e.g. `2MJDdzSXL74`). Phase 4 reads these fields. If the entry has an `also_referenced_by: [slug, ...]` list, also update the same `videos[]` entry under each of those slugs' `metadata.json` (the harvester deduplicated identical URLs across pages to avoid redundant downloads — but every referring entry still needs the `local_path` populated for Phase 4 lookup).
- If `video-download.py` returns `{"success": false}` (geoblock, age-gate, 410, etc.), leave the entry with `download_required: true` and skip it — Phase 4 will ignore it. If the topic depends on that exact clip, run `web_search` for a re-uploaded mirror and rerun `harvest-pages.py` with the new URL.

This decoupling means `harvest-pages.py` runtime is dominated by Playwright (fast, deterministic) and yt-dlp failures are isolated to specific URLs, not the entire batch.

### Phase 4 — Material Understanding & Selection

**Delegate to a subagent.** This phase is context-heavy (vision analysis on many images/frames, 30-50+ tool calls). Spawn a subagent with the manifest path and research brief; it produces `material-catalog.json`. The main agent reads only the final catalog.

Iterate over `harvest_page/manifest.json["entries"]` from Phase 3. For each entry, build a "material entry" in `{work_dir}/{topic_name}/material-catalog.json`.

**Per harvested entry (one per URL):**

1. **Extract frames** from every video in `entry.videos` AND from `entry.scroll_recording` (if present):
   ```bash
   scripts/extract-frames.py <video> \
     {work_dir}/{topic_name}/extract_frames/<slug>/<video-name>/ \
     --max-frames 16
   ```
   Frames are timestamp-named (`frame_t00.5s.jpg` etc.) so we can map back to clip ranges.

2. **Parse subtitles** for every downloaded video that has a sidecar subtitle file:
   ```bash
   scripts/subtitle-parse.py <subtitle> --keywords '<terms from research brief>'
   ```

3. **Vision analysis** with `scripts/vision-analyze.py`:
   - For images (raster and SVG): one batch per URL (max 10 per call). Prompt asks for subject, visual style, suitability score 1-10. SVGs render natively in the browser and can be analyzed like raster images.
   - For each video: one batch on the extracted frames. Prompt additionally asks for start/end timestamp of the most relevant span.
   - **Mode 1 (explicit VLM):** if `VLM_API_KEY` + `VLM_BASE_URL` + `VLM_MODEL` are set → direct OpenAI-compatible call.
   - **Mode 2 (delegate):** otherwise → script returns `delegate_to_agent` with image paths; the agent uses its own `view` tool.

4. **Combine** `entry.text_excerpt` + image descriptions + per-frame descriptions into the catalog entry. **CRITICAL:** for each video, write a `selected_clips` list of `{start, end, reason, frame_paths[]}` — these are the spans Phase 5 (narration) and Phase 8 (compose) draw from.

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
- Every image/video carries an `id` (file stem the harvester wrote, e.g. `img_001` or the YouTube video id). Phases 5/7/8 cite materials via a **`material_ref`** — the schema is defined where it's first used in Phase 7. The coding sub-agent in Phase 8 resolves `material_ref` → catalog entry → `local_path`; the main agent never touches `local_path` directly.
- `semantic_description` is the VLM-generated caption; the sub-agent in Phase 8 uses it to pick an appropriate motion/GSAP effect.

**Outputs:** `extract_frames/<slug>/<video-name>/`, `vision_analyze/<slug>/`, `material-catalog.json`.

### Phase 5 — Write Narration Script

**Inputs:** the research brief from Phase 2 + `material-catalog.json` from Phase 4 + the user's preferred angle/length. Annotate each scene with a recommended `material_ref` (the full schema is defined in Phase 7); the actual `local_path` resolution happens later, inside the sub-agent in Phase 8.

Goals:
- Use **only facts from the research brief** — every number, name, date, and quote must be traceable.
- Reference the collected materials where helpful, and annotate each scene with recommended visual material.
- 3-10 minutes at `speech_rate=1.5` ≈ **8 chars/sec** → `3min ≈ 1440 chars`, `5min ≈ 2400 chars`, `10min ≈ 4800 chars`.
- 15-40 paragraphs (scaled to target duration), separated by blank lines (each ≈ one scene = 6-15s of audio).
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
python3 voice-clone.py --output-dir {work_dir}/{topic_name}/voice_clone
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {work_dir}/{topic_name}/voice_clone/narration.mp3
```

If duration is much longer than user wanted, retry with higher `speech_rate` (1.5 default; try 1.7 for shorter, 1.2 for slower).

### Phase 7 — ASR + Scene Anchoring

Run `scripts/transcribe-paraformer.py {work_dir}/{topic_name}/voice_clone/narration.mp3 {work_dir}/{topic_name}/transcribe/transcript.json`.

Then design scenes (one per narration paragraph — typically 15-40 for a 3-10 minute video), each with:
- `id` (e.g. `s1-hook`, `s2-stat`)
- `anchor` (a 4-8 char substring that appears uniquely in the ASR text, signalling this scene starts when this phrase is spoken)
- `display_text` (what shows on screen — usually different from spoken text, much shorter)
- `material_ref` (required) — `{ entry_slug, kind: "image" | "video_clip", asset_id, clip_index?: int }`. Picks one asset from `{work_dir}/{topic_name}/material-catalog.json`: locate the entry where `entries[*].slug == entry_slug`, then locate the image (`kind=image`) or video (`kind=video_clip`) where `id == asset_id`. When `kind = video_clip`, `clip_index` (0-based) points at the chosen item inside that video's `selected_clips`.

**Every scene must cite at least one catalog entry.** If no harvested material fits a scene, go back to Phase 3 and harvest more URLs — never invent assets or fall back to a generic stock image. This is the structural guarantee that the materials gathered by `harvest-pages.py` actually reach the final video.

Write the scene list to `{work_dir}/{topic_name}/transcribe/scenes-config.json` (intermediate file, consumed in the next step), then run `scripts/scene-anchor.py {work_dir}/{topic_name}/transcribe/transcript.json {work_dir}/{topic_name}/transcribe/scenes-config.json {work_dir}/{topic_name}/transcribe/scene-timing.json`. The script anchors each scene to the ASR word stream, computes `begin_ms` / `duration_s`, and **passes every per-scene field (including `material_ref` and `display_text`) straight through** to the output. `scene-timing.json` is the single authoritative input the Phase 8 brief points the sub-agent at — it contains both the timing and the `material_ref` per scene, so the sub-agent never needs to read `scenes-config.json`.

### Phase 7.5 — Pre-stage fonts (so the sub-agent doesn't re-download)

Download the fonts for the selected style as local deterministic WOFF2 assets into the workspace, where Phase 8's brief points the sub-agent:

```bash
# Dawn default handdrawn style
bash scripts/fonts-download.sh {work_dir}/{topic_name}/fonts dawn

# Moon serious technical/editorial style
bash scripts/fonts-download.sh {work_dir}/{topic_name}/fonts moon

# If creating a reusable project template that may switch styles later
bash scripts/fonts-download.sh {work_dir}/{topic_name}/fonts all
```

Why pre-stage instead of letting the sub-agent do it: this skill owns the CJK-font setup story (Iron Rules #5 and #6). Fonts in `{work_dir}/{topic_name}/fonts/` come from a known-good Google Fonts mirror; without them the sub-agent may regress to `fc-match` system fonts and trip the `[Compiler] No deterministic font mapping` failure at render time.

### Phase 8 — Hand off composition + render to a coding sub-agent

Everything from this point — scaffolding a HyperFrames project, deciding the look (`DESIGN.md`), composing `index.html` with GSAP, running `lint`/`inspect`, and rendering — is a deep iterative HTML+CSS+GSAP task with its own dedicated skill (`hyperframes`). It is owned by a **coding sub-agent**, not the main agent.

The main agent's job ends here: produce the upstream artifacts (`narration.mp3`, `scene-timing.json`, `material-catalog.json`, `narration.txt`, `fonts/`), write a brief, invoke the sub-agent, then sanity-check the resulting mp4.

The sub-agent's job is to turn those into a rendered video using the `hyperframes` skill — freely picking templates, design, palette, motion, and pacing within the constraints the brief lists.

#### 8.1 — Write `composition-brief.md`

Write `{work_dir}/{topic_name}/composition-brief.md` using this exact template, filling in the bracketed fields from the project's Phase 1-7 outputs:

```markdown
# Composition Brief — <TOPIC>

## Project
- Topic: <one-line description from Phase 1>
- Target duration: <N> s (matches narration.mp3 exactly — do not retime)
- Orientation: <1920×1080 | 1080×1920 | 1080×1440>
- Output: ./composition/renders/final.mp4 (--quality high --fps 30 --workers 1)

## Inputs (paths are relative to this brief, which lives in the workspace root)
- Audio (final, do not regenerate): voice_clone/narration.mp3   # 22050 Hz MP3, CosyVoice clone
- Scene timing (authoritative): transcribe/scene-timing.json     # begin_ms / duration_s / material_ref per scene
- Material catalog: material-catalog.json                        # every visual must trace here
- Narration script (for context only): narration.txt
- Pre-downloaded fonts (use these, do NOT fc-match): fonts/

## Style hints
<free-form description — tone, mood, palette, pacing.
Examples:
  "Chinese narrated explainer, muted handdrawn warmth, slow contemplative pacing."
  "AI/SaaS technical editorial, dark serious typography, Bloomberg-style data callouts."
>

<Optionally point at one of the bundled style references if the user picked a look:
  - references/design-dawn.md  → Rosé Pine Dawn handdrawn warm
  - references/design-moon.md  → Rosé Pine Moon dark technical/editorial
You may also ignore both and design from scratch — both files are reference, not canon.>

You are free to:
- Pick any of the built-in hyperframes templates (`blank`, `warm-grain`, `play-mode`,
  `swiss-grid`, `vignelli`, `decision-tree`, `kinetic-type`, `product-promo`, `nyt-graph`)
  or scaffold from `blank`.
- Run the hyperframes DESIGN.md gate to lock palette / typography / motion before
  composing `index.html`.
- Choose any GSAP image animations. The parent skill's `references/image-animations.md`
  is a curated catalog you MAY consult; it is suggestive, not prescriptive.

## Hard constraints (do NOT override — these are upstream contracts)

1. **Audio is final.** Do not regenerate TTS. Do not call `hyperframes tts` or
   `hyperframes transcribe`. Use `narration.mp3` and `scene-timing.json` as-is.
2. **Scene timing is authoritative.** Each scene's `data-start` / `data-duration`
   must match `scene-timing.json` exactly; preserve 6-decimal precision so chained
   clips don't trip lint's "Track N overlaps" rule.
3. **Every on-screen visual must trace to `material_ref` in `material-catalog.json`.**
   Resolution: look up `entries[*]` where `slug == material_ref.entry_slug`, then
   look up the image (`kind="image"`) or video (`kind="video_clip"`) where
   `id == material_ref.asset_id`. For videos, cut `selected_clips[clip_index]`
   with `ffmpeg -ss <start> -to <end> -c copy` before embedding as
   `<video class="clip" muted>`. Never invent stock images. If a scene needs a
   visual the catalog cannot supply, stop and report back — do not improvise.
4. **CJK font handling.** Narration is Chinese with Latin proper nouns. Fonts
   in `fonts/` are already downloaded — use them via relative `@font-face`,
   never `fc-match` system fonts. For mixed runs split spans by script:
     - Dawn style: Chinese in `MaShanZheng`/`LongCang`; English/numbers in
       `Caveat`/`PatrickHand`. NEVER put Chinese characters inside a Caveat
       or PatrickHand element — they have no CJK glyphs and render as boxes.
     - Moon style: Chinese in `NotoSerifSC`/`NotoSansSC`; English/data/code
       in `IBMPlexMono`.
5. **Render env quirks on this machine:**
   - Pass `--workers 1` to `hyperframes render`. Multi-worker hits a Chromium
     fallback bug ("FFmpeg exited 187 — height not divisible by 2").
   - `hyperframes lint` and `hyperframes inspect` must both pass (0 errors)
     before the final render.
6. **GSAP text animation pitfall.** Do not animate `textContent` from a number
   (e.g. `tl.from(el, { textContent: 0 })`) on an element that has nested
   `<span>` children — GSAP overwrites the children and the count renders as
   `NaN%`. For emphasis on numbers with units, animate `scale` / `opacity`
   instead, or split the number and unit into separate sibling spans.

## Deliverable
- `composition/index.html` (GSAP timeline + scenes)
- `composition/DESIGN.md` (so future runs can match the look)
- `composition/renders/final.mp4`
- Print a short summary at the end: path, duration (`ffprobe -i ...`), file size.
```

#### 8.2 — Invoke the coding sub-agent

From the workspace, hand the brief to a coding agent that has access to the
`hyperframes` skill:

```bash
cd {work_dir}/{topic_name}

# Default: GitHub Copilot CLI
copilot --allow-all-tools --add-dir . \
  -p "$(cat composition-brief.md)

Read the brief above and produce the deliverables. Use the hyperframes skill
(installed under ~/.hermes/hermes-agent/optional-skills/creative/hyperframes/).
Workflow: scaffold ./composition with hyperframes init, write DESIGN.md, compose
index.html, run hyperframes lint && hyperframes inspect, fix issues, then render
with --workers 1. Iterate until lint and inspect pass and renders/final.mp4 exists."
```

Alternative — Claude Code with the same brief:

```bash
claude --add-dir . --allowedTools "Bash Edit Write Read Glob Grep" \
       -p "$(cat composition-brief.md)

Read the brief above and produce the deliverables. Use the hyperframes skill.
Iterate hyperframes init → DESIGN.md → compose → lint → inspect → render."
```

Do **not** drive composition from the main agent's session. Composition needs
many small file edits, lint loops, and render attempts; running it inside a
coding sub-agent with the hyperframes skill loaded is dramatically faster and
keeps the main agent's context clean.

#### 8.3 — Sanity-check the result

After the sub-agent returns, verify from the main agent:

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 \
  {work_dir}/{topic_name}/composition/renders/final.mp4
ls -la {work_dir}/{topic_name}/composition/renders/final.mp4
```

Expect: duration within ±0.1 s of `narration.mp3`; file size > 1 MB; an audio
stream present. If anything looks off, send the failure back to the sub-agent
(`copilot resume` or a fresh `claude -p ...`) with a pointer to the symptom —
don't try to hand-patch the composition from the main agent.

## Gotchas Quick Table (read `references/gotchas.md` for details)

| Symptom | Cause | Fix |
|---|---|---|
| `Failed to download model small.en` | Whisper download blocked | Use Paraformer instead |
| `status_code=44 sample rate 16000 not equals with real 22050` | Paraformer sample_rate mismatch | `sample_rate=22050` for CosyVoice MP3 |
| `Conversion failed! Try --docker` from hyperframes render | multi-worker chromium fallback bug | Pin `--workers 1` in the brief |
| `[Compiler] No deterministic font mapping for: AR PL UKai CN` | Sub-agent reached for `fc-match` system fonts | Re-run with the brief explicitly pointing at `fonts/` and forbidding `fc-match` |
| Chinese badge shows ★▢□ garbage in final render | Caveat/PatrickHand applied to Chinese characters | Tighten CJK rule in the brief (Iron Rule #6); re-render |
| Paraformer transcript missing capitals (`hugging face` not `Hugging Face`) | Paraformer normalizes English to lowercase | Use case-insensitive anchor matching (shipped script handles this) |
| `WARN: anchor not found for X` from scene-anchor.py | Case mismatch OR audio doesn't say that exact phrase | Run `cat transcript.json` first, pick anchors from the actual ASR text |
| `vision-analyze.py` returns `mode: "delegate_to_agent"` | `VLM_API_KEY` not set — this is **not** an error | Either set `VLM_API_KEY`/`VLM_BASE_URL`/`VLM_MODEL` for explicit VLM, OR honor the directive: use your `view` tool on each path in `images.local` |
| `vision-analyze.py` errors with "VLM_API_KEY is set but missing required config" | Partial VLM_* setup | Set both `VLM_BASE_URL` and `VLM_MODEL` (or pass `--model`) |
| `harvest-pages.py` blocked by cookie banner | EU/cookie wall absorbs scroll/clicks | Re-run after accepting the banner once in the shared profile (`{work_dir}/chrome_profile`) — cookie state persists across CDP sessions |
| `harvest-pages.py` returns 0 images on a real gallery | Lazy-loaded images need scroll | Already handled (auto-scroll-to-bottom); if still 0, raise `--page-load-timeout` |
| External video download fails | yt-dlp upstream issue (geoblock, age-gate, 410, etc.) — manifests in Phase 3.b | Leave that `videos[]` entry with `download_required: true`; Phase 4 ignores it. If the clip is essential, `web_search` for a re-uploaded mirror and rerun `harvest-pages.py` with the new URL |
| Playwright import error | venv missing playwright | `pip install playwright` — NO `playwright install chromium` (we use system Chrome over CDP) |
| `Chrome exited immediately` from `harvest-pages.py` | Profile dir already locked by another Chrome | Close other Chrome instances using `{work_dir}/chrome_profile`, or pass a different `--profile-dir` |
| Chrome exits with `Missing X server or $DISPLAY` | No display in container/SSH session | `harvest-pages.py` auto-detects this (`--headless auto` checks `DISPLAY`). Force with `--headless on` if auto-detect misfires |
| Chrome exits with sandbox errors as root | Running inside a container | `--no-sandbox` is auto-enabled when running as root or inside Docker; pass explicitly with `--no-sandbox` if needed |
| CDP port 9222 busy with the wrong Chrome | Another tool launched Chrome on that port | If it's a Chrome we WANT, that's fine (reuse). If not, pass `--cdp-url http://localhost:9223` |
| Scene references an asset not in `material-catalog.json` | Phase 7 wrote a `material_ref` whose `entry_slug`/`asset_id` pair doesn't resolve in the catalog, or skipped `material_ref` entirely | Re-run Phase 4 vision-analyze and re-build the catalog; every scene must have a `material_ref` that resolves via `entry_slug → asset_id` (and `clip_index` for videos). If no entry fits, harvest more URLs (Phase 3) — do not invent or borrow generic stock assets |

## Resources Bundled With This Skill

> All scripts follow the unified I/O protocol: JSON stdout, `[tool-name]` stderr logs, exit codes 0/1/2. See "Output Conventions" above.

- `scripts/fonts-download.sh` — bulletproof font download + WOFF2 conversion
- `scripts/voice-clone-template.py` — CosyVoice template (replace `input_text`)
- `scripts/transcribe-paraformer.py` — Paraformer ASR (handles sample_rate auto-detect)
- `scripts/scene-anchor.py` — anchor scenes to ASR word stream
- `scripts/check-cjk-fonts.py` — flags Chinese text inside Caveat/PatrickHand contexts (use it as a Phase 8 sanity check on the sub-agent's `composition/index.html`)
- `scripts/extract-frames.py` — FFmpeg frame extraction (uniform sampling or time window)
- `scripts/subtitle-parse.py` — SRT/VTT parser with keyword filtering
- `scripts/vision-analyze.py` — model-agnostic vision analysis: calls any OpenAI-compatible VLM via `VLM_API_KEY` + `VLM_BASE_URL` + `VLM_MODEL`, or delegates to the agent's `view` tool when no VLM is configured
- `scripts/gemini-deep-research.py` — Playwright/CDP automation for Google Gemini's Deep Research. Takes a research prompt, submits it to gemini.google.com, waits for the full report, and extracts the result as Markdown + cited sources JSON. Used in Phase 2 as the primary research backbone. Outputs: `gemini_deep_research.md` + `gemini_deep_research_sources.json`. Supports `--start-from-step N` for retry on failure.
- `scripts/harvest-pages.py` — Playwright/CDP batch URL harvester: takes an array of URLs (official sites, GitHub, docs, etc.), extracts ≥512px images (raster + SVG, including inline `<svg>` elements) and embedded videos per URL, OR records a scroll-through video for text-heavy pages. Downloads native HTML5 `<video>` clips inline; **lists** YouTube/Bilibili URLs in `manifest.pending_downloads[]` for Phase 3.b to fetch. Reuses one Chrome process across the whole batch.
- `scripts/video-download.py` — yt-dlp wrapper for YouTube/Bilibili. Called by the agent in Phase 3.b, once per `pending_downloads[]` entry.
- `references/design-dawn.md` — Rosé Pine Dawn handdrawn warm style reference (optional input to the Phase 8 brief)
- `references/design-moon.md` — Rosé Pine Moon dark technical/editorial style reference (optional input to the Phase 8 brief)
- `references/gotchas.md` — full pitfall catalog with reproductions
- `references/palettes.md` — style routing for Rosé Pine Dawn, Rosé Pine Moon Serious, warm-editorial, and dark-premium
- `references/script-templates.md` — narration patterns (interview-recap, news, tutorial, story)
- `references/image-animations.md` — suggestive GSAP image animation patterns the sub-agent MAY consult in Phase 8 (Ken Burns, pan, slideshow, grid, montage, …)

## Dependencies for Material Tools

The material processing scripts require additional dependencies beyond the base skill:

- **ffmpeg/ffprobe** (for frame extraction): usually pre-installed on Linux
- **playwright** (Python bindings only, ~3 MB) for `harvest-pages.py`: `pip install playwright`. NO `playwright install chromium` — we attach to system Chrome over CDP.
- **system Chrome** (auto-detected per platform: Linux `/usr/bin/google-chrome`, macOS `/Applications/Google Chrome.app`, Windows `%ProgramFiles%\Google\Chrome\Application\chrome.exe`; or set `CHROME_PATH` env var, or pass `--chrome-path`): auto-launched on demand with `--remote-debugging-port=9222 --user-data-dir={work_dir}/chrome_profile`. Shared across `gemini-deep-research.py` and `harvest-pages.py` so cookies/logins persist. **Gemini Deep Research requires a logged-in Google account** — log in once manually via the shared Chrome profile.
- **yt-dlp** (for `video-download.py`): on PATH (`/home/jieliu1/.local/bin/yt-dlp`).
- **vision model** (optional): set `VLM_API_KEY` + `VLM_BASE_URL` + `VLM_MODEL` to enable `vision-analyze.py` Mode 1 (e.g. point at DashScope's OpenAI-compatible endpoint with `qwen-vl-max`). When unset, the script delegates to the calling agent's own `view` tool — no extra dependency required.
- **coding sub-agent** (Phase 8): GitHub `copilot` CLI or `claude` CLI on PATH, with the `hyperframes` skill installed under `~/.hermes/hermes-agent/optional-skills/creative/hyperframes/`.

## Red Flags — STOP if you see any of these

You are about to make a known mistake if you find yourself:

- **Writing the script without doing Phase 2 research first** (or skipping web_search/web_fetch)
- **Skipping vision-analyze** when you have 20+ frames and need to pick the best 3-4
- Writing narration before running vision-analyze on harvested videos and building `material-catalog.json`
- **Designing a scene without a `material_ref`** into `material-catalog.json`, or referencing an `<img src>` / `<video src>` whose path is not a catalog entry
- **Embedding the full source video** instead of an ffmpeg-cut `selected_clips[i]` range
- **Hand-writing `composition/index.html` from the main agent** instead of handing the brief to a coding sub-agent
- **Skipping `composition-brief.md`** and dropping the sub-agent into a workspace with no instructions
- Reaching for `npx hyperframes transcribe` for Chinese audio
- Reaching for `npx hyperframes tts` because you forgot CosyVoice
- Picking system Chinese fonts via `fc-match`
- Setting Paraformer `sample_rate=16000`

Stop and re-read the relevant Iron Rule above.
