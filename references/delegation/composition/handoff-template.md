# composition-handoff 模板（Phase 8 — composition）

`scripts/prepare-handoff.py <ws> composition` 读取本文件里的 markdown 代码块，把 `{{name}}` 占位符换成实际值，写出 `{work_dir}/{topic_name}/composition-handoff.md`；同一次调用还会把委派包和 `modules/` 物化到工作区，并按所选 design 预置字体。主 agent 不手写 handoff；有占位符没被替换时脚本报错退出。

五个小节固定为 `## Coding Agent`、`## Inputs`、`## Outputs`、`## Required References`、`## Additional Instructions`，标题不变；Additional Instructions 没有额外指令时写 `None`，但小节始终保留。

占位符取值（命令里的 skill 脚本用 skill 根目录的绝对路径，design 指向工作区副本，scene-config 指向本阶段产物）：

| 占位符 | 取值 |
|---|---|
| `{{topic_name}}` / `{{ws}}` | 工作区目录名 / 工作区绝对路径（散文里用裸路径） |
| `{{ws_q}}` / `{{skill_root_q}}` | 上两者的 shell 引号版：**命令行里必须用这一对**（路径可能含空格），散文里不用 |
| `{{skill_root}}` | skill 根目录的绝对路径 |
| `{{coding_agent}}` / `{{coding_model_instruction}}` | 按 `inputs.json.delegation.composition` 与全局 `coding_agent` 解析的有效 agent / model；未指定 model 时模型说明为空 |
| `{{design}}` / `{{orientation}}` | `inputs.json` 的对应字段，全片固定约束；全局 template / layout 不是准备前提，由本阶段逐视觉场景决定 |
| `{{material_catalog}}` | catalog 适用时（联网抓素材，或论文模式）：catalog 的路径；否则“无（无素材，画面用纯排版）” |
| `{{required_references}}` | 按叠加顺序编号：基础指令 → scene-config 数据契约 → `modules.md` → design 文档与 `<design>.json` 机器契约 → layout 目录（`layouts.md`，可借用的 preset）→ 模板目录（`templates.md`，按场景借用）→ 组件索引（`components.md`，按需读要挂载的组件文档）。它们是发现入口，不是采用清单；全部指向工作区副本；patterns / motion / transitions 单独列为可选参考 |
| `{{additional_instructions}}` | `inputs.json` 的 `composition_requests` 逐条列出；没有写 `None`。各条要求的作用范围以用户表述为准（某个叙事场景 / 某个视觉场景 / 整片），未说明时按整片应用 |
| `{{transcript_q}}` / `{{narration_q}}` / `{{offsets_q}}` / `{{script_txt_q}}` | 确定性字幕生成的四个上游 |
| `{{subtitle_units_q}}` | 字幕单元的最终位置：`{{ws}}/composition/assets/subtitle-units.json` |
| `{{template_cues_q}}` / `{{template_timeline_q}}` | 模板时间锚点的 cue 声明与它的时间文件 |
| `{{timeline_q}}` | Phase 7 的不可变时间轴 |
| `{{check_report_q}}` / `{{composition_dir_q}}` / `{{scene_config_q}}` / `{{narration_audio_q}}` / `{{design_json_q}}` | scene-config、字幕生成、自查与报告的路径 |

```markdown
# composition-handoff — {{topic_name}}

## Coding Agent

{{coding_agent}}
{{coding_model_instruction}}

## Inputs

### Agent 阅读与画面资源

- 工作区：{{ws}}/
- {{ws}}/voice_clone/narration.mp3：生成的配音（唯一音频来源，不重生成 TTS）
- {{timeline_q}}：Phase 7 不可变的段落与 cue 时间轴（只提供真实语音锚点，不提供最终视觉 scene 切分）；本阶段不修改它
- material-catalog.json：{{material_catalog}}
- 素材 ref：图片 / 视频用 `<slug>/<id>`，视频 clip 用 `<slug>/<video_id>:<start>-<end>`；按 slug 定位 entry 后，视频 clip 解析到该 entry 的 `selected_clips[].clip_path`（相对工作区根），不用视频的 `local_path`
- {{ws}}/scene-plan.json：叙事层场景规划（仅作参考）：`intent` / `content_plan` 说明讲什么、怎样展开；可以合并 / 拆分 / 改选素材与演绎方式，最终视觉 scenes、逐场景 template / layout 与构图由你自主设计
- {{ws}}/script.txt：显示稿（旁白与屏幕文字的文本来源，不能改）
- {{ws}}/inputs.json：design {{design}}、orientation {{orientation}}；orientation / design 是全片固定约束。`composition_requests` 的用户画面要求见 Additional Instructions，其作用范围以用户表述为准
- 字体目录：{{ws}}/composition/assets/fonts/（已按所选 design 预置，只用它）

### 仅供工具读取

- {{transcript_q}}：本轮音频的 fresh transcript（词级时间戳；字幕唯一的时间来源）
- {{narration_q}} + {{offsets_q}}：朗读稿与逐字映射表（把时间还原到显示稿）

这些文件只作为下面字幕 / cue 对齐命令的参数；正常流程不阅读或复述其全文，也不拿它们重新理解或改写旁白。执行命令后读取生成的字幕单元与 cue 时间；仅在工具报错且必须诊断时读取相关句子或时间窗口，不重复加载全部文本。

## Outputs

写到工作区（{{ws}}/）：

- {{scene_config_q}}：最终视觉场景机器配置，schema 见 Required References 里的 scene-config 契约文档（version / canvas / total_s / scenes；每个 scene 有唯一 scene_id、source_scene_ids、begin_s / end_s、template 与落盘完整 regions / caption 的 layout）；时间为全片秒，主区间覆盖整段视频。它由你与 storyboard 一起产出：先按「用户要求 → 特别匹配模块 → 即时生成」的顺序逐视觉场景定方案，再落盘
- {{subtitle_units_q}}：最终字幕单元。**在 scene-config 写出后，按各 scene 落盘的 caption 规格生成**（下面第一条命令）。默认脚本生成初稿；已有用户编辑是有效输入，仅改画面 / 重渲染不要覆盖它
- {{ws}}/composition/storyboard.md：storyboard，开头是「组件与转场使用表」，逐个记录实际使用的组件或转场及其挂载参数、`window.VIDEO` 数据来源（含采用转场时的 `cuts`）；每个视觉 scene 写明 intent、template / layout 方案及理由、所用的 content 区域、素材、构图、信息展开与动效安排；必用素材覆盖表按基础指令第一部分处理
- {{ws}}/composition/index.html + {{ws}}/composition/compositions/：HyperFrames 工程与子合成
- {{ws}}/composition/check-composition.json：check-composition 的报告（下面命令的 `--output` 写出它；最后一次运行的 verdict 必须是 pass）
- {{ws}}/composition/renders/final.mp4：渲染产物

先写 {{scene_config_q}}（逐视觉场景定方案），再生成字幕单元（排版参数由各 scene 落盘的 caption 决定，分段由脚本完成）：

- source {{venv_activate_q}} && python3 {{skill_root_q}}/scripts/align-narration.py \
    --mode subtitles \
    --transcript {{transcript_q}} \
    --narration {{narration_q}} \
    --offsets {{offsets_q}} \
    --script {{script_txt_q}} \
    --scene-config {{scene_config_q}} \
    --narration-audio {{narration_audio_q}} \
    --units-output {{subtitle_units_q}}

模板时间锚点（仅用到模板时需要）用同一次对齐取时间：在 {{template_cues_q}} 里按 cue 声明的形状（`scene_id` / `paragraphs` / `cues`，不需要完整的场景规划字段）声明要卡点的原句，再让 timing 模式定位它们：

- source {{venv_activate_q}} && python3 {{skill_root_q}}/scripts/align-narration.py \
    --mode timing \
    --transcript {{transcript_q}} \
    --narration {{narration_q}} \
    --offsets {{offsets_q}} \
    --script {{script_txt_q}} \
    --scene-plan {{template_cues_q}} \
    --timeline-output {{template_timeline_q}}

渲染前自查（全部通过再渲染）：

- cd {{composition_dir_q}} && npx hyperframes check
- source {{venv_activate_q}} && python3 {{skill_root_q}}/scripts/check-composition.py {{composition_dir_q}} \
    --scene-config {{scene_config_q}} \
    --design {{design_json_q}} \
    --subtitle-units {{subtitle_units_q}} \
    --output {{check_report_q}}
- 每个 scene 的中点截一张快照目检

## Required References

以下编号项按顺序阅读（模块目录是发现入口，不是采用清单；叠加顺序与冲突处理见 {{ws}}/references/delegation/conventions.md）：

{{required_references}}

**可选参考（可跳过）**：{{ws}}/modules/patterns/、{{ws}}/modules/motion.md、{{ws}}/modules/transitions/。查阅条件见基础指令第四部分；需要转场时再读目录与所选具体模块文档，不要求所有 scene 使用转场。

## Additional Instructions

{{additional_instructions}}
```
