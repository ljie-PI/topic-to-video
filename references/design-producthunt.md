# Style Hint — Product Hunt × 温暖、产品优先

> `topic-to-video` 的 Product Hunt 主题预设。这不是 HyperFrames 的实现规范。Phase 8 的 sub-agent 会通过 `hyperframes` skill 和项目自身的 `DESIGN.md` 流程，决定具体的 CSS、布局、动画与渲染。
> 配套的姊妹预设：`references/design-dawn.md`（手绘）、`references/design-moon.md`（深色技术）、`references/design-github.md`（GitHub）。

## 配色（只用以下颜色）

**Brand**
- 主橙 / 火焰色：`#FF6154`（**核心识别色** —— logo、upvote、"GET IT" CTA、hover）
- 旧版深橙（仅匹配 pre-2024 资产）：`#DA552F`
- Kitty face 橙红：`#FA5757`
- 次级 CTA 蓝：`#0075FF`（newsletter / 注册流）
- Maker badge 绿：`#00B27F`（"verified" / "maker" 标）

**Backgrounds**
- 主画布：`#FFFFFF`
- 次级 / 段落交替 / hero band：`#F8F9FA`
- Chip / 分段控件 / 搜索条：`#EAECF0`

**Text**
- Primary / 标题 / 产品名：`#21293C`
- Secondary / 正文 / tagline / meta：`#4B587C`
- Tertiary / 时间戳 / "Promoted" 标：`#988F8C`
- 高对比（白 logo 里的 "P"）：`#000000`

**Borders / 分割线**
- 卡片 1px：`#E5E7EB`

**Topic chip accents（可选）**
- AI / SaaS → 底 `#F4F2EE`、文字 `#21293C`
- Productivity → 底 `#EEF7FF`、文字 `#0075FF`
- Design → 底 `#FFF1ED`、文字 `#FF6154`

## 排版

PH 几乎全部使用 **Inter**；logotype 用自定义圆滑显示字体，但 Inter 800 + 紧排（`letter-spacing: -0.02em`）是社区通用替代。

| 用途 | 字体 | 字重 | 备注 |
|------|------|------|------|
| UI / 产品名 / tagline / meta / nav | `Inter`（variable 优先） | 400/500/600/700 | 通用 |
| Section 大标题（"Top Products Launching Today"） | `Inter` 800 + tight tracking | 800 | 紧排 -0.02em |
| Logotype 替身 | `Inter 800` 或 `Helvetica Bold` | — | "Product" semibold + "Hunt" bold |

中文混排走系统 CJK fallback；正文里中文较多时，工作区追加 `NotoSansSC.woff2`。

## 视频尺寸（覆盖网页常规尺寸）

| 元素 | 1920×1080 | 1080×1440 | 1080×1920 | 字重 |
|------|-----------|-----------|-----------|------|
| Hero（"Top Products Launching Today"） | 120-160px | 100-138px | 108-148px | 800 |
| 产品名 | 56-72px | 48-62px | 52-66px | 700 |
| Tagline（产品名下一行） | 32-40px | 28-36px | 30-38px | 400 |
| Topic chip | 22-26px | 22-26px | 22-26px | 500 |
| Upvote 数（tabular-nums） | 48-64px | 42-56px | 46-60px | 700 |
| Section eyebrow（uppercase） | 22-26px | 22-26px | 22-26px | 600 |
| Padding（.scene） | 90px 140px | 90px 80px | 90px 70px | — |

## 形状风格

- 圆角统一：卡片 12-16px、缩略图 8-12px。**永远不用尖角**。
- 不要厚阴影。最多 `0 2px 8px rgba(0,0,0,.04)` 的 hover 微抬。
- 橙色用于 mark、upvote、CTA 按钮 —— **不要做大面积背景**。画布保持白。

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
  background: #FFFFFF; border: 2px solid #FF6154; color: #FF6154;
  font-family: "Inter", sans-serif; font-weight: 700;
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
- 永远不要 `repeat: -1`（HyperFrames 需要有限确定性 repeat）。

## 不要做

- ❌ 不要用红色替代 `#FF6154`。PH 的橙是 warm-coral，不是消防红。
- ❌ 不要把 kitty 放进 P disc 里面。disc 只是字母 P；猫是单独的 marketing 资产。
- ❌ 不要用 Helvetica / Arial 替代 Inter（仅 preview 可临时 fallback）。
- ❌ Logotype 不要小写或斜体。永远是 "Product Hunt"，两个首字母大写的单词。
- ❌ 不要把橙做大面积背景。canvas 保持白；橙只用在 mark、upvote、CTA pill 上。
- ❌ 不要用厚 drop shadow。PH 用 1px 边框 + 最多极淡 hover lift。
- ❌ Hero 字号不要超过 160px。
