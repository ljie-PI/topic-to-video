### Phase 7 — ASR + Font Staging

This phase prepares timing and font inputs for the downstream HyperFrames
sub-agent. The main `topic-to-video` agent does **not** design scenes, write
`info_units`, map materials to layouts, or produce HyperFrames HTML.

#### 7.1 — Generate ASR transcript

Skip if `{work_dir}/{topic_name}/transcribe/transcript.json` already exists and
is valid JSON with at least one sentence and word timing.

```bash
scripts/transcribe-paraformer.py \
  {work_dir}/{topic_name}/voice_clone/narration.mp3 \
  {work_dir}/{topic_name}/transcribe/transcript.json
```

The output is the raw word-level timestamp database consumed by the Phase 8
HyperFrames sub-agent.

#### 7.2 — Pre-stage fonts

Skip if `{work_dir}/{topic_name}/fonts/` contains the required `.woff2` files
and style CSS for the selected style.

```bash
# Dawn default handdrawn style
bash scripts/fonts-download.sh {work_dir}/{topic_name}/fonts dawn

# Moon serious technical/editorial style
bash scripts/fonts-download.sh {work_dir}/{topic_name}/fonts moon

# If creating a reusable project template that may switch styles later
bash scripts/fonts-download.sh {work_dir}/{topic_name}/fonts all
```

Pre-staging fonts is an upstream responsibility because it gives the
HyperFrames sub-agent deterministic local font assets and prevents accidental
system-font fallback.

#### Optional — scene-anchor helper

`scripts/scene-anchor.py` remains available as an optional deterministic helper
for an agent that already has a scene config and wants to anchor scene starts to
ASR text. It is no longer a required main-agent phase. Scene segmentation,
material mapping, visual cue timing, and `composition/index.html` generation are
owned by the Phase 8 HyperFrames sub-agent.
