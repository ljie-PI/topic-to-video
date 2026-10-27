# composition-handoff 模板（Phase 8 — composition）

`scripts/prepare-handoff.py <ws> composition` 读取本文件里的 markdown 代码块，把 `{{name}}` 占位符换成实际值，写出 `{work_dir}/{topic_name}/composition-handoff.md`；同一次调用还会把委派包和 `modules/`（不含 `examples/`）物化到工作区，并按所选 design 预置字体。主 agent 不手写 handoff；有占位符没被替换时脚本报错退出。

五个小节的标题固定不变；Additional Instructions 没有额外指令时写 `None`，但小节始终保留。

占位符取值（路径全是绝对路径；命令里的 skill 脚本用 skill 根目录的绝对路径，layout / design 指向工作区副本）：

| 占位符 | 取值 |
|---|---|
| `{{topic_name}}` / `{{ws}}` | 工作区目录名 / 工作区绝对路径（散文里用裸路径） |
| `{{ws_q}}` / `{{skill_root_q}}` | 上两者的 shell 引号版：**命令行里必须用这一对**（路径可能含空格），散文里不用 |
| `{{skill_root}}` | skill 根目录的绝对路径 |
| `{{coding_agent}}` | `inputs.json` 的 `coding_agent` |
| `{{design}}` / `{{layout}}` / `{{template}}` / `{{orientation}}` | `inputs.json` 的对应字段（`template` 为 null 时写“无”） |
| `{{material_catalog}}` | `fetch_materials` 为真：catalog 的路径；否则“无（无素材，画面用纯排版）” |
| `{{required_references}}` | 按叠加顺序编号：基础指令 → `modules.md` → design 文档 → layout 的 json 与文档 → 所选模板的文档（`template` 为 null 时省略）→ pattern / 组件目录（固定一句，按 storyboard 需要自行阅读）。全部指向工作区副本 |
| `{{additional_instructions}}` | 实际存在的 `composition-instructions.md` 和旧项目的 `style-prompt.md`；都没有写 `None` |

```markdown
# composition-handoff — {{topic_name}}

## Coding Agent

{{coding_agent}}

## Inputs

- 工作区：{{ws}}/
- {{ws}}/voice_clone/narration.mp3：生成的配音（唯一音频来源，不重生成 TTS）
- {{ws}}/transcribe/subtitle-units.json：字幕单元（text / begin_s / end_s，逐字使用）
- {{ws}}/transcribe/timeline.json：段落与 cue 时间轴（scene 切分与 cue 锚点）
- material-catalog.json：{{material_catalog}}
- 视频 clip：解析到 catalog 里 `selected_clips[].clip_path`（相对工作区根），不用视频的 `local_path`
- {{ws}}/scene-plan.json：叙事层场景规划（仅作参考，可合并 / 拆分 / 改选）
- {{ws}}/script.txt：显示稿（旁白与屏幕文字的文本来源，不能改）
- {{ws}}/inputs.json：design {{design}}、layout {{layout}}、template {{template}}、orientation {{orientation}}
- 字体目录：{{ws}}/composition/assets/fonts/（已按所选 design 预置，只用它）

## Outputs

写到工作区（{{ws}}/）：

- {{ws}}/composition/storyboard.md：storyboard，开头是「组件使用表」，每个 scene 写明 intent、所用的 content 区域、素材与 pattern 选择；偏离场景规划处写明理由
- {{ws}}/composition/index.html + {{ws}}/composition/compositions/：HyperFrames 工程与子合成
- {{ws}}/composition/check-composition.json：check-composition 的报告（下面命令的 `--output` 写出它；最后一次运行的 verdict 必须是 pass）
- {{ws}}/composition/renders/final.mp4：渲染产物

渲染前自查（全部通过再渲染）：

- cd {{composition_dir_q}} && npx hyperframes check
- source {{venv_activate_q}} && python3 {{skill_root_q}}/scripts/check-composition.py {{composition_dir_q}} \
    --layout {{layout_json_q}} \
    --design-doc {{design_doc_q}} \
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
