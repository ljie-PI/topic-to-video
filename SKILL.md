---
name: topic-to-video
description: 当用户提供一个主题、文章 URL 或文本，并请求做一段有解说的视频（通常 3-10 分钟）时使用。本 skill 拥有上游 pipeline —— 主题调研、可选的视觉素材抓取、素材理解、解说撰写、用本地 Qwen3-TTS 做克隆音色 TTS（DashScope CosyVoice 作 fallback）、用本地 Qwen3-ASR + ForcedAligner 拿词级 ASR 时间戳（DashScope Paraformer 作 fallback）、确定性字体预置，以及一份精简的 HyperFrames composition handoff。HyperFrames composition、scene 设计、HTML/CSS、animation/effect skills、lint/inspect 与渲染都委派给 hyperframes 和 hyperframes-cli；Phase 9 sub-agent 必须通过 hyperframes-animation 的当前索引发现动画能力，按需加载 hyperframes-keyframes，并最后选择 gsap、animejs、waapi、css-animations、lottie、three、typegpu 等 runtime；tailwind 只用于静态布局 / 样式支持。
---

# Topic → Video（HyperFrames + Qwen3-TTS 工作流）

## 本 skill 产出什么

一段有解说的视频（3-10 分钟），使用：

- **Web 调研** 在写脚本之前获取准确的内容
- **HyperFrames** 用于下游 HTML composition + 渲染（delegated）
- **Qwen3-TTS**（本地 GPU，Apache-2.0）实现克隆音色 TTS —— 默认中文；DashScope CosyVoice 作云端 fallback
- **Qwen3-ASR + ForcedAligner**（本地 GPU）拿词级 ASR 时间戳；DashScope Paraformer 作云端 fallback
- 一份可配置的 style hint，交给下游 HyperFrames sub-agent

**输出：** `{work_dir}/{topic_name}/composition/renders/final.mp4`，可直接发布（由 Phase 9 coding sub-agent 产出）；Phase 10 混入 BGM 后得到 `final_with_bgm.mp4`。

## 工作流：一个循环

**禁止预读其他 phase 文档。** 每次只读 `pipeline-status` 指出的那一份 phase 文档；除此之外不要打开 `references/phases/` 下的任何其他文件。

1. 运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}`（工作区目录省略时默认为当前目录）。它输出一个 JSON：已完成的 phase、下一个 phase、要读的文档、缺失 / 损坏的产物。
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

2. **TTS = 本地 Qwen3-TTS 克隆音色（默认）。** 用参考 WAV + 其 transcript 克隆（`TTS_REF_WAV` 指定音色）。DashScope CosyVoice 作 fallback（`TTS_BACKEND=dashscope`）。**绝不**使用 `npx hyperframes tts`。
3. **ASR = 本地 Qwen3-ASR + ForcedAligner（默认）。** 返回词级（CJK 按字 / Latin 按词）时间戳，自动识别语言，无需 ffprobe 探测。默认开 ITN（中文数字→阿拉伯，如 `三点一→3.1`、`2026年6月`；`ASR_ITN=0` 关）。DashScope 非实时 `paraformer-v2` 作 fallback（`ASR_BACKEND=dashscope`）。
   ↳ DO NOT：用 Whisper / `npx hyperframes transcribe`；在 Turing GPU 上用 bf16 或装 flash-attn（用 fp16）。

### 字体与文本

4. **预先 stage 确定性的 WOFF2 字体。** 用 `scripts/fonts-download.sh` 下载，然后让 Phase 9 handoff 指向 `fonts/`。
   ↳ DO NOT：让主 agent 处理 composition 的字体 CSS。
5. **字体实现归 HyperFrames。** Phase 9 sub-agent 使用本地字体，并按 `hyperframes` skill 中的排版规则处理。

### 素材

6. **每个资源都能追溯到 `material-catalog.json`。** 没有 catalog 引用 → 屏幕上不出现该资源。**视频材料一律剥音轨**：catalog 阶段 `ffmpeg -an` 输出；Phase 9 HTML 嵌入时 `<video>` 标签必须带 `muted playsinline` 兜底。
   ↳ DO NOT：嵌入整段原视频；切片段时不带 `-an`；`<video>` 漏 `muted`。
7. **素材搜索是可选但推荐的。** `inputs.json` 里 `fetch_materials = false` 或用户自带全部视觉时跳过（Phase 4 / 5 一起跳过）。

### Composition

8. **Composition 委派给 HyperFrames sub-agent。** 主 agent 只写 `composition-handoff.md`，并把固定 rules（`references/composition-rules.md`）/ layout routing（`references/layout-routing.md`）/ animation routing（`references/animation-routing.md`）/ stage protocol（`references/composition-stage-protocol.md`）/ design references 物化到项目工作区的 `references/` 下。
   ↳ DO NOT：手写 `composition/index.html`、挑选低层 animation / effect skill，或在本 session 里修 HyperFrames lint；除非用户明确指定，否则由 Phase 9 sub-agent 选择。
9. **Scene 设计归 HyperFrames。** 切分、素材映射、布局、视觉层级、动画、lint/inspect 与渲染迭代都发生在 Phase 9。

### 环境与工具

10. **跑 Python 前一律 `source .venv/bin/activate`。** 用 `python3`。
11. **Chrome over CDP。** 共享 profile 位于 `{work_dir}/chrome_profile/`。
12. **视频下载顺序执行。** yt-dlp 并行时会被限速。

## 输出约定

所有脚本都把 JSON 输出到 stdout，人类可读 log 输出到 stderr，并使用以下退出码：`0`=成功，`1`=运行时错误，`2`=参数非法。`scripts/pipeline-status.py` 遵循同一约定，它的 JSON 额外携带 `completed_phases` / `next_phase` / `missing_products` / `corrupt_products` ——它是整个流程唯一的续跑入口，取代了过去的人工 checkpoint 表。

共享 Chrome profile：`{work_dir}/chrome_profile/` —— **不要**删除。

## 工具与依赖

| 脚本 | 用途 | 依赖 |
| --- | --- | --- |
| `pipeline-status.py` | 扫描工作区，输出已完成 / 下一个 phase、要读的文档、缺失或损坏的产物 | — |
| `fonts-download.sh` | 确定性 WOFF2 字体下载 + 本地 CSS | — |
| `voice-clone.py` | TTS（默认本地 Qwen3-TTS 克隆；`TTS_BACKEND=dashscope` 切 CosyVoice） | 本地：GPU + `TTS_REF_WAV`；fallback：`DASHSCOPE_API_KEY` |
| `transcribe.py` | ASR（默认本地 Qwen3-ASR + ForcedAligner，`ASR_BACKEND=dashscope` 切 `paraformer-v2`） | 本地：GPU；fallback：`DASHSCOPE_API_KEY` |
| `calibrate-transcript.py` | 基于 transcript timing 生成单行字幕单元，并用 narration 修正 Latin words | — |
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

**Python 包（装到 venv 里）：** 本地推理用 `torch`（CUDA 构建）、`qwen-tts`（Qwen3-TTS）、`qwen-asr`（Qwen3-ASR + ForcedAligner）、`wetext`（ASR 的 ITN 中文数字归一化）、`soundfile`；云端 fallback 用 `dashscope`（CosyVoice TTS + Paraformer ASR），以及所有辅助脚本 import 的依赖。本地模型默认从 HF id 自动下载，也可用 `QWEN3TTS_MODEL` / `QWEN3_ASR_MODEL` / `QWEN3_ALIGNER_MODEL` 指向本地目录。注意 `qwen-tts` 与 `qwen-asr` 对 `transformers` 的精确 pin 略有差异（4.57.3 vs 4.57.6），同装时 `pip check` 会告警，但实测两者在任一版本下都能正常运行，可忽略该告警。`wetext` 是独立包（`pip install wetext`）；缺失时 ASR 会自动跳过 ITN、保留逐字中文。

**GPU 注意（Turing，如 RTX 2080 Ti）：** 本地 TTS/ASR 用 fp16，**不要**装 flash-attn（Turing sm_75 不支持）。Qwen3-TTS 与 Qwen3-ASR 多 GB 模型分阶段顺序加载，单卡 11GB 可跑。
