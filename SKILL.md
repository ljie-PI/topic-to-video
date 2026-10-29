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

1. 运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}`（工作区目录必填）。它输出一个 JSON：已完成的 phase、下一个 phase（`next_phase.reason` 说明原因：缺失 / 损坏 / stale）、要读的文档、缺失 / 损坏的产物。
2. 只读它指出的那一份 phase 文档（`next_phase.doc`）。
3. 按该文档执行；文档头部的「输入 / 输出 / 完成判据 / 下一步」是自包含的，不需要查其他 phase 文档。
4. 回到第 1 步，直到脚本报告 `next_phase` 为 `null`（全部完成）。

`next_phase.reason == "awaiting_approval"` 时，按 `instruction` 找用户确认；除非用户已经明确确认，否则不要自己执行 `--approve`。

续跑、回退与重做都由状态脚本驱动。状态由三部分组成：`inputs.json`、各 phase 的产物，以及 `.pipeline/`（状态脚本记下的上游指纹，**只由状态脚本写，不要手改**）。

- 某个 phase 的产物被删掉或写坏时，脚本回退到那个 phase（`reason` 为 `missing` / `corrupt`）。
- 产物齐全，但它依赖的上游在它生成之后变过（比如改了 `script.txt`，或改了 `inputs.json` 的 layout），该 phase 判为 `stale`，`changed_upstream` 列出变化的上游，按它的 phase 文档重做。
- `next_phase` 之后的 phase 一律是 `pending`：不进 `completed_phases`，也不检查；轮到它们时再判断。
- 用户说 "redo phase N" 时，删掉对应产物或修改上游，再跑状态脚本。
- 某个 stale 的 phase 确认不用重新生成（比如确定性的重跑得到了字节完全相同的结果）时，运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name} --restamp <phase_id>`，让脚本按当前文件重写它的指纹；该 phase 的产物必须全部合格，否则退出码为 1。
- 输出里 `stamps_reset` 为 `true` 时，`.pipeline/stamps.json` 已损坏并被隔离为 `stamps.json.quarantined`：脚本不会把任何 phase 标为可信，也不会写回指纹。逐个确认 phase 的产物后，用 `--restamp <phase_id>` 重建对应指纹。

不要自己扫描工作区猜进度，也不要把 Scratchpad 当进度记录。

## 核心护栏

1. **写之前先调研。** Phase 3 是强制的。每个论断都通过 Gemini Deep Research + `web_search` 落地；用户给了论文，就必须先解析，不能用训练数据描述论文。
   ↳ DO NOT：调研之前写脚本；没有明确条件就跳过 Gemini；用户给了 PDF 还跳过 Phase 2；用训练数据描述一篇论文。
2. **进度只看 pipeline-status。** 续跑、回退与重做都由状态脚本驱动。
   ↳ DO NOT：自己扫描工作区猜进度；把 Scratchpad 当进度记录；手改 `.pipeline/`。
3. **委派步骤（Phase 5 / 6 / 8）的内容由 sub-agent 产出。** 主 agent 只准备 handoff、派发并验收。唯一例外：Phase 5 当前环境没有 sub-agent 工具时，主 agent 按 `references/phases/05-material-catalog.md` 的兜底流程生成 catalog。
   ↳ DO NOT：主 agent 手写旁白或 composition HTML；有 sub-agent 工具时主 agent 手写 catalog。
4. **屏幕上的每个素材都能追溯到 `material-catalog.json`。** 没有 catalog 引用 → 屏幕上不出现该资源。
   ↳ DO NOT：让没有 catalog 引用的素材出现在屏幕上。
5. **跑 Python 前一律 `source .venv/bin/activate`。** 用 `python3`。
   ↳ DO NOT：在未激活项目 venv 的 shell 里运行 Python，或改用 `python`。

## 输出约定

所有脚本都把 JSON 输出到 stdout，人类可读 log 输出到 stderr，并使用以下退出码：`0`=成功，`1`=运行时错误，`2`=参数非法。`scripts/pipeline-status.py` 遵循同一约定，它的 JSON 额外携带 `phases` / `completed_phases` / `stale_phases` / `pending_phases` / `next_phase` / `missing_products` / `corrupt_products` ——它是整个流程唯一的续跑入口，取代了过去的人工 checkpoint 表。

共享 Chrome profile：`{work_dir}/chrome_profile/` —— **不要**删除。

## 工具与依赖

| 脚本 | 用途 | 依赖 |
| --- | --- | --- |
| `pipeline-status.py` | 扫描工作区，输出已完成 / 下一个 phase、要读的文档、缺失 / 损坏 / stale 的产物；`--restamp <phase_id>` 接受某个 stale phase 的现有产物；`--approve <gate>` 在用户明确确认后记录 gate 及产物指纹 | — |
| `prepare-handoff.py` | 委派步骤（catalog / script / composition）的准备：物化委派包（composition 另含 modules 与预置字体）、生成 handoff，输出可原样派发的 `dispatch_prompt` | — |
| `fonts-download.sh` | 按 `<design>.json` 的 `fonts` 清单把仓库里预置的 WOFF2 字体（CSS 在 `resources/fonts/<design>/`，WOFF2 在共用池 `resources/fonts/files/`）装进工程，不联网；`--refresh` 才从 Google Fonts 重新下载（维护用） | — |
| `voice-subtitles.py` | Phase 7 一条命令：配音、fresh transcript、字幕单元与时间轴；`--align-only` 只重跑对齐 | 见 voice-clone.py / transcribe.py 顶部说明 |
| `voice-clone.py` | TTS：把 `narration.txt` 合成 `voice_clone/narration.mp3`；后端由环境变量选择 | 见脚本顶部说明 |
| `transcribe.py` | ASR：输出带词级时间戳的 transcript；后端由环境变量选择 | 见脚本顶部说明 |
| `align-narration.py` | 把 ASR 时间对齐回显示稿，生成字幕单元（subtitle-units.json）与段落 / cue / beat 时间轴（timeline.json） | — |
| `make-narration.py` | 按显示稿与 TTS 词表确定性生成 `narration.txt` 和 `narration-offsets.json` | — |
| `check-composition.py` | composition 渲染前检查：越界 / reserved 区域侵入 / 文字溢出 / 资源与字体加载 / 字号下限（`--design <design>.json`）/ 字幕一致性 | `playwright`、系统 Chrome |
| `check-render.py` | 渲染后确定性检查：音轨与时长偏差 / 朝向分辨率 / 黑屏与黑尾 / 冻结（发现映射回 scene_id） | `ffmpeg` |
| `make-contact-sheet.py` | 每 scene 中点帧拼 2×2 contact sheet（strict 加入场帧与切点帧），标注 scene_id 与时间戳 | `ffmpeg`、`Pillow` |
| `extract-frames.py` | ffmpeg 抽帧 | `ffmpeg` |
| `cut-clips.py` | 把 catalog 的 `selected_clips` 切成无音轨片段文件（`clips/`），并写回 `clip_path` | `ffmpeg` |
| `subtitle-parse.py` | SRT/VTT 解析 + 关键词过滤 | — |
| `vision-analyze.py` | VLM 分析（或委派回 agent 的 `view`） | `VLM_*`（可选） |
| `gemini-deep-research.py` | Gemini Deep Research 自动化 | `playwright`、已登录的 Chrome |
| `parse-pdf.py` | 通过 MinerU 云端 / 本地解析 PDF | `MINERU_API_TOKEN` 或 `mineru[pipeline]` |
| `harvest-pages.py` | 批量 URL 抓取（图片 / 视频 / 滚动） | `playwright`、系统 Chrome |
| `video-download.py` | YouTube/Bilibili 下载 | `yt-dlp` |
| `mix-bgm.py` | 把 BGM 混入视频 | `ffmpeg` |

**系统依赖：** `ffmpeg`、`playwright`（`pip install playwright`，**不要**执行 `playwright install chromium`）、系统 Chrome（自动检测）、`yt-dlp`、带 venv 的 `python3`。

**Python 包（装到 venv 里）：** 各后端自己的参数与依赖（Python 包、环境变量、硬件要求）只写在 `scripts/voice-clone.py` 与 `scripts/transcribe.py` 的顶部说明里。此外是所有辅助脚本 import 的依赖。
