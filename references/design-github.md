# Style Hint — GitHub × 编辑、技术、克制

> `topic-to-video` 的 GitHub 主题预设。这不是 HyperFrames 的实现规范。Phase 8 的 sub-agent 会通过 `hyperframes` skill 和项目自身的 `DESIGN.md` 流程，决定具体的 CSS、布局、动画与渲染。
> 配套的姊妹预设：`references/design-dawn.md`（手绘）、`references/design-moon.md`（深色技术）、`references/design-producthunt.md`（PH 品牌）。

## 配色（只用以下颜色）

**Backgrounds**
- 主画布：`#FFFFFF`（白）
- 次级面板：`#F6F8FA`（hero band / page title 后面的浅灰条）
- Elevated / 悬停：`#E4EBE6`（绿调浅 hover）
- 顶部导航：`#25292E`（近黑）
- 黑色块：`#000000`（footer、深色 hero、terminal 风）

**Text**
- Primary / 标题：`#1F2328`（深近黑）
- Secondary / 次级 / 副标：`#59636E`（中灰）
- Muted / 装饰（**不能**用于正文）：`#8C959F`

**Borders / 分割线**
- 标准 1px：`#D1D9E0`
- 弱：`#EFEFEF`

**Accents —— 每个 scene 选一个**
- Blue `#0969DA` —— 链接、tab underline、repo path hover、信息高亮
- Success / Star green `#1F883D` —— 主 "Star" CTA、成功状态
- Success fg `#08872B` —— "N stars this week" 计数文字
- Success subtle `#EBF9F4` —— Sponsor 按钮淡绿底
- Attention `#BE7D00` —— 警告 / 黄色 callout
- Severe `#B85B06` —— 橙色（sponsor heart hover）
- Danger `#CF2230` —— 删除 / 破坏性操作
- Done purple `#8534F3` —— 已完成 PR
- Done emphasis `#EF2AA4` —— "New" / sponsor 粉
- Teal `#197B7B` —— 讨论 / metadata
- Lime `#92C219` —— JS 语言色点

### 语言色点（列 trending repo 时）

每行 repo 末尾跟一个语言色点（`●`）。用这些标准值；若你只有 GitHub 自己的小调色板，用括号里的替代：

- TypeScript → `#3178C6`（替代：`#0969DA`）
- JavaScript → `#F1E05A`（替代：`#92C219`）
- Python → `#3572A5`
- Rust → `#DEA584`（替代：`#B85B06`）
- Go → `#00ADD8`
- C++ → `#F34B7D`（替代：`#EF2AA4`）
- Java → `#B07219`
- Ruby → `#701516`

## 排版

| 用途 | 字体 | 字重 | 备注 |
|------|------|------|------|
| 显示 / Hero 标题 | `Mona Sans VF`（variable wdth+wght+opsz） | 600 | 全部场景的主字体 |
| 中文标题 / 中文正文 | `Mona Sans VF` 退回系统 CJK | — | Mona Sans 无 CJK 字形，混排走系统 fallback |
| Repo path / 数据 / 命令 | `Mona Sans Mono VF`（variable wght） | 600 | `owner / repo`、星数、代码片段 |
| 备用 marketing 显示 | `Hubot Sans`（variable） | 700-900 | 仅 marketing hero；不要在 repo 卡里出现 |

**绝不要用 Mona Sans 显示长串中文** —— 它没有 CJK 字形。中文要么走 `system-ui / sans-serif` 兜底，要么在工作区追加 `NotoSansSC.woff2`。

**全部数据读数必须** `font-variant-numeric: tabular-nums`，避免动画计数时数字宽度抖动。

## 视频尺寸（覆盖网页常规尺寸）

| 元素 | 1920×1080 | 1080×1440 | 1080×1920 | 字重 |
|------|-----------|-----------|-----------|------|
| Hero 标题（"Trending this week"） | 130-180px | 110-150px | 116-160px | 600 |
| Section 标题 | 64-88px | 54-74px | 58-80px | 600 |
| Repo path `owner / repo`（mono） | 56-72px | 48-62px | 52-66px | 600 |
| Repo 描述 | 38-46px | 32-40px | 34-42px | 400 |
| Meta（lang、stars、forks） | 26-32px | 24-30px | 24-30px | 400 |
| Padding（.scene） | 90px 140px | 90px 80px | 90px 70px | — |

## 形状风格

- 1px 边框，**不要阴影**。GitHub 整体不用 drop shadow。
- 圆角统一 6px（卡片）/ 8px（按钮 pill）。
- 不要把 accent 色做大面积背景；只用作链接、按钮、色点、状态标签。

## 图标

### GitHub mark（`currentColor` 感知）

```html
<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" aria-label="GitHub">
  <path d="M12 1C5.923 1 1 5.923 1 12c0 4.867 3.149 8.979 7.521 10.436.55.096.756-.233.756-.522 0-.262-.013-1.128-.013-2.049-2.764.509-3.479-.674-3.699-1.292-.124-.317-.66-1.292-1.127-1.554-.385-.207-.936-.715-.014-.729.866-.014 1.485.797 1.691 1.128.99 1.663 2.571 1.196 3.204.907.097-.715.385-1.196.701-1.471-2.448-.275-5.005-1.224-5.005-5.432 0-1.196.426-2.186 1.128-2.956-.111-.275-.496-1.402.11-2.915 0 0 .921-.288 3.024 1.128a10.193 10.193 0 0 1 2.75-.371c.936 0 1.871.124 2.75.371 2.103-1.43 3.024-1.128 3.024-1.128.605 1.513.221 2.64.111 2.915.701.77 1.127 1.747 1.127 2.956 0 4.222-2.571 5.157-5.019 5.432.399.344.743 1.004.743 2.035 0 1.471-.014 2.654-.014 3.025 0 .289.206.632.756.522C19.851 20.979 23 16.854 23 12c0-6.077-4.922-11-11-11Z"/>
</svg>
```

### 语言色点

```html
<span class="lang-dot" style="background:#3178C6"></span>
<span>TypeScript</span>

<style>
.lang-dot {
  display: inline-block; width: 14px; height: 14px; border-radius: 50%;
  margin-right: 8px; vertical-align: middle;
}
</style>
```

## 动效

- 入场短促：`power2.out`（默认）、`expo.out`（hero）、duration 0.4-0.7s。
- **Stagger repo cards** 100-140ms，模拟 feed 灌入。
- **Count-up** 星数用 `gsap.to({ value, snap: 'value', duration: 1.2, ease: 'power1.out' })` 驱动 `textContent`。
- **Star pill micro-pulse** —— 卡片落定时，绿色 Star pill scale `1 → 1.06 → 1`，0.25s。
- **Octocat reveal** —— fade + 轻微 scale（`0.9 → 1`），0.4s。**不要旋转**。
- 永远不要 `repeat: -1`（HyperFrames 需要有限确定性 repeat）。

## 不要做

- ❌ 不要用 Roboto、Inter、系统 sans 替代 Mona Sans。Mona Sans 就是 GitHub 的品牌。
- ❌ 不要给 Octocat 染色。白底黑、黑底白，仅此而已。
- ❌ 不要给卡片加 drop shadow。GitHub 用 1px 边框。阴影 = 非 GitHub 感。
- ❌ 不要引入第 5 个 accent 色。在上面捕获的色板里挑。
- ❌ 不要满屏 linear gradient 背景。H.264 banding + GitHub 的平面美学 = off-brand。
- ❌ 不要把深色顶栏当作 hero 背景。顶栏是 chrome，不是 hero。
- ❌ Hero title 字号不要超过 180px。
