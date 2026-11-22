# 组件：nav-bar（顶部导航栏）

讲解模式布局顶部的深色条，占满宽度。横屏默认 72px 高，从左到右依次是站点标志、页面路径、章节标签页；竖屏讲解布局传 `mode: "compact"`（88px 高，右侧当前章节指示 + 底部进度线）。

**组件本身没有任何具体内容**：标志、路径、标签页都在拼视频时传入；配色和字体全部来自设计主题的变量，组件里没有写死的色值和字体名。

当前章节的标签是白字，下方有一条珊瑚色下划线。到了某个章节的开始时间，下划线滑到对应的标签下，所以它就是整支视频的进度条。

## 文件

- `components/nav-bar/nav-bar.html`：静态标记和样式。
- `components/nav-bar/nav-bar.mjs`：导出 `init`（接口见 `modules.md` 的「模块初始化接口」）。

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

1. 把 `components/nav-bar/nav-bar.html` 和 `nav-bar.mjs` 一起复制到视频工程的 `compositions/`。
2. 在根节点加挂载点：
   - `data-composition-id="nav-bar"`，`data-composition-src="compositions/nav-bar.html"`；
   - `data-start="0"`，时长为整片；
   - `style="z-index: 15"`。
3. 在工程里调 `init`：传入参数和标签页数据，拿到暂停的 timeline 后按局部秒 seek。接线示例见 `modules.md` 的「模块初始化接口」。

## 参数（`init` 的 `params`）

| 参数 | 默认 | 说明 |
|---|---|---|
| `logo` | 空 | 标志图片路径（横屏 40×40、紧凑模式 34×34），例如 `github-trending` 模板的标志复制到工程后是 `assets/brand/github-mark-white.svg`。留空则不显示标志，路径左移到左边距 |
| `path` | 空 | 页面路径，例如 `"github / trending"`。最后一个 `/` 后面是页面名，前面是灰色 |
| `tabsX` | 420 | 标签页起点的 x 坐标，单位 px（仅 `"tabs"` 模式） |
| `mode` | `"tabs"` | `"tabs"`：横屏标签页行（72px 高，左右边距 40px）；`"compact"`：竖屏紧凑模式（88px 高，左右边距 70px） |
| `data` | `"tabs"` | 工程数据（`window.VIDEO`）里哪个键是标签页，adapter 取出后作为 `init` 的 `data` |

## 数据（`init` 的 `data`，工程里通常来自 `window.VIDEO.tabs`）

```js
tabs: [
  { label: "概览", at: 0 },
  { label: "#1", at: 20.7 },
  { label: "#2", at: 45.5 },
  …
  { label: "趋势", at: 146.4 },
]
```

- `at` 是这个章节开始的视频时间（局部秒；本组件常驻挂在 0 秒，两者一致）。
- 下划线在 `at - 0.1` 秒开始移动，用时 0.32 秒。如果这里有贡献图转场，下划线正好在格子盖住画面时移动。
- 标签宽度按文字估算：中文每字 28px，其他字符每个 17.5px，左右各加 22px 内边距，最小 80px。每次渲染的结果都一样。

## 紧凑模式（`mode: "compact"`）

- 右侧在 `at - 0.04` 切换显示 `NN / 总章数 · 章节名`（`tabular-nums`），底部 6px 进度线按片长匀速填满。
- 挂载参数示例：`{"mode": "compact", "logo": "assets/brand/github-mark-white.svg", "path": "github / trending"}`（宿主 `data-width="1080"`）。
- 组件无按 scene 显隐能力，同片不要混排无导航栏区的场景。

## 限制

- 横屏模式下标签页太多时会超出 1920px 宽，建议不超过 8 个。
