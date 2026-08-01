# Composition Handoff — <TOPIC>

本文件位于项目工作区根目录。它记录本项目变量、输入路径、style hint、用户定制约束和冲突说明；固定规则来自工作区本地副本 `references/composition-rules.md`，动画软路由来自 `references/animation-routing.md`，stage / QA 协议来自 `references/composition-stage-protocol.md`。

## Required References

Phase 8 主 agent 必须在调用 HyperFrames sub-agent 前物化这些文件，并在本节写入实际相对路径。

- Rules：`references/composition-rules.md`（必需；从 skill 的 `references/composition-rules.md` 复制到项目工作区）
- Animation Routing：`references/animation-routing.md`（必需；`visual_role` / `layout_role` 动画候选与 runtime 软路由）
- Stage Protocol：`references/composition-stage-protocol.md`（必需；Phase 8 self-audit / render / Visual QA / feedback loop）
- Design：`references/design-default.md`（未指定主题时的默认；若已选择其他主题，替换为对应的 `references/design-<theme>.md` 并从 skill 复制到项目工作区）

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

输入文件的语义解释、`scene-text-plan.json` routing、layout-aware 字段读取和 `visual_role × orientation` 规则以 `references/composition-rules.md` 为准；动画候选机制与 runtime 选择参考 `references/animation-routing.md`；Phase 8.3-8.7 的执行、检查、QA 和反馈循环以 `references/composition-stage-protocol.md` 为准。

## Style Hint

来自 Phase 1 的自由格式 mood、受众、配色与节奏提示。示例：
- "中文解说讲解视频，温暖的手绘笔记本氛围，节奏舒缓。"
- "中文 AI/SaaS 技术编辑风，深色严肃语调，信息密集但易读，多 data callout。"

可选的风格路由参考：

- `references/design-default.md` —— 未指定主题时的默认参考（暖白 + 克制薰衣草编辑风）
- `references/design-dawn.md` —— 温暖手绘氛围参考
- `references/design-moon.md` —— 深色技术 / 编辑氛围参考
- `references/design-github.md` —— GitHub trending / repo launch / open source 项目参考
- `references/design-producthunt.md` —— Product Hunt 周榜 / SaaS launch / 新产品发布参考
- `references/palettes.md` —— 备选的 mood / palette 路由

未指定主题时，Required References 使用 `references/design-default.md`。若已指定其他 design 文件，以该文件中的具体数值为准；Style Hint 的自由格式描述退为补充说明。

## Animation / Effect Constraints

这些字段只记录用户 / 项目明确提出的视觉机制、runtime、资产和禁用项；没有明确要求时不要由主 agent 代选低层实现。

- Requested visual mechanisms：`None`，或如 `SVG path drawing` / `3D camera flight` / `Lottie logo reveal`
- Required runtimes：`None`，或用户明确要求的 `gsap` / `animejs` / `waapi` / `css-animations` / `lottie` / `three` / `typegpu`
- Preferred runtimes：`None`，或非强制偏好
- Forbidden runtimes or effects：`None`，或明确禁用项
- Available animation assets：`None`，或本地 `.json` / `.lottie` / `.glb` / `.gltf` / shader 等实际路径
- Reason：用户要求、已有资产、品牌限制或渲染环境限制；没有则写 `None`

视觉机制描述“想看到什么”，runtime 描述“必须 / 希望怎样实现”，asset 描述“当前实际有什么”。若没有 required runtime，HyperFrames sub-agent 必须先按 R18 和 `references/animation-routing.md` 选择语义机制，再选择最小合适 runtime。Lottie / dotLottie preference 没有本地动画资产时不得伪装满足；Three.js / TypeGPU 必须由真实 depth / shader / GPU 需求和渲染环境支持证明。required runtime 与 R18、可用资产或渲染环境不兼容时，视为 handoff conflict：sub-agent 必须在 authoring 前停止并反馈主 agent，不得静默忽略 requirement 或违反 R18。Tailwind 只可作为静态 layout / style utility 记录，不属于 animation runtime。以上字段只能补充项目偏好，不得覆盖 `references/composition-rules.md`。

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
