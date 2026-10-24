# 设计主题：moon（Rosé Pine Moon × 严肃技术编辑风）

深色、克制、编辑感。深紫底上是 Rosé Pine Moon 的浅紫白文字和 flat / line-based 的技术 accent。Moon 不是手绘风：保持技术 label、终端 cursor、细线轨道、小节点和状态 tag。

这份文档只规定外观，任何类型的视频都能用。字体清单在 `fonts.json`，下载方式见 `designs/designs.md`。

---

## 1. 配色

### 1.1 原则

- 按信息语义使用 accent；允许同一画面出现多个语义色；禁止随机换色；禁止同一元素叠加多种 accent。
- Iris `#c4a7e7` 是主技术强调色（label、definition、active state、关键路径）。
- success 用 Pine `#3e8fb0`，info 用 Foam `#9ccfd8`，二者不可互换；同一画面需区分时加 ✓ / label 辅助，不只靠颜色。
- Pine 不承载小号正文；小号可读 accent text 改用 Iris / Foam / Rose。
- 环境装饰只能是 flat / line-based：网格、细线、小轨道标记、终端式 cursor；禁止 glow、radial spotlight、ambient orb、neon halo。

### 1.2 主题变量值

变量的含义见 `designs/designs.md`。额外的层级色：弱分割线 `#44415a`，低高光 / inset `#2a283e`。

| 变量 | 色值 |
|---|---|
| `--c-canvas` | `#232136` |
| `--c-card` | `#2a273f` |
| `--c-surface` | `#393552` |
| `--c-border` | `#56526e` |
| `--c-ink` | `#e0def4` |
| `--c-ink2` | `#908caa` |
| `--c-muted` | `#6e6a86` |
| `--c-focus` | `#c4a7e7`（Iris） |
| `--c-focus-tint` | `#393552` |
| `--c-info` | `#9ccfd8`（Foam） |
| `--c-warning` | `#f6c177`（Gold） |
| `--c-danger` | `#eb6f92`（Love） |
| `--c-positive` | `#3e8fb0`（Pine） |
| `--c-positive-solid` | `#3e8fb0` |
| `--c-positive-tint` | `#393552` |
| `--c-positive-text` | `#3e8fb0` |
| `--c-highlight` | `#ea9a97`（Rose） |
| `--c-done` | `#c4a7e7`（Iris，同 focus 的完成态语义） |
| `--c-chrome` | `#2a273f` |
| `--c-chrome-ink` | `#e0def4` |
| `--c-chrome-muted` | `#908caa` |
| `--c-chrome-active` | `#f6c177`（Gold） |
| `--c-tile0`–`--c-tile4` | `#6e6a86` `#56526e` `#6e5d96` `#967fc0` `#c4a7e7`：从 muted 到 Iris 的色阶 |
| `--font-sans` | `"NotoSansSC", sans-serif` |
| `--font-mono` | `"IBMPlexMono", "NotoSansSC", monospace` |

### 1.3 变量代码（复制到视频 `index.html` 的 `:root`）

```css
:root {
  --c-canvas: #232136;  --c-card: #2a273f;  --c-surface: #393552;  --c-border: #56526e;
  --c-ink: #e0def4;     --c-ink2: #908caa;  --c-muted: #6e6a86;
  --c-focus: #c4a7e7;   --c-focus-tint: #393552;
  --c-info: #9ccfd8;    --c-warning: #f6c177;  --c-danger: #eb6f92;
  --c-positive: #3e8fb0;  --c-positive-solid: #3e8fb0;  --c-positive-tint: #393552;  --c-positive-text: #3e8fb0;
  --c-highlight: #ea9a97; --c-done: #c4a7e7;
  --c-chrome: #2a273f;  --c-chrome-ink: #e0def4;  --c-chrome-muted: #908caa;  --c-chrome-active: #f6c177;
  --c-tile0: #6e6a86;   --c-tile1: #56526e;  --c-tile2: #6e5d96;  --c-tile3: #967fc0;  --c-tile4: #c4a7e7;
  --ground: #232136;
  --font-sans: "NotoSansSC", sans-serif;
  --font-mono: "IBMPlexMono", "NotoSansSC", monospace;
  --motion-enter-duration: 0.4s;
  --motion-easing: power3.out;
  --motion-list-interval: 0.1s;
}
```

字体在 `index.html` 的 `<head>` 里用 `<link rel="stylesheet" href="assets/fonts/rose-pine-moon-fonts.css">` 引入（文件名以 `fonts.json` 的 `css_filename` 为准）。

### 1.4 对比度

- `#e0def4` 可在 base / surface / overlay 上承载正文（对 `#232136` 约 12.9:1）。
- `#908caa` 只在主画布 `#232136` 上承载正文；在 `#2a273f` / `#393552` 上只用于大号辅助、metadata 或 source。
- `#6e6a86` 永远只做装饰 chrome，不承载信息。
- 正文至少 4.5:1；大号文字、icon、chart stroke、粗线 marker 至少 3:1。

---

## 2. 字体与字号

- 中文标题 `NotoSansSC` 700（主论断），section 标题 600；正文 400；字幕 500（略加重以适应视频可读性）。
- 英文 / 数据 / 代码用 `IBMPlexMono`：技术 label、文件名、模型名 400，数字、版本号、命令片段 600。
- 会滚动或需要对齐的数字一律用等宽数字（`font-variant-numeric: tabular-nums`）。

### 2.1 视频尺寸（1920×1080；竖屏按同比例收敛，见 `layouts/portrait.md`）

| 元素 | 1920×1080 | 1080×1440 | 1080×1920 |
|---|---|---|---|
| Hero 标题 | 88–136px | 72–116px | 76–124px |
| Section 标题 | 54–82px | 46–70px | 50–76px |
| 正文 | 30–48px | 28–42px | 28–44px |
| 数据 label | 22–32px | 22–30px | 22–32px |
| 代码 / 等宽 | 22–34px | 22–30px | 22–32px |
| 字幕 | 35px | 35px | 35px |

**字号下限**：阅读文字不小于 24px，数据 label / 代码不小于 22px，字幕 35px（以所选 layout 的字幕规格为准）。深色背景会让字体看起来更粗：正文保持 400/500，700 只用于标题。

---

## 3. 背景与质感

- 默认背景是纯 `--c-canvas` 深紫 `#232136`，允许极淡网格 / 细线 / 低对比结构（`#44415a`）。
- 禁止满屏 linear gradient、radial spotlight、localized glow、发光阴影。
- 图片 / 视频素材默认无可见卡片框、无 border、无 padding、无 shadow、无 glow。

## 4. 形状

- 紧凑的平面 panel 和严肃的编辑式 data block；高亮表现为线、tag 或小标记，不做大面积亮色填充。

## 5. 图标

- 等宽 label、节点、cursor、线性箭头、状态点或 terminal-style marker；保持低调、平面、线性。

## 6. 动效

- 运动 token：`--motion-enter-duration: 0.4s`、`--motion-easing: power3.out`、`--motion-list-interval: 0.1s`——克制的技术节奏。
- 位移幅度比 dawn 小（`y: 20–44`、`x: 20–40`、`scale: 0.96–1`）；避免 bouncy 的 `back.out(1.7)`，仅罕见强调瞬间可用。
- 所有动画只由时间决定：不用 `repeat: -1`，不用随机数（需要随机时用固定种子）。

## 7. 不要做

- ❌ 不要使用 Dawn 的手写字体（`MaShanZheng`、`LongCang`、`Caveat`、`PatrickHand`），除非用户明确要求手绘混搭对比。
- ❌ 不要把 `#6e6a86` 用作正文；不要在深色背景上使用满屏 gradient 或发光装饰。
- ❌ 不要给素材加可见边框、卡片底、shadow、glow；不要把标注压在素材之上。
- ❌ 不要在同一个元素上叠加多种 accent 色；不要把 accent 色做大面积背景。

---

> ## 「待迁 patterns」：按 visual_role 覆盖颜色
>
> 以下段落原来属于 style hint 的「`visual_role` 色彩覆盖」，等 patterns 文档建好后会迁到对应 pattern 的「用色」小节，届时此处删除。
>
> | `visual_role` | 配色方式 |
> |---|---|
> | `title` / `product_card` / `section_divider` | Primary 标题 + Iris / Foam eyebrow；产品或项目身份的关键数字可用 Gold。 |
> | `leaderboard` / `big_number` / `data_block` / `metric_strip` | 数字用 Gold / Foam；rank marker 用 Iris；风险数值用 Love；普通 label 用 Secondary。 |
> | `data_table` / `chart` | 表格正文 Secondary；highlight cell 用 Gold 描边；chart 主线 Foam，secondary series Iris / Rose，danger series Love。 |
> | `timeline` / `process_flow` / `state_machine` | 节点正文 Primary / Secondary；当前节点 Gold；active tech 节点 Iris；失败状态 Love；连接线 Foam。 |
> | `architecture_diagram` / `network_graph` | 模块边线 Foam / Iris；关键路径 Iris；背景结构线 `#44415a`；Pine 仅作大形状或粗线。 |
> | `comparison_matrix` / `pros_cons` | 正向 / stable 用 Pine，风险 / cons 用 Love，中性维度用 Secondary；info 维度才用 Foam；不给整列大面积 accent 底。 |
> | `list` / `feature_grid` | item label Primary；bullet / index 按语义用 Iris / Foam / Gold / Love；detail 用 Secondary。 |
> | `callout` / `definition` / `qa` | callout 用 Surface 底 + 语义色左线；definition 用 Iris；QA 的 Q 用 Foam、A 用 Primary。 |
> | `code_block` / `terminal_block` / `file_tree` | panel 底 Surface；命令 / path 用 Iris；输出值用 Foam / Gold；error / fail 用 Love。 |
> | `annotated_media` | 标注在素材外部；pin 用 Gold / Foam；解释文字 Primary / Secondary。 |
> | `quote` | 引号 / source marker 用 Rose；quote 正文 Primary；source 用 Secondary。 |
