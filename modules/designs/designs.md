# 设计主题

设计主题只规定**外观**：配色、字体、字号、背景、形状、图标风格、动效节奏。它不管内容，也不管版面，所以所有类型的视频、所有场景都能用。

组件和模板不认识具体的颜色和字体，只读下面这套**主题变量**。每个主题都要把这套变量定义完整；换主题，就是换一组变量值和背景资源。

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

语义色（`--c-info` / `--c-warning` / `--c-danger`）只表达真实的信息语义，不做装饰；同一元素不叠加多种语义色。有些主题的 warning / danger 会映射到同一个品牌色（例如 Product Hunt 用高对比橙表达警示），映射关系写在该主题文档里。

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

这三个变量给组件和模板的默认动效定节奏；个别强调动效（数字弹跳、转场）不受它们约束，写法见各主题文档的动效小节。所有动画只由时间决定：不用 `repeat: -1`，不用随机数；需要随机的地方用固定种子。

### 字号下限

每个主题必须写明自己的字号下限，渲染前检查（check-composition）会拿它当硬门槛：

- **阅读文字**（正文、列表、说明）不小于主题文档规定的下限，默认主题不得低于 **22px**；
- **字幕**字号由所选 layout 的字幕规格决定（见 `layouts/*.json` 的 `caption`），不占主题的下限额度；
- 大号的弱化数字（`--c-muted`）只允许 34px 以上。

用法：
- 主题文档里给出一段 `:root { … }` 代码，复制到视频的 `index.html`。
- 字体的 `@font-face` 也写在 `index.html` 里，组件只读 `--font-sans` 和 `--font-mono`。
- 模板可以在主题变量之后再写一段 `:root { … }`，覆盖其中几个变量，加入这类视频专属的颜色。例如 GitHub 模板把方格换成贡献图的绿色。

## 字体清单（fonts.json）

每个主题目录里有一份 `fonts.json`，是字体下载脚本唯一读取的清单。脚本用法：

```bash
bash scripts/fonts-download.sh <目标目录> --theme modules/designs/<主题>
# 旧的具名风格仍然有效，等价于对应主题的清单：
bash scripts/fonts-download.sh <目标目录> <主题>
```

清单格式：

```json
{
  "css_filename": "rose-pine-<主题>-fonts.css",
  "rename": true,
  "css2_families": ["Noto+Sans+SC:wght@400;500;700", "IBM+Plex+Mono:wght@400;600"]
}
```

- `css2_families`：Google Fonts css2 API 的 `family=` 参数，每项一个家族（含轴规格），脚本把它们用 `&` 拼成 `https://fonts.googleapis.com/css2?family=…&display=swap`。
- `css_filename`：写进目标目录的本地 CSS 文件名；视频工程在 `index.html` 的 `<head>` 里用 `<link rel="stylesheet" href="assets/fonts/<css_filename>">` 引入。
- `rename`：为 `true` 时把 Google 家族名改成短别名（`Noto Sans SC` → `NotoSansSC`，`IBM Plex Mono` → `IBMPlexMono`，手写体同理），主题文档里的 `--font-*` 栈用短别名；为 `false` 时保留 Google 原名（github 主题用全名）。

## 现有主题

| 主题 | 目录 | 气质 |
|---|---|---|
| default | `designs/default/` | 暖白画布 + 克制薰衣草强调，安静明亮的轻编辑风（Frag Note） |
| dawn | `designs/dawn/` | Rosé Pine Dawn 暖奶油底，手绘圈点与手写体 |
| moon | `designs/moon/` | Rosé Pine Moon 深色底，严肃克制的技术编辑风 |
| github | `designs/github/`，背景贴图在同目录的 `textures/` | 冷灰棉纸，加上低饱和的 GitHub 灰、蓝、绿；无阴影，2px 线，卡片分层 |
| producthunt | `designs/producthunt/` | Product Hunt 产品风：白底、品牌橙、温暖对话感 |

## 备选配色

默认是 **default**（暖白、安静、克制的编辑风）。用户想换风格时按上表选择；也可以从下面的 mood 描述反查：

| 用户说 | 选 |
|--------|----|
| "frag note"、"安静"、"明亮编辑"、"暖白"、"克制"、没说风格 | default |
| "rose pine dawn"、"dawn"、"笔记本"、"小红书"、"温暖"、"手绘"、"ins 风" | dawn |
| "rose pine moon"、"moon"、"严肃"、"深色"、"深色编辑" | moon |
| "github trending"、"repo"、"开源" | github |
| "product hunt"、"周榜"、"launch"、"新产品" | producthunt |
| "杂志"、"编辑"、"复古"、"质感" | 未来主题 Warm Editorial（见下） |
| "科技"、"未来"、"premium"、"暗黑" 但不是 "moon" | 反问：moon 还是 Dark Premium（见下） |

以下两套配色已有完整 token 草案，还没有迁入主题目录；用户点名时可以照抄这组变量建 `:root`，字体用各自列出的家族（下载方式同上，把家族加进一份 fonts.json 即可）。

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

字体：`EB Garamond` 或 `Crimson Pro`（serif 标题） + `Inter` 或 `IBM Plex Sans`（正文） + `JetBrains Mono`（数据）。即便用这个配色，**也不要搭配两种 sans-serif**：serif + sans + mono 是安全的三件套。

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

字体：`Space Grotesk` 或 `Manrope`（标题） + `Inter`（正文） + `JetBrains Mono`（代码）。
