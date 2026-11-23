# 动态模块：focus-callout（局部 zoom-in 推近放大与外沿引线标注）

**用于真实图片素材的大图小焦点单次 zoom-in 推近强调，或围绕目标区域外框做零遮挡引线标注（对应 `patterns/media/detail-callout.md`）。**

1. 舞台自动划分**主视口区**与**外置标注带**（横屏默认左图右标注列，竖屏默认上图下标注带，也可显式传入 `targetRect` 与 `stops[].side`），保证标注卡与引线始终位于视口外侧，**不遮挡主画面内部任何关键像素**。
2. 传入 `params.src` 时，模块在主视口内渲染带 `1.5px` `--c-border` 圆角框的图片，并按各停靠点 `stops[].crop` 在语音时刻 `at` 平滑推拉缩放至当前讲解区域；省略 `params.src` 时，可围绕 `data.targetRect` 绘制外沿锚点与引线。
3. 每条引线锚定在主视口对应侧的**外边框**上，以 `pathLength="1"`（`1.65px` `--c-focus`）折线生长连接外置标注卡；外置空间充足时多条标注纵向排布并切换主次焦点，空间紧凑时按时间顺序单卡交替展示，绝不重叠。

## 文件

- `motions/focus-callout/focus-callout.md`：本文档。
- `motions/focus-callout/focus-callout.html`：静态标记和样式。
- `motions/focus-callout/focus-callout.mjs`：导出 `init`（接口见 `modules.md` 的「模块初始化接口」）。
- `motions/motion-utils.mjs`：共用确定性文本测量、折行与 1:1 舞台工具（一同复制到工程 `compositions/`）。

## 依赖（来自设计主题，视频的 `index.html` 必须提供）

| 变量 | 用在哪里 |
|---|---|
| `--c-card` / `--c-surface` | 半透明视口衬底、外置标注卡底与编号徽标底 |
| `--c-border` | 视口外框（`1.5px`）、非当前标注卡细框（`1.3px`）与辅助底衬 |
| `--c-ink` / `--c-ink2` | 标注主标题（`>= 26px`）/ 补充细节（`>= 22px` UI） |
| `--c-focus` / `--c-focus-tint` | 当前激活停靠点的外沿锚点、引线与标注卡高亮边框/浅底 |
| `--c-done` | 已讲完停靠点的沉淀边框色 |
| `--font-sans` / `--font-mono` | 正文与停靠点序号字体 |
| `--motion-enter-duration` / `--motion-easing` | 默认入场与视口推拉缓动 |

## 安装与挂载

1. 把 `motions/focus-callout/focus-callout.html`、`motions/focus-callout/focus-callout.mjs` 和 `motions/motion-utils.mjs` 一起复制到视频工程的 `compositions/`。
2. 在当前视觉 scene 的目标 content 区域挂载：
   - `data-composition-id="focus-callout"`，`data-composition-src="compositions/focus-callout.html"`；
   - `data-start` 为场景起点，`data-duration` 为场景时长。
3. 在工程 adapter 中调用 `init(root, { params, data, duration, gsap })`，按局部秒驱动返回的暂停 `timeline`。

## 参数（`init` 的 `params`）

| 参数 | 默认 | 说明 |
|---|---|---|
| `x`, `y` | `0, 0` | 舞台相对 `#root` 左上角的像素偏移 |
| `width`, `height` | 宿主像素宽高（回退 `1048, 788`） | 舞台像素尺寸，SVG 自动设置 `viewBox="0 0 width height"` |
| `src` | `""` | 可选图片路径（相对工程根，如 `"assets/materials/arch.png"`）；留空时仅绘制外框与外沿引线标注 |
| `intrinsicWidth`, `intrinsicHeight` | 视口宽高 | 可选原图像素宽高，用于在字体/图片异步解码前即确定性计算 `contain` 与像素级 `crop` 变换 |
| `title` | `""` | 可选舞台顶部标题（`>= 30px`） |
| `side` | `"auto"` | 默认外置标注侧：`"auto"`（横屏 `"right"`、竖屏 `"bottom"`）、`"right"`、`"bottom"`、`"left"` 或 `"top"` |
| `data` | `"focusCallout"` | 工程数据（`window.VIDEO`）中对应的键名 |

## 数据（`init` 的 `data`，工程里通常来自 `window.VIDEO.focusCallout`）

```js
focusCallout: {
  // 可选：显式指定舞台内被标注的目标矩形（省略时自动按朝向分配主视口与外置标注带）
  // targetRect: { x: 24, y: 24, width: 620, height: 740 },
  stops: [
    {
      crop: { x: 0.0, y: 0.0, w: 1.0, h: 1.0 },
      anchor: { x: 0.82, y: 0.28 },
      label: "编码器输入分块",
      detail: "先看全局结构与输入特征切分",
      side: "right",
      at: 0.2,
    },
    {
      crop: { x: 0.30, y: 0.35, w: 0.65, h: 0.65 },
      anchor: { x: 0.9, y: 0.64 },
      label: "稀疏注意力路由核",
      detail: "视口推进聚焦关键算子，外沿引线同步切换",
      side: "right",
      at: 1.8,
    },
  ],
}
```

- `stops[].crop`：`0..1` 归一化矩形（或配 `intrinsicWidth` / `intrinsicHeight` 传像素坐标），省略时全图适配。细节推近只做一次、起止停稳，缩放比宜 ≤1.6；推近时长为 `--motion-enter-duration × 1.3`（需 ≥1.2s 时局部覆盖）。
- `stops[].anchor`：`0..1` 归一化锚点（或舞台像素坐标），自动投影到对应侧视口**外边框**作为引线起点，避免压入画面内部。
