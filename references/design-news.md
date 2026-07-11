# Style Hint — Kraken × 新闻洞察 / 时事分析

> Phase 8 style hint。按本文件执行「干净可信的新闻编辑风」、配色、排版、形状和动效约束。
> 配色提取自 Kraken DESIGN.md（白底 + 品牌紫）。
> 姊妹预设：`references/design-dawn.md`（手绘）、`references/design-moon.md`（深色技术）、`references/design-github.md`（GitHub）、`references/design-producthunt.md`（PH 品牌）、`references/design-tech.md`（终端技术）。

适用场景：新闻解读、时事分析、热点复盘、深度报道、媒体洞察、行业动态。整体气质是**可信、克制、编辑感**——白底、品牌紫做强调、冷灰承载正文、语义色只表信息角色。

## 配色（只用以下颜色）

**Backgrounds**
- 主画布：`#FFFFFF`（白）
- 次级面板 / 段落交替 / hero band：`#F5F5F8`（冷灰浅底）
- 紫色 subtle band / 强调区：`#F1ECFE`（品牌紫 16% 感的浅底，用于 hero eyebrow band、重点 callout 底）
- Chip / 分段控件：`#EDEDF2`

**Text**
- Primary / 标题 / 正文：`#101114`（近黑）
- Secondary / 次级正文 / 副标 / 导语：`#686B82`（冷灰）
- Muted / metadata / 时间戳 / 来源标（**不要**用于正文）：`#9497A9`（银蓝）

**Borders / 分割线**
- 卡片 / 标准 1px：`#DEDEE5`
- 弱分割线：`#EDEDF2`

**Semantic accents / 使用场景**

按新闻信息语义使用 accent；允许同一 scene 出现多个语义色；禁止随机换色；禁止同一元素叠加多种 accent。

- 品牌紫 `#7132F5` —— brand、链接、section eyebrow、标题关键词、来源 marker、CTA 外形、重点数字标记。**不作为小号正文色**（小号紫色文字改用可读紫 `#5741D8`）。
- 可读紫 `#5741D8` —— 需要紫色语义**文字**时使用（link 文字、eyebrow 文字、outlined 标签文字）；deep `#5B1ECF` 作最深强调。
- 紫 subtle `rgba(113,50,245,0.12)` —— 紫色 chip / callout 的浅底。
- Success 绿 marker `#149E61` —— 利好、正向、确认、verified、上涨数据的 marker / badge 外形。
- 可读绿字 `#026B3F` —— success 语义**文字**、利好读数说明；subtle 底 `#E7F6EF`。
- **Danger 红（为新闻语义派生，非 Kraken 原生）** —— 利空、风险、突发、下跌、争议、否定。marker `#E5484D`；可读红字 `#C81E1E`；subtle 底 `#FDECEC`。
- **Warning 琥珀（为新闻语义派生，非 Kraken 原生）** —— 存疑、待核实、注意、悬而未决。marker `#E3A008`；可读琥珀字 `#8A5A00`；subtle 底 `#FBF1D6`。

> 派生红 / 琥珀是为承载完整新闻语义而加入的最小扩展；它们与 Kraken 品牌紫 / 绿保持相同的「亮色作 marker、深色作可读文字」纪律，不引入其它色相。

### 主题专属标记

使用 section eyebrow（紫色 uppercase 小标签）、来源 pill（`来源 / Source`）、时间戳、利好利空箭头（▲ 绿 / ▼ 红）、引述卡左线、数据 callout。列多条新闻时可用紫色序号 marker。

### 颜色使用场景

| 场景 | 前景 | 背景 / 表面 | 线 / 标记 | 规则 |
|------|------|-------------|-----------|------|
| Canvas / scene base | `#101114` / `#686B82` | `#FFFFFF` | `#DEDEE5` | 标题 Primary，正文 Primary / Secondary；Muted 只做 metadata。 |
| Band / section alternate | `#101114` / `#686B82` | `#F5F5F8` | `#DEDEE5` | hero band / 段落交替，不做饱和紫底。 |
| 紫色强调 band / eyebrow | `#5741D8` | `#F1ECFE` | `#7132F5` | 仅用于 eyebrow、重点 callout 底；不铺满屏。 |
| Surface / card | `#101114` / `#686B82` | `#FFFFFF` | `#DEDEE5` | 1px 边；最多 whisper 阴影（见形状）。 |
| Chip / control | `#101114` | `#EDEDF2` / 紫 subtle | `#DEDEE5` | chip 文字配套色；不混用多套 chip 色。 |
| Link / 来源 / 引用标记 | `#5741D8` | 透明 / `#F1ECFE` | `#7132F5` | 链接与来源用紫；长说明文字用可读紫或 Primary。 |
| 利好 / 正向 / verified | `#026B3F` | `#E7F6EF` / `#FFFFFF` | `#149E61` | tint 底正文用 `#026B3F`；`#149E61` 只用于白底短 label、icon、▲。 |
| 利空 / 风险 / 突发 | `#C81E1E` | `#FDECEC` / `#FFFFFF` | `#E5484D` | 风险 / 下跌 / 争议用红 callout 或红色短标记与 ▼。 |
| 存疑 / 待核实 / 注意 | `#8A5A00` | `#FBF1D6` | `#E3A008` | 未核实信息、悬念用琥珀 callout / marker，不与利空红混用。 |
| Neutral / metadata / 时间戳 | `#101114` / `#9497A9` | `#F5F5F8` | `#DEDEE5` | promoted / 时间戳用 Muted，但不承担正文。 |
| Big number / 数据 callout | `#101114` / mono；涨跌用绿 / 红 | `#FFFFFF` / `#F5F5F8` | `#7132F5` / `#149E61` / `#E5484D` | 数字用 mono + tabular-nums；涨用绿、跌用红；rank marker 用紫。 |
| Timeline / 事件流 | 当前节点 `#5741D8` | `#FFFFFF` / `#F5F5F8` | `#DEDEE5` + 语义色 marker | 进行中用紫，已确认用绿，风险节点用红。 |
| Data table / chart | 表格正文 `#101114` / `#686B82` | highlight cell 用 callout tint | `#7132F5` / `#149E61` / `#E5484D` | series 用紫 / 绿 / 红 / 冷灰；不给整列饱和底。 |
| Quote / 引述 | quote 正文 `#101114` | `#F5F5F8` / `#F1ECFE` | `#7132F5` 左线 | 引述用紫色左线卡；source 用 Secondary / Muted。 |
| Callout boxes / role surfaces | callout text 色 | callout tint | callout border | callout、definition、QA 优先用下方三件套，不裸用紫色小字正文。 |
| Code / 数据块 | `#101114` / `#686B82` | `#F5F5F8` | `#5741D8` / `#026B3F` / `#C81E1E` | 命令 / 数据用 mono；状态用绿 / 红短 marker。 |
| Media annotation | `#101114` / callout text | 素材外部信息区 | 语义 callout border | 不把 label / callout 压在素材关键区域。 |
| Subtitle | `#101114` 或 `#FFFFFF` | shrink-to-fit 遮罩 | `#DEDEE5` | 字幕按画面背景选高对比，不用裸 accent 正文色。 |

### 标题配色与高亮 box

画布保持白 / 浅灰，标题与 callout 按真实语义上色：

**标题**
- 正文标题维持 `#101114`。
- Hero 可坐落在浅色 band 上：中性 `#F5F5F8`，或紫色 subtle `#F1ECFE`。
- 标题关键词用品牌紫 `#7132F5` 上色（其余字保持 `#101114`）；利好关键词可用 `#026B3F`，风险关键词用 `#C81E1E`。
- Section eyebrow（uppercase 小标签）：紫色文字 `#5741D8` + `#F1ECFE` 底做成 pill。

**高亮 box / callout**（小卡，**不是**满屏背景）—— 底 / 1px 边 / 文字 三件套：

| 语义 | 底 | 边 | 文字 |
| --- | --- | --- | --- |
| 重点 / 洞察（紫） | `#F1ECFE` | `#7132F5` | `#5741D8` |
| 利好 / 正向（绿） | `#E7F6EF` | `#149E61` | `#026B3F` |
| 利空 / 风险（红，派生） | `#FDECEC` | `#E5484D` | `#C81E1E` |
| 存疑 / 注意（琥珀，派生） | `#FBF1D6` | `#E3A008` | `#8A5A00` |
| 中性（chip） | `#F5F5F8` | `#DEDEE5` | `#101114` |

裸 accent 用于 link、icon、tag、badge、marker、大号数字；解释性正文或 callout 内容使用上表的底 / 边 / 文字三件套。

### `visual_role` 色彩覆盖

| `visual_role` | 配色方式 |
| --- | --- |
| `title` / `product_card` / `section_divider` | Primary 标题 + 紫色 eyebrow；关键词 / 来源用紫。 |
| `leaderboard` / `big_number` / `data_block` / `metric_strip` | 数字 Primary / mono；涨 / 利好用绿，跌 / 利空用红；rank / link 用紫；存疑数值用琥珀。 |
| `data_table` / `chart` | 表格正文 Primary / Secondary；highlight cell 用 callout tint；series 用紫 / 绿 / 红 / 冷灰。 |
| `timeline` / `process_flow` / `state_machine` | 进行中 紫；确认节点 绿；风险节点 红；待核实 琥珀；连接线 `#DEDEE5` + 语义 marker。 |
| `architecture_diagram` / `network_graph` | 关系线 紫 / 冷灰；风险边 红；正文 Primary。 |
| `comparison_matrix` / `pros_cons` | 正向 绿，风险 红，注意 琥珀；正文 Primary / Secondary；不给整列饱和底。 |
| `list` / `feature_grid` | item label Primary；bullet / 序号按语义用紫 / 绿 / 红 / 琥珀；detail 用 Secondary。 |
| `callout` / `definition` / `qa` | 优先用五套 callout 三件套；definition 用紫；QA 的 Q 用紫，A 用 Primary / 绿。 |
| `code_block` / `terminal_block` / `file_tree` | panel 用 `#F5F5F8`；命令 / 数据用 mono；success 绿、error 红、hint 紫。 |
| `annotated_media` | 标注外置；pin / border 用紫 / 琥珀 / 红；解释文字用 callout text 或 Primary。 |
| `quote` | quote 正文 Primary；source Secondary / Muted；引述卡用紫色左线或紫 callout tint。 |

### 对比度 guardrails

- 正文必须达到 4.5:1；大号文字、icon、chart stroke、粗线 marker 必须达到 3:1；低于 3:1 的颜色只能做装饰。
- Primary `#101114` 和 Secondary `#686B82` 可在白 / 浅灰底上承载正文；Muted `#9497A9` 只做 metadata、装饰或弱 chrome。
- 品牌紫 `#7132F5` 是 brand / link / marker 色，不作为小号正文色；小号紫色文字用可读紫 `#5741D8` 或 deep `#5B1ECF`。
- Success 绿 `#149E61` 只用于白底短 label / icon / ▲；tint 底正文用 `#026B3F`。
- 派生红 / 琥珀同理：亮色（`#E5484D` / `#E3A008`）作 marker / ▼；可读文字用 `#C81E1E` / `#8A5A00`。
- 裸 accent 主要用于链接、icon、tag、marker、大号数字；长说明文字使用对应 callout text 色。

## 排版

中文字体复用 **Moon 预设**（`references/design-moon.md`）的确定性 CJK 字体，经 `scripts/fonts-download.sh <target_dir> moon` 预置；拉丁品牌字体可选。

| 用途 | 字体 | 字重 | 备注 |
| --- | --- | --- | --- |
| 中文标题 / Hero | `NotoSansSC` | 700 | 引自 Moon；紧排显编辑感 |
| 中文 section 标题 | `NotoSansSC` | 600 | |
| 中文正文 / 导语 | `NotoSansSC` | 400 | |
| 中文字幕 | `NotoSansSC` | 500 | |
| 数字 / 数据 / 英文 / 来源 | `IBMPlexMono` | 400 / 600 | 涨跌数据、时间、来源域名 |
| 拉丁品牌显示（可选） | `IBM Plex Sans` | 600 / 700 | 仅当 workspace 提供该字体时用于纯英文 hero / 标签；无则回退 `IBMPlexMono` |

**绝不要用拉丁品牌字体显示中文**。中文一律走 `NotoSansSC`。**全部数据读数必须** `font-variant-numeric: tabular-nums`。

## 视频尺寸（覆盖网页常规尺寸）

| 元素 | 1920×1080 | 1080×1440 | 1080×1920 | 字重 |
| --- | --- | --- | --- | --- |
| Hero 标题 | 120-160px | 100-138px | 108-148px | 700 |
| Section 标题 | 60-84px | 52-72px | 56-78px | 600 |
| 导语 / 副标 | 36-46px | 32-40px | 34-44px | 400 |
| Section eyebrow（uppercase） | 22-28px | 22-26px | 22-28px | 600 |
| Big number / 涨跌读数（mono） | 56-80px | 48-66px | 52-70px | 600 |
| Meta（来源、时间、tag） | 24-30px | 22-28px | 24-30px | 400 |
| 字幕 | 35px | 35px | 35px | 500 |
| Padding（.scene） | 90px 140px | 90px 80px | 90px 70px | — |

## 形状风格

- 卡片 1px 边框（`#DEDEE5`）；圆角统一：卡片 12px、按钮 12px（**非 pill**）、chip / 标签 8px、缩略图 8px。
- 阴影极克制：最多 whisper 微抬 `rgba(0,0,0,0.03) 0 4px 24px` 或 micro `rgba(16,24,40,0.04) 0 1px 4px`；默认优先 1px 边框，不用厚阴影。
- 品牌紫用于 mark、link、marker、eyebrow band、CTA 外形；**不做饱和满屏紫背景**。画布保持白 / 浅灰；区域填充只用浅 subtle 底（`#F5F5F8`、`#F1ECFE`、语义 callout tint）。
- 引述用紫色左线卡；来源 / 时间戳保持低调 metadata。

## 图标

- 使用线性 icon、来源 pill、▲ / ▼ 涨跌箭头、时间戳、序号 marker、引号符。
- 图标平面、克制；语义色只作小 marker / icon，不扩展为大面积色块。
- 涨跌箭头：绿 ▲ `#149E61` / 红 ▼ `#E5484D`，配 mono 读数。

## 动效

- 入场克制、专业：`power2.out`（默认）、`expo.out`（hero），duration 0.4-0.7s。
- **新闻条 stagger** 100-140ms，模拟信息灌入。
- **Count-up** 数据 / 涨跌用 `gsap.to({ value, snap, duration: 1.0-1.2, ease: 'power1.out' })` 驱动 `textContent`。
- **来源 / 引述 reveal** —— fade + 轻微上移（`y: 20 → 0`），0.4s。
- **Eyebrow pill** 落定时紫色 pill 轻微 scale `1 → 1.04 → 1`，0.25s。
- 永远不要 `repeat: -1`。

## 不要做

- ❌ 不要用品牌紫 `#7132F5` 之外的紫；紫色系只用 `#7132F5` / `#5741D8` / `#5B1ECF`。
- ❌ 不要把品牌紫当小号正文色；小号紫字用 `#5741D8`。
- ❌ 不要用 pill 按钮；12px 是按钮最大圆角。
- ❌ 不要把**饱和**紫做满屏背景。画布保持白；区域底用浅 subtle tint。
- ❌ 不要用厚 drop shadow；最多 whisper 级微抬。
- ❌ 不要把派生红 / 琥珀当装饰随意乱用；它们只表利空 / 存疑语义。
- ❌ 不要为了「丰富」而给无语义差异的同类元素随机换 accent 色。
- ❌ 不要用拉丁品牌字体渲染中文（无 CJK 字形）。中文一律 `NotoSansSC`。
- ❌ Hero 字号不要超过 160px。
