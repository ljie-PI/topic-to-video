# Phase 6 — 脚本与场景规划（委派给 coding agent）

本 phase 整体委派给 coding agent 完成：旁白（显示稿 + 词表）与叙事层场景规划由 script agent 按委派包独立完成。委派约定见 `references/delegation/conventions.md`（默认 claude-code；派发 prompt 只有一句话，让对方读 handoff）。

## 输入

Phase 3 的 `research-brief.md` + Phase 5 的 `material-catalog.json`（标准模式且 `fetch_materials = false` 时没有 catalog，按“无素材”路径写纯旁白；论文模式总有 catalog）+ `inputs.json`（目标时长、语言、input_mode、所选模板）+ 模板旁白要求（`modules/templates/<template>/narration.md`，如有）+ 项目指令 `narration-instructions.md`（如有）。

## 输出

`script.txt`（非空，显示稿）+ `tts-lexicon.json`（非空 JSON map，显示形式 → 朗读形式）+ `narration.txt`（非空，由 make-narration 生成）+ `narration-offsets.json`（偏移表）+ `scene-plan.json`（叙事层场景规划，非空列表）。

## 完成判据

运行 `pipeline-status` 后，Phase 6 不再是 `next_phase`。状态脚本替你判定：

- `script.txt`、`narration.txt` 存在且非空；`script.txt` 的字数（去掉所有空白）与 `inputs.json` 的 `duration`（分钟）× 60 × 7.5 的偏差在 ±15% 以内；
- `tts-lexicon.json` 是可解析的非空 JSON map，键值都是非空字符串；
- `narration-offsets.json` 是 `version` 为 1 的 JSON 对象，带非空的 `segments` 列表；它记录的 `script_length` / `narration_length` 等于当前 `script.txt` / `narration.txt` 的字符数；表里的 `script_sha256` / `narration_sha256`（make-narration 写入）必须等于当前两个文件的内容哈希——等长修改字符数看不出来，哈希躲不掉（改了 `script.txt` 就要重跑 make-narration）；
- `scene-plan.json` 是非空列表，每个 scene 有 `scene_id` 和整数 `paragraphs`；所有 scene 的段落并集恰好是 `script.txt` 的第 1 段到最后一段；`material_candidates[].ref` 都能在 catalog 里解析（素材 id，或 `<video_id>:<start>-<end>` 且与某个 `selected_clips` 的起止相差都不超过 0.01 秒）；没有 catalog（`fetch_materials = false` 且不是论文模式）时，`material_candidates` 必须是空列表。

通过后，把旁白和场景摘要交给用户确认，再进入 TTS。

## 下一步

Phase 7（配音与字幕）：只对 `narration.txt` 配音，并生成词级时间戳与字幕单元。

---

## Phase 6.1 — 委派 script agent

**主 agent 不读委派包里的基础指令**（`references/delegation/script/base-instructions.md` 只给被委派的 agent 读）。主 agent 做三件事：

1. 运行 `source .venv/bin/activate && python3 scripts/prepare-handoff.py {work_dir}/{topic_name} script`。它把委派约定和 script 委派包拷进 `{work_dir}/{topic_name}/references/delegation/`（已存在的副本不覆盖，要覆盖加 `--refresh`），再按 `inputs.json` 和工作区里实际存在的文件生成 `{work_dir}/{topic_name}/script-handoff.md`：Coding Agent、Inputs、Outputs、Required References（基础指令 → 模板旁白要求）、Additional Instructions（实际存在的 `narration-instructions.md`，没有写 None），路径全是绝对路径。主 agent 不手写 handoff。
2. 把输出 JSON 里的 `dispatch_prompt` 原样派发，派发方式见 `references/delegation/conventions.md`。
3. script agent 返回后做 **Phase 6.2 的确定性校验**。

## Phase 6.2 — 主 agent 校验与用户确认

script agent 报告完成后：

1. 运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}`。
2. `next_phase` 仍是 Phase 6 时，把 `next_phase.problems`（产物 → 原因）原样交给 script agent 修复，修完再跑一次。字数、段落覆盖、素材引用都由状态脚本判定：不要自己手算，也不要改产物。
3. Phase 6 不再是 `next_phase` 后，把旁白和场景摘要（每个 scene 的 `scene_id` + `intent`）交给用户确认；用户确认前不要进入 Phase 7。

## Phase 6.3 — 朗读稿生成归属

`narration.txt` 与 `narration-offsets.json` 由 **script agent** 在委派任务内作为最后一步生成（handoff 的 Outputs 已列出 `scripts/make-narration.py` 命令；生成是确定性的）。主 agent 不运行 make-narration，只靠 6.2 的状态脚本确认这两份产物合格。不要手改 `narration.txt`；要改就改显示稿或词表，然后让 script agent 重新生成（改了显示稿需重新过一遍 6.2 校验与用户确认）。
