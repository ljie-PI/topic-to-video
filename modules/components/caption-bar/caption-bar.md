# 组件：caption-bar（底部字幕条）

讲解模式布局底部的深色条，72px 高，和顶部导航栏对称。传统挂载时条里显示单行字幕：左对齐，36px，同一时间只显示一句；人物坐在这条深色条上。使用视觉 scene 数据时，字幕文字区的位置、尺寸、字号和最大行数按当前 scene 的 layout 切换。

**组件本身没有任何具体内容**：字幕都在拼视频时传入；配色和字体全部来自设计主题的变量，组件里没有写死的色值和字体名。

## 文件

- `components/caption-bar/caption-bar.html`

## 依赖（全部来自设计主题，视频的 `index.html` 必须提供）

| 变量 | 用在哪里 |
|---|---|
| `--c-chrome` | 条的底色（和导航栏同色，上下对称） |
| `--c-chrome-ink` | 字幕文字 |
| `--font-sans` | 字体栈，对应的 `@font-face` 也写在 `index.html` |

组件里没有兜底色：缺少哪个变量，对应的部分就不显示。

## 安装

1. 把 `components/caption-bar/caption-bar.html` 复制到视频工程的 `compositions/caption-bar.html`。
2. 在根节点加挂载点：
   - `data-composition-id="caption-bar"`，`data-composition-src="compositions/caption-bar.html"`；
   - `data-start="0"`，时长为整片；
   - `data-track-kind="captions"`；
   - `style="z-index: 16"`。

## 挂载参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `x` | 96 | 字幕文字区左边，单位 px |
| `width` | 1166 | 字幕文字区宽度，单位 px。默认值让右边界停在人物左边缘前 32px；人物位置变了要跟着改 |
| `y`, `height` | 1008, 72 | 深色条和文字区的位置和高度，单位 px |
| `fontSize` | 36 | 字号，单位 px |
| `bar` | `"on"` | 设为 `"off"` 时只显示文字，不画深色条 |
| `data` | `"captions"` | 从 `window.VIDEO` 的哪个键读字幕 |
| `layoutData` | `"captionSegments"` | 可选：从 `window.VIDEO` 的哪个键读视觉 scene 字幕布局；有非空数组时启用 scene 模式 |

## 数据（`window.VIDEO.captions`）

```js
captions: [
  { start: 0.033, end: 1.3, text: "GitHub 本周热榜" },
  { start: 1.467, end: 3.133, text: "排在榜首的是 artcraft，" },
  …
]
```

- 时间是视频时间（秒），一般直接取配音的逐句时间。
- 以下是没有 `captionSegments` 时的**传统兼容行为**：一句话在 `start` 出现，最早不早于 0.15 秒；在 `end + 0.1` 秒或者下一句开始时消失，取较早的那个，并至少显示 0.3 秒。
- 传统模式入场 0.18 秒（上移 8px 淡入），出场 0.12 秒。
- 传统模式下，一句话比文字区宽时自动缩小字号，最小 28px，不换行。

## 视觉 scene 数据（`window.VIDEO.captionSegments`）

视觉 scene 模式使用 `subtitle-units.json` 的两个字段，映射是固定的，不要重排时间、重新计算矩形或另写字幕规格：

```js
// subtitleUnits 是 composition/assets/subtitle-units.json 解析后的对象
window.VIDEO = {
  captions: subtitleUnits.units.map((unit) => ({
    start: unit.begin_s,       // begin_s → start，视频秒，原样复制
    end: unit.end_s,           // end_s → end，视频秒，原样复制
    text: unit.text,           // 原样复制
  })),
  // 有 caption_segments 时整个数组原样暴露；没有该字段时省略此键，走传统模式。
  captionSegments: subtitleUnits.caption_segments,
};
```

`caption_segments[]` 由 `align-narration.py --mode subtitles --scenes composition/scenes.json` 生成。每一项的字段及组件行为如下：

| 字段 | 来源 | 组件行为 |
|---|---|---|
| `begin_s`, `end_s` | 当前 layout 的有效显示区间 | 用 `[begin_s, end_s)` 判断区间；字幕跨过边界时在边界切换布局 |
| `caption_rect` | 该 layout JSON 中 `id: "caption-text"` 的 `rect` | `x` → 容器 `left`，`y` → `top`，`width` / `height` → 容器宽高；缺省矩形字段才回退到挂载参数 |
| `caption.width_px` | 该 layout JSON 的 `caption` | 没有 `caption_rect.width` 时作为容器宽度 |
| `caption.font_size_px` | 同上 | 当前区间的实际字号，**不再按文字宽度缩小** |
| `caption.max_lines` | 同上 | `1` 时 `white-space: nowrap`；大于 `1` 时允许正常换行，最大高度为 `max_lines × font_size_px × 1.15`，多余内容裁剪 |

scene 模式的显示边界是确定性的：

- 每句从 `captions[].start` 开始，不做传统的 0.15 秒延迟，也不保证最少 0.3 秒；
- 每句在 `min(captions[].end, 下一句.start)` 结束，不再追加 0.1 秒；
- 对每个与这句重叠的 `caption_segment`，在 `max(start, segment.begin_s)` 应用该段的 `caption_rect` 和 `caption`；向前或向后 seek 都得到同一状态；
- 保留淡入 / 淡出，但时长会随短字幕可用时长缩短。场景切换只改变字幕布局，不重挂组件。

## 限制

- 字幕元素由脚本按数据生成，所以在 Studio 里不能直接点选单句修改。要改字幕，改 `video-data.js`。
