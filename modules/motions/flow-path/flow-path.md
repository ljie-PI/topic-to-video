# 动态模块：flow-path（流程与状态流转）

**用有向节点与渐进描边连线演绎步骤链路、时间线或状态机流转。**

1. 舞台铺设半透明 `--c-card` 面板与 `1px` 微网格底衬，透出底层 `#ground` 纸纹肌理，SVG `viewBox` 与宿主像素 `1:1` 对齐。
2. 每个节点在各自的语音时刻 `at` 渐进浮现并点亮为当前焦点态（`--c-focus` `1.75px` 边框 + `--c-focus-tint` 浅底）。
3. 指向下一节点的 `1.75px` 有向连线通过 `pathLength="1"` 与 `strokeDashoffset` 从源端口生长至目标端口；下一节点激活后，前一常规节点自动沉淀为已完成态（`--c-done` 标记与 `1.35px` 细框）。
4. 根据容器宽高比（或显式 `direction`）自动切换横屏横向链路（多节点自动折为双行蛇形链路以保证框宽）与竖屏纵向堆叠链路，长标题与说明按确定性字宽模型自动折行并撑开节点框。

## 文件

- `motions/flow-path/flow-path.md`：本文档。
- `motions/flow-path/flow-path.html`：静态标记和样式。
- `motions/flow-path/flow-path.mjs`：导出 `init`（接口见 `modules.md` 的「模块初始化接口」）。
- `motions/motion-utils.mjs`：共用确定性文本测量、折行与 1:1 舞台工具（一同复制到工程 `compositions/`）。

## 依赖（来自设计主题，视频的 `index.html` 必须提供）

| 变量 | 用在哪里 |
|---|---|
| `--c-card` / `--c-surface` | 半透明舞台与节点底色、步骤编号胶囊底 |
| `--c-border` | 舞台外框（`1.5px`）、默认节点外框（`1.35px`）与微网格（`1px`） |
| `--c-ink` / `--c-ink2` | 节点主标题（`>= 26px`）/ 补充说明与连线标签（`>= 22px` UI） |
| `--c-focus` / `--c-focus-tint` | 当前激活节点边框、连线主色与高亮浅底 |
| `--c-done` | 已讲完节点的完成态圆点与勾标 |
| `--c-positive` / `--c-warning` / `--c-danger` | 可选显式状态语义（成功 / 警示 / 失败状态机分支） |
| `--font-sans` / `--font-mono` | 正文与编号字体 |
| `--motion-enter-duration` / `--motion-easing` | 默认入场时长与缓动 |

## 安装与挂载

1. 把 `motions/flow-path/flow-path.html`、`motions/flow-path/flow-path.mjs` 和 `motions/motion-utils.mjs` 一起复制到视频工程的 `compositions/`（保持文件名 `flow-path.html`、`flow-path.mjs`、`motion-utils.mjs`）。
2. 在当前视觉 scene 的目标 content 区域挂载（可直接将宿主元素定位到该区域，或挂全画布并通过 `params` 传入 `x`、`y`、`width`、`height`）：
   - `data-composition-id="flow-path"`，`data-composition-src="compositions/flow-path.html"`；
   - `data-start` 为场景起点，`data-duration` 为场景时长。
3. 在工程 adapter 中调用 `init(root, { params, data, duration, gsap })` 并按局部秒驱动返回的暂停 `timeline`。

## 参数（`init` 的 `params`）

| 参数 | 默认 | 说明 |
|---|---|---|
| `x`, `y` | `0, 0` | 舞台相对 `#root` 左上角的像素偏移（全画布挂载时可传 content 区域的 `x, y`） |
| `width`, `height` | 宿主像素宽高（回退 `1048, 788`） | 舞台像素尺寸，SVG 自动设置 `viewBox="0 0 width height"` |
| `direction` | `"auto"` | `"auto"`（竖长或窄于 `760px` 时纵向堆叠，否则横向排布；横向节点过多时自动折双行蛇形）、`"horizontal"` 或 `"vertical"` |
| `title` | `""` | 可选舞台顶部标题（`>= 30px`），留空不占高度 |
| `data` | `"flowPath"` | 工程数据（`window.VIDEO`）中对应的键名，由 adapter 取出后传入 `init` 的 `data` |

## 数据（`init` 的 `data`，工程里通常来自 `window.VIDEO.flowPath`）

```js
flowPath: {
  nodes: [
    { id: "parse", label: "解析输入源码", detail: "提取 AST 与依赖边", at: 0.2 },
    { id: "check", label: "静态契约校验", detail: "核对区域与字号下限", at: 1.4 },
    { id: "render", label: "确定性帧编码", detail: "输出 H.264 成片", at: 2.8, status: "positive" },
  ],
  // 可选：省略时默认按 nodes 顺序串联相邻节点
  edges: [
    { from: "parse", to: "check", label: "AST", at: 1.1 },
    { from: "check", to: "render", label: "通过", at: 2.5 },
  ],
}
```

- `nodes[].at` 与 `edges[].at` 为相对挂载点起点的**局部秒**。
- `nodes[].status` 可选：`"default"`（默认随焦点推进为激活 → 完成）、`"focus"`、`"done"`、`"positive"`、`"warning"`、`"danger"`。
