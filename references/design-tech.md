# Style Hint — OpenCode × 终端 / manpage 技术讲解

> Phase 8 style hint。按本文件执行「终端原生、纯等宽、manpage 感」的技术讲解风、配色、排版、形状和动效约束。
> 配色提取自 opencode.ai DESIGN.md（暖奶油画布 + 近黑 ink + Apple 语义 ramp）。
> 姊妹预设：`references/design-dawn.md`（手绘）、`references/design-moon.md`（深色技术）、`references/design-github.md`（GitHub）、`references/design-producthunt.md`（PH 品牌）、`references/design-news.md`（新闻洞察）。

适用场景：技术讲解、CLI / 终端工具、开发者内容、源码 / 命令行原理、工程拆解。与姊妹技术预设的区别：
- **Moon** 是深色 rose-pine 编辑风；**GitHub** 是浅色 GitHub 品牌克制风；
- **本预设（Tech）** 是**暖奶油底 + 100% 等宽 + 终端/manpage** 的极简技术风——整页读起来像一份 README / man 手册，仅有的「视觉时刻」是一张深色 TUI mockup 卡。

## 配色（只用以下颜色）

**Backgrounds**
- 主画布：`#FDFCFC`（暖奶油，带极淡血色）
- Soft surface / 交替行：`#F8F7F7`
- Card surface / install snippet：`#F1EEEE`
- 深色 TUI surface（仅 TUI mockup / 代码块）：`#201D1D`（近黑，等于 ink）
- 深色 elevated（TUI prompt row）：`#302C2C`

**Text**
- Ink / 标题 / 正文 / 主 CTA fill：`#201D1D`（近黑）
- Body / 段落：`#424245`
- Mute / metadata / tab 默认 / 页脚：`#646262`
- Stone / 最弱工具文字：`#6E6E73`
- Ash / disabled / 深色上弱标记 / on-dark-mute：`#9A9898`
- On-dark 正文（深色 surface 上）：`#FDFCFC`

**Borders / 分割线**
- Hairline（1px section 分隔，暖调半透明）：`rgba(15,0,0,0.12)`
- Hairline strong（tab 底线 / 强分隔）：`#646262`

**Semantic accents / 使用场景（Apple HIG ramp）**

按信息语义使用 accent；允许同一 scene 出现多个语义色；禁止随机换色；禁止同一元素叠加多种 accent。亮色只作 marker / 大字 / 语法高亮；可读**正文**用加深变体。

- Accent 蓝 `#007AFF` —— info、link、命令高亮、active tab、关键路径 marker。可读蓝色**文字**用 hover `#0056B3`（更深用 active `#004085`）。
- Danger 红 `#FF3B30` —— error、失败、destructive、反例 marker。可读红色**文字**用 `#D70015`（更深 `#A50011`）。
- Warning 琥珀 `#FF9F0A` —— caution、注意、非致命告警 marker。可读琥珀**文字**用 `#995F06`（中间态 `#CC7F08`）。
- Success 绿 `#30D158` —— 通过、verified、in-TUI 成功 marker。opencode 未提供加深变体；可读绿色**文字派生** `#147A3C`（标注为派生）。

> `#30D158` / `#FF3B30` / `#FF9F0A` 在奶油底上对比不足，**只**作 marker / 大字 / TUI 语法高亮；正文一律用其加深变体（`#0056B3` / `#D70015` / `#995F06` / 派生 `#147A3C`）。

### 主题专属标记

使用 ASCII 括号 marker（`[+]` / `[-]` / `[x]`）代替 bullet / icon；块像素 ASCII wordmark；等宽 label、终端 cursor、keybinding 提示（`tab` / `ctrl-p`）、hairline 细线分隔。保持 flat / line-based / 无阴影。

### 颜色使用场景

| 场景 | 前景 | 背景 / 表面 | 线 / 标记 | 规则 |
|------|------|-------------|-----------|------|
| Canvas / scene base | `#201D1D` / `#424245` | `#FDFCFC` | `rgba(15,0,0,0.12)` | 标题 Ink，正文 Body；Mute 只做 metadata。 |
| Soft surface / 交替行 | `#201D1D` / `#424245` | `#F8F7F7` | `rgba(15,0,0,0.12)` | 交替行 / 输入底 / 引述行。 |
| Card / install snippet | `#201D1D` | `#F1EEEE` | `rgba(15,0,0,0.12)` | 命令片段 / 轻抬 section 行；4px 圆角。 |
| 深色 TUI mockup / 代码块 | `#FDFCFC` / `#9A9898` | `#201D1D` | `#302C2C` | 唯一「视觉时刻」；正文 on-dark，弱标记 Ash；语法用 Apple ramp 亮色。 |
| 深色 prompt row | `#FDFCFC` | `#302C2C` | `#646262` | TUI 内命令行 / prompt；比 dark surface 亮一档。 |
| Mute / metadata / chrome | `#646262` / `#6E6E73` | 任一浅底 | `rgba(15,0,0,0.12)` | tab 默认、页脚、breadcrumb；不承载正文。 |
| Info / link / 命令高亮 | `#0056B3` | 透明 / `#F8F7F7` | `#007AFF` | 链接 / 命令 marker 用 `#007AFF`；说明文字用 `#0056B3`。 |
| Success / 通过 / verified | `#147A3C` | `#F8F7F7` / 透明 | `#30D158` | tint / 白底正文用派生 `#147A3C`；`#30D158` 只作 marker / `[x]` 勾 / 大字。 |
| Danger / 失败 / error | `#D70015` | `#F8F7F7` / 透明 | `#FF3B30` | 错误输出 / 反例正文用 `#D70015`；`#FF3B30` 只作 marker。 |
| Warning / 注意 | `#995F06` | `#F8F7F7` / 透明 | `#FF9F0A` | 告警正文用 `#995F06`；`#FF9F0A` 只作 marker。 |
| Big number / 数据 | `#201D1D` / mono | `#FDFCFC` / `#F8F7F7` | `#007AFF` / `#147A3C` | 数字 mono + tabular-nums；状态用蓝 / 绿 marker。 |
| Timeline / process / state | 当前 `#0056B3` | `#FDFCFC` / `#F8F7F7` | hairline + 语义 marker | 进行中蓝，成功绿，失败红，注意琥珀；连接线 hairline。 |
| Data table / chart | 表格正文 `#201D1D` / `#424245` | highlight cell soft | `#007AFF` / `#147A3C` / `#D70015` | series 用蓝 / 绿 / 红 / 琥珀；不给整列饱和底。 |
| Callout / definition / qa | callout text 色 | soft / 深色 TUI | hairline 或语义左线 | 优先用下方三件套；definition 用蓝；QA 的 Q 用蓝、A 用 Ink。 |
| Code / terminal / file tree | `#FDFCFC` / `#9A9898`（深底）或 `#201D1D`（浅底 snippet） | `#201D1D` / `#F1EEEE` | `#007AFF` / `#147A3C` / `#D70015` | 命令 / path mono；success 绿、error 红、hint 蓝。 |
| Media annotation | `#201D1D` / callout text | 素材外部信息区 | 语义 marker | 不把 label / callout 压在素材关键区域。 |
| Subtitle | `#201D1D` 或 `#FDFCFC` | shrink-to-fit 遮罩 | `rgba(15,0,0,0.12)` | 字幕按背景选高对比，不用裸亮色 accent 正文。 |

### 标题配色与高亮 box

**标题**
- 正文标题维持 `#201D1D`。
- 关键词可用可读蓝 `#0056B3` 做短 accent（其余字保持 `#201D1D`）；成功关键词用 `#147A3C`，风险关键词用 `#D70015`。
- Section label 用 `heading-md` 感的等宽粗体 `#201D1D`，或 `[ SECTION ]` ASCII bracket label。
- **不要用 glow / 渐变 / 大面积亮色**表达层级；层级来自字号 / 字重 / hairline / 唯一深色 TUI surface。

**高亮 box / callout**（hairline 文本块，**不是**满屏背景）—— 底 / 1px 边 / 文字 三件套：

| 语义 | 底 | 边 | 文字 |
| --- | --- | --- | --- |
| Info / 说明（蓝） | `#F8F7F7` | `#007AFF` | `#0056B3` |
| 通过 / verified（绿） | `#F8F7F7` | `#30D158` | `#147A3C` |
| 失败 / error（红） | `#F8F7F7` | `#FF3B30` | `#D70015` |
| 注意 / caution（琥珀） | `#F8F7F7` | `#FF9F0A` | `#995F06` |
| 中性（hairline） | `#F1EEEE` | `rgba(15,0,0,0.12)` | `#201D1D` |
| 终端 / 代码（深） | `#201D1D` | `#302C2C` | `#FDFCFC` |

裸亮色 accent 只用于 marker、`[x]` / `[+]` / `[-]`、icon、命令高亮、大号数字；说明性正文用对应加深文字色。

### `visual_role` 色彩覆盖

| `visual_role` | 配色方式 |
| --- | --- |
| `title` / `product_card` / `section_divider` | Ink 标题 + 蓝色 `[ label ]` eyebrow；关键词用 `#0056B3`。 |
| `leaderboard` / `big_number` / `data_block` / `metric_strip` | 数字 mono `#201D1D`；成功 / 增长绿 marker，风险红，rank / link 蓝；label 用 Mute。 |
| `data_table` / `chart` | 表格正文 Ink / Body；highlight cell soft 底；series 用蓝 / 绿 / 红 / 琥珀；ASCII / 细线图。 |
| `timeline` / `process_flow` / `state_machine` | 当前节点蓝，成功绿，失败红，注意琥珀；连接线 hairline / `#646262`。 |
| `architecture_diagram` / `network_graph` | 模块边线 hairline strong / 蓝；关键路径蓝；正文 Ink；无阴影。 |
| `comparison_matrix` / `pros_cons` | 正向绿，风险红，注意琥珀；正文 Ink / Body；不给整列饱和底。 |
| `list` / `feature_grid` | 用 `[+]` / `[-]` / `[x]` ASCII bullet；item label Ink，detail Body；语义 bullet 用蓝 / 绿 / 红。 |
| `callout` / `definition` / `qa` | 六套 callout 三件套；definition 用蓝；QA 的 Q 蓝、A Ink / 绿。 |
| `code_block` / `terminal_block` / `file_tree` | 用深色 TUI surface `#201D1D`；命令 / path mono；success 绿、error 红、hint 蓝；prompt row `#302C2C`。 |
| `annotated_media` | 标注外置；pin 用蓝 / 琥珀；解释文字 Ink / Body。 |
| `quote` | quote 正文 Ink；source Mute；引述用 hairline 左线文本块，不用大色块。 |

### 对比度 guardrails

- 正文必须达到 4.5:1；大号文字、icon、chart stroke、粗线 marker 必须达到 3:1；低于 3:1 的颜色只能做装饰。
- Ink `#201D1D` / Body `#424245` 在奶油底上承载正文；Mute `#646262`、Stone `#6E6E73`、Ash `#9A9898` 只做 metadata / 装饰 / disabled。
- 深色 TUI surface `#201D1D` 上用 `#FDFCFC` 承载正文，`#9A9898` 做弱标记；不要把 `#424245` 放到深色上承载信息。
- Apple ramp 亮色（`#007AFF` / `#FF3B30` / `#FF9F0A` / `#30D158`）作 marker / 大字 / TUI 语法高亮；奶油底上的可读语义文字用加深变体 `#0056B3` / `#D70015` / `#995F06` / 派生 `#147A3C`。
- success 用绿、info 用蓝，二者不可互换；同一 scene 需区分时加 `[x]` / label 辅助，不只靠颜色。

## 排版

**纯等宽是本预设的身份。** 拉丁 / 代码 / 数据 / marker 全部走等宽；中文因等宽字体无 CJK 字形，改用 `NotoSansSC`（复用 Moon 预设，经 `scripts/fonts-download.sh <target_dir> moon` 预置）。

| 用途 | 字体 | 字重 | 备注 |
| --- | --- | --- | --- |
| 中文标题 / Hero | `NotoSansSC` | 700 | Berkeley/mono 无 CJK 字形，中文标题走 NotoSansSC |
| 中文 section 标题 | `NotoSansSC` | 600 | |
| 中文正文 | `NotoSansSC` | 400 | |
| 中文字幕 | `NotoSansSC` | 500 | |
| 拉丁 / 代码 / 命令 / 数据 / marker | `IBMPlexMono` | 400 / 500 / 600 | opencode 记载的 Berkeley Mono 开源替代；ASCII bracket、wordmark、TUI |
| 英文 / 数字强调 | `IBMPlexMono` | 600 | 版本号、命令片段、大号数字 |

**绝不**在拉丁 chrome 里引入 sans-serif（除中文 `NotoSansSC` 外）。**全部数据读数** `font-variant-numeric: tabular-nums`。行高按 opencode：正文 `1.5`，按钮 `2.0`。

## 视频尺寸（覆盖网页常规尺寸）

| 元素 | 1920×1080 | 1080×1440 | 1080×1920 | 字重 |
| --- | --- | --- | --- | --- |
| Hero 标题 | 96-140px | 80-120px | 84-128px | 700 |
| Section label（等宽 / `[ ]`） | 40-60px | 34-52px | 36-56px | 700 |
| 正文 | 30-46px | 28-40px | 28-42px | 400 |
| 代码 / 命令 / 等宽 | 26-38px | 24-34px | 24-36px | 400 / 500 |
| Big number（mono） | 56-84px | 48-70px | 52-74px | 600 |
| Meta / caption | 22-30px | 22-28px | 22-30px | 400 |
| 字幕 | 35px | 35px | 35px | 500 |
| Padding（.scene） | 90px 140px | 90px 80px | 90px 70px | — |

## 形状风格

- 圆角只有两档：交互元素（按钮 / 输入 / snippet / badge / prompt row）`4px`；其余一切容器（section / TUI mockup / 导航 / 列表行）`0px` 直角。
- **完全无阴影。** 层级只靠 hairline 1px 细线与唯一的深色 TUI surface 表达；不 lift、不 float。
- **无渐变、无装饰图、无发光**。section 之间用大间距（~96px 节奏）+ 单条 hairline 分隔，无装饰 divider。
- 图片 / 视频素材默认无可见卡片框、无 border、无 padding、无 shadow；素材说明放素材外部信息区。
- 深色 surface `#201D1D` 只保留给 TUI mockup / 代码块 / 反白 CTA，不铺满 hero。

## 图标

- 用 ASCII 括号 marker（`[+]` 增 / `[-]` 减 / `[x]` 完成 · 勾）代替 bullet 与图标；块像素 ASCII wordmark；等宽字符 glyph（如 `kbd`、`⊕`、`↻`）。
- 终端 cursor（`▍` / `_`）、keybinding 提示（`tab` / `ctrl-p`）用 Ash / Mute。
- 图标一律 flat / line-based / 等宽；**不要**手绘 icon、发光 icon 或 bitmap。

## 动效

- 入场极克制：`power3.out`、`expo.out`、`sine.out`；位移小（`y: 16-40`、`scale: 0.98-1`）。
- **打字机 / 逐行 reveal** 用于命令与 TUI 输出：逐字符或逐行推进，模拟终端打印；节奏稳定、不花哨。
- **终端 cursor 闪烁** 可用，但必须有限次（`repeat: 2-4`），不做无限闪。
- **ASCII bullet 灌入** —— `[+]` / `[-]` 行 stagger 80-120ms 入场。
- 避免 bouncy `back.out(1.7)`；无 radial glow / orb / neon。
- 永远不要 `repeat: -1`。

## 不要做

- ❌ 不要在拉丁 chrome 里用 sans-serif；除中文 `NotoSansSC` 外一律 `IBMPlexMono`。
- ❌ 不要用等宽字体渲染中文（无 CJK 字形）；中文一律 `NotoSansSC`。
- ❌ 不要加任何 drop shadow / 发光 / 渐变 / 装饰图；层级只靠 hairline 与深色 TUI surface。
- ❌ 不要用 pill 圆角；交互元素 4px，其余 0px。
- ❌ 不要把 Apple ramp 亮色当小号正文；正文用加深变体 `#0056B3` / `#D70015` / `#995F06` / `#147A3C`。
- ❌ 不要把深色 surface `#201D1D` 铺成 hero 满屏背景；它只留给 TUI mockup / 代码 / 反白 CTA。
- ❌ 不要在同一元素上叠加多种 accent 色；不同语义状态可用不同颜色，但必须能解释其信息角色。
- ❌ 不要为了「丰富」而给无语义差异的同类元素随机换 accent 色。
- ❌ Hero 字号不要超过 140px。
