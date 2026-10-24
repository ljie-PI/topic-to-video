# 组件：caption-bar（底部字幕条）

讲解模式布局底部的深色条，72px 高，和顶部导航栏对称。条里显示单行字幕：左对齐，36px，同一时间只显示一句。人物坐在这条深色条上。

**组件本身没有任何具体内容**：字幕都在拼视频时传入；配色和字体全部来自设计主题的变量，组件里没有写死的色值和字体名。

## 文件

- `assets/components/caption-bar/caption-bar.html`

## 依赖（全部来自设计主题，视频的 `index.html` 必须提供）

| 变量 | 用在哪里 |
|---|---|
| `--c-chrome` | 条的底色（和导航栏同色，上下对称） |
| `--c-chrome-ink` | 字幕文字 |
| `--font-sans` | 字体栈，对应的 `@font-face` 也写在 `index.html` |

组件里没有兜底色：缺少哪个变量，对应的部分就不显示。

## 安装

1. 把 `assets/components/caption-bar/caption-bar.html` 复制到视频工程的 `compositions/caption-bar.html`。
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

## 数据（`window.VIDEO.captions`）

```js
captions: [
  { start: 0.033, end: 1.3, text: "GitHub 本周热榜" },
  { start: 1.467, end: 3.133, text: "排在榜首的是 artcraft，" },
  …
]
```

- 时间是视频时间（秒），一般直接取配音的逐句时间。
- 一句话在 `start` 出现，最早不早于 0.15 秒；在 `end + 0.1` 秒或者下一句开始时消失，取较早的那个。
- 入场 0.18 秒（上移 8px 淡入），出场 0.12 秒。
- 一句话比文字区宽时自动缩小字号，最小 28px，不换行。

## 限制

- 字幕元素由脚本按数据生成，所以在 Studio 里不能直接点选单句修改。要改字幕，改 `video-data.js`。
