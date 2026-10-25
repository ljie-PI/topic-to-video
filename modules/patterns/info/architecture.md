# Pattern：architecture（架构图 / 关系图）

系统结构、模块分层、技术栈、依赖关系、生态网络。本文件是建议，不是规则。

## 适用场景和触发信号

- 旁白解释「系统、模块、层、pipeline、输入输出、组件」→ 架构图。
- 旁白解释「关系、依赖、生态、传播、连接、谁影响谁」→ 关系 / 网络图。
- 屏幕文本单元 `visual_role = "architecture_diagram"` / `"network_graph"`；典型字段是模块、层、数据流、节点、边。

## 区域尺寸建议

- 模块数以能放得下 label + 一句话为准；超过一屏的图建议 focus window 或拆 scene。
- 分层架构用 grouped columns 或 layered bands；关系图只画与旁白相关的子图，不画 dense full graph。

## 横屏摆法

- grouped columns、layered bands、readable clusters：按层或按组排布，关键路径用强调色。
- 讲到哪一层 / 哪个模块时高亮，其余降视觉权重。

## 竖屏摆法

- 模块层级、focus window 或 primary path；避免 dense full graph 和横向多列。
- 一次只展开一条主路径，其余模块收起到相邻层级。

## 动效候选与应避免

候选：layer assemble（逐层拼合）、primary-path reveal（关键路径生长）、depth scatter、camera journey、rack focus。

避免：dense full diagram 统一 scale pop；全节点同速漂浮或呼吸；装饰性连线生长不对应真实依赖。

## 用色

- 通用：中性模块用 `--c-surface` / `--c-border`；关键路径用 `--c-focus`；状态节点才用语义色。
- 各主题的具体覆盖写法已从主题文档迁到本 pattern：

| 主题 | 架构图用色 |
| --- | --- |
| default | 中性模块用 `surface` / `border`；关键路径用 `focus`；状态节点才用语义色。 |
| dawn | 模块边线用 Foam / Pine；依赖关系用 Iris；关键路径用 Pine，Gold 只做小 marker。 |
| moon | 模块边线 Foam / Iris；关键路径 Iris；背景结构线 `#44415a`；Pine 仅作大形状或粗线。 |
| github | 模块边线 Blue / Teal；dependency 用 Teal；completed path Done；risk edge Danger。 |
| producthunt | product / CTA 节点用 `#C8392F` 文本或线，用户 / register 蓝，maker / partner 用 `#046B50`；正文 Primary。 |

## 已有实现

尚无。
