# topic-to-video

把一个主题、文章链接或一段文字变成有解说的视频（通常 3-10 分钟），底层使用本地 Qwen3-TTS 克隆音色 TTS、本地 Qwen3-ASR 词级 ASR（均以 DashScope 云端作 fallback）、抓取到的素材，以及通过 HyperFrames 完成的渲染。

## Prerequisites

| 工具 | 说明 |
|------|------|
| Python 3 + venv | 运行任何 Python 脚本前先 `source .venv/bin/activate` |
| `torch` (CUDA) + `qwen-tts` + `qwen-asr` + `wetext` + `soundfile` | 装在 venv 里——本地 TTS（Qwen3-TTS）与本地 ASR（Qwen3-ASR + ForcedAligner）。本地 ASR 默认开 ITN（中文数字→阿拉伯），用独立包 `wetext`（缺失则自动跳过 ITN）。需要 NVIDIA GPU；Turing（如 2080 Ti）用 fp16、不装 flash-attn |
| `dashscope` | 装在 venv 里——云端 fallback：CosyVoice TTS（`TTS_BACKEND=dashscope`）与 Paraformer ASR（`ASR_BACKEND=dashscope`） |
| `ffmpeg` / `ffprobe` | 音频探测和抽帧 |
| `playwright` (仅 Python) | `pip install playwright`——**不要** 执行 `playwright install chromium`，本项目通过 CDP 接管系统 Chrome |
| 系统 Google Chrome | 各平台（Linux / macOS / Windows）自动检测；也可通过 `CHROME_PATH` 环境变量或 `--chrome-path` 指定。自动启动并使用位于 `{work_dir}/chrome_profile` 的共享 profile |
| `yt-dlp` | 放在 PATH 上——`scripts/video-download.py` 需要 |
| 本地 TTS 参考音频 | `TTS_REF_WAV` 指向要克隆的音色 WAV——本地 TTS 必需（旧别名 `VOXCPM_REF_WAV` 仍兼容） |
| `DASHSCOPE_API_KEY` | 仅在用云端 fallback（`TTS_BACKEND`/`ASR_BACKEND=dashscope`）时需要 |
| `VLM_*`（可选） | 同时设 `VLM_API_KEY` + `VLM_BASE_URL` + `VLM_MODEL` 即可启用显式视觉模型；未设置时 `vision-analyze.py` 会回退到 agent 自己的 `view` 工具 |
| sub-agent 支持（Phase 8） | 优先使用当前客户端原生的 sub-agent / 委派工具。仅当用一句短 prompt 让 agent 自己读 `composition-handoff.md`、工作区本地 `references/composition-rules.md` 与 `references/composition-stage-protocol.md` 时，CLI fallback 才可接受 |
| `hyperframes` + `hyperframes-cli` skills（Phase 8） | 由 composition sub-agent 加载。sub-agent 的 HyperFrames CLI 间接依赖 Node.js；主 agent 自身不写 `composition/index.html`。文档：https://hyperframes.heygen.com/quickstart |

## 本地 TTS / ASR（默认，可切云端）

默认在本地 GPU 上推理，无需云端 key：

- **TTS = 本地 Qwen3-TTS 克隆音色**：`TTS_REF_WAV` 指向要克隆的参考音频；脚本会用 Qwen3-ASR 自动转写参考音频并缓存为同名 `<ref>.txt`（也可用 `TTS_REF_TEXT` 直接给）。
- **ASR = 本地 Qwen3-ASR + ForcedAligner**：返回词级时间戳；默认开 ITN（中文数字→阿拉伯，如 `三点一→3.1`、`二零二六年六月→2026年6月`），`ASR_ITN=0` 关。
- **模型**：首次运行自动从 HuggingFace 下载（Qwen3-TTS-12Hz-1.7B-Base、Qwen3-ASR-1.7B、Qwen3-ForcedAligner-0.6B）；也可用 `QWEN3TTS_MODEL` / `QWEN3_ASR_MODEL` / `QWEN3_ALIGNER_MODEL` 指向已下载的本地目录。
- **切云端 fallback**：`export TTS_BACKEND=dashscope` / `export ASR_BACKEND=dashscope`，并设 `DASHSCOPE_API_KEY`（TTS 还需 `COSYVOICE_VOICE_ID`）。

| 环境变量 | 默认 | 说明 |
|------|------|------|
| `TTS_BACKEND` | `qwen3tts` | `qwen3tts`（本地）\| `dashscope`（云端 CosyVoice） |
| `ASR_BACKEND` | `qwen3` | `qwen3`（本地）\| `dashscope`（云端 paraformer-v2） |
| `TTS_REF_WAV` / `TTS_REF_TEXT` | — | 克隆参考音频 / 其 transcript（旧别名 `VOXCPM_REF_*` 仍兼容） |
| `ASR_ITN` | `1` | 中文数字→阿拉伯，`0` 关 |
| `QWEN3TTS_MODEL` / `QWEN3_ASR_MODEL` / `QWEN3_ALIGNER_MODEL` | HF id | 可指向本地模型目录 |

> GPU 注意：本地推理用 **fp16**，**不要**装 flash-attn（Turing/sm_75 不支持）。两个多 GB 模型分阶段顺序加载，单卡 11GB 可跑。

## Quick Start

```bash
# 直接告诉主 agent 你想要什么，例如：
#   "给我做一个 90 秒讲 <主题> 的视频"
#
# 输出位于：
#   {work_dir}/{topic_name}/composition/renders/final.mp4
```

## 使用方法

### 如何触发

无需记命令，直接用自然语言把需求告诉主 agent 即可，例如：

- “给我做一个 90 秒讲 <某主题> 的视频。”
- “把这篇文章做成 5 分钟的解说视频：<文章 URL>。”
- “根据这段文字做一段竖屏讲解视频。”（随后粘贴文本）

### Phase 1 会先和你确认这些输入

主 agent 会一次问一个问题，逐项确认：

| 输入 | 说明 | 默认 |
|------|------|------|
| 来源 | 要抓取的 URL、粘贴的文本，或仅一个主题 | — |
| 方向 | `1920×1080`（横屏）/ `1080×1920`（竖屏）/ `1080×1440`（3:4） | — |
| 风格 | 从措辞推断，或读取工作区 `style-prompt.md`（见 Visual Styles） | Rosé Pine Dawn |
| 时长 | 通常 3-10 分钟 | 5 分钟 |
| 语言 | 解说语言 | 中文 |
| 视觉素材 | 是否联网搜索图片 / 视频片段来丰富场景 | 是 |

> 也可以在项目工作区放一份 `style-prompt.md`（自由文本），它会覆盖默认风格推断，并作为 style hint 传给下游 composition。

### 工作流（9 个 Phase）

主 agent 自动串联下列 phase；除 Phase 1 的确认外，通常无需人工介入：

| Phase | 做什么 |
|-------|--------|
| 1 | 收集输入（主题 / 方向 / 风格 / 时长 / 语言） |
| 2 | 主题调研（Gemini Deep Research + web search） |
| 3 | 从 URL 抓取图片 / 视频素材（可跳过） |
| 4 | 视觉分析 + 建立素材 catalog |
| 5 | 撰写解说脚本、匹配场景素材、规划屏幕文本块 |
| 6 | 本地 Qwen3-TTS 克隆音色生成解说音频 |
| 7 | 本地 Qwen3-ASR 词级时间戳 + 确定性字体预置 |
| 8 | HyperFrames composition handoff + sub-agent 渲染 |
| 9 | 混入背景音乐 |

### 输出

- 主产物：`{work_dir}/{topic_name}/composition/renders/final.mp4`
- 含背景音乐版本（Phase 9 后）：`{work_dir}/{topic_name}/composition/renders/final_with_bgm.mp4`

### 断点续跑（Checkpoint & Resume）

每个 phase 的产物都会落盘。再次对同一 `{topic_name}` 发起请求时，主 agent 会发现已有工作区并询问是从中断处 resume 还是从头开始；也可以说 “redo phase N” 强制重跑某个 phase。

## Visual Styles

下面这些风格条目是给 composition handoff 的风格路由提示，不是 composition 实现规范；最终设计由 HyperFrames sub-agent 决定。

| 风格 | 参考文件 | 字体 | 适用场景 |
|------|---------|------|---------|
| **Rosé Pine Dawn**（默认建议） | `references/design-dawn.md` | Caveat、PatrickHand、MaShanZheng、NotoSansSC | 温暖、手绘风的讲解视频 |
| **Rosé Pine Moon** | `references/design-moon.md` | NotoSansSC、IBMPlexMono | 深色、严肃的编辑向内容 |
| **GitHub** | `references/design-github.md` | NotoSansSC、IBMPlexMono | GitHub trending / repo launch / 开源项目介绍 |
| **Product Hunt** | `references/design-producthunt.md` | NotoSansSC、IBMPlexMono | Product Hunt 周榜 / SaaS launch / 新产品发布 |
| **News（新闻洞察）** | `references/design-news.md` | NotoSansSC、IBMPlexMono | 白底 + 品牌紫，可信编辑风的新闻解读 / 时事分析 / 深度报道 |
| **Tech（技术讲解）** | `references/design-tech.md` | NotoSansSC、IBMPlexMono | 暖奶油 + 纯等宽 + 终端 manpage 感的技术讲解 / CLI / 命令行原理 |
