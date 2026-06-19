### Phase 7 — ASR + 字体预置

本阶段为下游的 HyperFrames sub-agent 准备时间轴与字体输入。`topic-to-video` 主 agent **不**负责设计 scene、写 `info_units`、把素材映射到布局，或者生成 HyperFrames 的 HTML。

#### 7.1 — 生成并校准 ASR transcript

如果 `{work_dir}/{topic_name}/transcribe/transcript.json` 已存在、且是包含至少一句话和词级时间戳的合法 JSON，并且 `{work_dir}/{topic_name}/transcribe/subtitle-units.json` 已存在且可读取，则跳过。

```bash
scripts/transcribe-paraformer.py \
  {work_dir}/{topic_name}/voice_clone/narration.mp3 \
  {work_dir}/{topic_name}/transcribe/transcript.json
```

默认走**本地 Qwen3-ASR + ForcedAligner**（CJK 按字 / Latin 按词的词级时间戳，自动识别语言）。可选 env：`QWEN3_ASR_MODEL`（默认 `Qwen/Qwen3-ASR-1.7B`，可指向本地目录）、`QWEN3_ALIGNER_MODEL`（默认 `Qwen/Qwen3-ForcedAligner-0.6B`）、`QWEN3_LANGUAGE`（强制语言名，缺省自动）。云端 fallback：`ASR_BACKEND=dashscope` + `DASHSCOPE_API_KEY` 走非实时 `paraformer-v2`。

随后生成 transcript-first 的字幕单元：

```bash
scripts/calibrate-transcript.py \
  --narration {work_dir}/{topic_name}/narration.txt \
  --transcript {work_dir}/{topic_name}/transcribe/transcript.json \
  --output {work_dir}/{topic_name}/transcribe/subtitle-units.json
```

校准规则：字幕单元和 timing 以 `transcribe/transcript.json` 为准；`narration.txt` 只作为纠错来源，用于高置信度匹配时修正 Latin words / 产品名 / 模型名拼写。匹配以中文内容为主，CJK 字符权重大于 Latin，并把中文数字和阿拉伯数字视作可匹配形式（如 transcript 的 `13432` 可匹配 narration 的 `一万三千四百三十二`）。找不到对应 narration 句子时，保留 transcript 文本并在 `subtitle-units.json` 中标记 `transcript_fallback`，不要阻塞流程。若 `narration.txt` 在 TTS 后被改过，必须重新生成 TTS + ASR + subtitle units。

#### 7.2 — 预置字体

如果 `{work_dir}/{topic_name}/fonts/` 已经包含所选风格对应的 `.woff2` 文件与 style CSS，则跳过。

```bash
# Dawn 默认手绘风
bash scripts/fonts-download.sh {work_dir}/{topic_name}/fonts dawn

# Moon 严肃技术 / 编辑风
bash scripts/fonts-download.sh {work_dir}/{topic_name}/fonts moon

# 如果想做一个后期可切换风格的可复用项目模板
bash scripts/fonts-download.sh {work_dir}/{topic_name}/fonts all
```

预置字体属于上游职责——这样能为 HyperFrames sub-agent 提供确定性的本地字体资源，避免不小心 fallback 到系统字体。

#### 可选 —— scene-anchor 辅助工具

`scripts/scene-anchor.py` 仍然作为一个可选的确定性辅助工具保留，给已经有一份 scene 配置、想把 scene 起点对齐到 ASR 文本的 agent 使用。它不再是主 agent 的必经阶段。Scene 切分、素材映射、视觉提示时间，以及 `composition/index.html` 的生成全部归 Phase 8 的 HyperFrames sub-agent。
