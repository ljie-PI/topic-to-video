# Patterns：画面形态建议库

patterns 是**按需参考库**，提供常见媒体与信息形态的摆法及动效候选。采用条件与借用记录统一见 [composition 基础指令第四部分](../../references/delegation/composition/base-instructions.md#四内容演绎与模板选择)：仅在用户明确指定，或已有构想与某个 pattern 的形态和触发信号特别匹配时定向查阅借用，否则自主构图。

每份 pattern 文档固定含：适用场景和触发信号 / 区域尺寸建议 / 横屏摆法 / 竖屏摆法 / 动效候选与应避免 / 用色 / 已有实现。可复用动态模块与 runtime 选型见 `motions/motions.md`，转场见 `transitions/transitions.md`。

## 媒体呈现（media/）

素材是画面主角时的摆法：

| pattern | 文档 | 一句话 |
| --- | --- | --- |
| media-first | `patterns/media/media-first.md` | 单张主图是核心证据，文字少量辅助 |
| video-first | `patterns/media/video-first.md` | 视频 clip 是主证据，文字只留短解释 |
| viewport-reveal | `patterns/media/viewport-reveal.md` | 极端比例素材用移动视口沿长轴展示 |
| band | `patterns/media/band.md` | 超宽素材以足够高的信息横带呈现 |
| detail-callout | `patterns/media/detail-callout.md` | 保留素材全貌，局部窗口 + 外置标注 |
| comparison | `patterns/media/comparison.md` | 两个及以上素材同屏或分时对比 |
| continuation | `patterns/media/continuation.md` | 同一张技术图深入拆解时的无过场连续镜头与分区 zoom |

## 信息形态（info/）

没有真实主素材、按 **SVG → WebGL → Three.js → GSAP** 优先级用视觉动画演绎 `content_plan` 时的信息结构参考（借用版式骨架时仍须把对象、关系或分步变化做成生动动画，不得退化成静态纯排版卡片）：

| pattern | 文档 | 适用信息形态 |
| --- | --- | --- |
| leaderboard | `patterns/info/leaderboard.md` | 排名榜单（Top N / 周榜） |
| product-card | `patterns/info/product-card.md` | 产品 / 项目 / 论文身份卡、章节标题卡 |
| big-number | `patterns/info/big-number.md` | 单点冲击性核心数字 |
| data-table | `patterns/info/data-table.md` | 结构化多行多列表格 |
| chart | `patterns/info/chart.md` | 趋势、分布、占比与数值对比图 |
| process-flow | `patterns/info/process-flow.md` | 步骤流程、时间线、状态机 |
| architecture | `patterns/info/architecture.md` | 分层系统架构图、依赖关系网络 |
| list-grid | `patterns/info/list-grid.md` | 并列列表、功能网格、多指标数据条 |
| comparison-matrix | `patterns/info/comparison-matrix.md` | 多维对比矩阵、单主体优缺点 |
| code-terminal | `patterns/info/code-terminal.md` | 代码块、终端输出、目录文件树 |
| callout-quote | `patterns/info/callout-quote.md` | 要点警示标注、原文引述、术语定义、问答 |

## 决定借用后怎么查

1. 带着已经构思的画面或具体问题，从 media/ 或 info/ 定位相关文档，只读匹配的条目。
2. 用「适用场景和触发信号」核对适用性；横 / 竖屏摆法与动效候选都可局部借用或改写，坐标仍以所选 layout 的区域表（`layouts/`）为准。
3. 「动效候选与应避免」只是本 pattern 的参考，不规定最终机制与 runtime；若「已有实现」列出了匹配的动态模块，可按需查阅 `motions/motions.md` 与对应模块文档决定直接借用或拷入工程改写。
4. 「用色」里的分主题写法覆盖在主题 token 之上；没有特殊覆盖时全部颜色只用主题 token（`designs/designs.md`）。
