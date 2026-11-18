# Phase 6 — 脚本与场景规划（委派给 coding agent）

本 phase 按 `references/delegation/conventions.md` 整体委派给 script coding agent，独立产出旁白（显示稿 + 词表 + 朗读稿 + 偏移表）与叙事层场景规划。

## 输入

- `research-brief.md`（Phase 3 调研简报）；
- `material-catalog.json`（Phase 5 产出；标准模式且 `fetch_materials = false` 时无 catalog，走无素材路径；论文模式总有 catalog，含成片必出的 `required_material_refs`）；
- `inputs.json`（目标时长、语言、`input_mode`、`narration_requests`）。

模板与 pattern 归 Phase 8 决定，不在本阶段输入中。

## 输出

- `script.txt`（非空，显示稿）；
- `tts-lexicon.json`（非空 JSON map，显示形式 → 朗读形式）；
- `narration.txt`（非空，由 `make-narration.py` 生成）；
- `narration-offsets.json`（偏移表）；
- `scene-plan.json`（叙事层场景规划，非空列表）。

## 完成判据

- `pipeline-status` 校验通过（Phase 6 不再是 `next_phase`）：
- `script.txt`、`narration.txt` 存在且非空；`script.txt` 的字数（去掉所有空白）与 `inputs.json` 的 `duration`（分钟）× 60 × 5（按 5 中文字/秒计算）的偏差在 ±15% 以内；
- `tts-lexicon.json` 为非空 JSON map，键值均为非空字符串；
- `narration-offsets.json`（`version: 1`）含非空 `segments`，且 `script_length` / `narration_length` 等于当前 `script.txt` / `narration.txt` 字符数（改 `script.txt` 必须重跑 `make-narration.py`）；
- `scene-plan.json` 为非空列表：每项仅含契约允许字段（`scene_id`、整数 `paragraphs`、非空 `intent` / `content_plan` 及可选 `material_candidates` / `cues`；模板、pattern 与动作归 Phase 8）；全部 scene 的 `paragraphs` 并集恰好覆盖 `script.txt` 第 1 段到最后一段；`material_candidates[].ref` 均可在 catalog 按 entry 解析（图片 / 视频 `<slug>/<id>`，片段 `<slug>/<video_id>:<start>-<end>` 且与 `selected_clips` 起止误差 ≤ 0.01s，裸 id 无效；无 catalog 时为 `[]`）；`required_material_refs` 每条均至少被一个 scene 选入候选；
- 校验通过后默认自动进入 Phase 7；仅当 `inputs.json` 的 `approval_gates` 含 `"script"` 时，先交用户确认再执行 `--approve script`。

## 执行后自检

状态脚本通过后，由 script agent 自检（主 agent 验收复核）：

- 所有事实、数字、人名、日期（含标“据报道”的内容）均可在 `research-brief.md` 追溯出处；无依据处删去或回报上游不足。
- 开场三句短句内立住具体钩子（首句直接给异常、困境或取舍，禁自我介绍与空泛预告）；首个主体部分即开始回答开头问题，段落连贯无重复。
- 默认采用直白易懂的深入浅出讲法（除非 `narration_requests` 另有指定）：先引出具体问题再讲机制，禁术语堆砌、碎短句连发或空泛套话；抽象难点配日常例子或分步拆解。
- 每个 scene 的 `intent` 与段落一致；`content_plan` 具体写明登场对象、因果 / 对比关系与分步状态变化（难点有分步推演或类比，深讲同一张技术图时写明依次拆解的局部区域，足以支撑下游动画演绎），不重复 `intent`；catalog 中贴合场景的通用素材尽量优先选入 `material_candidates`（不硬塞无关素材，也不预设同一通用配图跨不同话题反复出场）。
- `narration_requests` 要求均已兑现；论文模式的 `required_material_refs` 关键图 / 表均在正文中实际讲到，而非仅挂名候选。

不合格交回 script agent 指明原因重写；属上游证据或素材不足时按 `references/pipeline-control.md` 登记更早阶段重做，禁编造补充。

## 下一步

Phase 7（配音与时间对齐）：对 `narration.txt` 配音并生成词级时间戳与时间轴；字幕切分归 Phase 8。

## 护栏

- **先完成 Phase 5 catalog 再写稿与匹配素材。** 本阶段只引用 catalog 写旁白、选候选并规划 `content_plan`，禁跳过前置视觉分析（论文模式非空 caption 直接复用属正常规则）。

---

## Phase 6.1 — 委派 script agent

**主 agent 不阅读 `references/delegation/script/base-instructions.md`**，只做三步：

1. 将新增旁白要求（如有）先写入 `inputs.json.narration_requests`，再运行 `source .venv/bin/activate && python3 scripts/prepare-handoff.py {work_dir}/{topic_name} script` 物化委派包（覆盖旧副本加 `--refresh`）并生成 `{work_dir}/{topic_name}/script-handoff.md`。
2. 按输出 JSON 的 `coding_agent` / `coding_model` 原样派发单句 `dispatch_prompt`（见 `references/delegation/conventions.md`）。
3. 返回后执行 Phase 6.2 校验。

## Phase 6.2 — 主 agent 校验与按需审稿

1. 运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}`。
2. 若 `next_phase` 仍为 Phase 6 且 `reason` 为 `missing` / `corrupt`，将 `next_phase.problems` 原样交回 script agent 修复后重验（主 agent 不手算字数或手改产物）。
3. 若 `next_phase.reason == "awaiting_approval"` 且 `gate == "script"`，向用户展示旁白及各 scene 的 `scene_id + intent + 一句 content_plan 摘要`；确认后运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name} --approve script`（授权后续全自动时改 `approval_gates` 为 `[]` 再跑状态脚本）。未启用 gate 时自动继续。

## Phase 6.3 — 朗读稿生成归属

`narration.txt` 与 `narration-offsets.json` 由 **script agent** 在委派末尾调用 `scripts/make-narration.py` 确定性生成。禁止手改 `narration.txt`；需调整时修改 `script.txt` 或 `tts-lexicon.json` 后由 script agent 重新生成并重过 6.2 校验。
