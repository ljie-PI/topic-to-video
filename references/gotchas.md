# Gotchas Catalog —— 上游 pipeline 踩坑清单

本文件聚焦 `topic-to-video` 的上游问题：调研、抓取、TTS、ASR、确定性资源以及 handoff contract。`SKILL.md` 只保留必须常驻上下文的核心护栏；这里记录具体症状、原因和恢复方式。HyperFrames composition、CSS、animation/effect skills、lint、inspect 与渲染实现的坑请去看 `hyperframes`、`hyperframes-cli` 以及对应 skill（如 `gsap`、`animejs`、`waapi`、`css-animations`、`lottie`、`three`、`typegpu`）。Tailwind 属于静态 layout / style utility，不负责 render-critical motion timing。

## 1. 中文场景下避免使用 Whisper / HyperFrames Transcribe

本工作流中，不要用 Whisper 或 `npx hyperframes transcribe` 处理中文解说。历史 run 多次遇到模型下载失败和 UTF-8 输出乱码。

修复：用 `scripts/transcribe-paraformer.py`，它调用 DashScope **非实时识别接口**（默认 `paraformer-v2`，HTTP REST 异步任务，自动识别 sample rate / format），返回干净的词级时间戳。可通过 `ASR_MODEL` 环境变量切到 `qwen3-asr-flash-filetrans` 等其他兼容模型。

如果 DashScope 不可用，问用户要一份外部 transcript，而不是悄悄切换到 HyperFrames 的 transcribe。

## 2. 不要编辑 CosyVoice 脚本源码

不要把 `voice-clone.py` 复制一份，再把解说粘进 Python 源码。这种做法让 resume 和 review 都变得脆弱。

修复：把解说放在 `narration.txt` 里，调用：

```bash
python3 scripts/voice-clone.py \
  --input-file {work_dir}/{topic_name}/narration.txt \
  --output-dir {work_dir}/{topic_name}/voice_clone \
  --speech-rate 1.4
```

通过 `--voice` 或 `COSYVOICE_VOICE_ID` 设置音色。

## 3. 全角中文冒号可能引入 TTS 停顿

当全角冒号 `：` 后紧跟一个长复合句时，CosyVoice 偶尔会在其后插入一段明显停顿。

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
- `dashscope` import 出错：在 venv 里安装 DashScope SDK
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
