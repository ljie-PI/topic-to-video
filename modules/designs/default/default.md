# 设计主题：default（Frag Note 安静明亮编辑风）

连续暖白画布 + 单一薰衣草强调。深度来自表面色与细分隔线，不靠厚阴影或多色背景。内容 / 论断是最强视觉元素，界面 chrome 必须退后。源自 Frag Note Design System。

这份文档只规定外观，任何类型的视频都能用。字体清单在 `fonts.json`，下载方式见 `designs/designs.md`。

---

## 1. 配色

### 1.1 原则

- 暖白画布 + 单一薰衣草强调：`--c-focus` 表示行动、焦点、选中、当前结论。
- 蓝、绿、琥珀、红只表达真实的 info / success / warning / danger 语义，绝不作为随意装饰。
- 深色 token 只用于代码、终端、媒体局部或遮罩；不把浅色画面切成装饰性的深色分区。
- 一个卡片、callout、chart series 最多一个强 accent；允许「薰衣草表当前焦点 + 一个语义色表真实状态」，两者必须分属不同元素。

### 1.2 主题变量值

变量的含义见 `designs/designs.md`。深色表面（代码 / 终端局部）：`#211F26`（底）/ `#2C2932`（抬升）/ `#37333E`（弱表面），其上文字 `#FAF9F5` / `#B9B4C0`。

| 变量 | 色值 |
|---|---|
| `--c-canvas` | `#FAF9F5` |
| `--c-card` | `#FFFEFB` |
| `--c-surface` | `#F0ECE6` |
| `--c-border` | `#E3DED8` |
| `--c-ink` | `#1F1D24` |
| `--c-ink2` | `#4D4954` |
| `--c-muted` | `#716C79` |
| `--c-focus` | `#6F5BD3` |
| `--c-focus-tint` | `#EEEAFE` |
| `--c-info` | `#3D6FA8` |
| `--c-warning` | `#916019` |
| `--c-danger` | `#AD414A` |
| `--c-positive` | `#397352` |
| `--c-positive-solid` | `#397352` |
| `--c-positive-tint` | `#EAF5ED` |
| `--c-positive-text` | `#2E5C44` |
| `--c-highlight` | `#DED7F7` |
| `--c-done` | `#513EAD` |
| `--c-chrome` | `#211F26` |
| `--c-chrome-ink` | `#FAF9F5` |
| `--c-chrome-muted` | `#B9B4C0` |
| `--c-chrome-active` | `#7965DD` |
| `--c-tile0`–`--c-tile4` | `#F6F3EE` `#E5DEF7` `#CFC4EE` `#B3A3E6` `#6F5BD3`：从暖白到薰衣草的色阶 |
| `--font-sans` | `"NotoSansSC", sans-serif` |
| `--font-mono` | `"IBMPlexMono", "NotoSansSC", monospace` |

### 1.3 变量代码（复制到视频 `index.html` 的 `:root`）

```css
:root {
  --c-canvas: #faf9f5;  --c-card: #fffefb;  --c-surface: #f0ece6;  --c-border: #e3ded8;
  --c-ink: #1f1d24;     --c-ink2: #4d4954;  --c-muted: #716c79;
  --c-focus: #6f5bd3;   --c-focus-tint: #eeeafe;
  --c-info: #3d6fa8;    --c-warning: #916019;  --c-danger: #ad414a;
  --c-positive: #397352;  --c-positive-solid: #397352;  --c-positive-tint: #eaf5ed;  --c-positive-text: #2e5c44;
  --c-highlight: #ded7f7; --c-done: #513ead;
  --c-chrome: #211f26;  --c-chrome-ink: #faf9f5;  --c-chrome-muted: #b9b4c0;  --c-chrome-active: #7965dd;
  --c-tile0: #f6f3ee;   --c-tile1: #e5def7;  --c-tile2: #cfc4ee;  --c-tile3: #b3a3e6;  --c-tile4: #6f5bd3;
  --ground: #faf9f5;
  --font-sans: "NotoSansSC", sans-serif;
  --font-mono: "IBMPlexMono", "NotoSansSC", monospace;
  --motion-enter-duration: 0.2s;
  --motion-easing: power1.out;
  --motion-list-interval: 0.12s;
}
```

字体在 `index.html` 的 `<head>` 里用 `<link rel="stylesheet" href="assets/fonts/rose-pine-default-fonts.css">` 引入（文件名以 `fonts.json` 的 `css_filename` 为准）。

### 1.4 对比度

- `ink` / `canvas` 15.8:1，`body`(#4D4954) / `canvas` 8.3:1，`muted` / `canvas` 4.8:1，`on-primary` / `primary` 5.1:1，`primary-ink`(#49399B) / `primary-soft` 7.6:1。
- 正文、表单和字幕目标至少 4.5:1；大号文字、icon、chart stroke 至少 3:1。
- 状态不能仅用颜色表达；必须有文字、图标或结构辅助。

---

## 2. 字体

- 中文标题、正文、屏幕文字与字幕固定使用 `NotoSansSC`（标题 600，正文 400/500）；禁止宋体、衬线中文 fallback、手写字体。
- `IBMPlexMono` 只用于标识符、日志、路径、代码、数字和紧凑 source metadata，不排整段中文正文。
- 会滚动或需要对齐的数字一律用等宽数字（`font-variant-numeric: tabular-nums`）。
- 正文保持至少 1.55 行高；避免 700+ 的沉重显示字体。

### 2.1 视频尺寸（1920×1080；竖屏按同比例收敛，见 `layouts/portrait.md`）

| 元素 | 1920×1080 | 1080×1440 | 1080×1920 |
|---|---|---|---|
| Hero 标题 | 88–136px | 72–116px | 76–124px |
| Section 标题 | 54–82px | 46–70px | 50–76px |
| 正文 / callout | 30–48px | 28–42px | 28–44px |
| 数据 label / source | 22–32px | 22–30px | 22–32px |
| 代码 / 等宽 | 22–34px | 22–30px | 22–32px |
| 字幕 | 35px | 35px | 35px |

**字号下限**：阅读文字不小于 24px，数据 label / 界面小字不小于 22px，字幕 35px（以所选 layout 的字幕规格为准）。

---

## 3. 背景与质感

- 默认背景是纯暖白 `--ground: #FAF9F5`，连续画布，不换色。
- 层级由表面色（`--c-surface` / `--c-card`）+ `hairline` 细分隔线 + 间距形成；允许的微阴影：`0 1px 2px rgb(31 29 36 / 0.05)`，floating 用 `0 12px 32px rgb(64 52 86 / 0.12), 0 2px 8px rgb(64 52 86 / 0.08)`。
- 图片 / 视频素材默认无可见 card frame、border、padding、shadow 或露底。

## 4. 形状

- 紧凑、平面、安静的编辑式 panel；不用玻璃、厚投影或 glow。
- 圆角：`--c-card` 12px（card、dialog）、8px（button、input、tab）、16px（重要容器）、999px（badge、status chip）。
- 高亮 box 使用 `focus-tint + #49399B` 短文字，或 `card + border`；紧贴短文本，不做大面积紫色填充。

## 5. 图标

- 低调的线性 icon、短 label、细分隔线、节点、箭头与状态 marker；颜色用 `ink2`、`focus` 或真实语义 token。
- 不使用 emoji、3D icon、贴纸、彩色 icon 拼盘、发光 icon；状态 icon 必须和文字 / 数字一起出现。

## 6. 动效

- 运动 token：`--motion-enter-duration: 0.2s`、`--motion-easing: power1.out`、`--motion-list-interval: 0.12s`——克制、轻编辑的节奏。
- 只 animate opacity / transform；不做 bouncy、背景 blob、渐变、粒子、外发光、idle decorative drift。
- 文本与信息单元按旁白句子 / 语义 beat 出现；禁止 scene 开头用统一 stagger 把所有叙事文本铺开。
- 所有动画只由时间决定：不用 `repeat: -1`，不用随机数（需要随机时用固定种子）。

## 7. 不要做

- ❌ 不要用多色 bokeh、mesh background、紫色 gradient、glassmorphism、半透明白卡、outer glow。
- ❌ 不要混用 slate / stone 等额外中性色阶；所有颜色回到本文件 token。
- ❌ 不要把浅紫 `focus-tint` 配白字，不要把 `muted` 用于正文。
- ❌ 不要把状态色用于无关装饰或随机换色；同一元素不叠加多种 accent。
- ❌ 不要为视觉多样性在浅色画面中插入深色 section；深色仅用于真实代码、终端、媒体局部或 overlay。
- ❌ 不要在素材关键区域上压 caption、tag、badge、callout；说明信息放在素材外部。

---

> ## 「待迁 patterns」：按 visual_role 覆盖颜色
>
> 以下段落原来属于 style hint 的「`visual_role` 色彩覆盖」，等 patterns 文档建好后会迁到对应 pattern 的「用色」小节，届时此处删除。
>
> | `visual_role` | 配色方式 |
> |---|---|
> | `title` / `product_card` / `section_divider` | `ink` 标题；可用一个 `focus` 关键词、短 eyebrow 或身份标记。 |
> | `leaderboard` / `big_number` / `data_block` / `metric_strip` | 主数字 `ink` / `focus`；确认或风险数值才用 success / warning / danger；普通 label 用 `ink2` / `muted`。 |
> | `data_table` / `chart` | focal series 用 `focus`；辅助 series 用暖中性色；语义 series 必须表达相应数据语义。 |
> | `timeline` / `process_flow` / `state_machine` | 默认节点与连线用 `border` / `ink2`；当前节点用 `focus` / `focus-tint`；失败 / 等待用真实语义 token。 |
> | `architecture_diagram` / `network_graph` | 中性模块用 `surface` / `border`；关键路径用 `focus`；状态节点才用语义色。 |
> | `comparison_matrix` / `pros_cons` | 中性维度用暖灰；优劣或风险使用 success / danger 等真实语义，不给整列铺满 accent。 |
> | `list` / `feature_grid` | item label 用 `ink` / `ink2`；bullet / index 只在有语义时用 `focus` 或 status color。 |
> | `callout` / `definition` / `qa` / `quote` | `card` 或 `focus-tint` 仅在必要时做短信息区；正文保持 `ink` / `ink2`。 |
> | `code_block` / `terminal_block` / `file_tree` | 局部深色 `#211F26`；命令、路径、版本号用 `IBMPlexMono`；错误用 `danger`。 |
> | `annotated_media` | 标注放在素材外部，pin / marker 可用 `focus` 或真实状态色。 |
