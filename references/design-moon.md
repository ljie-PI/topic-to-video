# Style Hint — Rosé Pine Moon × 严肃技术编辑风

> `topic-to-video` 的可选深色 mood 与配色提示。这不是 HyperFrames 的实现规范。Phase 8 的 sub-agent 会通过 `hyperframes` skill 和项目自身的 `DESIGN.md` 流程，决定具体的 CSS、布局、动画与渲染。
> 配套的手绘参考是 `references/design-dawn.md`。

## 配色（只用以下颜色）

**Backgrounds**
- 主画布：`#232136`（Moon base）
- 卡片表面：`#2a273f`（Moon surface）
- Elevated overlay：`#393552`（Moon overlay）

**Text**
- Primary / 标题：`#e0def4`（Moon text）
- Secondary / 正文：`#908caa`（Moon subtle；在 base 上对中 / 大号字安全）
- 仅装饰用 muted：`#6e6a86`（Moon muted；不要用于正文）

**Accents —— 每个 scene 选一个**
- Iris `#c4a7e7` —— 主要技术高亮、label、强调
- Foam `#9ccfd8` —— 中性数据 callout、对比标记
- Gold `#f6c177` —— 每个 scene 一个重要数字或 warning
- Love `#eb6f92` —— 风险、失败、紧张、紧急 callout
- Rose `#ea9a97` —— 人情味 / 柔对比、罕用的 CTA
- Pine `#3e8fb0` —— 深蓝辅助 accent；仅用于大字或形状

**Borders / 分割线**
- 标准线：`#56526e`
- 弱分割线：`#44415a`
- 低高光 / inset：`#2a283e`

## 排版

| 用途 | 字体 | 字重 | 备注 |
|------|------|------|------|
| 中文标题 | `NotoSansSC` | 700 | 用于主论断 |
| 中文 section 标题 | `NotoSansSC` | 600 | 当 700 显得过重时 |
| 中文正文 | `NotoSansSC` | 400 | 清晰、现代，比 Dawn 不那么俏皮 |
| 中文字幕 | `NotoSansSC` | 500 | 略加重以适应视频可读性 |
| 英文 / 数据 / 代码 | `IBMPlexMono` | 400 | 技术 label、文件名、模型名 |
| 英文 / 数字强调 | `IBMPlexMono` | 600 | 数字、版本号、命令片段 |

**Moon 风格中不要使用 Dawn 的手写字体**，除非用户明确要求"手绘对比"。Moon 应当克制、技术、编辑感强。

主 agent 通过 `scripts/fonts-download.sh` 预置 Moon 字体。HyperFrames sub-agent 决定如何加载和应用这些本地字体资源。

## 视频尺寸

| 元素 | 1920×1080 | 1080×1440 | 1080×1920 |
|------|-----------|-----------|-----------|
| Hero 标题 | 88-136px | 72-116px | 76-124px |
| Section 标题 | 54-82px | 46-70px | 50-76px |
| 正文 | 30-48px | 28-42px | 28-44px |
| 数据 label | 22-32px | 22-30px | 22-32px |
| 代码 / 等宽 | 22-34px | 22-30px | 22-32px |
| Padding（.scene） | 90px 140px | 90px 80px | 90px 70px |

## 形状风格

- 紧凑的平面 panel 和严肃的编辑式 data block。
- 高亮应表现为线、tag 或小标记，而不是大面积的亮色填充。
- 避免厚重阴影和俏皮装饰。

## 动效

- 入场应当克制：`power3.out`、`expo.out`、`sine.out`。
- 位移幅度比 Dawn 小：`y: 20-44`、`x: 20-40`、`scale: 0.96-1`。
- 除非内容需要罕见的强调瞬间，否则避免 bouncy 的 `back.out(1.7)`。
- 环境装饰要克制：网格、细线、小轨道标记、终端式 cursor 或图谱节点。

## 不要做

- ❌ 不要替换 Dawn 的手绘默认风格；Moon 是可选项。
- ❌ 不要在 Moon 中使用 `MaShanZheng`、`LongCang`、`Caveat` 或 `PatrickHand`，除非用户明确要求手绘混搭对比。
- ❌ 不要把 `#6e6a86` 用作正文。
- ❌ 不要在深色背景上使用满屏 linear gradient。
- ❌ 同一个 scene 的主内容里不要叠加超过一种 accent 色。
- ❌ 不要把 accent 色做大面积背景；只用作线、tag、数字或小符号。
