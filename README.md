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

## Visual Styles

下面这些风格条目是给 composition handoff 的风格路由提示，不是 composition 实现规范；最终设计由 HyperFrames sub-agent 决定。

| 风格 | 参考文件 | 字体 | 适用场景 |
|------|---------|------|---------|
| **Rosé Pine Dawn**（默认建议） | `references/design-dawn.md` | Caveat、PatrickHand、MaShanZheng、LongCang | 温暖、手绘风的讲解视频 |
| **Rosé Pine Moon** | `references/design-moon.md` | NotoSansSC、IBMPlexMono | 深色、严肃的技术 / 编辑向内容 |
