# 设计主题：default（燕麦纸）

一张暖燕麦色的棉纸，上面是低饱和的墨灰文字和一点灰薰衣草。画面里最显眼的是内容和论断，界面退到后面。不加阴影，用 2px 细线和卡片分层，看起来像一份安静、干净的编辑稿。没有指定风格时用这个主题，适合大多数讲解视频。

这份文档只规定外观，任何类型的视频都能用。

背景贴图在 `designs/default/textures/`，用的时候复制到视频工程的 `assets/textures/`。字体已经放在仓库的 `resources/fonts/`（CSS 在 `default/`，WOFF2 在共用的 `files/`），安装方式见 1.4。

| 文件 | 用途 |
|---|---|
| `textures/paper.jpg` | 背景：暖燕麦棉纸，1920×1080 |

---

## 1. 配色

### 1.1 颜色只有四种用途

每一帧最多一种焦点色，再加上指标色的数字：

- **焦点（灰薰衣草）**：正在讲的东西，包括当前高亮的行、当前步骤、当前结论、当前标签。
- **指标（鼠尾草绿）**：数字、增长、正面的结果。只用在数字和指标上，不拿来做装饰。
- **标记（赭黄）**：被收藏、被标记的状态，以及需要观众记住的关键词。只做形状和大号短字。
- **完成（深靛）**：讲完的步骤。

信息蓝、琥珀、砖红只表达真实的 info / warning / danger 语义，不做装饰。

### 1.2 主题变量值

变量的含义见 `designs/designs.md`。

| 变量 | 色值 |
|---|---|
| `--c-canvas` | `#F3F1EC` |
| `--c-card` | `#FBFAF7` |
| `--c-surface` | `#F1EEE8` |
| `--c-border` | `#D9D4CC` |
| `--c-ink` | `#25232A` |
| `--c-ink2` | `#58545F` |
| `--c-muted` | `#878290` |
| `--c-focus` | `#5E559E` |
| `--c-focus-tint` | `#ECE9F4` |
| `--c-info` | `#3E6994` |
| `--c-warning` | `#94661B` |
| `--c-danger` | `#A4434A` |
| `--c-positive` | `#3D7353` |
| `--c-positive-solid` | `#4A8261` |
| `--c-positive-tint` | `#E5EEE7` |
| `--c-positive-text` | `#2C573F` |
| `--c-highlight` | `#A3823F` |
| `--c-done` | `#4C4583` |
| `--c-chrome` | `#2A282F` |
| `--c-chrome-ink` | `#F5F3EF` |
| `--c-chrome-muted` | `#A6A1AD` |
| `--c-chrome-active` | `#B2A6DE`（淡薰衣草） |
| `--c-tile0`–`--c-tile4` | `#E8E4DD` `#D9D4E6` `#B8B0D5` `#8A80BD` `#5E559E`：从纸色到焦点薰衣草的色阶 |
| `--font-sans` | `"NotoSansSC", sans-serif` |
| `--font-mono` | `"IBMPlexMono", "NotoSansSC", monospace` |

### 1.3 对比度

- 正文：`ink` 在卡片底上 14.9:1，`ink2` 7.1:1；`focus` 在卡片底上 6.2:1，在 `focus-tint` 上 5.4:1。
- `--c-muted` 在卡片底上只有约 3.6:1，只能用在 34px 以上的数字上。
- `--c-highlight` 在卡片底上约 3.5:1，只做形状、图标和大号短字，不承载正文。
- 界面条上的次要文字用 `--c-chrome-muted`，约 5.8:1。
- 指标色标签里的文字用 `--c-positive-text`（在 `positive-tint` 上 7.0:1），不要直接用 `--c-positive`。

### 1.4 变量代码（复制到视频 `index.html` 的 `:root`）

```css
:root {
  --c-canvas: #f3f1ec;  --c-card: #fbfaf7;  --c-surface: #f1eee8;  --c-border: #d9d4cc;
  --c-ink: #25232a;     --c-ink2: #58545f;  --c-muted: #878290;
  --c-focus: #5e559e;   --c-focus-tint: #ece9f4;
  --c-info: #3e6994;    --c-warning: #94661b;  --c-danger: #a4434a;
  --c-positive: #3d7353;  --c-positive-solid: #4a8261;  --c-positive-tint: #e5eee7;  --c-positive-text: #2c573f;
  --c-highlight: #a3823f; --c-done: #4c4583;
  --c-chrome: #2a282f;  --c-chrome-ink: #f5f3ef;  --c-chrome-muted: #a6a1ad;  --c-chrome-active: #b2a6de;
  --c-tile0: #e8e4dd;   --c-tile1: #d9d4e6;  --c-tile2: #b8b0d5;  --c-tile3: #8a80bd;  --c-tile4: #5e559e;
  --ground: url("assets/textures/paper.jpg") center / cover, #f3f1ec;
  --font-sans: "NotoSansSC", sans-serif;
  --font-mono: "IBMPlexMono", "NotoSansSC", monospace;
  --motion-enter-duration: 0.2s;
  --motion-easing: power1.out;
  --motion-list-interval: 0.12s;
}
```

字体已经下载好放在仓库的 `resources/fonts/`（CSS 在 `default/`，WOFF2 在共用的 `files/`）。安装：`bash scripts/fonts-download.sh <工程>/assets/fonts --theme modules/designs/default`，把 NotoSansSC（中文和正文）、IBMPlexMono（代码、数字、路径）的 WOFF2 和一份 `default-fonts.css` 拷进工程，不联网。在 `index.html` 的 `<head>` 里用 `<link rel="stylesheet" href="assets/fonts/default-fonts.css">` 引入，CSS 里的字体名就是上面变量用的 `NotoSansSC` / `IBMPlexMono`。

---

## 2. 字体

- 标题、正文、屏幕文字和字幕都用 NotoSansSC；不用宋体、衬线中文或手写体。
- IBMPlexMono 只用于标识符、日志、路径、代码和数字，不排整段中文。
- 会滚动或需要对齐的数字一律用等宽数字（`font-variant-numeric: tabular-nums`），比如排名、计数、日期、标签。
- 字重：正文 400–500，标签和按钮 600，标题和数字 700。正文行高至少 1.5。

### 2.1 字号阶梯（1920×1080）

| 级别 | 字号 / 字重 | 典型用途 |
|---|---|---|
| 特大数字 | 128–150px / 700–800 | 封面上的核心数字、转场卡片上的大标签 |
| 开场标题 | 140px / 700，字距 -0.01em | 开场大标题 |
| 大标题 | 72px / 400 + 700 | 封面主名称（过长时自动缩小，最小 36px） |
| 标题 | 56–60px / 700 | 页眉行标题、一句话介绍 |
| 小标题 | 44–48px | 标题条里的名称、转场卡片标题 |
| 强调正文 | 30–36px / 600–700 | 步骤标题、指标说明、字幕（36px / 500） |
| 正文 | 26–28px / 500 | 描述、列表文字、标签页（28px / 600） |
| 界面小字 | 22–26px / 600 | 面板标题栏、按钮、小标签 |

竖屏画布（1080×1920、1080×1440）宽只有 1080px：特大数字、开场标题、大标题、标题、小标题按上表取值的 0.85 倍（取整到偶数）；强调正文、正文、界面小字以及下面的两条下限都不变。

**字号下限**：阅读文字不小于 26px，界面小字不小于 22px（只适用于放在 `data-text-role="ui"` 元素里的面板标题栏、按钮、小标签），字幕 36px（以所选 layout 的字幕规格为准）。渲染前检查（check-composition）按这两个下限分别检查。HyperFrames 的检查会把 28px 以下的文字报成警告：阅读文字要按警告处理；界面小字可以忽略这条警告。

---

## 3. 背景与质感

- 背景是**暖燕麦棉纸** `textures/paper.jpg`，铺满整个画面（`--ground`）。上面不要再叠网格、点阵或方格底纹。
- 纸纹按 `designs/github/github.md` 第 3 节的做法生成，换成这套颜色：
  - 底色 `#F3F1EC`；
  - 深纤维偏暖灰 `#A29B91`；
  - 四角压暗约 12 级亮度，暗部偏灰薰衣草 `#B4AEC4`；
  - 其余参数（低频斑驳、纸齿、纤维和杂点数量、颗粒）与 github 相同。
- 贴图是 1920×1080，用 `center / cover` 铺满：竖屏画布（1080×1920、1080×1440）会把它放大后取中间，不平铺、不出接缝。
- 背景是静态的，不做动画。
- 卡片和面板用 `--c-card` 实底盖在纸纹上，靠底色差和 2px 边框分层。
- 代码和终端可以用 `--c-chrome` 深底的局部面板；除此之外不把浅色画面切成深色分区。

---

## 4. 形状

- 边框统一 **2px** `--c-border`。1px 的线经 H.264 压缩、在手机上看会断开。
- 圆角：卡片和面板 12px，按钮和分段控件 8px，转场卡片 16px，标签和药丸形 999px，方格 9px（格子 48px）。
- **不用阴影**，不用渐变、玻璃质感或外发光，不用满屏的饱和色块。唯一的满屏色块是方格转场。
- 面板顶部的标题栏用 `--c-surface` 底，下边一条 2px 线，高 56–60px。
- 界面条（导航栏、字幕条）都是 72px 高的 `--c-chrome` 色条，上下对称。

---

## 5. 图标

- 线性图标，16×16 视图框，`fill: currentColor`，粗细统一。
- 图标尺寸是所在行字号的 0.8–0.9 倍，颜色跟随文字，或用真实语义色。
- 不用 emoji、3D 图标、贴纸、彩色图标拼盘；状态图标必须和文字或数字一起出现。

---

## 6. 通用元素的外观

- **卡片 / 面板**：`--c-card` 底，2px 边，12px 圆角，没有阴影；可以带一个标题栏（见第 4 节）。
- **高亮行**：`--c-focus-tint` 浅底，左侧 6px `--c-focus` 竖条，行首的编号变成焦点色。
- **小标签（药丸）**：圆点加文字。指标色三件套是：`positive-tint` 底、`positive-solid` 边、`positive-text` 字。焦点色的小标签是 `focus-tint` 底加 `focus` 字。
- **关键词标记**：在词下方画一条 6px 的 `--c-highlight` 半透明（opacity 0.35）底线，文字颜色不变。
- **步骤时间线**：左侧一条 2px 竖线串起 44px 圆形节点。当前步骤的节点填焦点色，整行浅焦点底；讲完的步骤节点盖一个 `--c-done` 色的对勾。
- **数字滚动**：从 0 滚到目标值，1.2 秒，`power1.out`，带千分位。
- **界面条**：深色条，主文字用 `chrome-ink`，次要文字用 `chrome-muted`，当前项下面有一条 6px 的 `chrome-active` 下划线。

---

## 7. 动效

节奏由运动 token 定：`--motion-enter-duration: 0.2s`、`--motion-easing: power1.out`、`--motion-list-interval: 0.12s`，是克制、轻编辑的节奏。

- 入场：0.2 秒，`power1.out`，向上位移 12–16px 加淡入。只动 opacity 和 transform。
- 文本和信息单元按旁白的句子和语义节拍出现；不要在 scene 开头用统一的 stagger 把所有文字一次铺开。
- 退场：0.2 秒，`power1.in`，淡出。
- 强调只用焦点色切换和下划线擦出，不做弹跳、背景色团、粒子、外发光或无意义的漂浮。
- 转场和字幕的时间写法见各组件文档。
- 所有动画只由时间决定：不用 `repeat: -1`，不用随机数；需要随机的地方用固定种子。

---

## 8. 要做 / 不要做

**要做**
- 所有颜色都走主题变量。
- 每帧只有一种焦点色，加上指标色的数字。
- 讲到的东西总是用焦点色；素材的说明放在素材外面。
- 文字放不下时自动缩小字号，不要溢出，也不要换行。

**不要做**
- 不要加阴影、渐变卡片、玻璃质感、满屏饱和色。
- 不要在纸纹上再叠网格、点阵、方格底纹。
- 不要使用 NotoSansSC / IBMPlexMono 以外的字体。
- 不要把 `--c-muted` 或 `--c-highlight` 用作正文颜色，不要把浅薰衣草底配白字。
- 不要在素材的关键区域上压字幕、标签或标注。

按信息形态的用色见 `patterns/` 各文档的「用色」小节。
