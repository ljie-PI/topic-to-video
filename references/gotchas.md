# 维护者笔记：历史症状 → 原因 → 修复

本文件只记录未被 phase 护栏完全覆盖的历史症状、原因与恢复方式，供维护者 review；执行流程仍只读 `pipeline-status` 当前指出的 phase 文档。修改护栏前，从该 phase 的「护栏」小节核对对应历史坑，避免重开旧问题。HyperFrames composition、CSS、animation/effect skills、lint、inspect 与渲染实现的坑请去看 `hyperframes`、`hyperframes-cli` 以及对应 skill。

## 1. HyperFrames Transcribe 的中文下载与 UTF-8 故障

**历史症状：** 历史 run 多次遇到模型下载失败和 UTF-8 输出乱码；所有已配置的 ASR 后端也可能同时不可用。

**原因：** HyperFrames Transcribe 的中文模型下载与输出编码不稳定；外部 ASR 服务或本地后端也可能暂时不可用。

**修复：** 用 `scripts/transcribe.py`，后端、参数和依赖见其顶部说明。如果所有已配置的后端都不可用，问用户要一份外部 transcript，不要悄悄切换到 HyperFrames 的 transcribe。

## 2. ASR 的数字归一化影响文本对比 / CER

**历史症状：** 做文本对比 / CER 评测时，数字格式差异会让分数虚高。

**原因：** transcript 里的数字可能是中文或阿拉伯写法，取决于后端与开关；下游对齐会把两者视为等价，不做假设。

**修复：** 对两侧都做同样归一化。数字归一化的行为、依赖与开关见 `scripts/transcribe.py` 的顶部说明。

## 3. 参考音频需要 transcript；长 narration 可能 OOM

**历史症状：** 声音克隆的参考 WAV 缺少对应逐字稿；合成较长 narration 时可能在高负载机器上 OOM。

**原因：** 声音克隆除了参考 WAV 还需要它对应的逐字稿；长文本合成有额外的内存压力。

**修复：** 参考音频逐字稿的解析顺序、缓存位置与自动转写行为见 `scripts/voice-clone.py` 的顶部说明。`voice-clone.py` 已缓解长 narration 的内存压力；仍失败时可把 narration 分段合成再用 ffmpeg 拼接，或切到其他后端。

## 4. Gemini Deep Research 的 UI 自动化很脆

**历史症状：** 脚本出现 selector timeout、failed step 或运行时错误。

**原因：** `scripts/gemini-deep-research.py` 自动化的是一个消费级 web UI，selector 或流程变更都会让它崩。

**修复：** 回退到有针对性的 `web_search` 调研，不要让项目卡在 Gemini UI 自动化上。

## 5. MinerU 云端失败

**历史症状：** MinerU 云端因为 token、超时或 URL 抓取等原因失败，包括云端错误 `-60007`。

**原因：** 云端 token 缺失或失效、URL 模式超时、云端服务错误。

**修复：**
- token 缺失或失效：允许 `parse-pdf.py` 在本地有 `mineru` 时回退到本地。
- URL 模式云端超时：把 PDF 下下来，用 `--pdf` 重试。
- 云端错误 `-60007`：本地重试。

## 6. Chrome CDP 的 profile 锁

**历史症状：** Chrome 立刻退出，或复用 CDP 后新的启动配置没有生效。

**原因：** 另一个 Chrome 进程可能正占用共享 profile。CDP 已就绪时脚本会直接 attach；此次传入的 `--profile-dir` / `--headless` / `--chrome-path` / `--no-sandbox` 不会改变正在运行的 Chrome。stderr 会记录 warning，输出 JSON 的 `chrome.ignored_flags` 会列出这些被忽略的参数，`chrome.reused` 为 `true`。

**修复：** 需要应用不同启动配置时，先关闭复用的 Chrome 再运行；profile 锁冲突时关闭冲突进程或换 `--profile-dir`。如果 CDP 端口 9222 被占用，传另一个 `--cdp-url`，比如 `http://localhost:9223`。

## 7. `harvest-pages.py` 返回 0 张图

**历史症状：** 页面抓取结果为空。

**原因：** 页面加载慢、cookie banner 或懒加载。

**修复：** 调大 `--page-load-timeout`，必要时用共享 Chrome profile 先处理 cookie banner，再重跑抓取。

## 8. `vision-analyze.py` 返回 `delegate_to_agent`

**历史症状：** `vision-analyze.py` 返回 `delegate_to_agent`，无法自动完成视觉分析。

**原因：** 当前环境缺少可用 VLM 配置。

**修复：** 设置 `VLM_API_KEY` / `VLM_BASE_URL` / `VLM_MODEL` 后重跑；如果没有 VLM，用 `view` 工具检查图片并手写分析结果。

## 9. `warning: cue not found for scene ...`

**历史症状：** 场景规划的 cue 锚点在对齐后的文本里找不到，`scripts/align-narration.py` 的 stderr 记录 warning；找不到的 cue 会被跳过，不阻塞流程。

**原因：** 通常是大小写、标点、TTS 文本与 transcript 不一致。

**修复：** 从实际 `transcribe/transcript.json` / 显示稿文本中挑 cue，避免凭 `narration.txt` 原文硬配。

## 10. 未校准 ASR 会造成字幕文本错误

**历史症状：** ASR 可能把 Latin words、产品名或模型名识别错，也可能把词粘在一起或在词中间断句。

**原因：** ASR 的时间戳最接近音频，但文本不一定与显示稿一致。

**修复：** 最终字幕使用 `transcribe/subtitle-units.json`，以显示稿为文本来源，ASR 只提供时间；低置信区段保留 ASR 文本并标记 `fallback`。重跑 `scripts/align-narration.py`；如果 `narration.txt` 在 TTS 后改过，先重新生成 TTS 和 ASR。TTS 漏读的内容没有音频可依，会被丢弃并在 summary 里警告。
