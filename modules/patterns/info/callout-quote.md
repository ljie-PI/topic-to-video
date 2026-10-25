# Pattern：callout-quote（要点标注 / 引述）

关键结论、风险、反常识、术语解释、问答，以及用户评价、作者原话、论文结论的引述。本文件是建议，不是规则。

## 适用场景和触发信号

- 旁白是关键判断、风险、反常识、结论 → callout。
- 旁白引用用户评价、作者原话、论文结论、tagline 或明确引文 → quote。
- 旁白出现「所谓、指的是、定义为、即、名词解释、概念」→ 术语解释。
- 旁白是「问题 → 回答」、FAQ、常见疑问、Q&A → 问答。
- 屏幕文本单元 `visual_role = "callout"` / `"quote"` / `"definition"` / `"qa"`。

## 区域尺寸建议

- callout / quote 以一条短信息为单位：一句话结论 + 一句理由或出处；过长时拆成多条。
- 引述保留原文措辞，出处（作者 / 论文 / 产品名）用小字跟在下面；不显示原始 URL。

## 横屏摆法

- 外置 rail / band：素材 scene 的 callout 放在素材外侧的信息区，不压素材关键内容。
- 纯文字 scene 的 callout 可居中或偏侧，用 card 底或语义色左线区分层级。

## 竖屏摆法

- 素材外纵向堆叠或一次一个 callout；避免窄 side rail。
- 问答用上下堆叠：Q 在上、A 在下。

## 动效候选与应避免

候选：line / word reveal（引述逐行 / 逐词出现）、fixed-anchor cycle、focus-blur resolve、marker draw / connector draw（配合素材标注时）。

避免：callout 覆盖素材关键区域；长段文字逐字符出现拖慢可读性；多个 callout 同时抢占焦点。

## 用色

- 通用：`--c-card` 或 `--c-focus-tint` 只在必要时做短信息区底；正文保持 `--c-ink` / `--c-ink2`；风险 / 结论类 callout 用真实语义色左线。
- 各主题只写和通用写法不同的地方：

| 主题 | callout / quote 用色 |
| --- | --- |
| default | 无特殊覆盖。 |
| github | callout 用 `--c-card` 底 + 2px 边 + 语义色左线（`--c-info` / `--c-warning` / `--c-danger` / `--c-positive`）；definition 用 `--c-info` 左线；QA 的 Q 用 `--c-focus`，A 用 `--c-ink`。 |
| producthunt | 主推 callout 用 `--c-focus-tint` 底 + `--c-focus` 左线；注册 / info 用 `--c-info` 左线；maker / 已认证用 `--c-positive-tint` 底；QA 的 Q 用 `--c-info`，A 用 `--c-ink`。 |

引述（quote）三个主题写法相同：正文用 `--c-ink`，引号和来源前的标记用 `--c-focus`，来源文字用 `--c-ink2`。producthunt 的用户评价亮点可以放进主推 callout。

## 已有实现

尚无。
