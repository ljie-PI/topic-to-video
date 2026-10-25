# voice-utils

通用语音工具集(基于 mlx-audio,Qwen3-TTS / VoxCPM2,Apple Silicon)。

## 工具

### `narrate.py` — 旁白一站式:TTS + 对齐字幕(推荐)

把旁白文稿一步变成「配音 + 字幕」:克隆参考声音生成音频,再拿**原始文稿**
做强制对齐,产出词级/句子级时间戳和 SRT。两个模型只加载一次。

```bash
.venv/bin/python voice-utils/narrate.py --text-file 旁白文稿.txt --prefix ep01
```

输出:`ep01.wav` / `ep01.srt` / `ep01.align.json` / `ep01_metrics.json`,
stdout 末尾打印 `WAV=` / `SRT=` / `JSON=` 供脚本取用。

### `tts_qwen.py` — 单步 TTS(只要音频不要字幕时)

以参考音频克隆声音,**生成即干净,无需降噪**(Qwen codec 架构底噪比
~0.0006,比 diffusion 系模型低一个数量级,也不产生停顿幻觉)。

```bash
.venv/bin/python voice-utils/tts_qwen.py --text "要合成的文本" --prefix my_task
```

输出:
- `<prefix>.wav` — 合成音频(24kHz)
- `<prefix>_metrics.json` — 延迟与资源占用(模型加载/合成耗时、CPU、内存、GPU 显存)

### `text_align.py` — 单步对齐(已有音频+文稿,要时间戳时)

```bash
.venv/bin/python voice-utils/text_align.py --audio ep01.wav --text-file 旁白文稿.txt
```

输出:`<音频名>.align.json`(词级+句子级)/ `<音频名>.srt`

### 公共参数约定

所有工具统一遵循 CLI > 环境变量 > 默认值,无硬编码路径:

| 参数 | 环境变量 | 默认 |
|---|---|---|
| `--text` / `--text-file` / 位置参数 | `TTS_TEXT` | 必填 |
| `--voice` | `VOICE_REF` | `<repo>/resources/my_voice.wav` |
| `--ref-text` | `TTS_REF_TEXT` | 无(Qwen Base 不需要也能克隆) |
| `--language` | `TTS_LANGUAGE` | `auto` |
| `--model` | `TTS_MODEL` | `<repo>/models/Qwen3-TTS-12Hz-1.7B-Base-bf16` |
| `--aligner-model` | `ALIGNER_MODEL` | `<repo>/models/Qwen3-ForcedAligner-0.6B-8bit` |
| `--output-dir` | `TTS_OUTPUT_DIR` | 当前目录 |
| `--prefix` | `TTS_PREFIX` | `narration` / `tts` |

### 依赖

- Python 3.12 + mlx-audio 环境(仓库根目录 `.venv`)
- `psutil`(资源监控,可选,缺失时自动跳过 CPU/内存采样)

## 选型建议

| 场景 | 工具 |
|---|---|
| 旁白视频生产(音频+字幕) | `narrate.py` |
| 日常 TTS(克隆 `my_voice.wav`) | `tts_qwen.py` |
| 给已有音频+文稿出字幕 | `text_align.py` |
| 需要 48kHz / 特殊风格设计 | VoxCPM2(workflow 见 `workspace/voice_clone_voxcpm2.py`) |
| 设计全新声音(不用参考) | Qwen VoiceDesign(`workspace/voice_design_qwen.py`) |

## 生成一个自定义 voice 参考

1. 录一段干净人声 → 降噪(如 Adobe Podcast / 谱减)
2. whisper STT 出转写文本
3. 之后每次 `--voice` 指向它即可
