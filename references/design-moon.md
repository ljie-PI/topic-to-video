# Style Hint — Rosé Pine Moon × 严肃技术编辑风

> Phase 8 style hint。按本文件执行深色技术编辑风、配色、排版、形状和动效约束。
> 手绘对照见 `references/design-dawn.md`。

## 配色（只用以下颜色）

**Backgrounds**
- 主画布：`#232136`（Moon base）
- 卡片表面：`#2a273f`（Moon surface）
- Elevated overlay：`#393552`（Moon overlay）

**Text**
- Primary / 标题 / 深色 panel 正文：`#e0def4`（Moon text）
- Secondary / 主画布正文 / 大号辅助：`#908caa`（Moon subtle；在主画布上正文安全，surface / overlay 上只用于大号辅助、metadata）
- 仅装饰用 muted：`#6e6a86`（Moon muted；不要用于正文）

**Semantic accents / 使用场景**

按信息语义使用 accent；允许同一 scene 出现多个语义色；禁止随机换色；禁止同一元素叠加多种 accent。

- Iris `#c4a7e7` —— 主要技术高亮、label、definition、active state、结构图关键路径。
- Foam `#9ccfd8` —— info、neutral data、chart 主线、diagram connector、外置 annotation；不兼作 success。
- Gold `#f6c177` —— big number、重要排名、warning 数字、当前步骤；用作数字、短 label、marker。
- Love `#eb6f92` —— risk、failure、danger、紧急 callout、反例 / don't。
- Rose `#ea9a97` —— human note、quote、柔对比、罕用 CTA；不兼作 success。
- Pine `#3e8fb0` —— success / verified / stable 状态色；用于 success marker、大号 label、几何形状、粗线、连接线；不用于小号正文。

**Borders / 分割线**
- 标准线：`#56526e`
- 弱分割线：`#44415a`
- 低高光 / inset：`#2a283e`

### 主题专属标记

使用技术 label、终端 cursor、细线轨道、小节点、状态 tag 和外置信息区左线。保持 flat / line-based。

### 颜色使用场景

| 场景 | 前景 | 背景 / 表面 | 线 / 标记 | 规则 |
|------|------|-------------|-----------|------|
| Canvas / scene base | `#e0def4` / `#908caa` | `#232136` | `#56526e` | 标题用 Primary，正文用 Secondary；正文不得用 muted。 |
| Surface / panel / card | `#e0def4`；大号辅助可用 `#908caa` | `#2a273f` | `#56526e` | panel 正文用 Primary；Secondary 只做大号辅助 / metadata；禁止用 glow 建层级。 |
| Elevated overlay / detail band | `#e0def4` | `#393552` | `#56526e` | 用于 callout、外置信息区、状态条。 |
| Muted metadata / decorative chrome | `#6e6a86` | 任一背景 | `#44415a` / `#2a283e` | 只用于装饰、网格、低权重 label，不承载正文。 |
| Info / neutral data | `#9ccfd8` 或 `#e0def4` | `#2a273f` / 透明 | `#9ccfd8` | Foam 可承载短标签和数据，不压素材。 |
| Success / verified / stable | `#3e8fb0`（大号 / marker） | `#2a273f` | `#3e8fb0` | Pine 表 success；不用 Foam 表 success；Pine 不承载小号正文。 |
| Warning / important number | `#f6c177` | `#2a273f` | `#f6c177` | Gold 可做大号数字、当前节点、warning marker；不做大面积底色。 |
| Danger / failure / urgent | `#eb6f92` | `#2a273f` / `#393552` | `#eb6f92` | Love 用于风险、失败、紧急 callout。 |
| Emphasis / active tech label | `#c4a7e7` | 透明 / `#2a273f` | `#c4a7e7` | Iris 是主技术强调色，可用于短标签和 active state。 |
| Citation / quote / human note | `#ea9a97` | `#2a273f` | `#ea9a97` / `#c4a7e7` | quote 正文仍可用 Primary；source 可用 Secondary。 |
| CTA / rare action | `#ea9a97` 或 `#c4a7e7` | `#393552` | `#ea9a97` | CTA 罕用，保持克制，不做亮色大按钮。 |
| Tags / badges / progress | `#e0def4` / accent 短字 | `#2a273f` / `#393552` | `#c4a7e7` / `#9ccfd8` / `#f6c177` | tag、badge、rank、progress step 用短文本 + 线 / marker；Pine 不用于小字。 |
| Callout boxes / role surfaces | `#e0def4`；大号 meta 可用 `#908caa` | `#2a273f` / `#393552` | 按语义选 accent 左线 | callout、definition、QA、quote 的正文用 Primary；Secondary 不用于 overlay 小号正文。 |
| Code / terminal / file tree | `#e0def4` / `#908caa` | `#2a273f` | `#c4a7e7` / `#9ccfd8` | 命令、路径、状态用 mono；错误用 Love，重要数字用 Gold。 |
| Diagram connector / graph node | `#e0def4` | 透明 / `#2a273f` | `#9ccfd8` / `#c4a7e7` / `#3e8fb0` | Pine 只做形状 / 粗线；小字不用 Pine。 |
| Media annotation | `#e0def4` / `#908caa` | 素材外部信息区 | `#f6c177` / `#9ccfd8` | 不把 tag、badge、caption 压在素材上。 |
| Subtitle | `#e0def4` | shrink-to-fit 深色遮罩 | `#56526e` | 字幕优先稳定可读，不使用低对比 accent。 |

### 标题配色与高亮 box

**标题**

- 正文标题维持 `#e0def4`；技术关键词可用 Iris `#c4a7e7` 或 Foam `#9ccfd8` 做短 accent。
- 重要数字 / 当前步骤可用 Gold `#f6c177`，风险 / failure 用 Love `#eb6f92`。
- Pine `#3e8fb0` 不用于小号标题或正文，只做大形状、粗线或低权重结构。

**高亮 box / callout**

- 使用 `#2a273f` / `#393552` panel + 语义色左线 / top rule。
- callout 正文用 Primary `#e0def4`；Secondary `#908caa` 只做大号辅助或 source。
- 禁止用 glow、radial spotlight 或大面积亮色填充表达层级。

### `visual_role` 色彩覆盖

| `visual_role` | 配色方式 |
| --- | --- |
| `title` / `product_card` / `section_divider` | Primary 标题 + Iris / Foam eyebrow；产品或项目身份的关键数字可用 Gold。 |
| `leaderboard` / `big_number` / `data_block` / `metric_strip` | 数字用 Gold / Foam；rank marker 用 Iris；风险数值用 Love；普通 label 用 Secondary。 |
| `data_table` / `chart` | 表格正文 Secondary；highlight cell 用 Gold 描边；chart 主线 Foam，secondary series Iris / Rose，danger series Love。 |
| `timeline` / `process_flow` / `state_machine` | 节点正文 Primary / Secondary；当前节点 Gold；active tech 节点 Iris；失败状态 Love；连接线 Foam。 |
| `architecture_diagram` / `network_graph` | 模块边线 Foam / Iris；关键路径 Iris；背景结构线 `#44415a`；Pine 仅作大形状或粗线。 |
| `comparison_matrix` / `pros_cons` | 正向 / stable 用 Pine，风险 / cons 用 Love，中性维度用 Secondary；info 维度才用 Foam；不要给整列大面积 accent 底。 |
| `list` / `feature_grid` | item label Primary；bullet / index 按语义用 Iris / Foam / Gold / Love；detail 用 Secondary。 |
| `callout` / `definition` / `qa` | callout 用 Overlay 底 + 语义色左线；definition 用 Iris；QA 的 Q 用 Foam、A 用 Primary。 |
| `code_block` / `terminal_block` / `file_tree` | panel 底 Surface；命令 / path 用 Iris；输出值用 Foam / Gold；error / fail 用 Love。 |
| `annotated_media` | 标注在素材外部；pin 用 Gold / Foam；解释文字 Primary / Secondary。 |
| `quote` | 引号 / source marker 用 Rose；quote 正文 Primary；source 用 Secondary。 |

### 对比度 guardrails

- 正文必须达到 4.5:1；大号文字、icon、chart stroke、粗线 marker 必须达到 3:1；低于 3:1 的颜色只能做装饰。
- `#e0def4` 可在 base / surface / overlay 上承载正文。
- `#908caa` 只在主画布 `#232136` 上承载正文；在 `#2a273f` / `#393552` 上只用于大号辅助、metadata 或 source。
- `#6e6a86` 永远只做装饰 chrome，不承载信息。
- Pine `#3e8fb0` 用于 success / stable 状态 marker、大号 label、几何形状、连接线、icon 或粗线；小号可读 accent text 改用 Iris / Foam / Rose。
- success 用 Pine，info 用 Foam，二者不可互换；同一 scene 需区分时加 ✓ / label 辅助，不只靠颜色。

## 排版

| 用途 | 字体 | 字重 | 备注 |
|------|------|------|------|
| 中文标题 | `NotoSansSC` | 700 | 用于主论断 |
| 中文 section 标题 | `NotoSansSC` | 600 | 当 700 显得过重时 |
| 中文正文 | `NotoSansSC` | 400 | 清晰、现代，比 Dawn 不那么俏皮 |
| 中文字幕 | `NotoSansSC` | 500 | 略加重以适应视频可读性 |
| 英文 / 数据 / 代码 | `IBMPlexMono` | 400 | 技术 label、文件名、模型名 |
| 英文 / 数字强调 | `IBMPlexMono` | 600 | 数字、版本号、命令片段 |

**Moon 风格禁止使用 Dawn 的手写字体**，除非用户明确要求“手绘对比”。保持克制、技术、编辑感。

使用 `scripts/fonts-download.sh` 预置的 Moon 字体。HyperFrames sub-agent 负责加载本地字体资源。

## 视频尺寸（覆盖网页常规尺寸）

| 元素 | 1920×1080 | 1080×1440 | 1080×1920 |
|------|-----------|-----------|-----------|
| Hero 标题 | 88-136px | 72-116px | 76-124px |
| Section 标题 | 54-82px | 46-70px | 50-76px |
| 正文 | 30-48px | 28-42px | 28-44px |
| 数据 label | 22-32px | 22-30px | 22-32px |
| 代码 / 等宽 | 22-34px | 22-30px | 22-32px |
| 字幕 | 35px | 35px | 35px |
| Padding（.scene） | 90px 140px | 90px 80px | 90px 70px |

## 形状风格

- 紧凑的平面 panel 和严肃的编辑式 data block。
- 高亮应表现为线、tag 或小标记，而不是大面积的亮色填充。
- 背景默认是 `#232136` 纯色 + 极淡网格 / 细线 / 低对比结构；环境装饰只能是 flat / line-based。
- 图片 / 视频素材默认无可见卡片框、无 border、无 outline、无 padding、无 shadow、无 glow、无可见容器底色。
- 禁止厚重阴影、发光层和俏皮装饰。

## 图标

- 使用等宽 label、节点、cursor、线性箭头、状态点或 terminal-style marker。
- 图标保持低调、平面、线性；不要使用 Dawn 的手绘 icon，也不要使用发光 icon。

## 动效

- 入场应当克制：`power3.out`、`expo.out`、`sine.out`。
- 位移幅度比 Dawn 小：`y: 20-44`、`x: 20-40`、`scale: 0.96-1`。
- 避免 bouncy 的 `back.out(1.7)`；仅罕见强调瞬间可用。
- 环境装饰要克制：网格、细线、小轨道标记、终端式 cursor 或图谱节点。它们必须是 flat / line-based，不要做成 radial glow、blurred orb、neon halo 或发光阴影。

## 不要做

- ❌ 不要替换 Dawn 的手绘默认风格；Moon 是可选项。
- ❌ 不要在 Moon 中使用 `MaShanZheng`、`LongCang`、`Caveat` 或 `PatrickHand`，除非用户明确要求手绘混搭对比。
- ❌ 不要把 `#6e6a86` 用作正文。
- ❌ 不要在深色背景上使用满屏 linear gradient。
- ❌ 不要使用 `radial-gradient` spotlight、localized glow、ambient orb、neon halo 或发光阴影。
- ❌ 不要给图片 / 视频素材加可见 border、outline、padding、卡片底、shadow、glow 或 inset 框感。
- ❌ 不要把 foreground caption、tag、badge、callout、label 压在图片 / 视频素材之上；需要说明素材时放到素材外部信息区。
- ❌ 不要在同一个元素上叠加多种 accent 色；不同语义状态可以使用不同颜色，但必须能解释其信息角色。
- ❌ 不要为了“丰富”而给无语义差异的同类元素随机换 accent 色。
- ❌ 不要把 accent 色做大面积背景；只用作线、tag、数字或小符号。
