# 动态模块：chart-build（图表与核心指标动态构建）

**用于演绎柱状对比、趋势折线面积构建，或单点冲击性大数字指标（hero metric）。**

1. 舞台采用 `1:1` 像素 `viewBox`、半透明 `--c-card` 面板与 `1px` 精细坐标轴/辅助网格线，透出底层 `#ground` 纸纹肌理。
2. 支持三种 `variant`：
   - `"bar"`（默认）：根据容器朝向与标签长度自动选用纵向柱或横向条，柱体随 `at` 渐进生长，等宽数字（`tabular-nums`）同步滚动至目标值；
   - `"line"`：`2px` 趋势曲线通过 `pathLength="1"` 渐进描边，配半透明渐变面积裁切揭示、数据点圆环锚点与右上角实时跟随读数；
   - `"metric"`：单点大数字冲击卡（对应 `patterns/info/big-number.md`），超大号等宽数字滚动计数、进度量尺生长与结论说明同框适配。
3. 标题、分类名、刻度标签与底部结论条均经确定性字宽模型测量折行或缩字号（阅读字 `>= 26px`、刻度辅助字 `>= 22px` UI），不溢出承载框。

## 文件

- `motions/chart-build/chart-build.md`：本文档。
- `motions/chart-build/chart-build.html`：静态标记和样式。
- `motions/chart-build/chart-build.mjs`：导出 `init`（接口见 `modules.md` 的「模块初始化接口」）。
- `motions/motion-utils.mjs`：共用确定性文本测量、折行与 1:1 舞台工具（一同复制到工程 `compositions/`）。

## 依赖（来自设计主题，视频的 `index.html` 必须提供）

| 变量 | 用在哪里 |
|---|---|
| `--c-card` / `--c-surface` | 半透明图表底板、常规对比柱底、结论条底 |
| `--c-border` | 舞台外框（`1.5px`）、柱体边框（`1.35px`）、坐标轴与辅助虚线（`1px`） |
| `--c-ink` / `--c-ink2` | 标题、分类标签、常规数值 / 次要说明与坐标刻度 |
| `--c-focus` / `--c-focus-tint` | 主趋势线、渐变面积、强调柱体与核心读数 |
| `--c-positive` / `--c-positive-solid` / `--c-positive-tint` | 正向增长标记或 `emphasis: "positive"` 数据项 |
| `--c-highlight` | 关键数据点外圈点缀 |
| `--font-sans` / `--font-mono` | 文本与等宽数字字体 |
| `--motion-enter-duration` / `--motion-easing` | 默认动画时长与缓动 |

## 安装与挂载

1. 把 `motions/chart-build/chart-build.html`、`motions/chart-build/chart-build.mjs` 和 `motions/motion-utils.mjs` 一起复制到视频工程的 `compositions/`。
2. 在当前视觉 scene 的目标 content 区域挂载：
   - `data-composition-id="chart-build"`，`data-composition-src="compositions/chart-build.html"`；
   - `data-start` 为场景起点，`data-duration` 为场景时长。
3. 在工程 adapter 中调用 `init(root, { params, data, duration, gsap })`，按局部秒驱动返回的暂停 `timeline`。

## 参数（`init` 的 `params`）

| 参数 | 默认 | 说明 |
|---|---|---|
| `x`, `y` | `0, 0` | 舞台相对 `#root` 左上角的像素偏移 |
| `width`, `height` | 宿主像素宽高（回退 `1048, 788`） | 舞台像素尺寸，SVG 自动设置 `viewBox="0 0 width height"` |
| `variant` | `"bar"` | `"bar"`（柱状/条形对比）、`"line"`（折线面积构建）或 `"metric"`（大数字指标卡） |
| `orientation` | `"auto"` | 仅 `"bar"` 有效：`"auto"`（竖屏、多条目或长标签自动改横向条）、`"vertical"` 或 `"horizontal"` |
| `title` | `""` | 图表顶部标题（`>= 30px`） |
| `unit` | `""` | 数值单位后缀（如 `"ms"`、`"%"`、`"×"`） |
| `prefix` | `""` | 数值前缀（如 `"+"`、`"$"`） |
| `data` | `"chartBuild"` | 工程数据（`window.VIDEO`）中对应的键名 |

## 数据（`init` 的 `data`，工程里通常来自 `window.VIDEO.chartBuild`）

```js
// variant: "bar" 或 "line"（items 与 points 均可）
chartBuild: {
  items: [
    { label: "基线方案", value: 42, at: 0.2 },
    { label: "缓存优化", value: 78, at: 1.0 },
    { label: "零拷贝流水线", value: 136, displayValue: "136 req/s", at: 1.9, emphasis: true },
  ],
  summary: "吞吐量较基线提升 3.2 倍，尾延迟保持稳定",
  summaryAt: 2.6,
}

// variant: "metric"
heroMetric: {
  label: "端到端编码吞吐提升",
  value: 3.2,
  displayValue: "3.2",
  detail: "1920×1080 30fps H.264 实测均值",
  summary: "半透明纸纹与 1px 辅助网格无断线",
  at: 0.3,
}
```
