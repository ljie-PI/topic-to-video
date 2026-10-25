# Pattern：leaderboard（榜单）

排名类内容：Top N、周榜、产品榜、repo 榜。本文件是建议，不是规则。

## 适用场景和触发信号

- 旁白出现 Top N、排名、榜单、周榜、产品榜、repo 榜。
- 屏幕文本单元 `visual_role = "leaderboard"`；典型字段是 rank、name、metric、why it matters。

## 区域尺寸建议

- 每行建议至少 72–92px 高，放得下 rank、名称、一句话描述和指标；行数按区域高度倒推，放不下就减少行数或分页。
- 参考：`layouts/presenter.md` 副展示区 640×522 放紧凑榜单约 5 行（行高 92px、标题栏 56px）；`layouts/stage.md` 主展示区 1728×764 可放更宽的榜单加详情栏；竖屏见 `layouts/portrait.md`。

## 横屏摆法

- rank list + 右侧 detail rail：当前行高亮，详情栏显示该条目的更多信息或预览。
- 也可以整榜平铺，讲到某一行时高亮这一行并刷新旁边的说明。
- 条目多于一屏时按 Top N 截断或分页，不缩字号硬塞。

## 竖屏摆法

- 纵向榜单：一次突出一个条目，其余收进分页 Top N。
- 避免左右窄栏；当前条目放大 + 简短 metric，其余条目小字纵向排列。

## 动效候选与应避免

候选：榜单逐行有序入场；active-row progression（讲到哪行哪行高亮）；count-up、rank swap（排名变化时的位置交换）。

避免：每行用相同的 fade 依次出现而没有主项变化；全部行一次性全亮。

## 用色

- 通用：主数字用 `--c-ink` / `--c-focus`；确认或风险数值才用 `--c-positive` / `--c-warning` / `--c-danger`；普通 label 用 `--c-ink2`（`--c-muted` 只用于 34px 以上的弱化数字）。
- 各主题只写和通用写法不同的地方：

| 主题 | 榜单用色 |
| --- | --- |
| default | 无特殊覆盖。 |
| github | star / 增长数字用 `--c-positive`；排名和链接用 `--c-focus`；数字用等宽字。 |
| producthunt | upvote / 排名的形状（三角、药丸边）用 `--c-highlight`，数字用 `--c-ink`；当前项文字用 `--c-focus`；maker / 已认证指标用 `--c-positive-text`；注册 / 流量用 `--c-info`。 |

## 已有实现

- `templates/github/trending-overview.md`：GitHub Trending 榜单场景，紧凑榜单最多 5 行，讲到某个项目时该行高亮、README 面板同步切换。
