# Pattern：comparison-matrix（对比矩阵 / 优缺点）

竞品对比、before / after、方法对比，以及单一主体的正反两面（pros / cons）。本文件是建议，不是规则。

## 适用场景和触发信号

- 旁白出现「相比、对比、before / after、旧方案 / 新方案、优缺点、取舍、vs」→ 对比矩阵。
- 旁白是「优点 / 缺点、利弊、该做 / 不该做、推荐 / 避免」，针对单一主体的正反两面 → 优缺点。
- 屏幕文本单元 `visual_role = "comparison_matrix"` / `"pros_cons"`；典型字段是维度、选项、差异、positives、negatives。

## 区域尺寸建议

- 维度数以旁白实际讨论的为准，3–5 个维度最易读；维度多时优先删次要维度。
- 每个单元格放得下短语；放不下时缩短文案，不缩字号。

## 横屏摆法

- side-by-side matrix / 双列对比：左右两列共享同一组维度行，差异点高亮。
- 优缺点用双列（正 / 反）或上下两组，配短 badge。

## 竖屏摆法

- 上下分组或分步对比：先讲 A 再讲 B，或按维度逐个对比。
- 不压进窄列；两列在竖屏里各自太窄时改为分时。

## 动效候选与应避免

候选：mirrored reveal（两侧对称入场）、shared-axis comparison（共享轴同步推进）、shared element / FLIP、card morph、split tilt。

避免：两侧无因果的相反方向乱飞；整列铺 accent 底色造成阵营感。

## 用色

- 通用：中性维度用中性灰（`--c-ink2`）；优劣或风险使用 `--c-positive` / `--c-danger` 等真实语义色；不给整列铺满 accent。
- 各主题只写和通用写法不同的地方：

| 主题 | 对比矩阵用色 |
| --- | --- |
| default | 无特殊覆盖。 |
| github | 需要提醒但不算风险的格子用 `--c-warning`。 |
| producthunt | 推荐 / maker 适配用 `--c-positive`；注册 / info 维度用 `--c-info`；限制用中性小标签加 ⚠，不用 `--c-danger` 铺色。 |

## 已有实现

尚无。
