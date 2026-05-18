### Phase 9 — Mix BGM (background music)

After the sub-agent's render is sanity-checked, layer a low-volume background
music track on top of the narration. The narration stays at full volume; the
BGM sits underneath at `0.03` linear gain by default.

The skill ships a default music bed at `assets/bgm.mp3` (a 24-second loopable
clip), so the common case needs no music-related flags:

```bash
python3 scripts/mix-bgm.py \
  --video {work_dir}/{topic_name}/composition/renders/final.mp4 \
  --output {work_dir}/{topic_name}/composition/renders/final_with_bgm.mp4
```

To use a different track or volume:

```bash
python3 scripts/mix-bgm.py \
  --video {work_dir}/{topic_name}/composition/renders/final.mp4 \
  --bgm /path/to/your_music.mp3 \
  --bgm-volume 0.05 \
  --output {work_dir}/{topic_name}/composition/renders/final_with_bgm.mp4
```

The script does a single ffmpeg pass: it loops `--bgm` (default
`assets/bgm.mp3`) to cover the full video duration, mixes it with the existing
narration at `--bgm-volume`, and writes `final_with_bgm.mp4` with `-c:v copy`
(no re-encode of the video stream). 3% volume keeps the music audible without
muddying the narration — tweak `--bgm-volume` up if the music is inaudible,
down if it competes with the voice.
