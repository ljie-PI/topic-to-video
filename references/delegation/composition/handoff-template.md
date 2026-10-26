# composition-handoff 模板（Phase 8 — composition）

主 agent 复制本模板为 `{work_dir}/{topic_name}/composition-handoff.md`，填好各节，然后按 `references/delegation/conventions.md` 派发：委派 prompt 只有一句话，让被委派的 agent 读本文件。

五个小节的标题固定不变；Additional Instructions 没有额外指令时写 `None`，但小节始终保留。

```markdown
# composition-handoff — <topic_name>

## Coding Agent

<委派目标，例如 claude-code（默认）；用户点名其他 agent 时写用户指定的>

## Inputs

- 工作区：{work_dir}/{topic_name}/
- voice_clone/narration.mp3：生成的配音（唯一音频来源，不重生成 TTS）
- transcribe/subtitle-units.json：字幕单元（text / begin_s / end_s，逐字使用）
- transcribe/timeline.json：段落与 cue 时间轴（scene 切分与 cue 锚点）
- material-catalog.json：<路径；fetch_materials = false 时写“无（无素材，画面用纯排版）”>
- scene-plan.json：叙事层场景规划（仅作参考，可合并 / 拆分 / 改选）
- script.txt：显示稿（旁白与屏幕文字的文本来源，不能改）
- inputs.json：design <design>、layout <layout>、template <template 或 无>、orientation <朝向>
- 字体目录：composition/assets/fonts/（主 agent 已按所选 design 预置，只用它）

## Outputs

写到工作区（{work_dir}/{topic_name}/）：

- composition/storyboard.md：storyboard，每个 scene 写明 intent、所用的 content 区域、素材与 pattern 选择；偏离场景规划处写明理由
- composition/index.html + composition/compositions/：HyperFrames 工程与子合成
- composition/renders/final.mp4：渲染产物

渲染前自查（全部通过再渲染）：

- npx hyperframes check
- python3 scripts/check-composition.py {work_dir}/{topic_name}/composition \
    --layout modules/layouts/<layout>.json \
    --design-doc modules/designs/<design>/<design>.md \
    --subtitle-units {work_dir}/{topic_name}/transcribe/subtitle-units.json \
    --timeline {work_dir}/{topic_name}/transcribe/timeline.json
- 每个 scene 的中点截一张快照目检

## Required References

按顺序阅读（叠加顺序与冲突处理见 references/delegation/conventions.md）：

1. references/delegation/composition/base-instructions.md（基础指令：输入契约、design、layout 区域、工作顺序）
2. modules/modules.md（模块库入口与组装约定）
3. modules/designs/<design>/<design>.md（所选 design；token 契约见 modules/designs/designs.md）
4. modules/layouts/<layout>.json + modules/layouts/<layout>.md（所选 layout 的区域定义）
5. <modules/templates/<template>/<template>.md 及其场景 / 组件文档；未选模板则写“无”>
6. <相关 pattern 文档：modules/patterns/<类>/<pattern>.md，按 storyboard 需要列；没有则写“无”>
7. <所用组件文档：modules/components/<组件>/<组件>.md；没有则写“无”>

## Additional Instructions

<实际存在的项目指令文件列表，例如 composition-instructions.md（旧项目的 style-prompt.md 视为其中一部分）；没有就写 None>
```
