### Phase 6 — Generate TTS

Copy `scripts/voice-clone-template.py` to project root as `voice-clone.py`, paste `narration.txt` content into `input_text`, then:

```bash
source .venv/bin/activate  # from parent dir, or wherever the venv is
export DASHSCOPE_API_KEY="sk-..."
python3 voice-clone.py --output-dir {work_dir}/{topic_name}/voice_clone
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {work_dir}/{topic_name}/voice_clone/narration.mp3
```

If duration is much longer than user wanted, retry with higher `speech_rate` (1.2 default; try 1.4 for shorter, 1.0 for slower).
