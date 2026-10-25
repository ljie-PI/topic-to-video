# Pattern：product-card（产品身份卡）

产品、repo、paper 或项目的身份卡：名字、一句话定位、关键指标。本文件是建议，不是规则。

## 适用场景和触发信号

- 旁白在介绍一个产品 / repo / paper 的身份：名字、tagline、类别、关键指标。
- 屏幕文本单元 `visual_role = "product_card"`（或 `title`）；典型字段是 name、tagline、category、metric。
- 长视频里出现章节切换、「接下来、第 N 部分」时，也可用同一套身份卡形态做章节标题卡。

## 区域尺寸建议

- 身份卡需要足够的字号落差：名字最大（建议 60px 以上），tagline 次之，指标和标签再次。
- 卡内元素多时优先纵向堆叠：标签 → 名字 → tagline → topic / metric → CTA；横屏可名字居左、指标居右。

## 横屏摆法

- 大号产品卡放主展示区，配一个次要元素（logo 卡、短 metric）在副展示区。
- 名字太长时自动缩小字号（例如 72px 缩到能放下的尺寸），不换行溢出。

## 竖屏摆法

- 纵向堆叠：名字、tagline、指标逐层向下，避免贴顶小字。
- 指标超过 2 个时只保留最重要的，其余交给相邻 scene。

## 动效候选与应避免

候选：card morph anchor（卡从锚点展开）、anchored expand、surface assemble（卡面逐块拼合）；有品牌资产时可用 Lottie。

避免：没有产品行为的空泛 3D spin；名字和指标同时抢焦点的复合动效。

## 用色

- 通用：`--c-ink` 标题；可挑一个 `--c-focus` 关键词、短 eyebrow 或身份标记；指标数字按主题指标色。
- 各主题只写和通用写法不同的地方：

| 主题 | 身份卡用色 |
| --- | --- |
| default | 无特殊覆盖。 |
| github | eyebrow 按身份用 `--c-focus` / `--c-positive` / `--c-done`；仓库路径用 `--font-mono` + `--c-ink`。 |
| producthunt | 产品名用 `--c-ink`；发布 / 排名 / CTA 文字用 `--c-focus`；`--c-highlight` 只做 upvote 形状和标记；tagline 用 `--c-ink2`。 |

## 已有实现

- `templates/github/project-cover.md`：上榜项目的封面场景，绿色排名标签、仓库路径、一句话介绍、star 数滚动、语言和 Star 按钮。
