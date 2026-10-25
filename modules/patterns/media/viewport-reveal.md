# Pattern：viewport-reveal（视口揭示）

素材比例极端（超长、超宽、超高），完整放不下也缩不得，用一个沿长轴移动的视口逐步展示， traversal 本身就是这个 scene 的主要呈现。本文件是建议，不是规则。

## 适用场景和触发信号

- 单个 tall / ultra-tall / ultra-wide 素材，完整适配后不可读，但沿长轴或重点区域阅读是合理的呈现方式。
- 有素材的重点区域证据（catalog 里的 `focal_region`、start / mid / end 关键区域说明或 avoid-region）；旁白的讲解顺序正好沿长轴推进。
- 场景规划里 `layout_role = "viewport_reveal"`，或 media-first 遇到极端比例素材时改选本 pattern。

## 区域尺寸建议

- 视口按素材的重点区域定尺寸：建议视口的短边不小于内容区对应边的 1/2，窗口内的一切（含叠上去的文字）保持可读。
- 内容区参考：`layouts/stage.md` 主展示区 1728×764、`layouts/presenter.md` 主展示区 1048×788、竖屏 `layouts/portrait.md` 940×1240 / 940×880。
- 视口之外建议配一个外置信息区（文本列、callout 列），与 reveal 的 start / mid / end 关键区域对应。

## 横屏摆法

- 竖长素材：左侧或居中放大视口，右侧外置信息列；视口沿纵向 pan。
- 超宽素材：横向视口沿长轴 pan，或改用 `patterns/media/band.md`（能形成足够高的信息带时）。
- 单个 reveal 帧只要求当前窗口清晰、没有意外裁掉关键结构；start / mid / end 或证明序列合起来覆盖所有必要结构。

## 竖屏摆法

- 横图：横向 reveal，宽度撑满内容区，高度按可读性定。
- 竖图：宽度驱动，纵向 reveal 沿长轴覆盖重点。
- 文本列规划 3–4 个信息单元、每个带 detail / value，填满列宽列高，不只放标题加短标签；单元对应 reveal 的关键区域。

## 动效候选与应避免

候选：沿素材长轴 pan / scroll，跟随旁白到达重点；scrub 读数；marker 沿路径移动指示当前位置。

避免：视口内 slide 后又缩回导致重点一闪而过；只扫过素材的一部分却声称讲完了整张图；用 3D 倾斜或过小的缩放降低可读性。

## 用色

- 外观全部来自所选主题的 token；视口边框 / 当前位置 marker 可用 `--c-focus` 或 `--c-border`。
- 外置信息区按 `patterns/info/` 对应信息形态的建议用色。
- 本 pattern 没有按 visual_role 的特殊覆盖。

## 已有实现

尚无。
