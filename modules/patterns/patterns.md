# Patterns：画面形态建议库

patterns 是**按需参考库**，提供常见媒体和信息形态的摆法与动效候选，不是 scene 分类表或必选菜单。查阅条件与借用记录见 [composition 基础指令第四部分](../../references/delegation/composition/base-instructions.md#四内容演绎与模板选择)；每个 scene 最终以旁白语义、素材实际情况和所选 layout 的区域为准。

每份 pattern 文档都有同样的小节：适用场景和触发信号 / 区域尺寸建议 / 横屏摆法 / 竖屏摆法 / 动效候选与应避免 / 用色 / 已有实现。需要具体动效参考时可查 `motion.md`；使用转场组件时读 `components/transitions/tile-wipe/tile-wipe.md`。

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
| continuation | `patterns/media/continuation.md` | 相邻 scene 围绕同一素材连续讲解 |

## 信息形态（info/）

没有主素材、靠排版和数据承担叙事时的形态：

| pattern | 文档 | 覆盖的 visual_role |
| --- | --- | --- |
| leaderboard | `patterns/info/leaderboard.md` | `leaderboard` |
| product-card | `patterns/info/product-card.md` | `product_card` / `title` / `section_divider` |
| big-number | `patterns/info/big-number.md` | `big_number` |
| data-table | `patterns/info/data-table.md` | `data_table` |
| chart | `patterns/info/chart.md` | `chart` |
| process-flow | `patterns/info/process-flow.md` | `process_flow` / `timeline` / `state_machine` |
| architecture | `patterns/info/architecture.md` | `architecture_diagram` / `network_graph` |
| list-grid | `patterns/info/list-grid.md` | `list` / `feature_grid` / `data_block` / `metric_strip` |
| comparison-matrix | `patterns/info/comparison-matrix.md` | `comparison_matrix` / `pros_cons` |
| code-terminal | `patterns/info/code-terminal.md` | `code_block` / `terminal_block` / `file_tree` |
| callout-quote | `patterns/info/callout-quote.md` | `callout` / `quote` / `definition` / `qa` |

## 决定借用后怎么查

1. 带着已经构思的画面或具体问题，从 media/ 或 info/ 定位相关文档，只读匹配的条目。
2. 用「适用场景和触发信号」核对适用性；横 / 竖屏摆法与动效候选都可局部借用或改写，坐标仍以所选 layout 的区域表（`layouts/`）为准。
3. 「动效候选与应避免」只是本 pattern 的参考，不要求继续查阅 `motion.md`，也不规定最终机制与 runtime。
4. 「用色」里的分主题写法覆盖在主题 token 之上；没有特殊覆盖时全部颜色只用主题 token（`designs/designs.md`）。
