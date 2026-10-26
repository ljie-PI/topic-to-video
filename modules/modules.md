# 视频模块库

一套做 HyperFrames 视频用的可复用模块，分四类：

- **设计主题**：管外观；
- **布局**：管版面；
- **组件**：通用部件；
- **模板**：某一类视频的组装方法和场景。

用模块拼视频，比每次从零写场景更快，风格也更统一。

本文档是模块库的入口。下文所有路径都相对 `modules/` 目录。每个模块的文档、HTML 和图片放在同一个目录里；HTML 和图片按各模块文档复制进视频工程。

路径约定：正文（散文、表格、行内代码）里的路径引用一律相对 `modules/` 书写；可以直接照抄运行的 shell 命令一律从 skill 根目录（仓库根）写相对路径，例如 `bash scripts/fonts-download.sh <工程>/assets/fonts --theme modules/designs/github`。

## 目录

```
modules.md                                 本文档：入口、组装流程、约定
designs/
  designs.md                              主题变量约定（token 契约：--c-* 颜色 / --font-* / --motion-* / 字号下限）、字体清单格式、备选配色
  default/default.md, fonts.json, textures/   主题：燕麦纸（暖燕麦棉纸 + 低饱和墨灰与灰薰衣草）；paper.jpg
  github/github.md, fonts.json, textures/   主题：纸本（冷灰棉纸 + 低饱和 GitHub 色）；paper.jpg、slate.jpg
  producthunt/producthunt.md, fonts.json, textures/   主题：亚麻纸（粉调亚麻纸 + 低饱和墨蓝与陶土橙）；paper.jpg
layouts/
  presenter.md, presenter.json            布局：讲解模式（人物右下角主持，主 / 副展示区，上下界面条）
  stage.md, stage.json                    布局：舞台模式（1920×1080，无主持人，主展示区贯穿，全局字幕区）
  portrait.md, portrait.json, portrait-3x4.json   布局：竖屏（1080×1920 与 1080×1440，一文档两画布，各一份区域定义 JSON）
components/
  components.md                           组件总览和共同约定
  jay/jay.md, jay.html, images/           人物动作：组件和两张姿势图
  nav-bar/nav-bar.md, nav-bar.html        顶部界面条
  caption-bar/caption-bar.md, caption-bar.html   底部字幕条
  transitions/tile-wipe/tile-wipe.md, tile-wipe.html   方格转场
patterns/
  patterns.md                             patterns 总览：两类 pattern 的索引和使用方式
  media/                                  媒体呈现类：media-first、video-first、viewport-reveal、band、detail-callout、comparison、continuation
  info/                                   信息形态类：leaderboard、product-card、big-number、data-table、chart、process-flow、architecture、list-grid、comparison-matrix、code-terminal、callout-quote
motion.md                                 运动指南：动画能力发现、选择顺序、runtime 选择、全局运动原则
templates/
  templates.md                            模板总览
  github/github.md                        GitHub 热榜视频：组装方法、专属配色和元素、人物演法
  github/trending-overview.md, .html      场景：榜单总览
  github/project-cover.md, .html          场景：项目封面
  github/brand/                           github-mark-white.svg
examples/
  github-trending/                        完整示例工程（27.2 秒），只在 skill 仓库里，委派场景下工作区没有 examples/
  jay-actions/                            人物动作演示：15 个动作加打字和瞥视逐个演一遍（59.9 秒）
```

主题字体已经下载好放在仓库的 `resources/fonts/<主题>/`，用 skill 根目录的 `scripts/fonts-download.sh` 拷进视频工程，不联网，例如 `bash scripts/fonts-download.sh <视频工程>/assets/fonts --theme modules/designs/github`（旧的具名风格 `github` 等价）。

## 读哪份文档

| 要做的事 | 先读 |
|---|---|
| 做一类已有模板的视频（如 GitHub 热榜） | `templates/<类型>/<类型>.md`，再看它用到的场景和组件文档 |
| 选外观 / 新建主题 | `designs/designs.md`，再看具体主题 |
| 安排版面、确定区域坐标 | `layouts/<布局>.md` + 同名的 `.json`（机器可读区域定义，字幕脚本读它的 `caption` 段） |
| 挂某个组件、写它的数据 | `components/<组件>/<组件>.md` |
| 设计某个 scene 的画面（选形态、摆位置、配动效） | `patterns/<类>/<pattern>.md`，动效问题再看 `motion.md` |
| 让人物做动作、配嘴型 | `components/jay/jay.md`；每个动作的样子见 `examples/jay-actions/`（示例只在 skill 仓库；委派时路径见 handoff 的 Required References） |
| 看一个完整的成品怎么写 | `examples/github-trending/`（`index.html`、`data/video-data.js`、`tools/build-data.mjs`；示例只在 skill 仓库，委派时路径见 handoff 的 Required References） |

## 分层

| 层 | 位置 | 定位 |
|---|---|---|
| 设计主题 | `designs/<主题>/` | **通用**：配色、字体、字号、背景、形状、动效。只管外观 |
| 布局 | `layouts/` | **通用**：区域的位置、尺寸、层级。只管版面 |
| 组件 | `components/<组件>/` | **通用**：不带具体内容；配色和字体只读主题变量；位置默认按布局 |
| patterns | `patterns/<类>/` | **通用建议**：媒体呈现和信息形态怎么摆、怎么动，只作建议不作规则 |
| 模板 | `templates/<类型>/` | **专用于一类视频**：选布局，组合组件并定好参数，加入专属配色和元素，提供可填内容的场景 |

## 组装一支视频

1. **建工程**：
   - `npx hyperframes init` 不接受非空目录，而委派场景下 `composition/assets/fonts/` 已经预置——顺序必须是 init 先行：在工作区里 `npx hyperframes init composition-init/`，把生成的文件拷进 `composition/`（不要动 `assets/fonts/`），再删掉 `composition-init/`；
   - 非委派场景（还没有 `composition/` 目录时）直接 `npx hyperframes init composition/`；
   - `examples/` 只存在于 skill 仓库，工作区副本里没有；需要参考完整示例工程时从 handoff 的 Required References 给出的绝对路径读。
2. **主题**：
   - 把 `designs/<主题>/textures/` 复制到工程的 `assets/textures/`；
   - 用 skill 根目录的 `bash scripts/fonts-download.sh <工程>/assets/fonts --theme modules/designs/<主题>` 把字体装进工程，并在 `index.html` 的 `<head>` 里引入装进去的 CSS；委派场景下字体已经由 `prepare-handoff.py` 预置在 `composition/assets/fonts/`，不用再装，直接引入其中的 CSS；
   - 把主题文档里的变量代码放进 `index.html` 的 `:root`；
   - 根节点放一个铺满全屏的 `#ground`，背景用 `var(--ground)`。
3. **模板**：按 `templates/<类型>/<类型>.md`：
   - 在主题变量之后加上模板的专属变量；
   - 复制模板资源（如 `templates/github/brand/` → 工程 `assets/brand/`）；
   - 选用它的场景。
4. **布局**：按 `layouts/<布局>.md` 的区域表和层级表排列挂载点。
5. **组件和场景**：
   - 把 `.html` 复制到工程的 `compositions/`，文件名不变；
   - 组件自带的图片按各自文档复制，例如 `components/jay/images/*` → 工程 `assets/jay/`；
   - 挂载点的 `data-composition-id` 用组件名或场景名。
6. **数据**：
   - 写 `data/video-data.js`（`window.VIDEO = {…}`），在 `index.html` 的 `<head>` 里、GSAP 之后引入；
   - 数据最好用脚本从字幕和配音生成，参考示例里的 `tools/build-data.mjs`（示例只在 skill 仓库，路径见 handoff 的 Required References）；
   - 嘴型用 `node modules/components/jay/make-envelope.mjs <配音>` 生成。
7. **检查**：
   - `npx hyperframes check` 和 check-composition 都通过后再 `render`，`check` 的错误都要修掉；
   - 只有人直接操作时才用 `npx hyperframes preview` 给人看，确认后再渲染；委派场景下由 sub-agent 直接渲染。

## 内容和外观分开

- **外观只来自主题变量**。组件和场景里没有写死的色值和字体名，换主题就是换变量。模板可以在主题之后覆盖几个变量，加入这类视频的专属配色。
- **内容只在拼视频时传入**，分两种方式：
  - 单个值（文字、图片路径、颜色、时间点）写在挂载点的 `data-variable-values` 上，组件和场景里用 `window.__hyperframes.getVariables()` 读。同一个场景可以挂多次，每次给不同的值。
  - 列表放在 `data/video-data.js`：

```js
window.VIDEO = {
  tabs:     [{ label, at }],                                         // nav-bar
  captions: [{ start, end, text }],                                  // caption-bar
  cuts:     [{ at, label, title, emphasis, meta: [{ dot, strong, text }] }],   // tile-wipe
  jay:      { acts, thoughts, typing, glances, envelopeFps, envelope },        // jay
  trending: { title, date, range, repos: [{ rank, owner, repo, desc, stars, readme, cue }] },  // github 模板的 trending-overview
};
```

每个组件和场景都有一个 `data` 参数，可以改成读别的键名。

## 时间约定

- 常驻组件（`nav-bar`、`caption-bar`、`tile-wipe`、`jay`）挂在 0 秒、覆盖整片，**数据用视频秒**。
- 场景挂在它开始的时间，**场景里的时间是场景秒**（相对场景的 `data-start`）。
- 场景交接：`cuts[].at` = `tabs[].at` = 下一个场景的 `data-start`。新场景开头的 0.55 秒被转场盖着，场景里第一个元素放在 0.55 秒之后出现。
- 所有时间点都取自配音：字幕的逐句时间，以及每句话的开始时间。

## 扩展约定

- **新主题**：按 `designs/designs.md` 定义全部变量（颜色 + 字体 + 运动 token + 字号下限），并写一份 `fonts.json` 字体清单。文档和清单都放 `designs/<名>/`，文档名 `<名>.md`。
- **新布局**：写清每个区域的坐标、尺寸、层级，以及哪个组件填哪个区域；再放一份同名 `.json` 区域定义（`canvas` / `regions` / `caption`），数值与文档一致。放 `layouts/<名>.md`。
- **新组件**：
  - 不带内容，只读主题变量，位置默认按某个布局；
  - 文档和代码都放 `components/<名>/`：`<名>.md` 加 `<名>.html`；
  - 转场放 `transitions/` 子目录。
- **新模板**：一类视频一个目录。`templates/<类型>/<类型>.md` 写组装方法；每个场景一份 `<场景>.md` 加同目录的 `<场景>.html`。
- **所有 HTML** 都是 HyperFrames 子合成（`<template>` 包裹，根元素 `#root` 带固定的 `data-composition-id`，注册同名时间线），动画只由时间决定。
