# 模板：github/project-cover（项目封面）

属于 GitHub 热榜这一类视频（见 `templates/github/GUIDE.md`）。

一个上榜项目的封面，用来开始讲一个项目。

- **布局**：讲解模式（`layouts/presenter.md`）。
  - **主展示区**：放大版的 GitHub 仓库头，从上到下是：
    1. 绿色标签“Trending #1 · 本周”；
    2. 仓库图标、`owner / repo`（72px）和 Public 标签；
    3. 一句话介绍（60px）；
    4. 可选的 topic 标签；
    5. 大号 star 数字，从 0 滚到目标值；
    6. 语言，以及 Star 按钮（会变成 Starred）。
  - **副展示区**：项目 logo 卡片。没有 logo 时，显示仓库名首字母的大字卡片。
- **节奏**：按配音分三拍。
  1. 念到项目名：标签、路径、logo 依次出现。
  2. 念一句话介绍：介绍文字从左往右擦出，topic 标签随后出现。
  3. 念 star 数：数字滚动 1.4 秒，然后语言和 Star 按钮出现，Star 变成 Starred。

  最后可以选择整体退场，交给后面的场景（比如演示和功能步骤）。

## 文件

- `templates/github/project-cover.html`：场景本体。图标已内联；logo 由参数指定。

## 依赖

- 设计主题的全部变量（`--c-*`、`--font-sans`），由视频的 `index.html` 提供；模板里没有写死的色值和字体名。
- 项目 logo 图片（可选）。

## 安装与挂载

1. 把 `templates/github/project-cover.html` 复制到视频工程的 `compositions/project-cover.html`。
2. 每个项目挂一个挂载点：
   - `data-composition-id="project-cover"`，`data-composition-src="compositions/project-cover.html"`；
   - `data-start`：项目段开始的视频时间，等于转场的切点；
   - `data-duration`：至少到退场结束；
   - `style="z-index: 2"`；
   - `data-variable-values`：这个项目的内容和时间点。

同一个模板可以挂多次，每次填不同的参数。

## 挂载参数（全部写在 `data-variable-values`）

| 参数 | 默认 | 说明 |
|---|---|---|
| `rank` | 1 | 排名 |
| `owner`, `repo` | — | 仓库路径 |
| `eyebrow` | `"Trending #<rank> · 本周"` | 绿色标签的文字 |
| `visibility` | `"Public"` | 路径后面的小标签；设为 `""` 或 `"none"` 就不显示 |
| `tagline` | `""` | 一句话介绍，最好不超过 16 个汉字 |
| `topics` | `""` | 逗号分隔的 topic，例如 `"rust, ai, image-generation"`，显示成蓝色小标签。只填项目真实的 topic，不确定就留空 |
| `stars` | 0 | star 数（数字），滚动的目标值 |
| `starsPrefix` | `"+"` | 数字前缀 |
| `starsLabel` | `"本周新增 star"` | 数字后面的说明 |
| `lang`, `langColor` | — | 语言名和色点（色值见 `templates/github/GUIDE.md` 的语言色表） |
| `logo` | `""` | logo 图片路径。留空时显示仓库名首字母卡片 |
| `starred` | `"on"` | 设为 `"off"` 时，Star 按钮不变成 Starred |
| `nameAt` | 0.55 | 第一拍：名字出现（场景秒）。默认值刚好在贡献图转场退去时 |
| `taglineAt` | 2.4 | 第二拍：介绍出现 |
| `starsAt` | 4.3 | 第三拍：数字开始滚动 |
| `exitAt` | 0 | 退场时间，0 表示一直停留到场景结束。设了时间后，主展示区的元素依次上移淡出，logo 卡片随之淡出 |

三个时间点一般直接取配音：念项目名、念介绍、念 star 数的那三句话各自的开始时间，减去场景开始的时间。

## 自动适配

- 路径太长时自动缩小字号：比如 `K-Dense-AI / scientific-agent-skills`，72px 放不下，会缩到正好放进主展示区，最小 36px。
- 一句话介绍太长时同样自动缩小。
- 没有 topic 时，topic 那一行不占位置，下面的内容自动上移。
- 没有语言时，不显示语言。

## 和其他模块的配合

- **转场**：在 `window.VIDEO.cuts` 里加一项，`at` 等于这个封面的 `data-start`；卡片按 `templates/github/GUIDE.md` 里的对应关系，用同一个项目的信息填。
- **导航栏**：在 `window.VIDEO.tabs` 里加一项，`at` 也等于 `data-start`。
- **人物动作**（视频秒）：
  - `data-start + starsAt` 时做 `["eureka", 2700]`，数字一出来就惊喜，头顶冒“!”；
  - `data-start + taglineAt + 0.05` 时瞥视 `"L"`，看介绍文字。
- **后续场景**：要接演示画面时，把 `exitAt` 设成交接时间，例如 6.45。后面的场景从同一时间开始，把左上角的页眉行换成项目标题条。
