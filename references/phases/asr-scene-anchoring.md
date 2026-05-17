### Phase 7 — ASR + Scene Anchoring

Run `scripts/transcribe-paraformer.py {work_dir}/{topic_name}/voice_clone/narration.mp3 {work_dir}/{topic_name}/transcribe/transcript.json`.

Then design scenes (one per narration paragraph — typically 15-40 for a 3-10 minute video), each with:
- `id` (e.g. `s1-hook`, `s2-stat`)
- `anchor` (a 4-8 char substring that appears uniquely in the ASR text, signalling this scene starts when this phrase is spoken)
- `display_text` — on-screen copy when used. Do not treat this as a paragraph to paste onto the screen. For any scene with multiple pieces of textual information, prefer `info_units`: small, separate facts/claims/labels that Phase 8 can render as cards, badges, timeline entries, callouts, or diagram nodes.
- `info_units` — a list of `{ text, role, narration_cue }` items. `role` can be `headline`, `metric`, `quote`, `label`, `source`, `step`, `comparison`, `warning`, `definition`, or `takeaway`. `narration_cue` is the exact spoken phrase that should trigger the visual element. Phase 8 uses these cues to reveal each element in sync with the narration, not merely with the scene start.
- `material_ref` (required) — `{ entry_slug, kind: "image" | "video_clip", asset_id, clip_index?: int }`. Picks one asset from `{work_dir}/{topic_name}/material-catalog.json`: locate the entry where `entries[*].slug == entry_slug`, then locate the image (`kind=image`) or video (`kind=video_clip`) where `id == asset_id`. When `kind = video_clip`, `clip_index` (0-based) points at the chosen item inside that video's `selected_clips`.

**Every scene must cite at least one catalog entry.** If no harvested material fits a scene, go back to Phase 3 and harvest more URLs — never invent assets or fall back to a generic stock image. This is the structural guarantee that the materials gathered by `harvest-pages.py` actually reach the final video.

Write the scene list to `{work_dir}/{topic_name}/transcribe/scenes-config.json` (intermediate file, consumed in the next step), then run `scripts/scene-anchor.py {work_dir}/{topic_name}/transcribe/transcript.json {work_dir}/{topic_name}/transcribe/scenes-config.json {work_dir}/{topic_name}/transcribe/scene-timing.json`. The script anchors each scene to the ASR word stream, computes `begin_ms` / `duration_s`, and **passes every per-scene field (including `material_ref`, `display_text`, and `info_units`) straight through** to the output. `scene-timing.json` is the single authoritative input the Phase 8 brief points the sub-agent at — it contains timing, material refs, and text-structure hints per scene, so the sub-agent never needs to read `scenes-config.json`.

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
