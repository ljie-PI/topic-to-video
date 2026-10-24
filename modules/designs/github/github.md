# 设计主题：github（纸本）

一张冷灰色的棉纸，上面是低饱和的 GitHub 配色：灰、蓝、绿，不加阴影，用 2px 细线和卡片分层。看起来像一张安静、干净的技术页面。

这份文档只规定外观，任何类型的视频都能用。GitHub 专属的内容（Octocat 标志、语言色点、仓库卡片、Star 按钮、贡献图配色等）不在这里，在 `templates/github/github.md`。

背景贴图在 `designs/github/textures/`，用的时候复制到视频工程的 `assets/textures/`。字体不放在仓库里，用 skill 根目录的 `scripts/fonts-download.sh <工程>/assets/fonts github` 下载，得到 Noto Sans（英文和数字）、Noto Sans SC（中文）、Noto Sans Mono（代码、文件名）三种可变字重（100–900）的 WOFF2 和一份 `rose-pine-github-fonts.css`。

| 文件 | 用途 |
|---|---|
| `textures/paper.jpg` | 默认背景：冷灰棉纸，1920×1080 |
| `textures/slate.jpg` | 变体背景：淡灰绿石板 |
| `textures/grain.png` | 变体背景用的静态颗粒，256×256 平铺 |

---

## 1. 配色

### 1.1 颜色只有四种用途

每一帧最多一种焦点色，再加上指标色的数字：

- **焦点（蓝）**：正在讲的东西，包括当前高亮的行、当前步骤、链接、当前标签。
- **指标（绿）**：数字、增长、正面的结果。只用在数字和指标上，不拿来做装饰。
- **标记（黄）**：被收藏、被标记的状态。
- **完成（紫）**：讲完的步骤。

红色只在真正的失败或禁止时出现，目前还没有用到。

### 1.2 主题变量值（默认：纸本 paper）

变量的含义见 `designs/designs.md`。

| 变量 | 色值 |
|---|---|
| `--c-canvas` | `#F2F4F6` |
| `--c-card` | `#FBFCFD` |
| `--c-surface` | `#F3F5F7` |
| `--c-border` | `#D3D9DF` |
| `--c-ink` | `#22272E` |
| `--c-ink2` | `#57606A` |
| `--c-muted` | `#818A94` |
| `--c-focus` | `#2F6AA8` |
| `--c-focus-tint` | `#E6EEF7` |
| `--c-positive` | `#337A4C` |
| `--c-positive-solid` | `#3D8757` |
| `--c-positive-tint` | `#E4F0E8` |
| `--c-positive-text` | `#24563A` |
| `--c-highlight` | `#C9A645` |
| `--c-done` | `#6F5BB5` |
| `--c-chrome` | `#262B31` |
| `--c-chrome-ink` | `#F6F8FA` |
| `--c-chrome-muted` | `#9AA3AD` |
| `--c-chrome-active` | `#E08A73`（柔珊瑚） |
| `--c-tile0`–`--c-tile4` | `#E4E8EC` `#C9D6E3` `#9DB4CC` `#6F92B5` `#2F6AA8`：从纸色到焦点蓝的色阶 |
| `--font-sans` | `"Noto Sans", "Noto Sans SC", sans-serif` |
| `--font-mono` | `"Noto Sans Mono", "Noto Sans SC", monospace` |

### 1.3 对比度

- 正文（26px 及以下）对背景至少 4.5:1；大字、图标、粗线至少 3:1。
- `--c-muted` 在卡片底上只有约 3.4:1，只能用在 34px 以上的数字上。
- 界面条上的次要文字用 `--c-chrome-muted`，约 4.8:1。
- 指标色标签里的文字用 `--c-positive-text`，不要直接用 `--c-positive`。

### 1.4 变体

只换变量值和背景，组件和模板都不用改：

- **slate（淡石板）**：
  - 底色 `#D4DDD7`，背景 `textures/slate.jpg`，上面有粉笔灰和擦掉的字迹；
  - 文字 `ink #1F2A25`，`ink2 #4F5E57`；焦点 `focus #2A6B88`；指标 `positive #2D7646`；
  - 界面条 `chrome #2C3A34`，当前项标记 `chrome-active #F0B56A`；
  - 方格从 `#E3E9E4` 到 `#2A6B88`。
- **aurora（柔光）**：
  - 底色 `#F7F8FA`，背景是四团柔和色晕加 `grain.png` 颗粒（见 1.5）；
  - 颜色保持原饱和度：`focus #0969DA`，`positive #08872B`，`chrome #25292E`，`chrome-active #FD8C73`。

### 1.5 变量代码（复制到视频 `index.html` 的 `:root`）

```css
:root {
  --c-canvas: #f2f4f6;  --c-card: #fbfcfd;  --c-surface: #f3f5f7;  --c-border: #d3d9df;
  --c-ink: #22272e;     --c-ink2: #57606a;  --c-muted: #818a94;
  --c-focus: #2f6aa8;   --c-focus-tint: #e6eef7;
  --c-positive: #337a4c;  --c-positive-solid: #3d8757;  --c-positive-tint: #e4f0e8;  --c-positive-text: #24563a;
  --c-highlight: #c9a645; --c-done: #6f5bb5;
  --c-chrome: #262b31;  --c-chrome-ink: #f6f8fa;  --c-chrome-muted: #9aa3ad;  --c-chrome-active: #e08a73;
  --c-tile0: #e4e8ec;   --c-tile1: #c9d6e3;  --c-tile2: #9db4cc;  --c-tile3: #6f92b5;  --c-tile4: #2f6aa8;
  --ground: url("assets/textures/paper.jpg") 0 0 / 1920px 1080px, #f2f4f6;
  --font-sans: "Noto Sans", "Noto Sans SC", sans-serif;
  --font-mono: "Noto Sans Mono", "Noto Sans SC", monospace;
}
```

字体在 `index.html` 的 `<head>` 里用 `<link rel="stylesheet" href="assets/fonts/rose-pine-github-fonts.css">` 引入，CSS 里的字体名就是上面变量用的 `Noto Sans` / `Noto Sans SC` / `Noto Sans Mono`。

aurora 变体的 `--ground`：

```css
--ground:
  url("assets/textures/grain.png") 0 0 / 256px 256px,
  radial-gradient(1000px 760px at 6% 8%, rgba(176, 216, 255, 0.8), rgba(176, 216, 255, 0) 70%),
  radial-gradient(820px 620px at 82% 0%, rgba(226, 208, 255, 0.6), rgba(226, 208, 255, 0) 70%),
  radial-gradient(1100px 820px at 98% 100%, rgba(173, 238, 196, 0.75), rgba(173, 238, 196, 0) 70%),
  radial-gradient(760px 520px at 30% 112%, rgba(255, 226, 204, 0.45), rgba(255, 226, 204, 0) 70%),
  #f7f8fa;
```

---

## 2. 字体

- 只用 Noto Sans 家族。英文和数字用 Noto Sans，中文回落到 Noto Sans SC，代码和文件名用 Noto Sans Mono。
- 会滚动或需要对齐的数字一律用等宽数字（`font-variant-numeric: tabular-nums`），比如排名、计数、日期、标签。
- 字重：正文 400–500，标签和按钮 600，标题和数字 700–800。

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

**字号下限**：阅读文字不小于 26px，界面小字不小于 22px，字幕 36px。HyperFrames 的检查会把 28px 以下的文字报成警告：阅读文字要按警告处理；界面小字可以忽略这条警告。

---

## 3. 背景与质感

- 默认背景是**冷灰棉纸** `textures/paper.jpg`，铺满整个画面（`--ground`）。上面不要再叠网格、点阵或方格底纹：它们会让画面显得拥挤、像瓷砖，压过内容。
- 纸纹的做法（重新生成或做新色版时照这个来）：
  - 底色 `#F2F4F6`；
  - 低频斑驳：约 300px 尺度，亮度 ±9；
  - 细纸齿：2–6px 尺度，±5；
  - 约 5200 根很淡的短纤维：长 5–40px，不透明度 2.5%–7.5%，深纤维偏冷灰 `#96A0AC`；
  - 约 500 个细小杂点；
  - 四角压暗约 12 级亮度，暗部偏灰蓝；
  - 最后加 ±2.5 的颗粒；
  - 输出 1920×1080 的 JPEG（质量 q2）。

  颗粒同时能防止渐变在 H.264 下出现色带。
- 背景是静态的，不做动画。
- 卡片和面板用 `--c-card` 实底盖在纸纹上，靠底色差和 2px 边框分层。

---

## 4. 形状

- 边框统一 **2px** `--c-border`。1px 的线经 H.264 压缩、在手机上看会断开。
- 圆角：卡片和面板 12px，按钮和分段控件 8px，转场卡片 16px，标签和药丸形 999px，方格 9px（格子 48px）。
- **不用阴影**，不用渐变填充卡片，不用满屏的饱和色块。唯一的满屏色块是方格转场。
- 面板顶部的标题栏用 `--c-surface` 底，下边一条 2px 线，高 56–60px。
- 界面条（导航栏、字幕条）都是 72px 高的 `--c-chrome` 色条，上下对称。

---

## 5. 图标

- 线性图标，16×16 视图框，`fill: currentColor`。风格同 GitHub Octicons，现有模板用的就是 Octicons。
- 图标尺寸是所在行字号的 0.8–0.9 倍，颜色跟随文字。

---

## 6. 通用元素的外观

- **卡片 / 面板**：`--c-card` 底，2px 边，12px 圆角，没有阴影；可以带一个标题栏（见第 4 节）。
- **高亮行**：`--c-focus-tint` 浅底，左侧 6px `--c-focus` 竖条，行首的编号变成焦点色。
- **小标签（药丸）**：圆点加文字。指标色三件套是：`positive-tint` 底、`positive-solid` 边、`positive-text` 字。焦点色的小标签是 `focus-tint` 底加 `focus` 字。
- **步骤时间线**：左侧一条 2px 竖线串起 44px 圆形节点。当前步骤的节点填焦点色，整行浅焦点底；讲完的步骤节点盖一个 `--c-done` 色的对勾。
- **数字滚动**：从 0 滚到目标值，1.4 秒，`power1.out`，带千分位。
- **焦点闪框**：面板内容切换时，边框先变成焦点色，0.6 秒内淡回边框色。
- **界面条**：深色条，主文字用 `chrome-ink`，次要文字用 `chrome-muted`，当前项下面有一条 6px 的 `chrome-active` 下划线。

---

## 7. 动效

- 入场：0.35–0.5 秒，`power2.out`，向上位移 16–24px 加淡入。不做旋转，不做大幅弹跳缩放。
- 列表入场：每行间隔 0.1 秒，像信息流一样逐行出现。
- 文字揭示：从左到右裁切擦出，0.55 秒。
- 退场：0.25–0.3 秒，`power2.in`，向上 18px 淡出，元素之间错开 0.04 秒。
- 强调：
  - 数字弹一下，1 → 1.04 至 1.06 → 1，用时 0.25–0.28 秒；
  - 状态切换的小图标从 0.3 倍弹到 1 倍，`back.out(3)`，0.35 秒。
- 界面条上的当前项标记：0.32 秒，`power3.inOut`，在转场盖住画面时移动。
- 方格转场：从一个点向外扩散，每格 0.12 秒，速度约 6500px/秒。在切点时刻完全盖住画面，切点后约 0.55 秒收回。
- 字幕：入场 0.18 秒（上移 8px 淡入），出场 0.12 秒，同一时间只显示一行。
- 所有动画只由时间决定：不用 `repeat: -1`，不用随机数；需要随机的地方用固定种子。

---

## 8. 要做 / 不要做

**要做**
- 所有颜色都走主题变量。新主题只换变量和背景。
- 每帧只有一种焦点色，加上指标色的数字。
- 面板内容切换时闪一下焦点框，讲到的东西总是用焦点色。
- 文字放不下时自动缩小字号，不要溢出，也不要换行。

**不要做**
- 不要加阴影、渐变卡片、满屏饱和色。
- 不要在纸纹上再叠网格、点阵、方格底纹。
- 不要使用 Noto 家族以外的字体。
- 不要把裸的强调色当作小号正文颜色。
