# 组件：nav-bar（顶部导航栏）

讲解模式布局顶部的深色条，占满宽度。横屏默认 72px 高，从左到右依次是站点标志、页面路径、章节标签页；竖屏讲解布局用 88px 的紧凑模式，把标签页换成右侧的当前章节指示和底部进度线（见下文「紧凑模式」）。

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
| `logo` | 空 | 标志图片路径（40×40 显示），例如 `github-trending` 模板的标志复制到工程后是 `assets/brand/github-mark-white.svg`。留空则不显示标志，路径左移到 40px |
| `path` | 空 | 页面路径，例如 `"github / trending"`。最后一个 `/` 后面是页面名，前面是灰色 |
| `tabsX` | 420 | 标签页起点的 x 坐标，单位 px（仅标签页模式） |
| `mode` | `"tabs"` | `"tabs"`：横屏标签页行；`"compact"`：竖屏紧凑模式（右侧当前章节 + 底部进度线） |
| `height` | 72 | 条高，单位 px。竖屏讲解布局用 `88` |
| `padX` | 40 | 左右内边距：标志左边、页面路径起点（标志右 18px）、右侧章节指示的右边，单位 px。竖屏讲解布局用 `70` |
| `logoSize` | 40 | 标志边长，单位 px。竖屏讲解布局用 `34` |
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

## 紧凑模式（竖屏讲解布局）

竖屏画布只有 1080px 宽，横屏那排标签页放不下，所以 `mode: "compact"` 把整排标签换成两件事：

- **右侧当前章节**：`01 / 07 · 概览`——两位序号 + 总章数 + 章节名。章节序号与总数用 `tabular-nums`，章节名与序号之间用 `chrome-muted` 的 `/ 07 · ` 分隔。换章节时只做 0.06 秒的透明度切换（`at - 0.04`），不做滑动。
- **底部进度线**：条的最下沿一条 6px `--c-chrome-active` 线，从 0 匀速填到 100%，时长等于整片时长；它同时是整片进度条，方格转场期间也不暂停。

挂载参数（`layouts/portrait-presenter.md` 的取值）：

```js
// 9:16 与 3:4 相同；宿主 data-width="1080"
{'mode': 'compact', 'height': 88, 'padX': 70, 'logoSize': 34,
 'logo': 'assets/brand/github-mark-white.svg', 'path': 'github / trending'}
```

- 条高、内边距、标志尺寸都用 CSS 变量（`--nb-h` / `--nb-pad` / `--nb-logo`）注入，所以同一份组件在横屏 72px 与竖屏 88px 下都不需要改样式文件。
- 没有 `logo` 时页面路径左移到 `padX`；没有标签数据时进度线仍按片长填充，右侧章节指示留空。
- 紧凑模式没有按 scene 切换显隐的能力：同一支视频里不要在它下面混排没有导航栏区的场景。

## 限制

- 标签页太多时会超出 1920px 宽，建议不超过 8 个（紧凑模式不受此限，它只显示当前章节）。
