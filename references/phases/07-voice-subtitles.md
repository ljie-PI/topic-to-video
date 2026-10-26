# Phase 7 — 配音与字幕

## 输入

Phase 6 产出的 `narration.txt`（朗读稿）+ `script.txt`（显示稿）+ `narration-offsets.json`（偏移表）+ 可选的 `scene-plan.json`。

## 输出

`voice_clone/narration.mp3`（配音音频）+ `transcribe/transcript.json`（词级时间戳的句子列表）+ `transcribe/subtitle-units.json`（字幕单元）+ `transcribe/timeline.json`（段落 / cue 时间轴）。

## 完成判据

`voice_clone/narration.mp3` 存在且非空（ffprobe duration 非零且合法）；`transcript.json` 存在、非空、JSON 可解析，是句子列表且每句含 `begin` / `end` / `text` / `words`；`subtitle-units.json` 存在且 `units` 非空；`timeline.json` 存在且 `paragraphs` 非空。

## 下一步

Phase 8（composition，委派）：sub-agent 用字幕单元、时间轴和素材 catalog 完成画面与渲染；字体由 Phase 8 准备阶段按所选 design 预置。

---

TTS 与字幕合并在同一个 phase：先配音并拿到词级时间戳（transcript），再把时间对齐回显示稿生成字幕单元。本阶段为下游的 HyperFrames sub-agent 准备音频与时间轴输入；`topic-to-video` 主 agent **不**负责设计 scene、写 `info_units`、把素材映射到布局，或者生成 HyperFrames 的 HTML。

三种环境方法（backend 默认 `auto` 自动选择；`--resolve-backend` 只打印决策、不加载模型）：

| 环境 | TTS（voice-clone.py） | 词级时间戳来源 |
| --- | --- | --- |
| M 系列（arm64）Mac + mlx-audio | backend `mlx`：mlx-audio Qwen3-TTS | Qwen3-ForcedAligner 直接对齐朗读稿原文，**跳过 ASR**（transcript.json 由 voice-clone.py 一并写出） |
| 有 CUDA 的机器 | backend `qwen3tts`：torch Qwen3-TTS | 优先 `--emit-transcript`：torch Qwen3-ForcedAligner 直对齐；aligner 不可导入时退到 `transcribe.py` 全 ASR |
| 兜底 | backend `dashscope`：云端 CosyVoice | `transcribe.py`（auto → dashscope 云端 ASR） |

直对齐方案（mlx / emit-transcript）里 transcript 与朗读稿逐字一致，「ASR 结果与旁白校对映射」天然退化：7.2 的 align-narration.py 归一化 / difflib 校对逻辑照常运行但平凡通过（不会产生 `fallback: true` 单元）。

#### 7.1 — TTS 配音 + transcript

如果 `voice_clone/narration.mp3` 已存在且非空、`transcribe/transcript.json` 已是合法的 transcript contract（见本节末尾），并且 `subtitle-units.json` 与 `timeline.json` 都已存在且可读取，则跳过整个 phase。

直接使用 `scripts/voice-clone.py`。**不要**把脚本复制一份，也**不要**把解说文本粘进 Python 源码。

```bash
source .venv/bin/activate  # 从父目录或 venv 所在目录执行
python3 scripts/voice-clone.py \
  --input-file {work_dir}/{topic_name}/narration.txt \
  --output-dir {work_dir}/{topic_name}/voice_clone \
  --transcript-output {work_dir}/{topic_name}/transcribe/transcript.json \
  --emit-transcript

ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 \
  {work_dir}/{topic_name}/voice_clone/narration.mp3
```

- 后端由环境选择，参数和依赖（参考音色、Python 包、硬件要求等）见 `scripts/voice-clone.py` 的顶部说明。拿不准当前机器会选哪个后端时先跑 `python3 scripts/voice-clone.py --resolve-backend`。
- **mlx**（arm64 Mac）：合成后直接用 mlx-audio ForcedAligner 对齐朗读稿原文并写出 transcript.json（该后端默认出 transcript，不需要 `--emit-transcript`；aligner 不可用时告警并跳过，用户需按 7.2 的回退路径补 transcript）。
- **qwen3tts**（CUDA）：`--emit-transcript` 让 torch Qwen3-ForcedAligner 可用时同样直对齐出 transcript.json；aligner 不可导入时脚本只在 stderr 警告、不写 transcript.json —— 这时跑全 ASR：

  ```bash
  scripts/transcribe.py \
    {work_dir}/{topic_name}/voice_clone/narration.mp3 \
    {work_dir}/{topic_name}/transcribe/transcript.json
  ```
- **dashscope**（云端兜底）：没有本地 aligner，合成后总是跑上面这条 transcribe.py（auto 会选 dashscope ASR）。transcribe.py 的后端选择与依赖见 `scripts/transcribe.py` 的顶部说明。

脚本编写规范：
- 解说内容只放在 `narration.txt` 里。
- 避免在长复合句之前出现全角中文冒号 `：`；改用 `——`、逗号或重新断句。这能避免 TTS 偶发的停顿。

#### 7.2 — 对齐并生成字幕单元与时间轴

```bash
python3 scripts/align-narration.py \
  --transcript {work_dir}/{topic_name}/transcribe/transcript.json \
  --narration {work_dir}/{topic_name}/narration.txt \
  --offsets {work_dir}/{topic_name}/narration-offsets.json \
  --script {work_dir}/{topic_name}/script.txt \
  --units-output {work_dir}/{topic_name}/transcribe/subtitle-units.json \
  --timeline-output {work_dir}/{topic_name}/transcribe/timeline.json \
  --layout modules/layouts/<inputs.json 的 layout 字段>.json
```

字幕宽度直接取自所选 layout 的区域定义：`--layout` 读取 JSON 里的 `caption` 段（`width_px` / `font_size_px` / `max_lines`，如 `presenter` 的 1166px / 36px / 1 行、`portrait` 的 940px / 42px / 2 行），每行宽度上限按现有公式 `int(width_px / font_size_px)` 折算成 CJK 单位。layout 名从 `inputs.json` 的 `layout` 字段取，映射到 `modules/layouts/<layout>.json`（本 phase 由主 agent 显式传入；不做自动查找，design/layout 的自动接线归 composition 阶段）。显式的 `--width` / `--font-size` / `--max-lines` 仍然可用（与 `--layout` 同传时 layout 优先；两者都不传是参数错误）。如果存在带 `cues` 的 `scene-plan.json`，追加 `--scene-plan {work_dir}/{topic_name}/scene-plan.json`，cue 的秒数会写进 `timeline.json`；没有场景规划时 `timeline.json` 只含段落起止。

对齐规则：字幕文本以显示稿 `script.txt` 为准，transcript 只提供时间。脚本先把 transcript token 和朗读稿归一化（标点 / 空格 / 大小写不敏感，中文数字与阿拉伯数字等价）再做字符级对齐，然后通过偏移表映射回显示稿，品牌名和数字按显示形式出现。transcript 有而朗读稿没有的内容保留 transcript 文本，并在该字幕单元上标记 `fallback: true`；TTS 漏读的内容没有音频可依，会被丢弃并在 stderr / summary 里警告。分段先按句末标点切，超宽时在逗号、分号、顿号、冒号、破折号处断开，不在英文单词或数字内部断开，过短尾段均衡重切，不足 0.6 秒的单元并入相邻单元。详见 `scripts/align-narration.py` 的顶部说明。

产物：

- `transcribe/subtitle-units.json`：`units` 列表，每项含 `text` / `begin_s` / `end_s`（及 `begin_ms` / `end_ms` / `fallback` / `paragraph`）。
- `transcribe/timeline.json`：`total_s`、每个段落的 `begin_s` / `end_s`；传入场景规划时另有 `cues`（每个 cue 的秒数）。

若 `narration.txt` 在 TTS 后被改过，必须重新生成配音 + transcript + 字幕产物（偏移表与音频都失效）。

字体预置不属于本 phase：它随 composition 重写挪到了 Phase 8 的准备阶段，由所选 design 决定（见 `references/phases/08-composition.md` 的 8.1）。本阶段的 align-narration 只做文本与时间对齐，不读字体、不需要字体目录。

## TTS / ASR 接口契约

TTS 和 ASR 的 CLI 参数、输出路径、transcript schema 固定不变；后端可换，只要新后端满足契约即可接入。与后端绑定的说明（硬件精度、参考音频转写、数字归一化依赖等）只写在两个脚本自己的说明与 `--help` 里。

**TTS（`scripts/voice-clone.py`）**：

- 参数：`--input-file <narration.txt>`、`--output-dir <dir>`（其余参数见 `--help`）。
- 产物：`<output-dir>/narration.mp3`（本阶段即 `voice_clone/narration.mp3`）；直对齐后端（mlx，或 qwen3tts + `--emit-transcript` 且 aligner 可用时）额外写 `transcript.json`（`--transcript-output` 可改路径，本阶段指向 `transcribe/transcript.json`）。

**ASR（`scripts/transcribe.py`，仅非直对齐路径使用）**：

- 参数：`<input.mp3> <output.json>`（`--backend` 等见 `--help`）。
- 产物：`<output.json>`，transcript schema 为**句子列表**，每句：

  ```json
  {"begin": 0, "end": 60020, "text": "...",
   "words": [{"text": "为", "begin": 0, "end": 326}]}
  ```

  每个句子含 `begin`、`end`、`text` 和词级 `words`；每个词含 `text`、`begin`、`end`；时间单位是**毫秒**。token 是否带标点、带空格，数字用中文还是阿拉伯写法，都不做假设（下游对齐自行归一化）。直对齐路径写出的 transcript.json 满足同一 schema（文本与朗读稿逐字一致）。

**两条不变量**：

1. 绝不使用 HyperFrames 自带的 `tts` / `transcribe`。
2. transcript 必须带词级时间戳。
