# cover-handoff 模板（Phase 11 — 生成封面）

`scripts/prepare-handoff.py <ws> cover` 读取本文件里的 markdown 代码块，把 `{{name}}` 占位符换成实际值，写出 `{work_dir}/{topic_name}/cover-handoff.md`；同一次调用还会把委派包物化到工作区。主 agent 不手写 handoff；有占位符没被替换时脚本报错退出。

五个小节固定为 `## Coding Agent`、`## Inputs`、`## Outputs`、`## Required References`、`## Additional Instructions`，标题不变；Additional Instructions 没有额外指令时写 `None`，但小节始终保留。

占位符取值（路径全是绝对路径；命令里的 skill 脚本用 skill 根目录的绝对路径）：

| 占位符 | 取值 |
|---|---|
| `{{topic_name}}` / `{{ws}}` | 工作区目录名 / 工作区绝对路径（散文里用裸路径） |
| `{{ws_q}}` / `{{skill_root_q}}` / `{{venv_activate_q}}` | 工作区 / skill 根目录 / venv activate 脚本的 shell 引号版：**命令行里必须用引号版**（路径可能含空格） |
| `{{skill_root}}` | skill 根目录的绝对路径 |
| `{{coding_agent}}` / `{{coding_model_instruction}}` | 按 `inputs.json.delegation.cover` 与全局 `coding_agent` 解析的有效 agent / model；未指定 model 时模型说明为空 |
| `{{orientation}}` / `{{language}}` / `{{input_mode}}` | `inputs.json` 的对应字段 |
| `{{default_sizes}}` | 默认产出的三套封面尺寸（`1080x1440`、`1440x1080`、`1920x1080`） |
| `{{material_catalog}}` | catalog 适用时：catalog 的路径；否则“无（无可用素材）” |
| `{{cover_dir_q}}` / `{{cover_report_q}}` / `{{cover_summary_q}}` | 封面目录、机器自检报告与交付摘要的路径（shell 引号版） |
| `{{required_references}}` | 按叠加顺序编号：cover 基础指令（工作区副本） |
| `{{additional_instructions}}` | `inputs.json` 的 `cover_requests` 逐条列出；没有写 `None` |

```markdown
# cover-handoff — {{topic_name}}

## Coding Agent

{{coding_agent}}
{{coding_model_instruction}}

## Inputs

- 工作区：{{ws}}/
- {{ws}}/research-brief.md：已核实的调研简报（`## Key facts`、`## Numbers`、`## Quotes` 是封面钩子与重要数字的唯一事实边界）
- {{ws}}/script.txt + {{ws}}/scene-plan.json：显示稿与叙事规划（对照开场钩子与核心结论，只读不改）
- {{ws}}/transcribe/timeline.json + {{ws}}/composition/assets/subtitle-units.json：语音与字幕时间（用于定位前 15 秒与全片核心内容帧，只读不改）
- {{ws}}/composition/design.json：全片 design 机器契约（复用 `tokens` 色板与字体栈，已安装本地字体位于工作区相对路径 `composition/assets/fonts/`）
- {{ws}}/composition/scene-config.json + {{ws}}/composition/renders/final.mp4：成片与各视觉场景区域（截取前 15 秒与全片最重要的 1–2 帧，并按 `regions` 裁掉 `nav-bar` / `caption-bar` / 原片 `presenter` 保留区）
- material-catalog.json：{{material_catalog}}（图片 `local_path` 相对 `harvest_page/`，视频片段相对工作区根 `clips/`）
- 必用招手主持人立绘：{{skill_root}}/modules/components/presenter/images/presenter-wave.png（复制到 `cover/assets/presenter-wave.png`，按各尺寸固定槽位挂载）
- {{ws}}/inputs.json：视频朝向 {{orientation}}、语言 {{language}}、input_mode {{input_mode}}；默认产出尺寸为 {{default_sizes}}（Additional Instructions 另有指定尺寸时以用户要求为准）

## Outputs

写到工作区封面目录（{{ws}}/cover/；按派发指令限定的尺寸与文件边界落盘，主会话已预取 `cover/assets/` 时直接复用）：

- 独立 HTML 源文件：`cover/cover_{W}x{H}.html`（默认按单尺寸小批并行覆盖 {{default_sizes}} 共 3 份独立 HTML，禁缩放同一份 HTML 换尺寸）
- 成品位图、高清母版与 `400px` 缩略图：`cover/cover_{W}x{H}.png`、`cover/cover_{W}x{H}@2x.png`、`cover/qa/thumb_{W}x{H}_400w.png`
- {{cover_report_q}}：确定性渲染与 DOM 机器自检报告（最终 `verdict` 必须为 `pass`）
- {{cover_summary_q}}：封面交付说明（记录钩子文案、`1–3` 个重要数字口径、所截 `1–2` 帧时间点与场景来源、各尺寸成品路径及 `400px` 缩略图三问结论）

全部目标尺寸 HTML 落盘后，运行确定性渲染与机器自检（默认由主会话中心化执行）：

- source {{venv_activate_q}} && python3 {{skill_root_q}}/scripts/render-cover.py {{cover_dir_q}} \
    --output {{cover_report_q}}

（若 Additional Instructions 明确指定了自定义尺寸列表，追加 `--sizes <W1xH1> <W2xH2>`；仅当调研简报确无任何核实数字时才允许传 `--allow-zero-num`。）

机器自检 `verdict == "pass"` 后，对生成的 `cover/qa/thumb_{W}x{H}_400w.png` 执行 `400px` 缩略图三问验收（Mode 1 显式 VLM 或 Mode 2 自身看图工具）：

- source {{venv_activate_q}} && python3 {{skill_root_q}}/scripts/vision-analyze.py \
    --detail high \
    --prompt "逐张回答三个问题：1. 3秒内你读到的第一句话是什么？2. 画面主体是什么，占画面大概多少，右下角招手主持人是否清晰？3. 整张图有几个明显的视觉块？" \
    --images {{cover_dir_q}}/qa/thumb_1080x1440_400w.png {{cover_dir_q}}/qa/thumb_1440x1080_400w.png {{cover_dir_q}}/qa/thumb_1920x1080_400w.png

## Required References

按顺序阅读（叠加顺序与冲突处理见 {{ws}}/references/delegation/conventions.md）：

{{required_references}}

## Additional Instructions

{{additional_instructions}}
```
