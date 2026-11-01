# composition-handoff 模板（Phase 8 — composition）

`scripts/prepare-handoff.py <ws> composition` 读取本文件里的 markdown 代码块，把 `{{name}}` 占位符换成实际值，写出 `{work_dir}/{topic_name}/composition-handoff.md`；同一次调用还会把委派包和 `modules/`（不含 `examples/`）物化到工作区，并按所选 design 预置字体。主 agent 不手写 handoff；有占位符没被替换时脚本报错退出。

五个小节的标题固定不变；Additional Instructions 没有额外指令时写 `None`，但小节始终保留。

占位符取值（路径全是绝对路径；命令里的 skill 脚本用 skill 根目录的绝对路径，layout / design 指向工作区副本）：

| 占位符 | 取值 |
|---|---|
| `{{topic_name}}` / `{{ws}}` | 工作区目录名 / 工作区绝对路径（散文里用裸路径） |
| `{{ws_q}}` / `{{skill_root_q}}` | 上两者的 shell 引号版：**命令行里必须用这一对**（路径可能含空格），散文里不用 |
| `{{skill_root}}` | skill 根目录的绝对路径 |
| `{{coding_agent}}` / `{{coding_model_instruction}}` | 按 `inputs.json.delegation.composition` 与全局 `coding_agent` 解析的有效 agent / model；未指定 model 时模型说明为空 |
| `{{design}}` / `{{layout}}` / `{{template}}` / `{{orientation}}` | `inputs.json` 的对应字段（`template` 为 null 时写“无”） |
| `{{material_catalog}}` | `fetch_materials` 为真：catalog 的路径；否则“无（无素材，画面用纯排版）” |
| `{{required_references}}` | 按叠加顺序编号：基础指令 → `modules.md` → design 文档与 `<design>.json` 机器契约 → layout 的 json 与文档 → 所选模板的文档与 `supported_layouts` 声明（`template` 为 null 时省略）→ pattern / 组件目录（固定一句，按 storyboard 需要自行阅读）。全部指向工作区副本 |
| `{{additional_instructions}}` | `inputs.json` 的 `composition_requests` 逐条列出；没有写 `None` |
| `{{transcript_q}}` / `{{narration_q}}` / `{{offsets_q}}` / `{{script_txt_q}}` | 确定性字幕生成的四个上游 |
| `{{subtitle_units_q}}` | 字幕单元的最终位置：`{{ws}}/composition/assets/subtitle-units.json` |
| `{{template_cues_q}}` / `{{template_timeline_q}}` | 模板时间锚点的 cue 声明与它的时间文件 |
| `{{timeline_q}}` | Phase 7 的不可变时间轴 |
| `{{check_report_q}}` / `{{composition_dir_q}}` / `{{layout_json_q}}` / `{{design_json_q}}` | 自查与报告的路径 |

```markdown
# composition-handoff — {{topic_name}}

## Coding Agent

{{coding_agent}}
{{coding_model_instruction}}

## Inputs

- 工作区：{{ws}}/
- {{ws}}/voice_clone/narration.mp3：生成的配音（唯一音频来源，不重生成 TTS）
- {{transcript_q}}：本轮音频的 fresh transcript（词级时间戳；字幕唯一的时间来源）
- {{narration_q}} + {{offsets_q}}：朗读稿与逐字映射表（把时间还原到显示稿）
- {{timeline_q}}：Phase 7 的段落、cue 与语义节拍时间轴（scene 切分、cue 锚点与 beat 画面动作）；本阶段不修改它
- material-catalog.json：{{material_catalog}}
- 素材 ref：图片 / 视频用 `<slug>/<id>`，视频 clip 用 `<slug>/<video_id>:<start>-<end>`；按 slug 定位 entry 后，视频 clip 解析到该 entry 的 `selected_clips[].clip_path`（相对工作区根），不用视频的 `local_path`
- {{ws}}/scene-plan.json：叙事层场景规划（仅作参考，可合并 / 拆分 / 改选）
- {{ws}}/script.txt：显示稿（旁白与屏幕文字的文本来源，不能改）
- {{ws}}/inputs.json：design {{design}}、layout {{layout}}、template {{template}}、orientation {{orientation}}
- 字体目录：{{ws}}/composition/assets/fonts/（已按所选 design 预置，只用它）

## Outputs

写到工作区（{{ws}}/）：

- {{subtitle_units_q}}：最终字幕单元。**在本阶段按选定 layout 生成**（下面第一条命令），之后逐单元原样上屏；不要手改文本或边界
- {{ws}}/composition/storyboard.md：storyboard，开头是「组件使用表」，每个 scene 写明 intent、所用的 content 区域、素材与 pattern 选择；偏离场景规划处写明理由
- {{ws}}/composition/index.html + {{ws}}/composition/compositions/：HyperFrames 工程与子合成
- {{ws}}/composition/check-composition.json：check-composition 的报告（下面命令的 `--output` 写出它；最后一次运行的 verdict 必须是 pass）
- {{ws}}/composition/renders/final.mp4：渲染产物

先按最终 layout 生成字幕单元（排版参数由 layout 决定，分段由脚本完成）：

- source {{venv_activate_q}} && python3 {{skill_root_q}}/scripts/align-narration.py \
    --mode subtitles \
    --transcript {{transcript_q}} \
    --narration {{narration_q}} \
    --offsets {{offsets_q}} \
    --script {{script_txt_q}} \
    --layout {{layout_json_q}} \
    --units-output {{subtitle_units_q}}

模板时间锚点（仅本项目使用模板时需要）用同一次对齐取时间：在 {{template_cues_q}} 里按 scene-plan 的形状（`scene_id` / `paragraphs` / `cues`）声明要卡点的原句，再让 timing 模式定位它们：

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
    --layout {{layout_json_q}} \
    --design {{design_json_q}} \
    --subtitle-units {{subtitle_units_q}} \
    --timeline {{timeline_q}} \
    --output {{check_report_q}}
- 每个 scene 的中点截一张快照目检

## Required References

按顺序阅读（叠加顺序与冲突处理见 {{ws}}/references/delegation/conventions.md）：

{{required_references}}

## Additional Instructions

{{additional_instructions}}
```
