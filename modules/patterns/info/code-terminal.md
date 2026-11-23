# Pattern：code-terminal（代码 / 终端 / 文件树）

代码片段、安装命令、运行日志、repo 目录结构。本文件是建议，不是规则。

## 适用场景和触发信号

- 旁白出现命令、安装、运行、日志、输出、终端、CLI → 终端块。
- 旁白出现代码、函数、API、配置、diff、片段、参数 → 代码块。
- 旁白出现目录、文件、路径、package、模块文件组织 → 文件树。

## 区域尺寸建议

- 优先用有明确边界的 HTML IDE / terminal 大面板做容器（顶栏圆点 + 文件名标签、可选行号列、面板占主内容区宽 `70%+` 并设 `overflow: hidden`），代码 / 终端用 `20–24px` 等宽细体（`--font-mono`，`weight 400–500`，标 `data-text-role="ui"`）；行长按容器宽度截断或摘取，**严禁在窄卡片或裸 SVG `<text>` 中堆长代码行**。
- 只显示关键行：完整文件或长日志摘取与旁白相关的部分。
- 文件树只展开与旁白相关的分支，层级深时折叠。

## 横屏摆法

- 单个宽面板 + 短解释（代码左侧或右侧放一句说明）。
- diff 对比用左右或上下双面板。

## 竖屏摆法

- 单个可读面板 + 上下解释；长行截断 / 摘取。
- 终端输出高亮关键行，其余省略号带过。

## 动效候选与应避免

候选：discrete typing（逐字输入）、line-by-line reveal、execution state（运行状态变化）；cursor tracking、keyword highlight、camera focus；文件树用 branch expansion（分支展开）、selection path。

避免：完整文件 / 日志一次出现；打字机动画慢到影响可读性。

## 用色

- 通用：代码 / 终端面板默认用 `--c-surface` 浅底加 2px 边；需要终端感时用 `--c-chrome` 深底，此时正文用 `--c-chrome-ink`、次要文字用 `--c-chrome-muted`，成功 / 失败只用 ✓ / ✗ 前缀，不把语义色压在深底上；命令、路径、版本号用 `--font-mono`；浅面板上的错误输出用 `--c-danger`。
- 各主题只写和通用写法不同的地方：

| 主题 | 代码 / 终端用色 |
| --- | --- |
| default | 无特殊覆盖。 |
| github | 浅面板上，成功输出用 `--c-positive`，提示用 `--c-info`。 |
| producthunt | 无特殊覆盖。 |

## 已有实现

尚无。
