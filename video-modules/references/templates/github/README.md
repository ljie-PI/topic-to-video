# 模板：github（GitHub 热榜 / 开源项目盘点）

一类视频：人物 Jay 主持，盘点 GitHub 上的一批项目（例如本周 Trending Top 5）。整支视频看起来像在浏览 GitHub 页面。

这里写的是**这类视频怎么组装**：用哪个布局、哪些组件、给组件什么参数、GitHub 专属的配色和元素、数据怎么填，以及人物怎么演。完整的例子见 `examples/github-trending/`。

## 1. 组成

| 部分 | 用什么 | 说明 |
|---|---|---|
| 设计主题 | `references/designs/github.md`（纸本） | 也可以换成同一套变量的其他主题 |
| 布局 | `references/layouts/presenter.md`（讲解模式） | 区域位置固定 |
| 顶部导航 | 组件 `nav-bar` | 参数和标签写法见第 3 节 |
| 底部字幕 | 组件 `caption-bar` | 字幕取配音的逐句时间 |
| 场景转场 | 组件 `transitions/tile-wipe` | 方格改成贡献图配色，卡片写法见第 3 节 |
| 主持人 | 组件 `jay` | 动作写法见第 5 节 |
| 场景 | `trending-overview`、`project-cover`（文档 `references/templates/github/<场景>.md`，代码 `assets/templates/github/<场景>.html`） | 后面可以继续加：项目演示、注意事项、结尾 |

一支典型视频的场景顺序：

1. 榜单总览（`trending-overview`）。
2. 每个项目一段：先是项目封面（`project-cover`），然后是项目演示加功能步骤（还没做成模板）。
3. 结尾（还没做成模板）。

每次换段都用方格转场。

## 2. GitHub 专属的配色和元素

### 2.1 方格转场 = 贡献图

在设计主题的变量后面，再加一段覆盖，把方格换成 GitHub 贡献图的五档颜色（空格灰加四档绿，按纸本主题降过饱和度）：

```css
/* templates/github — the tile wipe is the contribution graph */
:root {
  --c-tile0: #e4e8ec;  --c-tile1: #c3dfca;  --c-tile2: #92c4a0;  --c-tile3: #5f9f75;  --c-tile4: #33744c;
}
```

如果用的是饱和度更高的主题（如 aurora），换成 GitHub 原色：`#EBEDF0 #9BE9A8 #40C463 #30A14E #216E39`。

### 2.2 语言色点

语言名前面的小圆点，用 GitHub 的标准语言色，不跟随主题变化：

| 语言 | 色值 | 语言 | 色值 |
|---|---|---|---|
| Rust | `#DEA584` | Go | `#00ADD8` |
| Python | `#3572A5` | C++ | `#F34B7D` |
| TypeScript | `#3178C6` | Java | `#B07219` |
| JavaScript | `#F1E05A` | Ruby | `#701516` |
| 其他 | `#8B949E` | | |

### 2.3 品牌与界面元素

- **GitHub 标志**：`assets/templates/github/brand/github-mark-white.svg`，白色，用在深色导航栏上。复制到视频工程的 `assets/brand/`。不旋转，不改颜色。
- **图标**：GitHub Octicons，已经内联在场景里，包括 repo、star、star-fill、book、triangle-down。
- **仓库路径**：`owner / repo`，焦点色。owner 用常规字重，repo 加粗，用比例字体，和 GitHub 一样。
- **Star → Starred**：讲到一个项目约 0.45 秒后，空心星变成 `--c-highlight` 色的实心星，按钮文字从“Star”换成“Starred”，旁边的数字弹一下。
- **Trending 标签**：指标色的药丸标签，写作“Trending #名次 · 本周”。
- **“README.md” 面板**：标题栏是书本图标加等宽的 `README.md`，右侧是仓库名。

## 3. 组件参数

| 组件 | 挂载参数（`data-variable-values`） | `window.VIDEO` 数据 |
|---|---|---|
| `nav-bar` | `{"logo": "assets/brand/github-mark-white.svg", "path": "github / trending"}` | `tabs`：`概览`（0 秒）、`#1`…`#5`（每个项目段开始的时间）、`趋势`（结尾开始的时间） |
| `caption-bar` | 不用填，默认就是讲解模式布局的字幕区 | `captions`：配音逐句 `{ start, end, text }` |
| `tile-wipe` | 不用填，默认起点就是 Jay 的笔记本 | `cuts`：每个项目段开始时一项，卡片写法见下 |
| `jay` | `{"x": 1294, "y": 642, "size": 420}` | `jay`：动作剧本，见第 5 节 |

**转场卡片**，从项目信息对应过来：

| 卡片字段 | 填什么 | 例子 |
|---|---|---|
| `label` | 名次 | `"#1"` |
| `title` | `owner / ` | `"storytold / "` |
| `emphasis` | `repo` | `"artcraft"` |
| `meta` | 语言色点 + 语言；本周 star | `[{"dot": "#dea584", "text": "Rust"}, {"strong": "+20,267", "text": "star 本周"}]` |

## 4. 数据从哪来

- **项目信息**：每个项目的名次、owner、repo、一句话描述、本周 star 数、主要语言，都取自 GitHub Trending 页面或仓库页面。
- **README 截图**：每个项目一张，PNG，宽度至少 1044px，从 README 顶部开始的长截图。
- **logo**：项目自己的 logo 图片；没有可以不填，封面会显示首字母卡片。
- **配音**：
  - 字幕的逐句时间就取自配音；
  - 每个项目的 `cue`，以及封面的 `nameAt`、`taglineAt`、`starsAt`，都取配音里对应那句话的开始时间；
  - 嘴型数据用 `scripts/make-envelope.mjs` 从配音生成。

## 5. 人物怎么演（写在 `VIDEO.jay`，时间是视频秒）

| 时刻 | 动作 |
|---|---|
| 开场后 0.45 秒 | `["wave", 3000]`，挥手欢迎 |
| 榜单总览里每个项目的 `cue` | 瞥视 `[cue, 1.0, "U"]`，抬头看榜单 |
| `cue + 1.7` 秒 | 瞥视 `[cue + 1.7, 1.0, "L"]`，看 README |
| 每次转场前约 0.85 秒 | `typing [切点 - 0.85, 切点 + 0.05]`，方格像是从他的笔记本里冒出来的 |
| 封面的 star 数出现时（段开始 + `starsAt`） | `["eureka", 2700]`，头顶冒出“!” |
| 封面的介绍出现时 | 瞥视 `"L"` |
| 讲注意事项时 | `["think", 2000]`，加一条 `thoughts`，比如“授权？”；或者用 `sigh`（限制条件） |
| 讲到项目的亮点、演示效果很好时 | `["smile", 2200]` |
| 讲到关键思路、“原理是……”时 | `["idea", 2400]` |
| 抛出问题、“它是怎么做到的？” | `["question", 2400]` |
| 演示画面里有值得细看的地方 | `["lean", 2400]`，同时瞥视 `L` |
| 不推荐、某种用法不可取 | `["shake", 1600]` |
| 边讲边认同 | `["nod-small", 1000]`，不要连续用 |
| 结尾 | `["laugh", 2200]`，再 `["wave", 3200]` 告别 |
