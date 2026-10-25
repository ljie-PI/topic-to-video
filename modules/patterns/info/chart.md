# Pattern：chart（图表）

趋势、分布、数值对比、benchmark 曲线、占比。本文件是建议，不是规则。

## 适用场景和触发信号

- 旁白描述趋势、benchmark curve、成本对比、速度对比、占比、分布。
- 屏幕文本单元 `visual_role = "chart"`；典型字段是 chart_type、series、axis labels、highlighted points、summary。
- 旁白分别讨论一张大表里的多个独立数值维度时，可拆成多个 chart 单元逐个讲。
- 只有现成的 `chart` 单元或表格数据明确可 chart（有 numeric series / 高亮维度）时才画 chart；没有数据不凭空发明。

## 区域尺寸建议

- 单 chart 是常态：坐标轴标签、刻度、图例都要可读，宁可少画一条 series。
- 2–3 个 small multiples 是上限；更多就分页或拆 scene。
- 竖屏 chart 的宽度受内容区限制，高度建议占内容区的 1/2 以上，横向滚动条不如分页。

## 横屏摆法

- 单 chart + summary rail：图在左，结论在右；或 chart 居中，下方一行 summary。
- scrub 型图表（随旁白推进读数）适合宽幅横屏。

## 竖屏摆法

- 单 chart 纵向拉长，避免 3 个以上小图挤一屏。
- 多 series 时突出主 series，其余降透明度，必要时拆 scene。

## 动效候选与应避免

候选：SVG / path draw（曲线生长）、bar / area build（柱 / 面积逐段建立）、chart scrub readout（读数随旁白更新）、marker travel（标记点沿曲线移动）。

避免：图表整张一次淡入且没有数据推进；动画完成后所有 series 同等亮度没有主次。

## 用色

- 通用：focal series 用 `--c-focus`；辅助 series 用暖中性色；语义 series 表达真实数据语义。
- 各主题的具体覆盖写法已从主题文档迁到本 pattern：

| 主题 | 图表用色 |
| --- | --- |
| default | focal series 用 `focus`；辅助 series 用暖中性色；语义 series 表达相应数据语义。 |
| dawn | series 用 Foam / Pine / Iris；highlight 用 Pine / Love / Foam 线，Gold 只做非唯一辅助点。 |
| moon | 主线 Foam，secondary series Iris / Rose，danger series Love；highlight cell 用 Gold 描边。 |
| github | series 用 Blue / Success / Attention / Danger / Done / Teal；highlight cell 用 callout tint。 |
| producthunt | 信息性橙色 series 用 `#C8392F`，主橙只作辅助 marker；highlight cell 用 callout tint。 |

## 已有实现

尚无。
