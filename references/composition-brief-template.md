# Composition Brief — <TOPIC>

## Project
- Topic: <one-line description from Phase 1>
- Target duration: <N> s (matches narration.mp3 exactly — do not retime)
- Orientation: <1920×1080 | 1080×1920 | 1080×1440>
- Output: ./composition/renders/final.mp4 (--quality high --fps 30 --workers 1)

## Inputs (paths are relative to this brief, which lives in the workspace root)
- Audio (final, do not regenerate): voice_clone/narration.mp3   # 22050 Hz MP3, CosyVoice clone
- Scene timing (authoritative): transcribe/scene-timing.json     # begin_ms / duration_s / material_ref per scene
- ASR transcript (word-level timings): transcribe/transcript.json # use for element-level text reveal timing
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

## Text display + motion contract

Text is visual information design, not subtitles. For every place that displays
textual information, do not paste `display_text` as plain text. Build a designed
composition using the current style's typography and motion language. When the
frame has open space because the referenced image/video is absent, backgrounded,
or not information-dense, use structured text forms to fill the available space
with useful visual information rather than leaving sparse plain text.

Use one or more of these forms, choosing the form that explains the narration
best:
- title / chapter cards for scene turns, hooks, or conclusions
- metric / data cards for numbers, percentages, dates, rankings, prices, or deltas
- quote pullouts for quoted claims, user comments, or memorable lines
- lower-thirds for names, organizations, products, locations, or source context
- side annotations / callouts attached to an image, video frame, diagram, or screenshot
- keyword badges / chips for named concepts, technologies, risks, or benefits
- timeline labels for chronology, releases, incidents, or cause-and-effect chains
- multi-card grids for lists of examples, symptoms, objections, or takeaways
- comparison columns for before/after, pros/cons, old/new, competitor A/B, or tradeoffs
- process flows / step cards for procedures, pipelines, decisions, or failure chains
- flowcharts / decision trees for branching logic, diagnosis, or "if X then Y" explanations
- architecture diagrams / stack diagrams for systems, data flow, ownership, or dependencies
- map / matrix / quadrant layouts for positioning, segmentation, or prioritization
- checklist / scorecard layouts for criteria, readiness, or review outcomes

Text hierarchy must be explicit:
- Primary layer: one main claim or question, large and readable.
- Secondary layer: supporting context in short phrases, not full paragraphs.
- Evidence layer: numbers, dates, quotes, source labels, or concrete examples.
- Navigation layer: scene number, chapter marker, or source badge when helpful.

Motion must clarify the spoken sequence:
- Default to subtle `opacity` + `y` / `scale` reveals with staggered timing.
- Use highlight sweeps, underline draws, connector-line draws, number pops, or card
  flips only when they match the content structure.
- Avoid long typewriter effects for Chinese paragraphs; they are slow and compete
  with the voice. If using a typewriter, limit it to very short labels.
- Do not reveal all cards at scene start when the narration introduces them one
  by one.

Synchronization is element-level, not just scene-level:
- The scene's `data-start` / `data-duration` still comes from `scene-timing.json`.
- Inside the scene, each card, label, badge, line, diagram node, or callout should
  enter when its matching narration phrase is spoken. Use word-level timings from
  `transcribe/transcript.json`: match `info_units[].narration_cue` when provided;
  otherwise derive cues from `display_text` and `narration.txt`.
- If a sentence introduces three points, reveal the three visual elements in that
  spoken order, each within roughly 0.3s of the phrase it represents.
- Keep each element visible long enough to be read, but do not let stale elements
  dominate after the narration has moved on; fade, de-emphasize, or shift them into
  a summary layout.
- If exact phrase timing is unavailable, distribute reveals across the spoken
  sentence in semantic order rather than dumping everything at scene start.

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
   with `ffmpeg -ss <start> -to <end> -i <source.mp4> -c:v copy -an <out.mp4>` — **`-an` strips
   the source audio**; the narration in `narration.mp3` is the only voice in
   the final mix. Embed as `<video class="clip" muted playsinline>` (the
   `muted` attribute is belt-and-suspenders against any clip that slipped
   through without `-an`). Never invent stock images. If a scene needs a
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
7. **Don't crop information-dense images.** If a scene's image is a screenshot,
   chart, data table, or portrait with important edges, use `object-fit: contain`
   (or equivalent framing) so no content is lost. Treat the letterbox margins
   however you like (solid color, blur, pattern — your call). For atmospheric /
   decorative photos where cropping is harmless, `cover` is fine.
8. **No plain-text information dumps.** Any textual information shown on screen
   must use designed information structures (cards, callouts, timelines, diagrams,
   comparisons, flows, badges, etc.) with clear hierarchy and should fill the
   available frame with intentional visual structure. Never paste a paragraph of
   `display_text` into the scene as the main visual.
9. **Text motion must follow narration cues.** Do not reveal all text elements at
   scene start unless the narration also states them as one unit. For multiple
   cards, labels, diagram nodes, or callouts, reveal each element when the matching
   narration phrase is spoken, using `transcribe/transcript.json` for word-level
   timing when needed, then keep or de-emphasize it according to the scene's
   information flow.

## Deliverable
- `composition/index.html` (GSAP timeline + scenes)
- `composition/DESIGN.md` (so future runs can match the look)
- `composition/renders/final.mp4`
- Print a short summary at the end: path, duration (`ffprobe -i ...`), file size.
