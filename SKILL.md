---
name: topic-to-video
description: 当用户提供一个主题、文章 URL、论文 PDF 或链接、一段粘贴的文本，并请求做成一段有解说的视频（通常 3-10 分钟，横屏或竖屏）时使用。
---

# Topic → Video 工作流

## 本 skill 产出什么

一段有解说的视频（3-10 分钟），使用：

- **Web 调研** 在写脚本之前获取准确的内容
- **HyperFrames** 用于下游 HTML composition + 渲染（delegated）
- **TTS / ASR** 生成配音并拿回词级时间戳；后端由环境变量选择，参数和依赖见两个脚本的 `--help`
- 一份 design / layout / template 选择，约束下游 composition 的外观与版面

**输出：** `{work_dir}/{topic_name}/composition/renders/final.mp4`，可直接发布（由 Phase 8 coding sub-agent 产出）；Phase 9 混入 BGM 后得到 `final_with_bgm.mp4`。

## 工作流：一个循环

**禁止预读其他 phase 文档。** 每次只读 `pipeline-status` 指出的那一份 phase 文档；除此之外不要打开 `references/phases/` 下的任何其他文件。

1. 运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}`（工作区目录必填）。它输出一个 JSON：已完成的 phase、下一个 phase、要读的文档、缺失 / 损坏的产物。
2. 只读它指出的那一份 phase 文档（`next_phase.doc`）。
3. 按该文档执行；文档头部的「输入 / 输出 / 完成判据 / 下一步」是自包含的，不需要查其他 phase 文档。
4. 回到第 1 步，直到脚本报告 `next_phase` 为 `null`（全部完成）。

续跑与回退都由状态脚本驱动：某个 phase 的产物被删掉或写坏时，脚本会自动回退到那个 phase。用户说 "redo phase N" 时，删掉对应产物再跑状态脚本即可。不要自己扫描工作区猜进度，也不要把 Scratchpad 当进度记录——`inputs.json` 和各 phase 产物才是唯一状态。

## 核心护栏

这些规则是常驻上下文的高风险护栏；具体症状、原因和恢复方式见 `references/gotchas.md`。修改这些规则前，先 review gotchas 中对应条目，确认不会重开历史坑。

### 研究与脚本

0. **写之前先调研。** Phase 3 是强制的。每个论断都通过 Gemini Deep Research + `web_search` 落地。
   ↳ DO NOT：调研之前写脚本；没有明确条件就跳过 Gemini；用户给了 PDF 还跳过 Phase 2；用训练数据描述一篇论文。
1. **素材 catalog / vision 分析在 Phase 5，不是 Phase 6。** Phase 6 只引用 catalog 写脚本、匹配场景素材并规划屏幕文本块。
   ↳ DO NOT：catalog 还没建就写解说或场景-素材匹配；跳过 vision-analyze。

### TTS / ASR

2. **TTS 后端由环境变量选择。** 配音脚本、参考音色、参数和依赖见 `scripts/voice-clone.py` 的顶部说明。**绝不**使用 `npx hyperframes tts`。
3. **ASR 后端由环境变量选择。** transcript 必须带词级时间戳（schema 见 Phase 7 文档的接口契约）。后端、参数和依赖见 `scripts/transcribe.py` 的顶部说明；直对齐后端（voice-clone.py 的 mlx，或启用转写的 qwen3tts）由配音脚本直接写出 transcript，跳过 ASR。
   ↳ DO NOT：用 `npx hyperframes transcribe`；接受没有词级时间戳的 transcript。

### 字体与文本

4. **预先 stage 确定性的 WOFF2 字体。** Phase 8 的 `scripts/prepare-handoff.py` 按所选 design 调用 `scripts/fonts-download.sh`，预置到 composition 工程的 `assets/fonts/`，handoff 指向该目录。
   ↳ DO NOT：让主 agent 处理 composition 的字体 CSS。
5. **字体实现归 HyperFrames。** Phase 8 sub-agent 使用本地字体，并按 `hyperframes` skill 中的排版规则处理。

### 素材

6. **每个资源都能追溯到 `material-catalog.json`。** 没有 catalog 引用 → 屏幕上不出现该资源。**视频材料一律剥音轨**：catalog 阶段 `ffmpeg -an` 输出；Phase 8 HTML 嵌入时 `<video>` 标签必须带 `muted playsinline` 兜底。
   ↳ DO NOT：嵌入整段原视频；切片段时不带 `-an`；`<video>` 漏 `muted`。
7. **素材搜索是可选但推荐的。** `inputs.json` 里 `fetch_materials = false` 或用户自带全部视觉时跳过（Phase 4 / 5 一起跳过）。

### Composition

8. **Composition 委派给 coding agent。** 主 agent 只运行 `scripts/prepare-handoff.py <ws> composition`：它生成 `composition-handoff.md`，把 composition 委派包（`references/delegation/composition/`）与 modules（不含 `examples/`）物化到工作区，再按所选 design 预置字体；委派约定与指令叠加顺序见 `references/delegation/conventions.md`。
   ↳ DO NOT：手写 `composition/index.html`、挑选低层 animation / effect skill，或在本 session 里修 HyperFrames lint；除非用户明确指定，否则由 Phase 8 sub-agent 选择。
9. **Scene 设计归 HyperFrames。** 切分、素材映射、布局、视觉层级、动画、lint/inspect 与渲染迭代都发生在 Phase 8。

### 环境与工具

10. **跑 Python 前一律 `source .venv/bin/activate`。** 用 `python3`。
11. **Chrome over CDP。** `harvest-pages.py` 和 `gemini-deep-research.py` 必须显式传 `--profile-dir {work_dir}/chrome_profile`。复用已运行的 CDP 时，启动参数不会生效；检查 stderr warning 和输出 JSON 的 `chrome.ignored_flags`，需要新配置就先关闭复用的 Chrome。
12. **视频下载顺序执行。** yt-dlp 并行时会被限速。

## 输出约定

所有脚本都把 JSON 输出到 stdout，人类可读 log 输出到 stderr，并使用以下退出码：`0`=成功，`1`=运行时错误，`2`=参数非法。`scripts/pipeline-status.py` 遵循同一约定，它的 JSON 额外携带 `completed_phases` / `next_phase` / `missing_products` / `corrupt_products` ——它是整个流程唯一的续跑入口，取代了过去的人工 checkpoint 表。

共享 Chrome profile：`{work_dir}/chrome_profile/` —— **不要**删除。

## 工具与依赖

| 脚本 | 用途 | 依赖 |
| --- | --- | --- |
| `pipeline-status.py` | 扫描工作区，输出已完成 / 下一个 phase、要读的文档、缺失或损坏的产物 | — |
| `prepare-handoff.py` | 委派步骤（script / composition）的准备：物化委派包（composition 另含 modules 与预置字体）、生成 handoff，输出可原样派发的 `dispatch_prompt` | — |
| `fonts-download.sh` | 把仓库里预置的 WOFF2 字体（`resources/fonts/<design>/`）装进工程，不联网；`--refresh` 才从 Google Fonts 重新下载（维护用） | — |
| `voice-clone.py` | TTS：把 `narration.txt` 合成 `voice_clone/narration.mp3`；后端由环境变量选择 | 见脚本顶部说明 |
| `transcribe.py` | ASR：输出带词级时间戳的 transcript；后端由环境变量选择 | 见脚本顶部说明 |
| `align-narration.py` | 把 ASR 时间对齐回显示稿，生成字幕单元（subtitle-units.json）与时间轴（timeline.json） | — |
| `check-composition.py` | composition 渲染前检查：越界 / reserved 区域侵入 / 文字溢出 / 资源与字体加载 / 字号下限 / 字幕一致性 | `playwright`、系统 Chrome |
| `check-render.py` | 渲染后确定性检查：音轨与时长偏差 / 朝向分辨率 / 黑屏与黑尾 / 冻结（发现映射回 scene_id） | `ffmpeg` |
| `make-contact-sheet.py` | 每 scene 中点帧拼 2×2 contact sheet（strict 加入场帧与切点帧），标注 scene_id 与时间戳 | `ffmpeg`、`Pillow` |
| `extract-frames.py` | ffmpeg 抽帧 | `ffmpeg` |
| `subtitle-parse.py` | SRT/VTT 解析 + 关键词过滤 | — |
| `vision-analyze.py` | VLM 分析（或委派回 agent 的 `view`） | `VLM_*`（可选） |
| `gemini-deep-research.py` | Gemini Deep Research 自动化 | `playwright`、已登录的 Chrome |
| `parse-pdf.py` | 通过 MinerU 云端 / 本地解析 PDF | `MINERU_API_TOKEN` 或 `mineru[pipeline]` |
| `harvest-pages.py` | 批量 URL 抓取（图片 / 视频 / 滚动） | `playwright`、系统 Chrome |
| `video-download.py` | YouTube/Bilibili 下载 | `yt-dlp` |
| `mix-bgm.py` | 把 BGM 混入视频 | `ffmpeg` |

**系统依赖：** `ffmpeg`、`playwright`（`pip install playwright`，**不要**执行 `playwright install chromium`）、系统 Chrome（自动检测）、`yt-dlp`、带 venv 的 `python3`。

**Python 包（装到 venv 里）：** 各后端自己的参数与依赖（Python 包、环境变量、硬件要求）只写在 `scripts/voice-clone.py` 与 `scripts/transcribe.py` 的顶部说明里。此外是所有辅助脚本 import 的依赖。
