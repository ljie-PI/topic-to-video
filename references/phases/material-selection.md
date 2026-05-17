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
   - For images (raster and SVG): one batch per URL (max 10 per call). Prompt asks for subject, visual style, suitability score 1-10.
   - For each video: one batch on the extracted frames. Prompt additionally asks for start/end timestamp of the most relevant span.
   - **Mode 1 (explicit VLM):** if `VLM_API_KEY` + `VLM_BASE_URL` + `VLM_MODEL` are set → direct OpenAI-compatible call.
   - **Mode 2 (delegate):** otherwise → script returns `delegate_to_agent` with image paths; the agent uses its own `view` tool.

   **Paper-origin entries (`source_type: "paper_pdf"`):** figures and tables already have authoritative captions from the PDF (in `paper_metadata.figure_captions` / `table_captions`). Use these directly as `semantic_description` with default `score: 8`. Only run VLM on paper assets that lack captions.

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
