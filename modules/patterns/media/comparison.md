# Pattern：comparison（多素材对比）

两个及以上素材按时间或同屏排列比较：同屏放得下且可读就并排，放不下就逐个 / 分组过。本文件是建议，不是规则。

## 适用场景和触发信号

- 恰好两个需要同等比较的素材，且同屏能满足可读性 → 同屏对比（pair）。
- 三个及以上素材，或两个素材同屏不可读 → 按时间逐个 / 分组比较（sequence）。
- 旁白出现「相比、对比、before / after、旧方案 / 新方案、vs」；场景规划里 `layout_role = "comparison_pair"` 或 `"comparison_sequence"`。

## 区域尺寸建议

- 同屏对比时两个素材保持统一高度或统一可读尺度，各自宽度等比；任何一个素材缩到不可读就改 sequence。
- sequence 一次只突出一个或少量一组素材；不默认三等分或小宫格。
- 同屏不可读时的优先处理：分时 → 拆 scene，而不是继续压小。

## 横屏摆法

- pair：左右并排最常见，共享同一基线；上下排列适合一高一矮的两张图。
- sequence：carousel / 分时轮换，必要时拆成多个 scene，每个 scene 用自己的主呈现（media-first、video-first 等）。

## 竖屏摆法

- pair：优先上下排列；左右窄列在竖屏里通常不可读。
- sequence：一次一个，纵向全幅展示单个素材。

## 动效候选与应避免

候选：mirrored reveal（两侧对称入场）、shared-axis 同步运动、同步 scrub、FLIP 位置交换；sequence 用分页、carousel、固定锚点轮换。

避免：两侧无因果关系的相反方向乱飞；两个素材保持不对等的可读权重；把两个素材压小硬塞同屏。

## 用色

- 外观全部来自所选主题的 token；两个对比侧建议共享同一套中性色，差异用 marker 或边框表达，不给某一侧铺大面积 accent。
- 各主题的具体覆盖写法已从主题文档迁到 `patterns/info/comparison-matrix.md`（其中的对比矩阵用色同样适用于素材对比）。

## 已有实现

尚无。
