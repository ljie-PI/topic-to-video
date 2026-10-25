# Pattern：process-flow（流程 / 时间线 / 状态机）

步骤、pipeline、用户旅程、发布时间线、状态流转。本文件是建议，不是规则。

## 适用场景和触发信号

- 旁白出现「第一、第二、然后、最后、步骤、链路、流程」→ 流程。
- 旁白出现「过去、现在、未来、从 X 到 Y、演进、版本、发布、时间线、历史、阶段、里程碑」→ 时间线。
- 旁白出现「状态、生命周期、重试、失败恢复、状态流转、agent loop」→ 状态机。
- 屏幕文本单元 `visual_role = "process_flow"` / `"timeline"` / `"state_machine"`；典型字段是 step label、输入、输出、时间点、状态。

## 区域尺寸建议

- 3–5 个节点最容易读；节点再多建议分页、分时或拆 scene。
- 每个节点放得下 label + 一行 detail；节点宽度不够时减节点数，不缩字号。

## 横屏摆法

- 流程：横向节点链或纵向步骤列均可，配 connector 线；状态机可用明确的状态块 + 转移箭头。
- 时间线：横向时间轴，当前阶段高亮。

## 竖屏摆法

- 优先纵向节点链 / 路径、分页或分时；避免 3 个以上横向窄节点。
- 状态机在竖屏用纵向堆叠的状态块 + 向下的转移箭头。

## 动效候选与应避免

候选：ordered node reveal + connector draw（节点按旁白顺序出现，连线随之生长）、MotionPath follower、camera follow；状态机用 explicit state transitions、active-path progression、shared element / FLIP。

避免：所有节点与连线一次全亮；只有装饰粒子不表现状态变化。

## 用色

- 通用：默认节点与连线用 `--c-border` / `--c-ink2`；当前节点用 `--c-focus` / `--c-focus-tint`；失败 / 等待用真实语义 token（`--c-danger` / `--c-warning`）。
- 各主题的具体覆盖写法已从主题文档迁到本 pattern：

| 主题 | 流程 / 时间线用色 |
| --- | --- |
| default | 默认节点与连线用 `border` / `ink2`；当前节点用 `focus` / `focus-tint`；失败 / 等待用真实语义 token。 |
| dawn | 节点正文 Primary；当前节点用 Pine / Primary + Gold 点缀；完成节点 Pine；连接线 Foam / Iris。 |
| moon | 节点正文 Primary / Secondary；当前节点 Gold；active tech 节点 Iris；失败状态 Love；连接线 Foam。 |
| github | 当前步骤 Blue；成功节点 Success；失败节点 Danger；完成节点 Done；连接线 `#D1D9E0` + 语义色 marker。 |
| producthunt | launch step 可用 `#C8392F` 文本 / 线 + `#FF6154` 外形点缀；register / onboarding 用蓝；maker verified 用 `#046B50`。 |

## 已有实现

尚无。
