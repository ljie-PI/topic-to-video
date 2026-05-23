### Phase 3 — Material Harvest

The agent (LLM) produces a list of URLs likely to yield rich visual material, then runs `harvest-pages.py` ONCE with the whole list. For each normal rendered page, the tool extracts images/videos and records a top-to-bottom scroll video by default; direct YouTube/Bilibili watch URLs are listed for Phase 3.b instead of opened in Chrome.

#### URL selection rules (use these to build the array)

Aim for **10-15 URLs**. INCLUDE pages of these types:

| Page type                                | Why it's a good source                              | Expected useful outputs |
|------------------------------------------|-----------------------------------------------------|-------------------------|
| Official product/project homepage         | Hero shots, screenshots, product video             | images/videos + scroll recording |
| GitHub repository main page               | README screenshots, demo gifs, social preview      | images/videos + scroll recording |
| Official documentation landing page       | Diagrams, architecture, long explanatory text      | images/SVGs + scroll recording |
| Official blog post / launch announcement  | Inline images, embedded YouTube                    | images/videos + scroll recording |
| Wikipedia article (for established topics)| Infobox images, well-edited prose                  | images + scroll recording |
| Conference talk / keynote YouTube page    | Downloaded via yt-dlp                              | pending video download |
| Author's personal site / about page       | Headshots, banners                                 | images + scroll recording |

EXCLUDE (low yield, often bot-blocked):

- Search result pages (Google, Bing) — not destinations
- Social media feeds (Twitter/X timelines, LinkedIn feeds) — login walls
- Aggregator listicles ("Top 10 AI tools…") — stock images
- Paywalled news article body pages — blocked content
- App store listings — small thumbnails only
- PDFs — use `parse-pdf.py` instead (Phase 2a); harvest-pages.py cannot render PDFs

Sources for picking URLs (in order of preference):

1. The URL the user provided (always include if they gave one).
2. URLs listed in the research brief's **Source URLs** section — these were pre-filtered during Phase 2 to match harvest-worthy page types.
3. All remaining URLs from `gemini_deep_research_sources.json` that match INCLUDE page types above. Read the entire file and include every qualifying URL not already covered.
4. If still <10 URLs, run `web_search` for `"{topic} official site"`, `"{topic} github"`, `"{topic} documentation"`, `"{topic} demo"` until the list reaches 10-15.

#### Running harvest-pages.py

```bash
scripts/harvest-pages.py \
  --urls https://anthropic.com/news/claude-code \
         https://github.com/anthropics/claude-code \
         https://docs.anthropic.com/claude-code \
         https://www.youtube.com/watch?v=... \
  --output-dir {work_dir}/{topic_name}/harvest_page/ \
  --profile-dir {work_dir}/chrome_profile
```

The first invocation launches Chrome at `{work_dir}/chrome_profile`; subsequent invocations reuse it over CDP (`http://localhost:9222`). Chrome stays running between calls. Per-URL failures don't sink the batch.

Outputs: `harvest_page/manifest.json` + `harvest_page/<url-slug>/` directories (one per URL). See the `manifest.entries[]` shape — each rendered-page entry has `text_excerpt`, `metrics`, `images[]`, `videos[]`, and optional `scroll_recording`; direct YouTube/Bilibili entries have `videos[]` with `download_required: true` and no scroll recording. The manifest also contains a top-level **`pending_downloads[]`** — every YouTube/Bilibili URL the harvester detected (either passed in `--urls` directly or found embedded on a page).

#### Paper mode: merge parsed papers into manifest

When `input_mode = "paper"`, `parse-pdf.py` writes paper entries to
`harvest_page/manifest_papers.json` (separate from the web harvest manifest).
After `harvest-pages.py` completes (or is skipped), merge them:

```bash
scripts/merge-paper-manifest.py \
  --harvest-dir {work_dir}/{topic_name}/harvest_page/
```

From this point forward, `manifest.json` contains both paper-origin entries (`source_type: "paper_pdf"`) and web-origin entries. All downstream phases read the same unified manifest.

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
- After each successful download, apply the JSON result to `manifest.json` and
  the corresponding `metadata.json` files:
  ```bash
  scripts/apply-video-download-result.py \
    --harvest-dir {work_dir}/{topic_name}/harvest_page/ \
    --source-slug "<item.source_slug>" \
    --url "<item.url>" \
    --result-json /path/to/video-download-result.json
  ```
  This sets `download_required: false`, adds `local_path` and optional
  `subtitle_path`, sets `id` to the downloaded file stem, and fans the update
  out to any `also_referenced_by` slugs.
- If `video-download.py` returns `{"success": false}` (geoblock, age-gate, 410, etc.), leave the entry with `download_required: true` and skip it — Phase 4 will ignore it. If the topic depends on that exact clip, run `web_search` for a re-uploaded mirror and rerun `harvest-pages.py` with the new URL.

This decoupling means `harvest-pages.py` runtime is dominated by Playwright (fast, deterministic) and yt-dlp failures are isolated to specific URLs, not the entire batch.
