# Pattern：viewport-reveal（视口揭示）

素材比例极端（超长、超宽、超高），完整放不下也缩不得，用一个沿长轴移动的视口逐步展示， traversal 本身就是这个 scene 的主要呈现。本文件是建议，不是规则。

## 适用场景和触发信号

- 单个 tall / ultra-tall / ultra-wide 素材，完整适配后不可读，但沿长轴或重点区域阅读是合理的呈现方式。
- 有素材的重点区域证据（catalog 里的 `focal_region`、start / mid / end 关键区域说明或 avoid-region）；旁白的讲解顺序正好沿长轴推进。
- `material-catalog.json` 中素材 `layout_affordance` 含 `"viewport_reveal"`，或 media-first 遇到极端比例素材时改选本 pattern。

## 区域尺寸建议

- 视口按素材的重点区域与当前 scene 内容区尺寸（见 `layouts/layouts.md` 或 `scene-config.json`）定大小：建议视口的短边不小于内容区对应边的 1/2，窗口内的一切（含叠上去的文字）保持可读。
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

网页 / 榜单：按 `capture.elements[].bbox` 定正文裁剪，以实际 PNG 宽高换算坐标；固定可读缩放，GSAP `ease: "none"` 沿长轴慢滚，条目间停约 1s。速度用展示像素 / 秒定义（如 65px/s），按真实旁白窗口调整位移；首尾停稳，运动与停顿全写入 timeline，确保任意 seek 可复现。保留相邻条目上下文，可加当前位置 marker。

避免：按 cue 逐条 zoom；真实滚动网页或二次录屏；只扫部分却声称讲完整图；3D 倾斜或整页微缩损害可读性。

## 用色

- 外观全部来自所选主题的 token；视口边框 / 当前位置 marker 可用 `--c-focus` 或 `--c-border`。
- 外置信息区按 `patterns/info/` 对应信息形态的建议用色。

## 已有实现

- 网页慢滚：裁剪容器 + 固定尺寸图片的 GSAP 位移，不用 `focus-callout` 的多停靠点 zoom。
- `motions/focus-callout/`：大图小焦点的单次推近 / 外置标注，见 `motions/focus-callout/focus-callout.md`。
