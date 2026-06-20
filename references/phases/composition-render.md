### Phase 8 — 委派 HyperFrames Composition + Render

从这一步开始，composition 交由一个使用 `hyperframes` 与 `hyperframes-cli` skills 的 coding sub-agent 负责执行；动画 / 视觉效果可按项目需要使用 `gsap`、`animejs`、`waapi`、`css-animations`、`lottie`、`three` 或 `typegpu` 等 skills。Tailwind 只作为静态布局 / 样式支持，不是 animation/effect adapter。`topic-to-video` 主 agent 只负责准备上游资源、写 `composition-handoff.md`、物化固定 rules / stage protocol / design references、调用 sub-agent，并按 stage protocol 执行 sanity-check / Visual QA / feedback loop。

#### 8.1 — 写 `composition-handoff.md`

从 `references/composition-handoff-template.md` 出发，写出 `{work_dir}/{topic_name}/composition-handoff.md`，填入项目 metadata、实际输入路径、来自 Phase 1 的 style hint，以及从用户输入 / follow-up feedback / `style-prompt.md` 提取的 `User-derived Customized Rules`。Customized rules 必须可执行，不能只写抽象审美词。

同时把固定 references 复制到项目工作区，供 sub-agent 从磁盘读取本地副本：

- 必需：`references/composition-rules.md` → `{work_dir}/{topic_name}/references/composition-rules.md`
- 必需：`references/composition-stage-protocol.md` → `{work_dir}/{topic_name}/references/composition-stage-protocol.md`
- 如 handoff 指定 design route：`references/design-<theme>.md` → `{work_dir}/{topic_name}/references/design-<theme>.md`

`composition-handoff.md` 只记录项目变量、实际输入路径、style hint、animation / effect preference、customized rules、conflict notes 和 project-specific overrides；固定输入解释与 layout rules 来自 `references/composition-rules.md`，stage 执行协议来自 `references/composition-stage-protocol.md`，不得复制 / 摘要 / 覆盖。

Legacy fallback：旧项目若只有 `{work_dir}/{topic_name}/composition-brief.md`，主 agent 必须先把它迁移 / 归一化为 `composition-handoff.md`，再调用 sub-agent；sub-agent 仍统一读取 `composition-handoff.md`。

#### 8.2 — 调用一个 coding sub-agent

如果用户 query 指定了 coding agent / 委派目标，优先使用该目标；否则使用当前客户端 / runtime 原生的 sub-agent 或委派工具。prompt 要简短，且应让 sub-agent 自己从磁盘读 `composition-handoff.md`、`references/composition-rules.md`、`references/composition-stage-protocol.md` 和指定的 `references/design-<theme>.md`。

Prompt 示例：

```text
读取当前工作区的以下文件：
- composition-handoff.md
- references/composition-rules.md
- references/composition-stage-protocol.md
- handoff 指定的 references/design-<theme>.md（如有）

如果必需文件缺失，停止并反馈主 agent。

使用 hyperframes 和 hyperframes-cli skills 完成 scene 切分、素材映射、
composition authoring、HTML/CSS、pre-render self-audit、
lint/inspect、HTML-to-video render。

Animation / effect skill 选择：
- 如果 handoff 或用户明确指定 skill，优先使用该 skill；
- 否则选择最小合适实现：css-animations / waapi 用于简单 DOM motion，gsap 用于 timeline/tween-heavy choreography，animejs 用于 Anime.js-specific 实现；
- lottie 用于 Lottie / dotLottie 资产，three 用于 Three.js / WebGL scene 或 camera motion，typegpu 用于 WebGPU / WGSL shader / particle / liquid effects；
- tailwind 只用于静态 layout / style utility，不负责 render-critical motion timing；
- 只加载实际需要的 skill docs；
- 在 composition/DESIGN.md 记录选择的 skill(s) 和原因。

严格遵守 references/composition-rules.md：
- Scope and Required References
严格按 references/composition-rules.md 的 `visual_role × orientation` routing 选择布局；portrait / vertical 中不得把 landscape horizontal flow / side rail / multi-column grid 直接套到结构型 unit。

严格遵守 references/composition-stage-protocol.md：
- Phase 8.3 — Pre-render Self-Audit Rules
- Phase 8.4 — HTML-to-video Render Rules

完成后返回 final.mp4 路径、ffprobe duration 和文件大小。
```

如果环境里没有原生 sub-agent 工具，仅当 CLI fallback 能把上面那段 prompt 原样传过去、并让 coding sub-agent 自己去读 `composition-handoff.md`、`references/composition-rules.md`、`references/composition-stage-protocol.md` 与指定的 `references/design-<theme>.md` 时，才可以接受。

**不要**在主 agent 的会话里驱动 composition authoring 或手工 patch `composition/index.html`。

#### 8.3 — Pre-render self-audit

由 sub-agent 在首次 HTML-to-video render 前执行。要求见 `references/composition-stage-protocol.md` 的 **Phase 8.3 — Pre-render Self-Audit Rules**；结果必须写入 `composition/DESIGN.md`。

#### 8.4 — HTML-to-video render

按 `references/composition-stage-protocol.md` 的 **Phase 8.4 — HTML-to-video Render Rules** 执行。

#### 8.5 — Sanity check

sub-agent 返回后，主 agent 按 `references/composition-stage-protocol.md` 的 **Phase 8.5 — Sanity Check Rules** 验证 `composition/renders/final.mp4`。如果有异常，把症状反馈给 HyperFrames sub-agent；主 agent 不手工 patch HTML。

#### 8.6 — Post-render Visual QA

sanity-check 通过后，主 agent 按 `references/composition-stage-protocol.md` 的 **Phase 8.6 — Post-Render Visual QA Rules** 对 final.mp4 跑视觉 QA，并生成 `composition/qa-report.json` / `composition/qa-history.md`。

#### 8.7 — QA feedback loop

按 `references/composition-stage-protocol.md` 的 **Phase 8.7 — QA Feedback Loop** 决定进入 Phase 9、反馈 sub-agent 限定范围重渲，或触发止损交还用户。

规则与 QA 覆盖关系见 `references/composition-stage-protocol.md` 的 **Rule Coverage Matrix**。
