# Style Hint — Rosé Pine Dawn × Notion 手绘风

> `topic-to-video` 的可选 mood 与配色提示。这不是 HyperFrames 的实现规范。Phase 8 的子 agent 会通过 `hyperframes` skill 和项目自身的 `DESIGN.md` 流程，决定具体的 CSS、布局、动画与渲染。

## 配色（只用以下颜色）

**Backgrounds**
- 主画布：`#faf4ed`（warm cream）
- 卡片表面：`#fffaf3`（近白的温色）
- Elevated overlay：`#f2e9e1`（柔和的桃米色）

**Text**
- Primary / 标题：`#575279`（柔紫灰）
- Secondary / 正文：`#797593`（淡薰衣草色）
- Subtle / 仅装饰：`#9893a5`（**不能**用于正文 —— 达不到 WCAG 4.5:1）

**Accents —— 每个 scene 选一个**
- Foam `#56949f`（海水青）—— info block、中性 tag
- Love `#b4637a`（柔玫红）—— 暖色强调、warning、"fade" badge
- Iris `#907aa9`（沉紫）—— 次要链接、提示、Loop 主题元素
- Gold `#ea9d34`（琥珀）—— 重点高亮（节制使用，每 scene 最多 1 个元素）
- Rose `#d7827e`（柔珊瑚）—— 温和 callout、"now" 标记
- Pine `#286983`（深青）—— 关键词、冷色对比、"solid" badge

**Borders / 分割线**：`#cecacd`（暖灰）

## 排版

| 用途 | 字体 | 字重 | 备注 |
|------|------|------|------|
| 中文标题 | `MaShanZheng` | 400 | 笔锋感强 |
| 中文正文 | `MaShanZheng` | 400 | 同字体，字号更小 |
| 中文字幕 | `LongCang` | 400 | 草书 |
| 中文装饰强调 | `ZhiMangXing` | 400 | 可选 |
| 英文 / 数字 —— 强调 | `Caveat` | 700 | 手写马克笔感 |
| 英文 / 数字 —— 正文 | `PatrickHand` | 400 | 随意手写体 |

**绝不要用 Caveat 或 PatrickHand 显示中文字符** —— 它们没有 CJK 字形，浏览器会 fallback 成乱码渲染。

混排中文 + 拉丁字符时，HyperFrames 子 agent 应有意识地使用项目字体。本文件只指定希望使用的字体家族，不规定 CSS 实现。

## 视频尺寸（覆盖网页常规尺寸）

| 元素 | 1920×1080 | 1080×1440 | 1080×1920 |
|------|-----------|-----------|-----------|
| Hero 标题 | 100-160px | 80-130px | 90-140px |
| Section 标题 | 60-90px | 50-76px | 56-80px |
| 正文 | 32-56px | 28-46px | 30-48px |
| 数据 label | 22-32px | 22-30px | 22-32px |
| Padding（.scene） | 90px 140px | 90px 80px | 90px 70px |

## 形状基调

- 平面、有质感的卡片和 tag。
- 圆角 label 在服务于信息设计时可以使用。
- 避免厚重阴影；保持手绘氛围轻盈、安静。

## 动效基调

- 每个装饰元素：环境感 breathe / drift / rotate（`sine.inOut yoyo`，有限重复）
- 每次入场：每个 scene 用 3+ 种不同 ease（混用 `expo.out`、`back.out(1.7)`、`power3.out`、`sine.out`）
- 除最终 scene 外，**不要**用 exit 动画
- Scene 转场由 hyperframes 的 track 切换隐式处理
- 标题先入场，辅助元素 stagger 跟进

## 不要做

- ❌ 不要用 shadow、gradient、glow、neon
- ❌ 不要用配色之外的高饱和颜色
- ❌ 不要把 `#9893a5` 用在正文（对比度）
- ❌ 不要用拉丁手写字体显示中文
- ❌ 不要在同一个元素上叠加多种 accent 颜色
- ❌ 不要把 accent 色作为大面积背景填充
