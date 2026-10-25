# topic-to-video

把一个主题、文章链接或一段文字变成有解说的视频（通常 3-10 分钟），底层使用可切换后端的 TTS 配音与词级 ASR、抓取到的素材，以及通过 HyperFrames 完成的渲染。TTS / ASR 后端由环境变量选择，参数和依赖见两个脚本的 `--help`。

## Prerequisites

| 工具 | 说明 |
|------|------|
| Python 3 + venv | 运行任何 Python 脚本前先 `source .venv/bin/activate` |
| TTS / ASR 后端 | 后端由环境变量选择；各后端的 Python 包、环境变量与硬件要求见 `scripts/voice-clone.py --help` 和 `scripts/transcribe.py --help` |
| `ffmpeg` / `ffprobe` | 音频探测和抽帧 |
| `playwright` (仅 Python) | `pip install playwright`——**不要** 执行 `playwright install chromium`，本项目通过 CDP 接管系统 Chrome |
| 系统 Google Chrome | 各平台（Linux / macOS / Windows）自动检测；也可通过 `CHROME_PATH` 环境变量或 `--chrome-path` 指定。自动启动并使用位于 `{work_dir}/chrome_profile` 的共享 profile |
| `yt-dlp` | 放在 PATH 上——`scripts/video-download.py` 需要 |
| `VLM_*`（可选） | 同时设 `VLM_API_KEY` + `VLM_BASE_URL` + `VLM_MODEL` 即可启用显式视觉模型；未设置时 `vision-analyze.py` 会回退到 agent 自己的 `view` 工具 |
| sub-agent 支持（Phase 9 composition） | 优先使用当前客户端原生的 sub-agent / 委派工具。仅当用一句短 prompt 让 agent 自己读 `composition-handoff.md` 与工作区里物化的委派包（`references/delegation/composition/`）和 modules 副本时，CLI fallback 才可接受 |
| `hyperframes` + `hyperframes-cli` + `hyperframes-animation` skills（Phase 9 composition） | 由 composition sub-agent 加载；`hyperframes-animation` 的当前索引用于必需的动画能力发现，涉及 FLIP / path / mask / SVG / 3D keyframes 时按需加载 `hyperframes-keyframes`。sub-agent 的 HyperFrames CLI 间接依赖 Node.js；主 agent 自身不写 `composition/index.html`。文档：https://hyperframes.heygen.com/quickstart |

## TTS / ASR（后端由环境变量选择）

TTS 与 ASR 的输入输出格式固定，后端可换：只要新后端满足接口契约即可接入。

- **两条不变量**：绝不使用 HyperFrames 自带的 `tts` / `transcribe`；ASR 产物 transcript 必须带词级时间戳。
- **TTS**：`scripts/voice-clone.py` 把 `narration.txt` 合成 `voice_clone/narration.mp3`。后端、参考音色、参数和依赖见 `--help`。
- **ASR**：`scripts/transcribe.py` 把配音转成带词级时间戳的句子列表（transcript schema 见 Phase 7 / 8 文档的接口契约）。后端、参数和依赖见 `--help`。

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
| 风格 | 从措辞推断，或读取工作区 `style-prompt.md`（见 Visual Styles） | Frag Note Default |
| 时长 | 通常 3-10 分钟 | 5 分钟 |
| 语言 | 解说语言 | 中文 |
| 视觉素材 | 是否联网搜索图片 / 视频片段来丰富场景 | 是 |

> 也可以在项目工作区放一份 `style-prompt.md`（自由文本），它会覆盖默认风格推断，并作为 composition 项目指令的一部分传给下游 composition agent（叠加顺序见 `references/delegation/conventions.md`）。

### 工作流（状态脚本驱动的 10 个 phase）

主 agent 每次运行 `scripts/pipeline-status.py <workspace>`，只读它指出的那一份 phase 文档并执行，如此循环直到全部完成。论文模式（`input_mode = "paper"`）会多出一个 Phase 2（解析论文）；`fetch_materials = false` 时 Phase 4 / 5 跳过。

| Phase | 做什么 |
|-------|--------|
| 1 | 收集输入（落盘 `inputs.json`） |
| 2 | 解析论文（仅论文模式） |
| 3 | 主题调研（落盘 `research-brief.md`） |
| 4 | 从 URL 抓取图片 / 视频素材（可跳过） |
| 5 | 视觉分析 + 建立素材 catalog |
| 6 | 撰写解说脚本、匹配场景素材、规划屏幕文本块 |
| 7 | TTS 配音（后端由环境变量选择） |
| 8 | 词级 ASR + 字幕对齐 |
| 9 | composition handoff + sub-agent 组装与渲染（字体在准备阶段按所选 design 预置） |
| 10 | 混入背景音乐 |

### 输出

- 主产物：`{work_dir}/{topic_name}/composition/renders/final.mp4`
- 含背景音乐版本（Phase 10 后）：`{work_dir}/{topic_name}/composition/renders/final_with_bgm.mp4`

### 断点续跑（Checkpoint & Resume）

每个 phase 的产物都会落盘。续跑入口是唯一的：`python3 scripts/pipeline-status.py {work_dir}/{topic_name}` 输出已完成的 phase、下一个 phase、要读的文档以及缺失 / 损坏的产物；某个产物被删掉或写坏时，脚本自动回退到对应 phase。也可以说 “redo phase N” 强制重跑某个 phase。

## 开发

测试只走脚本的命令行 seam（stdout 一个 JSON + 退出码 0 / 1 / 2），不断内部函数。运行方式：

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

## Visual Styles

下面这些风格条目是 Phase 1 选择 design 的参考；选定后 composition 的颜色、字体、动效只取该 design 的 token，最终画面由 composition sub-agent 决定。

| 风格 | 参考文件 | 字体 | 适用场景 |
|------|---------|------|---------|
| **Frag Note Default**（默认） | `modules/designs/default/default.md` | NotoSansSC、IBMPlexMono | 暖白 + 克制薰衣草的安静编辑风 |
| **Rosé Pine Dawn** | `modules/designs/dawn/dawn.md` | Caveat、PatrickHand、MaShanZheng、NotoSansSC | 温暖、手绘风的讲解视频 |
| **Rosé Pine Moon** | `modules/designs/moon/moon.md` | NotoSansSC、IBMPlexMono | 深色、严肃的编辑向内容 |
| **GitHub** | `modules/designs/github/github.md` | NotoSansSC、IBMPlexMono | GitHub trending / repo launch / 开源项目介绍 |
| **Product Hunt** | `modules/designs/producthunt/producthunt.md` | NotoSansSC、IBMPlexMono | Product Hunt 周榜 / SaaS launch / 新产品发布 |
