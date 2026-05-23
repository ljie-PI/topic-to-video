# Composition Brief — <TOPIC>

## Project
- Topic: <one-line description from Phase 1>
- Target duration: <N> s
- Orientation: <1920x1080 | 1080x1920 | 1080x1440>
- Output: ./composition/renders/final.mp4

## Inputs
Paths are relative to this brief, which lives in the workspace root.

- Final narration audio: voice_clone/narration.mp3
- Narration script: narration.txt
- ASR transcript with word timings: transcribe/transcript.json
- Material catalog: material-catalog.json
- Pre-staged fonts: fonts/

Optional sister-project inputs may exist from prior runs:

- Sister-project design reference: composition/DESIGN.md or copied fonts/

## Style Hint
<Free-form mood, audience, palette, and pacing hint from Phase 1. Examples:
"Chinese narrated explainer, warm handdrawn notebook mood, calm pacing."
"Chinese AI/SaaS technical editorial, dark serious tone, dense but readable data callouts.">

Optional style-routing references:
- references/design-dawn.md — warm handdrawn mood reference
- references/design-moon.md — dark technical/editorial mood reference
- references/palettes.md — alternate mood/palette routing

These references are style hints, not implementation specs. Use the
`hyperframes` skill and the project's own `DESIGN.md` process for all actual
composition, typography, layout, animation, and render decisions.

## Upstream Contracts
1. Audio is final. Do not regenerate TTS and do not call HyperFrames TTS.
2. Use `transcribe/transcript.json` for word-level timing. If you need a
   deterministic scene timing file, you may generate one in `transcribe/`, but
   scene segmentation and visual cue timing are owned by the HyperFrames agent.
3. All material-backed visuals must resolve through `material-catalog.json`.
   Do not invent stock visuals when a catalog material is required.
4. If you cut a source video clip from the catalog, strip its original audio
   with `-an`; `narration.mp3` is the only narration voice in the final video.
5. Use local assets under `fonts/` for deterministic font loading. Do not depend
   on system `fc-match` fonts.
6. Use the `hyperframes` and `hyperframes-cli` skills for all composition,
   animation, validation, and rendering work. The parent `topic-to-video` skill
   owns only the upstream assets listed above.

## Deliverables
- composition/index.html
- composition/DESIGN.md
- composition/renders/final.mp4
- A short completion summary with output path, ffprobe duration, and file size.
