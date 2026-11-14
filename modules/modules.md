# 视频模块库

一套做解说视频画面用的可复用模块，按职责划分：

- **设计主题**：管外观；
- **布局**：管版面；
- **组件**：通用内容部件；
- **转场**：scene 之间的交接；
- **模板**：某一类视频的组装方法和场景。

用模块拼视频，比每次从零写场景更快，风格也更统一。

本文档是模块库的入口。模块目录和 handoff 的 Required / Optional References 都是**发现入口，不是采用清单**：阅读模块目录不等于采用模块。每个视觉 scene 的统一选择与即时生成规则见 [composition 基础指令第四部分](../references/delegation/composition/base-instructions.md#四内容演绎与模板选择)。每个模块的文档放在同一个目录里；HTML 是静态标记和样式，初始化脚本是同目录的 `.mjs`，选中采用后按各模块文档复制进视频工程并由工程接线。

## 模块初始化接口（唯一约定）

六个已迁移模块（`caption-bar`、`nav-bar`、`tile-wipe`、`presenter`、`trending-overview`、`project-cover`）用同一个显式初始化约定；后续新模块也沿用它，不另建平行接口。接口名称以本节为准。

```js
// <模块名>.mjs
export function init(root, { params, data, duration, gsap }) { … }
```

- `root`：模块标记所在的根元素（HTML 里 `#root` 的那个节点）。模块内所有 DOM 查询都限定在 `root` 里。
- `params`：挂载参数（数字、字符串；即原来的 host variables），各模块文档逐条列出默认值。
- `data`：模块的数据载荷（即原来 `window.VIDEO` 里对应键的内容），形状见各模块文档。
- `duration`：这段挂载的时长，**局部秒**。
- `gsap`：调用方注入的 GSAP。模块不自己加载动画库。

时间语义：**局部秒**。`timeline` 上的 0 秒 = 挂载点的开始（常驻组件挂在 `data-start="0"` 时就是视频秒；场景挂在场景开始时就是场景秒）。视频秒到局部秒的换算由调用方做。

返回值：

```js
{
  timeline,   // 必返：暂停的 GSAP timeline，位置按局部秒；调用方负责驱动 seek
  ready,      // 可选：Promise，异步资产（如图层）就绪后 resolve；presenter 类模块用
  seek(t),    // 可选：在局部秒 t 自绘一帧；timeline seek 之外画面仍需更新的自绘模块用
  destroy(),  // 必返：拆除驱动（kill timeline 等），销毁/重挂不得残留
}
```

暂停的 timeline 不是唯一能力假设：纯 DOM tween 模块只返回 `timeline` + `destroy`；异步加载图层的 WebGL 自绘模块（`presenter`）另返回 `ready` / `seek(t)`，宿主在 hf-seek 时先 seek timeline 再调 `seek(t)` 并等待 `ready`。

模块**不**做、也没有 HyperFrames 知识：不读 `window.__hyperframes`、不从 host 推断参数或时长、不向 `window.__timelines` 注册。厂商事件桥接（`hf-seek`、`buildReady` 等）属于使用模块的视频工程的 adapter，不是模块库接口。

### 视频工程怎么接线（adapter 职责）

普通浏览器：引入 `.mjs`，克隆 HTML 模板到挂载点，调 `init` 后驱动 `timeline.pause().seek(t)` 即可，不需要任何厂商全局变量。

选用 HyperFrames 的生成工程，adapter 做三件事（这段代码驻留在工程里，不属于模块库）：

```js
import { init } from './compositions/caption-bar.mjs';
const host = document.querySelector('[data-composition-id="caption-bar"]');
const root = host.appendChild(template.content.cloneNode(true)).querySelector('#root')
  || host.querySelector('#root');
const params = JSON.parse(host.dataset.variableValues || '{}');
const { timeline, ready, seek, destroy } = init(root, {
  params,
  data: {
    captions: window.VIDEO[params.data || 'captions'],
    captionSegments: window.VIDEO[params.layoutData || 'captionSegments'],
  },
  duration: Number(host.dataset.duration) || 0,
  gsap,
});
// 工程侧的厂商协议接线：按 HyperFrames 核心协议把 timeline 注册进 scene host、
// 在 hf-seek 时 seek(timeline) 后 await ready 再调 seek?.(t)。
```

同一模块挂多次时，每次克隆一份干净模板、各调一次 `init`，各自的 timeline 互不共享。

路径约定：正文（散文、表格、行内代码）里的路径引用相对 `modules/`；**Markdown 链接目标相对当前 Markdown 文件所在目录**，阅读原始文档时也按此基准解析链接；可以直接照抄运行的 shell 命令从 skill 根目录（仓库根）写相对路径，例如 `bash scripts/fonts-download.sh <工程>/assets/fonts --theme modules/designs/github`。

## 目录

```
modules.md                                 本文档：入口、组装流程、约定
designs/
  designs.md                              主题选择与落盘契约、共享变量/字号阶梯/通用元素基线、字体维护与备选配色
  default/default.md, textures/           主题：燕麦纸（暖燕麦棉纸 + 低饱和墨灰与灰薰衣草）；paper.jpg
  github/github.md, textures/             主题：纸本（冷灰棉纸 + 低饱和 GitHub 色）；paper.jpg、slate.jpg
  producthunt/producthunt.md, textures/   主题：亚麻纸（粉调亚麻纸 + 低饱和墨蓝与陶土橙）；paper.jpg
layouts/
  layouts.md                              布局目录：逐视觉 scene 选择 layout；全片 canvas 固定、regions / caption 随 scene 变化
  landscape.md, landscape.json            布局：横屏模式（1920×1080，无主持人，主展示区贯穿，导航与底部字幕条）
  landscape-presenter.md, landscape-presenter.json  布局：横屏讲解模式（1920×1080，人物右下角主持，主 / 副展示区，上下界面条）
  portrait.md, portrait.json, portrait-3x4.json     布局：竖屏模式（1080×1920 与 1080×1440，无主持人，一文档两画布）
  portrait-presenter.md, portrait-presenter.json, portrait-3x4-presenter.json  布局：竖屏讲解模式（1080×1920 与 1080×1440，人物右下角主持，底部双行字幕条）
components/
  components.md                           组件总览和共同约定
  presenter/presenter.md, presenter.html, presenter.mjs, images/   人物动作：组件和两张姿势图（已迁移到显式初始化）
  nav-bar/nav-bar.md, nav-bar.html, nav-bar.mjs   顶部界面条（已迁移到显式初始化）
  caption-bar/caption-bar.md, caption-bar.html, caption-bar.mjs   底部字幕条（已迁移）
transitions/
  transitions.md                           转场总览：采用条件、目录、接入与时间约定
  tile-wipe/tile-wipe.md, tile-wipe.html, tile-wipe.mjs   方格转场（已迁移到显式初始化）
patterns/
  patterns.md                             patterns 总览：两类 pattern 的索引和使用方式
  media/                                  媒体呈现类：media-first、video-first、viewport-reveal、band、detail-callout、comparison、continuation
  info/                                   信息形态类：leaderboard、product-card、big-number、data-table、chart、process-flow、architecture、list-grid、comparison-matrix、code-terminal、callout-quote
motion.md                                 按需动效参考：能力查询、构思维度、runtime 选择、编排建议
templates/
  templates.md                            模板总览
  github-trending/github-trending.md      GitHub 热榜视频：组装方法、专属配色和元素、人物演法
  github-trending/trending-overview.md, .html, .mjs      场景：榜单总览（已迁移到显式初始化）
  github-trending/project-cover.md, .html, .mjs          场景：项目封面（已迁移到显式初始化）
  github-trending/brand/                  github-mark-white.svg
```

主题字体已经下载好放在仓库的 `resources/fonts/`（每个主题一份 CSS，WOFF2 在共用的 `resources/fonts/files/`），用 skill 根目录的 `scripts/fonts-download.sh` 从仓库字体资源拷进视频工程，例如 `bash scripts/fonts-download.sh <视频工程>/assets/fonts --theme modules/designs/github`。主题总是用 `--theme` 明确指定。

## 读哪份文档

| 要做的事 | 先读 |
|---|---|
| 做一类已有模板的视频（如 GitHub 热榜） | `templates/<类型>/<类型>.md`，再看它用到的场景和组件文档 |
| 选择全片外观主题或新建主题 | 先读 `designs/designs.md`（默认从库内注册 preset 中选择），选定后再看具体 `designs/<主题>/<主题>.md` 并落盘 `composition/design.json` |
| 安排版面、逐视觉 scene 选布局、确定区域坐标 | `layouts/layouts.md` → 每个所用 `layouts/<布局>.md` + 对应 `.json`（机器可读区域定义，字幕脚本读它的 `caption` 段） |
| 挂某个组件、写它的数据 | `components/<组件>/<组件>.md` |
| 需要转场、写它的切点数据 | `transitions/transitions.md`，选定后再读 `transitions/<转场>/<转场>.md`（如 `transitions/tile-wipe/tile-wipe.md`） |
| 已有画面构想，需要借用非常匹配的形态 / 动效建议 | 按需查 `patterns/<类>/<pattern>.md` 或 `motion.md`；查阅条件见 [composition 基础指令第四部分](../references/delegation/composition/base-instructions.md#四内容演绎与模板选择) |
| 让人物做动作、配嘴型 | `components/presenter/presenter.md`，动作库逐个列出每个动作的样子 |

## 分层

| 层 | 位置 | 定位 |
|---|---|---|
| 设计主题 | `designs/<主题>/` | **通用**：配色、字体、字号、背景、形状、动效。只管外观 |
| 布局 | `layouts/` | **通用**：区域的位置、尺寸、层级。只管版面 |
| 组件 | `components/<组件>/` | **通用**：不带具体内容；配色和字体只读主题变量；位置默认按布局 |
| 转场 | `transitions/<转场>/` | **通用交接层**：连接 scene；只在用户指定或特别匹配时采用，自由布局可以使用简单接缝 |
| patterns / motion | `patterns/<类>/`、`motion.md` | **按需参考（可跳过）**：画面形态与动效建议，不承担 scene 分类或设计流程 |
| 模板 | `templates/<类型>/` | **专用于一类视频**：选布局，组合组件并定好参数，加入专属配色和元素，提供可填内容的场景 |

## 组装一支视频

1. **建工程**：还没有 `composition/` 目录时直接 `npx hyperframes init composition/`。`prepare-handoff.py` 只物化 modules，不预装字体，因此无需为 `composition/assets/fonts/` 绕过 init。
2. **主题**：
   - 按 `designs/designs.md` 选定主题并写出 `composition/design.json`，运行 `bash scripts/fonts-download.sh <工程>/assets/fonts --theme modules/designs/<主题>` 把字体装入 `composition/assets/fonts/` 并在 `<head>` 引入字体 CSS；
   - 把主题 `:root` 放入 `index.html`，根节点放铺满全屏的 `#ground`（背景用 `var(--ground)`）。
3. **模板**：按 `templates/<类型>/<类型>.md`：
   - 在主题变量之后加上模板的专属变量；
   - 复制模板资源（如 `templates/github-trending/brand/` → 工程 `assets/brand/`）；
   - 选用它的场景。
4. **布局**：按 `layouts/<布局>.md` 的区域表和层级表排列挂载点。
5. **组件、转场和场景**：
   - 把实际采用的组件、转场和场景的 `.html` 与 `.mjs` 一起复制到工程的 `compositions/`，文件名不变；
   - 组件自带的图片按各自文档复制，例如 `components/presenter/images/*` → 工程 `assets/presenter/`；
   - 挂载点的 `data-composition-id` 用组件名、转场名或场景名；
   - 在工程里按 [模块初始化接口](#模块初始化接口唯一约定) 接线：克隆模板、调 `init`、驱动 timeline；选用 HyperFrames 时由工程 adapter 接其核心协议。
6. **数据**：
   - 写 `data/video-data.js`（`window.VIDEO = {…}`），在 `index.html` 的 `<head>` 里、GSAP 之后引入；adapter 从里面取各模块的 `data`；
   - 数据最好用脚本从字幕和配音生成；
   - 用到 `presenter` 时，动作演法与嘴型 `envelope` 生成方式见 `components/presenter/presenter.md`。
7. **检查**：
   - `npx hyperframes check` 和 check-composition 都通过后再 `render`，`check` 的错误都要修掉；
   - 只有人直接操作时才用 `npx hyperframes preview` 给人看，确认后再渲染；委派场景下由 sub-agent 直接渲染。

## 内容和外观分开

- **外观只来自主题变量**。组件和场景里没有写死的色值和字体名，换主题就是换变量。模板可以在主题之后覆盖几个变量，加入这类视频的专属配色。
- **内容只在拼视频时传入**，由 adapter 显式交给 `init`：
  - 单个值（文字、图片路径、颜色、时间点）作为 `params` 传入；在 HyperFrames 工程里习惯写在挂载点的 `data-variable-values` 上，由工程 adapter 读取后传给 `init`。同一个场景可以挂多次，每次给不同的值。
  - 列表作为 `data` 传入；在工程里习惯放在 `data/video-data.js` 的 `window.VIDEO` 里，由 adapter 按各模块的键取出：

```js
window.VIDEO = {
  tabs:     [{ label, at }],                                         // nav-bar
  captions: [{ start, end, text }],                                  // caption-bar
  captionSegments: [{ scene_id, begin_s, end_s, layout, caption_rect, caption_bar_rect, caption }], // 可选：scene 字幕布局
  cuts:     [{ at, label, title, emphasis, meta: [{ dot, strong, text }] }],   // tile-wipe
  presenter: { acts, thoughts, typing, glances, envelopeFps, envelope,
              placements: [{ begin_s, end_s, visible, x, y, size }] },          // presenter；placements 可选
  trending: { title, date, range, repos: [{ rank, owner, repo, desc, stars, readme, cue }] },  // github-trending 模板的 trending-overview
};
```

每个组件、转场和场景都有一个 `data` 参数，可以改成读别的键名。

视觉 scene 的常驻组件数据不从零编写：`subtitle-units.json` 的 `units[]` 以 `begin_s → start`、`end_s → end`、`text → text` 映射为 `captions[]`，`caption_segments[]` 原样映射为 `captionSegments[]`；`scene-config.json` 的每个 scene 以原起止时间映射为 `presenter.placements[]`，regions 有人物区（`component` 为 `presenter` 的 reserved 区）时为 `visible: true`，位置取该人物区 rect。完整映射见 `layouts/layouts.md` 和两个组件文档。

## 时间约定

- 常驻组件（`nav-bar`、`caption-bar`、`presenter`）和常驻转场（`tile-wipe`）挂在 0 秒、覆盖整片，**数据用视频秒**。
- 场景挂在它开始的时间，**场景里的时间是场景秒**（相对场景的 `data-start`）；其他非零 `data-start` 的挂载也使用相对各自起点的局部秒。
- 场景交接：`cuts[].at` = `tabs[].at` = 下一个场景的 `data-start`。新场景开头的 0.55 秒被转场盖着，场景里第一个元素放在 0.55 秒之后出现。
- 所有时间点都取自配音：字幕的逐句时间，以及每句话的开始时间。

## 扩展约定

- **新主题**：按 `designs/designs.md` 在 `designs/<名>/<名>.md` 单文件中定义完整 `:root` 变量代码块与包含 `min_font_px` / `fonts` 的机器配置 JSON 代码块，运行 `--refresh` 拉取并提交字体。
- **新布局**：写清每个区域的坐标、尺寸、层级，以及哪个组件填哪个区域；再放一份同名 `.json` 区域定义（`canvas` / `regions` / `caption`），数值与文档一致。放 `layouts/<名>.md`。
- **新组件**：
  - 不带内容，只读主题变量，位置默认按某个布局；
  - 文档和代码都放 `components/<名>/`：`<名>.md`、`<名>.html`（静态标记 + 样式）加同目录 `<名>.mjs`（导出 `init`，接口见 [模块初始化接口](#模块初始化接口唯一约定)）。
- **新转场**：负责 scene 交接，文档和代码放顶级 `transitions/<名>/`，文件形式与 `init` 接口同上；采用规则和时间语义见 `transitions/transitions.md`。
- **新模板**：一类视频一个目录。`templates/<类型>/<类型>.md` 写组装方法；每个场景一份 `<场景>.md`、同目录的 `<场景>.html` 和 `<场景>.mjs`。
- **所有 HTML** 都是静态模板：用 `<template>` 包起来，根元素 `#root` 带固定的 `data-composition-id`；所有动画只由时间决定，动画编排写在同目录 `.mjs` 的 `init` 里。
