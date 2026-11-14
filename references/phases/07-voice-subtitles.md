# Phase 7 — 配音与时间对齐

## 输入

- `script.txt`：Phase 6 的 script agent 撰写的显示稿；后面字幕文本的唯一来源。
- `narration.txt`：script agent 在 Phase 6 最后运行 `scripts/make-narration.py`，按显示稿 + 词表生成；TTS 只读这份。
- `narration-offsets.json`：同一次 `make-narration.py` 生成；把朗读字符位置映射回显示字符位置，品牌名和数字因此能按显示形式出现。
- `scene-plan.json`：script agent 在 Phase 6 撰写。正常流程里一定存在；缺失时统一入口仍能运行，只是 timeline 不含 scene / cue。

本阶段不读 `inputs.json` 的 `layout`：排版属于 Phase 8。

## 输出

- `voice_clone/narration.mp3`：本轮配音。
- `transcribe/transcript.json`：本轮音频的句级 + 词级时间戳。
- `transcribe/timeline.json`：段落时间，以及场景规划存在时的 scene / cue 时间。

最终字幕不在这里生成：它要按定下来的 layout 切成合适宽度，因此属于 Phase 8。

## 完成判据

**状态脚本校验（`pipeline-status` 判定）**

- `voice_clone/narration.mp3` 是存在且非空的普通文件。状态脚本只做这一项，不校验音频时长。
- `transcribe/transcript.json` 是非空句子列表，每句是对象且含 `begin` / `end` / `text` / `words`，其中 `words` 是列表。
- `transcribe/timeline.json` 的 `paragraphs` 是非空列表，每项含数字 `index` / `begin_s` / `end_s`；可选 `scenes` / `cues` 存在时按各自形状带数字秒数；带 `beats` 的时间轴是旧构建，会被打回。

**执行者核对（脚本判断不了）**

- 统一命令退出码为 0；非 0 时按输出 JSON 的 `failed_step` 处理，见「执行与重跑」，不要手写或手动补跑子命令。
- 看 `transcript_method`：`asr` 意味着词级时间来自识别，文本不保证与朗读稿逐字一致。
- 看 `warnings`：漏读告警、`broke inside a token` 告警出现时，核对那一段是重复、被吞掉还是断词，需要改文本就回上游。
- 音频时长与时间轴最后一段的 `end_s` 对得上；偏差明显说明音频或 transcript 不是本轮的。

## 下一步

Phase 8（composition，委派）：sub-agent 根据内容选定 design 并安装字体，按最终视觉 scene 生成字幕单元、用时间轴和素材 catalog 完成画面与渲染。

## 护栏

- **TTS 后端由环境变量选择。** 配音脚本、参考音色、参数和依赖见 `scripts/voice-clone.py` 的顶部说明。**绝不**使用 `npx hyperframes tts`。参考音频缺逐字稿时脚本按自己的顺序查找并自动转写。
- **ASR 后端由环境变量选择。** transcript 必须带词级时间戳。后端、参数和依赖见 `scripts/transcribe.py` 的顶部说明。voice-clone.py 保证要么产出本轮新鲜的 transcript、要么失败：直对齐优先，失败自动回退 ASR，成功 JSON 带 `transcript_method`。即使主用直对齐（如 mlx），也要配置一种 ASR 后备，否则回退路径不可用。
  ↳ DO NOT：用 `npx hyperframes transcribe`；接受没有词级时间戳的 transcript；沿用上一轮留下的 transcript。
- **不要手改派生产物。** 解说内容只放在 `narration.txt`（由 `make-narration.py` 生成，不要手写），时间轴由脚本生成。要改就改显示稿、词表或 scene-plan，再由对应负责人重跑。
  ↳ DO NOT：手改 `narration.txt`、`timeline.json`；把脚本复制一份；把解说文本粘进 Python 源码。
- **避免全角中文冒号 `：`。** 显示稿和朗读稿里都改用 `——`、逗号或重新断句；TTS 在它之前会偶发停顿。

## 执行与重跑

在 skill 根目录只运行这一条：

```bash
source .venv/bin/activate && python3 scripts/voice-subtitles.py {work_dir}/{topic_name}
```

它先校验输入，再依次调用 voice-clone.py 与 align-narration.py（`--mode timing`）；场景规划探测和输出路径都由它处理，不要手拼子命令。

- **默认（完整生成）**：重新配音，产出本轮新鲜的 transcript，再重建时间轴。
- **`--align-only`**：复用现有音频和 transcript，只重建时间轴。只在音频仍然对应这版朗读稿时才用——例如只改了 `scene-plan.json`。排版变化不是这里的理由：本阶段不看书排。
- 指定后端加 `--backend <name>`，否则由 `TTS_BACKEND` / 自动探测选择。

失败时按输出 JSON 的 `failed_step` 处理：`inputs` 表示输入缺失或为空；`tts` 表示配音或 transcript 失败；`align` 表示时间对齐失败（包括偏移表不合格）。`child` 是对应子进程的错误 JSON；TTS 失败时里面仍有 `transcript_attempts`，`narration.mp3` 保留。

### 什么时候要回上游

下面几种情况 Phase 7 自己解决不了：

| 要改的东西 | 找谁 |
| --- | --- |
| 读音、断句、措辞 | Phase 6 的 script agent：改词表或显示稿，由它重新生成 `narration.txt` 与 `narration-offsets.json` |
| scene / cue | 同上，改 `scene-plan.json` |
| 音色或后端，但输入文件没变 | 主 agent 登记 `--redo 7-voice-subtitles --reason "..."`，再完整重跑（环境变量不在依赖表里，改文件触发不了） |

`narration.txt` 或 `narration-offsets.json` 一变，旧音频就作废：必须完整重跑，不能加 `--align-only`。

### 下游要不要跟着重做

由主 agent 按已知修改范围显式登记，不由文件变化推断。本阶段没完成时，后面的阶段是 `pending`，暂不检查；本阶段重建过（重跑配音 / 对齐 / 转写）后，主 agent 核对影响范围并登记下游重做：Phase 8 按音频 / transcript / 时间轴 / 显示稿等依赖、Phase 9 / Phase 10 按成片与混音交付范围判断，按各自文档重做。用户明确要求多个阶段都重做时才逐项登记 `--redo`。

只重对齐时音频与 transcript 的字节没变：没有新鲜度比对，状态脚本不会因此要求本阶段重做。反过来，朗读稿已经改过却只重跑对齐时，主 agent 要完整重跑本阶段并登记重做——那份音频确实不是当前稿的。

## 时间戳与字幕

两步，不要混：

1. **音频 → 朗读稿的时间**：voice-clone.py 优先用后端自带的直接对齐器，失败或该后端没有对齐器时自动调用 transcribe.py 做 ASR。两条路都写同一份 `transcribe/transcript.json`。
2. **朗读稿 → 显示稿的映射**：align-narration.py 用 `narration-offsets.json` 把时间还原到显示稿，并写出时间轴。本阶段只做这两步。

**字幕文本的切分在 Phase 8 做**：它要按最终 layout 的 `caption` 规格算宽度，所以等 layout 定下来之后由确定性脚本再跑一次（同一个 align-narration.py 的 `--mode subtitles`）。本阶段不猜字号、行数或每行字数。

**共同的时间戳契约**（后端可换，形状不变；参数、硬件和依赖看脚本顶部与 `--help`）：

- `transcript.json` 是句子列表，每句 `{begin, end, text, words}`，每个词 `{text, begin, end}`；时间单位是**整数毫秒**。
- 句子的切分取决于来源：直接对齐按朗读稿原文的标点 / 换行分组，云端 ASR 沿用服务返回的句子。两条路都保留词级时间，但**不保证**句子有统一的最大长度或时长。
- `timeline.json` 的 `begin_s` / `end_s` 用秒。

**`narration-offsets.json` 的契约**：`version`、`script_length`、`narration_length`、`segments` 全部必需；字数必须与当前 `script.txt` / `narration.txt` 对得上，对不上时脚本会直接报错并让你重跑 `make-narration.py`。

**cue 只能取自显示稿。** `scene-plan.json` 的 `cues` 必须原样摘自显示稿，且落在该 scene 的 `paragraphs` 范围内。对齐时会归一化大小写、标点、空格和数字写法，所以 `NVIDIA` 和 `nvidia，` 都能匹配；但换成朗读稿里的读法（如 `英伟达`）就对不上显示稿，会被跳过。出现 `cue not found for scene ...` 时先核对显示稿文本和段落归属，确实要改就走上面「什么时候要回上游」。

## 异常恢复

**转写失败，但音频已生成。** `failed_step` 为 `tts` 且 `child.transcript_attempts` 非空，说明配音成功、只是没拿到 transcript（`narration.mp3` 会保留）：

- 先换一个已配置的 ASR 后备后端，用同一条命令重跑。
- 所有后端都不可用时，向用户要一份**对应本轮音频**的外部 transcript，必须带词级时间戳；没有时间戳的纯文本不能用。核对它确实属于这段音频（时长和端点对得上）、每句都有非空 `words` 且时间单调，再存到 `transcribe/transcript.json`。
- 存好后跑同一条命令加 `--align-only`，只重跑对齐，不重做 TTS。
- 默认命令会先删掉这个路径上已有的 transcript（它描述的是更早那份音频），所以导入后不要直接跑不带 `--align-only` 的命令。

**换音色 / 换后端。** 见「什么时候要回上游」的最后一行：这类变化不在依赖表里，必须登记 redo 后完整重跑。

**长旁白 OOM。** 切到已配置且可用的后端，用同一条命令完整重跑；没有可用后端就报告阻塞、请用户补环境配置。不要自己把旁白切段配音再拼接——本阶段没有把分段的时间戳合成回整段音频的入口，拼出来的音频和 transcript 对不上。

**字幕过宽或切开位置不对。** 这是 Phase 8 的事：那里能看到 layout 的 caption 规格和实际效果。字幕默认由脚本生成，制作中可以编辑文本与边界，需要改字幕时直接编辑当前字幕文件即可；属于显示稿断句问题时按上面「什么时候要回上游」改显示稿。
