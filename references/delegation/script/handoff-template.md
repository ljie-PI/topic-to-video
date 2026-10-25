# script-handoff 模板（Phase 6 — 脚本与场景规划）

主 agent 复制本模板为 `{work_dir}/{topic_name}/script-handoff.md`，填好各节，然后按 `references/delegation/conventions.md` 派发：委派 prompt 只有一句话，让被委派的 agent 读本文件。

五个小节的标题固定不变；Additional Instructions 没有额外指令时写 `None`，但小节始终保留。

```markdown
# script-handoff — <topic_name>

## Coding Agent

<委派目标，例如 claude-code（默认）；用户点名其他 agent 时写用户指定的>

## Inputs

- 工作区：{work_dir}/{topic_name}/
- research-brief.md：<是否存在及路径；否写“无（fetch_materials = false 或纯主题）”>
- material-catalog.json：<是否存在及路径；素材 id 引用格式的定义见 references/phases/05-material-catalog.md>
- inputs.json：目标时长 <duration>、语言 <language>、input_mode <mode>、所选模板 <template 或 无>

## Outputs

写到工作区根目录（{work_dir}/{topic_name}/）：

- script.txt：显示稿，段间空行分隔（schema 见基础指令）
- tts-lexicon.json：词表，JSON map 显示形式 → 朗读形式
- scene-plan.json：叙事层场景规划（schema 见基础指令；段落并集覆盖全部段落；素材引用必须存在于 catalog）
- narration.txt + narration-offsets.json：由脚本确定性生成，不要手写——
  python3 scripts/make-narration.py --script {work_dir}/{topic_name}/script.txt \
    --lexicon {work_dir}/{topic_name}/tts-lexicon.json --output-dir {work_dir}/{topic_name}/

## Required References

按顺序阅读（叠加顺序与冲突处理见 references/delegation/conventions.md）：

1. references/delegation/script/base-instructions.md（基础指令：叙事结构、写法要求、产物 schema）
2. <modules/templates/<template>/narration.md；未选模板则写“无”>
3. <narration-instructions.md；不存在则写“无”>

## Additional Instructions

<实际存在的项目指令文件列表，例如 narration-instructions.md；没有就写 None>
```
