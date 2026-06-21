### Phase 6 — 生成 TTS

如果 `{work_dir}/{topic_name}/voice_clone/narration.mp3` 已存在、且 ffprobe 显示其 duration 非零且合法，则跳过。

直接使用 `scripts/voice-clone.py`。**不要**把脚本复制一份，也**不要**把解说文本粘进 Python 源码。

默认走**本地 Qwen3-TTS 克隆**——把 `TTS_REF_WAV` 指向要克隆的参考音频即可：

```bash
source .venv/bin/activate  # 从父目录或 venv 所在目录执行
export TTS_REF_WAV="/path/to/voice_ref.wav"   # 要克隆的目标音色

python3 scripts/voice-clone.py \
  --input-file {work_dir}/{topic_name}/narration.txt \
  --output-dir {work_dir}/{topic_name}/voice_clone

ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 \
  {work_dir}/{topic_name}/voice_clone/narration.mp3
```

后端开关、模型路径、参考音频 transcript 解析、`--speech-rate` 等细节见 `scripts/voice-clone.py --help`。

云端 fallback（DashScope CosyVoice）：

```bash
export TTS_BACKEND=dashscope
export DASHSCOPE_API_KEY="sk-..."
export COSYVOICE_VOICE_ID="cosyvoice-v3.5-plus-..."   # 或 --voice
python3 scripts/voice-clone.py \
  --input-file {work_dir}/{topic_name}/narration.txt \
  --output-dir {work_dir}/{topic_name}/voice_clone \
  --speech-rate 1.4
```

脚本编写规范：
- 解说内容只放在 `narration.txt` 里。
- 避免在长复合句之前出现全角中文冒号 `：`；改用 `——`、逗号或重新断句。这能避免 TTS 偶发的停顿。
