# Phase 8 — 对齐与字幕（ASR + 字体预置）

## 输入

Phase 7 产出的 `voice_clone/narration.mp3` + Phase 6 产出的 `script.txt`（显示稿）、`narration.txt`（朗读稿）、`narration-offsets.json`（偏移表）、可选的 `scene-plan.json`。

## 输出

`transcribe/transcript.json`（词级时间戳的句子列表）+ `transcribe/subtitle-units.json`（字幕单元）+ `transcribe/timeline.json`（段落 / cue 时间轴）+ `fonts/`（按所选 design 预置的 WOFF2 字体与 CSS，供 Phase 9 composition 使用）。

## 完成判据

`transcript.json` 存在、非空、JSON 可解析，是句子列表且每句含 `begin` / `end` / `text` / `words`；`subtitle-units.json` 存在且 `units` 非空；`timeline.json` 存在且 `paragraphs` 非空；`fonts/` 含所选 design 的 `.woff2` 与 style CSS。

## 下一步

Phase 9（composition，委派）：sub-agent 用字幕单元、时间轴、素材 catalog 和字体目录完成画面与渲染。

---

本阶段为下游的 HyperFrames sub-agent 准备时间轴与字体输入。`topic-to-video` 主 agent **不**负责设计 scene、写 `info_units`、把素材映射到布局，或者生成 HyperFrames 的 HTML。

#### 8.1 — ASR transcript

如果 `{work_dir}/{topic_name}/transcribe/transcript.json` 已存在、且是包含至少一句话和词级时间戳的合法 JSON，并且 `subtitle-units.json` 与 `timeline.json` 都已存在且可读取，则跳过。

```bash
scripts/transcribe.py \
  {work_dir}/{topic_name}/voice_clone/narration.mp3 \
  {work_dir}/{topic_name}/transcribe/transcript.json
```

后端由环境变量选择，参数和依赖见 `scripts/transcribe.py --help`。transcript schema 是固定契约（见 Phase 7 的「TTS / ASR 接口契约」）：句子列表，每句含 `begin` / `end` / `text` 和词级 `words`，毫秒。token 带不带标点、带不带空格，数字用中文还是阿拉伯写法，下游都不做假设。

#### 8.2 — 对齐并生成字幕单元与时间轴

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

对齐规则：字幕文本以显示稿 `script.txt` 为准，ASR 只提供时间。脚本先把 ASR token 和朗读稿归一化（标点 / 空格 / 大小写不敏感，中文数字与阿拉伯数字等价）再做字符级对齐，然后通过偏移表映射回显示稿，品牌名和数字按显示形式出现。ASR 听到而朗读稿没有的内容保留 ASR 文本，并在该字幕单元上标记 `fallback: true`；TTS 漏读的内容没有音频可依，会被丢弃并在 stderr / summary 里警告。分段先按句末标点切，超宽时在逗号、分号、顿号、冒号、破折号处断开，不在英文单词或数字内部断开，过短尾段均衡重切，不足 0.6 秒的单元并入相邻单元。详见 `scripts/align-narration.py --help`。

产物：

- `transcribe/subtitle-units.json`：`units` 列表，每项含 `text` / `begin_s` / `end_s`（及 `begin_ms` / `end_ms` / `fallback` / `paragraph`）。
- `transcribe/timeline.json`：`total_s`、每个段落的 `begin_s` / `end_s`；传入场景规划时另有 `cues`（每个 cue 的秒数）。

若 `narration.txt` 在 TTS 后被改过，必须重新生成 TTS + ASR + 字幕产物（偏移表与音频都失效）。

#### 8.3 — 预置字体

如果 `{work_dir}/{topic_name}/fonts/` 已经包含所选风格对应的 `.woff2` 文件与 style CSS，则跳过。

```bash
# Default 默认明亮编辑风
bash scripts/fonts-download.sh {work_dir}/{topic_name}/fonts default

# Moon 严肃技术 / 编辑风
bash scripts/fonts-download.sh {work_dir}/{topic_name}/fonts moon

# 如果想做一个后期可切换风格的可复用项目模板
bash scripts/fonts-download.sh {work_dir}/{topic_name}/fonts all
```

预置字体属于上游职责——这样能为 HyperFrames sub-agent 提供确定性的本地字体资源，避免不小心 fallback 到系统字体。
