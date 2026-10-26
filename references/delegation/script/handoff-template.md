# script-handoff 模板（Phase 6 — 脚本与场景规划）

`scripts/prepare-handoff.py <ws> script` 读取本文件里的 markdown 代码块，把 `{{name}}` 占位符换成实际值，写出 `{work_dir}/{topic_name}/script-handoff.md`。主 agent 不手写 handoff；有占位符没被替换时脚本报错退出。

五个小节的标题固定不变；Additional Instructions 没有额外指令时写 `None`，但小节始终保留。

占位符取值（路径全是绝对路径；命令里的 skill 脚本用 skill 根目录的绝对路径）：

| 占位符 | 取值 |
|---|---|
| `{{topic_name}}` / `{{ws}}` | 工作区目录名 / 工作区绝对路径（散文里用裸路径） |
| `{{skill_root}}` | skill 根目录的绝对路径（散文里用） |
| `{{skill_root_q}}` / `{{venv_activate_q}}` | skill 根目录 / venv activate 脚本的 shell 引号版：**命令行里必须用引号版**（路径可能含空格） |
| `{{script_txt_q}}` / `{{lexicon_q}}` / `{{output_dir_q}}` | make-narration 命令里三条路径的 shell 引号版 |
| `{{coding_agent}}` | `inputs.json` 的 `coding_agent` |
| `{{duration}}` / `{{language}}` / `{{input_mode}}` / `{{template}}` | `inputs.json` 的对应字段（`template` 为 null 时写“无”） |
| `{{material_catalog}}` | `fetch_materials` 为真：catalog 的路径和 id 引用格式文档；否则“无” |
| `{{required_references}}` | 按叠加顺序编号：基础指令（工作区副本）→ 论文解析文档（论文模式才有，skill 侧绝对路径）→ 所选模板的旁白要求（skill 目录；未选模板或模板没有旁白要求则省略） |
| `{{additional_instructions}}` | 实际存在的 `narration-instructions.md`；没有写 `None` |

```markdown
# script-handoff — {{topic_name}}

## Coding Agent

{{coding_agent}}

## Inputs

- 工作区：{{ws}}/
- research-brief.md：{{ws}}/research-brief.md
- material-catalog.json：{{material_catalog}}
- inputs.json：{{ws}}/inputs.json（目标时长 {{duration}}、语言 {{language}}、input_mode {{input_mode}}、所选模板 {{template}}）

## Outputs

写到工作区根目录（{{ws}}/）：

- {{ws}}/script.txt：显示稿，段间空行分隔（schema 见基础指令）
- {{ws}}/tts-lexicon.json：词表，JSON map 显示形式 → 朗读形式
- {{ws}}/scene-plan.json：叙事层场景规划（schema 见基础指令；段落并集覆盖全部段落；素材引用必须存在于 catalog）
- {{ws}}/narration.txt + {{ws}}/narration-offsets.json：由脚本确定性生成，不要手写——
  source {{venv_activate_q}} && python3 {{skill_root_q}}/scripts/make-narration.py \
    --script {{script_txt_q}} --lexicon {{lexicon_q}} --output-dir {{output_dir_q}}

## Required References

按顺序阅读（叠加顺序与冲突处理见 {{ws}}/references/delegation/conventions.md）：

{{required_references}}

## Additional Instructions

{{additional_instructions}}
```
