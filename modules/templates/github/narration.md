# 旁白要求：github 模板（GitHub 热榜 / 开源项目盘点）

模板（见 `modules/templates/github/github.md`）需要的**锚点句**和读法要求。script agent 撰写旁白与场景规划时读本文件；锚点句写进 `scene-plan.json` 的 `cues` 字段，Phase 8 用它们从配音里算出秒数，驱动导航 tab、转场卡片、Jay 的瞥视和 Star → Starred 动画。

## 锚点句（cues）

每个场景按模板场景给出锚点句。锚点句必须**原样取自显示稿**（align-narration 按文本匹配定位），每个项目依次念到：

1. **`trending-overview`（榜单总览）**
   - 开场一句点题（“本周 GitHub 上有哪些项目值得关注”一类）。
   - 每个项目一句，依次念到**项目名**（owner / repo 或 repo 名）——一句里只念一个项目，顺序与榜单名次一致。每个项目名的出现时间就是该项目的 `cue`。
2. **`project-cover`（项目封面，每个项目一段）**，按顺序出现：
   - 念到**项目名** → 对应封面的 `nameAt`；
   - 念到**一句话介绍（tagline）** → 对应 `taglineAt`；
   - 念到**本周 star 数** → 对应 `starsAt`（数字写法进词表，如 `"20,267": "两万零二百六十七"`）。

场景规划里把上面这些锚点句摘录进各 scene 的 `cues`。封面场景用 `template_scene: "project-cover"`，总览场景用 `template_scene: "trending-overview"`。

## 读法要求

- 项目名按显示稿原样写（`storytold / artcraft`），owner 与 repo 之间用空格或“斜杠”读法在词表里声明（如 `"/": ""` 或改写句子结构避开斜杠）。
- star 数、名次等数字在显示稿里写阿拉伯数字，朗读形式进词表。
- 主要语言名（Rust、Go、TypeScript……）保留原文，通常不需要词表条目。
- 结尾可以回到榜单收束（“趋势”tab 的时间点取结尾段开始时间）。

## 内容触发参考（写 facts / pattern_hints 用）

旁白出现以下内容时，在 scene 的 `facts` / `pattern_hints` 里体现对应的信息形态（仅供 composition 参考，不是硬约束）：

1. 出现 `owner/repo`、仓库名、GitHub、开源、stars、forks、issues、PR、license、release → `github_repo` 领域。
2. 仓库身份 / 一句话用途 → `product_card` / `title` 形态（`repo_identity_card`）。
3. stars / forks / contributors / issues / releases / commits → `metric_strip` / `data_block`（`repo_metrics`）。
4. 语言、框架、依赖、技术栈 → `architecture_diagram` / `network_graph`（`language_stack` / `dependency_graph`）。
5. 安装、quickstart、命令行 → `terminal_block`（`quickstart_command`）。
6. 目录、核心文件、monorepo、packages → `file_tree`。
7. issue → PR → merge、CI、release → `process_flow`（`contribution_flow`）。
8. 项目历史、版本、最近更新 → `timeline`（`release_timeline`）。
