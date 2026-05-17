### Phase 8 — Hand off composition + render to a coding sub-agent

Everything from this point — scaffolding a HyperFrames project, deciding the look (`DESIGN.md`), composing `index.html` with GSAP, running `lint`/`inspect`, and rendering — is a deep iterative HTML+CSS+GSAP task with its own dedicated skill (`hyperframes`). It is owned by a **coding sub-agent**, not the main agent.

The main agent's remaining work: produce the upstream artifacts (`narration.mp3`, `scene-timing.json`, `material-catalog.json`, `narration.txt`, `fonts/`), write a brief, invoke the sub-agent, sanity-check the resulting mp4, then layer BGM (Phase 9).

The sub-agent's job is to turn those into a rendered video using the `hyperframes` skill — freely picking templates, design, palette, motion, and pacing within the constraints the brief lists.

#### 8.1 — Write `composition-brief.md`

Write `{work_dir}/{topic_name}/composition-brief.md` using the template at `references/composition-brief-template.md`, filling in the bracketed fields from the project's Phase 1-7 outputs.

#### 8.2 — Invoke the coding sub-agent

From the workspace, hand the brief to a coding agent that has access to the
`hyperframes` skill:

```bash
cd {work_dir}/{topic_name}

# Default: GitHub Copilot CLI
copilot --allow-all-tools --add-dir . \
  -p "$(cat composition-brief.md)

Read the brief above and produce the deliverables. Use the hyperframes skill.
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
