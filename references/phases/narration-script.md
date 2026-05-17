### Phase 5 — Write Narration Script

**Inputs:** the research brief from Phase 2 + `material-catalog.json` from Phase 4 + the user's preferred angle/length. Annotate each scene with a recommended `material_ref` (the full schema is defined in Phase 7); the actual `local_path` resolution happens later, inside the sub-agent in Phase 8.

Goals:

**Paper mode narration structure** (when `input_mode = "paper"`):

The narration follows the paper's logical flow, not a generic topic structure:
1. Hook — why this paper matters / the problem it addresses
2. Background — prior work and SOTA (from Deep Research)
3. Key insight / approach (from paper abstract + intro, cite paper figures)
4. Method walkthrough (cite paper figures as `material_ref`)
5. Results (cite paper tables/charts as `material_ref`)
6. Impact and follow-up work (from Deep Research)
7. Takeaway / CTA

Paper figures (`source_type: "paper_pdf"` entries) are the PREFERRED materials. Web-harvested assets serve as supplementary B-roll. Reference figure/table numbers naturally in narration when appropriate: `"如表一所示..."`.

- Use **only facts from the research brief** — every number, name, date, and quote must be traceable.
- Reference the collected materials where helpful, and annotate each scene with recommended visual material.
- 3-10 minutes at `speech_rate=1.2` ≈ **7.5 chars/sec** → `3min ≈ 1350 chars`, `5min ≈ 2250 chars`, `10min ≈ 4500 chars`.
- 15-40 paragraphs (scaled to target duration), separated by blank lines (each ≈ one scene = 6-15s of audio).
- Numbers in Chinese characters (`二零二六` not `2026`) — TTS reads them more naturally.
- English proper nouns in original Latin (`Anthropic`, `Claude Code`, `Boris`).
- **Avoid the full-width Chinese colon `：`.** CosyVoice can occasionally insert a 0.5-1 s silence after a full-width colon followed immediately by a long compound sentence, which makes the video feel stuck mid-scene. Use an em dash `——`, split the sentence with commas, or rewrite it. Example: `某品牌：日均消耗一百万` → `某品牌 —— 日均消耗一百万`.
- Last paragraph should be a CTA (`点赞、关注、收藏，下期见`) if user wants social-media style.

**Show the script to the user before generating TTS.** Lets them tweak tone, add/remove a beat, or reject a direction before you spend API budget.

Save to `narration.txt`.
