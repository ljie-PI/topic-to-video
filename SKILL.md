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

0. **Research before script.** Phase 2 is mandatory. Do not draft a single line of narration before running Gemini Deep Research (primary) and web_search (gap-filling) to verify names, dates, numbers, and quotes. Untruthful video = useless video.
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
11. **Don't `cover`-crop information-dense images.** Screenshots, charts, data tables, and portraits with important edges must use `object-fit: contain` (or equivalent framing) so no content is lost. How to treat the resulting letterbox margins (background color, blur, etc.) is a design choice — see `references/image-animations.md` §Image Sizing Best Practices for suggestions.
12. **No plain-text scenes.** Every piece of on-screen textual information must become designed information graphics — never a bare paragraph or unstyled caption block. Use structured forms such as title cards, metric cards, quote pullouts, lower-thirds, timelines, comparison grids, process steps, flowcharts, architecture diagrams, callouts, badges, or chapter markers; fill the available frame with intentional visual structure; and synchronize each visual element to the exact narration phrase it explains.

## Checkpoint & Resume

**Before running any tool, check if its output already exists in the workspace.** If a previous run (or a previous session) already produced the expected output files, skip the tool and reuse the existing results. This enables resuming from any breakpoint without re-running expensive operations (TTS, ASR, Gemini Deep Research, harvest, etc.).

### Per-Phase Skip Conditions

| Phase | Tool / Action | Skip if these files exist | What to do on skip |
|-------|--------------|--------------------------|-------------------|
| 2 | `gemini-deep-research.py` | `gemini_deep_research.md` (non-empty) | Read the existing report; proceed to gap-filling web_search |
| 2a | `parse-pdf.py` (main paper) | `harvest_page/main-paper/metadata.json` exists | Read existing paper data |
| 2c | `parse-pdf.py` (related papers) | `harvest_page/related-*/metadata.json` exists for expected papers | Read existing entries |
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
| 9 | `mix-bgm.py` | `composition/renders/final_with_bgm.mp4` exists | Skip BGM mix; verify with ffprobe |

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
├── mineru_output/              # Phase 2a: MinerU raw output (retained for debug)
│   └── {slug}/
│       ├── full.md
│       └── content_list.json
├── harvest_page/               # Phase 3: per-URL harvest results (one call to harvest-pages.py)
│   ├── manifest.json            #   ↳ contains entries[] and pending_downloads[] (Phase 3.b feeds these to video-download.py)
│   ├── manifest_papers.json     #   ↳ paper-origin entries (merged into manifest.json in Phase 3)
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
| Final mp4 plays the narration on top of a clip's original voice/music | The sub-agent cut `selected_clips[i]` with `ffmpeg ... -c copy` (audio track preserved) and embedded the result; Chromium's `muted` attribute does not strip the audio track during `hyperframes render` | Re-cut every embedded clip with `-c:v copy -an` (and re-render). The narration in `narration.mp3` is the only audio source for the final mix; clip audio must be discarded at cut time, not just hidden via the HTML attribute |
| `parse-pdf.py` cloud returns `-60007` | MinerU model service temporarily unavailable | Script auto-falls back to local `mineru` CLI with `pipeline` backend |
| `parse-pdf.py` cloud timeout on URL | GitHub/AWS URLs blocked from China-hosted MinerU servers | Use `--pdf` with a locally downloaded file instead of `--url` |
| `mineru` CLI not found (local fallback) | `mineru[pipeline]` not installed in venv | `pip install "mineru[pipeline]"` in the shared venv |

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
- `scripts/parse-pdf.py` — MinerU cloud API wrapper for PDF parsing: extracts text, figures, tables with captions into harvest-manifest-compatible format. Falls back to local `mineru` CLI when cloud is unavailable.
- `scripts/harvest-pages.py` — Playwright/CDP batch URL harvester: takes an array of URLs (official sites, GitHub, docs, etc.), extracts raster images meeting the configurable size filter (default ≥500px wide and ≥300px tall), SVG images (no size filter), inline `<svg>` elements, and embedded videos per rendered page, and records a scroll-through video by default. Downloads native HTML5 `<video>` clips inline; **lists** YouTube/Bilibili URLs in `manifest.pending_downloads[]` for Phase 3.b to fetch. Reuses one Chrome process across the whole batch.
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
- **yt-dlp** (for `video-download.py`): on PATH (`yt-dlp --version` should work).
- **vision model** (optional): set `VLM_API_KEY` + `VLM_BASE_URL` + `VLM_MODEL` to enable `vision-analyze.py` Mode 1 (e.g. point at DashScope's OpenAI-compatible endpoint with `qwen-vl-max`). When unset, the script delegates to the calling agent's own `view` tool — no extra dependency required.
- **MinerU cloud API** (for `parse-pdf.py`): requires `requests` (`pip install requests`) and `MINERU_API_TOKEN` in `.env` (register free at https://mineru.net). 1,000 pages/day at full priority. Falls back to local `mineru` CLI (`pip install "mineru[pipeline]"`) when token is unset or cloud is unreachable.
- **coding sub-agent** (Phase 8): GitHub `copilot` CLI or `claude` CLI on PATH, with the `hyperframes` skill installed wherever that agent discovers skills from (e.g. its plugin/extension/marketplace dir). The main agent does not need to know the path — the sub-agent finds it via its own skill loader when it sees the brief say "use the hyperframes skill".

## Red Flags — STOP if you see any of these

You are about to make a known mistake if you find yourself:

- **Writing the script without doing Phase 2 research first** (or skipping web_search/web_fetch)
- **Skipping Gemini Deep Research without an explicit skip condition** — falling back to web_search-only when Gemini is available and the topic has factual claims to verify
- **Skipping vision-analyze** when you have 20+ frames and need to pick the best 3-4
- Writing narration before running vision-analyze on harvested videos and building `material-catalog.json`
- **Designing a scene without a `material_ref`** into `material-catalog.json`, or referencing an `<img src>` / `<video src>` whose path is not a catalog entry
- **Embedding the full source video** instead of an ffmpeg-cut `selected_clips[i]` range
- **Cutting a `video_clip` without `-an`** — leaving the source audio in the embedded `<video>` lets it fight the narration even if `muted` is set on the tag (some renderers still mix the audio track). Always cut with `ffmpeg -ss ... -to ... -i <source.mp4> -c:v copy -an <out.mp4>`.
- **Hand-writing `composition/index.html` from the main agent** instead of handing the brief to a coding sub-agent
- **Skipping `composition-brief.md`** and dropping the sub-agent into a workspace with no instructions
- Reaching for `npx hyperframes transcribe` for Chinese audio
- Reaching for `npx hyperframes tts` because you forgot CosyVoice
- Picking system Chinese fonts via `fc-match`
- Setting Paraformer `sample_rate=16000`
- **Using `object-fit: cover` on an information-dense image** (screenshot, chart, data table, portrait with important edges) — content WILL be cropped
- **Pasting `display_text` as a plain paragraph** instead of turning it into designed information objects (cards, callouts, timelines, diagrams, comparison grids, etc.)
- **Revealing every text card at scene start** when the narration introduces those cards one by one — visual elements must enter with their matching spoken cues
- **Skipping Phase 2a when the user gave a PDF** — the parsed paper markdown and extracted figures are the content spine; without them the narration has nothing to ground on
- **Using training data to describe a paper** instead of reading the parsed `full.md` from MinerU output

Stop and re-read the relevant Iron Rule above.
