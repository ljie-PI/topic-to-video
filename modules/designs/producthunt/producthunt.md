# 设计主题：producthunt（亚麻纸）

粉调亚麻纸配低饱和墨蓝文字与陶土橙焦点色，温暖、有对话感的产品发布看板气质，适合新产品发布、Product Hunt 周榜与 SaaS 类视频。Product Hunt 专属品牌元素（P 字标、猫、Logotype）归模板，不放进本主题。共享变量语义、字号阶梯、纸面与通用元素基线见 [`../designs.md`](../designs.md)，本文只列本主题的专属设定。

背景贴图 `designs/producthunt/textures/paper.jpg`（粉调亚麻纸，1920×1080），使用时复制到视频工程的 `assets/textures/`。主题变量代码见 1.3，字体与字号配置见第 2 节。

---

## 1. 配色

### 1.1 颜色角色

- **焦点（陶土橙）**：正在讲的产品、当前排名、当前步骤、CTA 文字。
- **指标（maker 绿）**：数字、增长、正面结果、maker / 已认证。
- **标记（珊瑚）**：upvote 三角、排名徽章、品牌形状（只做形状，不承载文字）。
- **完成（maker 绿实色）**：讲完的步骤。
- 信息蓝用于注册、链接与流量信息；砖红极少使用，需要时配 `⚠` 或「注意」前缀（限制类信息优先用中性小标签加 `⚠`）。

### 1.2 对比度

- 正文：`ink` 在卡片底上 13.8:1，`ink2` 6.6:1；`focus` 在卡片底上 5.4:1，在 `focus-tint` 上 4.8:1。
- `--c-muted`（约 3.5:1）只用于 34px 以上数字；`--c-highlight`（约 3.6:1）只做形状不承载文字；`--c-chrome-muted` 约 6.3:1；指标标签字用 `--c-positive-text`（在 `positive-tint` 上 6.9:1）。

### 1.3 变量代码（复制到视频 `index.html` 的 `:root`）

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

---

## 2. 字体

- 标题、正文、屏幕文字和字幕都用 `NotoSansSC`，不使用 `NotoSansSC` / `IBMPlexMono` 以外的字体。
- 数字、upvote 数和英文数据用 `IBMPlexMono` 600。
- 字重：正文 400–500，标签和按钮 600，标题、产品名和数字 700。
- **字号下限**：阅读文字不小于 26px，界面小字不小于 22px；字幕字号由各 scene 的 `layout.caption.font_size_px` 决定（阶梯与缩放规则见 [`../designs.md`](../designs.md)）。
- 安装本主题字体后，在 `index.html` 的 `<head>` 引入 `<link rel="stylesheet" href="assets/fonts/producthunt-fonts.css">`（安装与维护见 [`../designs.md`](../designs.md)）：

```json
{
  "min_font_px": {"reading": 26, "ui": 22},
  "fonts": {
    "css_filename": "producthunt-fonts.css",
    "rename": {"Noto Sans SC": "NotoSansSC", "IBM Plex Mono": "IBMPlexMono"},
    "css2_families": ["Noto+Sans+SC:wght@100..900", "IBM+Plex+Mono:wght@400;500;600;700"]
  }
}
```

---

## 3. 背景与质感

- 纸纹按 `designs/github/github.md` 第 3 节的做法生成，换成粉调亚麻色系：底色 `#F4F0EC`，深纤维偏暖褐灰 `#A6988E`，四角压暗约 12 级亮度、暗部偏桃灰 `#C7B2A8`。

---

## 4. 形状、图标与元素

- **圆角（更圆润、不用尖角）**：卡片和面板 16px，缩略图 12px，按钮 10px，转场卡片 20px。
- **图标**：线性图标端点用圆头；upvote 用 `--c-highlight` 实心三角。
- **upvote 药丸**：2px `--c-border` 边的药丸（当前项换成 `--c-highlight` 边），左 `--c-highlight` 实心三角、右 `IBMPlexMono` 600 数字（`--c-ink`）。
- **topic 小标签**：`--c-surface` 底加 `--c-ink2` 字的无色药丸。
- **数字滚动**：从 0 滚到目标值，1.4 秒，`power3.out`，带千分位；落定时微弹（`1 → 1.05 → 1`，0.25 秒）。

---

## 5. 动效

有活力、对话感的节奏（`0.5s` / `power3.out` / 行间隔 `0.2s`）：

- 入场：0.5 秒，`power3.out`，向上位移 20–28px 加淡入；卡片和榜单行按 0.2 秒间隔依次入场，upvote 药丸落定微弹并同步滚数字；开场标题可按词出现（每词间隔 0.08 秒）。
- 退场：0.3 秒，`power2.in`，向上 18px 淡出。
- 允许有限次数的脉冲（如当前推荐卡片边每 4 秒亮一次，共 3 次），不允许无限循环。
