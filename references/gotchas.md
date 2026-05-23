# Gotchas Catalog —— 上游 pipeline 踩坑清单

本文件聚焦 `topic-to-video` 的上游问题：调研、抓取、TTS、ASR、确定性资源以及 handoff contract。HyperFrames composition、CSS、GSAP、lint、inspect 与渲染实现的坑请去看 `hyperframes`、`hyperframes-cli` 和 `gsap` 这三个 skill。

## 1. 中文场景下避免使用 Whisper / HyperFrames Transcribe

本工作流中，不要用 Whisper 或 `npx hyperframes transcribe` 处理中文解说。历史 run 多次遇到模型下载失败和 UTF-8 输出乱码。

修复：用 `scripts/transcribe-paraformer.py`，它调用 DashScope Paraformer-realtime-v2 并返回干净的词级时间。

如果 Paraformer 不可用，问用户要一份外部 transcript，而不是悄悄切换到 HyperFrames 的 transcribe。

## 2. Paraformer Sample Rate 不匹配

症状：

```text
status_code: 44
error: Failed to decode audio: sample rate 16000 not equals with real 22050
```

根因：Paraformer 会拒绝声明的 sample rate 与实际文件 sample rate 不一致的音频。

修复：调用 `Recognition()` 之前一律用 ffprobe 探测真实 sample rate。随包的 `scripts/transcribe-paraformer.py` 已经这么做了。

## 3. 不要编辑 CosyVoice 脚本源码

不要把 `voice-clone.py` 复制一份，再把解说粘进 Python 源码。这种做法让 resume 和 review 都变得脆弱。

修复：把解说放在 `narration.txt` 里，调用：

```bash
python3 scripts/voice-clone.py \
  --input-file {work_dir}/{topic_name}/narration.txt \
  --output-dir {work_dir}/{topic_name}/voice_clone \
  --speech-rate 1.2
```

通过 `--voice` 或 `COSYVOICE_VOICE_ID` 设置音色。

## 4. 全角中文冒号可能引入 TTS 停顿

当全角冒号 `：` 后紧跟一个长复合句时，CosyVoice 偶尔会在其后插入一段明显停顿。

修复：改用 `——`、逗号，或在生成 TTS 之前断句。

## 5. Gemini Deep Research 的 UI 自动化很脆

`scripts/gemini-deep-research.py` 自动化的是一个消费级 web UI，selector 或流程变更都会让它崩。

修复：如果脚本因 selector timeout、failed step 或运行时错误失败，回退到有针对性的 `web_search` 调研。不要让项目卡在 Gemini UI 自动化上。

## 6. MinerU 云端失败

MinerU 云端可能因为 token、超时或 URL 抓取等原因失败。

修复：
- token 缺失或失效：允许 `parse-pdf.py` 在本地有 `mineru` 时回退到本地。
- URL 模式云端超时：把 PDF 下下来，用 `--pdf` 重试。
- 云端错误 `-60007`：本地重试。

## 7. Chrome CDP 的 profile 锁

Chrome 启动时会复用位于 `{work_dir}/chrome_profile/` 的共享 profile。如果 Chrome 立刻退出，可能是另一个 Chrome 进程正占用该 profile。

修复：关掉冲突的 Chrome 进程，或传一个不同的 `--profile-dir`。如果 CDP 端口 9222 被占用，传另一个 `--cdp-url`，比如 `http://localhost:9223`。

## 8. 视频下载必须顺序执行

YouTube/Bilibili 经 yt-dlp 并行下载时容易被限速。

修复：顺序遍历 `manifest.pending_downloads[]`。如果下载因地区封锁、年龄门、410 或限速失败，保留 `download_required: true`；Phase 4 会忽略尚未解决的 clip。

## 9. 将视频下载结果应用到 manifest

下载视频本身还不够。Phase 4 会读 `manifest.json` 和每个 slug 的 `metadata.json`。

修复：每次 `video-download.py` 成功后，应用结果：

```bash
scripts/apply-video-download-result.py \
  --harvest-dir {work_dir}/{topic_name}/harvest_page/ \
  --source-slug "<item.source_slug>" \
  --url "<item.url>" \
  --result-json /path/to/video-download-result.json
```

## 10. 将解析出的论文并入 harvest manifest

`parse-pdf.py` 写入的是 `manifest_papers.json`，不是统一的 `manifest.json`。

修复：论文解析和 web 抓取都完成后，运行：

```bash
scripts/merge-paper-manifest.py \
  --harvest-dir {work_dir}/{topic_name}/harvest_page/
```

## 11. 剥掉视频片段的原始音轨

素材视频本身可能包含解说、音乐或 UI 音效。最终视频里，唯一的解说人声只能是 `voice_clone/narration.mp3`。

修复：切 catalog 视频片段时，用 `-an` 去掉原始音频。这是传递给 HyperFrames 子 agent 的一项上游素材契约。

## 12. 在项目环境里使用 Python 3

激活项目 venv 后用 `python3`。不要假设所有机器上的 `python` 都指向 Python 3。

常见修复：
- `playwright` import 出错：`pip install playwright`
- `dashscope` import 出错：在 venv 里安装 DashScope SDK
- `mineru` 缺失：`pip install "mineru[pipeline]"`
