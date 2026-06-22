# Style Hint — GitHub × 编辑、技术、克制

> Phase 8 style hint。按本文件执行 GitHub 编辑技术风、配色、排版、形状和动效约束。
> 姊妹预设：`references/design-dawn.md`（手绘）、`references/design-moon.md`（深色技术）、`references/design-producthunt.md`（PH 品牌）。

## 配色（只用以下颜色）

**Backgrounds**

- 主画布：`#FFFFFF`（白）
- 次级面板：`#F6F8FA`（hero band / page title 后面的浅灰条）
- 浅色背景网格：`#EFEFEF`（参考 `C:\Workspace\topic-to-video\github-weekly-0608\composition-portrait\index.html` 的 scene 背景网格）
- Elevated / 悬停：`#E4EBE6`（绿调浅 hover）
- 顶部导航：`#25292E`（近黑）
- 黑色块：`#000000`（footer、深色 hero、terminal 风）

**Text**

- Primary / 标题：`#1F2328`（深近黑）
- Secondary / 次级 / 副标：`#59636E`（中灰）
- Muted / 装饰 / metadata（**不要**用于正文）：`#8C959F`

**Borders / 分割线**

- 标准 1px：`#D1D9E0`
- 弱：`#EFEFEF`

**Semantic accents / 使用场景**

按 GitHub / Primer 语义使用 accent；允许同一 scene 出现多个语义色；禁止随机换色；禁止同一元素叠加多种 accent。

- Blue `#0969DA` —— link、repo path hover、info、tab underline、主要交互高亮。
- Success / Star green `#1F883D` —— Star CTA、success、verified、positive metric。
- Success fg `#08872B` —— "N stars this week" 等成功计数文字。
- Success subtle `#EBF9F4` —— Sponsor / success subtle surface。
- Attention `#BE7D00` —— warning、attention、重要但非错误的状态。
- Severe `#B85B06` —— severe、orange hover、需要区分 warning 与 danger 的状态。
- Danger `#CF2230` —— destructive、fail、risk、delete。
- Done purple `#8534F3` —— done、merged、completed workflow。
- Done emphasis `#EF2AA4` —— "New"、sponsor、罕见强调。
- Teal `#197B7B` —— discussion、metadata、neutral relation。
- Lime `#92C219` —— JS 语言色点或轻量生态 marker。

### 主题专属标记

使用 GitHub mark、repo path、PR / issue 状态、Star pill 和语言色点。列 trending repo 时，每行 repo 末尾添加语言色点（`●`）。

用这些标准值；若你只有 GitHub 自己的小调色板，用括号里的替代：

- TypeScript → `#3178C6`（替代：`#0969DA`）
- JavaScript → `#F1E05A`（替代：`#92C219`）
- Python → `#3572A5`
- Rust → `#DEA584`（替代：`#B85B06`）
- Go → `#00ADD8`
- C++ → `#F34B7D`（替代：`#EF2AA4`）
- Java → `#B07219`
- Ruby → `#701516`

### 颜色使用场景

| 场景 | 前景 | 背景 / 表面 | 线 / 标记 | 规则 |
|------|------|-------------|-----------|------|
| Canvas / scene base | `#1F2328` / `#59636E` | `#FFFFFF` | `#D1D9E0` | 正文用 Primary / Secondary；Muted 只做 metadata。 |
| Light background grid | 内容仍用 `#1F2328` / `#59636E` | `#FFFFFF` + `#EFEFEF` 细网格 | `#EFEFEF` | 网格位于 scene 背景层；禁止压内容或素材。 |
| Surface / panel / card | `#1F2328` / `#59636E` | `#F6F8FA` | `#D1D9E0` | 1px border，无 shadow。 |
| Elevated / hover / subtle state | `#1F2328` | `#E4EBE6` | `#D1D9E0` | 只用于轻 hover / state，不做默认大底。 |
| Dark chrome / terminal | `#FFFFFF` | `#25292E` / `#000000` | `#8C959F` | 顶栏是 chrome；terminal 可用黑色块；`#59636E` 不用于深色 chrome。 |
| Info / link | `#0969DA` 或 callout text `#0A3069` | `#DDF4FF` | `#0969DA` | 小号语义正文优先用 callout 三件套。 |
| Success / verified | callout text `#0A5128` 或白底上的 `#1F883D` / `#08872B` | `#DAFBE1` / `#EBF9F4` / `#FFFFFF` | `#1F883D` | tint 底上的正文用 `#0A5128`；Star / success 裸色只用于白底上的短 label、icon、count。 |
| Warning / attention | callout text `#7D4E00` | `#FFF8C5` | `#BE7D00` | Attention 色裸用只适合 label / icon / 大字。 |
| Severe / orange | `#B85B06` | `#F6F8FA` | `#B85B06` | 用于 severe marker 或 sponsor hover，不与 danger 混用。 |
| Danger / failure | callout text `#A40E26` | `#FFEBE9` | `#CF2230` | 删除、失败、风险统一用 Danger callout 或红色短标记。 |
| Done / merged | callout text `#512A97` | `#FBEFFF` | `#8534F3` | done / merged / completed 用紫色体系。 |
| Citation / discussion / metadata | `#59636E` / `#197B7B` | `#F6F8FA` | `#197B7B` | discussion、source、repo metadata 可用 Teal marker。 |
| Code / terminal / file tree | `#1F2328` / `#FFFFFF` | `#F6F8FA` / `#000000` | `#0969DA` / `#1F883D` / `#CF2230` | 命令、路径、状态用 mono；错误用 Danger，成功用 Success。 |
| Diagram connector / graph node | `#1F2328` | `#FFFFFF` / `#F6F8FA` | `#0969DA` / `#197B7B` / `#8534F3` | 关系线按语义色，底仍保持 GitHub 平面白 / 灰。 |
| Tags / badges / progress | `#1F2328` / callout text | callout tint / `#F6F8FA` | Blue / Success / Attention / Danger / Done | issue label、PR status、progress step、rank badge 用 Primer 状态色。 |
| Callout boxes / role surfaces | callout text 色 | callout tint | callout border | callout、definition、QA、quote 优先使用 Primer 三件套，不用裸 accent 小字。 |
| Language / ecosystem marker | `#59636E` | `#FFFFFF` | language dot values | 语言点只做小圆点，不扩展为大面积色块。 |
| Media annotation | `#1F2328` / callout text | 素材外部信息区 | semantic callout border | 不把 label / callout 压在素材关键区域。 |
| Subtitle | `#1F2328` 或 `#FFFFFF` | shrink-to-fit 遮罩 | `#D1D9E0` | 字幕按画面背景选择高对比，不用裸 accent 正文色。 |

### 标题配色与高亮 box

画布保持白 / 浅灰，但标题与 callout 可以按真实语义上色：

**标题**

- 正文标题维持 `#1F2328`。
- Hero 可坐落在浅色 band 上：中性 `#F6F8FA`，或下方 box 的「底」色做淡 accent band。
- 标题里的关键词用 accent 上色（其余字保持 `#1F2328`）：Blue `#0969DA`、Success `#1F883D`、Done purple `#8534F3`。
- Section eyebrow（小标签）：accent 文字 + 对应 subtle 底做成 pill。

**高亮 box / callout**（小卡，**不是**满屏背景）—— 底 / 1px 边 / 文字 三件套（Primer token，已校对对比度）：

| 语义 | 底 | 边 | 文字 |
| --- | --- | --- | --- |
| Info（蓝） | `#DDF4FF` | `#0969DA` | `#0A3069` |
| Success（绿） | `#DAFBE1` | `#1F883D` | `#0A5128` |
| Attention（黄） | `#FFF8C5` | `#BE7D00` | `#7D4E00` |
| Danger（红） | `#FFEBE9` | `#CF2230` | `#A40E26` |
| Done（紫） | `#FBEFFF` | `#8534F3` | `#512A97` |

裸 accent 用于 link、icon、tag、badge、chart stroke 和大号数字；解释性正文或 callout 内容使用上表的底 / 边 / 文字三件套。

### `visual_role` 色彩覆盖

| `visual_role` | 配色方式 |
| --- | --- |
| `title` / `product_card` / `section_divider` | Primary 标题 + Blue / Success / Done eyebrow；repo path 可用 Blue hover 或 mono Primary。 |
| `leaderboard` / `big_number` / `data_block` / `metric_strip` | 数字 Primary / mono；star / growth 用 Success；rank / link 用 Blue；warning metric 用 Attention callout。 |
| `data_table` / `chart` | 表格正文 Primary / Secondary；highlight cell 用 callout tint；series 用 Blue / Success / Attention / Danger / Done / Teal。 |
| `timeline` / `process_flow` / `state_machine` | 当前步骤 Blue；成功节点 Success；失败节点 Danger；完成节点 Done；连接线 `#D1D9E0` + 语义色 marker。 |
| `architecture_diagram` / `network_graph` | 模块边线 Blue / Teal；dependency 用 Teal；completed path Done；risk edge Danger。 |
| `comparison_matrix` / `pros_cons` | 正向 Success，风险 Danger，注意 Attention；正文使用 Primary / Secondary；不要给整列饱和色底。 |
| `list` / `feature_grid` | item label Primary；bullet / icon 按语义用 Blue / Success / Attention / Danger；detail 用 Secondary。 |
| `callout` / `definition` / `qa` | 必须优先使用 Primer callout 三件套；definition 用 Info；QA 的 Q 用 Blue，A 用 Primary / Success。 |
| `code_block` / `terminal_block` / `file_tree` | panel 用 `#F6F8FA` 或 terminal 黑；path / command 用 mono；success output Success，error output Danger，hint Blue。 |
| `annotated_media` | 标注外置；pin / border 用 Blue / Attention / Danger；解释文字用 callout text 或 Primary。 |
| `quote` | quote 正文 Primary；source Secondary / Teal；引用卡可用 Info 或 Done callout tint。 |

### 对比度 guardrails

- 正文必须达到 4.5:1；大号文字、icon、chart stroke、粗线 marker 必须达到 3:1；低于 3:1 的颜色只能做装饰。
- Primary `#1F2328` 和 Secondary `#59636E` 可在白 / 浅灰底上承载正文；Muted `#8C959F` 只做 metadata、装饰或弱 chrome。
- 深色 chrome / terminal 上使用 `#FFFFFF` 承载正文，`#8C959F` 做弱标记；不要把 `#59636E` 放在 `#25292E` 上承载信息。
- 语义正文优先使用 Primer callout 三件套。Success tint 上的文字用 `#0A5128`，不要用 `#1F883D` / `#08872B` 写小号正文。
- 两个 success 绿分工：count 文字用 `#08872B`；Star CTA / badge 外形与 success 节点用 `#1F883D`；tint 底正文用 `#0A5128`；不混用。
- 裸 accent 主要用于链接、icon、tag、underline、status dot 和大号数字；长说明文字使用对应 callout text 色。

## 排版

中文字体复用 **Moon 预设**（`references/design-moon.md`）的确定性 CJK 字体，经 `scripts/fonts-download.sh <target_dir> moon` 预置；拉丁品牌字体可选。

| 用途 | 字体 | 字重 | 备注 |
| --- | --- | --- | --- |
| 中文标题 / Hero | `NotoSansSC` | 700 | 引自 Moon |
| 中文 section 标题 | `NotoSansSC` | 600 |  |
| 中文正文 | `NotoSansSC` | 400 |  |
| 中文字幕 | `NotoSansSC` | 500 |  |
| Repo path / 数据 / 命令 / 英文 | `IBMPlexMono` | 400 / 600 | `owner / repo`、星数、代码、语言名 |
| 拉丁品牌显示（可选） | `Mona Sans VF` | 600 | 仅当 workspace 提供该字体时用于纯英文 hero / 标签；无则回退 `IBMPlexMono` |

**绝不要用 Mona Sans 显示中文**。中文一律走 `NotoSansSC`。

**全部数据读数必须** `font-variant-numeric: tabular-nums`。

## 视频尺寸（覆盖网页常规尺寸）

| 元素 | 1920×1080 | 1080×1440 | 1080×1920 | 字重 |
| --- | --- | --- | --- | --- |
| Hero 标题（"Trending this week"） | 130-180px | 110-150px | 116-160px | 600 |
| Section 标题 | 64-88px | 54-74px | 58-80px | 600 |
| Repo path `owner / repo`（mono） | 56-72px | 48-62px | 52-66px | 600 |
| Repo 描述 | 38-46px | 32-40px | 34-42px | 400 |
| Meta（lang、stars、forks） | 26-32px | 24-30px | 24-30px | 400 |
| Padding（.scene） | 90px 140px | 90px 80px | 90px 70px | — |

## 形状风格

- 1px 边框，**不要阴影**。GitHub 整体不用 drop shadow。
- 圆角统一 6px（卡片）/ 8px（按钮 pill）。
- 浅色 scene 可使用极淡背景网格：在 `#FFFFFF` scene 上用 `#EFEFEF` 横竖 2px 线、约 `72px 72px` 间距、`opacity: 0.35-0.45`；网格放在 `::before` / 背景层，内容层在其上方。
- 横屏可把网格间距放宽到 80-96px；竖向 / 竖屏可保持 64-72px。网格只能是轻量 structural texture，不是主视觉。
- 不要把**饱和** accent 色做满屏背景；链接 / 按钮 / 色点 / 状态标签用实色 accent，区域填充只用上表的浅 subtle 底（hero band、callout box）。

示例网格写法（可按画幅微调）：

```css
.scene::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(#EFEFEF 2px, rgba(255,255,255,0) 2px),
    linear-gradient(90deg, #EFEFEF 2px, rgba(255,255,255,0) 2px);
  background-size: 72px 72px;
  opacity: 0.42;
  pointer-events: none;
  z-index: 0;
}
.scene-content { position: relative; z-index: 1; }
```

## 图标

### GitHub mark（`currentColor` 感知）

```html
<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" aria-label="GitHub">
  <path d="M12 1C5.923 1 1 5.923 1 12c0 4.867 3.149 8.979 7.521 10.436.55.096.756-.233.756-.522 0-.262-.013-1.128-.013-2.049-2.764.509-3.479-.674-3.699-1.292-.124-.317-.66-1.292-1.127-1.554-.385-.207-.936-.715-.014-.729.866-.014 1.485.797 1.691 1.128.99 1.663 2.571 1.196 3.204.907.097-.715.385-1.196.701-1.471-2.448-.275-5.005-1.224-5.005-5.432 0-1.196.426-2.186 1.128-2.956-.111-.275-.496-1.402.11-2.915 0 0 .921-.288 3.024 1.128a10.193 10.193 0 0 1 2.75-.371c.936 0 1.871.124 2.75.371 2.103-1.43 3.024-1.128 3.024-1.128.605 1.513.221 2.64.111 2.915.701.77 1.127 1.747 1.127 2.956 0 4.222-2.571 5.157-5.019 5.432.399.344.743 1.004.743 2.035 0 1.471-.014 2.654-.014 3.025 0 .289.206.632.756.522C19.851 20.979 23 16.854 23 12c0-6.077-4.922-11-11-11Z"/>
</svg>
```

### 语言色点

```html
<span class="lang-dot" style="background:#3178C6"></span>
<span>TypeScript</span>

<style>
.lang-dot {
  display: inline-block; width: 14px; height: 14px; border-radius: 50%;
  margin-right: 8px; vertical-align: middle;
}
</style>
```

## 动效

- 入场短促：`power2.out`（默认）、`expo.out`（hero）、duration 0.4-0.7s。
- **Stagger repo cards** 100-140ms，模拟 feed 灌入。
- **Count-up** 星数用 `gsap.to({ value, snap: 'value', duration: 1.2, ease: 'power1.out' })` 驱动 `textContent`。
- **Star pill micro-pulse** —— 卡片落定时，绿色 Star pill scale `1 → 1.06 → 1`，0.25s。
- **Octocat reveal** —— fade + 轻微 scale（`0.9 → 1`），0.4s。**不要旋转**。
- 永远不要 `repeat: -1`。

## 不要做

- ❌ 不要用 Mona Sans 渲染中文（无 CJK 字形）。中文一律走 `NotoSansSC`；Mona Sans 仅作可选拉丁品牌显示。
- ❌ 不要给 Octocat 染色。白底黑、黑底白，仅此而已。
- ❌ 不要给卡片加 drop shadow。GitHub 用 1px 边框。阴影 = 非 GitHub 感。
- ❌ 不要引入设计文件之外的 accent 色。在上面捕获的色板里按语义挑。
- ❌ 不要为了“丰富”而给无语义差异的同类元素随机换 accent 色。
- ❌ 不要把裸 accent 当小号正文色；语义正文优先用 callout 三件套。
- ❌ 不要满屏 linear gradient 背景。
- ❌ 不要把浅色背景网格做成高对比 checkerboard、扫描线、进度条或装饰覆盖层；它只能是低对比背景结构。
- ❌ 不要把深色顶栏当作 hero 背景。顶栏是 chrome，不是 hero。
- ❌ Hero title 字号不要超过 180px。
