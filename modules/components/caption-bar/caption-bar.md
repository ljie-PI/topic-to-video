# 组件：caption-bar（底部字幕条）

常驻底部字幕与深色条组件。单布局默认模式（未传 `captionSegments`）对应横屏讲解底部的 72px 深色条与单行左对齐 36px 字幕；传入视觉 scene 数据 `captionSegments` 时，文字框位置/尺寸/字号/最大行数及底部深色条显隐高度（如竖屏讲解 144px 双行底条，或无主持人竖屏无底条居中双行字幕）均按当前 scene 的 layout 自动切换。

**组件本身没有任何具体内容**：字幕都在拼视频时传入；配色和字体全部来自设计主题的变量，组件里没有写死的色值和字体名。

## 文件

- `components/caption-bar/caption-bar.html`：静态标记和样式。
- `components/caption-bar/caption-bar.mjs`：导出 `init`（接口见 `modules.md` 的「模块初始化接口」）。

## 依赖（全部来自设计主题，视频的 `index.html` 必须提供）

| 变量 | 用在哪里 |
|---|---|
| `--c-chrome` | 条的底色（和导航栏同色，上下对称） |
| `--c-chrome-ink` | 有底部深色条时的字幕文字 |
| `--c-ink` | 无底部深色条场景（`caption_bar_rect: null`）直接在画布底色上显示时的字幕文字 |
| `--font-sans` | 字体栈，对应的 `@font-face` 也写在 `index.html` |

组件里没有兜底色：缺少哪个变量，对应的部分就不显示。

## 安装

1. 把 `components/caption-bar/caption-bar.html` 和 `caption-bar.mjs` 一起复制到视频工程的 `compositions/`。
2. 在根节点加挂载点：
   - `data-composition-id="caption-bar"`，`data-composition-src="compositions/caption-bar.html"`；
   - `data-start="0"`，时长为整片；
   - `data-track-kind="captions"`；
   - `style="z-index: 16"`。
3. 在工程里调 `init`：传入挂载参数和 `{ captions, captionSegments }` 数据，拿到暂停的 timeline 后按局部秒 seek。接线示例见 `modules.md` 的「模块初始化接口」。

## 参数（`init` 的 `params`）

| 参数 | 默认 | 说明 |
|---|---|---|
| `x` | 96 | 字幕文字区左边，单位 px |
| `width` | 1166 | 字幕文字区宽度，单位 px。默认值让右边界停在人物左边缘前 32px；人物位置变了要跟着改 |
| `y`, `height` | 1008, 72 | 深色条和文字区的位置和高度，单位 px |
| `fontSize` | 36 | 字号，单位 px |
| `bar` | `"on"` | 设为 `"off"` 时在初始化阶段永久移除 `#cb-bar`（全片无底条）。同片混用有底条与无底条场景（如 `portrait-presenter` 与 `portrait`）时保持默认 `"on"`，由 `captionSegments[].caption_bar_rect` 按场景切换显隐 |
| `data` | `"captions"` | 工程数据（`window.VIDEO`）里哪个键是字幕，adapter 取出后作为 `init` 的 `data.captions` |
| `layoutData` | `"captionSegments"` | 可选：哪个键是视觉 scene 字幕布局，adapter 取出后作为 `data.captionSegments`；有非空数组时启用 scene 模式 |

## 数据（`init` 的 `data.captions`，工程里通常来自 `window.VIDEO.captions`）

```js
captions: [
  { start: 0.033, end: 1.3, text: "GitHub 本周热榜" },
  { start: 1.467, end: 3.133, text: "排在榜首的是 artcraft，" },
  …
]
```

- 时间是视频秒（本组件常驻挂在 0 秒，即局部秒），直接取配音逐句时间。
- **单布局默认行为（未传 `captionSegments` 时）**：每句在 `max(start, 0.15)` 出现，在 `min(end + 0.1, 下一句.start)` 消失（且至少显示 0.3s）；入场 0.18s（上移 8px 淡入）、出场 0.12s；超宽时自动缩字号（最小 28px，不换行）。

## 视觉 scene 数据（`init` 的 `data.captionSegments`，工程里通常来自 `window.VIDEO.captionSegments`）

视觉 scene 模式直接使用 `subtitle-units.json` 的两个字段，禁重排时间或重算矩形：

```js
// subtitleUnits 是 composition/assets/subtitle-units.json 解析后的对象
window.VIDEO = {
  captions: subtitleUnits.units.map((unit) => ({
    start: unit.begin_s,       // begin_s → start，视频秒，原样复制
    end: unit.end_s,           // end_s → end，视频秒，原样复制
    text: unit.text,           // 原样复制
  })),
  // 有 caption_segments 时原样传入；省略此键则走单布局默认行为。
  captionSegments: subtitleUnits.caption_segments,
};
```

`caption_segments[]` 由 `align-narration.py --mode subtitles --scene-config composition/scene-config.json` 生成。每一项的字段及组件行为如下：

| 字段 | 来源 | 组件行为 |
|---|---|---|
| `begin_s`, `end_s` | 当前 layout 的有效显示区间 | 用 `[begin_s, end_s)` 判断区间；字幕跨过边界时在边界切换布局 |
| `caption_rect` | 该 layout 中 `id: "caption-text"` 的 `rect` | `x` → 容器 `left`，`y` → `top`，`width` / `height` → 容器宽高；缺省矩形字段才回退到挂载参数 |
| `caption_bar_rect` | 该 layout 中 `id: "caption-bar"` 的 `rect`（无该保留区时为 `null`） | 有矩形时定位并显示 `#cb-bar`（文字用 `--c-chrome-ink`）；为 `null` 时隐藏 `#cb-bar`（文字用 `--c-ink`；深底自由布局如需浅色文字加描边/遮罩，可在工程 `<head>` 写 `#caption-bar .cb-line span` 覆盖）。竖屏画布且 `max_lines > 1` 时居中，其余左对齐 |
| `caption.width_px` | 该 layout 的 `caption` | 没有 `caption_rect.width` 时作为容器宽度 |
| `caption.font_size_px` | 同上 | 当前区间的实际字号，**不再按文字宽度缩小** |
| `caption.max_lines` | 同上 | `1` 时 `white-space: nowrap`；大于 `1` 时允许正常换行，最大高度为 `max_lines × font_size_px × 1.15`，多余内容裁剪 |

scene 模式的显示边界是确定性的：

- 每句严格在 `[captions[].start, min(captions[].end, 下一句.start)]` 显示（无 0.15s 延迟、0.3s 下限或 0.1s 延后）；
- 对每个重叠的 `caption_segment`，在 `max(start, segment.begin_s)` 应用其 `caption_rect` 与 `caption`（正反向 seek 状态一致）；
- 保留随短字幕自动缩短的淡入 / 淡出；场景切换只改布局，不重挂组件。

## 限制

- 字幕元素由脚本按数据生成，所以在 Studio 里不能直接点选单句修改。要改字幕，改 `video-data.js`。
