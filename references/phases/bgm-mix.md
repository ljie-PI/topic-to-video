### Phase 9 — 混入 BGM（背景音乐）

子 agent 渲染出来的成品做完 sanity check 后，在解说之上叠一条低音量的背景音乐。解说音量不变；BGM 的默认线性增益是 `0.03`，垫在底下。

本 skill 自带一段默认背景乐 `assets/bgm.mp3`（24 秒可循环片段），常见场景下不需要任何与音乐相关的额外 flag：

```bash
python3 scripts/mix-bgm.py \
  --video {work_dir}/{topic_name}/composition/renders/final.mp4 \
  --output {work_dir}/{topic_name}/composition/renders/final_with_bgm.mp4
```

如需换曲或调音量：

```bash
python3 scripts/mix-bgm.py \
  --video {work_dir}/{topic_name}/composition/renders/final.mp4 \
  --bgm /path/to/your_music.mp3 \
  --bgm-volume 0.05 \
  --output {work_dir}/{topic_name}/composition/renders/final_with_bgm.mp4
```

脚本一次 ffmpeg pass 完成所有事：循环 `--bgm`（默认 `assets/bgm.mp3`）填满整个视频时长、以 `--bgm-volume` 与原解说混音、并用 `-c:v copy` 写出 `final_with_bgm.mp4`（视频流不重编码）。3% 音量足以让音乐听得见又不糊掉解说——如果听不见就把 `--bgm-volume` 调大，如果压住人声了就调小。
