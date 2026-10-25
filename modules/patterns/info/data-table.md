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

- 通用：focal series / 高亮单元格用 `--c-focus`；辅助内容用暖中性色；语义内容必须表达真实数据语义（涨跌、风险用对应语义色）。
- 各主题的具体覆盖写法已从主题文档迁到本 pattern：

| 主题 | 表格用色 |
| --- | --- |
| default | focal series 用 `focus`；辅助 series 用暖中性色；语义 series 必须表达相应数据语义。 |
| dawn | 表格正文 Primary；表头 Secondary 大号；highlight cell 用 Pine / Love / Foam 线，Gold 只做非唯一辅助点；series 用 Foam / Pine / Iris。 |
| moon | 表格正文 Secondary；highlight cell 用 Gold 描边；chart 主线 Foam，secondary series Iris / Rose，danger series Love。 |
| github | 表格正文 Primary / Secondary；highlight cell 用 callout tint；series 用 Blue / Success / Attention / Danger / Done / Teal。 |
| producthunt | 表格正文 Primary / Secondary；highlight cell 用 callout tint；信息性橙色 series 用 `#C8392F`，主橙只作辅助 marker。 |

## 已有实现

尚无。
