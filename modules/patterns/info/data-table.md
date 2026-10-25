# Pattern：data-table（表格）

成本表、硬件表、benchmark 表、pricing 表等结构化多行多列内容。本文件是建议，不是规则。

## 适用场景和触发信号

- 旁白引用一张表格、pricing、benchmark table、hardware matrix、cost table。
- 屏幕文本单元 `visual_role = "data_table"`；典型字段是 columns、rows、highlighted cells、summary。
- 素材本身是表格图片时，保留来源表格，配外置结论 callout（见 `patterns/media/detail-callout.md`）。

## 区域尺寸建议

- small（≤3 行、≤3 列、单元格内容短）：紧凑表格直接放。
- medium（4–8 行或 4–5 列）：完整表格 + 高亮行 / 单元格 + 一句 summary。
- large（>8 行或 >5 列）：建议 summarize / 分页 / 拆 scene，只保留 primary rows / columns；只有旁白明确逐个讨论多个数值维度时才拆成多个 `chart` 单元。

## 横屏摆法

- 表格为主体，右侧或下方配 summary rail / highlights；讲到某一行时高亮。
- 列太多时优先删次要列，不缩字号。

## 竖屏摆法

- small 可放紧凑表格或 mini-table；medium 转行卡 / 分页；large 只保留 primary rows / columns，或分页维度，或拆 scene。
- 避免在窄列里硬塞多列表格。

## 动效候选与应避免

候选：行 / 列逐行 reveal、primary-row highlight、分页切换；配 shared-axis 状态变化、detail zoom。

避免：大表整体缩小后逐字淡入；为动画牺牲可读性。

## 用色

- 通用：focal series / 高亮单元格用 `--c-focus`；辅助文字用 `--c-ink2`（`--c-muted` 只用于 34px 以上的弱化数字）；语义内容表达真实数据语义（涨跌、风险用对应语义色）。
- 各主题只写和通用写法不同的地方：

| 主题 | 表格用色 |
| --- | --- |
| default | 无特殊覆盖。 |
| github | 涨跌用 `--c-positive` / `--c-danger`；高亮单元格用 `--c-focus-tint` 底。 |
| producthunt | 高亮单元格用 `--c-focus-tint` 底；upvote 列的数字用 `--c-ink`，前面的三角用 `--c-highlight`。 |

## 已有实现

尚无。
