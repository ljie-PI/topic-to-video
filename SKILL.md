---

name: topic-to-video
description: 当用户提供一个主题、文章 URL 或文本，并请求做一段有解说的视频（通常 3-10 分钟）时使用。本 skill 拥有上游 pipeline —— 主题调研、可选的视觉素材抓取、素材理解、解说撰写、通过 DashScope 调用 CosyVoice 完成克隆音色 TTS、用 Paraformer 拿词级 ASR 时间戳、确定性字体预置，以及一份精简的 HyperFrames composition handoff。HyperFrames composition、scene 设计、HTML/CSS/GSAP、lint/inspect 与渲染都委派给 hyperframes 和 hyperframes-cli 两个 skill。

---

# Topic → Video（HyperFrames + CosyVoice 工作流）

## 本 skill 产出什么

一段有解说的视频（3-10 分钟），使用：

- **Web 调研** 在写脚本之前获取准确的内容
- **HyperFrames** 用于下游 HTML composition + 渲染（delegated）
- **CosyVoice**（通过 Aliyun DashScope）实现克隆音色 TTS —— 默认中文
- **Paraformer**（通过 DashScope）拿词级 ASR 时间戳
- 一份可配置的 style hint，交给下游 HyperFrames sub-agent

**输出：** `{work_dir}/{topic_name}/composition/renders/final.mp4`，可直接发布（由 Phase 8 coding sub-agent 产出）。

## 规则与排错

下面这些规则，每一条都对应基线 agent 踩过的某个具体 bug。**DO NOT "改进"这些规则——除非先重新跑完 `references/gotchas.md` 里的 gauntlet。**

### 研究与脚本

0. **写之前先调研。** Phase 2 是强制的。每个论断都通过 Gemini Deep Research + `web_search` 落地。
   ↳ DO NOT：调研之前写脚本；没有明确条件就跳过 Gemini；用户给了 PDF 还跳过 Phase 2a；用训练数据描述一篇论文。
1. **素材选择在 Phase 4，不是 Phase 5。** 写解说之前先跑 vision-analyze。
   ↳ DO NOT：catalog 还没建就写解说；跳过 vision-analyze。

### TTS / ASR

2. **TTS = 通过 DashScope 调用 CosyVoice。** 用克隆音色。**绝不**使用 `npx hyperframes tts`。
3. **ASR = DashScope 非实时识别（默认 `paraformer-v2`）。** HTTP REST 异步任务接口，自动识别 sample rate / format，无需 ffprobe 探测。
   ↳ DO NOT：用 Whisper / `npx hyperframes transcribe`；硬编码 sample_rate；切回 `paraformer-realtime-v2`（实时模型上限 ~5min 且必须手动传 format/sample_rate）。
   ↳ 可选切换：`export ASR_MODEL=qwen3-asr-flash-filetrans` 或其他兼容文件转写模型。

### 字体与文本

4. **预先 stage 确定性的 WOFF2 字体。** 用 `scripts/fonts-download.sh` 下载，然后让 Phase 8 handoff 指向 `fonts/`。
   ↳ DO NOT：让主 agent 处理 composition 的字体 CSS。
5. **字体实现归 HyperFrames。** Phase 8 sub-agent 使用本地字体，并按 `hyperframes` skill 中的排版规则处理。

### 素材

6. **每个资源都能追溯到 `material-catalog.json`。** 没有 catalog 引用 → 屏幕上不出现该资源。**视频材料一律剥音轨**：catalog 阶段 `ffmpeg -an` 输出；Phase 8 HTML 嵌入时 `<video>` 标签必须带 `muted playsinline` 兜底。
   ↳ DO NOT：嵌入整段原视频；切片段时不带 `-an`；`<video>` 漏 `muted`。
   ↳ Fix：片段里漏音 → 用 `ffmpeg -c:v copy -an` 重剪；已嵌入 HTML 的 `<video>` 缺 `muted` → 补上。
7. **素材搜索是可选但推荐的。** 用户说"skip materials"或自带全部视觉时跳过。

### Composition

8. **Composition 委派给 HyperFrames sub-agent。** 主 agent 只写 `composition-handoff.md`，并把固定 rules / design references 物化到项目工作区的 `references/` 下。
   ↳ DO NOT：手写 `composition/index.html`、挑选 GSAP 模式，或在本 session 里修 HyperFrames lint。
9. **Scene 设计归 HyperFrames。** 切分、素材映射、布局、视觉层级、动画、lint/inspect 与渲染迭代都发生在 Phase 8。

### 环境与工具

10. **跑 Python 前一律 `source .venv/bin/activate`。** 用 `python3`。
    ↳ 修复：`playwright` import 出错 → `pip install playwright`。`mineru` 找不到 → `pip install "mineru[pipeline]"`。
11. **Chrome over CDP。** 共享 profile 位于 `{work_dir}/chrome_profile/`。
    ↳ 修复：Chrome 立刻退出 → 关掉另一个使用该 profile 的 Chrome。缺 `$DISPLAY` → `--headless on`。Sandbox 报错 → `--no-sandbox`（以 root 运行时自动启用）。Cookie banner → 在 profile 里 accept 一次。
12. **视频下载顺序执行。** yt-dlp 并行时会被限速。
    ↳ 修复：下载失败 → 保留 `download_required: true`，Phase 4 会忽略它。

### 排错

| 症状 | 修复 |
| --- | --- |
| `WARN: anchor not found for X` | 检查大小写不一致；从实际 ASR 文本里挑 anchor |
| `vision-analyze.py` 返回 `delegate_to_agent` | 设置 `VLM_API_KEY` / `VLM_BASE_URL` / `VLM_MODEL`，或用 `view` 工具 |
| `harvest-pages.py` 返回 0 张图 | 调大 `--page-load-timeout` |
| `parse-pdf.py` 云端返回 `-60007` | 自动 fallback 到本地 `mineru` CLI |
| `parse-pdf.py` 云端 URL 超时 | 改用 `--pdf` 配本地文件，而不是 `--url` |
| CDP 端口 9222 被占 | 传 `--cdp-url http://localhost:9223` |

## Checkpoint 与恢复

跑任何工具之前，检查其输出是否已存在。已存在则跳过并复用。

| Phase | 已存在则跳过 |
| --- | --- |
| 2 | `gemini_deep_research.md` |
| 2a | `harvest_page/main-paper/metadata.json` |
| 2c | `harvest_page/related-*/metadata.json` |
| 3 | `harvest_page/manifest.json` 且 `entries[]` 非空 |
| 3.b | `harvest_page/<slug>/videos/` 下视频存在 且 `download_required: false` |
| 4 | `extract_frames/<slug>/<video>/` 有 ≥1 张 JPEG；或 `material-catalog.json` 含 `selected_clips` |
| 5 | `narration.txt`（非空） |
| 5.5 | `scene-material-suggestions.json`（非空） |
| 6 | `voice_clone/narration.mp3` |
| 7a | `transcribe/transcript.json` |
| 7b | `fonts/` 至少含 1 个 `.woff2` 和对应的 style CSS |
| 8 | `composition/renders/final.mp4` |
| 9 | `composition/renders/final_with_bgm.mp4` |

工作区发现发生在 Phase 1：检查 `{work_dir}/{topic_name}/` 是否存在，扫描其中的输出，问用户是 resume 还是从头开始。如果文件存在但损坏（0 字节、JSON 截断），删掉重跑。用户可以用"redo phase N"强制重跑。

## 输出约定

所有脚本都把 JSON 输出到 stdout，人类可读 log 输出到 stderr，并使用以下退出码：`0`=成功，`1`=运行时错误，`2`=参数非法。

**工作区布局：** 输出位于 `{work_dir}/{topic_name}/`，包含标准子目录：
`harvest_page/`、`extract_frames/`、`vision_analyze/`（含 `topic-context.txt`）、`material-catalog.json`、`scene-material-suggestions.json`、`voice_clone/`、`transcribe/`、`fonts/`、`composition/`、`references/`、`narration.txt`、`composition-handoff.md`。

共享 Chrome profile：`{work_dir}/chrome_profile/` —— **不要**删除。

## 工作流（9 个 Phase）

执行每个 phase 之前，先读它对应的文档。

| Phase | 文档 | 内容 |
| --- | --- | --- |
| 1 | `references/phases/gather-inputs.md` | 收集输入（主题、方向、风格、时长） |
| 2 | `references/phases/research.md` | 主题调研（Gemini Deep Research + web search） |
| 3 | `references/phases/material-harvest.md` | 从 URL 抓取图片 / 视频 |
| 4 | `references/phases/material-selection.md` | 视觉分析 + 素材 catalog |
| 5 | `references/phases/narration-script.md` | 撰写解说脚本 |
| 5.5 | `references/phases/narration-script.md` | 场景-素材匹配建议（inline，主 agent 完成） |
| 6 | `references/phases/tts-generation.md` | 用 CosyVoice 生成 TTS 音频 |
| 7 | `references/phases/asr-transcript-generation.md` | ASR + 字体预置 |
| 8 | `references/phases/composition-render.md` | HyperFrames handoff + sub-agent 渲染 |
| 9 | `references/phases/bgm-mix.md` | 混入背景音乐 |

## 工具与依赖

| 脚本 | 用途 | 依赖 |
| --- | --- | --- |
| `fonts-download.sh` | 确定性 WOFF2 字体下载 + 本地 CSS | — |
| `voice-clone.py` | CosyVoice TTS | `DASHSCOPE_API_KEY` |
| `transcribe-paraformer.py` | DashScope 非实时 ASR（默认 `paraformer-v2`，可用 `ASR_MODEL` 覆盖） | `DASHSCOPE_API_KEY` |
| `scene-anchor.py` | 可选辅助：把预先设计好的 scene 锚定到 ASR 词流 | — |
| `extract-frames.py` | ffmpeg 抽帧 | `ffmpeg` |
| `subtitle-parse.py` | SRT/VTT 解析 + 关键词过滤 | — |
| `vision-analyze.py` | VLM 分析（或委派回 agent 的 `view`） | `VLM_*`（可选） |
| `gemini-deep-research.py` | Gemini Deep Research 自动化 | `playwright`、已登录的 Chrome |
| `parse-pdf.py` | 通过 MinerU 云端 / 本地解析 PDF | `MINERU_API_TOKEN` 或 `mineru[pipeline]` |
| `harvest-pages.py` | 批量 URL 抓取（图片 / 视频 / 滚动） | `playwright`、系统 Chrome |
| `video-download.py` | YouTube/Bilibili 下载 | `yt-dlp` |
| `mix-bgm.py` | 把 BGM 混入视频 | `ffmpeg` |
| `merge-paper-manifest.py` | 把论文解析 manifest 条目并入 harvest manifest | — |
| `apply-video-download-result.py` | 把 yt-dlp 下载结果应用到 manifest metadata | — |
| `check-cjk-fonts.py` | 渲染后可选的 CJK 字体 sanity check | — |

**系统依赖：** `ffmpeg`、`playwright`（`pip install playwright`，**不要**执行 `playwright install chromium`）、系统 Chrome（自动检测）、`yt-dlp`、带 venv 的 `python3`。

**Python 包（装到 venv 里）：** `dashscope`（CosyVoice TTS + Paraformer ASR），以及所有辅助脚本 import 的依赖。