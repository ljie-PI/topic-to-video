### Phase 6 — Generate TTS

Skip if `{work_dir}/{topic_name}/voice_clone/narration.mp3` exists and has a
valid non-zero ffprobe duration.

Use `scripts/voice-clone.py` directly. Do not copy the script or paste
the narration into Python source.

```bash
source .venv/bin/activate  # from parent dir, or wherever the venv is
export DASHSCOPE_API_KEY="sk-..."
export COSYVOICE_VOICE_ID="cosyvoice-v3.5-plus-..."

python3 scripts/voice-clone.py \
  --input-file {work_dir}/{topic_name}/narration.txt \
  --output-dir {work_dir}/{topic_name}/voice_clone \
  --speech-rate 1.2

ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 \
  {work_dir}/{topic_name}/voice_clone/narration.mp3
```

Voice selection:
- Prefer `--voice` for one-off runs.
- Prefer `COSYVOICE_VOICE_ID` for repeatable project runs.
- The script fails clearly if no voice id is configured.

Duration retry:
- If duration is much longer than requested, retry with `--speech-rate 1.35` or
  `--speech-rate 1.4`.
- If it feels rushed, retry with `--speech-rate 1.0` or `--speech-rate 1.1`.

Script hygiene:
- Keep the narration in `narration.txt`.
- Avoid the full-width Chinese colon `：` before long compound sentences; use
  `——`, commas, or split the sentence. This prevents occasional CosyVoice pauses.
