# Pattern：list-grid（列表 / 功能网格 / 指标条）

并列的功能点、卖点、限制、takeaways，以及多个轻量指标（数据块 / 指标条）。本文件是建议，不是规则。

## 适用场景和触发信号

- 旁白有多个并列点、功能点、限制或 takeaway，每项只有 item + 一行 detail → 列表。
- 每项有独立标题 + benefit + proof → 功能网格。
- 旁白包含多个数字、比例、增长、成本、时长、性能分数 → 数据块 / 指标条；单个冲击性数字用 `patterns/info/big-number.md`。
- 屏幕文本单元 `visual_role = "list"` / `"feature_grid"` / `"data_block"` / `"metric_strip"`。

## 区域尺寸建议

- 每项保持短 label + 一行 detail；卡片 / 条目宽度建议不小于内容区宽度的 1/4（2 列时）或 1/5（grid）。
- 条目数：横屏 list / grid 通常 2–4 项；竖屏纵向卡片或最多 2 列；更多条目建议轮换或拆 scene。

## 横屏摆法

- list：横向 rail 或 2 列短行。
- feature grid：2×2 或 1×4 网格。
- 指标条：横向一排 2–4 个 compact 卡片。

## 竖屏摆法

- 纵向卡片或最多 2 列；过密时轮换次要条目到后续时间点。
- 指标 / 数据块最多 2 列；不靠缩字号塞指标。

## 动效候选与应避免

候选：waterfall / grid assemble、ordered reveal（按旁白顺序逐条出现）、focus cycle、nudge curve、item status change；指标条用 staggered metric reveal、stat bars / fills。

避免：所有条目在 scene 开头一次全亮；把数据只做成普通文字 fade-in。

## 用色

- 通用：item label 用 `--c-ink` / `--c-ink2`；bullet / index 只在有语义时用 `--c-focus` 或状态色。
- 各主题的具体覆盖写法已从主题文档迁到本 pattern：

| 主题 | 列表 / 指标用色 |
| --- | --- |
| default | item label 用 `ink` / `ink2`；bullet / index 只在有语义时用 `focus` 或 status color。 |
| dawn | item label Primary；bullet / index 用 Foam / Rose / Pine 按语义区分；detail 用 Primary 或大号 Secondary。 |
| moon | item label Primary；bullet / index 按语义用 Iris / Foam / Gold / Love；detail 用 Secondary。 |
| github | item label Primary；bullet / icon 按语义用 Blue / Success / Attention / Danger；detail 用 Secondary。 |
| producthunt | feature icon 若承载信息用 `#C8392F` / 蓝 / `#046B50` 按语义；item label Primary，detail Secondary。 |

## 已有实现

尚无。
