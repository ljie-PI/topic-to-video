### Phase 8 — 委派 HyperFrames Composition + Render

从这一步开始，composition 由一个使用 `hyperframes` 与 `hyperframes-cli` skills 的 coding sub-agent 拥有。`topic-to-video` 主 agent 只负责准备上游资源、写 `composition-handoff.md`、物化固定 rules / design references、调用 sub-agent，并按 rules 执行 sanity-check / Visual QA / feedback loop。

#### 8.1 — 写 `composition-handoff.md`

从 `references/composition-handoff-template.md` 出发，写出 `{work_dir}/{topic_name}/composition-handoff.md`，填入项目 metadata、实际输入路径、来自 Phase 1 的 style hint，以及从用户输入 / follow-up feedback / `style-prompt.md` 提取的 `User-derived Customized Rules`。Customized rules 必须可执行，不能只写抽象审美词。

同时把固定 references 复制到项目工作区，供 sub-agent 从磁盘读取本地副本：

- 必需：`references/composition-rules.md` → `{work_dir}/{topic_name}/references/composition-rules.md`
- 如 handoff 指定 design route：`references/design-<theme>.md` → `{work_dir}/{topic_name}/references/design-<theme>.md`

`composition-handoff.md` 只记录项目变量、实际输入路径、style hint、customized rules 和 conflict notes；固定规则来自 `references/composition-rules.md`，不得复制 / 摘要 / 覆盖。

Legacy fallback：旧项目若已存在 `{work_dir}/{topic_name}/composition-brief.md`，可以作为 legacy handoff 继续读取；新项目一律生成 `composition-handoff.md`。

#### 8.2 — 调用一个 coding sub-agent

如果用户 query 指定了 coding agent / 委派目标，优先使用该目标；否则使用当前客户端 / runtime 原生的 sub-agent 或委派工具。prompt 要简短，且应让 sub-agent 自己从磁盘读 `composition-handoff.md`、`references/composition-rules.md` 和指定的 `references/design-<theme>.md`。

Prompt 示例：

```text
读取当前工作区的以下文件：
- composition-handoff.md
- references/composition-rules.md
- handoff 指定的 references/design-<theme>.md（如有）

如果必需文件缺失，停止并反馈主 agent。

使用 hyperframes 和 hyperframes-cli skills 完成 composition authoring、
HTML/CSS/GSAP、pre-render self-audit、lint/inspect、HTML-to-video render。

严格遵守 references/composition-rules.md：
- Phase 8.2 — Sub-agent Execution Rules
- Phase 8.3 — Pre-render Self-Audit Rules
- Phase 8.4 — HTML-to-video Render Rules

完成后返回 final.mp4 路径、ffprobe duration 和文件大小。
```

如果环境里没有原生 sub-agent 工具，仅当 CLI fallback 能把上面那段 prompt 原样传过去、并让 coding sub-agent 自己去读 `composition-handoff.md`、`references/composition-rules.md` 与指定的 `references/design-<theme>.md` 时，才可以接受。

**不要**在主 agent 的会话里驱动 composition authoring 或手工 patch `composition/index.html`。

#### 8.3 — Pre-render self-audit

由 sub-agent 在首次 HTML-to-video render 前执行。要求见 `references/composition-rules.md` 的 **Phase 8.3 — Pre-render Self-Audit Rules**；结果必须写入 `composition/DESIGN.md`。

#### 8.4 — HTML-to-video render

这里的 render 指从 `composition/index.html` 渲染成 `composition/renders/final.mp4`，不是生成 HTML。要求见 `references/composition-rules.md` 的 **Phase 8.4 — HTML-to-video Render Rules**。

#### 8.5 — Sanity check

sub-agent 返回后，主 agent 按 `references/composition-rules.md` 的 **Phase 8.5 — Sanity Check Rules** 验证 `composition/renders/final.mp4`。如果有异常，把症状反馈给 HyperFrames sub-agent；主 agent 不手工 patch HTML。

#### 8.6 — Post-render Visual QA

sanity-check 通过后，主 agent 按 `references/composition-rules.md` 的 **Phase 8.6 — Post-Render Visual QA Rules** 对 final.mp4 跑视觉 QA，并生成 `composition/qa-report.json` / `composition/qa-history.md`。

#### 8.7 — QA feedback loop

按 `references/composition-rules.md` 的 **Phase 8.7 — QA Feedback Loop** 决定进入 Phase 9、反馈 sub-agent 限定范围重渲，或触发止损交还用户。

规则与 QA 覆盖关系见 `references/composition-rules.md` 的 **Phase 8.8 — QA Coverage Mapping**。
