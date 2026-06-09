# Composition Handoff — <TOPIC>

本文件是每个视频项目的 Phase 8 handoff，位于项目工作区根目录。它只记录本项目变量和用户定制约束；固定 hard rules 来自工作区本地副本 `references/composition-contract.md`。

## Required References

Phase 8 主 agent 必须在调用 HyperFrames sub-agent 前，把这些文件物化到项目工作区，并在本节写入实际相对路径。

- Contract：`references/composition-contract.md`（必需；从 skill 的 `references/composition-contract.md` 复制到项目工作区）
- Design：`references/design-<theme>.md`（如适用；从 skill 的对应 design 文件复制到项目工作区）

如果任一必需 reference 不存在，HyperFrames sub-agent 必须停止并反馈主 agent，不得凭默认审美继续制作。

## Project

- Topic：<Phase 1 中给出的一句话描述>
- Target duration：<N> 秒
- Orientation：<1920x1080 | 1080x1920 | 1080x1440>
- Output：`composition/renders/final.mp4`

## Inputs

路径相对于本 handoff，本 handoff 位于工作区根目录。

- 最终解说音频：`voice_clone/narration.mp3`
- 解说脚本：`narration.txt`
- 带词级时间戳的 ASR transcript：`transcribe/transcript.json`
- 素材 catalog：`material-catalog.json`
- 场景-素材分配：`scene-material-suggestions.json`（如存在；按 Contract Upstream #11 视为素材→scene 的硬性分配）
- 已预置字体：`fonts/`

## Style Hint

<来自 Phase 1 的自由格式 mood、受众、配色与节奏提示。示例：
"中文解说讲解视频，温暖的手绘笔记本氛围，节奏舒缓。"
"中文 AI/SaaS 技术编辑风，深色严肃语调，信息密集但易读，多 data callout。">

可选的风格路由参考：

- `references/design-dawn.md` —— 温暖手绘氛围参考
- `references/design-moon.md` —— 深色技术 / 编辑氛围参考
- `references/palettes.md` —— 备选的 mood / palette 路由

若上方 Required References 未指定 design 文件，这些参考只是 style hint，不是实现规范。若已指定 design 文件，以 design 文件中的具体数值（配色 hex 值、字体族、字重）为准；Style Hint 的自由格式描述退为补充说明。

## User-derived Customized Rules

这些规则来自用户输入、project prompt、`style-prompt.md` 或主 agent 与用户确认过的偏好。它们是本项目的额外约束，不属于全局 contract。

### Source summary

- <一句话说明这些规则来自哪里，例如：user prompt / style-prompt.md / follow-up feedback>

### Rules

- <规则 1：尽量保留用户原话，必要时改写为可执行约束>
- <规则 2>

### Conflict handling

- Customized rules 可以收紧 `references/composition-contract.md`，但不能静默放宽 contract 的 hard constraints。
- 如果 customized rule 与 contract 冲突，主 agent 必须在本 handoff 中写明冲突，并在调用 sub-agent 前向用户确认或选择更严格规则。
- 如果 customized rule 与 design 文件冲突，以 customized rule 优先；design 文件退为风格参考。
- HyperFrames sub-agent 遇到未标注冲突时，必须以 contract 为底线，并在 `composition/DESIGN.md` 记录处理方式。

## Project-specific Overrides

<仅写本项目特有、且不会放宽 contract hard constraints 的覆盖项。没有则写 “None”。>

## Deliverable Reminder

最终 deliverables 与硬性质量规则以 `references/composition-contract.md` 为准。
