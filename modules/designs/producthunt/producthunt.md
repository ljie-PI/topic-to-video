# 设计主题：producthunt（亚麻纸）

一张带一点粉调的亚麻纸，上面是低饱和的墨蓝文字和陶土橙。看起来像产品发布日的看板：温暖、有对话感，但颜色收着用。不加阴影，用 2px 细线和圆润的卡片分层。适合新产品发布、Product Hunt 周榜、SaaS 发布这类视频。

这份文档只规定外观，任何类型的视频都能用。Product Hunt 自己的品牌元素（P 字标、猫、Logotype）不在这里，需要时放进模板。

背景贴图在 `designs/producthunt/textures/`，用的时候复制到视频工程的 `assets/textures/`。字体已经放在仓库的 `resources/fonts/producthunt/`，安装方式见 1.4。

| 文件 | 用途 |
|---|---|
| `textures/paper.jpg` | 背景：粉调亚麻纸，1920×1080 |

---

## 1. 配色

### 1.1 颜色只有四种用途

每一帧最多一种焦点色，再加上指标色的数字：

- **焦点（陶土橙）**：正在讲的产品、当前排名、当前步骤、CTA 文字。
- **指标（maker 绿）**：数字、增长、正面的结果、maker / 已认证。只用在数字和指标上，不拿来做装饰。
- **标记（珊瑚）**：upvote 三角、排名徽章、品牌形状。只做形状，不承载文字。
- **完成（maker 绿实色）**：讲完的步骤。

信息蓝用于注册、链接和流量类信息。琥珀只表达真实的 warning。砖红极少使用，需要时配 ⚠ 或「注意」前缀；限制类信息优先用中性小标签加 ⚠。

### 1.2 主题变量值

变量的含义见 `designs/designs.md`。

| 变量 | 色值 |
|---|---|
| `--c-canvas` | `#F4F0EC` |
| `--c-card` | `#FCFAF8` |
| `--c-surface` | `#F2EDE8` |
| `--c-border` | `#DBD3CC` |
| `--c-ink` | `#242A36` |
| `--c-ink2` | `#535B6A` |
| `--c-muted` | `#8A8580` |
| `--c-focus` | `#A84B37` |
| `--c-focus-tint` | `#F7EAE4` |
| `--c-info` | `#3D6793` |
| `--c-warning` | `#94661B` |
| `--c-danger` | `#9E3B3B` |
| `--c-positive` | `#2E7360` |
| `--c-positive-solid` | `#3B836E` |
| `--c-positive-tint` | `#E1EDE8` |
| `--c-positive-text` | `#235747` |
| `--c-highlight` | `#BF6F58` |
| `--c-done` | `#3B836E` |
| `--c-chrome` | `#262B36` |
| `--c-chrome-ink` | `#F7F4F1` |
| `--c-chrome-muted` | `#A8ADB7` |
| `--c-chrome-active` | `#E0957F`（柔珊瑚） |
| `--c-tile0`–`--c-tile4` | `#EAE2DB` `#EFD5CB` `#DDAE9F` `#C47E69` `#A84B37`：从纸色到陶土橙的色阶 |
| `--font-sans` | `"NotoSansSC", sans-serif` |
| `--font-mono` | `"IBMPlexMono", "NotoSansSC", monospace` |

### 1.3 对比度

- 正文：`ink` 在卡片底上 13.8:1，`ink2` 6.6:1；`focus` 在卡片底上 5.4:1，在 `focus-tint` 上 4.8:1。
- `--c-muted` 在卡片底上只有约 3.5:1，只能用在 34px 以上的数字上。
- `--c-highlight` 在卡片底上约 3.6:1，只做形状，不承载文字。
- 界面条上的次要文字用 `--c-chrome-muted`，约 6.3:1。
- 指标色标签里的文字用 `--c-positive-text`（在 `positive-tint` 上 6.9:1），不要直接用 `--c-positive`。

### 1.4 变量代码（复制到视频 `index.html` 的 `:root`）

```css
:root {
  --c-canvas: #f4f0ec;  --c-card: #fcfaf8;  --c-surface: #f2ede8;  --c-border: #dbd3cc;
  --c-ink: #242a36;     --c-ink2: #535b6a;  --c-muted: #8a8580;
  --c-focus: #a84b37;   --c-focus-tint: #f7eae4;
  --c-info: #3d6793;    --c-warning: #94661b;  --c-danger: #9e3b3b;
  --c-positive: #2e7360;  --c-positive-solid: #3b836e;  --c-positive-tint: #e1ede8;  --c-positive-text: #235747;
  --c-highlight: #bf6f58; --c-done: #3b836e;
  --c-chrome: #262b36;  --c-chrome-ink: #f7f4f1;  --c-chrome-muted: #a8adb7;  --c-chrome-active: #e0957f;
  --c-tile0: #eae2db;   --c-tile1: #efd5cb;  --c-tile2: #ddae9f;  --c-tile3: #c47e69;  --c-tile4: #a84b37;
  --ground: url("assets/textures/paper.jpg") center / cover, #f4f0ec;
  --font-sans: "NotoSansSC", sans-serif;
  --font-mono: "IBMPlexMono", "NotoSansSC", monospace;
  --motion-enter-duration: 0.5s;
  --motion-easing: power3.out;
  --motion-list-interval: 0.2s;
}
```

字体已经下载好放在仓库的 `resources/fonts/producthunt/`。安装：`bash scripts/fonts-download.sh <工程>/assets/fonts --theme modules/designs/producthunt`，把 NotoSansSC（中文和正文）、IBMPlexMono（数字、upvote、英文数据）的 WOFF2 和一份 `producthunt-fonts.css` 拷进工程，不联网。在 `index.html` 的 `<head>` 里用 `<link rel="stylesheet" href="assets/fonts/producthunt-fonts.css">` 引入，CSS 里的字体名就是上面变量用的 `NotoSansSC` / `IBMPlexMono`。

---

## 2. 字体

- 标题、正文、屏幕文字和字幕都用 NotoSansSC。
- 数字、upvote 数和英文数据用 IBMPlexMono 600，并且一律用等宽数字（`font-variant-numeric: tabular-nums`）。
- 字重：正文 400–500，标签和按钮 600，标题、产品名和数字 700。

### 2.1 字号阶梯（1920×1080）

| 级别 | 字号 / 字重 | 典型用途 |
|---|---|---|
| 特大数字 | 128–150px / 700–800 | 封面上的核心数字（upvote 总数、排名）、转场卡片上的大标签 |
| 开场标题 | 140px / 700，字距 -0.01em | 开场大标题 |
| 大标题 | 72px / 400 + 700 | 产品名（过长时自动缩小，最小 36px） |
| 标题 | 56–60px / 700 | 页眉行标题、一句话介绍 |
| 小标题 | 44–48px | 标题条里的产品名、转场卡片标题 |
| 强调正文 | 30–36px / 600–700 | tagline、指标说明、字幕（36px / 500） |
| 正文 | 26–28px / 500 | 描述、列表文字、标签页（28px / 600） |
| 界面小字 | 22–26px / 600 | topic 小标签、按钮、面板标题栏 |

竖屏画布（1080×1920、1080×1440）宽只有 1080px：特大数字、开场标题、大标题、标题、小标题按上表取值的 0.85 倍（取整到偶数）；强调正文、正文、界面小字以及下面的两条下限都不变。

**字号下限**：阅读文字不小于 26px，界面小字不小于 22px（只适用于放在 `data-text-role="ui"` 元素里的面板标题栏、按钮、小标签），字幕 36px（以所选 layout 的字幕规格为准）。渲染前检查（check-composition）按这两个下限分别检查。HyperFrames 的检查会把 28px 以下的文字报成警告：阅读文字要按警告处理；界面小字可以忽略这条警告。

---

## 3. 背景与质感

- 背景是**粉调亚麻纸** `textures/paper.jpg`，铺满整个画面（`--ground`）。上面不要再叠网格、点阵或方格底纹。
- 纸纹按 `designs/github/github.md` 第 3 节的做法生成，换成这套颜色：
  - 底色 `#F4F0EC`；
  - 深纤维偏暖褐灰 `#A6988E`；
  - 四角压暗约 12 级亮度，暗部偏桃灰 `#C7B2A8`；
  - 其余参数（低频斑驳、纸齿、纤维和杂点数量、颗粒）与 github 相同。
- 贴图是 1920×1080，用 `center / cover` 铺满：竖屏画布（1080×1920、1080×1440）会把它放大后取中间，不平铺、不出接缝。
- 背景是静态的，不做动画。
- 卡片和面板用 `--c-card` 实底盖在纸纹上，靠底色差和 2px 边框分层。

---

## 4. 形状

- 边框统一 **2px** `--c-border`。1px 的线经 H.264 压缩、在手机上看会断开。
- 圆角比 github 圆润：卡片和面板 16px，缩略图 12px，按钮 10px，标签、upvote 和药丸形 999px，转场卡片 20px，方格 9px（格子 48px）。永远不用尖角。
- **不用阴影**，不用渐变填充卡片，不用满屏的饱和色块。唯一的满屏色块是方格转场。
- 面板顶部的标题栏用 `--c-surface` 底，下边一条 2px 线，高 56–60px。
- 界面条（导航栏、字幕条）都是 72px 高的 `--c-chrome` 色条，上下对称。

---

## 5. 图标

- 线性图标，16×16 视图框，`fill: currentColor`，端点圆头。
- 图标尺寸是所在行字号的 0.8–0.9 倍，颜色跟随文字。
- upvote 用实心三角，填 `--c-highlight`。

---

## 6. 通用元素的外观

- **卡片 / 面板**：`--c-card` 底，2px 边，16px 圆角，没有阴影；可以带一个标题栏（见第 4 节）。
- **高亮行**：`--c-focus-tint` 浅底，左侧 6px `--c-focus` 竖条，行首的排名变成焦点色。
- **upvote 药丸**：2px `--c-border` 边的药丸，左边 `--c-highlight` 实心三角，右边 IBMPlexMono 600 的数字（`--c-ink`）。当前项的药丸边换成 `--c-highlight`。
- **topic 小标签**：`--c-surface` 底加 `--c-ink2` 字的药丸，不带颜色。
- **指标小标签**：`positive-tint` 底、`positive-solid` 边、`positive-text` 字，用于 maker、已认证、增长。
- **步骤时间线**：左侧一条 2px 竖线串起 44px 圆形节点。当前步骤的节点填焦点色，整行浅焦点底；讲完的步骤节点盖一个 `--c-done` 色的对勾。
- **数字滚动**：从 0 滚到目标值，1.4 秒，`power3.out`，带千分位；落定时弹一下（1 → 1.05 → 1，0.25 秒）。
- **界面条**：深色条，主文字用 `chrome-ink`，次要文字用 `chrome-muted`，当前项下面有一条 6px 的 `chrome-active` 下划线。

---

## 7. 动效

节奏由运动 token 定：`--motion-enter-duration: 0.5s`、`--motion-easing: power3.out`、`--motion-list-interval: 0.2s`，是有活力、对话感的节奏。

- 入场：0.5 秒，`power3.out`，向上位移 20–28px 加淡入。
- 卡片和榜单行按 0.2 秒间隔依次入场；upvote 药丸落定时弹一下，数字同时滚动。
- 开场标题可以按词出现，每词间隔 0.08 秒。
- 退场：0.3 秒，`power2.in`，向上 18px 淡出。
- 允许有限次数的脉冲（例如当前推荐卡片的边每 4 秒亮一次，共 3 次）；不允许无限循环。
- 转场和字幕的时间写法见各组件文档。
- 所有动画只由时间决定：不用 `repeat: -1`，不用随机数；需要随机的地方用固定种子。

---

## 8. 要做 / 不要做

**要做**
- 所有颜色都走主题变量。
- 每帧只有一种焦点色，加上指标色的数字。
- 讲到的产品总是用焦点色；upvote 和排名的形状用标记色。
- 文字放不下时自动缩小字号，不要溢出，也不要换行。

**不要做**
- 不要加阴影、渐变卡片、满屏饱和色。
- 不要在纸纹上再叠网格、点阵、方格底纹。
- 不要使用 NotoSansSC / IBMPlexMono 以外的字体。
- 不要把 `--c-highlight` 或 `--c-muted` 用作文字颜色。
- 不要为了“丰富”给没有语义差别的同类元素随机换色。

按信息形态的用色见 `patterns/` 各文档的「用色」小节。
