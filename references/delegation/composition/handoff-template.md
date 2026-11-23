# composition-handoff 模板（Phase 8 — composition）

`scripts/prepare-handoff.py <ws> composition` 读取本文件里的 markdown 代码块，把 `{{name}}` 占位符换成实际值，写出 `{work_dir}/{topic_name}/composition-handoff.md`；同一次调用还会把委派包和 `modules/` 物化到工作区，但不预选 design、不预装字体；实际全片外观写入 `composition/design.json`。主 agent 不手写 handoff；有占位符没被替换时脚本报错退出。

五个小节固定为 `## Coding Agent`、`## Inputs`、`## Outputs`、`## Required References`、`## Additional Instructions`，标题不变；Additional Instructions 没有额外指令时写 `None`，但小节始终保留。

占位符取值（命令里的 skill 脚本用 skill 根目录的绝对路径，design.json 与 scene-config 都指向本阶段产物）：

| 占位符 | 取值 |
|---|---|
| `{{topic_name}}` / `{{ws}}` | 工作区目录名 / 工作区绝对路径（散文里用裸路径） |
| `{{ws_q}}` / `{{skill_root_q}}` | 上两者的 shell 引号版：**命令行里必须用这一对**（路径可能含空格），散文里不用 |
| `{{skill_root}}` | skill 根目录的绝对路径 |
| `{{coding_agent}}` / `{{coding_model_instruction}}` | 按 `inputs.json.delegation.composition` 与全局 `coding_agent` 解析的有效 agent / model；未指定 model 时模型说明为空 |
| `{{orientation}}` | 全片固定的画布朝向约束；全片 design 与逐场景 template / layout 不是准备前提，均由本阶段根据内容决定 |
| `{{material_catalog}}` | catalog 适用时（联网抓素材，或论文模式）：catalog 的路径；否则“无（无可用素材）” |
| `{{required_references}}` | 按叠加顺序编号：基础指令 → scene-config 数据契约 → `modules.md` → `designs.md` 目录与共享契约 → layout 目录（`layouts.md`，可借用的 preset）→ 模板目录（`templates.md`，按场景借用）→ 组件索引（`components.md`，按需读要挂载的组件文档）→ 动效模块目录（`motions.md`，按场景决定是否借用或改写某个动态模块）。具体 `<主题>.md` 与模块文档在选定后按需阅读。它们是发现入口，不是采用清单；全部指向工作区副本；patterns / transitions 单独列为可选参考 |
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
- {{timeline_q}}：Phase 7 不可变的段落与 cue 时间轴（提供真实语音锚点，本阶段只读不改）
- material-catalog.json：{{material_catalog}}
- 素材 ref 解析：图片 / 视频用 `<slug>/<id>`（图片 `local_path` 相对 `harvest_page/`），视频 clip 用 `<slug>/<video_id>:<start>-<end>` 并解析到相对工作区根的无音轨 `selected_clips[].clip_path`
- {{ws}}/scene-plan.json：叙事层场景规划（供参考 `intent` / `content_plan` / `material_candidates`；可自主合并 / 拆分视觉 scenes、决定逐场景 template / layout 与演绎方式，素材与动画约束守基础指令第一、四部分）
- {{ws}}/script.txt：显示稿（旁白与屏幕文字的文本来源，不能改）
- {{ws}}/inputs.json：orientation {{orientation}}（全片固定画布约束）；用户画面与风格要求见 Additional Instructions（`composition_requests`，按表述的作用范围应用）
- 字体目录：{{ws}}/composition/assets/fonts/（选定 design 后由你安装；不使用系统字体）

### 仅供工具读取

- {{transcript_q}}：本轮音频的 fresh transcript（词级时间戳；字幕唯一的时间来源）
- {{narration_q}} + {{offsets_q}}：朗读稿与逐字映射表（把时间还原到显示稿）

这些文件只作为下面字幕 / cue 对齐命令的参数；正常流程不阅读或复述其全文，也不拿它们重新理解或改写旁白。执行命令后读取生成的字幕单元与 cue 时间；仅在工具报错且必须诊断时读取相关句子或时间窗口，不重复加载全部文本。

## Outputs

写到工作区（{{ws}}/；按派发限定的批次与文件落盘，`storyboard.md` 验收前禁创建 `composition/compositions/` 文件）：

- {{design_json_q}}：全片 design 机器契约（`version` / `source` / `preset` / `tokens` / `min_font_px`，见 `modules/designs/designs.md`）
- {{scene_config_q}}：最终视觉场景机器配置（按「用户要求 → 特别匹配模块 → 即时生成」定方案并落盘完整 `regions` / `caption`）
- {{subtitle_units_q}}：最终字幕单元（由下方命令按落盘 `caption` 生成；保留已有用户编辑）
- {{ws}}/composition/storyboard.md：前置硬关卡 storyboard（组件与转场表、逐场景方案/区域/素材或动画说明、必用素材覆盖表；规划批写完即停）
- {{ws}}/composition/index.html + {{ws}}/composition/compositions/：HyperFrames 工程与分批子合成（`compositions/<scene>.{html,mjs}` 独立写盘）
- {{ws}}/composition/check-composition.json + {{ws}}/composition/renders/final.mp4：检查报告（`verdict == "pass"`）与成片（默认主会话执行）

先读旁白与叙事规划，按 `modules/designs/designs.md` 选定 design，初始化工程（若 `composition/` 不存在）、安装字体并写 {{design_json_q}}（不用系统字体；选定后将 `<design>` 换成实际字体包名）：

- cd {{ws_q}} && npx hyperframes init composition/（仅当 `composition/` 目录不存在时）
- bash {{skill_root_q}}/scripts/fonts-download.sh {{composition_dir_q}}/assets/fonts --theme {{ws_q}}/modules/designs/<design>

然后写 {{scene_config_q}}，再生成字幕单元（排版参数由各 scene 落盘的 caption 决定，分段由脚本完成）：

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

渲染前检查（主会话中心化执行，全部通过再渲染）：

- cd {{composition_dir_q}} && npx hyperframes check
- source {{venv_activate_q}} && python3 {{skill_root_q}}/scripts/check-composition.py {{composition_dir_q}} \
    --scene-config {{scene_config_q}} \
    --design {{design_json_q}} \
    --subtitle-units {{subtitle_units_q}} \
    --output {{check_report_q}}

## Required References

以下编号项按顺序阅读（模块目录是发现入口，不是采用清单；叠加顺序与冲突处理见 {{ws}}/references/delegation/conventions.md）：

{{required_references}}

**可选参考（可跳过）**：{{ws}}/modules/patterns/、{{ws}}/modules/transitions/。查阅条件见基础指令第四部分；借用画面形态时先看 `patterns.md` 再读匹配的 `<media|info>/<p>.md`，需要转场时先读 `transitions.md` 再读具体的 `<tr>/<tr>.md`，不要求所有 scene 使用转场。

## Additional Instructions

{{additional_instructions}}
```
