# 动态模块：topology-graph（分层架构与拓扑关系图）

**用于演绎系统分层架构、模块依赖网络、请求路由与局部焦点切换。**

1. 舞台内置 `1px` 微网格与细点阵底衬、`1.5px` `--c-border` 外框和半透明 `--c-card` 底板，透出 `#ground` 纸纹肌理，SVG `viewBox` 与像素尺寸 `1:1` 对齐。
2. 模块卡片采用 `1.35px` 细边框与端口锚点圆点，主标题（`>= 26px`）与模块职责说明（`>= 22px` UI）按确定性字宽模型自动折行并适配卡片高度。
3. 依赖连线在各自 `at` 时刻以 `pathLength="1"` 贝塞尔曲线生长，并附带沿曲线推进的信号脉冲圆点；关键路径（`emphasis`）使用 `1.85px` `--c-focus`（或语义色）突出层级。
4. 可选 `focusSequence` 按旁白节奏依次高亮当前讲解的子图节点并柔化其余层，支持正反向确定性 `seek`。

## 文件

- `motions/topology-graph/topology-graph.md`：本文档。
- `motions/topology-graph/topology-graph.html`：静态标记和样式。
- `motions/topology-graph/topology-graph.mjs`：导出 `init`（接口见 `modules.md` 的「模块初始化接口」）。
- `motions/motion-utils.mjs`：共用确定性文本测量、折行与 1:1 舞台工具（一同复制到工程 `compositions/`）。

## 依赖（来自设计主题，视频的 `index.html` 必须提供）

| 变量 | 用在哪里 |
|---|---|
| `--c-card` / `--c-surface` | 半透明舞台、模块节点底与分层标签底 |
| `--c-border` | 舞台外框（`1.5px`）、模块框（`1.35px`）、分层虚线与微网格（`1px`） |
| `--c-ink` / `--c-ink2` | 模块名称 / 职责说明、常规依赖连线 |
| `--c-focus` / `--c-focus-tint` | 关键路径连线、脉冲点、聚焦模块边框与浅底 |
| `--c-done` / `--c-positive` / `--c-warning` / `--c-danger` | 可选语义连线或模块状态强调 |
| `--font-sans` / `--font-mono` | 模块文字与标签字体 |
| `--motion-enter-duration` / `--motion-easing` | 默认入场时长与缓动 |

## 安装与挂载

1. 把 `motions/topology-graph/topology-graph.html`、`motions/topology-graph/topology-graph.mjs` 和 `motions/motion-utils.mjs` 一起复制到视频工程的 `compositions/`。
2. 在当前视觉 scene 的目标 content 区域挂载：
   - `data-composition-id="topology-graph"`，`data-composition-src="compositions/topology-graph.html"`；
   - `data-start` 为场景起点，`data-duration` 为场景时长。
3. 在工程 adapter 中调用 `init(root, { params, data, duration, gsap })`，按局部秒驱动返回的暂停 `timeline`。

## 参数（`init` 的 `params`）

| 参数 | 默认 | 说明 |
|---|---|---|
| `x`, `y` | `0, 0` | 舞台相对 `#root` 左上角的像素偏移 |
| `width`, `height` | 宿主像素宽高（回退 `1048, 788`） | 舞台像素尺寸，SVG 自动设置 `viewBox="0 0 width height"` |
| `title` | `""` | 可选架构图顶部标题（`>= 30px`） |
| `data` | `"topologyGraph"` | 工程数据（`window.VIDEO`）中对应的键名 |

## 数据（`init` 的 `data`，工程里通常来自 `window.VIDEO.topologyGraph`）

```js
topologyGraph: {
  layers: [
    { id: "edge", label: "接入层" },
    { id: "core", label: "编排核" },
    { id: "store", label: "存储层" },
  ],
  nodes: [
    { id: "gw", label: "API Gateway", detail: "鉴权与限流", layer: "edge", at: 0.2 },
    { id: "router", label: "任务调度器", detail: "DAG 拓扑分发", layer: "core", at: 0.9, emphasis: true },
    { id: "worker", label: "执行沙箱", detail: "隔离渲染进程", layer: "core", at: 1.2 },
    { id: "cache", label: "构件缓存", detail: "内容寻址存储", layer: "store", at: 2.0 },
  ],
  links: [
    { from: "gw", to: "router", label: "RPC", at: 0.7, emphasis: true },
    { from: "router", to: "worker", at: 1.5, emphasis: true },
    { from: "worker", to: "cache", at: 2.2 },
  ],
  focusSequence: [
    { nodeIds: ["gw", "router"], at: 1.0 },
    { nodeIds: ["router", "worker", "cache"], at: 2.3 },
  ],
}
```

- 也支持直接把 `nodes` 内嵌在 `layers[].nodes` 中，或为 `nodes[]` 提供归一化坐标 `x, y`（`0..1`）自定义自由拓扑位置。
- 所有 `at` 均为相对挂载点起点的**局部秒**。
