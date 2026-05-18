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
7. **Input type detection:**
   - Source is a `.pdf` file path → set `input_mode = "paper"`
   - Source is a URL ending in `.pdf` (e.g. arXiv) → set `input_mode = "paper"`, keep the URL for `parse-pdf.py --url`
   - Otherwise → `input_mode = "standard"` (default; all subsequent "paper mode" sections are skipped)

**If a sister project already exists** (e.g. user says "same style as `claude-code-video/`"), copy `composition/DESIGN.md` + `fonts/` from it and note "reuse this DESIGN.md" inside the brief; the sub-agent will skip fresh design and font work.

**Workspace discovery (checkpoint entry point):** After determining the `topic_name` slug, check if `{work_dir}/{topic_name}/` already exists:
```
ls {work_dir}/{topic_name}/ 2>/dev/null
```
If the directory exists and contains output files, scan against the checkpoint table (see "Checkpoint & Resume" section) and report to the user:
> "Found existing workspace for `{topic_name}`. Detected outputs: [harvest (5 URLs), TTS, ASR, scene-timing]. Resume from Phase 5 (narration)? Or start fresh?"

Wait for user confirmation before proceeding. This is the **only** mechanism by which the agent discovers a prior run — without a workspace directory, there is nothing to resume from.
