# Phase 输入边界与 Pi 委派调整计划

## 状态与基线

- 状态：已实施（本轮）。实现结果与偏差记在文末「8. 实施结果」；计划正文保留为决策依据。
- 历史状态：本文最初作为待实施计划编写；本轮按最新讨论更新后实施。
- 同步来源：`origin/main`（`git@github.com:ljie-PI/topic-to-video.git`），不是 `local` 回链。
- 首次同步：工作区干净，`main` 从 `f9cf3f8` 快进到 `54aa0967227d9e975f9d5769a1e7f488bc0e067b`。
- 本次同步：先更新本地计划，再 `git fetch origin main` 并快进到 `c7a5b204c53bb1c83dac15fb165ce69667414a35`；HEAD 与抓取后的 `origin/main` 一致。同步前后逐字比较确认本地计划未被覆盖，再补记本次基线与远端变化。
- 范围：落实已确认的默认值、阶段职责、指令传递、模板后移、Pi 默认委派与论文关键图要求；QA 已确认留在 Phase 1。字幕的现有布局依赖单列为技术核对项，不预设保守容量或新增字幕分层。
- 不提交、不推送、不把计划当作实施或落地授权。

## 1. 已确认的目标

| 事项 | 目标行为 |
| --- | --- |
| Phase 1 标题 | 只写“Phase 1 — 收集输入”，不把提问规则写进标题 |
| 提问 | 在正文说明：先提取已有信息，未指定项采用默认值；仅缺少不可默认的必要信息或要求有冲突时才问；需要问时一次问一个问题 |
| 时长 | 默认 3 分钟，用户明确指定时优先采用用户的值；仍保存为正的分钟数，不额外设上下限 |
| 竖屏 | “竖屏”未指定比例时采用 1080×1440（3:4）；只有明确指定 9:16 时采用 1080×1920 |
| 风格项 | Phase 1 的风格项只确定 `design`，不在这里实现旁白或画面覆盖 |
| 项目指令文件 | 全流程取消对三个旧项目指令文件的读取、创建、追加、复制和兼容回退 |
| 补充要求 | 不丢失用户的旁白与画面要求；Phase 6 / Phase 8 在委派前分别整理、传递各自的要求 |
| 模板 | Phase 8 才确定最终 `template`；Phase 6 不读取模板旁白要求，也不依赖模板字段 |
| 字幕说明 | Phase 1 只说明“模板、布局和字幕排版在 Phase 8 确定”，不展开配音、字幕容量或时间对齐流程 |
| QA | Phase 1 保留可选档位和默认 `standard` 的简短说明，不主动询问；完整执行流程放 Phase 9 |
| 委派 | 新项目默认 `coding_agent = "pi-coding-agent"`，使用可执行命令 `pi`，不再默认 Claude Code |
| 论文图表 | 方法、模型结构、关键实验结果等关键图必须全部纳入视频；关闭网络素材抓取不能省掉论文自身关键图 |

这里的三个旧文件是 `narration-instructions.md`、`composition-instructions.md`、`style-prompt.md`。本文和负向回归测试可以提及其名称，但执行代码和使用指南不再建立对它们的依赖；不另外引入同类替代 Markdown 文件。

## 2. 同步后需要注意的现状

1. 远端新增了 `references/pipeline-control.md`，以及每个阶段的“执行后自检”。保留这些规则，不能按旧版本覆盖整个阶段文档。
2. 远端把时长改成了“没有默认值、用户没说就问”。这与本轮明确要求冲突，按本轮要求统一改为 3 分钟。
3. 新的调度文档仍把长期要求写进旧项目指令文件，仍把模板问题归到 Phase 1；这两处也要修改。
4. Phase 1 的文档声称会校验 `layout`，但当前通用输入校验只要求该字段存在，没有校验布局可用性。应把最终视觉配置的校验放在 Phase 8，而不是仅修改描述。
5. `prepare-handoff.py` 的公共必填字段要求 `template` / `layout`；script handoff 会读模板旁白文档。必须一起修改 schema、handoff 与状态依赖。
6. GitHub 模板目前自带 presenter 布局，并依赖模板旁白锚点句；模板后移不能只删掉 Phase 1 的选择说明。
7. 编写初版时已执行本机 `pi --help` 和 `pi --version`：版本为 `1.0.1`，支持 `-p` / `--print`、`--`、`--model`。帮助中没有 Claude CLI 的 `--add-dir` 或 `--permission-mode`，不能照搬旧命令。
8. 编写初版时工作区没有 `.venv/bin/activate`。本轮不安装依赖、不创建环境、不调用 Pi 执行任务、不生成视频。
9. 本次同步到 `c7a5b20` 后，远端已删除 `references/gotchas.md`，把失败症状与恢复方式移入 Phase 2 / 3 / 4 / 5 / 7，并更新相应文档测试。Task 7 保留和核对这项已完成的迁移，不恢复共享 gotchas 文件。

关键现状位置：

- [Phase 1 当前默认值与职责](worktree://5a5c3e0d-8bdb-4b1c-b719-0062e34170b1/references/phases/01-gather-inputs.md#L11-L77)
- [通用输入必填字段](worktree://5a5c3e0d-8bdb-4b1c-b719-0062e34170b1/scripts/pipeline-status.py#L124-L135)
- [script handoff 的模板与项目指令读取](worktree://5a5c3e0d-8bdb-4b1c-b719-0062e34170b1/scripts/prepare-handoff.py#L272-L301)
- [Phase 7 当前布局读取与调用](worktree://5a5c3e0d-8bdb-4b1c-b719-0062e34170b1/scripts/voice-subtitles.py#L61-L75)
- [字幕对齐器已有的显式尺寸参数](worktree://5a5c3e0d-8bdb-4b1c-b719-0062e34170b1/scripts/align-narration.py#L17-L23)
- [状态戳对新增或移除上游键的处理](worktree://5a5c3e0d-8bdb-4b1c-b719-0062e34170b1/scripts/pipeline-status.py#L1600-L1606)

## 3. 推荐的数据与阶段契约

### 3.1 用现有 inputs.json 保存补充要求

推荐增加两个可选字符串列表，沿用现有 `material_search_requests` 的表达方式：

```json
{
  "narration_requests": ["语气更口语", "结尾不要 CTA"],
  "composition_requests": ["强调方法图与实验对比图"]
}
```

- 缺省与 `[]` 都表示没有额外要求；不要求用户填写，也不创建空的指令文件。
- 用户在早期已经提出的要求可以先保存，避免续跑或委派时丢失；具体整理和消费责任分别放在 Phase 6 / Phase 8。
- 处理新要求时保留无冲突的已有要求，更新被明确替代的要求，不盲目追加互相矛盾的句子。
- handoff 的五个固定小节保留；Additional Instructions 改为内联对应列表的文字，没有要求写 `None`。
- catalog 的 Additional Instructions 仍为 `None`。
- Phase 6 只依赖 `inputs.json#narration_requests`；Phase 8 只依赖 `inputs.json#composition_requests`。
- 指纹归一化时，缺省与空列表等价；不要把整个 `inputs.json` 当成两个阶段共同的构建依赖。
- 一次性修复意见仍走 `--redo` / `--finish`，不混入长期要求列表。审稿策略仍只由 `approval_gates` 表示。

### 3.2 让视觉选择只属于 Phase 8

- Phase 1 保存来源、模式、时长、语言、朝向、`design`、委派目标、素材策略和已提出的用户要求；不自动选择最终模板或布局。
- `template` / `layout` 不再是 Phase 1、catalog handoff、script handoff 的必填字段。旧输入中已有的值可以保留，不能据此让 Phase 6 读取模板指令。
- Phase 8 的准备步骤根据内容、朝向和用户画面要求确定高层 `template` / `layout`，然后更新 `inputs.json` 的这两个字段，再生成 composition handoff。
- 无模板时显式写 `template: null`，表示已决定使用通用画面；最终 `layout` 必须是可用的非空名称。
- 用户明确指定的朝向和 `design` 优先，模板不能暗中覆盖它们。现有 GitHub 模板只适配 presenter：竖屏时不能为了套模板改成横屏，可保留 GitHub design 并使用通用竖屏布局。
- 无模板时沿用通用布局规则：横屏通常 stage；明确要求主持人时 presenter；3:4 / 9:16 使用对应竖屏布局，不自行加入人物区。
- 在 composition handoff 准备与 Phase 8 现有校验入口校验模板存在性、布局文件、画布与朝向的一致性；失败留在 Phase 8，不回退 Phase 1。
- 不把可变的 `inputs.json` 整份增加为 Phase 8 的构建产物，避免其未改变的基础字段妨碍现有“所有产物已重建”判据。
- Phase 8 更新模板后不得反向使 Phase 6 过期；视觉字段变化与字幕现有依赖的关系按 Task 4 核对并验证，不能靠删除指纹依赖把旧产物假装成有效。

### 3.3 Phase 1 不展开字幕流程

Phase 1 的相关说明收紧为：

> 模板、布局和字幕排版在 Phase 8 确定。

这里只界定输入收集与画面阶段的职责，不描述后续配音或字幕对齐阶段，也不预先指定字幕宽度、字号、行数或容量。

- 撤回原先按朝向采用兼容布局最小字幕容量的方案；不为了提前固定预算而缩短横屏字幕。
- “时间对齐与字幕排版分离”、新增对齐产物或拆分字幕流水线也不是已确定方案，不纳入本次默认实施范围。
- 现有 `voice-subtitles.py` 仍会读取 `layout` 并调用确定性对齐器，这个真实依赖只在 Task 4 的技术核对清单中处理；从说明中移除阶段名称不等于已解除代码依赖。
- 优先复用现有脚本与字幕产物。若模板后移确实需要更大的字幕接口或产物变更，先列明最小必要改动与影响，单独确认，不把它隐含在 Phase 1 文档修改中。

### 3.4 模板不再规定旁白句式

- 从 script Required References、Inputs、场景规划示例和自检中移除模板旁白依赖。
- 模板目录中的旁白文档不再作为 Phase 6 的执行入口；其中纯叙事说明确有必要时并入 script 的通用内容规则，不能隐含绑定一个视觉模板。
- 保留通用语义 `cues` / `beats` 与已有时间戳能力；`cues` 来自内容锚点，不再描述为“模板要求的句子”。
- Phase 6 不输出确定的 `template_scene`。旧场景计划中该字段最多作为历史提示，不能强制 Phase 8 采用它。
- GitHub 的 `cue`、`nameAt`、`taglineAt`、`starsAt` 在 Phase 8 从已有显示稿、段落、词级时间戳中匹配；缺失的事实或句子不编造，不要求重写旁白来满足模板。

## 4. 实施任务与文件范围

### Task 1 — 收紧 Phase 1，统一默认值

修改：`references/phases/01-gather-inputs.md`、`tests/test_phase_docs.py`，按需核对 `SKILL.md`。

- [ ] 标题去掉括号说明，提问规则只放正文；不再逐项强制确认来源、语言、素材搜索。
- [ ] 字段表、执行步骤与执行后自检统一默认 3 分钟，删除“没有默认值、必须问”的规则；显式时长不被覆盖。
- [ ] 普通竖屏请求写 `orientation: "portrait-3:4"`；显式 9:16 写 `"portrait"`，保留旧枚举尺寸含义。
- [ ] 风格项只选 `design`，移除模板推导 design 的反向规则与项目文件处理。
- [ ] 移除 Phase 1 的空“护栏”小节，保留完成判据与执行后自检。
- [ ] 删除姊妹项目指令文件复制流程；只在用户确实要求复用时读取实际项目配置，并保留适用的 design / 用户要求。
- [ ] 更新自检：区分必填基础字段与可选要求，不能因模板尚未选择而判 Phase 1 未完成；续跑已有下游时修改输入仍按状态脚本处理，不宣称总是“没有下游”。
- [ ] Phase 1 只说明“模板、布局和字幕排版在 Phase 8 确定”，不提 Phase 7 或展开字幕容量、时间对齐流程。

### Task 2 — 取消旧文件依赖，改用要求列表

修改：`scripts/prepare-handoff.py`、`scripts/pipeline-status.py`、`references/delegation/conventions.md`、script / composition 的 `base-instructions.md` 与 `handoff-template.md`、`references/phases/06-script-scene-plan.md`、`references/phases/08-composition.md`、`references/pipeline-control.md`、`modules/designs/designs.md`、`tests/test_prepare_handoff.py`、`tests/test_pipeline_status.py`。

- [ ] 增加可选要求列表的类型校验与有效值归一化。
- [ ] 删除 `instruction_list` 对三个旧文件的发现逻辑及所有读取、追加、复制、覆盖说明。
- [ ] handoff 内联对应阶段要求；即使旧文件仍在磁盘，也完全不读取，且不改变它们。
- [ ] 更新状态上游：移除三个文件路径，按阶段加入两个要求字段。
- [ ] 修改调度文档的长期要求记录方式；Phase 6 / Phase 8 分别整理要求后再准备 handoff。
- [ ] 现有 design 的可选配色覆盖也从画面要求传递，不保留旧文件作为隐藏回退。
- [ ] 回归：没有要求、中文及多行要求、非法列表、旁白与画面要求隔离、修改要求后的最早 stale 阶段、缺省与 `[]` 等价。
- [ ] 旧状态戳没有新增要求键时，首次加入非空要求须由主 agent 明确登记相应阶段重做；保留远端的新增上游键兼容机制，不全局改成“新增键一律 stale”。

### Task 3 — 将模板与最终布局选择归到 Phase 8

修改：`scripts/pipeline-status.py`、`scripts/prepare-handoff.py`、Phase 1 / 6 / 8 文档、script / composition 委派包、`references/pipeline-control.md`、`modules/templates/templates.md`、`modules/templates/github/github.md` 与 `modules/templates/github/narration.md`、`tests/test_pipeline_status.py`、`tests/test_prepare_handoff.py`、`tests/test_phase_docs.py`、`tests/test_doc_references.py`。

- [ ] 公共输入与 handoff 必填字段拆成基础字段和 composition 专用选择；Phase 1 无 `template` / `layout` 也能通过。
- [ ] 删除 Phase 6 的 `inputs.json#template` 上游、模板旁白引用与 `template_scene` 生成要求。
- [ ] 更新 Phase 8 顺序：确定高层选择 → 合并写入输入 → 准备 handoff / 字体 → 委派组装。
- [ ] Phase 8 校验可用模板、布局与朝向；非法选择在写入物化副本或预置字体之前失败。
- [ ] 调度文档把模板和最终布局问题归到 Phase 8，不再归到 Phase 1。
- [ ] 移除模板旁白文档的旧执行契约；如删除文件，同步清理文档与测试引用。
- [ ] GitHub 模板不再要求预先写入固定旁白锚点；保留现有场景组件、Jay 演法和语义节拍映射。
- [ ] 回归：模板缺省不阻塞非 composition 步骤、旧输入已有模板、无模板 / 合法模板、非法模板、竖屏与 presenter 模板冲突、模板在 Phase 8 写入后 Phase 6 不 stale。

### Task 4 — 核对现有字幕布局依赖，限制实施范围

先核对：`scripts/voice-subtitles.py`、`scripts/align-narration.py`、`scripts/pipeline-status.py`、`references/phases/07-voice-subtitles.md`、composition 字幕契约、`tests/test_voice_subtitles.py`、`tests/test_pipeline_status.py`、`tests/test_align_narration.py`；只有必要时修改，不预先承诺重构这些文件。

- [ ] 核对 `layout` 的用途：输入必填、caption 规格、对齐调用、状态指纹，以及模板后移会影响哪些真实调用。
- [ ] 核对“不提前选最终 layout”与现有字幕命令的衔接，先给出最小必要改动；不能只删说明或状态上游就宣称问题已解决。
- [ ] 优先复用现有字幕产物、确定性对齐器和 `--align-only`，保持显示稿与音频时间来源，不让画面 agent 随意改写字幕文本。
- [ ] 不实施保守容量预算，不新增对齐产物，不默认拆分字幕流水线；确需改变字幕接口、产物或单元边界契约时，另列方案和影响后确认。
- [ ] 对核对后实际采用的最小改动补充调用和状态回归：新旧输入、布局变化、字幕边界与时间来源、音频复用；不把尚未选择的方案写成必然通过的验收路径。
- [ ] 保留原有重做、`--finish`、`--restamp` 和隔离恢复规则，不借本项放宽状态校验。

本项是实施前的技术核对项，不是已批准的字幕架构变更。

### Task 5 — 全流程默认 Pi

修改：`references/delegation/conventions.md`、Phase 1 / 5 / 6 / 8 文档、必要的 handoff 默认值说明、`scripts/prepare-handoff.py` 中相关有效值处理、`tests/test_prepare_handoff.py`、`tests/test_pipeline_status.py`、`tests/test_cut_clips.py`、`tests/test_voice_subtitles.py` 的默认 fixture。

- [ ] 默认标识为 `pi-coding-agent`；新项目输入显式写入该值，用户明确选择其他 agent 时保留覆盖能力。
- [ ] 派发说明使用 Pi 非交互模式，形态为 `(cd <ws> && pi -p -- "<dispatch_prompt>")`；实际目录和 prompt 使用正确 shell 引用。
- [ ] 保留主 agent 派发、仓库脚本只准备 handoff 的分工，不新增自动 shell 调用 agent 的 Python 启动器。
- [ ] 不假定 Pi 内置 sub-agent 工具；只有环境实际提供对应委派能力时才使用，否则按 Pi CLI 路径。
- [ ] 删除默认 Claude CLI、`--add-dir`、`--permission-mode` 路径；缺少 Pi 时明确报告，不静默退回 Claude。
- [ ] 模型、认证与权限由现有环境或用户明确配置，不能把秘钥写进 handoff 或项目文件。
- [ ] 仅替换委派目标和默认 fixture；文章 URL、示例主题中的 Claude Code 产品名称不做无关替换。
- [ ] 回归默认 Pi 与用户覆盖、带空格工作目录、派发 prompt 不被 shell 拆分、脚本不自行调用 Pi。

### Task 6 — 让论文关键图要求贯穿到成片

修改：Phase 1 / 2 / 3 / 5 / 6 / 8 / 9 中相关论文说明、catalog / script / composition 委派包、`scripts/pipeline-status.py`、`tests/test_pipeline_status.py`、`tests/test_phase_docs.py`，按需补充 `tests/test_cut_clips.py` 的字段保留回归。

- [ ] 新规则只写：“方法、模型结构、关键实验结果等关键图必须全部纳入视频；关闭网络素材抓取不能省掉论文自身关键图。”不添加本轮用户要求省略的反面说明。
- [ ] Phase 2 保证关键图可提取、caption 可追溯；解析缺失时回补或报告，不凭空补图。
- [ ] Phase 3 / Phase 5 根据论文内容识别关键图，catalog 明确保留关键图，不能因一般素材评分过滤而漏掉。
- [ ] 推荐在 catalog 增加可选 `required_material_refs` 列表（使用已有 `<slug>/<id>` 格式），记录必须出现的图表；标准模式可缺省，论文模式由 catalog agent 明确填写。
- [ ] 状态脚本检查必用引用可解析、无重复；Phase 6 的候选引用并集覆盖清单，但明确候选覆盖不等于已经出现在成片里。
- [ ] Phase 8 storyboard 列出必用引用 → 展示 scene / 时间的覆盖表；执行后自检和 Phase 9 核对实际画面，不能仅凭候选列表声称图都用了。
- [ ] “哪些图属于关键图”以及“实际展示是否可读”仍由 agent 判断，确定性校验只保证声明的清单与引用覆盖；不冒充机器已理解全部论文。
- [ ] 回归 paper + `fetch_materials=false`、关键图引用缺失 / 错误、候选覆盖不足、重复引用清单、标准模式不受新增可选字段影响；保留 caption 直用和缺 caption 的 VLM 路径。

### Task 7 — 核对阶段执行约束，保留 QA 简短说明

远端已完成：共享 `gotchas.md` 的恢复说明已移入所属阶段，原文件已删除。本计划不重新迁移或恢复它。

核对与必要修改：相关 phase 文档、`tests/test_guardrail_docs.py`、`tests/test_phase_docs.py`。

- [ ] 执行约束 / 护栏是当前必须遵守的规则；完成判据是输出合格条件；执行后自检是事实、叙事、视觉匹配等内容判断。
- [ ] 失败症状与恢复方法保留在所属 phase，执行者读取当前文档就能处理故障；不重新建立共享 gotchas 文件或编号引用。
- [ ] 不全项目机械重命名“护栏”；仅修复本次涉及的空小节或表述，保留最新远端的阶段恢复规则及防回归测试。
- [ ] Phase 1 保留 `qa_level` 的简短说明：可选 `quick` / `standard` / `strict`，默认 `standard`，仅按用户明确要求覆盖，不主动询问；完整执行流程放 Phase 9，不改变档位行为。

### Task 8 — 回归验证与范围审查

- [ ] 先添加失败用例，再实现对应任务；不要删除测试来掩盖已移除依赖带来的问题。
- [ ] 移除旧正向依赖测试，改成“即使文件存在也被忽略”的负向回归；默认 fixture 改为 Pi，显式用户覆盖测试继续保留。
- [ ] 完整保留已同步远端的 redo、finish、审稿、stamps 损坏隔离、原子恢复及阶段故障恢复用例。
- [ ] 检查旧项目：已有时长、朝向、design、明确的委派目标不被默认值覆盖；不自动读取或迁移已取消依赖的旧指令文件。
- [ ] 检查物化副本：已存在的委派包默认不覆盖，旧副本可能仍含旧指令。对受本次变更影响的项目明确使用 `prepare-handoff.py --refresh` 更新对应包；不默认覆盖用户编辑过的其他副本。
- [ ] 确认本轮最终差异仅包含批准范围；不顺手修改 TTS 后端、ASR 规则、字体体系、动画组件或通用状态恢复机制。

## 5. QA 档位：已确认保留在 Phase 1

当前实现的档位如下，默认仍为 `standard`：

| 档位 | 渲染前检查 | 渲染后确定性检查 | contact sheet | agent 视觉检查 |
| --- | --- | --- | --- | --- |
| `quick` | 做 | 做 | 每 scene 中点帧，照常交给用户 | 不做 |
| `standard` | 做 | 做 | 每 scene 中点帧 | 主 agent 逐张看 sheet：渲染完整、画面与旁白相符、符合 design、明显空洞或错位四项 |
| `strict` | 做 | 做 | standard + 每 scene 入场帧 + 每切点前 / 中 / 后三帧 | 与 standard 相同四项，增加时间采样 |

每张 sheet 放 4 帧。以 40 个 scene、39 个内部切点为例：standard 约 10 张 sheet；strict 按定义约 197 帧 / 50 张 sheet；quick 生成约 10 张 sheet，但没有 agent 视觉检查。实际数量以抽帧脚本去重、边界处理后的输出为准。strict 不是观看完整视频，也没有增加其他视觉评价项。

用户已确认 QA 可以留在 Phase 1。实施时保留可选档位、默认 `standard` 与 Phase 9 引用的简短说明，不主动询问；完整流程只放 Phase 9，不删除档位、不改变默认值。

## 6. 实施时应运行的验证

以下是未来实施检查，不是本轮已经运行的测试。先准备项目 `.venv` 和对应测试依赖，再在 skill 根目录激活环境，使用 `python3`。

### 聚焦验证

```bash
source .venv/bin/activate && python3 -m pytest \
  tests/test_pipeline_status.py \
  tests/test_prepare_handoff.py \
  tests/test_voice_subtitles.py \
  tests/test_align_narration.py \
  tests/test_phase_docs.py \
  tests/test_guardrail_docs.py \
  tests/test_doc_references.py \
  tests/test_design_docs.py \
  tests/test_design_contract.py \
  tests/test_cut_clips.py -q
```

### 完整回归

```bash
source .venv/bin/activate && python3 -m pytest -q
```

依赖不可用或有跳过项时明确报告，不把未执行的 real TTS / ASR / HyperFrames / Pi 委派当作已验证。

### 真实工作流验收

1. 在新测试工作区验证 Phase 1 不要求提前选择模板，并在 Phase 8 完成视觉选择。模板写入后不回退旁白阶段；涉及字幕命令的布局衔接按 Task 4 核对后确定的最小改动验收，不默认字幕依赖已经消失。
2. 分别验证默认 3:4 竖屏、显式 9:16、横屏 stage、横屏 presenter 的字幕与渲染前检查。
3. 在认证和环境允许时，使用实际 `pi -p -- "<dispatch_prompt>"` 验证 handoff 可读、输出路径正确，及工作区外的 skill 绝对路径可访问；本机 `--help` 成功不能代替此项。
4. 用包含方法图、结构图和关键结果图的论文验证必用清单、场景规划和成片覆盖，包含 `fetch_materials=false` 路径。需要外部服务或真实素材时说明前置条件，不在普通单元测试里自动发送代码或私有资料。
5. 修改旁白要求从 Phase 6 重做；修改画面要求 / 模板从 Phase 8 重做。布局变化对现有字幕产物的影响按 Task 4 核对并验证，不靠隐藏依赖过关；审稿和 QA 策略按原规则处理。
6. 检查使用指南、运行代码已没有旧文件依赖和默认 Claude 派发说明；计划与负向测试中的名称不算运行依赖。
7. 运行 `git diff --check`，核对文档引用、阶段产物表与状态检查仍一致。

## 7. 完成判据

- 所有已确认目标均有对应的实现、使用说明和回归用例；QA 已确认保留，字幕现有布局依赖的技术核对与任何新增架构提议明确区分。
- Phase 1 不强制访谈，不在标题写提问规则，不提前选择模板或最终布局。
- 三个旧指令文件不再影响 handoff 或阶段状态，用户要求经现有 JSON 输入和内联 handoff 可靠传递。
- Phase 1 不展开后续字幕流程；模板在 Phase 8 确定不会反向使 Phase 6 过期。现有字幕布局依赖已核对，并通过实际调用和状态回归验证；未另行确认的字幕分层或新增产物不在实施范围。
- 新项目全流程默认 Pi，显式 agent 覆盖仍有效；无静默 Claude 回退。
- 论文关键图清单可追溯，并在实际成片中核对覆盖，不把格式通过冒充内容合格。
- 新旧工作区的续跑、审稿、重做与状态隔离规则不被破坏。
- 报告实际跑过的验证、未跑的真实服务流程及其原因；完成实现不等于获得提交、推送或合并授权。

## 8. 实施结果

### 8.1 已落地的改动

| 计划项 | 实现 |
| --- | --- |
| Task 1 | Phase 1 标题只留阶段名；默认时长改为 3 分钟；默认竖屏 3:4、显式 9:16 才用 1080×1920；模板不再由本阶段选；新增 `narration_requests` / `composition_requests` 两个字段行；QA 只留简短的档位与默认值行；护栏写实规则（不再为空）；删掉姊妹项目复制指令文件的流程 |
| Task 2 | `pipeline-status.py` 与 `prepare-handoff.py` 不再读三个旧指令文件，改为从 `inputs.json` 的两个要求列表内联到 handoff 的 Additional Instructions；阶段上游改为两个要求字段 |
| Task 3 | `template` 从必填输入中移除（仍是可选字段，存在时必须是 null 或普通名字）；Phase 6 不再读模板或 `narration.md`，`modules/templates/github/narration.md` 删除；Phase 8 新增 8.0 选模板步骤，再物化与派发 |
| Task 4 | 只做核对：`layout` 仍属 Phase 1，`voice-subtitles.py` 与字幕流程未改（详见 8.2） |
| Task 5 | 默认 `coding_agent = pi-coding-agent`；派发改为 `cd <ws> && pi -p -- "<prompt>"`，删掉 Claude CLI 的 `--add-dir` / `--permission-mode` 路径 |
| Task 6 | catalog 新增可选 `required_material_refs`；状态脚本校验可解析、不重复，并要求 Phase 6 的 `material_candidates` 覆盖它；Phase 2 / 5 / 6 / 8 / 9 与 catalog / composition 委派包各写一段关键图规则 |
| Task 7 | Phase 1 的护栏不再是“无”；远端已将恢复规则搬入各阶段，本计划未重建 gotchas |
| Task 8 | 新增 42 个回归用例；全套 1006 通过 |

### 8.2 与计划的两处偏差

1. **`layout` 没有移到 Phase 8，Task 4 未改字幕代码。** 核对结果：`voice-subtitles.py` 在 Phase 7 读 `layout` 取字幕容量，而 Phase 7 必在 Phase 8 之前。把 layout 一起后移就必须在 Phase 7 先定一个容量（即被否决的保守容量），或拆分字幕流水线（未经确认）。取最小改动：`layout` 留在 Phase 1（由朝向与“要不要主持人”决定），只把 `template` 后移。这样 Phase 7 一行不改，也没有任何地方新增字幕容量决策，Phase 1 文档也不提 Phase 7。
2. **Phase 1 的护栏改为写实规则，而不是删小节。** 原有测试要求每个阶段都有「护栏」小节、且紧跟「下一步」。删掉会让文档结构不统一；空写“无”又对不上新增的“不要逐项追问 / 要求要落地 / 不提前定模板”。改为三条实际规则，并同步放宽该测试只对 Phase 9 期望“无”。

### 8.3 实施中补的一处确定性校验

计划里写“在 Phase 8 校验可用模板、布局与朝向”。实现时把可判定的部分做成脚本检查：`prepare-handoff.py composition` 读 layout 的 `canvas`，与 `inputs.json` 的 `orientation` 比对，方向不符就 exit 1，且发生在物化副本与预置字体之前。“这个模板是否适合该朝向”仍留给 agent 判断（模板文档没有机器可读的 layout 声明，不在本次扩展）。

### 8.4 一处测试覆盖变薄

原 `test_an_unreadable_optional_upstream_does_not_abort_the_scan` 依赖 `style-prompt.md` 这个可选*文件*上游。改动后唯一剩下的可选文件上游是 `material-catalog.json`，而它同时是 Phase 5 的产物——把它弄成不可读会先在产物检查里失败，测不到“上游不可读不中断扫描”这个点。该用例已删除；未新增替代手段（告警而非断言）。

### 8.5 实际跑过的验证

- 基线：改动前 `.venv` 下 `python3 -m pytest -q` → 964 passed。
- 建成项目 `.venv`（当时不存在）并安装 `requirements-dev.txt`；之后所有测试都用 `.venv/bin/python`。
- 最终：`python3 -m pytest -q` → 1006 passed。
- 端到端手工跑一遍：无 `template` 的 `inputs.json` → Phase 1、3、6、7 依次完成（fake TTS 后端）→ Phase 8 选 `github` 模板 → `stale_phases` 仍为空，Phase 6 / 7 保持 completed；`prepare-handoff.py composition` 生成 handoff，Additional Instructions 内联 `composition_requests`，并预置 122 个字体文件。
- 反向验证：把 layout 改成与朝向不符的 `presenter` 后，`prepare-handoff.py composition` exit 1，且未写 handoff。
- 未验证：真实 Pi 派发（只核过 `pi --help` / `pi --version` 与命令形态）、真实 TTS / ASR、HyperFrames 渲染、真实论文的 `required_material_refs` 端到端（需要外部素材与服务）。
