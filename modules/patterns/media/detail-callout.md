# Pattern：detail-callout（局部放大 + 外置标注）

保留来源素材全貌，用一个局部窗口或标记指出重点区域，解释文字放在素材外面。本文件是建议，不是规则。

## 适用场景和触发信号

- 单个素材，旁白明确在解释它的某个局部细节，且素材的重点区域有证据支持（catalog 的 `focal_region`、avoid-region 或可验证的关键区域）。
- 旁白一次只讲一个重点；多个局部建议拆成相邻的 `patterns/media/continuation.md` scene，一次讲一个。
- 场景规划里 `layout_role = "detail_callout"`，或素材是图表 / figure 且旁白引用其中某个数据点、模块。

## 区域尺寸建议

- 局部窗口要大到能看清所指内容：建议窗口不小于内容区短边的 1/3。
- 外置 callout 列与素材并排时，callout 区宽度建议占内容区的 1/4–1/3，每条 callout 一到两行。
- callout 不压素材关键内容；局部窗口的裁切不意外切掉结构（例如坐标轴、图例）。

## 横屏摆法

- 素材在左或居中保持全貌，关键区域加框 / marker；右侧或下方外置信息解释这个重点。
- 讲多个重点时按旁白顺序逐个加 marker，一次一个。

## 竖屏摆法

- 局部窗口 / 素材 slab 在上，一次一个 callout 在下，纵向堆叠。
- 避免窄 side rail：竖屏的 callout 上下排列比左右排列更易读。

## 动效候选与应避免

候选：focal shift（焦点移动到重点区域）+ 一次一个外置 callout 出现；marker draw、connector draw、rack focus。

避免：callout 覆盖素材关键区域；多个 marker 同时亮起分不清主次；用作者临时标记代替素材本身的关键区域证据。

## 用色

- 标注一律放在素材外置信息区；pin / marker 可用 `--c-focus` 或真实状态色，说明文字保持 `--c-ink` / `--c-ink2`。
- 各主题只写和通用写法不同的地方：

| 主题 | 标注用色 |
| --- | --- |
| default | 无特殊覆盖。 |
| github | pin / 边框按语义用 `--c-focus` / `--c-warning` / `--c-danger`。 |
| producthunt | pin 用 `--c-focus` 或 `--c-info`；`--c-highlight` 只作非唯一的外形点缀。 |

## 已有实现

尚无。
