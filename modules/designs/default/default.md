# 设计主题：default（燕麦纸）

暖燕麦棉纸配低饱和墨灰文字与灰薰衣草焦点色；内容和论断最显眼，界面退到后面，适合无特定专题风格的大多数讲解视频。共享变量语义、字号阶梯、纸面与通用元素基线见 [`../designs.md`](../designs.md)，本文只列本主题的专属设定。

背景贴图 `designs/default/textures/paper.jpg`（暖燕麦棉纸，1920×1080），使用时复制到视频工程的 `assets/textures/`。主题变量代码见 1.3，字体与字号配置见第 2 节。

---

## 1. 配色

### 1.1 颜色角色

- **焦点（灰薰衣草）**：正在讲的内容（当前高亮行、步骤、结论、标签）。
- **指标（鼠尾草绿）**：数字、增长、正面结果。
- **标记（赭黄）**：被收藏 / 标记的状态及需要记住的关键词（只做形状、底线和大号短字）。
- **完成（深靛）**：讲完的步骤。

### 1.2 对比度

- 正文：`ink` 在卡片底上 14.9:1，`ink2` 7.1:1；`focus` 在卡片底上 6.2:1，在 `focus-tint` 上 5.4:1。
- `--c-muted`（约 3.6:1）只用于 34px 以上数字；`--c-highlight`（约 3.5:1）不承载正文，避免浅薰衣草底配白字；`--c-chrome-muted` 约 5.8:1；指标标签字用 `--c-positive-text`（在 `positive-tint` 上 7.0:1）。

### 1.3 变量代码（复制到视频 `index.html` 的 `:root`）

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

---

## 2. 字体

- 标题、正文、屏幕文字和字幕都用 `NotoSansSC`；不用宋体、衬线中文、手写体或其他字体家族。
- `IBMPlexMono` 只用于标识符、日志、路径、代码和数字，不排整段中文。
- 字重：正文 400–500（行高至少 1.5），标签和按钮 600，标题和数字 700。
- **字号下限**：阅读文字不小于 26px，界面小字不小于 22px；字幕字号由各 scene 的 `layout.caption.font_size_px` 决定（阶梯与缩放规则见 [`../designs.md`](../designs.md)）。
- 安装本主题字体后，在 `index.html` 的 `<head>` 引入 `<link rel="stylesheet" href="assets/fonts/default-fonts.css">`（安装与维护见 [`../designs.md`](../designs.md)）：

```json
{
  "min_font_px": {"reading": 26, "ui": 22},
  "fonts": {
    "css_filename": "default-fonts.css",
    "rename": {"Noto Sans SC": "NotoSansSC", "IBM Plex Mono": "IBMPlexMono"},
    "css2_families": ["Noto+Sans+SC:wght@100..900", "IBM+Plex+Mono:wght@400;500;600;700"]
  }
}
```

---

## 3. 背景与质感

- 纸纹按 `designs/github/github.md` 第 3 节的做法生成，换成暖燕麦色系：底色 `#F3F1EC`，深纤维偏暖灰 `#A29B91`，四角压暗约 12 级亮度、暗部偏灰薰衣草 `#B4AEC4`。
- 代码和终端可用 `--c-chrome` 深底的局部面板；除此之外不把浅色画面切成深色分区。

---

## 4. 形状、图标与元素

- **圆角**：卡片和面板 12px，按钮和分段控件 8px，转场卡片 16px。
- **图标**：粗细统一；不用 emoji、3D 图标、贴纸或彩色图标拼盘，状态图标须与文字或数字并列。
- **关键词标记**：在词下方画 6px `--c-highlight` 半透明（opacity 0.35）底线，文字颜色不变。
- **数字滚动**：从 0 滚到目标值，1.2 秒，`power1.out`，带千分位。

---

## 5. 动效

克制、轻编辑的节奏（`0.2s` / `power1.out` / 行间隔 `0.12s`）：

- 入场：0.2 秒，`power1.out`，向上位移 12–16px 加淡入，只动 `opacity` 和 `transform`；信息单元按旁白句子与语义时机出现，不在 scene 开头用统一 stagger 一次铺开。
- 退场：0.2 秒，`power1.in`，淡出。
- 强调只用焦点色切换和下划线擦出，不做弹跳、背景色团、粒子、外发光或无意义漂浮。
