# 设计主题

设计主题规定全片或场景的外观基线：配色、字体、字号、背景、形状、图标风格与动效节奏。

## 选择与落盘契约（`composition/design.json`）

- **在 Phase 8 根据内容选择，默认从库内注册 preset 中选择**：composition agent 读完旁白、叙事规划、素材与 `composition_requests` 后，默认从下表选择与全片内容气质最匹配的注册 preset（无特定专题匹配时选通用的 `default`）。用户在 `composition_requests` 点名注册主题时按作用范围采用（限定到单个 scene 时，全片仍按内容选基线 preset，只在该 scene 根作用域覆盖相应 token 并在 storyboard 记录，不自动传播到其他 scene）；仅当用户在 `composition_requests` 中明确要求库内 preset 无法覆盖的库外视觉风格时，才生成 `custom` design。
- **落盘 `composition/design.json`**：根字段恰好为 `version: 1` / `source` / `preset` / `tokens` / `min_font_px`。`source: "preset"` 时记录注册名，`tokens` 与 `min_font_px` 必须与所选 `<主题>.md` 中的声明完全一致；`source: "custom"` 时 `preset` 为 `null`，仍须写完整共享 tokens 与正整数 `reading` / `ui` 下限（`ui` 不低于 22px）。`fonts` 维护清单不写入该产物。

### 现有主题

| 主题 | 文档 | 气质与适用内容 |
|---|---|---|
| default | `designs/default/default.md` | 暖燕麦棉纸 + 低饱和墨灰与灰薰衣草；内容优先、界面退后的安静编辑风，无特定专题时的通用默认 |
| github | `designs/github/github.md` | 冷灰棉纸 + 低饱和 GitHub 灰、蓝、绿；技术解读、开源仓库与工程页面感 |
| producthunt | `designs/producthunt/producthunt.md` | 粉调亚麻纸 + 低饱和墨蓝、陶土橙与 maker 绿；新产品发布、SaaS 与周榜的温暖对话感 |

三个注册主题共用同一套纸感基底（静态 `textures/paper.jpg`、低饱和配色、无阴影、2px 细线分层与相同字号下限），区别在纸色、焦点色、圆角与动效节奏。组件和模板不认识具体颜色和字体，只读下面这套**主题变量**。

## 主题变量约定

### 颜色

| 变量 | 用途 |
|---|---|
| `--c-canvas` | 画布底色（背景贴图下面的底） |
| `--c-card` | 卡片、面板的底 |
| `--c-surface` | 面板标题栏、按钮、分段控件的底 |
| `--c-border` | 边框和分隔线 |
| `--c-ink` | 主文字 |
| `--c-ink2` | 次要文字 |
| `--c-muted` | 只用于大号的弱化数字（34px 以上）或装饰，不承载正文 |
| `--c-focus` | 焦点色：正在讲的东西、链接、当前项 |
| `--c-focus-tint` | 焦点色的浅底：高亮行、小标签 |
| `--c-info` | 信息语义：提示、进行中、中性数据标记 |
| `--c-warning` | 警示语义：延迟、部分完成、风险 |
| `--c-danger` | 危险语义：失败、禁止、破坏性状态 |
| `--c-positive` | 指标和增长的数字 |
| `--c-positive-solid` | 指标色标签的边和圆点 |
| `--c-positive-tint` | 指标色标签的底 |
| `--c-positive-text` | 指标色标签里的文字 |
| `--c-highlight` | 被标记、被收藏的状态（如实心星） |
| `--c-done` | 已完成（如步骤对勾） |
| `--c-chrome` | 界面条：顶部导航栏、底部字幕条 |
| `--c-chrome-ink` | 界面条上的主文字 |
| `--c-chrome-muted` | 界面条上的次要文字 |
| `--c-chrome-active` | 界面条上的当前项标记（如标签下划线） |
| `--c-tile0` … `--c-tile4` | 方格转场的五档颜色，从最浅到最深 |
| `--ground` | 整个画面的背景（贴图、渐变加底色） |

用色原则：每一帧最多一种焦点色加指标色数字；语义色（`--c-info` / `--c-warning` / `--c-danger`）只表达真实信息语义，不做装饰，同一元素不叠加多种语义色；不为了“丰富”给无语义差别的同类元素随机换色。

### 字体

| 变量 | 用途 |
|---|---|
| `--font-sans` | 正文字体栈 |
| `--font-mono` | 代码、文件名用的等宽字体栈 |

### 运动

| 变量 | 用途 |
|---|---|
| `--motion-enter-duration` | 元素入场时长（秒），如 `0.45s` |
| `--motion-easing` | 入场缓动（GSAP 风格 ease 名），如 `power2.out` |
| `--motion-list-interval` | 列表逐行入场的行间隔（秒），如 `0.1s` |

这三个变量给组件和模板的默认动效定节奏；个别强调动效见各主题文档。所有动画只由时间决定：不用 `repeat: -1`，不用随机数；需要随机的地方用固定种子。

## 共享排版、形状与通用元素基线

各注册主题默认继承以下基线，`<主题>.md` 只记录本主题的专属设定与差异：

### 字号阶梯（1920×1080）与字号下限

| 级别 | 字号 / 字重 | 典型用途 |
|---|---|---|
| 特大数字 | 128–150px / 700–800 | 封面核心数字、转场卡片大标签 |
| 开场标题 | 140px / 700，字距 -0.01em | 开场大标题 |
| 大标题 | 72px / 400 + 700 | 封面主名称 / 产品名（过长时自动缩小，最小 36px） |
| 标题 | 56–60px / 700 | 页眉行标题、一句话介绍 |
| 小标题 | 44–48px | 标题条名称、转场卡片标题 |
| 强调正文 | 30–36px / 600–700 | 步骤标题、tagline、指标说明 |
| 正文 | 26–28px / 500 | 描述、列表文字、标签页（28px / 600） |
| 界面小字 | 22–26px / 600 | 面板标题栏、按钮、小标签（须加 `data-text-role="ui"`） |

- **竖屏缩放**：竖屏画布（1080×1920、1080×1440）宽 1080px，特大数字、开场标题、大标题、标题、小标题五档按上表 `× 0.85`（取整到偶数）；强调正文、正文、界面小字及字号下限不变。
- **数字对齐**：会滚动或需要对齐的数字（排名、计数、日期、标签）一律用等宽数字（`font-variant-numeric: tabular-nums`）。
- **字号下限与溢出处理**：`check-composition` 按 `min_font_px.reading` 与 `min_font_px.ui` 检查：界面小字只适用于带 `data-text-role="ui"` 的元素，任何主题（含 custom）`ui` 下限不得低于 **22px**（HyperFrames 对 28px 以下文字报警告时，阅读文字须处理，界面小字可忽略）；字幕字号由各 scene 的 `layout.caption.font_size_px` 决定，不占主题下限。文字放不下时缩小字号，不要溢出；素材说明放在素材外，不压住素材关键区域。

### 纸面、形状、图标与通用元素

- **纸面与分层**：1920×1080 纸纹贴图静态铺满 `#ground`（`center / cover`，竖屏放大裁中间，不平铺、不做动画），纸纹上不叠网格、点阵或方格底纹；卡片和面板用 `--c-card` 实底盖在纸纹上，靠底色差与 **2px** `--c-border` 细线分层（1px 线经 H.264 压缩易断开）。不用阴影、渐变卡片、玻璃质感或满屏饱和色块（唯一满屏色块是方格转场，格子 48px、圆角 9px；药丸圆角统一 999px）。
- **面板栏与界面条**：面板顶部标题栏用 `--c-surface` 底 + 下边 2px 线，高 56–60px；界面条用 `--c-chrome` 深色底（横屏顶部导航栏与单行底部字幕条各高 72px、上下对称；竖屏讲解布局无顶部导航栏，底部双行字幕条高 144px，高度以当前 scene 布局区域为准），主字 `chrome-ink`、次字 `chrome-muted`、当前项下划线 6px `chrome-active`。
- **图标**：16×16 线性图标，`fill: currentColor`，尺寸为所在行字号的 0.8–0.9 倍，颜色跟随文字或真实语义色。
- **高亮行、指标药丸与步骤时间线**：高亮行用 `--c-focus-tint` 底 + 左侧 6px `--c-focus` 竖条，行首编号/排名变焦点色；指标小标签用 `positive-tint` 底 / `positive-solid` 边 / `positive-text` 字（不直接用 `--c-positive` 做标签字），焦点小标签用 `focus-tint` 底 + `focus` 字；步骤时间线左侧 2px 竖线串 44px 圆节点，当前步填 `--c-focus`、已完成盖 `--c-done` 对勾。
- **模板叠加**：模板可在主题 `:root { … }` 之后追加 `:root { … }` 增补或覆盖少量专属变量（如 GitHub 模板把方格换成贡献图绿），不能替换主题语义。

## 单文件主题契约与字体维护（`<主题>.md`）

每个注册主题由 `modules/designs/<主题>/<主题>.md` 单文件同时定义说明与机器配置：

1. **第 1 节唯一 `:root` CSS 代码块**（` ```css :root { … } ``` `）：完整定义共享主题变量，既是复制到工程 `index.html` 的样式，也是脚本提取 `tokens` 的唯一来源。
2. **第 2 节唯一字体与字号配置代码块**（` ```json { … } ``` `）：只放 `min_font_px` 与 `fonts` 两个字段（不含 `tokens` 或字幕字号）：

```json
{
  "min_font_px": {"reading": 26, "ui": 22},
  "fonts": {
    "css_filename": "<主题>-fonts.css",
    "rename": {"Google 家族名": "主题字体别名"},
    "css2_families": ["Family+Name:wght@400;700"]
  }
}
```

仓库已将各主题字体提交在 `resources/fonts/`：`resources/fonts/<主题>/<css_filename>` 存 CSS，共用的 WOFF2 存在 `resources/fonts/files/`（按 URL 哈希去重，SIL OFL 1.1 许可在 `resources/fonts/licenses/`）。视频工程安装已提交字体（不联网、不用系统字体）：

```bash
bash scripts/fonts-download.sh <目标目录> --theme modules/designs/<主题>
```

装入工程后在 `index.html` 的 `<head>` 用 `<link rel="stylesheet" href="assets/fonts/<css_filename>">` 引入。按用户要求生成 custom design 时可复用某个现有主题字体包作为资源，但 token 字体名必须匹配实际 CSS，复用字体资源不等于采用该 preset 的视觉设计。

新建主题、更新字体版本或补齐缺失字体时，修改 `<主题>.md` 的 `fonts` 块（`css2_families` 为 Google Fonts css2 `family=` 参数列表，`rename` 为家族名重命名映射，不改名填 `{}`），运行维护命令重新拉取并清理未引用的池文件后提交：

```bash
bash scripts/fonts-download.sh --refresh --theme <主题>
```

## Custom design 配色草案

以下草案仅在用户在 `composition_requests` 中明确要求库外风格、需要生成 custom design 时作为配色参考；它们不是注册 preset，未获用户明确要求时不主动采用。采用时须换算成完整的共享 `--c-*` / `--font-*` / `--motion-*` / `--ground` token 集合写入 `composition/design.json`，字体须复用仓库已有资源且与实际 CSS 一致（未入库字体名不能直接当作可用依赖）。若将来正式迁入主题目录，按上节写成 `designs/<名>/<名>.md` 并运行 `--refresh` 提交字体。

### Warm Editorial（杂志跨页、精致、新闻感）

```
--bg:        #f6f1e7
--surface:   #fffefb
--overlay:   #ece4d2
--text:      #2c2826
--muted:     #6b5f57
--subtle:    #aaa092
--line:      #c9bfae

--accent-1:  #c8521c   /* terracotta — hero accent */
--accent-2:  #4a6741   /* moss — secondary */
--accent-3:  #8a5a44   /* cocoa — tertiary */
--accent-4:  #d6a634   /* mustard — emphasis */
```

字体建议：serif + sans + mono 三件套（不要混搭两种 sans-serif），实际采用时映射为仓库已入库字体。

### Dark Premium（科技、深邃、高级）

```
--bg:        #0a0e1a
--surface:   #131826
--overlay:   #1c2237
--text:      #e8ecf4
--muted:     #9aa3b8
--subtle:    #5e6884
--line:      #2a3147

--accent-1:  #6366f1   /* indigo — hero */
--accent-2:  #06b6d4   /* cyan — secondary */
--accent-3:  #f59e0b   /* amber — emphasis */
--accent-4:  #ec4899   /* pink — rare CTA */
```

字体建议：无衬线标题/正文 + 等宽代码，实际采用时映射为仓库已入库字体。
