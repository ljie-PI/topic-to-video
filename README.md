# Topic → Video

一个 **agent skill**：把主题、文章 URL、论文 PDF 或一段文本，做成带解说的视频。

## 怎么运行

1. 把本目录注册为宿主的 skill（入口 `SKILL.md`；不同 agent 的 skill 目录不同，按宿主文档放置）。
2. 在对话里把需求交给 agent，例如：

   > 用这个主题做一个 3 分钟的视频：https://example.com/article

3. agent 先检查环境，再按 `SKILL.md` 的循环执行：
   - 运行 `python3 scripts/pipeline-status.py <work_dir>/<topic_name>`，读取 `next_phase`；
   - 打开 `next_phase.doc` 指向的阶段文档并执行（调研、写稿、配音、委派 composition 等）；
   - 回到上一步，直到 `next_phase` 为 `null`。

工作区由 agent 创建：`<work_dir>/<topic_name>/`，其中 `inputs.json` 在 Phase 1 生成，不需要用户手工准备。

最终产物：`<work_dir>/<topic_name>/composition/renders/final.mp4`（混入 BGM 后为 `final_with_bgm.mp4`）。

## 状态脚本不是启动器

```bash
python3 scripts/pipeline-status.py <work_dir>/<topic_name>
```

它扫描工作区里各阶段的产物，向 stdout 输出一份 JSON：已完成 / 缺失 / 损坏 / 过期的阶段，以及 `next_phase` 和该阶段要读的文档。续跑、回退、重做都由它决定。

但它**不生成**调研、旁白、字幕或视频，也不调用下游阶段；真正执行的是 agent 和阶段文档里写的脚本。手动运行它只适合查看进度或调试。

## 环境要求

agent 首次运行时按 `SKILL.md` 检查环境，已有配置直接复用。**项目依赖可以由已授权的 agent 代装；系统级调整和云端凭据由用户负责。**

- Python 3.9+（建议 3.11+；本地语音后端需要 3.10+）
- 系统依赖：`ffmpeg` / `ffprobe`、系统 Chrome、`yt-dlp`、Node.js（`npx`，用于 HyperFrames）
- 语音后端二选一：本地（macOS Apple Silicon 或 Linux + NVIDIA）或云端 DashScope

| 配置项 | 谁负责 |
| --- | --- |
| Python、系统软件及 NVIDIA 驱动 | 用户 / 宿主提供；需要安装、升级或重启时由用户 / 管理员执行 |
| `.venv`、Python 库（含 CUDA 版 PyTorch） | agent 可在用户授权和宿主权限允许的范围内创建 / 安装，用户也可手动执行 |
| 系统 CUDA Toolkit | 默认不要求安装；需要编译 CUDA 扩展时再由用户 / 管理员按需准备 |
| 本地模型权重 | 首次实际使用时由后端下载；agent 先说明资源需求并取得授权，也可使用用户预下载的目录 |
| 云端 KEY / 音色 ID | 用户通过启动 agent 的环境或宿主配置提供 |

## 安装

以下命令用于首次准备或补齐环境，可由已授权的 agent 代执行，也可由用户手动执行。已有 `.venv` 时只需激活，不必重建。在 skill 根目录运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip
```

按运行环境选择依赖：

| 环境 | 安装 |
| --- | --- |
| 所有平台（流水线本体） | `python3 -m pip install -r requirements.txt` |
| macOS Apple Silicon（本地 MLX） | `python3 -m pip install -r requirements-macos.txt` |
| Linux + NVIDIA（本地 Qwen3） | 先按下方步骤选择 CUDA 版 PyTorch，再安装 `requirements-cuda.txt` 与 Qwen 包 |
| 云端 DashScope | `python3 -m pip install -r requirements-cloud.txt` |
| 开发 / 测试 | `python3 -m pip install -r requirements-dev.txt` |

`requirements-dev.txt` 是“运行时依赖 + pytest / coverage”，不是只装测试工具；本地语音后端仍需按平台另外安装。

`playwright` 已随 requirements 安装，**不要**执行 `playwright install chromium`——脚本使用系统 Chrome。

### Linux + NVIDIA

**NVIDIA 驱动与 CUDA 版 PyTorch 是两回事。** 用户 / 管理员先准备兼容的 NVIDIA 驱动，agent 可以用 `nvidia-smi` 做只读检查。预编译 PyTorch 包自带或依赖所需的 CUDA 运行时，本项目默认不需要单独安装系统 CUDA Toolkit；只有编译 CUDA 扩展等场景才可能需要它。

激活 `.venv` 后，按 [PyTorch 官方安装选择器](https://pytorch.org/get-started/locally/) 安装与驱动兼容的 CUDA 版 `torch` / `torchaudio`，然后再安装下面的依赖。这个虚拟环境内的安装可由已授权的 agent 代执行。

`qwen-tts` 和 `qwen-asr` 分别锁定不同的 `transformers` 版本，不能让 pip 一次解析。下面的分步方式会绕过 ASR 的依赖校验，**不代表运行兼容性已验证**，仍需在 GPU 环境验证真实 TTS / ASR；`pip check` 可能继续报告版本冲突。

```bash
python3 -m pip install -r requirements-cuda.txt
python3 -m pip install qwen-tts==0.1.1
python3 -m pip install --no-deps qwen-asr==0.0.6
python3 -m pip install nagisa soynlp qwen-omni-utils flask pytz
```

装完确认 `torch.cuda.is_available()` 为 `True`，再用 `python3 scripts/voice-clone.py --resolve-backend` 和 `python3 scripts/transcribe.py --resolve-backend` 核对后端选择。这两个脚本的探测命令不会加载模型，不能代替真实推理验证。

## 语音后端与 KEY

`voice-clone.py` / `transcribe.py` 默认 `--backend auto`，按环境选后端。**macOS 和 Linux 的本地后端不需要任何 API key；只有云端 DashScope 需要。**

| 环境 | 后端 | Python 库 | 默认模型 | KEY |
| --- | --- | --- | --- | --- |
| macOS Apple Silicon | `mlx`（TTS + 直接对齐） | `mlx-audio` | TTS `mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16`；对齐 `mlx-community/Qwen3-ForcedAligner-0.6B-8bit` | 不需要 |
| Linux + NVIDIA | `qwen3tts`（TTS）/ `qwen3`（ASR） | `torch`、`torchaudio`、`soundfile`、`wetext`、`qwen-tts`、`qwen-asr` | TTS `Qwen/Qwen3-TTS-12Hz-1.7B-Base`；ASR `Qwen/Qwen3-ASR-1.7B`；对齐 `Qwen/Qwen3-ForcedAligner-0.6B` | 不需要 |
| 任意平台（云端兜底） | `dashscope` | `dashscope` | TTS `cosyvoice-v3.5-plus`；ASR `paraformer-v2` | `DASHSCOPE_API_KEY`；配音另需 `COSYVOICE_VOICE_ID` |

macOS 的正常路径是 MLX 直接把旁白文本对齐到音频，不要求独立 ASR 的环境检查通过。目前没有原生 macOS 本地 ASR 后端；只有直接对齐失败、需要 ASR 兜底且选择 DashScope 时，才需要安装云端依赖和配置 KEY。未配置时报告缺项，而不是把 KEY 当作本地运行的必填项。

### 本地模型下载

模型权重不是 Python 库：`pip install` 安装后端代码，实际合成、转写或对齐时，后端才按上表的模型 ID 从 Hugging Face 下载权重并缓存，后续复用。`--resolve-backend` 不会下载模型。

**通常不需要用户手工“安装模型”。** 首次下载前，agent 说明所选模型、预估下载量、磁盘及内存 / 显存需求，在授权范围内触发下载；只下载实际使用的模型，不一次下载所有平台的模型。表中的公开本地模型不需要 DashScope KEY。

离线或需要自定义存储位置时，用户也可以提前下载完整的兼容模型目录，再通过环境变量指定：macOS 用 `TTS_MODEL_MLX` / `ALIGNER_MODEL_MLX`，Linux 用 `QWEN3TTS_MODEL` / `QWEN3_ASR_MODEL` / `QWEN3_ALIGNER_MODEL`。

### 配置 KEY

只有选择云端语音后端时才需要下面的配置。脚本只读进程环境变量，不会自动加载 `.env`；在**启动 agent 的 shell** 中 export，或通过宿主的环境变量 / 秘密配置提供。已启动的 agent 不会继承另一个 shell 后来设置的变量。KEY 不写入仓库、`inputs.json` 或聊天日志。

```bash
# 显式选择云端 TTS / ASR；本地后端不用设置这些变量
export TTS_BACKEND="dashscope"
export ASR_BACKEND="dashscope"
export DASHSCOPE_API_KEY="sk-..."
export COSYVOICE_VOICE_ID="cosyvoice-v3.5-plus-..."
```

`DASHSCOPE_API_KEY` 从 DashScope 控制台获取；`COSYVOICE_VOICE_ID` 是用户已有或已创建的兼容音色 ID，并非 API key。仅使用云端 ASR 时不需要音色 ID。

确认后端选择：

```bash
python3 scripts/voice-clone.py --resolve-backend
python3 scripts/transcribe.py --resolve-backend
```

### 其他配置

- 参考音色默认用仓库里的 `resources/my_voice.wav`（转写 `resources/my_voice.txt`）；换音色设 `TTS_REF_WAV` / `TTS_REF_TEXT`，或传 `--reference-wav`。
- 后端选择：`TTS_BACKEND` 可设为 `mlx` / `qwen3tts` / `dashscope`，`ASR_BACKEND` 可设为 `qwen3` / `dashscope`；默认 `auto`，显式选择优先于自动检测。
- 覆盖模型：`TTS_MODEL_MLX`、`ALIGNER_MODEL_MLX`、`QWEN3TTS_MODEL`、`QWEN3_ASR_MODEL`、`QWEN3_ALIGNER_MODEL`、`ASR_MODEL`。
- 论文解析的 `MINERU_API_TOKEN` 和 vision 分析的 `VLM_API_KEY` 属于各自脚本的可选云端路径，见 `scripts/parse-pdf.py`、`scripts/vision-analyze.py` 顶部说明。
