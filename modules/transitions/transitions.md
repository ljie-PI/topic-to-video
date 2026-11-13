# 转场

转场负责 **scene 之间的交接**：在切点遮盖或连接前后画面，让场景边界服务于叙事节奏。转场不是内容部件，不为每个 scene 单独复制一份内容，也不要求每个接缝都有显著动画。

统一采用规则见 [composition 基础指令第四部分](../../references/delegation/composition/base-instructions.md#四内容演绎与模板选择)：只在用户明确指定，或现有转场与当前 scene 交接特别匹配时采用。普通接缝、直接切换或自绘的简单衔接已经能表达清楚时，保持简单即可；**自由布局不强制使用转场**。

## 目录

| 转场 | 文档 / 文件 | 作用 | 层级 | 读的数据 |
|---|---|---|---|---|
| `tile-wipe` | `transitions/tile-wipe/tile-wipe.md`；`transitions/tile-wipe/` | 方格从一点扩散盖住切点，可以亮出预告卡片，再收回起点 | 10 | `VIDEO.cuts` |

## 选定后怎么接入

1. 阅读所选转场的具体模块文档，核对适用场景、挂载参数、数据形状和时间行为。
2. 把该模块的 HTML 与同目录 MJS 一起复制到视频工程的 `compositions/`，工程内文件名保持文档约定。
3. 按文档放置挂载点、设置 `data-composition-id` 与 z-index，并在工程 adapter 中调用 `init`、传入参数和数据、驱动返回的暂停 timeline。读取索引本身不等于采用转场。

## 时间约定

- `init` 的 `duration` 和返回 timeline 都使用本次挂载的**工程局部秒**：timeline 的 0 秒对应挂载点的 `data-start`。
- 常驻转场挂在 `data-start="0"`，`duration` 覆盖整片，因此局部秒等于视频秒；此时 `VIDEO.cuts[].at` 等数据时间使用视频秒，切点通常等于下一个场景的 `data-start`。
- 非零 `data-start` 的挂载必须把视频秒换算为相对该挂载起点的局部秒，再交给 `init`；`duration` 是这次挂载自身的时长，不是整片时长。
- 具体字段、切点前后覆盖时长和场景内容避让规则以所选转场文档为准。
