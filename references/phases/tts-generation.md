### Phase 6 — 生成 TTS

如果 `{work_dir}/{topic_name}/voice_clone/narration.mp3` 已存在、且 ffprobe 显示其 duration 非零且合法，则跳过。

直接使用 `scripts/voice-clone.py`。**不要**把脚本复制一份，也**不要**把解说文本粘进 Python 源码。

默认走**本地 VoxCPM2 克隆**（ultimate cloning：参考音色 WAV + 其 transcript）：

```bash
source .venv/bin/activate  # 从父目录或 venv 所在目录执行
export VOXCPM_REF_WAV="/path/to/voice_ref.wav"   # 克隆的目标音色（参考音频）
# 可选：export VOXCPM_MODEL=/path/to/VoxCPM2     # 本地模型目录；缺省自动从 HF 下载
# 可选：export QWEN3_ASR_MODEL=/path/to/Qwen3-ASR-1.7B  # 首次自动转写参考音频用

python3 scripts/voice-clone.py \
  --input-file {work_dir}/{topic_name}/narration.txt \
  --output-dir {work_dir}/{topic_name}/voice_clone

ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 \
  {work_dir}/{topic_name}/voice_clone/narration.mp3
```

参考音色与 transcript：
- `--reference-wav` 或 `VOXCPM_REF_WAV` 指定参考音频（任意采样率 / 声道，脚本内部按需重采样）。
- 参考音频的逐字 transcript 解析顺序：`--reference-text` / `VOXCPM_REF_TEXT`（可为内联字符串或 `.txt` 路径）→ 参考 WAV 同名 `<ref>.txt` 缓存 → 首次用 Qwen3-ASR 自动转写并缓存到 `<ref>.txt`。
- 默认 `--speech-rate` 1.2（VoxCPM / Qwen3-TTS 通过 ffmpeg `atempo` 后处理，贴近云端节奏）。

可选本地后端 Qwen3-TTS（`TTS_BACKEND=qwen3tts`，模型 `Qwen3-TTS-12Hz-1.7B-Base`，同样靠参考 WAV + transcript 克隆）：纯中文解说可懂度很高、音频更紧凑，但英文专有名词偶有发音瑕疵；VoxCPM2 在中英混排上更稳、且 48kHz。按内容选择即可。

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
