### Phase 7 — ASR + 字体预置

本阶段为下游的 HyperFrames sub-agent 准备时间轴与字体输入。`topic-to-video` 主 agent **不**负责设计 scene、写 `info_units`、把素材映射到布局，或者生成 HyperFrames 的 HTML。

#### 7.1 — 生成 ASR transcript

如果 `{work_dir}/{topic_name}/transcribe/transcript.json` 已存在、且是包含至少一句话和词级时间戳的合法 JSON，则跳过。

```bash
scripts/transcribe-paraformer.py \
  {work_dir}/{topic_name}/voice_clone/narration.mp3 \
  {work_dir}/{topic_name}/transcribe/transcript.json
```

DashScope Paraformer-v2 默认开启 inverse text normalization（ITN），narration 里的中文数字（如"一万六千二百八十八"、"二零二六"）会在 ASR 输出中自动转成阿拉伯数字（`16288`、`2026`），无需额外后处理脚本。

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
