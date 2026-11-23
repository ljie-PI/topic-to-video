# 动态模块（motions）

`motions/` 是**通用动态场景与图示机制模块库**：用来演绎流程流转、系统拓扑、数据构建和素材重点推拉标注。

- **不带具体内容**：节点文案、数据序列、视口停靠点和语音触发时刻都在拼视频时通过挂载参数（`params` / `data-variable-values`）或 `window.VIDEO` 传入。
- **不带写死外观**：全部颜色、字体和默认运动节奏只读设计主题变量（`--c-*`、`--font-sans`、`--font-mono`、`--motion-*`，见 `designs/designs.md`），采用半透明 `--c-card` 透出 `#ground` 纸纹肌理与 `1–2px` 精细线宽阶梯。
- **像素 1:1 自适应排版**：每个模块读取宿主区域像素宽高、设置 `1:1` 像素 `viewBox`，并内置确定性中英文字宽估算与自动折行，保证横竖屏及长短文案下文字完整落在节点框与内容区域内。

目录与 handoff 引用均为发现入口，采用规则统一见 [composition 基础指令第四部分](../../references/delegation/composition/base-instructions.md#四内容演绎与模板选择)：命中时阅读对应模块 `.md` 文档，可直接按参数挂载或拷入 `compositions/` 按场景改写；不命中时自主设计即时生成动画。

转场（scene 之间的交接）不在此目录，按需见 `transitions/transitions.md`；常驻界面组件（主持人、导航栏、字幕条）见 `components/components.md`。

## 目录

| 模块 | 文档 / 文件 | 作用 | 覆盖形态 | 读的数据 |
|---|---|---|---|---|
| `flow-path` | `motions/flow-path/flow-path.md`；`motions/flow-path/` | 有向流程、时间线与状态机节点渐进揭示、焦点流转与 `pathLength="1"` 连线生长（横竖屏自动排布） | `patterns/info/process-flow.md` | `VIDEO.flowPath`（或参数指定键） |
| `topology-graph` | `motions/topology-graph/topology-graph.md`；`motions/topology-graph/` | 分层架构与依赖拓扑图：微网格舞台、模块端口锚点、依赖连线脉冲绘制与局部焦点切换 | `patterns/info/architecture.md` | `VIDEO.topologyGraph`（或参数指定键） |
| `chart-build` | `motions/chart-build/chart-build.md`；`motions/chart-build/` | 柱状对比、趋势折线面积与单点大数字指标构建，`1px` 坐标辅助线与等宽数字动态计数 | `patterns/info/chart.md`、`patterns/info/big-number.md` | `VIDEO.chartBuild`（或参数指定键） |
| `focus-callout` | `motions/focus-callout/focus-callout.md`；`motions/focus-callout/` | 素材局部 zoom-in 推近裁切与外沿非遮挡引线标注：引线锚定视口外边框，标注卡置于外置信息带 | `patterns/media/detail-callout.md` | `VIDEO.focusCallout`（或参数指定键） |

共用排版与几何工具：`motions/motion-utils.mjs`（1:1 舞台与标题初始化 `prepareStage`、确定性字宽估算与 `document.fonts.ready` 实测重排、零截断多行 `<tspan>` 折行、唯一 `<defs>` ID 与可逆状态驱动）。

## 选定后怎么接入

1. 阅读所选模块的具体 `.md` 文档，核对适用边界、`params`、数据形状和时间行为。
2. 把该模块的 `<名>.html`、`<名>.mjs` 以及共用的 `motions/motion-utils.mjs` 一起复制到视频工程的 `composition/compositions/`（工程内保持同名：`compositions/<名>.html`、`compositions/<名>.mjs`、`compositions/motion-utils.mjs`）；若场景需要定制结构，也可复制后在工程副本上直接改写。
3. 将挂载点放在当前 scene 的目标 content 区域（可直接将宿主定位到该区域矩形，或挂全画布并通过 `params` 传入区域的 `x`、`y`、`width`、`height`），设置 `data-composition-id="<名>"`、`data-composition-src="compositions/<名>.html"`、`data-start` 与 `data-duration`。
4. 在工程 adapter 中按 [modules.md](../modules.md) 的「模块初始化接口」调用 `init(root, { params, data, duration, gsap })`，驱动返回的暂停 `timeline` 按局部秒 `seek`。同一模块多次挂载时每次克隆独立模板、各调一次 `init`，实例与 `<defs>` ID 互不干扰。

## 时间约定与确定性要求

- `init` 的 `duration` 和返回 `timeline` 均使用本次挂载的**局部秒**：`timeline` 的 `0` 秒对应宿主 `data-start`（挂在某个视觉 scene 起点时即为该场景秒）。视频秒到局部秒的换算由调用方完成。
- 数据中的 `at` 锚点均填局部秒，须对应真实旁白朗读时机，不在 scene 开头一次性铺满全部节点或数据项。
- 所有几何计算与动画完全由输入数据和局部时间决定：不使用 `Math.random()`、`Date.now()`、定时器或 `repeat: -1` 无限循环；正向与反向 `seek(t)` 在任意时刻都得到完全一致的画面。

## 需要核对实现能力时

本项目只依赖 `hyperframes` 与 `hyperframes-cli` 两个外部 skill；不允许加载其他 HyperFrames 扩展。实现自主构思的动效或改写模块、需要核对能力或 API 时，从这两个 skill 的文档按问题读取：工程结构、渲染与检查命令看 `hyperframes-cli`；核心协议与场景组装约定看 `hyperframes`。确定方案后只读与本次实现直接相关的部分；不要预读全部实现文件，也不要把任何索引当作能力全集。具体的组件与模板写法见 `components/components.md` 和 `templates/templates.md`。

## 动效构思与 Runtime 选择

无论借用 `motions/` 模块还是即时生成自主动画，构思时可围绕以下维度判断，不作机械清单：

- 旁白要表达的对象关系、状态变化与观众当前需要看清的重点；
- 素材实际内容、比例和可读尺寸，以及当前 scene layout 区域划出的边界；
- 输出朝向、信息密度、可读停留时间和与前后 scene 的连续性；
- 动效是否推进理解：不用真实素材的场景围绕 `content_plan` 的对象、关系或分步变化做视觉动画演绎（不做无关装饰动效）；有真实素材的场景可用局部 zoom、外置引线标注或简洁稳定的呈现。

按元素类型区分表现手段与控制方式，且**无论选用哪种技术栈，均须严格遵循 `designs/designs.md` 规范**（内联 SVG 的 `fill` / `stroke` / `font-family` 必须写 `var(--c-*)` / `var(--font-*)`，禁写死 `#hex` 色值；`Canvas 2D`、`Three.js` 经 `getComputedStyle` 读取主题 `:root` token 的配色、字体与线宽阶梯；`GSAP` 对齐 `--motion-*` 时长与缓动规范）：

- **非图片 / 视频素材的元素**：结合内容特征使用 **`SVG`、`Canvas 2D`、`Three.js`** 做动画（`1:1` 像素 `SVG` 绘制结构图示与状态节点；`Canvas 2D` 自绘高密度点列、波形或连续轨迹；`Three.js` 处理真实三维空间、深度相机或着色器模拟；时间轴驱动可配合 `GSAP` 保持确定性 `seek`），按需选择或组合，不要求在同一支视频里铺满所有技术栈。
- **真实图片 / 视频素材的控制**：统一使用 **`GSAP` 动画特效**控制视口推拉、平移滚动、局部聚焦与外置标注联动。

| 技术栈 | 适用角色与场景 | 不建议只因 |
| --- | --- | --- |
| SVG（配合时间轴驱动） | 非图片/视频元素：结构流转、`pathLength="1"` 连线生长、拓扑节点与指标图表 | 想给所有 scene 统一套简单淡入上移 |
| Canvas 2D | 非图片/视频元素：高密度点列、连续波形或细粒度轨迹自绘（配合 `seek(t)` 确定性重绘） | 几个卡片节点用 SVG 已更清晰好调 |
| Three.js | 非图片/视频元素：真实三维空间、相机运动、GLTF 或着色器模拟 | 普通平面图示倾斜缩放已能说明语义 |
| GSAP | 真实图片/视频素材的视口推拉、平移、聚焦与标注控制，以及确定性时间线编排 | 脱离真实元素关系做无意义晃动装饰 |
| CSS animations / WAAPI / Lottie 等 | 单元素轻量状态过渡，或已有明确本地资产时按需补充 | 复杂多拍编排勉强拆成手工延迟或无资产堆砌技术栈 |

### 全片编排与朝向建议

- **焦点与留白**：围绕当前讲解的核心变化组织动效，阶段之间保留阅读停留；围绕同一张技术图拆成相邻连续 scene 深讲时，切点不加打断性过场，靠视口推拉（如 `focus-callout`）与焦点转移自然衔接。
- **横屏与竖屏几何**：横屏可使用横向链路、左右主图加外置标注列与宽幅曲线推进；竖屏流程、时间线、状态机优先纵向推进，图表纵向舒展或改横向条形，架构拓扑按上下分层聚焦主路径，不靠缩小字号把横屏排法硬塞进竖屏。

## 新 motion 模块扩展约定

- 新增通用动态模块放在 `motions/<名>/` 下，包含三份同名文件：
  - `<名>.md`：说明适用场景、文件清单、依赖的主题变量、安装接入、`params` 表、`data` 示例与时间线行为；
  - `<名>.html`：`<template>` 包裹静态标记和样式，根节点 `#root` 带固定 `data-composition-id="<名>"`，背景保持透明以限制可见内容在舞台矩形内；
  - `<名>.mjs`：零外部网络依赖，仅使用宿主注入的 `gsap`、浏览器原生 SVG / Canvas / DOM 与 `motions/motion-utils.mjs`，导出符合 `modules.md` 唯一约定的 `init(root, { params, data, duration, gsap })` 并返回 `{ timeline, destroy }`（及可选 `ready` / `seek(t)`）。
- 视觉与排版基线：颜色和字体只读主题 token，卡片与面板遵循 `designs/designs.md` 的半透明透纸质感与 `1–2px` 线宽阶梯；SVG 舞台采用与像素宽高 `1:1` 的 `viewBox`；阅读文字 `>= 26px`、带 `data-text-role="ui"` 的界面辅助小字 `>= 20px`，长文案通过确定性字宽模型自动折行并撑开或缩放承载框，严禁文字出框或越出宿主区域。
