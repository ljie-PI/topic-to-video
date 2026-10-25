# scripts/ 语音工具说明

`scripts/` 下有两组语音相关工具。**pipeline 流程只走第一组**；第二组是独立工具集（mlx-audio），按需单独使用。

## 一、pipeline 语音链路（Phase 7「配音与字幕」，见 `references/phases/07-voice-subtitles.md`）

| 脚本 | 作用 |
|---|---|
| `voice-clone.py` | TTS + transcript 一步出。`--backend auto`（默认）按环境选后端，见下表；mlx/qwen3tts 后端可直接强制对齐朗读稿并写 `transcript.json` |
| `transcribe.py` | 全 ASR 路线（transcript 由 ASR 产生）。`--backend auto`；ASR 后端 `qwen3` / `dashscope` |
| `align-narration.py` | transcript 时间 + 朗读稿 → 字幕单元（按标点分段）+ `timeline.json` |
| `make-narration.py` | 显示稿 + 词表 → 朗读稿 `narration.txt` |

后端选择（`--backend` 或环境变量，auto 的判定顺序）：

| 环境 | 方法 | TTS 后端 | transcript 来源 |
|---|---|---|---|
| M 系列 Mac（arm64） | 最新方案（默认） | `mlx`（mlx-audio Qwen3-TTS） | ForcedAligner 直接对齐朗读稿，**跳过 ASR** |
| 有 CUDA | 旧方案 / 优先直对齐 | `qwen3tts`（torch Qwen3-TTS） | 优先 `--emit-transcript`（ForcedAligner）；不可用回退 `transcribe.py` 全 ASR |
| 其他 | 兜底 | `dashscope`（需 `DASHSCOPE_API_KEY`） | `transcribe.py --backend dashscope` |

`voice-clone.py --resolve-backend` 只打印 auto 会选什么，不加载模型，可用来排查环境。

## 二、独立语音工具（mlx-audio，按需使用）

这三个工具不接入 pipeline，适合单独跑 TTS / 出 SRT；它们输出 `.wav` / `.srt` / `.align.json`，**不**产出 pipeline 用的 `transcript.json`（那是 `voice-clone.py` 的 `--emit-transcript` 与 `text_align.py --align-json` 转换的职责）。

| 工具 | 作用 | 输出 |
|---|---|---|
| `narrate.py` | TTS + 强制对齐一站式 | `<prefix>.wav` / `.srt` / `.align.json` / `_metrics.json` |
| `tts_qwen.py` | 只做 TTS | `<prefix>.wav` + `_metrics.json` |
| `text_align.py` | 只做对齐；`--align-json <in> --emit-transcript <out>` 可把 align.json 转成 pipeline transcript schema（不需要模型） | `<stem>.align.json` / `.srt` |

公共参数约定：CLI > 环境变量 > 默认值。

| 参数 | 环境变量 | 默认 |
|---|---|---|
| `--text` / 位置参数 | `TTS_TEXT` | 必填（与下面的文件二选一） |
| `--text-file` | `TTS_TEXT_FILE` | 无；`--text` 缺席时读取该文件 |
| `--voice` | `VOICE_REF` | `resources/my_voice.wav` |
| `--ref-text` | `TTS_REF_TEXT` | 无（Qwen Base 不提供也能克隆） |
| `--language` | `TTS_LANGUAGE` | `auto` |
| `--model` | `TTS_MODEL` | `<仓库>/models/Qwen3-TTS-12Hz-1.7B-Base-bf16`（也可给 HF id） |
| `--aligner-model` | `ALIGNER_MODEL` | `<仓库>/models/Qwen3-ForcedAligner-0.6B-8bit`（也可给 HF id） |
| `--output-dir` | `TTS_OUTPUT_DIR` | 当前目录 |
| `--prefix` | `TTS_PREFIX` | `narration` / `tts` |

`text_align.py` 另有 `ALIGN_AUDIO`（等同 `--audio`）、`ALIGN_TEXT` / `ALIGN_TEXT_FILE`（文本来源）、`ALIGN_LANGUAGE`（默认 `Chinese`）与 `ALIGN_OUTPUT_BASE`；`narrate.py` 的 `--metrics` 对应 `NARRATE_METRICS_FILE`。

## 依赖

- mlx 路线：`mlx-audio`（Apple Silicon），模型可用 HF id 让 mlx 自己下载，或放本地目录并用环境变量指过去
- CUDA 路线：`torch` + Qwen3-TTS / Qwen3-ASR（依赖与参数见 `python3 scripts/voice-clone.py --help`）
- 云端路线：`DASHSCOPE_API_KEY` + `COSYVOICE_VOICE_ID`（见 `--help`）
- `psutil` 可选（资源监控，缺失时跳过采样）
- 具体后端的包、环境变量与硬件要求只写在对应脚本的 `--help` 里

## 参考音色

默认参考音频是 `resources/my_voice.wav`（转写稿 `resources/my_voice.txt`）。换成自己的音色：录一段干净人声 → 降噪 → 出转写文本 → 用 `--voice` / `VOICE_REF` 指向它。
