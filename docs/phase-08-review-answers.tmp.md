# Phase 08 批注逐条答复（临时）

> 历史状态：本文件的 15 条批注已按 `docs/plans/phase08-composition-and-delegation-refactor.md` 由 #147–#153 实施完毕。本文保留为当时的批注与答复记录；文中以答复时行号为准的“应删除 / 建议改为”描述的是旧状态，现行指令以仓库内 references/ 与 modules/ 文档为准，不要按本文执行操作。

核对日期：2026-11-07。对象：`references/phases/08-composition.md` 及其实际调用的文档、脚本和模块。

**本轮只新增这份答复文件，不修改现有阶段文档、代码或测试，也没有执行删除、下载、卸载或渲染。** 下文的“应删除”“建议改为”都是对批注的答复和待实施范围，不表示已经改完。第 3 条按你的要求只解释，不提出改动。

下面按你给出的 15 条批注原顺序回答；路径均相对仓库根目录，行号以本轮读取的文件为准。

## 1. 第 10 行：`script.txt` 是做什么的，没有说明

它是 **Phase 6 产出的显示稿**，不是直接送给 TTS 的朗读稿。

- `script.txt` 保留品牌、数字和符号的显示写法，例如 `NVIDIA`、`2026`、`5%`。
- `narration.txt` 是按词表转换后的朗读写法，例如“英伟达”“二零二六”“百分之五”。
- Phase 8 用显示稿生成字幕、确定屏幕文字，以及为模板摘取需要卡点的原句；通过偏移表把朗读时间映射回显示文字。

所以输入列表里只写文件名确实不够。可补成“`script.txt`：显示稿，字幕、屏幕文字和模板 cue 的文本来源”。这是说明草案，本轮没有改原文。

依据：`references/delegation/script/base-instructions.md:74-90`、`references/delegation/composition/handoff-template.md:43`、`references/delegation/composition/base-instructions.md:44-48`。

## 2. 第 14 行：模板与 layout 在本阶段确定，这一句没有必要

这句话原本是在强调职责划分：视觉配置不应该倒过来影响写稿和配音。但后面的 8.0、8.3 已经讲了选择发生在哪里，重复放在输入列表后没有提供新的执行信息。

**同意这里删除。** 如果还需要说明职责划分，只在实际选择步骤或统一工作流说明里保留一次即可；不需要在输入、护栏和执行步骤里反复强调。

另外，删除指纹机制后，“不会让上游重做”应表达为工作流的职责规则，不能继续写成脚本自动判断的保证。

## 3. 第 30 行：`composition/storyboard.md` 是做什么用的（只回答，不改动）

它是 **Phase 8 的画面实施说明**，不是另写一份旁白。

当前要求它记录：

- 全片使用哪些组件、参数是什么、数据从哪里来；
- 每个视觉场景展示什么素材、怎么构图、信息怎样展开、动效怎样安排；
- 使用哪些 layout 内容区域，为什么选这个模板；
- 如偏离 Phase 6 场景计划，偏离的原因；
- 必用素材在哪个 scene、什么时间实际展示，方便主 agent 验收。

用途是让画面设计落盘，供 coding agent 实现、主 agent 检查以及后续定向修复。它本身不参与生成配音；当前 `check-composition.py` 也不读取它。`pipeline-status.py` 的“非空”检查只证明文档存在，不证明画面设计质量合格。

依据：`references/delegation/composition/base-instructions.md:54-64`、`scripts/pipeline-status.py:1169-1179,1405-1411`。**本条仅解释，不改它的要求。**

## 4. 第 33 行：删除指纹检查，其他步骤类似行为及调用也都删除

当前这套机制是为了阻止“上游或画面改过，却继续接受旧报告、旧成片”。但它不负责判断画面好不好，还引入了哈希、缓存、打戳、过期、重新接受产物等额外流程。

**按你的要求，应清理全流程的内容指纹与构建新鲜度追踪，而不只是删掉这一句。** 查到的实际范围如下：

| 位置 | 当前行为 | 待清理范围 |
| --- | --- | --- |
| `scripts/check-composition.py:58,678` | 计算源文件指纹，写入报告的 `sources_sha256` | 删除导入、计算、输出字段和对应说明；保留越界、溢出、资源、字体、字幕等实际检查 |
| `scripts/composition_hash.py` | 枚举 composition 源文件并计算聚合哈希 | `visible_files()` 还被目录产物检查使用，应先迁出这个非指纹工具函数，再删除整个专用指纹文件及其导入 |
| `scripts/pipeline-status.py:1188-1225` 的 `check_composition_report()` | 要求报告有哈希、比对当前源文件、比较成片与源文件修改时间 | 删除哈希验收及新鲜度比对；保留 JSON 可读、报告结论通过和成片存在等检查 |
| `scripts/pipeline-status.py:1169-1185` | `composition_source_paths()`、`newest_composition_source()` 查找最新源文件 | 随构建新鲜度检查清理；不以另一个时间戳机制替代指纹 |
| `scripts/pipeline-status.py:1443-1606,1706-1857` | `FpCache`、`Fingerprinter`、`Stamps`、`canonical_inputs_field()`、`text_sha256()`、`file_sha256()`、`changed_upstream_keys()`、`stale_upstream()`、`reconcile_stamp()` | 删除专用实现、常量及所有调用，删除为哈希服务的阶段上游声明 |
| `scripts/pipeline-status.py:1860-2140` | 扫描、`--finish`、`--restamp`、主入口调用上述机制 | 删除自动 `stale`、`changed_upstream`、`stamps_reset`、打戳隔离及恢复流程；`--restamp` 不再有用途；保留显式重做和基本验收 |
| `scripts/pipeline-status.py:1609-1638,1910-1923,2017-2034` | 用户审稿确认绑定产物哈希，文件变化后确认失效 | 同属指纹使用，也应清理哈希绑定；**审稿 gate 本身不能因此被自动取消或自动批准** |
| `scripts/make-narration.py:183-184` | 偏移表写入 `script_sha256`、`narration_sha256` | 删除这两个字段的生成；保留朗读稿生成和字符偏移表 |
| `scripts/video_contract.py:329-383` | `OFFSETS_HASH_SOURCES`、`text_sha256()` 及 `offsets_problem()` 中的哈希要求 | 删除内容哈希契约和比对；保留版本、长度、segments 等实际数据要求 |
| `scripts/align-narration.py:395`、`scripts/pipeline-status.py:974` | 调用公共偏移表校验，间接执行哈希检查 | 随公共契约更新；不删除对齐脚本或整个偏移表校验 |

还要同步清理：

- 文档：`SKILL.md`、`references/pipeline-control.md`、Phase 1 / 5 / 6 / 7 / 8 / 9 中的自动失效、哈希契约和打戳说明。
- 历史计划：`docs/plans/pr-review-fixes-and-remove-legacy-compat.md`、`docs/plans/phase-inputs-and-pi-delegation.md`、`docs/plans/script-hooks-and-scene-content-plan.md`、`docs/plans/2026-11-01-phase7-instructions-and-recovery.md`、`docs/plans/phase4-material-harvest-improvements.md` 的相关说明，至少不能继续作为现行要求。
- 测试：`tests/test_pipeline_status.py`、`tests/test_video_contract.py`、`tests/test_align_narration.py`、`tests/test_pr_review_regressions.py` 中对应的夹具、导入和断言。
- 不再读写 `.pipeline/stamps.json`、`.pipeline/fpcache.json` 及打戳隔离文件；不能因此删除保存用户审稿和重做请求的其他状态文件。

**删除后的变化要明确：** 修改上游不会再靠哈希自动发现并触发下游重做，也无法靠指纹证明报告对应最新画面。需要重做时由用户或执行 agent 显式登记；改过画面后的检查、重新渲染仍是执行流程，不再由文件指纹或修改时间充当验收证据。审稿内容变化时也应显式撤销旧确认，而不是继续承诺自动识别。

我把“类似行为”理解为也包括第 34 行按源文件修改时间判定成片是否旧的检查；它虽不是哈希，本质上仍是构建新鲜度追踪。

不应机械删除所有 `hash`、`mtime` 或 `timestamp`：

- `scripts/fonts-download.sh:238` 用 URL 哈希给字体命名、`scripts/harvest_manifest.py:422` 用 URL 哈希生成标识，不是在检查产物是否过期。
- `scripts/harvest-pages.py`、`scripts/video-download.py` 用修改时间寻找下载或录制结果，不是阶段指纹验收。
- 语音时间戳、字幕起止时间、音画时长检查是同步所必需的，与这里的指纹机制不同。

以上只是清理范围答复，本轮没有删任何实现。

## 5. 第 53 行：为什么字体归 HyperFrames，字体不是本 skill 自己的吗

**是的，字体来源是本项目 / 本 skill，不是 HyperFrames。这里的表述混淆了资源来源、执行者和工具。**

实际分工是：

1. design JSON 声明字体族和字体清单；
2. `resources/fonts/<design>/` 保存主题 CSS，`resources/fonts/files/` 保存共用 WOFF2；
3. `scripts/fonts-download.sh` 准备字体，`prepare-handoff.py` 把它们安装到工程；
4. composition agent 在画面代码中引入 CSS、使用 design 的字体变量；
5. HyperFrames 只是当前的画面运行 / 渲染工具。

所以更准确的职责说明是“composition agent 负责在画面中加载和使用本 skill 提供的字体”。不应该说“字体归 HyperFrames”，更不应该让这个措辞阻碍换渲染工具。

依据：`scripts/fonts-download.sh:13-22,150-176`、`scripts/prepare-handoff.py:184-217`、`modules/modules.md:81-84`。

## 6. 第 55 行：为什么不能手改字幕，我有时就是想手改

这条禁令的原意是防止 agent 擅自拆并字幕，破坏文本和语音时间的对应关系。但它写成绝对禁止，**把用户主动编辑也一并禁止了，范围过大。**

应区分两件事：默认让脚本生成初稿，用户明确要求时允许手工修改。这不是技术上做不到，而是当前指令禁止了它。

适合改成的规则是：

> 默认使用脚本生成的字幕；用户明确要求时允许修改文本、断句或时间边界。保留用户修改，不在后续准备步骤中未经允许重新生成并覆盖。

需要保留的只是基本正确性：JSON 有效、时间顺序合理、`begin_ms/end_ms` 与 `begin_s/end_s` 一致，以及画面实际使用修改后的字幕。改显示写法或断句不一定需要重新配音；改变实际解说内容才涉及上游音频。

当前覆盖风险是真实的：再次执行 `align-narration.py --mode subtitles` 会写出字幕产物，现有流程还要求 agent 开始时先执行它，没有单独的“保留人工字幕”约定。

相关限制不只在第 55 行，还在 `references/delegation/composition/base-instructions.md:12,54` 和 `references/delegation/composition/handoff-template.md:51,57-66`，实施时要一起调整。

## 7. 第 58 行：scene 设计为什么归 HyperFrames，script phase 不是已经给场景了吗

**Phase 6 确实已经给出了场景。** 它提供的是叙事层的 `scene-plan.json`：

- `paragraphs`：对应哪些旁白段落；
- `intent`：要让观众理解什么；
- `content_plan`：使用哪些内容、怎样展开；
- `material_candidates`：候选素材；
- `cues`：需要对齐时间的原句。

Phase 8 的工作是把它实现成画面：素材放哪里、如何突出重点、何时出现、怎样运动。当前还允许视觉场景合并 / 拆分，但必须说明偏离理由，不能改旁白或忽略叙事目标。

例如 Phase 6 写“同条件对照两组实验结果，先结论再解释”，Phase 8 决定使用并排图表、逐项高亮差异，并对齐对应解说时间。

**职责主体应该是 composition agent，不是 HyperFrames。** 工具没有场景设计权。可以说“根据 Phase 6 的场景规划设计并实现画面”，不能说“scene 设计归 HyperFrames”，也不能让下游把上游场景规划当成不存在。

依据：`references/delegation/script/base-instructions.md:92-115`、`references/delegation/composition/base-instructions.md:33-40,55-59`。

## 8. 第 58 行：找出项目中所有使用 HyperFrames 的地方，由我决定是否继续用

已检查显式的 `hyperframes` 引用，以及 `__hyperframes`、`__timelines`、`data-composition-*` 等不一定写出工具名的实际依赖。完整的文件位置按类别放在本文末尾的“HyperFrames 依赖清单”，重复的示例副本和生成缓存按目录合并。

结论不是“只引用了几个 skill”：

- **指令依赖**：入口和委派说明直接要求使用 HyperFrames、执行其检查和渲染。
- **代码依赖**：现有 HTML 组件 / 模板使用它的变量注入、子合成挂载和时间线注册约定。
- **验收依赖**：阶段产物固定为 HTML composition；检查脚本认识当前工程的部分运行时约定。

所以“删掉强制 skill”“只保留 HyperFrames 渲染”“完全更换画面实现与渲染工具”是三个不同范围。完全替换不能只删文档中的名称，否则旧组件未必能加载、传参或正确播放。

反过来，调研、素材抓取、旁白、TTS / ASR、文本对齐和基于 FFmpeg 的成片检查 / BGM 混音，并不需要 HyperFrames。字体、主题 token、素材 catalog 和真实语音时间也不应跟着被删。

**本轮不替你决定是否继续使用 HyperFrames，也不预选替代工具。** 清单不包含 `.git` 历史、系统缓存内容和安装在仓库外的外部 skills。

## 9. 第 62 行：项目中有说如何让 pi-coding-agent 选择模型吗

**有，而且支持按阶段分别指定。** 统一说明在 `references/delegation/conventions.md:7-9,25-30`，实际解析在 `scripts/delegation_config.py:26-32`。

`inputs.json` 可写成下面这样；其中模型值是占位符，必须换成实际可用的完整标识：

```json
{
  "coding_agent": "pi-coding-agent",
  "delegation": {
    "catalog": {"model": "<provider>/<catalog-model-id>"},
    "script": {"model": "<provider>/<script-model-id>"},
    "composition": {"model": "<provider>/<composition-model-id>"}
  }
}
```

现有规则是：

- 阶段 `agent` 覆盖全局 `coding_agent`；没写就继承全局。
- 阶段 `model` 写了就严格使用；没写时 `coding_model` 返回 `null`，使用目标 agent 自身的模型配置，不由仓库猜模型。
- `prepare-handoff.py` 同时把结果写入 handoff 并返回 `coding_agent/coding_model`。
- 实际调用必须选模型，不能只在 prompt 里要求模型名字。

仓库约定的 Pi 命令是：

```bash
pi --model "<provider>/<model-id>" -p -- "<dispatch_prompt>"
```

模型未指定时省略 `--model`。本轮只是核对仓库已有说明，没有启动 Pi 或重新验证本机安装版本的参数。

## 10. 第 62 行：去掉 `hyperframes-animation` skill

**应从项目指令中去掉，而不是只删这一处。** 当前找到两处直接引用：

1. `references/phases/08-composition.md:62`：按具体动画实现需要查阅该 skill。
2. `modules/motion.md:9-14`：要求加载该 skill，并列出其 recipes、blueprints、transitions、techniques 文档入口。

第二处也需要清理，否则 agent 仍会顺着 motion 文档去加载它。可以保留与具体外部 skill 无关的动效表达建议，不必因此删掉整份 motion 文档。

`modules/motion.md:16` 还提到另一个 `hyperframes-keyframes` skill。它不是本条点名的 `hyperframes-animation`，本轮不擅自把两者当成同一个删除要求；是否整体脱离 HyperFrames 由第 8 条的决定控制。

“去掉项目引用”也不等于“卸载系统里该 skill”。本轮没有改引用，更没有修改仓库外的安装目录。

## 11. 第 64 行：应该先看模板，再选 layout；都不匹配时让 LLM 自由发挥

**同意。当前 layout 先行的顺序会过早限制模板和画面设计。**

一个具体问题是：现有 `github` 模板只支持 `presenter`，而 8.0 对没有明确要求主持人的横屏直接选 `stage`。这样即使内容非常适合 GitHub 模板，也可能在看模板之前先把它排除。模块库本身已经把模板定义为“选择布局并组装一类视频”，与当前阶段顺序并不一致。

按你的意思，合理顺序是：

1. 先读取内容和用户要求；用户明确指定的 template / layout 优先。
2. 没有指定 template 时，先判断是否有**非常匹配**的模板；有则采用它的布局与组装方法。
3. 没有采用模板时，再考虑明确指定或非常匹配的现有 layout。
4. 都没有时，LLM 自主构图和编排，不强制套 `stage/presenter/portrait` 的固定分区。
5. 视觉方案确定后，才按实际字幕排版生成字幕并实现画面。

自主设计仍遵守用户已经确定的朝向、design、素材与语音同步要求。用户明确指定的 template 和 layout 互相冲突时应报告冲突，不能偷偷改其中一个。

这不只是交换标题：

- `scripts/video_contract.py:34-39,241-246` 当前要求 composition handoff 之前已有注册 layout。
- `scripts/prepare-handoff.py` 的 `require_registered_visuals()`、`require_compatible_template()`、`composition_plan()` 在准备 handoff 时就读取和校验布局。
- `scripts/pipeline-status.py` 的视觉前置校验也只接受注册布局。
- 字幕脚本需要实际的 `caption.width_px/font_size_px/max_lines`，`check-composition.py` 当前也需要 layout 区域定义。

实施时应让准备 / 派发不依赖提前选好的注册布局，把 template / layout 的设计决策交给 composition agent。自由布局可以落盘最小的工程级布局说明供字幕和检查使用，但**不应再要求它先注册到库里，也不能用一份固定 layout 假装“自由发挥”**。具体保存格式属于后续实现，不在这份答复里先定死。

## 12. 第 1–75 行：太复杂了，想说明什么

核心其实只有一句：

> 把已有旁白、真实语音时间和场景规划交给 composition agent，让它确定视觉方案、生成字幕、实现画面、检查并渲染成片；主 agent 准备输入并验收结果。

当前前 75 行混在一起讲了输入、输出、机器校验内部机制、人工自检、下一阶段 QA、字体准备、字幕禁令、委派职责和 layout 决策，同一职责又重复多次，所以很难看出主流程。

适合简化为四块：

1. **输入 / 输出**：每个文件补一句用途，避免只列名字。
2. **执行**：准备并派发 → agent 选视觉方案并制作 → 主 agent 验收。
3. **必要约束**：不随意改旁白，使用真实语音时间，满足用户要求和必用素材。
4. **完成条件**：产物齐全、实际检查通过、渲染成功。

命令和具体技术规则集中在 handoff、委派约定及脚本说明里；Phase 9 的完整 QA 不在这里展开。第 4 条要求删除的指纹机制直接清理，不是换个位置再保留一遍。

这是结构建议，本轮没有重写这 75 行。

## 13. 第 90 行：删除 examples 目录，整个项目中不再提及

**这项不能只把复制说明里的“不含 examples”删掉。** 当前目录有两组：

- `modules/examples/github-trending/`、`modules/examples/jay-actions/`：示例工程源文件与素材。
- `video-modules/examples/github-trending/`、`video-modules/examples/jay-actions/`：本地残留字体、预览 / 历史 / 检查等生成产物。

实际清理应覆盖这些目录，并同步移除以下目录引用：

- `modules/modules.md` 的目录树、参考入口、组装说明及数据脚本示例指引；
- `modules/components/jay/jay.md` 的完整工程和动作演示指引；
- `modules/templates/github/github.md` 的完整工程指引；
- `references/phases/08-composition.md`、`references/delegation/conventions.md`、`references/delegation/composition/handoff-template.md` 的复制排除说明；
- `scripts/prepare-handoff.py:14,175` 的说明和 `('examples',)` 排除参数；
- `tests/test_prepare_handoff.py` 的目录排除测试、夹具过滤与文档断言。

另外，`tests/test_phase_docs.py` 有两个方法名包含 `examples`，只是检查 Phase 4 文档中的 JSON 示例，不依赖待删除目录。如果要求项目里这个词**字面零出现**，可以改名，但不需要因此删除 JSON 示例校验。

本文为了回答清理范围暂时保留了这些名称；本轮没有删除目录或改引用。后续实施完成后，这份临时答复也可以移走或删除，避免它本身保留被清理的引用。

## 14. 第 91 行：不要强调不联网；缺字体就下载，下载失败再输出错误

**同意应改成“已有就复用，缺失就下载”，而不是“缺失直接失败，让人先维护仓库”。**

当前实现是两条分开的路径：

- `fonts-download.sh` 的普通 `install()` 只复制本地 CSS 和 WOFF2；缺失时 `theme_files()` 报错，提示手工运行 `--refresh`。
- `--refresh` 才调用 `fetch()` / `refresh()` 从 Google Fonts 下载。
- `prepare-handoff.py` 只调用普通安装路径，所以现在不会自动联网补齐。

应把缺失补齐整合进正常字体准备流程：本地完整就复用；缺 CSS 或字体文件就联网获取所需文件，成功后继续生成 handoff；实际下载失败时再返回带原因的错误 JSON，并保留已经可用的字体。

已有下载和错误传递实现可以复用，不必另造一套。`prepare-handoff.py` 的 `FontsError` 已经会携带字体脚本的错误 JSON。

注意当前 `--refresh` 是仓库维护入口，会替换主题 CSS 并清理字体池。正常制作视频时不应为了补一个缺失文件，直接无条件运行整个维护操作；下载补齐应针对需要的字体和工程 / 缓存。

需要同步更新 `scripts/fonts-download.sh`、`scripts/prepare-handoff.py`、Phase 8、`modules/modules.md` 及对应字体测试。本轮没有联网下载或修改这些文件。

## 15. 第 99 行：把默认 agent、命令、模型选择集中管理，不同阶段可用不同模型

**可以，而且现在已经有一部分统一管理，但还没做到单一来源。**

已有的部分：

- `references/delegation/conventions.md` 统一解释目标 agent、Pi 命令和模型 flag。
- `scripts/delegation_config.py` 统一解析阶段 agent / model 覆盖。
- `inputs.json.delegation.catalog/script/composition.model` 已经支持不同阶段不同模型。

不足是默认 `pi-coding-agent` 和命令说明仍在 Phase 1 / 5 / 6 / 8 多处重复。并且解析函数实际读取必填的 `inputs.json.coding_agent`，并没有在代码里统一定义 Pi 默认值；它依赖上游按照文档先写好这个值。

建议只设一个机器可读配置来源，例如待新增的 `references/delegation/agents.json`，集中声明：

- 默认 coding agent；
- 每种 agent 的执行命令、非交互入口和模型参数；
- catalog / script / composition 的默认 agent / model。

`scripts/delegation_config.py` 只负责读取这份配置、合并项目覆盖并返回解析结果；`conventions.md` 解释使用方法但不再复制默认配置，各 phase 只引用统一委派约定。实际派发仍由主 agent 执行，不需要新增自动 shell 派发脚本。

模型优先级可统一为：**项目的阶段级 model > 统一配置中该阶段 / agent 的默认 model > 目标 agent 自身的模型配置**。agent 优先级为：**阶段 agent > 项目全局 agent > 统一默认 agent**。换到另一个 agent 时不能无条件继承原后端的模型，应校验支持情况或报告冲突。

这样改默认命令或某阶段模型只改配置源，项目仍可覆盖，handoff 和实际调用也会使用相同结果。不必在每份 phase 文档里重复“默认 Pi，命令 pi”。本轮未新增这个配置，仅提出集中管理方案。

---

# HyperFrames 依赖清单

本清单同时覆盖“显式写出名称”和“使用其工程 / 运行时约定”。同文件内多处引用合并列出；重复源文件和生成缓存按目录列出，不把同一套副本误算成新的流水线能力。

## A. 工作流与委派文档

| 文件 | 使用方式 |
| --- | --- |
| `SKILL.md:13` | 将 HyperFrames 声明为下游 composition 与渲染工具 |
| `references/phases/08-composition.md:35,53,57,58,62,120` | 字体 / 场景职责措辞、指定 skills、检查与 lint 要求 |
| `references/phases/07-voice-subtitles.md:41,43` | 明确禁止 HyperFrames TTS / transcribe；属于禁止使用的说明，不是实际调用 |
| `references/delegation/composition/base-instructions.md:61-64` | 要求 HyperFrames 检查与渲染 |
| `references/delegation/composition/handoff-template.md:53,81` | 生成 HTML 子合成产物要求与 `npx hyperframes check` 命令 |
| `references/delegation/catalog/base-instructions.md:198` | 将素材尺寸的下游使用者称为 HyperFrames sub-agent |
| `references/delegation/script/base-instructions.md:69` | 禁止 script agent 设计 HyperFrames 卡片 / 布局；应改为工具无关的职责说明 |

## B. 模块文档与运行时代码

### 文档

| 文件 | 使用方式 |
| --- | --- |
| `modules/modules.md:3,77-101,107,138` | 库定位、init/check/preview/render、子合成挂载、变量注入和时间线约定 |
| `modules/motion.md:9-16` | 外部 `hyperframes-animation`、`hyperframes-keyframes` 及其参考入口 |
| `modules/components/components.md:24` | 所有组件必须符合 HyperFrames 子合成协议 |
| `modules/components/jay/jay.md:11,35,58` | Jay 子合成、挂载属性与参数 |
| `modules/components/nav-bar/nav-bar.md:32` | `data-composition-id/src` 挂载协议 |
| `modules/components/caption-bar/caption-bar.md:25` | `data-composition-id/src` 挂载协议 |
| `modules/components/transitions/tile-wipe/tile-wipe.md:38` | `data-composition-id/src` 挂载协议 |
| `modules/templates/github/project-cover.md:36` | 模板场景的子合成挂载协议 |
| `modules/templates/github/trending-overview.md:35` | 模板场景的子合成挂载协议 |
| `modules/designs/default/default.md:115` | HyperFrames 字号警告的处理说明 |
| `modules/designs/github/github.md:128` | 同上 |
| `modules/designs/producthunt/producthunt.md:114` | 同上 |

`modules/templates/templates.md` 和 `modules/templates/github/github.md` 还间接依赖这套实现：它们安排现有组件 / HTML 场景和布局，不能仅因没有写工具名就视为已经支持其他渲染方式。模板的 JSON 内容声明本身与渲染器无关。

### 实际 HTML

| 文件 | 直接变量接口位置 |
| --- | --- |
| `modules/components/jay/jay.html` | 第 99 行 |
| `modules/components/nav-bar/nav-bar.html` | 第 74 行 |
| `modules/components/caption-bar/caption-bar.html` | 第 51 行 |
| `modules/components/transitions/tile-wipe/tile-wipe.html` | 第 51 行 |
| `modules/templates/github/project-cover.html` | 第 163 行 |
| `modules/templates/github/trending-overview.html` | 第 144 行 |

这六份代码都通过 `window.__hyperframes.getVariables()` 读取挂载参数，并遵循模块库的子合成与时间线注册约定。虽然变量读取有空对象兜底，但兜底不等于不需要挂载、传参和时间驱动。

需要区分：HTML / CSS / SVG / GSAP 本身并不是 HyperFrames 独有；换工具时可以复用部分视觉代码，不能把所有 CSS、图像或 GSAP 动效都认定为必须删除。

## C. 脚本和阶段验收中的间接依赖

| 文件 | 依赖程度 |
| --- | --- |
| `scripts/check-composition-snapshot.js:7-43,105-107` | seek 认识 `window.__timelines`、`window.__hfAnime`；元素归属读取 `data-composition-id`。同时已有通用 `window.__layoutQA.seek()` 入口，不是只能检查 HyperFrames |
| `scripts/check-composition.py:17-31,353` | 用 Chrome / Playwright 测量 HTML DOM、区域和字幕；认识子合成标识，但**没有直接调用 HyperFrames CLI**。换到非 HTML 画面时要重新考虑这部分检查 |
| `scripts/prepare-handoff.py` 的 `composition_plan()`、`render_handoff()` | 物化当前模块和委派包，生成包含 HyperFrames 要求的 handoff；不是它自己执行 HyperFrames 渲染 |
| `scripts/pipeline-status.py:1382-1412` | 固定验收 `index.html`、`compositions/` 和当前 composition 报告等工程产物；不是直接的 HyperFrames 调用，但完全换工程形态时需更新 |

`scripts/composition_hash.py` 是项目自己的内容指纹实现，不是 HyperFrames SDK；它的删除属于第 4 条，不应与是否使用 HyperFrames 混为一件事。

## D. 示例工程和本地生成产物

以下位置全部在当前仓库目录范围内，本轮未删除。

### `modules/examples/jay-actions/`

- `package.json`：preview/check/render/publish 命令使用 `hyperframes@0.8.191`；这个版本是示例声明，不代表本机当前安装版本。
- `hyperframes.json`：schema、registry 地址及 `authoringSkill: hyperframes`。
- `.gitignore`：HyperFrames 生成目录的忽略说明。
- `jay-actions.md`：检查和预览命令。
- `index.html`：`data-hf-id`、子合成、track、时间与参数挂载属性。
- `compositions/jay.html`、`compositions/caption-bar.html`：组件副本及变量 / 时间线约定。
- `tools/build-data.mjs`、`data/video-data.js`：为这套示例组件准备数据，属于关联实现，不直接调用 HyperFrames CLI。

### `modules/examples/github-trending/`

- `package.json`、`hyperframes.json`、`.gitignore`：同一套 CLI、工程配置与生成目录约定。
- `github-trending.md`：HyperFrames 工程说明、`HYPERFRAMES_BROWSER_PATH`、检查和预览命令。
- `index.html`：子合成、时间和参数挂载属性。
- `compositions/jay.html`、`caption-bar.html`、`nav-bar.html`、`tile-wipe.html`、`project-cover.html`、`trending-overview.html`：六份运行时组件 / 场景副本。
- `tools/build-data.mjs`、`data/video-data.js`、`data/narration.json`：示例内容与时间数据，关联这套工程，不是独立渲染器调用。

### `video-modules/examples/` 下的两个本地目录

- `jay-actions/.hyperframes/`：`video-state.json`、`history-id`、`hf-ids-stamped.json`、`preview/87f090526aa79543c511cbb08fd2886a.html`、`artifacts/checks/`、`artifacts/snapshots/`。
- `github-trending/.hyperframes/`：`video-state.json`、`history-id`、`hf-ids-stamped.json`、`preview/b25eebb8a388b120adb4f3815afe95ee.html`、`artifacts/checks/`。

这些文件包含 HyperFrames 的历史路径、预览 runtime、变量作用域包装或检查记录，属于本地生成产物，不是现行工作流入口。整个目录清理范围见第 13 条。

## E. 测试与历史计划

| 文件 | 使用方式 |
| --- | --- |
| `tests/test_guardrail_docs.py:127,129,142` | 强制文档保留“字体 / Scene 归 HyperFrames”和禁止其 transcribe 的措辞 |
| `tests/test_prepare_handoff.py:439,925,1030` | 断言 handoff / 模块文档中的 HyperFrames check 和 init 命令 |
| `tests/test_template_cues.py:32` | 模拟 `__hyperframes.getVariables()` 与 `__timelines` 来执行模板脚本 |
| `docs/plans/pr-review-fixes-and-remove-legacy-compat.md:360,396,432` | 历史计划 / 实施记录里的 HyperFrames 渲染验证说明 |
| `docs/plans/phase-inputs-and-pi-delegation.md:248,306` | 历史记录里的 HyperFrames 依赖及未验证项 |

另有 `tests/test_check_composition.py`、`tests/test_check_composition_snapshots.py`、`tests/fixtures/check_composition_snapshots.json` 和 `tests/test_pipeline_status.py` 覆盖现有 DOM、区域与 HTML 工程产物。这些测试不都直接依赖 HyperFrames；如果改工程形态或放开 layout，需要按保留的真实检查能力调整，不能一律删除。

## F. 可与 HyperFrames 独立保留的能力

- Phase 1–6 的输入、论文解析、调研、素材、旁白和叙事规划。
- Phase 7 的 TTS / ASR 与 `scripts/align-narration.py` 的文本时间对齐；字幕排版目前依赖 layout 数据，但不调用 HyperFrames。
- `scripts/fonts-download.sh`、`resources/fonts/`、design token 与图片资源。
- `scripts/check-render.py`、`scripts/make-contact-sheet.py`、`scripts/mix-bgm.py` 的成片检查、拼图和混音。

**是否保留 HyperFrames 的最终决定留给你；本文件只回答批注并列出实际影响范围。**
