# Composition Handoff — <TOPIC>

本文件位于项目工作区根目录。它记录本项目变量、输入路径、style hint、用户定制约束和冲突说明；固定规则与 QA 协议来自工作区本地副本 `references/composition-rules.md`。

## Required References

Phase 8 主 agent 必须在调用 HyperFrames sub-agent 前物化这些文件，并在本节写入实际相对路径。

- Rules：`references/composition-rules.md`（必需；从 skill 的 `references/composition-rules.md` 复制到项目工作区）
- Design：`references/design-<theme>.md`（如适用；从 skill 的对应 design 文件复制到项目工作区）

如果任一必需 reference 不存在，HyperFrames sub-agent 必须停止并反馈主 agent，不得凭默认审美继续制作。

## Project

- Topic：<Phase 1 中给出的一句话描述>
- Target duration：<N> 秒
- Orientation：<1920x1080 | 1080x1920 | 1080x1440>
- Output：`composition/renders/final.mp4`

## Expected Inputs

路径相对于本 handoff；本 handoff 位于工作区根目录。

- 最终解说音频：`voice_clone/narration.mp3`
- 解说脚本：`narration.txt`
- 带词级时间戳的 ASR transcript：`transcribe/transcript.json`
- 校准后的字幕单元：`transcribe/subtitle-units.json`
- 素材 catalog：`material-catalog.json`
- 场景-素材分配：`scene-material-suggestions.json`（如存在）
- 屏幕文本块规划：`scene-text-plan.json`（如存在）
- 已预置字体：`fonts/`

输入文件的固定解释规则以 `references/composition-rules.md` 为准。

Phase 8 需要按 `references/composition-rules.md` 读取 layout-aware 字段：`material-catalog.json` 可能包含 `aspect_ratio`、`ratio_bucket`、`layout_affordance`、`focal_region`；`scene-material-suggestions.json` 可能包含 `layout_role`、`layout_reason`、`material_refs`、`continuation_group_id`、`continuation_of`。这些字段是布局决策输入，不替代固定规则。

### Scene text-plan routing

若 `scene-text-plan.json` 存在，Phase 8 HyperFrames sub-agent 必须把它作为非字幕屏幕文本的结构化输入，而不是普通 style hint：

1. 按 `scene_index` 把 `scene-text-plan.json` 条目与 `scene-material-suggestions.json` 条目 join。
2. 对每个 scene，先读取 `material_ref` / `material_refs` / `no_match`、`layout_role`、catalog 尺寸、`layout_affordance` 和 `focal_region`（如有），再读取该 scene 的 `visual_text_units`。
3. `priority: "primary"` 的 unit 是必须尝试实现的信息单元；若因素材尺寸、字幕安全区或 overlap 无法实现，必须在 `composition/DESIGN.md` 记录降级原因。
4. `visual_role` / `domain_hint` / `template_hint` 只指定信息形态，不指定最终 DOM / CSS；最终布局仍以 `references/composition-rules.md` 的素材占比、安全区、overlap 和 peak-state audit 为准。
5. 有图片 / 视频素材的 scene，`visual_text_units` 默认放在素材外置信息区、侧栏、上 / 下信息带、角标区或分时轮换区；禁止把前景文本压在 catalog 素材关键区域上。例外：`video_first` 的全屏 / 近全屏视频可按 R16 使用少量 shrink-to-fit 半透明短文本浮层，但必须避开主体动作、UI 关键区域、人物脸部和 `focal_region`。

## Style Hint

来自 Phase 1 的自由格式 mood、受众、配色与节奏提示。示例：
- "中文解说讲解视频，温暖的手绘笔记本氛围，节奏舒缓。"
- "中文 AI/SaaS 技术编辑风，深色严肃语调，信息密集但易读，多 data callout。"

可选的风格路由参考：

- `references/design-dawn.md` —— 温暖手绘氛围参考
- `references/design-moon.md` —— 深色技术 / 编辑氛围参考
- `references/design-github.md` —— GitHub trending / repo launch / open source 项目参考
- `references/design-producthunt.md` —— Product Hunt 周榜 / SaaS launch / 新产品发布参考
- `references/palettes.md` —— 备选的 mood / palette 路由

若 Required References 未指定 design 文件，这些参考只是 style hint，不是实现规范。若已指定 design 文件，以 design 文件中的具体数值为准；Style Hint 的自由格式描述退为补充说明。

## Animation / Effect Skill Preference

- Preference：`None`，或用户指定的一个 / 多个 skill：`gsap` / `animejs` / `waapi` / `css-animations` / `lottie` / `three` / `typegpu`
- Reason：用户或项目为何要求这些 skill；没有则写 “None”。

Tailwind 可以作为静态 layout / style utility 偏好记录在 Style Hint 或 Project-specific Overrides 中，但不属于 animation/effect skill。若没有明确偏好，HyperFrames sub-agent 选择最小合适 skill(s)，并在 `composition/DESIGN.md` 记录原因。此字段只能补充项目偏好，不得覆盖 `references/composition-rules.md`。

## User-derived Customized Rules

这些规则来自用户输入、project prompt、`style-prompt.md` 或主 agent 与用户确认过的偏好。它们是本项目的额外约束，不属于全局固定规则。

### Source summary

- <一句话说明这些规则来自哪里，例如：user prompt / style-prompt.md / follow-up feedback>

### Rules

- <规则 1：尽量保留用户原话，必要时改写为可执行约束>
- <规则 2>

## Rule Application Notes

`references/composition-rules.md` 的 Scope and Required References 是权威边界。Customized rules 可以补充项目偏好，但不得修改或覆盖 rules 文件。

### Conflict notes

- <如果 customized rule 与 rules 文件冲突，在这里写明；没有则写 “None”。>

### Design-file notes

- <如果 customized rule 与 design 文件冲突，在这里写明采用哪条项目偏好；没有则写 “None”。>

HyperFrames sub-agent 遇到未标注冲突时，必须以 `references/composition-rules.md` 为底线，并在 `composition/DESIGN.md` 记录处理方式。

## Project-specific Overrides

<仅写本项目特有、且不会修改或覆盖 `references/composition-rules.md` 的覆盖项。没有则写 “None”。>

## Deliverable Reminder

本项目期望产物：

- `composition/index.html`
- `composition/DESIGN.md`
- `composition/renders/final.mp4`
- `composition/qa-report.json`（执行 post-render visual QA 后）
- `composition/qa-history.md`（执行 post-render visual QA 后）

固定产物质量要求以 `references/composition-rules.md` 为准。
