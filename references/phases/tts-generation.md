### Phase 6 — 生成 TTS

如果 `{work_dir}/{topic_name}/voice_clone/narration.mp3` 已存在、且 ffprobe 显示其 duration 非零且合法，则跳过。

直接使用 `scripts/voice-clone.py`。**不要**把脚本复制一份，也**不要**把解说文本粘进 Python 源码。

```bash
source .venv/bin/activate  # 从父目录或 venv 所在目录执行
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

音色选择：
- 一次性 run 优先用 `--voice`。
- 可重复 run 的项目优先用 `COSYVOICE_VOICE_ID`。
- 如果没配 voice id，脚本会清晰报错。

时长重试：
- 如果时长明显比预期长，用 `--speech-rate 1.35` 或 `--speech-rate 1.4` 重跑。
- 如果听起来太赶，用 `--speech-rate 1.0` 或 `--speech-rate 1.1` 重跑。

脚本卫生：
- 解说内容只放在 `narration.txt` 里。
- 避免在长复合句之前出现全角中文冒号 `：`；改用 `——`、逗号或重新断句。这能避免 CosyVoice 偶发的停顿。
