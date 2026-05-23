### Phase 2 — Topic Research (CRITICAL — do this BEFORE writing)

#### Phase 2a — Parse PDF (paper mode only)

Skip unless `input_mode = "paper"`.

```bash
# URL input (arXiv, etc.) — passed directly to MinerU cloud API
python3 scripts/parse-pdf.py \
  --url "{pdf_url}" \
  --output-dir {work_dir}/{topic_name}/harvest_page/ \
  --slug "main-paper"

# Local file input
python3 scripts/parse-pdf.py \
  --pdf "{pdf_path}" \
  --output-dir {work_dir}/{topic_name}/harvest_page/ \
  --slug "main-paper"
```

Requires `MINERU_API_TOKEN` in environment (from `.env`). Falls back to local `mineru` CLI if token is missing or cloud fails.

Read the output JSON. It provides `title`, `abstract`, `full_markdown_path` (the parsed markdown for the full paper). These feed the Deep Research prompt in Phase 2b.

Important output fields:
- `manifest_entry.source_type = "paper_pdf"`
- `manifest_entry.paper_metadata.full_markdown_path` for full parsed text
- `manifest_entry.paper_metadata.figure_captions` for figure descriptions
- `manifest_entry.paper_metadata.table_captions` for table descriptions
- `manifest_papers.json` is updated under the harvest output directory and is
  merged into `manifest.json` during Phase 3.

**Checkpoint:** skip if `harvest_page/main-paper/metadata.json` exists.

#### Phase 2b — Deep Research (paper mode variant)

When `input_mode = "paper"`, replace the standard research prompt with one informed by the parsed paper:

```
"Background research for the paper '{title}':
Abstract: {abstract}

Research:
1. What problem does this paper address? What was SOTA before it?
2. Key related works and how they compare
3. Citations and impact since publication
4. Subsequent developments building on this work
5. Community criticisms or limitations
6. Real-world applications
7. arXiv URLs of the most important related papers (for Phase 2c)"
```

The paper's own markdown is the PRIMARY content source. Deep Research provides context — background, impact, related work comparison. The rest of Phase 2 (gap-filling web_search, research brief synthesis) proceeds as normal.

#### Phase 2c — Parse Related Papers (paper mode, optional)

If Phase 2b identifies 1-2 highly related papers with available PDF URLs (e.g. arXiv):

```bash
python3 scripts/parse-pdf.py \
  --url "https://arxiv.org/pdf/XXXX.XXXXX" \
  --output-dir {work_dir}/{topic_name}/harvest_page/ \
  --slug "related-{short-name}"
```

Max 2 related papers. Skip if user says "just the main paper" or no significant related work is identified.

**Checkpoint:** skip if `harvest_page/related-{short-name}/metadata.json` exists.

**Never write a script from your training data alone.** A 60-second video has no room for vague claims, and any factual error becomes a 60-second mistake. Ground every claim in fresh, citeable sources.

**Process:**

1. **If the user gave a URL** → `web_fetch` it FIRST. Read the full content. This is the spine of the video.
2. **Run Gemini Deep Research.** This is the primary research backbone — it produces a comprehensive, sourced report far richer than manual web searches.
   ```bash
   scripts/gemini-deep-research.py \
     --prompt "Comprehensive overview of [topic]: history, key developments, notable figures, technical details, latest news" \
     --output-dir {work_dir}/{topic_name}/
   ```
   - Outputs: `gemini_deep_research.md` (full report) + `gemini_deep_research_sources.json` (cited URLs)
   - Read the report; it becomes the primary source. The `sources.json` feeds into Phase 3 material harvest.
   - **Skip ONLY when:** (a) user explicitly says "skip deep research", OR (b) topic is a simple re-narration of user-provided text with no factual claims to verify.
   - **If it fails (selector timeout, runtime error, or other step failure):** Fall back to the manual web_search workflow (steps 3-4 below become the primary research path). Check `failed_step` in the error JSON — you can retry with `--start-from-step N`, but do not block the project on the consumer Gemini UI.
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
   Aim for **10-15 source URLs** covering diverse visual material types.
6. **Show the research brief to the user before writing the script.** They may add context, correct a misreading, or narrow the angle. ~1 round of feedback typically.

**Skip research only when:**
- The user explicitly says "skip research, use this exact text" + provides full content
- The topic is a re-narration of a piece they already wrote and provided in full

**Anti-pattern:** Searching once, then writing as if the brief is complete. Real research is iterative — you find one fact, it raises a new question, you search again. Plan for 2-3 rounds.
