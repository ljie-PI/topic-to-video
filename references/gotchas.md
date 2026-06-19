# Gotchas Catalog —— 上游 pipeline 踩坑清单

本文件聚焦 `topic-to-video` 的上游问题：调研、抓取、TTS、ASR、确定性资源以及 handoff contract。`SKILL.md` 只保留必须常驻上下文的核心护栏；这里记录具体症状、原因和恢复方式。HyperFrames composition、CSS、animation/effect skills、lint、inspect 与渲染实现的坑请去看 `hyperframes`、`hyperframes-cli` 以及对应 skill（如 `gsap`、`animejs`、`waapi`、`css-animations`、`lottie`、`three`、`typegpu`）。Tailwind 属于静态 layout / style utility，不负责 render-critical motion timing。

## 1. 中文场景下避免使用 Whisper / HyperFrames Transcribe

本工作流中，不要用 Whisper 或 `npx hyperframes transcribe` 处理中文解说。历史 run 多次遇到模型下载失败和 UTF-8 输出乱码。

修复：用 `scripts/transcribe-paraformer.py`。默认走**本地 Qwen3-ASR + Qwen3-ForcedAligner**（`ASR_BACKEND=qwen3`），返回干净的词级时间戳（CJK 按字、Latin 按词），自动识别语言，无需 ffprobe 探测 sample rate / format。云端 fallback 用 `ASR_BACKEND=dashscope`，走 DashScope 非实时 `paraformer-v2`（HTTP REST 异步任务）。

模型路径可用 `QWEN3_ASR_MODEL` / `QWEN3_ALIGNER_MODEL` 指向本地目录（缺省自动从 HF 下载）。注意输出是**扁平 token 流**，脚本按句末标点（`。！？!?…`）重新切句，再以"保留字符"匹配把 token 归入各句，因此 transcript 文本里的标点来自句子级文本、word 级 token 不含标点。

如果本地 GPU 和 DashScope 都不可用，问用户要一份外部 transcript，而不是悄悄切换到 HyperFrames 的 transcribe。

## 2. 不要编辑 TTS 脚本源码

不要把 `voice-clone.py` 复制一份，再把解说粘进 Python 源码。这种做法让 resume 和 review 都变得脆弱。

修复：把解说放在 `narration.txt` 里，调用：

```bash
python3 scripts/voice-clone.py \
  --input-file {work_dir}/{topic_name}/narration.txt \
  --output-dir {work_dir}/{topic_name}/voice_clone
```

默认走**本地 VoxCPM2 克隆**（`TTS_BACKEND=voxcpm`），用 `--reference-wav` / `VOXCPM_REF_WAV` 指定要克隆的音色。云端 fallback 用 `TTS_BACKEND=dashscope`，通过 `--voice` 或 `COSYVOICE_VOICE_ID` 设置 CosyVoice 音色。

## 2b. VoxCPM2 ultimate cloning 需要参考音频的 transcript

VoxCPM2 的最高保真克隆是"音频续写"模式，除了参考 WAV 还需要它对应的逐字稿（`prompt_text`）。`voice-clone.py` 的解析顺序：`--reference-text` / `VOXCPM_REF_TEXT`（内联字符串或 `.txt` 路径）→ 参考 WAV 同名 `<ref>.txt` 缓存 → 首次用 Qwen3-ASR 自动转写并写回 `<ref>.txt`。

坑：自动转写会先加载 Qwen3-ASR（多 GB），脚本在转写完成后显式 `del model + torch.cuda.empty_cache()` 再加载 VoxCPM2，避免单卡（如 11GB）同时驻留两个模型导致 OOM。第一次跑某个参考音频会慢一点（多一次 ASR 加载），之后命中 `<ref>.txt` 缓存。

坑（长 narration OOM）：在 11GB 卡上合成约 2 分钟以上的长 narration 时，VoxCPM2 的 KV cache 可能在末尾 OOM（`CUDA out of memory ... try expandable_segments`）。`voice-clone.py` 已用 `os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')` 缓解碎片化；实测一段 ~146s 的中文 narration 用此设置可正常合成。仍 OOM 时可把 narration 分段合成再用 ffmpeg 拼接，或切到云端 fallback。

## 2c. Turing GPU（如 RTX 2080 Ti）：用 fp16，不要装 flash-attn

本地 VoxCPM2 / Qwen3-ASR 在 Turing（sm_75）上：脚本统一用 `torch.float16`（**不要** bf16——Turing 无原生 bf16，会很慢），并且**不要**装 flash-attn（Turing 不支持，库不带它也能跑）。VoxCPM2 与 Qwen3-ASR 是分阶段顺序加载的，单卡 11GB 足够。VoxCPM2 加载时 config 标的是 bfloat16，实测在 2080 Ti 上仍能正常合成（~3 it/s）；如遇异常或过慢，可考虑改用更小模型或云端 fallback。

## 3. 全角中文冒号可能引入 TTS 停顿

当全角冒号 `：` 后紧跟一个长复合句时，TTS 偶尔会在其后插入一段明显停顿。

修复：改用 `——`、逗号，或在生成 TTS 之前断句。

## 4. Gemini Deep Research 的 UI 自动化很脆

`scripts/gemini-deep-research.py` 自动化的是一个消费级 web UI，selector 或流程变更都会让它崩。

修复：如果脚本因 selector timeout、failed step 或运行时错误失败，回退到有针对性的 `web_search` 调研。不要让项目卡在 Gemini UI 自动化上。

## 5. MinerU 云端失败

MinerU 云端可能因为 token、超时或 URL 抓取等原因失败。

修复：
- token 缺失或失效：允许 `parse-pdf.py` 在本地有 `mineru` 时回退到本地。
- URL 模式云端超时：把 PDF 下下来，用 `--pdf` 重试。
- 云端错误 `-60007`：本地重试。

## 6. Chrome CDP 的 profile 锁

Chrome 启动时会复用位于 `{work_dir}/chrome_profile/` 的共享 profile。如果 Chrome 立刻退出，可能是另一个 Chrome 进程正占用该 profile。

修复：关掉冲突的 Chrome 进程，或传一个不同的 `--profile-dir`。如果 CDP 端口 9222 被占用，传另一个 `--cdp-url`，比如 `http://localhost:9223`。

## 7. 视频下载必须顺序执行

YouTube/Bilibili 经 yt-dlp 并行下载时容易被限速。

修复：顺序遍历 `manifest.pending_downloads[]`。如果下载因地区封锁、年龄限制、410 或限速失败，保留 `download_required: true`；Phase 4 会忽略尚未解决的 clip。

## 8. 将视频下载结果应用到 manifest

下载视频本身还不够。Phase 4 会读 `manifest.json` 和每个 slug 的 `metadata.json`。

修复：每次 `video-download.py` 成功后，应用结果：

```bash
scripts/apply-video-download-result.py \
  --harvest-dir {work_dir}/{topic_name}/harvest_page/ \
  --source-slug "<item.source_slug>" \
  --url "<item.url>" \
  --result-json /path/to/video-download-result.json
```

## 9. 将解析出的论文并入 harvest manifest

`parse-pdf.py` 写入的是 `manifest_papers.json`，不是统一的 `manifest.json`。

修复：论文解析和 web 抓取都完成后，运行：

```bash
scripts/merge-paper-manifest.py \
  --harvest-dir {work_dir}/{topic_name}/harvest_page/
```

## 10. 剥掉视频片段的原始音轨

素材视频本身可能包含解说、音乐或 UI 音效。最终视频里，唯一的解说人声只能是 `voice_clone/narration.mp3`。

修复：切 catalog 视频片段时，用 `-an` 去掉原始音频。这是传递给 HyperFrames sub-agent 的一项上游素材契约。

## 11. 在项目环境里使用 Python 3

激活项目 venv 后用 `python3`。不要假设所有机器上的 `python` 都指向 Python 3。

常见修复：
- `playwright` import 出错：`pip install playwright`
- 本地 TTS/ASR import 出错（`voxcpm` / `qwen_asr` / `torch`）：在 venv 里 `pip install voxcpm qwen-asr` 并安装匹配 CUDA 的 `torch`
- `dashscope` import 出错（仅云端 fallback 需要）：在 venv 里安装 DashScope SDK
- `mineru` 缺失：`pip install "mineru[pipeline]"`

## 12. Paper mode 不要跳过主论文解析

用户给了 PDF 或论文 URL 时，不能只靠模型训练数据概括论文。先解析主论文，产出 `harvest_page/main-paper/metadata.json`，再把论文 figure / table 并入统一素材流。

修复：用 `scripts/parse-pdf.py` 解析本地 PDF 或 URL；云端失败时按 MinerU 条目回退到本地或本地文件模式。

## 13. catalog 未建立前不要写脚本或匹配素材

Phase 5 只能引用 Phase 4 产出的 `material-catalog.json`。如果 catalog 还没建，脚本会凭空安排素材，后续 handoff 也无法追溯资源来源。

修复：先完成 vision analyze 和 catalog 生成。用户明确跳过素材时，仍要在 Phase 5/8 中按“无素材”路径处理，不要伪造 `material_ref`。

## 14. `harvest-pages.py` 返回 0 张图

页面加载慢、cookie banner 或懒加载可能导致抓取结果为空。

修复：调大 `--page-load-timeout`，必要时用共享 Chrome profile 先处理 cookie banner，再重跑抓取。

## 15. `vision-analyze.py` 返回 `delegate_to_agent`

这表示当前环境缺少可用 VLM 配置，脚本无法自动完成视觉分析。

修复：设置 `VLM_API_KEY` / `VLM_BASE_URL` / `VLM_MODEL` 后重跑；如果没有 VLM，用 `view` 工具检查图片并手写分析结果。

## 16. `WARN: anchor not found for X`

字幕或 scene timing 锚点找不到，通常是大小写、标点、ASR 断句或 TTS 文本与 transcript 不一致。

修复：从实际 `transcribe/transcript.json` 文本中挑 anchor，避免凭 `narration.txt` 原文硬配。

## 17. 主 agent 不手写 composition HTML

主 agent 只负责生成 `composition-handoff.md` 并物化固定 references。`composition/index.html`、场景布局、动画、lint/inspect 修复和渲染迭代都属于 Phase 8 HyperFrames coding sub-agent。

修复：如果发现主 agent 已开始手写 HTML，停下并改为补全 handoff、rules 和素材引用；让 HyperFrames sub-agent 接管 composition。

## 18. 字幕文本不要直接照搬未校准 ASR

ASR 的时间戳最接近音频，但文本可能把 Latin words、产品名或模型名识别错。最终字幕应来自 `transcribe/subtitle-units.json`：以 `transcribe/transcript.json` 的句子 / 词时间为底，用 `narration.txt` 中匹配到的原句修正 Latin 拼写。匹配时中文内容权重更高，并把中文数字和阿拉伯数字归一化后比较，避免 `13432` 和 `一万三千四百三十二` 这类表达匹配失败。

修复：重跑 `scripts/calibrate-transcript.py`。如果 `narration.txt` 在 TTS 后改过，先重新生成 TTS 和 ASR；如果找不到对应 narration 句子，保留 transcript 文本并在 subtitle units 里标记 `transcript_fallback`。
