# Phase 6 — 脚本与场景规划（委派给 coding agent）

本 phase 整体委派给 coding agent 完成：旁白（显示稿 + 词表）与叙事层场景规划由 script agent 按委派包独立完成。委派约定见 `references/delegation/conventions.md`（默认 pi-coding-agent（命令 `pi`）；派发 prompt 只有一句话，让对方读 handoff）。

## 输入

- Phase 3 的 `research.md`；
- Phase 5 的 `material-catalog.json`（标准模式且 `fetch_materials = false` 时没有 catalog，按“无素材”路径写纯旁白；论文模式总有 catalog，其中 `required_material_refs` 标出必须用上的关键图）；
- `inputs.json`（目标时长、语言、input_mode、`narration_requests`）。

模板不在本阶段输入里：用哪个模板、哪个 pattern 由 Phase 8 的 composition agent 决定，旁白按内容写。

## 输出

- `script.txt`（非空，显示稿）；
- `tts-lexicon.json`（非空 JSON map，显示形式 → 朗读形式）；
- `narration.txt`（非空，由 make-narration 生成）；
- `narration-offsets.json`（偏移表）；
- `scene-plan.json`（叙事层场景规划，非空列表）。

## 完成判据

- 运行 `pipeline-status` 后，Phase 6 不再是 `next_phase`；状态脚本替你判定下面各项：
- `script.txt`、`narration.txt` 存在且非空；`script.txt` 的字数（去掉所有空白）与 `inputs.json` 的 `duration`（分钟）× 60 × 7 的偏差在 ±15% 以内；
- `tts-lexicon.json` 是可解析的非空 JSON map，键值都是非空字符串；
- `narration-offsets.json` 是 `version` 为 1 的 JSON 对象，带非空的 `segments` 列表；它记录的 `script_length` / `narration_length` 等于当前 `script.txt` / `narration.txt` 的字符数；表里的 `script_sha256` / `narration_sha256`（make-narration 写入）必须等于当前两个文件的内容哈希——等长修改字符数看不出来，哈希躲不掉（改了 `script.txt` 就要重跑 make-narration）；
- `scene-plan.json` 是非空列表，每个 scene 有 `scene_id`、整数 `paragraphs`，以及非空字符串 `intent` / `content_plan`；所有 scene 的段落并集恰好是 `script.txt` 的第 1 段到最后一段；`template_scene` / `pattern_hints` / `beats` 已移除，出现即不合格（模板、pattern 与动作归 Phase 8 的 composition agent）；`material_candidates[].ref` 都能在 catalog 里按 entry 解析（图片 / 视频用 `<slug>/<id>`，视频 clip 用 `<slug>/<video_id>:<start>-<end>` 且与该 entry 某个 `selected_clips` 的起止相差都不超过 0.01 秒；裸 id 无效）；没有 catalog（`fetch_materials = false` 且不是论文模式）时，`material_candidates` 必须是空列表；catalog 的 `required_material_refs` 必须每条都被某个 scene 选上（选上只是候选，不代表已经进成片）；
- 校验通过后默认自动进入 TTS；只有 `inputs.json` 的 `approval_gates` 包含 `script` 时，才把旁白和场景摘要交给用户确认，再运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name} --approve script`。未明确确认前不要自己批准。

## 执行后自检

`pipeline-status` 会判定字数、段落覆盖、素材引用、朗读稿与显示稿的一致性（见上）。这些通过后，script agent 自己（主 agent 验收时再核一次）判断：

- 每个事实、数字、人名、日期都能在 `research.md` 里找到；找不到的删掉或回报上游不足；写“据报道”也必须能给出出处。
- 开头三句内有具体钩子（见基础指令的「开场钩子」），事实全部可追溯；第一句就给异常、困境或取舍，不是自我介绍或空泛预告。
- 叙事是否连贯：各部分是不是一个意思、段落之间有没有断裂或重复；第一个主体部分就开始回答开头的问题。
- 场景计划的 `intent` 与对应段落是否对得上；`content_plan` 是否说清了用哪些内容、按什么顺序和方式讲，而不是把 `intent` 再说一遍；引用的素材是不是真的能讲这段内容。
- 用户要求（语气、结尾不要 CTA 等，见 `narration_requests`）是否都体现出来了。
- 论文模式的 `required_material_refs` 是否都在讲解里真正讲到了，而不只是被选为候选。

不合格就重写：委派时交回 script agent，并指明是事实、结构还是引用的问题。发现是上游不足（证据不够、素材不对）时，回报主 agent，按 `references/pipeline-control.md` 登记更早的阶段重做，不要在旁白里编造补充。

## 下一步

Phase 7（配音与时间对齐）：只对 `narration.txt` 配音，并生成词级时间戳与时间轴；字幕排版归 Phase 8。

## 护栏

- **素材 catalog / vision 分析在 Phase 5，不是 Phase 6。** Phase 6 只引用 catalog 写脚本、匹配场景素材并规划内容演绎。
  ↳ DO NOT：catalog 还没建就写解说或场景-素材匹配；跳过 vision-analyze（论文模式下带 caption 的图表按 Phase 5 规则直接用 caption、不做 VLM，是设计行为，不算跳过）。

---

## Phase 6.1 — 委派 script agent

**主 agent 不读委派包里的基础指令**（`references/delegation/script/base-instructions.md` 只给被委派的 agent 读）。主 agent 做三件事：

1. 运行 `source .venv/bin/activate && python3 scripts/prepare-handoff.py {work_dir}/{topic_name} script`。它把委派约定和 script 委派包拷进 `{work_dir}/{topic_name}/references/delegation/`（已存在的副本不覆盖，要覆盖加 `--refresh`），再按 `inputs.json` 生成 `{work_dir}/{topic_name}/script-handoff.md`：Coding Agent、Inputs、Outputs、Required References（基础指令）、Additional Instructions（`narration_requests` 逐条列出，没有写 None），路径全是绝对路径。主 agent 不手写 handoff。

   用户在本阶段又提出旁白要求时，先按 `references/pipeline-control.md` 写进 `inputs.json` 的 `narration_requests`，再生成 handoff——handoff 只算一次，生成后追加的要求进不去。
2. 用输出 JSON 里的 `coding_agent` / `coding_model` 选择实际 agent / model，把 `dispatch_prompt` 原样派发，派发方式见 `references/delegation/conventions.md`。
3. script agent 返回后做 **Phase 6.2 的确定性校验**。

## Phase 6.2 — 主 agent 校验与按需审稿

script agent 报告完成后：

1. 运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}`。
2. `next_phase` 仍是 Phase 6 且 `reason` 为 `missing` / `corrupt` 时，把 `next_phase.problems`（产物 → 原因）原样交给 script agent 修复，修完再跑一次。字数、段落覆盖、素材引用都由状态脚本判定：不要自己手算，也不要改产物。
3. `next_phase.reason` 为 `awaiting_approval` 且 `gate` 为 `script` 时，把旁白和场景摘要（每个 scene 的 `scene_id` + `intent` + 一句 `content_plan` 摘要）交给用户确认；明确确认后运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name} --approve script`。未确认前不要自己批准或进入 Phase 7；用户明确授权后续全自动时，把 `inputs.json` 的 `approval_gates` 改为 `[]` 再跑状态脚本，不用 `--approve` 代替。未启用此 gate 时，不额外找用户审稿，按状态脚本的 `next_phase` 自动继续。

## Phase 6.3 — 朗读稿生成归属

`narration.txt` 与 `narration-offsets.json` 由 **script agent** 在委派任务内作为最后一步生成（handoff 的 Outputs 已列出 `scripts/make-narration.py` 命令；生成是确定性的）。主 agent 不运行 make-narration，只靠 6.2 的状态脚本确认这两份产物合格。不要手改 `narration.txt`；要改就改显示稿或词表，然后让 script agent 重新生成（改了显示稿需重新过一遍 6.2 校验；只有启用了 `script` gate 才需重新确认）。
