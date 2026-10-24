# 设计主题：dawn（Rosé Pine Dawn × 手绘风）

温暖、平静、亲密。暖奶油画布上是 Rosé Pine Dawn 的柔紫灰文字和六个手绘语义色，配手写圈点、短 underline 和外置信息区左线。装饰元素允许有环境感 breathe / drift，但整体保持轻盈、安静。

这份文档只规定外观，任何类型的视频都能用。字体清单在 `fonts.json`，下载方式见 `designs/designs.md`。

---

## 1. 配色

### 1.1 原则

- 按信息语义使用 accent；允许同一画面出现多个语义色；禁止随机换色；禁止同一元素叠加多种 accent。
- Pine `#286983` 是唯一能承载可读 accent 文字的颜色；Foam / Love / Iris 只用于线、icon、tag、marker 或大号短字。
- Gold `#ea9d34` 只做辅助点缀、手绘圈点或非唯一 marker，禁止单独承载数字、文字或 UI 状态。
- 大号弱化文字用 `#797593`（只用于中 / 大号说明、meta），`#9893a5` 只用于装饰。

### 1.2 主题变量值

变量的含义见 `designs/designs.md`。浅底（高亮行 / 标签）直接用 surface `#f2e9e1` 或 card `#fffaf3`，不做额外的 accent 浅底。

| 变量 | 色值 |
|---|---|
| `--c-canvas` | `#faf4ed` |
| `--c-card` | `#fffaf3` |
| `--c-surface` | `#f2e9e1` |
| `--c-border` | `#cecacd` |
| `--c-ink` | `#575279` |
| `--c-ink2` | `#797593` |
| `--c-muted` | `#9893a5` |
| `--c-focus` | `#286983`（Pine） |
| `--c-focus-tint` | `#f2e9e1` |
| `--c-info` | `#56949f`（Foam） |
| `--c-warning` | `#b4637a`（Love，风险语义） |
| `--c-danger` | `#b4637a`（Love，Dawn 不用大红） |
| `--c-positive` | `#286983`（Pine） |
| `--c-positive-solid` | `#286983` |
| `--c-positive-tint` | `#fffaf3` |
| `--c-positive-text` | `#286983` |
| `--c-highlight` | `#ea9d34`（Gold，只做点缀） |
| `--c-done` | `#907aa9`（Iris） |
| `--c-chrome` | `#575279` |
| `--c-chrome-ink` | `#faf4ed` |
| `--c-chrome-muted` | `#cecacd` |
| `--c-chrome-active` | `#d7827e`（Rose） |
| `--c-tile0`–`--c-tile4` | `#f2e9e1` `#dcebea` `#bcd9d8` `#8fbfc2` `#56949f`：从桃米到 Foam 的色阶 |
| `--font-sans` | `"MaShanZheng", "NotoSansSC", sans-serif` |
| `--font-mono` | `"PatrickHand", "NotoSansSC", monospace` |

### 1.3 变量代码（复制到视频 `index.html` 的 `:root`）

```css
:root {
  --c-canvas: #faf4ed;  --c-card: #fffaf3;  --c-surface: #f2e9e1;  --c-border: #cecacd;
  --c-ink: #575279;     --c-ink2: #797593;  --c-muted: #9893a5;
  --c-focus: #286983;   --c-focus-tint: #f2e9e1;
  --c-info: #56949f;    --c-warning: #b4637a;  --c-danger: #b4637a;
  --c-positive: #286983;  --c-positive-solid: #286983;  --c-positive-tint: #fffaf3;  --c-positive-text: #286983;
  --c-highlight: #ea9d34; --c-done: #907aa9;
  --c-chrome: #575279;  --c-chrome-ink: #faf4ed;  --c-chrome-muted: #cecacd;  --c-chrome-active: #d7827e;
  --c-tile0: #f2e9e1;   --c-tile1: #dcebea;  --c-tile2: #bcd9d8;  --c-tile3: #8fbfc2;  --c-tile4: #56949f;
  --ground: #faf4ed;
  --font-sans: "MaShanZheng", "NotoSansSC", sans-serif;
  --font-mono: "PatrickHand", "NotoSansSC", monospace;
  --motion-enter-duration: 0.5s;
  --motion-easing: expo.out;
  --motion-list-interval: 0.15s;
}
```

字体在 `index.html` 的 `<head>` 里用 `<link rel="stylesheet" href="assets/fonts/rose-pine-dawn-fonts.css">` 引入（文件名以 `fonts.json` 的 `css_filename` 为准）。**绝不要用 Caveat 或 PatrickHand 显示中文字符**；中文一律用 `--font-sans` 栈里的 CJK 字体。英文 / 数字的强调手写体是 `Caveat`（马克笔感，700），正文手写体是 `PatrickHand`；`ZhiMangXing` 与 `LongCang` 是可选的装饰强调。

### 1.4 对比度

- 正文必须达到 4.5:1（`#575279` 在三个 Dawn 表面上都达标）；大号文字、icon、chart stroke、粗线 marker 至少 3:1。
- `#797593` 不承载小号正文；小号正文统一用 `#575279`；`#9893a5` 只用于装饰。
- Love `#b4637a` 与 Rose `#d7827e` 不在同一画面同时作状态信号；Love 优先配 ⚠ / 边线区分。

---

## 2. 字体与字号

| 用途 | 字体 | 字重 |
|---|---|---|
| 中文标题 / 正文 | `MaShanZheng`（手写） | 400 |
| 中文字幕 | `NotoSansSC`（黑体，稳定可读） | 400 |
| 英文 / 数字强调 | `Caveat` | 700 |
| 英文 / 数字正文 | `PatrickHand` | 400 |

### 2.1 视频尺寸（1920×1080；竖屏按同比例收敛，见 `layouts/portrait.md`）

| 元素 | 1920×1080 | 1080×1440 | 1080×1920 |
|---|---|---|---|
| Hero 标题 | 100–160px | 80–130px | 90–140px |
| Section 标题 | 60–90px | 50–76px | 56–80px |
| 正文 | 32–56px | 28–46px | 30–48px |
| 数据 label | 22–32px | 22–30px | 22–32px |
| 字幕 | 35px | 35px | 35px |

**字号下限**：阅读文字不小于 26px，数据 label 不小于 22px，字幕 35px（以所选 layout 的字幕规格为准）。

---

## 3. 背景与质感

- 默认背景是纯 `--c-canvas` 暖奶油色；不做网格、点阵或满屏装饰。
- 卡片平面化（`--c-card` 实底），避免厚重阴影，保持手绘氛围轻盈。

## 4. 形状

- 平面、有质感的卡片和 tag；圆角 label 在服务于信息设计时可以使用。
- 手绘 tag、badge、圈点、短 underline 和外置信息区左线是 Dawn 的主题专属标记。

## 5. 图标

- 手绘感短标记、圆点、圈线、箭头或 tag；图标 / marker 只服务信息层级，不把装饰图标铺满背景。

## 6. 动效

- 运动 token：`--motion-enter-duration: 0.5s`、`--motion-easing: expo.out`、`--motion-list-interval: 0.15s`——比 moon 活泼的节奏。
- 每次入场可以混用多种 ease（`expo.out`、`back.out(1.7)`、`power3.out`、`sine.out`）；除最终 scene 外不要用 exit 动画。
- 装饰元素允许有限重复的环境感 breathe / drift（`sine.inOut yoyo`）；标题先入场，辅助元素 stagger 跟进。
- 所有动画只由时间决定：不用 `repeat: -1`，不用随机数（需要随机时用固定种子）。

## 7. 不要做

- ❌ 不要用 shadow、gradient、glow、neon，不要用配色之外的高饱和颜色。
- ❌ 不要把 `#9893a5` 用在正文；不要把 `#797593` 当小号正文。
- ❌ 不要让 `#ea9d34` 单独承载数字、文字、线条或 UI 状态。
- ❌ 不要用拉丁手写字体显示中文；不要在同一个元素上叠加多种 accent 色。
- ❌ 不要把 accent 色作为大面积背景填充；标注不要压住素材关键区域。

---

> ## 「待迁 patterns」：按 visual_role 覆盖颜色
>
> 以下段落原来属于 style hint 的「`visual_role` 色彩覆盖」，等 patterns 文档建好后会迁到对应 pattern 的「用色」小节，届时此处删除。
>
> | `visual_role` | 配色方式 |
> |---|---|
> | `title` / `product_card` / `section_divider` | Primary 标题 + Rose / Iris eyebrow；身份信息可用 Pine 短 label。 |
> | `leaderboard` / `big_number` / `data_block` / `metric_strip` | 数字用 Primary 或 Pine；当前排名 / 重点数字可配 Gold 小点缀；变化趋势用 Foam / Love 线。 |
> | `data_table` / `chart` | 表格正文 Primary；表头 Secondary 大号；highlight cell 用 Pine / Love / Foam 线，Gold 只做非唯一辅助点；series 用 Foam / Pine / Iris。 |
> | `timeline` / `process_flow` / `state_machine` | 节点正文 Primary；当前节点用 Pine / Primary + Gold 点缀；完成节点 Pine；连接线 Foam / Iris。 |
> | `architecture_diagram` / `network_graph` | 模块边线用 Foam / Pine；依赖关系用 Iris；关键路径用 Pine，Gold 只做小 marker。 |
> | `comparison_matrix` / `pros_cons` | 双侧对比用 Pine vs Love；中性维度 Primary；优缺点标签用短 badge，不给整列大面积上色。 |
> | `list` / `feature_grid` | item label Primary；bullet / index 用 Foam / Rose / Pine 按语义区分；detail 用 Primary 或大号 Secondary。 |
> | `callout` / `definition` / `qa` | callout 用 `card` 或 `surface` 底 + 语义色左线；definition 用 Iris；QA 的 Q 用 Foam、A 用 Pine。 |
> | `code_block` / `terminal_block` / `file_tree` | panel 底 `#fffaf3`；路径 / 命令重点用 Pine；注释 / prompt 用 Iris；warning 输出用 Love 或 Gold marker。 |
> | `annotated_media` | 标注必须在素材外置信息区；pin / arrow 用 Gold / Foam；说明文字 Primary。 |
> | `quote` | 引号 / source 用 Rose 或 Iris；正文 Primary；不要用 Subtle 承载 quote 正文。 |
