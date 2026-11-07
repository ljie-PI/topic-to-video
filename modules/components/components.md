# 组件

组件是**通用部件**，不属于任何一类视频：

- **不带具体内容**：文字、图片、时间点都在拼视频时，通过挂载参数（`data-variable-values`）或 `window.VIDEO` 传入。
- **不带具体外观**：配色和字体只读设计主题的变量（`--c-*`、`--font-sans`，见 `designs/designs.md`），组件里没有写死的色值和字体名。唯一的例外是人物自身的美术颜色，比如 Jay 的嘴巴内部。
- **位置默认按布局**：位置参数的默认值是 `layouts/presenter.md` 里对应的区域，可以用参数改。

某一类视频专用的东西（品牌标志、专属配色、专属卡片）放在模板里（`templates/`），由模板组合这些组件来实现。

## 目录

| 组件 | 文档 / 文件 | 作用 | 层级 | 读的数据 |
|---|---|---|---|---|
| `jay` | `components/jay/jay.md`；`components/jay/`；`components/jay/make-envelope.mjs` | 人物动作：呼吸、眨眼、动嘴、瞥视；按剧本挥手、惊喜、点头、思考、大笑、打字 | 20 | `VIDEO.jay` |
| `nav-bar` | `components/nav-bar/nav-bar.md`；`components/nav-bar/` | 顶部 72px 界面条：标志、路径、章节标签，当前标签的下划线充当进度条 | 15 | `VIDEO.tabs` |
| `caption-bar` | `components/caption-bar/caption-bar.md`；`components/caption-bar/` | 底部 72px 界面条，显示单行字幕 | 16 | `VIDEO.captions`（+ 可选 `VIDEO.captionSegments`） |
| `transitions/tile-wipe` | `components/transitions/tile-wipe/tile-wipe.md`；`components/transitions/tile-wipe/` | 方格转场：方格从一点扩散盖住切点，可以亮出预告卡片 | 10 | `VIDEO.cuts` |

以后的转场都放在 `transitions/` 子目录下。

## 共同约定

- 每个组件是**静态 HTML + 同目录初始化脚本**：`<名>.html` 用 `<template>` 包起来，根元素 `#root` 带固定的 `data-composition-id`；`<名>.mjs` 导出 `init`，接口见 `modules.md` 的「模块初始化接口」。
- `nav-bar`、`caption-bar`、`tile-wipe`、`jay` 都已迁移：不读 HyperFrames 全局变量、不向 `window.__timelines` 注册；视频工程 adapter 负责接线（jay 是 WebGL 自绘模块，`init` 另返回 `ready` / `seek(t)`，见 [modules.md](../modules.md) 的模块初始化接口）。
- 这四个组件都是常驻的：挂在 `data-start="0"`，时长为整片，数据里的时间都是视频秒。
- 组件 HTML 里的资源路径都相对视频工程根目录（`assets/...`），所以组件自带的图片要按各自文档复制到工程 `assets/` 下指定的位置。
- 所有动画只由时间决定：不用随机数（需要随机时用固定种子），不用定时器。同样的输入每次渲染都完全一样。
