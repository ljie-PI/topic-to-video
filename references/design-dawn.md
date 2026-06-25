# Style Hint — Rosé Pine Dawn × Notion 手绘风

> Phase 8 style hint。按本文件执行 mood、配色、排版、形状和动效约束。

## 配色（只用以下颜色）

**Backgrounds**
- 主画布：`#faf4ed`（warm cream）
- 卡片表面：`#fffaf3`（近白的温色）
- Elevated overlay：`#f2e9e1`（柔和的桃米色）

**Text**
- Primary / 标题 / 正文：`#575279`（柔紫灰；正文安全）
- Secondary / 大号辅助文字：`#797593`（淡薰衣草色；只用于中 / 大号说明、meta，不用于小号正文）
- Subtle / 仅装饰：`#9893a5`（禁止用于正文）

**Semantic accents / 使用场景**

按信息语义使用 accent；允许同一 scene 出现多个语义色；禁止随机换色；禁止同一元素叠加多种 accent。

- Foam `#56949f`（海水青）—— info、neutral data、外置信息区标记、chart 次线；用于线、icon、tag，不承载小号正文。
- Love `#b4637a`（柔玫红）—— risk、warning、反常识、失败 / fade 状态；用于 callout 边线、badge、强调词，不承载小号正文。
- Iris `#907aa9`（沉紫）—— hint、secondary relation、quote / definition 标记、loop / iteration 主题元素；用于节点、连接线、eyebrow。
- Gold `#ea9d34`（琥珀）—— warm highlight、手绘圈点、当前步骤辅助 marker；禁止单独承载数字、文字或唯一状态信号。
- Rose `#d7827e`（柔珊瑚）—— warm callout、now、human note、CTA-like emphasis；用于柔和强调，不做大面积底色。
- Pine `#286983`（深青）—— readable accent text、success / solid、关键词、冷色对比；当 accent 必须承载可读文字时优先使用 Pine。

**Borders / 分割线**：`#cecacd`（暖灰）

### 主题专属标记

使用手绘 tag、badge、圈点、短 underline 和外置信息区左线。按下方语义色使用；不要发明新颜色。

### 颜色使用场景

| 场景 | 前景 | 背景 / 表面 | 线 / 标记 | 规则 |
|------|------|-------------|-----------|------|
| Canvas / scene base | `#575279` | `#faf4ed` | `#cecacd` | 正文默认用 Primary；`#797593` 不承载小号正文。 |
| Surface / panel / card | `#575279` | `#fffaf3` | `#cecacd` | 卡片平面化，内部文字尽量使用 Primary。 |
| Elevated overlay / soft band | `#575279` | `#f2e9e1` | `#cecacd` | 适合 callout、步骤节点、figure 外置信息区。 |
| Muted metadata / decorative chrome | `#797593` 或 `#9893a5` | 任一背景 | `#cecacd` | `#9893a5` 只用于装饰；`#797593` 只用于中 / 大号 meta。 |
| Info / neutral data | `#575279` 或 `#286983` | `#fffaf3` / `#f2e9e1` | `#56949f` | Foam 做边线、icon、chart stroke；正文仍用 Primary / Pine。 |
| Success / solid / positive | `#286983` | `#fffaf3` | `#286983` | 成功语义使用 Pine。 |
| Warning / risk | `#575279` / `#286983` | `#fffaf3` / `#f2e9e1` | `#b4637a` + 可选 `#ea9d34` 点缀 | Love 承载风险语义；Gold 只做辅助圈点或背景小标。 |
| Danger / urgent | `#575279` | `#fffaf3` | `#b4637a` | 不用大红；用 Love 的边线、badge、短强调表达。 |
| Emphasis / important number | `#286983` 或 `#575279` | 透明 / `#fffaf3` | `#ea9d34` 点缀 | 重要数字用 Pine / Primary；Gold 只做 underline、dot、sketch circle 或小面积辅助。 |
| Citation / quote / human note | `#575279` | `#fffaf3` | `#907aa9` 或 `#d7827e` | quote 标记用 Iris / Rose，正文仍保持 Primary。 |
| CTA / now marker | `#575279` | `#fffaf3` | `#d7827e` | Dawn 的 CTA 只做柔和标记，不做营销式按钮。 |
| Tags / badges / progress | `#575279` 或 `#286983` | `#fffaf3` / `#f2e9e1` | `#56949f` / `#907aa9` / `#ea9d34` | tag、badge、rank、progress step 用短文本 + 小 marker；不要随机换色。 |
| Callout boxes / role surfaces | `#575279` | `#fffaf3` / `#f2e9e1` | 按语义选 accent 左线 | callout、definition、QA、quote 都用浅表面 + 语义线，正文保持 Primary。 |
| Code / terminal / file tree | `#575279` | `#fffaf3` | `#286983` / `#907aa9` | 代码高亮用 Pine / Iris 的短 token 或下划线。 |
| Diagram connector / graph node | `#575279` | 透明 / `#f2e9e1` | `#56949f` / `#907aa9` / `#286983` | 连接线可多语义，但同一节点不要叠多色。 |
| Media annotation | `#575279` | `#fffaf3` / 外置信息区 | `#ea9d34` / `#56949f` | 只在素材外部解释；不要压住图片 / 视频关键区域。 |
| Subtitle | `#575279` | shrink-to-fit 浅色遮罩 | `#cecacd` | 字幕保持可读；禁止用 accent 作字幕正文色。 |

### 标题配色与高亮 box

**标题**

- 正文标题维持 `#575279`；使用手写字体、字号和留白。
- 关键词可用 Pine `#286983` 承载可读 accent text；Rose / Iris 可做 eyebrow、短 underline 或边线。
- Gold `#ea9d34` 只做手绘圈点、dot、sketch underline 等辅助 marker，不单独承载文字。

**高亮 box / callout**

- 使用 `#fffaf3` 或 `#f2e9e1` 浅表面 + 语义色左线 / 角标。
- callout 正文保持 `#575279`；需要可读 accent text 时用 Pine。
- 不做满屏 tint，不做厚阴影，不用 accent 填满整个卡片。

### `visual_role` 色彩覆盖

| `visual_role` | 配色方式 |
| --- | --- |
| `title` / `product_card` / `section_divider` | Primary 标题 + Rose / Iris eyebrow；身份信息可用 Pine 短 label。 |
| `leaderboard` / `big_number` / `data_block` / `metric_strip` | 数字用 Primary 或 Pine；当前排名 / 重点数字可配 Gold 小点缀；变化趋势用 Foam / Love 线。 |
| `data_table` / `chart` | 表格正文 Primary；表头 Secondary 大号；highlight cell 用 Pine / Love / Foam 线，Gold 只做非唯一辅助点；series 用 Foam / Pine / Iris。 |
| `timeline` / `process_flow` / `state_machine` | 节点正文 Primary；当前节点用 Pine / Primary + Gold 点缀；完成 / solid 节点 Pine；连接线 Foam / Iris。 |
| `architecture_diagram` / `network_graph` | 模块边线用 Foam / Pine；依赖关系用 Iris；关键路径用 Pine，Gold 只做小 marker。 |
| `comparison_matrix` / `pros_cons` | 双侧对比用 Pine vs Love；中性维度 Primary；优缺点标签用短 badge，不给整列大面积上色。 |
| `list` / `feature_grid` | item label Primary；bullet / index 用 Foam / Rose / Pine 按语义区分；detail 用 Primary 或大号 Secondary。 |
| `callout` / `definition` / `qa` | callout 用 `#fffaf3` 或 `#f2e9e1` 底 + 语义色左线；definition 用 Iris；QA 的 Q 用 Foam、A 用 Pine。 |
| `code_block` / `terminal_block` / `file_tree` | panel 底 `#fffaf3`；路径 / 命令重点用 Pine；注释 / prompt 用 Iris；warning 输出用 Love 或 Gold marker。 |
| `annotated_media` | 标注必须在素材外置信息区；pin / arrow 用 Gold / Foam；说明文字 Primary。 |
| `quote` | 引号 / source 用 Rose 或 Iris；正文 Primary；不要用 Subtle 承载 quote 正文。 |

### 对比度 guardrails

- 正文必须达到 4.5:1；大号文字、icon、chart stroke、粗线 marker 必须达到 3:1；低于 3:1 的颜色只能做装饰。
- `#575279` 可在 Dawn 的 base / card / overlay 上承载正文和标题。
- `#797593` 只用于中 / 大号辅助文字和 metadata；小号正文统一用 `#575279`。
- `#9893a5` 只用于装饰。
- Pine `#286983` 是 Dawn 中可承载可读 accent text 的首选；Foam / Love / Iris 只用于线、icon、tag、marker 或大号短字。
- Gold `#ea9d34` 只做辅助点缀、手绘圈点或非唯一 marker；禁止单独承载数字、文字、线条或 UI 状态。
- Love `#b4637a` 与 Rose `#d7827e` 不在同一 scene 同时作状态信号；Love 优先配 ⚠ / 边线区分，positive CTA 文字优先用 Pine，Rose 只做柔和 marker / underline。

## 排版

| 用途 | 字体 | 字重 | 备注 |
|------|------|------|------|
| 中文标题 | `MaShanZheng` | 400 | 笔锋感强 |
| 中文正文 | `MaShanZheng` | 400 | 同字体，字号更小 |
| 中文字幕 | `LongCang` | 400 | 草书 |
| 中文装饰强调 | `ZhiMangXing` | 400 | 可选 |
| 英文 / 数字 —— 强调 | `Caveat` | 700 | 手写马克笔感 |
| 英文 / 数字 —— 正文 | `PatrickHand` | 400 | 随意手写体 |

**绝不要用 Caveat 或 PatrickHand 显示中文字符**。中文一律使用 CJK 字体。

混排中文 + 拉丁字符时，显式指定项目字体家族。

## 视频尺寸（覆盖网页常规尺寸）

| 元素 | 1920×1080 | 1080×1440 | 1080×1920 |
|------|-----------|-----------|-----------|
| Hero 标题 | 100-160px | 80-130px | 90-140px |
| Section 标题 | 60-90px | 50-76px | 56-80px |
| 正文 | 32-56px | 28-46px | 30-48px |
| 数据 label | 22-32px | 22-30px | 22-32px |
| 字幕 | 35px | 35px | 35px |
| Padding（.scene） | 90px 140px | 90px 80px | 90px 70px |

## 形状风格

- 平面、有质感的卡片和 tag。
- 圆角 label 在服务于信息设计时可以使用。
- 避免厚重阴影；保持手绘氛围轻盈、安静。

## 图标

- 使用手绘感短标记、圆点、圈线、箭头或 tag；不要引入新色板。
- 图标 / marker 只服务信息层级；不要把装饰图标铺满背景。

## 动效

- 每个装饰元素：环境感 breathe / drift / rotate（`sine.inOut yoyo`，有限重复）
- 每次入场：每个 scene 用 3+ 种不同 ease（混用 `expo.out`、`back.out(1.7)`、`power3.out`、`sine.out`）
- 除最终 scene 外，**不要**用 exit 动画
- Scene 转场由 hyperframes 的 track 切换隐式处理
- 标题先入场，辅助元素 stagger 跟进

## 不要做

- ❌ 不要用 shadow、gradient、glow、neon
- ❌ 不要用配色之外的高饱和颜色
- ❌ 不要把 `#9893a5` 用在正文（对比度）
- ❌ 不要把 `#797593` 当小号正文；小号正文统一用 `#575279`
- ❌ 不要让 `#ea9d34` 单独承载数字、文字、线条或 UI 状态；只做辅助点缀
- ❌ 不要用拉丁手写字体显示中文
- ❌ 不要在同一个元素上叠加多种 accent 颜色
- ❌ 不要为了“丰富”而给无语义差异的同类元素随机换 accent 色
- ❌ 不要把 accent 色作为大面积背景填充
