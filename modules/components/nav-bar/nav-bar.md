# 组件：nav-bar（顶部导航栏）

讲解模式布局顶部的深色条，72px 高，占满宽度。从左到右依次是：
- 站点标志：一张图片，由参数传入；
- 页面路径：前半段是灰色，页面名是白色；
- 章节标签页。

**组件本身没有任何具体内容**：标志、路径、标签页都在拼视频时传入；配色和字体全部来自设计主题的变量，组件里没有写死的色值和字体名。

当前章节的标签是白字，下方有一条珊瑚色下划线。到了某个章节的开始时间，下划线滑到对应的标签下，所以它就是整支视频的进度条。

## 文件

- `components/nav-bar/nav-bar.html`

## 依赖（全部来自设计主题，视频的 `index.html` 必须提供）

| 变量 | 用在哪里 |
|---|---|
| `--c-chrome` | 条的底色 |
| `--c-chrome-ink` | 页面名、当前标签 |
| `--c-chrome-muted` | 路径前半段、其他标签 |
| `--c-chrome-active` | 当前标签的下划线 |
| `--font-sans` | 字体栈，对应的 `@font-face` 也写在 `index.html` |

组件里没有兜底色：缺少哪个变量，对应的部分就不显示。

## 安装

1. 把 `components/nav-bar/nav-bar.html` 复制到视频工程的 `compositions/nav-bar.html`。
2. 在根节点加挂载点：
   - `data-composition-id="nav-bar"`，`data-composition-src="compositions/nav-bar.html"`；
   - `data-start="0"`，时长为整片；
   - `style="z-index: 15"`。

## 挂载参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `logo` | 空 | 标志图片路径（40×40 显示），例如 GitHub 模板的标志复制到工程后是 `assets/brand/github-mark-white.svg`。留空则不显示标志，路径左移到 40px |
| `path` | 空 | 页面路径，例如 `"github / trending"`。最后一个 `/` 后面是页面名，前面是灰色 |
| `tabsX` | 420 | 标签页起点的 x 坐标，单位 px |
| `data` | `"tabs"` | 从 `window.VIDEO` 的哪个键读标签页 |

## 数据（`window.VIDEO.tabs`）

```js
tabs: [
  { label: "概览", at: 0 },
  { label: "#1", at: 20.7 },
  { label: "#2", at: 45.5 },
  …
  { label: "趋势", at: 146.4 },
]
```

- `at` 是这个章节开始的视频时间。
- 下划线在 `at - 0.1` 秒开始移动，用时 0.32 秒。如果这里有贡献图转场，下划线正好在格子盖住画面时移动。
- 标签宽度按文字估算：中文每字 28px，其他字符每个 17.5px，左右各加 22px 内边距，最小 80px。每次渲染的结果都一样。

## 限制

- 标签页太多时会超出 1920px 宽，建议不超过 8 个。
