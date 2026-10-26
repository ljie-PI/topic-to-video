# Gotchas Catalog —— 上游 pipeline 踩坑清单

本文件聚焦 `topic-to-video` 的上游问题：调研、抓取、TTS、ASR、确定性资源以及 handoff contract。`SKILL.md` 只保留必须常驻上下文的核心护栏；这里记录具体症状、原因和恢复方式。HyperFrames composition、CSS、animation/effect skills、lint、inspect 与渲染实现的坑请去看 `hyperframes`、`hyperframes-cli` 以及对应 skill（如 `gsap`、`animejs`、`waapi`、`css-animations`、`lottie`、`three`、`typegpu`）。Tailwind 属于静态 layout / style utility，不负责 render-critical motion timing。

## 1. 中文场景下避免使用 HyperFrames Transcribe

本工作流中，不要用 `npx hyperframes transcribe` 处理中文解说。历史 run 多次遇到模型下载失败和 UTF-8 输出乱码。

修复：用 `scripts/transcribe.py`。后端由环境变量选择，参数和依赖见 `scripts/transcribe.py` 的顶部说明。脚本输出带词级时间戳的句子列表（transcript schema 见 Phase 7 的接口契约）。

如果所有已配置的后端都不可用，问用户要一份外部 transcript，而不是悄悄切换到 HyperFrames 的 transcribe。

## 1b. ASR 的数字归一化（ITN）

transcript 里的数字可能是中文或阿拉伯写法（取决于后端与开关），下游对齐会把两者视为等价，不做假设。数字归一化的行为、依赖与开关见 `scripts/transcribe.py` 的顶部说明。

做文本对比 / CER 评测时应对两侧都做同样归一化，否则数字格式差异会让分数虚高。

## 2. 不要编辑 TTS 脚本源码

不要把 `voice-clone.py` 复制一份，再把解说粘进 Python 源码。这种做法让 resume 和 review 都变得脆弱。

修复：把解说放在 `narration.txt` 里，调用：

```bash
python3 scripts/voice-clone.py \
  --input-file {work_dir}/{topic_name}/narration.txt \
  --output-dir {work_dir}/{topic_name}/voice_clone
```

后端由环境变量选择，参考音色、参数和依赖见 `scripts/voice-clone.py` 的顶部说明。

## 2b. 参考音频需要 transcript

声音克隆除了参考 WAV 还需要它对应的逐字稿。解析顺序、缓存位置与自动转写行为见 `scripts/voice-clone.py` 的顶部说明。

坑（长 narration 内存不足）：合成较长 narration 时可能在高负载机器上 OOM。`voice-clone.py` 已做缓解；仍失败时可把 narration 分段合成再用 ffmpeg 拼接，或切到其他后端。

## 2c. 硬件精度注意事项

后端特定的硬件精度选择（如低精度推理、避免不支持的 kernel）见 `scripts/voice-clone.py` 与 `scripts/transcribe.py` 的顶部说明。

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

Chrome 启动时使用显式 `--profile-dir {work_dir}/chrome_profile` 指定的共享 profile。如果 Chrome 立刻退出，可能是另一个 Chrome 进程正占用该 profile。

如果 CDP 已就绪，脚本会直接 attach；此次传入的 `--profile-dir` / `--headless` / `--chrome-path` / `--no-sandbox` 不会改变正在运行的 Chrome。stderr 会记录 warning，输出 JSON 的 `chrome.ignored_flags` 会列出这些被忽略的参数，`chrome.reused` 为 `true`。

修复：需要应用不同启动配置时，先关闭复用的 Chrome 再运行；profile 锁冲突时关闭冲突进程或换 `--profile-dir`。如果 CDP 端口 9222 被占用，传另一个 `--cdp-url`，比如 `http://localhost:9223`。

## 7. 视频下载必须顺序执行

YouTube/Bilibili 经 yt-dlp 并行下载时容易被限速。

修复：顺序遍历 `manifest.pending_downloads[]`（Phase 4.b 的步骤）。如果下载因地区封锁、年龄限制、410 或限速失败，保留 `download_required: true`；Phase 5（素材 catalog）会忽略尚未解决的 clip。

## 10. 剥掉视频片段的原始音轨

素材视频本身可能包含解说、音乐或 UI 音效。最终视频里，唯一的解说人声只能是 `voice_clone/narration.mp3`。

修复：Phase 5 用 `scripts/cut-clips.py` 把 catalog 的 `selected_clips` 切成 `-an` 的无音轨文件（`clip_path`）。这是传递给 HyperFrames sub-agent 的一项上游素材契约：composition 只用 `clip_path`，不用视频的 `local_path`。

## 11. 在项目环境里使用 Python 3

激活项目 venv 后用 `python3`。不要假设所有机器上的 `python` 都指向 Python 3。

常见修复：
- `playwright` import 出错：`pip install playwright`
- TTS / ASR 后端依赖 import 出错：按 `scripts/voice-clone.py` / `scripts/transcribe.py` 的顶部说明安装对应后端的包
- `mineru` 缺失：`pip install "mineru[pipeline]"`

## 12. Paper mode 不要跳过主论文解析

用户给了 PDF 或论文 URL 时，不能只靠模型训练数据概括论文。先解析主论文，产出 `harvest_page/main-paper/metadata.json`，再把论文 figure / table 并入统一素材流。

修复：用 `scripts/parse-pdf.py` 解析本地 PDF 或 URL；云端失败时按 MinerU 条目回退到本地或本地文件模式。

## 13. catalog 未建立前不要写脚本或匹配素材

Phase 6 只能引用 Phase 5 产出的 `material-catalog.json`。如果 catalog 还没建，脚本会凭空安排素材，后续 handoff 也无法追溯资源来源。

修复：先完成 vision analyze 和 catalog 生成。用户明确跳过素材时，仍要在 Phase 6/9 中按“无素材”路径处理，不要伪造 `material_ref`。

## 14. `harvest-pages.py` 返回 0 张图

页面加载慢、cookie banner 或懒加载可能导致抓取结果为空。

修复：调大 `--page-load-timeout`，必要时用共享 Chrome profile 先处理 cookie banner，再重跑抓取。

## 15. `vision-analyze.py` 返回 `delegate_to_agent`

这表示当前环境缺少可用 VLM 配置，脚本无法自动完成视觉分析。

修复：设置 `VLM_API_KEY` / `VLM_BASE_URL` / `VLM_MODEL` 后重跑；如果没有 VLM，用 `view` 工具检查图片并手写分析结果。

## 16. `warning: cue not found for scene ...`

场景规划的 cue 锚点在对齐后的文本里找不到（`scripts/align-narration.py` 的 stderr 日志），通常是大小写、标点、TTS 文本与 transcript 不一致。找不到的 cue 会被跳过并记 warning，不阻塞流程。

修复：从实际 `transcribe/transcript.json` / 显示稿文本中挑 cue，避免凭 `narration.txt` 原文硬配。

## 17. 主 agent 不手写 composition HTML

主 agent 只负责生成 `composition-handoff.md`，并把 composition 委派包（`references/delegation/composition/`）与 modules（不含 `examples/`）物化到工作区、按所选 design 预置字体。`composition/index.html`、storyboard、场景布局、动画、渲染前自查和渲染迭代都属于 Phase 8 coding sub-agent。

修复：如果发现主 agent 已开始手写 HTML，停下并改为补全 handoff、物化委派包与 modules 副本、核对素材引用；让 composition sub-agent 接管 composition。

## 18. 字幕文本不要直接照搬未校准 ASR

ASR 的时间戳最接近音频，但文本可能把 Latin words、产品名或模型名识别错，也可能把词粘在一起或在词中间断句。最终字幕应来自 `transcribe/subtitle-units.json`：以显示稿为文本来源，ASR 只提供时间；低置信区段保留 ASR 文本并标记 `fallback`。

修复：重跑 `scripts/align-narration.py`。如果 `narration.txt` 在 TTS 后改过，先重新生成 TTS 和 ASR；TTS 漏读的内容没有音频可依，会被丢弃并在 summary 里警告。
