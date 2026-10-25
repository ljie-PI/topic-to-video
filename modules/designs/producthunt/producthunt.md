# 设计主题：producthunt（Product Hunt 产品风）

温暖、产品优先、对话感。白底上是 Product Hunt 的品牌橙和产品语义色：主推橙、注册蓝、maker 绿。PH 靠 1px 边框和浅 tint 分区，不用厚阴影。

这份文档只规定外观，任何类型的视频都能用。字体清单在 `fonts.json`，下载方式见 `designs/designs.md`。

---

## 1. 配色

### 1.1 原则

- 品牌橙 `#FF6154` 是核心识别色（logo、upvote 边框、CTA 外形、hero ranking marker），**不作为正文色或唯一信息信号**。
- 橙色语义文字用高对比 `#C8392F`，或主推 callout 三件套：`#FFF1ED` 底 / `#FF6154` 边 / `#C8392F` 字。
- 绿色语义文字 / 线条用 `#046B50`；`#00B27F` 只做 maker badge 外形。蓝色 `#0075FF` 用于 link、icon、badge 和大号 marker；长说明文字用 `#0B4FA8`。
- PH 不靠颜色表达 danger：warning / 限制用中性 chip + ⚠ / 「注意」前缀。契约要求的 `--c-warning` / `--c-danger` 因此都映射到高对比橙 `#C8392F`（配合 ⚠ 图标表达），不使用红色和黄色。

### 1.2 主题变量值

变量的含义见 `designs/designs.md`。额外的表面色：次级 / hero band `#F8F9FA`，chip / 分段控件 `#EAECF0`。

| 变量 | 色值 |
|---|---|
| `--c-canvas` | `#FFFFFF` |
| `--c-card` | `#FFFFFF` |
| `--c-surface` | `#F8F9FA` |
| `--c-border` | `#E5E7EB` |
| `--c-ink` | `#21293C` |
| `--c-ink2` | `#4B587C` |
| `--c-muted` | `#988F8C` |
| `--c-focus` | `#C8392F`（高对比橙文字） |
| `--c-focus-tint` | `#FFF1ED` |
| `--c-info` | `#0075FF` |
| `--c-warning` | `#C8392F`（中性 chip + ⚠ 表达） |
| `--c-danger` | `#C8392F`（PH 不用红，配合 ⚠ 表达） |
| `--c-positive` | `#046B50` |
| `--c-positive-solid` | `#00B27F` |
| `--c-positive-tint` | `#E6F7F1` |
| `--c-positive-text` | `#046B50` |
| `--c-highlight` | `#FF6154`（品牌外形色） |
| `--c-done` | `#00B27F` |
| `--c-chrome` | `#21293C` |
| `--c-chrome-ink` | `#FFFFFF` |
| `--c-chrome-muted` | `#E5E7EB` |
| `--c-chrome-active` | `#FF6154` |
| `--c-tile0`–`--c-tile4` | `#F4F2EE` `#FFE3DD` `#FFC4BA` `#FF9384` `#FF6154`：从中性 chip 到品牌橙的色阶 |
| `--font-sans` | `"NotoSansSC", sans-serif` |
| `--font-mono` | `"IBMPlexMono", "NotoSansSC", monospace` |

### 1.3 变量代码（复制到视频 `index.html` 的 `:root`）

```css
:root {
  --c-canvas: #ffffff;  --c-card: #ffffff;  --c-surface: #f8f9fa;  --c-border: #e5e7eb;
  --c-ink: #21293c;     --c-ink2: #4b587c;  --c-muted: #988f8c;
  --c-focus: #c8392f;   --c-focus-tint: #fff1ed;
  --c-info: #0075ff;    --c-warning: #c8392f;  --c-danger: #c8392f;
  --c-positive: #046b50;  --c-positive-solid: #00b27f;  --c-positive-tint: #e6f7f1;  --c-positive-text: #046b50;
  --c-highlight: #ff6154; --c-done: #00b27f;
  --c-chrome: #21293c;  --c-chrome-ink: #ffffff;  --c-chrome-muted: #e5e7eb;  --c-chrome-active: #ff6154;
  --c-tile0: #f4f2ee;   --c-tile1: #ffe3dd;  --c-tile2: #ffc4ba;  --c-tile3: #ff9384;  --c-tile4: #ff6154;
  --ground: #ffffff;
  --font-sans: "NotoSansSC", sans-serif;
  --font-mono: "IBMPlexMono", "NotoSansSC", monospace;
  --motion-enter-duration: 0.5s;
  --motion-easing: power3.out;
  --motion-list-interval: 0.2s;
}
```

字体在 `index.html` 的 `<head>` 里用 `<link rel="stylesheet" href="assets/fonts/rose-pine-producthunt-fonts.css">` 引入（文件名以 `fonts.json` 的 `css_filename` 为准）。拉丁品牌显示字体 Inter（variable，700/800）可选：仅用于纯英文 hero / 产品名，无则回退 `NotoSansSC`；**绝不要用 Inter 显示中文**。

### 1.4 对比度

- Primary `#21293C` 和 Secondary `#4B587C` 可在白 / 浅灰底上承载正文（16.4:1 / 8.2:1）；Tertiary `#988F8C` 只做 metadata。
- 大号文字、icon、chart stroke、粗线 marker 至少 3:1；低于 3:1 的颜色只能做装饰或 brand-only 外形。
- 全部数据读数必须 `font-variant-numeric: tabular-nums`。

---

## 2. 字体与字号

- 中文标题 / Hero `NotoSansSC` 700；section 标题 600；正文 / tagline / meta 400/500；字幕 500。
- 数字 / upvote / 英文数据用 `IBMPlexMono` 600（tabular-nums）。

### 2.1 视频尺寸（1920×1080；竖屏按同比例收敛，见 `layouts/portrait.md`）

| 元素 | 1920×1080 | 1080×1440 | 1080×1920 |
|---|---|---|---|
| Hero（"Top Products Launching Today"） | 120–160px | 100–138px | 108–148px |
| 产品名 | 56–72px | 48–62px | 52–66px |
| Tagline（产品名下一行） | 32–40px | 28–36px | 30–38px |
| Topic chip | 22–26px | 22–26px | 22–26px |
| Upvote 数（tabular-nums） | 48–64px | 42–56px | 46–60px |
| Section eyebrow（uppercase） | 22–26px | 22–26px | 22–26px |
| 字幕 | 35px | 35px | 35px |

**字号下限**：阅读文字不小于 26px，chip / eyebrow 不小于 22px，字幕 35px（以所选 layout 的字幕规格为准）；Hero 不超过 160px。

---

## 3. 背景与质感

- 画布保持白；区域填充只用浅 tint 底（hero band `#F8F9FA`、callout tint）。
- **不要做饱和满屏背景**；饱和橙只用在 mark、upvote、CTA pill 上。

## 4. 形状

- 圆角统一：卡片 12–16px、缩略图 8–12px，永远不用尖角。
- 最多 `0 2px 8px rgba(0,0,0,.04)` 的 hover 微抬，不要厚 drop shadow；默认 1px 边框。
- 主题专属标记：P disc、upvote pill、maker badge、topic chip、CTA 外形。

## 5. 图标

- "P" logo disc（圆 + 白色 P 字标）和 upvote pill 的写法见 Product Hunt 品牌资产；图标保持产品风，不引入新色板。

## 6. 动效

- 运动 token：`--motion-enter-duration: 0.5s`、`--motion-easing: power3.out`、`--motion-list-interval: 0.2s`——对话感、有活力的节奏。
- 卡片 stagger 180–220ms 倒数入场；upvote pill 落定弹一下 + 数字 count-up；hero 标题可 word-by-word（80ms stagger）。
- 有限脉冲允许（如 promoted 卡橙边每 4s 脉冲、共 3 次）；永远不要 `repeat: -1`。
- 所有动画只由时间决定；不用随机数（需要随机时用固定种子）。

## 7. 不要做

- ❌ 不要用红色替代 `#FF6154`；不要把 kitty 放进 P disc 里面。
- ❌ 不要把饱和橙做满屏背景；不要把 `#FF6154` / `#00B27F` 当正文色或唯一信息信号。
- ❌ 不要用厚 drop shadow；Hero 字号不要超过 160px；Logotype 永远是 "Product Hunt" 两个首字母大写的单词。
- ❌ 不要为了「丰富」而给无语义差异的同类元素随机换 accent 色。

---

> ## 「待迁 patterns」：按 visual_role 覆盖颜色
>
> 以下段落原来属于 style hint 的「`visual_role` 色彩覆盖」，等 patterns 文档建好后会迁到对应 pattern 的「用色」小节，届时此处删除。
>
> | `visual_role` | 配色方式 |
> |---|---|
> | `title` / `product_card` / `section_divider` | 产品名 Primary；launch / rank / CTA 文字用 `#C8392F` 或 Primary，主橙只做 marker / 外形；tagline 用 Secondary。 |
> | `leaderboard` / `big_number` / `data_block` / `metric_strip` | upvote / rank 的外形用主橙，文字用 Primary / `#C8392F`；maker / verified metric 文字用 `#046B50`；注册 / traffic info 用蓝色。 |
> | `data_table` / `chart` | 表格正文 Primary / Secondary；highlight cell 用 callout tint；信息性橙色 series 用 `#C8392F`，主橙只作辅助 marker。 |
> | `timeline` / `process_flow` / `state_machine` | launch step 可用 `#C8392F` 文本 / 线 + `#FF6154` 外形点缀；register / onboarding 用蓝；maker verified 用 `#046B50`。 |
> | `architecture_diagram` / `network_graph` | product / CTA 节点用 `#C8392F` 文本或线，用户 / register 蓝，maker / partner 用 `#046B50`；正文 Primary。 |
> | `comparison_matrix` / `pros_cons` | 推荐 / maker fit 用绿；注册 / info 用蓝；限制 / attention 用中性 chip + ⚠，不用橙 callout 或红。 |
> | `list` / `feature_grid` | feature icon 若承载信息用 `#C8392F` / 蓝 / `#046B50` 按语义；item label Primary，detail Secondary。 |
> | `callout` / `definition` / `qa` | 主推、注册 / info、Maker / verified、中性四套 callout 三件套；QA 的 Q 可用蓝，A 用 Primary。 |
> | `code_block` / `terminal_block` / `file_tree` | panel 用 `#F8F9FA`；命令 / path 用 mono；CTA / success / info 状态分别用橙 / 绿 / 蓝 marker。 |
> | `annotated_media` | 标注在素材外置信息区；pin 用 `#C8392F` 或蓝，主橙只作非唯一外形点缀。 |
> | `quote` | quote 正文 Primary；source / timestamp Tertiary；用户评价亮点可用主推 callout。 |
