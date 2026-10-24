# Phase 7 — 生成 TTS

## 输入

Phase 6 产出的 `narration.txt`（朗读稿）。

## 输出

`voice_clone/narration.mp3`（配音音频）。

## 完成判据

`voice_clone/narration.mp3` 存在且非空（ffprobe duration 非零且合法）。

## 下一步

Phase 8（对齐与字幕）：对配音跑 ASR 拿词级时间戳。

---

直接使用 `scripts/voice-clone.py`。**不要**把脚本复制一份，也**不要**把解说文本粘进 Python 源码。

```bash
source .venv/bin/activate  # 从父目录或 venv 所在目录执行
python3 scripts/voice-clone.py \
  --input-file {work_dir}/{topic_name}/narration.txt \
  --output-dir {work_dir}/{topic_name}/voice_clone

ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 \
  {work_dir}/{topic_name}/voice_clone/narration.mp3
```

后端由环境变量选择，参数和依赖（参考音色、Python 包、硬件要求等）见 `scripts/voice-clone.py --help`。

脚本编写规范：
- 解说内容只放在 `narration.txt` 里。
- 避免在长复合句之前出现全角中文冒号 `：`；改用 `——`、逗号或重新断句。这能避免 TTS 偶发的停顿。

## TTS / ASR 接口契约

TTS 和 ASR 的 CLI 参数、输出路径、transcript schema 固定不变；后端可换，只要新后端满足契约即可接入。与后端绑定的说明（硬件精度、参考音频转写、数字归一化依赖等）只写在两个脚本自己的说明与 `--help` 里。

**TTS（`scripts/voice-clone.py`）**：

- 参数：`--input-file <narration.txt>`、`--output-dir <dir>`（其余参数见 `--help`）。
- 产物：`<output-dir>/narration.mp3`（本阶段即 `voice_clone/narration.mp3`）。

**ASR（`scripts/transcribe.py`，Phase 8 使用）**：

- 参数：`<input.mp3> <output.json>`（`--backend` 等见 `--help`）。
- 产物：`<output.json>`，transcript schema 为**句子列表**，每句：

  ```json
  {"begin": 0, "end": 60020, "text": "...",
   "words": [{"text": "为", "begin": 0, "end": 326}]}
  ```

  每个句子含 `begin`、`end`、`text` 和词级 `words`；每个词含 `text`、`begin`、`end`；时间单位是**毫秒**。token 是否带标点、带空格，数字用中文还是阿拉伯写法，都不做假设（下游对齐自行归一化）。

**两条不变量**：

1. 绝不使用 HyperFrames 自带的 `tts` / `transcribe`。
2. transcript 必须带词级时间戳。
