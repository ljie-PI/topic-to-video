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

语义色（`--c-info` / `--c-warning` / `--c-danger`）只表达真实的信息语义，不做装饰；同一元素不叠加多种语义色。

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

每个主题必须在文档的「字号下限」那一行写明两条下限，并在 `<名>.json` 的 `min_font_px.reading` / `min_font_px.ui` 写入相同的数。渲染前检查（check-composition）通过 `--design <名>.json` 读取 JSON，把两个数分别当硬门槛；文档与 JSON 的一致性由测试保证：

- **阅读文字**（正文、列表、说明）不小于 N；
- **界面小字**（面板标题栏、按钮、小标签）不小于 M，只适用于放在 `data-text-role="ui"` 元素里的文字，任何主题的 M 都不得低于 **22px**；
- **字幕**字号由所选 layout 的字幕规格决定（见 `layouts/*.json` 的 `caption`），不占主题的下限额度；
- 大号的弱化数字（`--c-muted`）只允许 34px 以上。

用法：
- 主题文档里给出一段 `:root { … }` 代码，复制到视频的 `index.html`。
- 字体的 `@font-face` 也写在 `index.html` 里，组件只读 `--font-sans` 和 `--font-mono`。
- 模板可以在主题变量之后再写一段 `:root { … }`，覆盖其中几个变量，加入这类视频专属的颜色。例如 GitHub 模板把方格换成贡献图的绿色。

## 机器契约与字体清单（<名>.json）

每个主题都有 `<名>.md` 和 `<名>.json`：文档供人和 LLM 阅读，同名 JSON 是脚本读取的机器契约。JSON 的 `tokens` 必须完整定义上面的变量，值与文档 CSS 代码块一致；`min_font_px` 和 `caption_font_px` 与文档的字号下限一致。结构如下：

```json
{
  "design": "<主题>",
  "tokens": {"--c-canvas": "...", "--font-sans": "...", "--motion-easing": "..."},
  "min_font_px": {"reading": 26, "ui": 22},
  "caption_font_px": 36,
  "fonts": {
    "css_filename": "<主题>-fonts.css",
    "rename": {"Google 家族名": "主题字体别名"},
    "css2_families": ["Family+Name:wght@400;700"]
  }
}
```

每个主题的字体已经下载好，提交在仓库的 `resources/fonts/`：主题自己的目录 `resources/fonts/<主题>/` 里只放一份 CSS，它引用的 WOFF2 放在所有主题共用的字体池 `resources/fonts/files/`（文件名是 Google Fonts 下载地址的哈希）。多个主题用同一个字体家族时，WOFF2 只存一份，新增主题不会复制字体文件。字体都按 SIL Open Font License 1.1 分发，许可文本在 `resources/fonts/licenses/`；新增字体家族时把它的 OFL.txt 一起放进去。视频工程用字体时只拷贝，不联网：

```bash
bash scripts/fonts-download.sh <目标目录> --theme modules/designs/<主题>
# 旧的具名风格仍然有效：
bash scripts/fonts-download.sh <目标目录> <主题>
```

`<名>.json` 的 `fonts` 段是这些字体的来源清单，只在维护时用：新建主题、或者想换字体版本时，改好清单后运行 `bash scripts/fonts-download.sh --refresh --theme <主题>`，脚本从 Google Fonts 重新下载，覆盖 `resources/fonts/<主题>/` 里的 CSS，只往字体池里补缺的 WOFF2（池里已有的不再下载），并清掉不再被任何主题 CSS 引用的 WOFF2，再把结果提交进仓库。

- `fonts.css2_families`：Google Fonts css2 API 的 `family=` 参数，每项一个家族（含轴规格），`--refresh` 时脚本把它们用 `&` 拼成 `https://fonts.googleapis.com/css2?family=…&display=swap`。
- `fonts.css_filename`：`resources/fonts/<主题>/` 里、以及装进工程后的 CSS 文件名（装进工程时，CSS 和它引用的 WOFF2 平铺在目标目录里）；视频工程在 `index.html` 的 `<head>` 里用 `<link rel="stylesheet" href="assets/fonts/<css_filename>">` 引入。
- `fonts.rename`：Google 家族名到主题字体别名的逐项映射；刷新时只按这张表改名。不需要改名时用 `{}`（github 主题保留 Google 全名）。

## 现有主题

| 主题 | 目录 | 气质 |
|---|---|---|
| default | `designs/default/` | 暖燕麦棉纸，加上低饱和的墨灰和灰薰衣草；内容优先、界面退后的安静编辑风 |
| github | `designs/github/` | 冷灰棉纸，加上低饱和的 GitHub 灰、蓝、绿；技术页面感 |
| producthunt | `designs/producthunt/` | 粉调亚麻纸，加上低饱和的墨蓝、陶土橙和 maker 绿；产品发布的温暖对话感 |

三个主题是同一套做法：纸纹背景（各自目录下的 `textures/paper.jpg`）、低饱和配色、无阴影、2px 线和卡片分层，字号阶梯和字号下限也相同。区别在纸色、焦点色和动效节奏。

## 备选配色

默认是 **default**（暖燕麦纸、安静、克制的编辑风）。用户想换风格时按上表选择；也可以从下面的 mood 描述反查：

| 用户说 | 选 |
|--------|----|
| "安静"、"明亮"、"编辑"、"暖色"、"纸感"、"克制"、没说风格 | default |
| "github trending"、"repo"、"开源" | github |
| "product hunt"、"周榜"、"launch"、"新产品" | producthunt |
| "杂志"、"复古"、"质感" | design 写 default，配色按下面的 Warm Editorial 草案覆盖（见下） |
| "深色"、"暗黑"、"科技"、"未来"、"premium" | design 写 default，配色按下面的 Dark Premium 草案覆盖（见下） |
| "手绘"、"手写" | 目前没有手绘主题：告诉用户，并用 default |

以下两套配色已有完整 token 草案，还没有迁入主题目录，所以**不能**写进 `inputs.json` 的 `design`（状态脚本只接受 `modules/designs/` 下现有的主题）。用户点名时：`design` 写 `default`，先和用户确认，再把草案的配色换算成 `--c-*` 变量写进项目的 `composition-instructions.md`，作为对 default 变量的覆盖；字体仍用 default 的字体（草案列出的字体没有放进仓库）。正式迁入主题目录时，写好 `<名>.md` 和 `<名>.json`，按上面的方法 `--refresh` 并提交字体。

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
