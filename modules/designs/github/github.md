# 设计主题：github（纸本）

冷灰棉纸配低饱和 GitHub 灰、蓝、绿，安静干净的技术页面感。GitHub 专属品牌元素（Octocat 标志、语言色点、仓库卡片、Star 按钮、贡献图配色等）归模板，不放进本主题。共享变量语义、字号阶梯、纸面与通用元素基线见 [`../designs.md`](../designs.md)，本文只列本主题的专属设定。

背景贴图在 `designs/github/textures/`（默认冷灰棉纸 `paper.jpg`，变体淡灰绿石板 `slate.jpg`，均 1920×1080），使用时复制到视频工程的 `assets/textures/`。主题变量代码见 1.4，字体与字号配置见第 2 节。

---

## 1. 配色

### 1.1 颜色角色

- **焦点（蓝）**：正在讲的内容（高亮行、当前步骤、链接、当前标签）。
- **指标（绿）**：数字、增长、正面结果。
- **标记（黄）**：被收藏、被标记的状态。
- **完成（紫）**：讲完的步骤。

### 1.2 对比度

- 正文（26px 及以下）对背景至少 4.5:1；大字、图标、粗线至少 3:1。
- `--c-muted`（约 3.4:1）只用于 34px 以上数字；`--c-warning`（纸上 4.6:1，卡片上 4.9:1）可承载正文；`--c-highlight`（约 3.1:1）只做形状、图标和大号短字，不承载正文；`--c-chrome-muted` 约 4.8:1。

### 1.3 变体

- **slate（淡石板）**：底色 `#D4DDD7`，背景 `textures/slate.jpg`（带粉笔灰与擦痕）；`ink #1F2A25`、`ink2 #4F5E57`、`focus #2A6B88`、`positive #2D7646`、`chrome #2C3A34`、`chrome-active #F0B56A`，方格从 `#E3E9E4` 到 `#2A6B88`。

### 1.4 变量代码（复制到视频 `index.html` 的 `:root`）

```css
:root {
  --c-canvas: #f2f4f6;  --c-card: #fbfcfd;  --c-surface: #f3f5f7;  --c-border: #d3d9df;
  --c-ink: #22272e;     --c-ink2: #57606a;  --c-muted: #818a94;
  --c-focus: #2f6aa8;   --c-focus-tint: #e6eef7;
  --c-info: #0969da;    --c-warning: #986400;  --c-danger: #cf2230;
  --c-positive: #337a4c;  --c-positive-solid: #3d8757;  --c-positive-tint: #e4f0e8;  --c-positive-text: #24563a;
  --c-highlight: #a88831; --c-done: #6f5bb5;
  --c-chrome: #262b31;  --c-chrome-ink: #f6f8fa;  --c-chrome-muted: #9aa3ad;  --c-chrome-active: #e08a73;
  --c-tile0: #e4e8ec;   --c-tile1: #c9d6e3;  --c-tile2: #9db4cc;  --c-tile3: #6f92b5;  --c-tile4: #2f6aa8;
  --ground: url("assets/textures/paper.jpg") center / cover, #f2f4f6;
  --font-sans: "Noto Sans", "Noto Sans SC", sans-serif;
  --font-mono: "Noto Sans Mono", "Noto Sans SC", monospace;
  --motion-enter-duration: 0.45s;
  --motion-easing: power2.out;
  --motion-list-interval: 0.1s;
}
```

---

## 2. 字体

- 只用 Noto Sans 家族：英文和数字用 `Noto Sans`，中文回落到 `Noto Sans SC`，代码和文件名用 `Noto Sans Mono`。
- 字重：正文 400–500，标签和按钮 600，标题和数字 700–800。
- **字号下限**：阅读文字不小于 26px，界面小字不小于 22px；字幕字号由各 scene 的 `layout.caption.font_size_px` 决定（阶梯与缩放规则见 [`../designs.md`](../designs.md)）。
- 安装本主题字体后，在 `index.html` 的 `<head>` 引入 `<link rel="stylesheet" href="assets/fonts/github-fonts.css">`（安装与维护见 [`../designs.md`](../designs.md)）：

```json
{
  "min_font_px": {"reading": 26, "ui": 22},
  "fonts": {
    "css_filename": "github-fonts.css",
    "rename": {},
    "css2_families": [
      "Noto+Sans:wdth,wght@62.5..100,100..900",
      "Noto+Sans+SC:wght@100..900",
      "Noto+Sans+Mono:wdth,wght@62.5..100,100..900"
    ]
  }
}
```

---

## 3. 背景与质感

冷灰棉纸 `textures/paper.jpg` 的生成参数也是其他纸感主题重新生成色版时的基准：

- 底色 `#F2F4F6`；低频斑驳约 300px 尺度、亮度 ±9；细纸齿 2–6px 尺度、±5；
- 约 5200 根淡短纤维（长 5–40px，不透明度 2.5%–7.5%，深纤维偏冷灰 `#96A0AC`）与约 500 个细杂点；
- 四角压暗约 12 级亮度，暗部偏灰蓝；最后叠加 ±2.5 颗粒（兼防 H.264 色带），输出 1920×1080 JPEG（q2）。

---

## 4. 形状、图标与元素

- **圆角**：卡片和面板 12px，按钮和分段控件 8px，转场卡片 16px。
- **图标**：风格对齐 GitHub Octicons。
- **焦点闪框**：面板内容切换时，边框先变 `--c-focus`，0.6 秒内淡回 `--c-border`。
- **数字滚动**：从 0 滚到目标值，1.4 秒，`power1.out`，带千分位。

---

## 5. 动效

干脆的技术信息流节奏（`0.45s` / `power2.out` / 行间隔 `0.1s`）：

- 入场：0.35–0.5 秒（token 取 0.45s），`power2.out`，向上位移 16–24px 加淡入，不做旋转或大幅弹跳缩放；列表按 0.1 秒逐行出现；文字揭示可从左到右裁切擦出（0.55 秒）。
- 退场：0.25–0.3 秒，`power2.in`，向上 18px 淡出，元素错开 0.04 秒。
- 强调：数字微弹 `1 → 1.04–1.06 → 1`（0.25–0.28 秒）；状态小图标从 0.3 倍弹到 1 倍（`back.out(3)`，0.35 秒）；界面条当前项标记在转场盖住画面时以 0.32 秒 `power3.inOut` 移动。
