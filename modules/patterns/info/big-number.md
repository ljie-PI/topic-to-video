# Pattern：big-number（大数字）

单个关键数字作为画面主角：hero stat、冲击性指标。本文件是建议，不是规则。

## 适用场景和触发信号

- 旁白给出一个冲击性数字：成本、速度、显存、排名、增长，并把它当作 hook。
- 屏幕文本单元 `visual_role = "big_number"`；典型字段是 value、unit、label、context。
- 多个并列数字不算本 pattern，看 `patterns/info/list-grid.md` 的指标条 / 数据块。

## 区域尺寸建议

- 数字是主角：建议占画面高度的 1/4 以上，单位比数字小一到两档，label 和 context 再小一档。
- 只放一个指标；第二个指标会稀释冲击，建议拆 scene。

## 横屏摆法

- 大数字 hero：数字居中或偏左，label 和 context 在其下方或右侧。
- 也可数字 + 单指标冲击卡，配一条 summary rail 放背景数字的来源说明。

## 竖屏摆法

- 大数字 + 短解释纵向堆叠；避免多指标同屏。
- 数字在上、解释在下，利用竖屏的纵向落差。

## 动效候选与应避免

候选：count-up（数字滚到目标值）、dynamic scale（数字落定时的尺度反馈）、single stat hit；配 ring / bar fill、camera landing、关键词强调。

避免：所有数字同时出现后的 idle pulse；数字滚动没有目标值意义（只是装饰）。

## 用色

- 通用：主数字用 `--c-ink` / `--c-focus`；确认或风险数值才用语义色；普通 label 用 `--c-ink2` / `--c-muted`。
大数字与榜单共享同一套数值用色（来源是主题文档里 leaderboard / big_number / data_block / metric_strip 的合并行）：见 `info/leaderboard.md` 的「用色」表，按主题取行。

## 已有实现

尚无。
