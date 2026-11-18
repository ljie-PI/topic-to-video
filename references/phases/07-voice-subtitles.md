# Phase 7 — 配音与时间对齐

## 输入

- `script.txt`：Phase 6 撰写的显示稿（字幕文本唯一来源）。
- `narration.txt`：Phase 6 运行 `scripts/make-narration.py` 生成的朗读稿（TTS 唯一输入）。
- `narration-offsets.json`：同次生成的字符偏移表（将朗读字符位置映射回显示字符位置）。
- `scene-plan.json`：Phase 6 场景规划（缺失时仍可运行，仅输出的 timeline 不含 `scenes` / `cues`）。

## 输出

- `voice_clone/narration.mp3`：本轮配音。
- `transcribe/transcript.json`：本轮音频的句级 + 词级时间戳。
- `transcribe/timeline.json`：段落时间，以及场景规划存在时的 scene / cue 时间。

最终字幕单元需按视觉 scene 的 layout 宽度切分，归属 Phase 8 生成。

## 完成判据

**状态脚本校验（`pipeline-status` 判定）**

- `voice_clone/narration.mp3` 为存在且非空的普通文件。
- `transcribe/transcript.json` 为非空句子列表，每句含 `begin` / `end` / `text` / `words`（`words` 为列表）。
- `transcribe/timeline.json` 的 `paragraphs` 为非空列表（每项含数字 `index` / `begin_s` / `end_s`），可选 `scenes` / `cues` 按契约携带数字秒数。

**执行者核对（脚本判断不了）**

- 统一命令退出码为 `0`；非 `0` 时按输出 JSON 的 `failed_step` 处理（禁手动拼装子命令补跑）。
- 检查 `transcript_method`：`asr` 表示时间戳来自语音识别，文本未必与朗读稿逐字一致。
- 检查 `warnings`：出现漏读或 `broke inside a token` 告警时核对对应片段是否吞字、重复或断词，需改文本则回退 Phase 6。
- 音频实际时长与 `timeline.json` 末段 `end_s` 吻合（明显偏差说明音频或 transcript 非本轮产物）。

## 下一步

Phase 8（composition，委派）：选定 design 并安装字体，按视觉 scene 生成字幕单元、组装画面并渲染。

## 护栏

- **TTS / ASR 后端由环境变量选择**（参数与依赖见 `scripts/voice-clone.py`、`scripts/transcribe.py` 顶部说明），**严禁**使用 `npx hyperframes tts` 或 `npx hyperframes transcribe`。
- **必须产出本轮新鲜的词级时间戳 transcript**（直对齐优先，失败自动回退 ASR，成功 JSON 含 `transcript_method`；主用直对齐如 `mlx` 时也建议配置后备 ASR），禁沿用旧轮次或无词级时间的 transcript。
- **禁手改派生产物**（`narration.txt`、`timeline.json`）或把解说粘进源码；调整内容须回 Phase 6 修改显示稿、词表或 `scene-plan.json` 后重跑。
- **禁用全角中文冒号 `：`**（改用 `——`、逗号或断句，避免 TTS 偶发停顿）。

## 执行与重跑

在 skill 根目录统一运行：

```bash
source .venv/bin/activate && python3 scripts/voice-subtitles.py {work_dir}/{topic_name}
```

脚本自动校验输入并串联 `voice-clone.py` 与 `align-narration.py --mode timing`：

- **默认（完整生成）**：重新合成配音、生成本轮新鲜 transcript 并重建时间轴。
- **`--align-only`**：复用当前音频与 transcript 仅重建时间轴（**仅限**朗读稿未变、只改了 `scene-plan.json` 或刚导入外部 transcript 时使用；`narration.txt` 或 `narration-offsets.json` 一旦变更必须完整重跑）。
- **`--backend <name>`**：显式指定后端（缺省按 `TTS_BACKEND` 或自动探测）。
- **失败定位（`failed_step`）**：`inputs`（输入缺失/为空）、`tts`（配音或转写失败，`child` 保留 `transcript_attempts`，已合成的 `narration.mp3` 保留）、`align`（偏移表不匹配或对齐失败）。

### 什么时候要回上游

| 要改的东西 | 负责方与做法 |
| --- | --- |
| 读音、断句、措辞 | Phase 6 script agent：改词表或显示稿并重跑 `make-narration.py`，随后本阶段完整重跑 |
| scene / cue | Phase 6 script agent：改 `scene-plan.json`，本阶段可用 `--align-only` 重建时间轴 |
| 音色或后端（输入文件未变） | 主 agent 登记 `--redo 7-voice-subtitles --reason "..."` 后完整重跑 |

重跑过配音 / 转写 / 对齐后，由主 agent 按修改影响范围显式登记 Phase 8 及成片 QA / 混音（Phase 9 / 10）重做。

## 时间戳与字幕

1. **音频 → 朗读稿时间**：`voice-clone.py` 优先直对齐，失败回退 `transcribe.py` ASR，统一写出 `transcribe/transcript.json`（每句 `{begin, end, text, words}`，每词 `{text, begin, end}`，单位为**整数毫秒**；句子长度无统一上限）。
2. **朗读稿 → 显示稿时间轴**：`align-narration.py` 按 `narration-offsets.json`（须与当前 `script.txt` / `narration.txt` 长度严格一致）还原显示稿位置并写出秒级 `timeline.json`。字幕按版面宽度切分留到 Phase 8（`align-narration.py --mode subtitles`）。

**cue 必须原样摘自显示稿**且落在所属 scene 的 `paragraphs` 内（对齐器自动归一化大小写、标点、空格和数字写法，但写成朗读稿译音如 `英伟达` 会因匹配不到显示稿 `NVIDIA` 而跳过；报 `cue not found` 时回 Phase 6 核对）。

## 异常恢复

- **配音成功但转写失败**（`failed_step == "tts"` 且 `child.transcript_attempts` 非空，`narration.mp3` 已保留）：
  1. 优先切换已配置的后备 ASR 后端重跑原命令；
  2. 全部后端不可用时，请用户提供**对应本轮音频、带词级时间戳**的外部 transcript（核对时长/端点一致、每句 `words` 非空且时间单调），存入 `transcribe/transcript.json`；
  3. 必须加 `--align-only` 重跑只做对齐（默认命令会先删已有 transcript，直接跑会清空刚导入的文件）。
- **长旁白 OOM**：切换到可用的其他后端完整重跑，或报告阻塞请用户补环境；**禁止**手工分段配音再拼接（会导致时间戳与整段音频错位）。
- **字幕过宽或断行不当**：归 Phase 8 按所选 layout 规格重切或直接编辑字幕文件；属显示稿断句问题时回 Phase 6 修改。
