# topic-to-video

把一个主题、文章链接或一段文字变成有解说的视频（通常 3-10 分钟），底层使用 CosyVoice 克隆音色 TTS、Paraformer ASR、抓取到的素材，以及通过 HyperFrames 完成的渲染。

## Prerequisites

| 工具 | 说明 |
|------|------|
| Python 3 + venv | 运行任何 Python 脚本前先 `source .venv/bin/activate` |
| `dashscope` | 装在 venv 里——用于 CosyVoice TTS 与 Paraformer ASR |
| `ffmpeg` / `ffprobe` | 音频探测和抽帧 |
| `playwright` (仅 Python) | `pip install playwright`——**不要** 执行 `playwright install chromium`，本项目通过 CDP 接管系统 Chrome |
| 系统 Google Chrome | 各平台（Linux / macOS / Windows）自动检测；也可通过 `CHROME_PATH` 环境变量或 `--chrome-path` 指定。自动启动并使用位于 `{work_dir}/chrome_profile` 的共享 profile |
| `yt-dlp` | 放在 PATH 上——`scripts/video-download.py` 需要 |
| `DASHSCOPE_API_KEY` | 设置在环境变量里（例如 `~/.zshrc`）——TTS/ASR 必需 |
| `VLM_*`（可选） | 同时设 `VLM_API_KEY` + `VLM_BASE_URL` + `VLM_MODEL` 即可启用显式视觉模型；未设置时 `vision-analyze.py` 会回退到 agent 自己的 `view` 工具 |
| sub-agent 支持（Phase 8） | 优先使用当前客户端原生的 sub-agent / 委派工具。仅当用一句短 prompt 让 agent 自己读 `composition-brief.md` 时，CLI fallback 才可接受 |
| `hyperframes` + `hyperframes-cli` skills（Phase 8） | 由 composition sub-agent 加载。sub-agent 的 HyperFrames CLI 间接依赖 Node.js；主 agent 自身不写 `composition/index.html`。文档：https://hyperframes.heygen.com/quickstart |

## Quick Start

```bash
# 直接告诉主 agent 你想要什么，例如：
#   "给我做一个 90 秒讲 <主题> 的视频"
#
# 输出位于：
#   {work_dir}/{topic_name}/composition/renders/final.mp4
```

## Visual Styles

下面这些风格条目是给交付 brief 的风格路由提示，不是 composition 实现规范；最终设计由 HyperFrames sub-agent 决定。

| 风格 | 参考文件 | 字体 | 适用场景 |
|------|---------|------|---------|
| **Rosé Pine Dawn**（默认建议） | `references/design-dawn.md` | Caveat、PatrickHand、MaShanZheng、LongCang | 温暖、手绘风的讲解视频 |
| **Rosé Pine Moon** | `references/design-moon.md` | NotoSansSC、IBMPlexMono | 深色、严肃的技术 / 编辑向内容 |
