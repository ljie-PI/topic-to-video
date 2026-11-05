# catalog-handoff 模板（Phase 5 — 素材理解与筛选）

`scripts/prepare-handoff.py <ws> catalog` 读取本文件里的 markdown 代码块，把 `{{name}}` 占位符换成实际值，写出 `{work_dir}/{topic_name}/catalog-handoff.md`；同一次调用还会把委派包物化到工作区，不复制 modules，也不安装字体。主 agent 不手写 handoff；有占位符没被替换时脚本报错退出。

五个小节的标题固定不变；Additional Instructions 列出实际存在的 `catalog-instructions.md`（用户素材要求），没有时写 `None`。

占位符取值（路径全是绝对路径；命令里的 skill 脚本用 skill 根目录的绝对路径）：

| 占位符 | 取值 |
|---|---|
| `{{topic_name}}` / `{{ws}}` | 工作区目录名 / 工作区绝对路径（散文里用裸路径） |
| `{{skill_root}}` | skill 根目录的绝对路径（散文里用） |
| `{{skill_root_q}}` / `{{venv_activate_q}}` / `{{ws_q}}` | skill 根目录 / venv activate 脚本 / 工作区的 shell 引号版：**命令行里必须用引号版**（路径可能含空格） |
| `{{coding_agent}}` / `{{coding_model_instruction}}` | 按 `inputs.json.delegation.catalog` 与全局 `coding_agent` 解析的有效 agent / model；未指定 model 时模型说明为空 |
| `{{required_references}}` | 基础指令（工作区副本） |
| `{{additional_instructions}}` | 实际存在的 `catalog-instructions.md`；没有写 `None` |

```markdown
# catalog-handoff — {{topic_name}}

## Coding Agent

{{coding_agent}}
{{coding_model_instruction}}

## Inputs

- 工作区：{{ws}}/
- harvest_page/manifest.json：{{ws}}/harvest_page/manifest.json（素材清单；按其路径读取实际图片、视频、字幕、页面摘录与论文 metadata）
- research-brief.md：{{ws}}/research-brief.md（调研结果与证据）
- vision_analyze/topic-context.txt：{{ws}}/vision_analyze/topic-context.txt（主 agent 已写好的话题 context 摘要）
- inputs.json：{{ws}}/inputs.json（用户来源输入、目标时长、语言、朝向与 agent / model 要求；用户素材原话见 Additional Instructions）

## Outputs

写到工作区根目录（{{ws}}/）：

- {{ws}}/material-catalog.json：每条 harvest entry 对应一条 catalog entry（schema 见基础指令）
- {{ws}}/extract_frames/：视频与滚动录像的抽帧结果，含局部细看的 4×4 拼图及帧时间映射（拼接命令见基础指令）
- {{ws}}/vision_analyze/：视觉分析结果与话题 context 摘要
- {{ws}}/clips/：无音轨片段文件；所有 entry 写入 catalog 后运行一次——
  source {{venv_activate_q}} && python3 {{skill_root_q}}/scripts/cut-clips.py {{ws_q}}

## Required References

按顺序阅读（叠加顺序与冲突处理见 {{ws}}/references/delegation/conventions.md）：

{{required_references}}

## Additional Instructions

{{additional_instructions}}
```
