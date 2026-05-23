### Phase 8 — Delegate HyperFrames Composition + Render

From this point onward, composition is owned by a coding sub-agent that uses the
`hyperframes` and `hyperframes-cli` skills. The main `topic-to-video` agent only
prepares upstream assets, writes a compact handoff brief, invokes the sub-agent,
and sanity-checks the returned MP4.

The HyperFrames sub-agent owns:
- scene segmentation from `narration.txt` and `transcribe/transcript.json`
- optional scene timing artifact generation
- material-to-scene mapping from `material-catalog.json`
- visual information design, layout, typography, animation, and transitions
- `composition/index.html` and `composition/DESIGN.md`
- `hyperframes lint`, `hyperframes inspect`, and render iteration

#### 8.1 — Write `composition-brief.md`

Write `{work_dir}/{topic_name}/composition-brief.md` from
`references/composition-brief-template.md`, filling in project metadata, input
paths, and the style hint from Phase 1. Keep the brief short. Do not paste
HyperFrames implementation rules, GSAP snippets, or layout instructions into it.

#### 8.2 — Invoke a coding sub-agent

Use the current client/runtime's native sub-agent or delegation tool when one is
available. The prompt should be short and should ask the sub-agent to read the
brief file from disk rather than inlining the full brief into a shell command.

Prompt shape:

```text
Read composition-brief.md in the current workspace and produce the deliverables.
Use the hyperframes and hyperframes-cli skills. You own scene segmentation,
material mapping, composition design, animation, lint/inspect fixes, and final
rendering. Iterate until composition/renders/final.mp4 exists and HyperFrames
lint/inspect have no errors.
```

If the environment has no native sub-agent tool, a short CLI fallback is
acceptable only if it passes the prompt above and lets the coding agent read
`composition-brief.md` itself. Do not use `-p "$(cat composition-brief.md)"`.

Do not drive composition from the main agent's session.

#### 8.3 — Sanity-check the result

After the sub-agent returns, verify from the main agent:

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 \
  {work_dir}/{topic_name}/composition/renders/final.mp4
ls -la {work_dir}/{topic_name}/composition/renders/final.mp4
```

Expect: duration close to the target narration duration, file size > 1 MB, and
an audio stream present. If anything looks off, send the symptom back to the
HyperFrames sub-agent. Do not hand-patch `composition/index.html` from the main
agent.
