# Style Hint — Product Hunt × 温暖、产品优先

> Phase 8 style hint。按本文件执行 Product Hunt 产品风、配色、排版、形状和动效约束。
> 姊妹预设：`references/design-dawn.md`（手绘）、`references/design-moon.md`（深色技术）、`references/design-github.md`（GitHub）。

## 配色（只用以下颜色）

**Brand**
- 主橙 / 火焰色：`#FF6154`（**核心识别色** —— logo、upvote 边框、CTA 外形、hover marker；不作为正文色）
- 旧版深橙（仅匹配 pre-2024 资产）：`#DA552F`
- Kitty face 橙红：`#FA5757`
- 次级 CTA 蓝：`#0075FF`（newsletter / 注册流）
- Maker badge 绿：`#00B27F`（"verified" / "maker" badge 外形；可读绿色文字用 `#046B50`）

**Backgrounds**
- 主画布：`#FFFFFF`
- 次级 / 段落交替 / hero band：`#F8F9FA`
- Chip / 分段控件 / 搜索条：`#EAECF0`

**Text**
- Primary / 标题 / 产品名：`#21293C`
- Secondary / 正文 / tagline / meta：`#4B587C`
- Tertiary / 时间戳 / "Promoted" 标：`#988F8C`（metadata only，不用于正文）
- 高对比（白 logo 里的 "P"）：`#000000`

**Borders / 分割线**
- 卡片 1px：`#E5E7EB`

**Semantic accents / 使用场景**

按 Product Hunt 产品语义使用 accent；允许同一 scene 出现多个语义色；禁止随机换色；禁止同一元素叠加多种 accent。

- 主橙 `#FF6154` —— brand、logo、upvote 边框、CTA 外形、hero ranking marker、产品 launch 强调；禁止作为唯一信息信号或正文色。
- 旧版深橙 `#DA552F` —— 仅匹配 pre-2024 资产，不主动作为新 UI 色。
- Kitty face 橙红 `#FA5757` —— 仅用于 kitty / marketing 资产匹配，不替代主橙。
- 次级 CTA 蓝 `#0075FF` —— register、newsletter、info、productivity chip、secondary action。
- Maker badge 绿 `#00B27F` —— verified / maker badge 外形；success / maker 的可读文字、信息线和图表线用 `#046B50`。

### 主题专属标记

使用 P disc、upvote pill、maker badge、topic chip 和 CTA 外形。

Topic chip accents（可选）：

- AI / SaaS → 底 `#F4F2EE`、文字 `#21293C`
- Productivity → 底 `#EEF7FF`、文字 `#0075FF`
- Design → 底 `#FFF1ED`、文字 `#C8392F`、marker `#FF6154`

### 颜色使用场景

| 场景 | 前景 | 背景 / 表面 | 线 / 标记 | 规则 |
|------|------|-------------|-----------|------|
| Canvas / scene base | `#21293C` / `#4B587C` | `#FFFFFF` | `#E5E7EB` | 正文用 Primary / Secondary；Tertiary 只做 metadata。 |
| Surface / card | `#21293C` / `#4B587C` | `#FFFFFF` | `#E5E7EB` | 产品卡可微 hover shadow，但默认仍是 1px border。 |
| Band / section alternate | `#21293C` / `#4B587C` | `#F8F9FA` | `#E5E7EB` | hero band / section alternate，不做饱和橙底。 |
| Chip / control | `#21293C` | `#EAECF0` / topic chip tint | `#E5E7EB` | chip 文字用配套文字色；不混用多套 chip 色。 |
| Featured / launch / CTA | `#C8392F` 或 `#21293C` | `#FFF1ED` / 白底按钮 | `#FF6154` | 正文型主推用 callout；按钮 / upvote 用橙色边框或外形 + 高对比文字。 |
| Info / register / secondary action | `#0B4FA8` | `#EEF7FF` | `#0075FF` | 蓝色用于注册、newsletter、info，不抢主橙身份。 |
| Maker / verified / success | `#046B50` | `#E6F7F1` | `#00B27F` / `#046B50` | maker badge 外形可用 `#00B27F`；信息性文字 / 线条用 `#046B50`。 |
| Warning / risk / limitation | `#21293C` | `#F4F2EE` | `#E5E7EB` + ⚠ icon | 限制 / 风险用中性 chip + ⚠ / 「注意」前缀；不用橙色 callout；不另加黄 / 红。 |
| Neutral / metadata / promoted | `#21293C` / `#988F8C` | `#F4F2EE` / `#F8F9FA` | `#E5E7EB` | promoted / timestamp 用 Tertiary，但不承担正文。 |
| Tags / badges / progress | `#21293C` / callout text | topic chip / callout tint | `#FF6154` / `#0075FF` / `#046B50` | category chip、maker badge、rank、upvote、progress step 按产品语义用色；可读文字用 callout text 色。 |
| Callout boxes / role surfaces | callout text 色 | callout tint | callout border | callout、definition、QA、quote 优先使用四套三件套，不裸用主橙正文。 |
| Code / terminal / file tree | `#21293C` / `#4B587C` | `#F8F9FA` | `#0075FF` / `#C8392F` / `#046B50` | 命令和数据用 mono；状态可用蓝 / 橙 / 绿短 marker，橙 / 绿信息线用高对比文字色。 |
| Diagram connector / graph node | `#21293C` | `#FFFFFF` / `#F8F9FA` | `#0075FF` / `#046B50` / `#C8392F` | 产品流、maker、CTA 分别用蓝 / 高对比绿 / 高对比橙；品牌色只作外形点缀。 |
| Media annotation | `#21293C` / callout text | 素材外部信息区 | `#C8392F` / `#0075FF` | 不把 tag、badge、callout 压在素材关键区域；橙色 pin 用高对比文本色或主推 callout 边。 |
| Subtitle | `#21293C` 或 `#FFFFFF` | shrink-to-fit 遮罩 | `#E5E7EB` | 字幕优先稳定可读，不用主橙作字幕正文。 |

### 标题配色与高亮 box

画布保持白，但标题与 callout 可以按真实语义上色：

**标题**
- 正文标题维持 `#21293C`。
- Hero 可坐落在浅色 band 上：中性 `#F8F9FA`，或淡橙 `#FFF1ED` / 淡蓝 `#EEF7FF`。
- 标题关键词、排名数字、"今日 / Top" 若需要橙色文字，用 `#C8392F`；品牌橙 `#FF6154` 只做旁边 marker、underline、icon 或大形状。
- Section eyebrow（uppercase）：橙色文字用 `#C8392F`，蓝色文字用 `#0075FF`。

**高亮 box / callout**（小卡，**不是**满屏背景）—— 底 / 1px 边 / 文字 三件套：

| 语义 | 底 | 边 | 文字 |
|------|----|----|------|
| 主推（橙） | `#FFF1ED` | `#FF6154` | `#C8392F` |
| 注册 / info（蓝） | `#EEF7FF` | `#0075FF` | `#0B4FA8` |
| Maker / verified（绿） | `#E6F7F1` | `#00B27F` | `#046B50` |
| 中性（chip） | `#F4F2EE` | `#E5E7EB` | `#21293C` |

裸 `#FF6154` 只用于 mark、upvote 边框、CTA 外形、icon、marker 或品牌形状。橙色语义文字使用 `#C8392F`，或使用上表的主推三件套：`#FFF1ED` 底、`#FF6154` 边、`#C8392F` 文字。

主推三件套只表正向 / featured / launch。warning / 限制不复用主推橙，改用中性三件套 + ⚠ / 「注意」前缀。

### `visual_role` 色彩覆盖

| `visual_role` | 配色方式 |
| --- | --- |
| `title` / `product_card` / `section_divider` | 产品名 Primary；launch / rank / CTA 文字用 `#C8392F` 或 Primary，主橙只做 marker / 外形；tagline 用 Secondary。 |
| `leaderboard` / `big_number` / `data_block` / `metric_strip` | upvote / rank 的外形用主橙，文字用 Primary / `#C8392F`；maker / verified metric 文字用 `#046B50`；注册 / traffic info 用蓝色。 |
| `data_table` / `chart` | 表格正文 Primary / Secondary；highlight cell 用主推 / 蓝 / 绿 callout tint；信息性橙色 series 用 `#C8392F`，主橙只作辅助 marker。 |
| `timeline` / `process_flow` / `state_machine` | launch step 可用 `#C8392F` 文本 / 线 + `#FF6154` 外形点缀；register / onboarding 用蓝；maker verified 用 `#046B50`。 |
| `architecture_diagram` / `network_graph` | product / CTA 节点用 `#C8392F` 文本或线，用户 / register 蓝，maker / partner 用 `#046B50`；正文 Primary。 |
| `comparison_matrix` / `pros_cons` | 推荐 / maker fit 用绿；注册 / info 用蓝；限制 / attention 用中性 chip + ⚠，不用橙 callout 或红。 |
| `list` / `feature_grid` | feature icon 若承载信息用 `#C8392F` / 蓝 / `#046B50` 按语义；item label Primary，detail Secondary；主橙 / maker green 只做品牌形状。 |
| `callout` / `definition` / `qa` | 主推、注册 / info、Maker / verified、中性四套 callout 三件套；QA 的 Q 可用蓝，A 用 Primary。 |
| `code_block` / `terminal_block` / `file_tree` | panel 用 `#F8F9FA`；命令 / path 用 mono；CTA / success / info 状态分别用橙 / 绿 / 蓝 marker。 |
| `annotated_media` | 标注在素材外置信息区；pin 用 `#C8392F` 或蓝，主橙只作非唯一外形点缀；解释文字 Primary / Secondary。 |
| `quote` | quote 正文 Primary；source / timestamp Tertiary；用户评价亮点可用主推 callout。 |

### 对比度 guardrails

- 正文必须达到 4.5:1；大号文字、icon、chart stroke、粗线 marker 必须达到 3:1；低于 3:1 的颜色只能做装饰或 brand-only 外形。
- Primary `#21293C` 和 Secondary `#4B587C` 可在白 / 浅灰底上承载正文；Tertiary `#988F8C` 只做 metadata。
- `#FF6154` 是 brand / logo / upvote 边框 / CTA 外形色，不作为正文色或唯一信息信号。
- 需要橙色语义文字、线条或图表 series 时，用 `#C8392F` 或主推 callout 三件套。
- `#00B27F` 是 maker badge 外形色，不作为正文色或唯一信息信号；需要绿色语义文字、线条或图表 series 时，用 `#046B50` 或 Maker callout 三件套。
- 蓝色 `#0075FF` 可用于 link、icon、badge 和大号 marker；长说明文字使用 `#0B4FA8` 或 info callout 三件套。
- PH 不靠颜色表达 danger；橙色 `#FF6154` / `#C8392F` 只表品牌 / featured / 正向；warning / 限制用中性 chip + ⚠ icon，不与 featured 同色。

## 排版

中文字体复用 **Moon 预设**（`references/design-moon.md`）的确定性 CJK 字体，经 `scripts/fonts-download.sh <target_dir> moon` 预置；拉丁品牌字体（Inter）可选。

| 用途 | 字体 | 字重 | 备注 |
|------|------|------|------|
| 中文标题 / Hero | `NotoSansSC` | 700 | 引自 Moon |
| 中文 section 标题 | `NotoSansSC` | 600 | |
| 中文正文 / tagline / meta | `NotoSansSC` | 400 / 500 | |
| 中文字幕 | `NotoSansSC` | 500 | |
| 数字 / upvote / 英文数据 | `IBMPlexMono` | 600 | tabular-nums |
| 拉丁品牌显示（可选） | `Inter`（variable） | 700 / 800 | 仅当 workspace 提供；纯英文 hero / 产品名，紧排 -0.02em；无则回退 `NotoSansSC` |

**绝不要用 Inter 显示中文长串**；中文一律走 `NotoSansSC`。所有读数使用 `font-variant-numeric: tabular-nums`。

## 视频尺寸（覆盖网页常规尺寸）

| 元素 | 1920×1080 | 1080×1440 | 1080×1920 | 字重 |
|------|-----------|-----------|-----------|------|
| Hero（"Top Products Launching Today"） | 120-160px | 100-138px | 108-148px | 800 |
| 产品名 | 56-72px | 48-62px | 52-66px | 700 |
| Tagline（产品名下一行） | 32-40px | 28-36px | 30-38px | 400 |
| Topic chip | 22-26px | 22-26px | 22-26px | 500 |
| Upvote 数（tabular-nums） | 48-64px | 42-56px | 46-60px | 700 |
| Section eyebrow（uppercase） | 22-26px | 22-26px | 22-26px | 600 |
| 字幕 | 35px | 35px | 35px | 500 |
| Padding（.scene） | 90px 140px | 90px 80px | 90px 70px | — |

## 形状风格

- 圆角统一：卡片 12-16px、缩略图 8-12px。**永远不用尖角**。
- 不要厚阴影。最多 `0 2px 8px rgba(0,0,0,.04)` 的 hover 微抬。
- 主橙用于 mark、upvote 边框、CTA 外形和品牌 marker；可读橙色文字 / 图表线用 `#C8392F`。**不要做饱和满屏背景**。画布保持白；区域填充只用上表的浅 tint 底（hero band、callout box）。

## 图标

### "P" logo disc

```html
<svg viewBox="0 0 40 40" width="40" height="40" aria-label="Product Hunt">
  <circle cx="20" cy="20" r="20" fill="#FF6154"/>
  <path fill="#FFFFFF" d="M16 11h7.2c3.76 0 6.8 3.04 6.8 6.8s-3.04 6.8-6.8 6.8H19v4.4h-3V11Zm3 3v6.6h4.2a3.3 3.3 0 0 0 0-6.6H19Z"/>
</svg>
```

### Upvote pill

```html
<div class="ph-upvote">
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none"
       stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <path d="M5 15 L12 8 L19 15"/>
  </svg>
  <span class="count">1,247</span>
</div>

<style>
.ph-upvote {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  width: 56px; height: 64px; border-radius: 8px;
  background: #FFFFFF; border: 2px solid #FF6154; color: #C8392F;
  font-family: "IBMPlexMono", monospace; font-weight: 700;
}
.ph-upvote .count {
  font-size: 14px; line-height: 1; margin-top: 2px;
  font-variant-numeric: tabular-nums;
}
</style>
```

## 动效

PH 是对话感、有活力的 —— 视频也要对得上。

- **Card stagger** —— 产品从 #5 → #1 倒数入场，每行 stagger 180-220ms，`back.out(1.2)`，`y: 40 → 0`。
- **Upvote pop** —— 卡片落定时，upvote pill scale `0.85 → 1.08 → 1`，0.5s `elastic.out(1, 0.5)`，紧接着数字 0 → 终值 count-up 0.9s。
- **Hero word-by-word** —— "Top Products Launching Today" 一个词一个词入场，80ms stagger，`power3.out`。
- **Logo orbit** —— 收尾卡里 "P" disc 从画外滑入到 wordmark 旁，`gsap.from({ x: -120, opacity: 0, duration: 0.6, ease: 'expo.out' })`。
- **Promoted glow** —— promoted 卡橙边线每 4s 脉冲一次，**有限 3 次**（`repeat: 2`）。
- 永远不要 `repeat: -1`。

## 不要做

- ❌ 不要用红色替代 `#FF6154`。
- ❌ 不要把 kitty 放进 P disc 里面。
- ❌ 不要用 Helvetica / Arial 替代 Inter。
- ❌ Logotype 不要小写或斜体。永远是 "Product Hunt"，两个首字母大写的单词。
- ❌ 不要把**饱和**橙做满屏背景。canvas 保持白；饱和橙只用在 mark、upvote、CTA pill 上；区域底色用浅橙 `#FFF1ED` 等 tint。
- ❌ 不要用厚 drop shadow。PH 用 1px 边框 + 最多极淡 hover lift。
- ❌ Hero 字号不要超过 160px。
- ❌ 不要把 `#FF6154` 当正文色或唯一信息信号；需要橙色语义文字时用 `#C8392F` 或主推 callout。
- ❌ 不要把 `#00B27F` 当正文色或唯一信息信号；需要绿色语义文字 / 线条时用 `#046B50` 或 Maker callout。
- ❌ 不要为了“丰富”而给无语义差异的同类元素随机换 accent 色。
