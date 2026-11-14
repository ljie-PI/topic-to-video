# 模板：github-trending/trending-overview（Trending 榜单总览）

属于 GitHub 热榜这一类视频（见 `templates/github-trending/github-trending.md`）。

一个场景，逐个介绍 GitHub Trending 榜单里的项目。

- **布局**：讲解模式（`layouts/presenter.md`）。
  - **页眉行**：页面标题，例如“GitHub 本周热榜”，后面跟日期。
  - **副展示区**：Trending 榜单，紧凑样式，最多 5 行。
  - **主展示区**：README 面板，显示当前项目的 README 截图。
- **节奏**：
  1. 场景开始时，人物先挥手欢迎；同时标题、榜单（像信息流一样逐行出现）、README 面板依次入场。
  2. 讲到某个项目时：
     - 这一行的背景变成浅蓝，左边出现蓝色竖条，排名变蓝；
     - README 面板切换到这个项目的截图，面板边框闪一下蓝色，标题栏右侧显示仓库名；
     - README 截图在这个项目的讲解时间里缓慢向下滚动；
     - 约 0.45 秒后，这一行的星标变成实心黄星，star 数轻轻弹一下。
  3. 讲到下一个项目时，上一行恢复普通样式，星标保持实心。

这个场景不包含开场大标题：标题直接以页眉行的大小出现。

## 文件

- `templates/github-trending/trending-overview.html`：场景本体，静态标记和样式。图标已内联，没有额外图片。
- `templates/github-trending/trending-overview.mjs`：导出 `init`（接口见 `modules.md` 的「模块初始化接口」）。

## 依赖

- 设计主题的全部变量（`--c-*`、`--font-sans`、`--font-mono`），由视频的 `index.html` 提供；模板里没有写死的色值和字体名。`README.md` 字样用 `--font-mono`。
- 每个项目一张 README 截图（见下文）。

## 安装与挂载

1. 把 `templates/github-trending/trending-overview.html` 和 `trending-overview.mjs` 一起复制到视频工程的 `compositions/`。
2. 在根节点加挂载点：
   - `data-composition-id="trending-overview"`，`data-composition-src="compositions/trending-overview.html"`；
   - `data-start`：场景开始的视频时间；`data-duration`：场景时长；
   - `style="z-index: 2"`。
3. 在工程里调 `init`：传入参数和 `trending` 数据，拿到暂停的 timeline 后按场景秒 seek。接线示例见 `modules.md` 的「模块初始化接口」。

一支视频里一般只挂一次。

## 参数（`init` 的 `params`）

| 参数 | 默认 | 说明 |
|---|---|---|
| `title` | `"GitHub 本周热榜"` | 页眉行标题；也可以写在数据里 |
| `date` | `""` | 标题后面的日期，例如 `"10/12 — 10/18"` |
| `range` | `"本周"` | 榜单标题栏里“日期范围：”后面的文字 |
| `listAt` | 0.2 | 榜单入场时间（场景秒）。标题提前 0.2 秒，README 面板晚 0.1 秒 |
| `scrollSpeed` | 60 | README 截图最快的滚动速度，单位 px/秒 |
| `data` | `"trending"` | 工程数据（`window.VIDEO`）里哪个键是数据，adapter 取出后作为 `init` 的 `data` |

## 数据（`init` 的 `data`，工程里通常来自 `window.VIDEO.trending`）

```js
trending: {
  title: "GitHub 本周热榜",
  date: "10/12 — 10/18",
  range: "本周",
  repos: [
    { rank: 1, owner: "storytold", repo: "artcraft", desc: "先构图，再交给模型生成",
      stars: "20,267", readme: "assets/readme/artcraft.png", cue: 1.467 },
    …   // 最多 5 个
  ],
}
```

| 字段 | 说明 |
|---|---|
| `rank` | 排名数字，默认等于顺序 |
| `owner`, `repo` | 仓库路径。整条路径超过 32 个字符时，自动从 28px 缩到 26px |
| `desc` | 一句话描述，26px，单行，最好不超过 13 个汉字 |
| `stars` | 显示用的 star 数，已经格式化好的字符串，例如 `"20,267"` |
| `readme` | README 截图的路径 |
| `cue` | 必填，讲到这个项目的实际朗读时间，**场景秒**（相对 `data-start`）。用模板 cue 对齐结果换算，必须是非负有限数，项目按 cue 时间排序 |

## README 截图要求

- 用 PNG，宽度至少 1044px，按 1044px 宽显示。高度不限，越长能滚动的距离越大。
- 从 README 顶部开始截，最好包含项目标题。滚动从截图顶部开始向下走。
- 滚动距离 = min(截图显示高度 − 722, `scrollSpeed` × 这个项目的讲解时长)。截图比面板矮时不滚动。
- 滚动从 `cue + 0.3` 秒开始，用 `sine.inOut` 缓动，在下一个 `cue` 前 0.3 秒左右停下。

## 人物动作建议（写在 `window.VIDEO.presenter`，换算成视频秒）

- 场景开始 0.45 秒：`["wave", 3000]`，挥手欢迎。
- 每个 `cue`：瞥视 `[cue, 1.0, "U"]`，抬头看榜单。
- 每个 `cue + 1.7` 秒左右：瞥视 `[cue + 1.7, 1.0, "L"]`，看 README。
- 如果下一个场景用贡献图转场，在场景结束前约 0.85 秒加一段 `typing`。

## 限制

- 最多 5 个项目，因为副展示区高 522px，每行 92px，标题栏 56px。
- 没有给 `cue` 或 cue 非法时，场景直接报错，不按序号猜秒数。未被朗读的项目应从该场景的列表里省略；不能满足场景需求时不用该场景 / 模板。
- 行和截图都由脚本按数据生成。在 Studio 里改内容要改 `video-data.js`。
