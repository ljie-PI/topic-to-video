# 三句开场钩子、7 字符/秒与场景内容规划：修改计划

## 0. 状态、基线与范围

- 状态：已按本文实施（工作区改动，未提交、未推送）。实际差异见文末「实施记录」。
- 同步：先执行 `git fetch origin main`，确认工作区干净、无本地分叉，再用 `git merge --ff-only origin/main` 快进。
- 调研基线：`main` / `origin/main` 均为 `c6f151c0a19a7fcb47647197a4a1241411250976`，已包含 PR #137 的素材改进与 PR #138 的阶段归属 / 当前契约修复。
- 本计划承接三条评论：开场在三句话以内抓住注意力；去掉指定 `speech_rate`、按 7 字符/秒估算稿长；删除脚本场景里的 `template_scene`、`pattern_hints`、`beats`，新增内容演绎规划，并把 template / pattern 使用决策交给 composition agent。
- composition 本轮只改职责、输入契约、交接和必要的校验，不扩展完整视觉设计方法。后续可另写 composition 专项计划。
- 不提交、不推送、不发布；远端同步不等于授权把后续改动合入远端 `main`。

## 1. 调研结论：不能只改一份基础指令

| 现状与定位 | 本轮应如何处理 |
| --- | --- |
| [script 开场规则](worktree://0e7308a8-795f-4516-a44f-3070c2260479/references/delegation/script/base-instructions.md#L13-L31)仍只有反常识 / 数字 / 场景问题；论文 Hook 没有三句约束 | 补具体方法、选用流程和自检；标准模式与论文模式共用三句钩子规则，论文主体结构不改 |
| [稿长指令](worktree://0e7308a8-795f-4516-a44f-3070c2260479/references/delegation/script/base-instructions.md#L39-L42)、[Phase 6 判据](worktree://0e7308a8-795f-4516-a44f-3070c2260479/references/phases/06-script-scene-plan.md#L24-L27)、[状态脚本常量](worktree://0e7308a8-795f-4516-a44f-3070c2260479/scripts/pipeline-status.py#L199-L202)仍使用 7.5 | 同时改为 7；450 字符/分钟与 2250 字符/5 分钟分别改为 420 与 2100 |
| 新主线的 [script schema](worktree://0e7308a8-795f-4516-a44f-3070c2260479/references/delegation/script/base-instructions.md#L65-L89)已没有 `template_scene`，但仍有 `pattern_hints`、`beats` | 不重复删除已完成的字段说明；清理剩余字段，并对三个已移除字段建立明确拒绝规则 |
| [scene 校验](worktree://0e7308a8-795f-4516-a44f-3070c2260479/scripts/pipeline-status.py#L997-L1044)检查 beats，却没有检查 `intent` 的类型 / 非空性 | 改为检查 `intent` 与新字段 `content_plan`，不再校验 beat 类型、长度或文本 |
| [对齐器](worktree://0e7308a8-795f-4516-a44f-3070c2260479/scripts/align-narration.py#L825-L848)生成 beats，[时间轴输出](worktree://0e7308a8-795f-4516-a44f-3070c2260479/scripts/align-narration.py#L978-L1002)总是带 beats 与 `beat_count` | 删除 beat 定位、输出和统计；保留段落、scene 与 cues 的真实时间对齐 |
| [composition 基础指令](worktree://0e7308a8-795f-4516-a44f-3070c2260479/references/delegation/composition/base-instructions.md#L31-L52)要求读取 beats 并映射成动作，但模板专用 cues 已由本阶段生成 | 删除上游 beat → 动作指令，保留模板专用 cues 的现有实现，不另建对齐器 |
| [Phase 8.0](worktree://0e7308a8-795f-4516-a44f-3070c2260479/references/phases/08-composition.md#L64-L75)仍在派发之前决定 template；[handoff 生成器](worktree://0e7308a8-795f-4516-a44f-3070c2260479/scripts/prepare-handoff.py#L359-L398)只列已选模板文档 | 不能只写“composition 自己选”；需要让尚未选择模板时的 handoff 支持模板发现，并把实际选择放进 composition agent 的工作顺序 |
| [Jay 文档](worktree://0e7308a8-795f-4516-a44f-3070c2260479/modules/components/jay/jay.md#L91-L133)仍把语义动作关联到 timeline beats | 清理上游依赖说法，保留动作库、推荐时长、嘴型与动作防重叠规则 |
| [委派副本策略](worktree://0e7308a8-795f-4516-a44f-3070c2260479/references/delegation/conventions.md#L49-L61)不自动覆盖已有文件 | 实施后的执行说明必须包含按需 `--refresh`；只改仓库原文不保证已有工作区读到新规则 |

### 1.1 开场方法的外部参考及适用边界

调研参考以下平台官方说明（通过网页搜索获取正文片段；直接 fetch 两个页面时超过工具大小限制）：

1. [YouTube：Understand your content performance](https://support.google.com/youtube/answer/16559650?hl=en)：开头几秒要直接兑现主题 / 标题承诺，简短给出价值，并用期待与好奇心维持观看。
2. [YouTube：Measure key moments for audience retention](https://support.google.com/youtube/answer/9314415?hl=en)：intro 指标观察前 30 秒留存，建议尝试不同开头，并把后段吸引人的内容前移。
3. [TikTok Creator Academy：Understanding and engaging with your audience](https://www.tiktok.com/creator-academy/article/Understanding-and-engaging-with-your-audience)：建议开头快速说明内容、提出将被回答的问题、预览结果或说明时间投入，并根据留存调整。

据此归纳“具体冲突 / 异常 + 与观众有关的代价或收益 + 能兑现的悬念”。下文的方法分类、三句结构与示例是本项目的编辑建议；**三句话是用户要求，不是平台证明的最优阈值，也不承诺提升某个留存百分比**。不采用虚假稀缺、恐吓或无证据的 FOMO。

## 2. 推荐方案与取舍

### 2.1 三句话以内：用真实矛盾制造戏剧张力

推荐新增一个标准 / 论文模式共用的「开场钩子」小节，并让原有两处开场规则指向它。实际落地时按评审意见又精简了一次：先用一句白话解释“开场钩子是什么”，再列三句要点，然后直接引出方法表，不再保留下面这段较绕的描述。

基本结构，不要求机械凑满三句：

1. **第一句打破惯性**：直接给异常结果、具体困境或有代价的选择；不从自我介绍、行业背景和“今天我们来聊……”开始。
2. **第二句拉高张力**：说清反差、限制、代价或观众为什么该在意；给一个事实支点，不连续堆数字和术语。
3. **第三句建立可兑现的期待**：提出本文会回答的具体问题，或说明观众将学会怎样判断；随后立刻进入解释。

可以一句兼顾多个作用，**首个钩子最多三句短句**。不能用分号串接和超长句规避限制。第一句就应有信息，不要三句都在预告。

开场的 5–10% 是点题和必要衔接的整体参考，**不是先铺垫完这个比例才抛钩子**。钩子应在开头三句内完成；之后再补最低限度背景。可按约 40–90 个非空白字符检查是否过长，但这只是编辑建议，不新增硬字数门槛或固定开场秒数。

### 2.2 具体方法库：选一种主钩子，最多搭配一种辅助方法

下表是供 script agent 改写的骨架，不是可直接当事实使用的稿子。`[方括号]` 必须替换为 research brief 中已核实的内容；没有对应证据，就不用这一招。每个示例均不超过三句。

| 方法 | 怎样形成戏剧张力 | 三句以内的示例骨架 | 证据 / 使用边界 |
| --- | --- | --- | --- |
| 反常识反转 | 把直觉与真实结果正面相撞 | “删掉[模块]，结果反而[改善]。少做一步，为什么更有效？先看这个对照实验。” | 必须有同条件对照；不能把特定实验结论说成普遍定律 |
| 数字落差 | 用同一尺度的两组数字形成强反差 | “同一个[任务]，方法 A 要[数值与单位]，方法 B 只要[数值与单位]。差距来自哪里？答案藏在[关键步骤]。” | 单位、任务、测量条件必须一致；最多突出一组差距 |
| 困境冷开场 | 先进入出问题的那一刻，不先讲背景 | “任务跑到最后一步，却卡在[具体失败]。你已经[真实投入]，现在只能重来吗？这次从失败原因讲起。” | 场景是素材中真实事件，或明确标注的假设；不能伪称亲历 |
| 目标冲突 / 两难 | 两个观众都想要的目标似乎不能兼得 | “想要[目标 A]，就必须牺牲[目标 B]吗？[研究 / 工具]试着改变这个取舍。它在哪些条件下做到了？” | 不隐去边界；论文必须保留实验条件，不说“彻底解决” |
| 先给结果，再倒推 | 先展示有解释价值的成果，把过程变成悬念 | “先看[已验证结果]。最值得看的不是结果本身，而是[关键变化]。它究竟怎么做到的？” | 旁白先交代结果；素材足够时在 `content_plan` 建议结果先行，不指定组件 |
| 异常细节 / 侦探式提问 | 给一条不符合预期的线索，让观众想找原因 | “[现象 A]没变，[结果 B]却变了。被忽略的是哪个条件？我们沿着[可核实线索]查下去。” | 悬念必须有正文答案；不使用“有人故意隐瞒”式阴谋暗示 |
| 猜测再揭晓 | 让观众先建立一个预测，再用证据检验 | “这两种[方案]，你猜哪一种更适合[任务]？先别只看[表面指标]。实际对照里，[关键条件]才决定结果。” | 不凭空预设观众选错，也不人为构造假对照 |
| 把量级变成可感知代价 | 数字变成观众熟悉的时间、成本或工作量 | “[数值与单位]到底意味着什么？放到[可比场景]里，相当于[可核算换算]。这才是[变化]值得关注的原因。” | 换算基准明确；不能夸大收益或漏掉成本 |
| 收益与隐藏代价 | 给出好处后，立刻指出会影响决策的限制 | “[方案]能帮你[已验证收益]，但它也有[关键限制]。这个代价在什么情况下值得付？看完这组案例再决定。” | 不是标题党式“千万别用”；限制和收益都要有出处 |
| 旧办法 / 新办法转折 | 从原先的解法切到真正变化的规则 | “以前解决[问题]，要先[旧步骤]。现在，[新方法]改变的是[关键环节]。它省掉了什么，又留下了什么？” | 必须确认旧方法适用范围；不虚构行业共识或历史必然性 |

选用流程：

- 从 brief 中找最值得解释的一条冲突、失败、结果或取舍，先写三种不同方向的短开头，再选最清楚、最贴题的一种；不新增候选钩子产物或评分 JSON。
- 比较四点：第一句是否具体；与观众是否有关；是否有可信支点；正文是否能兑现。张力优先来自内容，不来自“震惊”“炸裂”“颠覆一切”等形容词。
- 第一个主体部分开始回答开头问题，结尾回扣，不能把答案拖到结尾才给。
- 用户要求严肃 / 学术语气时，仍用冲突或问题，但降低表演性；用户明确指定开场时尊重其要求，不强套方法库。
- 论文 Hook 优先来自问题难点、关键发现、实验对照或适用边界；不让戏剧化改写破坏原论文的逻辑流。

### 2.3 7 字符/秒只决定稿长估算，不决定 TTS 参数

推荐指令替换为：

> 按约 **7 字符/秒**估算显示稿长度：目标字符数 = `inputs.json` 的目标分钟数 × 420（5 分钟约 2100 字符，去掉所有空白，标点仍计数）。目标时长只取 `inputs.json.duration`；状态脚本会把偏差超过 ±15% 的显示稿打回。这是写稿预算，不是设置 TTS 语速的命令；实际画面同步以生成音频和 transcript 为准。

代码只改实际负责稿长验收的常量及注释，不把估算系数透传为 `--speech-rate`，不新增 inputs 字段。

| 目标时长 / 用例 | 新字符数 |
| --- | --- |
| 1 分钟 | 420 |
| 默认 3 分钟 | 1260；默认时长本身不变 |
| 5 分钟 | 2100 |
| 5 分钟的 ±15% 边界 | 1785–2415（含边界） |
| 5 分钟的 ±20% 失败用例 | 1680、2520 |
| 5 分钟的 ±14% 通过用例 | 1806、2394 |

范围区分：

- [Phase 7 统一入口](worktree://0e7308a8-795f-4516-a44f-3070c2260479/scripts/voice-subtitles.py#L146-L157)本来就不传 `--speech-rate`，保持这个行为，并加回归断言。
- [voice-clone 的 CLI](worktree://0e7308a8-795f-4516-a44f-3070c2260479/scripts/voice-clone.py#L273)仍支持用户显式控制语速；不因本条评论擅自修改各后端默认值或删掉这个 CLI 能力。这里将“不要指定”理解为写稿 / 流水线指令不锁定语速；如需连后端默认值一起改，另行确认。
- [fake_backend 的 7.5](worktree://0e7308a8-795f-4516-a44f-3070c2260479/scripts/fake_backend.py#L19-L30)是测试替身合成音频的独立速度，不是 Phase 6 稿长规则。本轮保留它及对应音频时长断言，不做全仓库 7.5 → 7 的机械替换。
- 不把写稿估算和测试替身速度合并成一个共享常量；两者含义不同。字号、时间点、颜色等无关数字也不改。

### 2.4 新字段：必填 `content_plan`，只表达内容与演绎逻辑

选择一个非空字符串，而不是嵌套对象、枚举或另一个节拍列表：

| 字段 | 回答的问题 | 边界 |
| --- | --- | --- |
| `intent` | 观众看完这一段应理解什么？ | 理解目标，不是模块名或画面描述 |
| `content_plan` | 用哪些内容、以什么展开顺序 / 演绎方式达成这个目标？ | 说明内容对象、对比 / 演示 / 推演方式与推进顺序，不规定视觉实现 |
| `facts` | 解释依赖哪些可追溯事实？ | 保留现有事实依据职责 |
| `material_candidates` | 哪些真实素材可能支撑讲解，为什么？ | 保留候选评分、slug 身份和必用素材覆盖，不做排他分配 |
| `cues`（可选） | 哪些已经写进显示稿的原句值得对齐到音频？ | 不是模板 / pattern / 动作提示；继续逐字摘录并落在对应段落内 |

推荐格式示例（仅示意结构，事实与素材需按实际 brief / catalog 填）：

```json
[
  {
    "scene_id": "scene_1",
    "paragraphs": [1, 2],
    "intent": "理解评测总分高不代表适合所有任务",
    "content_plan": "先用同一任务下的两组结果做对照，再讲困难任务中的失败样例，最后解释差异来自哪些测试条件；按对比、反例、归因的顺序展开，帮助观众区分总分与具体任务表现。",
    "facts": ["研究简报中核实过的评测结果与实验条件"],
    "material_candidates": [
      {"ref": "example/img_001", "score": 8, "reason": "支撑两种方案的同条件对照"}
    ],
    "cues": ["总分高，不代表适合所有任务。"]
  }
]
```

写法约束：

- 每项说明“拿什么来讲”与“怎样展开”，而不是把 `intent` 换几个词重复一遍。
- 可以建议结果先行、同条件对照、失败复盘、逐步推演、类比或图表解读；这是内容演绎方向，不是完整 storyboard。
- 不写 template / pattern 的库名，不指定 HTML 组件、layout 区域、坐标、屏幕文字、动画参数、Jay 动作或精确秒数。
- 不把旧 beats 改名塞进 `content_plan`，不在文字里保留 beat 类型 → 动作指令。
- 无 catalog 时，仍可规划假设例子、逻辑推演或纯信息讲解，但素材候选保持空列表；不能许诺使用不存在的录屏、图片或图表。
- `content_plan` 与场景计划整体仍是 composition 的参考；composition 可以合并、拆分或改变演绎方式，但应解释重大偏离如何仍达成 `intent`。

取舍：嵌套的 `content` / `approach` / `sequence` 会增加必填结构与重复表述；另建 beats 列表会重新把编排权锁在 script。先采用单个字符串，形式校验只检查类型和非空，内容质量交给执行者自检。

### 2.5 删除字段的整条链，保留独立 cues 能力

- `scene-plan.json`：三个字段 `template_scene`、`pattern_hints`、`beats` 都禁止出现，包括空列表 / null；失败原因列出 scene 和字段，要求 Phase 6 按新契约重新规划。
- 在 [公共契约模块](worktree://0e7308a8-795f-4516-a44f-3070c2260479/scripts/video_contract.py#L1-L8)集中声明已移除字段，并提供小型字段检查供状态检查与直接 timing 入口复用；不引入通用 JSON Schema 框架。
- Phase 6 的完整产物必须有非空字符串 `intent` / `content_plan`；段落覆盖、素材引用、词表、偏移表哈希和审稿策略保持现有规则，不顺带扩展全部字段严格校验。
- 对齐器不再读取、生成或统计 beats；Phase 7 的时间轴仅生成段落和可选的 scenes / cues。状态脚本明确拒绝含 `beats` 的旧 timeline，不能只删校验后把残留 beats 默默当有效输入。
- composition 专用 `template-cues.json` **不是 Phase 6 的完整 scene-plan**，仍允许只有 `scene_id` / `paragraphs` / `cues`。复用已移除字段检查时，不能错误地要求它补上 `intent` / `content_plan` / facts / materials。
- `content_plan` 不被对齐器解析或复制进 timeline；没有 cues 时也能按段落取得时间。
- `cues` 保留是因为它服务实际朗读文本的时间定位，与被删除的视觉决策字段不同。模板 / 动作需要新的卡点时由 composition 自己选已朗读原文，不回写上游规划。
- 不创建迁移脚本，不把 beats 自动改写成 content_plan，也不为了通过校验自动删除旧字段；按当前契约拒绝并说明负责重做的阶段。

### 2.6 composition 只做最小职责调整

目标顺序：读内容规划 → 自主选 template / pattern / 演法 → 自己写 storyboard → 生成必要的模板 cues → 组装、检查、渲染。

推荐最小交接方案：

1. **主 agent 暂时保留现有 layout 准备逻辑**：按已确定的 orientation、design 和用户画面要求选合法 layout，写入 inputs，保证字幕命令与字体准备仍是确定的。本轮不扩大到 layout 自主选择的两阶段派发。
2. 主 agent 不在 8.0 代选模板，也不为新项目预填 `template: null` 冒充“已决定不用”。`prepare-handoff.py composition` 允许缺少 template，并在 handoff 中显示“未选择，由 composition agent 决定”。
3. handoff 始终提供工作区 `modules/templates/templates.md`，让 composition 能发现模板。已有 template 值时继续列该模板文档与 JSON，但写清它是当前配置、应结合用户要求与内容核对；不是 script 的推荐或主 agent 强制套版。
4. composition agent 在写 storyboard 前查看模板目录及 `supported_layouts`，决定使用哪个模板或不用，**亲自写入 `inputs.json.template`（合法名称或 null）**，再读取选中模板的组装文档 / JSON、所需 pattern 和组件文档。正文中的具体模板引用按需读取即可，不新增第二份 bootstrap handoff，也不重复派发。
5. template 缺省表示尚未选择，null 表示已经明确不使用；不增加第三种持久化字符串状态。`prepare-handoff` 可以接受前者以便派发，Phase 8 完成校验必须要求字段已经落地，避免 agent 忘记选择仍被视作完成。
6. 已显式选择但不合法 / 与 layout 不兼容的配置仍在准备时明确报错；实际完成验收继续用当前库注册规则与实际工作区副本校验。不要为了“自主选择”取消 compatibility 检查。
7. 选择模板后按既有「基础指令 → 模板说明 → 用户 composition_requests」顺序叠加，用户要求优先；template / pattern 选择不能改旁白、朝向或 design。固定 layout 不支持模板时用 null，不扩大本轮范围去改 layout。
8. 用 `content_plan` 理解内容，最终具体素材、信息形态、视觉层级、动作与卡点写在 storyboard / VIDEO 数据里；不再读 `pattern_hints`、`template_scene` 或 timeline beats。
9. 删除固定 beat → 动作映射要求。Jay 动作由 composition 根据旁白和内容演绎自行选择，保留动作库和防重叠要求；需要精确时间时用已对齐段落 / cues 或本阶段自行摘录原句对齐，不按稿长估秒。
10. 保留 [模板时间锚点流程](worktree://0e7308a8-795f-4516-a44f-3070c2260479/references/delegation/composition/base-instructions.md#L44-L52)：composition 写专用 cues、跑同一 timing 模式、输出到自己的 assets，不重做 TTS / ASR，不改 Phase 7 时间轴。非模板的演绎卡点如需使用该能力，也只在 composition 下生成，不引入新的正式 beats schema。

为什么选这个方案：只改文字会留下“主 agent 先决定模板”的实际流程；让 composition 同时决定 layout、重新生成所有 handoff 命令又超出“大概改一下”。保留 layout 准备、把模板发现 / 选择放进已有单次 composition 委派，是可执行且范围最小的方案。

暂不做：模板自动评分器、新模板 / pattern、新动画系统、storyboard 机器 schema、镜头密度规则、构图与动效细则、新的渲染 QA 指标。

## 3. 要改哪些文件、具体怎么改

### 3.1 执行文档与委派包

| 文件 | 修改内容 |
| --- | --- |
| [script 基础指令](worktree://0e7308a8-795f-4516-a44f-3070c2260479/references/delegation/script/base-instructions.md#L9) | 增加共用钩子方法库 / 三句约束 / 选用与自检；统一 7 / 420 / 2100；schema 加 content_plan、删 pattern_hints / beats；单独解释 cues；自检加内容演绎与事实边界 |
| [script handoff 模板](worktree://0e7308a8-795f-4516-a44f-3070c2260479/references/delegation/script/handoff-template.md#L35-L44) | Outputs 提示 intent / content_plan 及新的职责边界，详细 schema 仍只在基础指令维护，不复制方法库 |
| [Phase 6](worktree://0e7308a8-795f-4516-a44f-3070c2260479/references/phases/06-script-scene-plan.md#L21-L40) | 稿长判据改为 7；场景判据改为新字段与已移除字段拒绝；自检覆盖三句钩子与 content_plan；审稿摘要在 scene_id + intent 后补演绎摘要 |
| [Phase 6 护栏](worktree://0e7308a8-795f-4516-a44f-3070c2260479/references/phases/06-script-scene-plan.md#L46-L49) | 去掉仍残留的“规划屏幕文本块”，改成内容演绎与素材候选，消除与视觉职责的直接冲突 |
| [Phase 7](worktree://0e7308a8-795f-4516-a44f-3070c2260479/references/phases/07-voice-subtitles.md#L5-L26) | 输入 / 输出 / 判据 / 回退表 / 文本对齐说明去掉 beat，保留 scene / cue 与完整重跑、align-only 规则 |
| [composition 基础指令](worktree://0e7308a8-795f-4516-a44f-3070c2260479/references/delegation/composition/base-instructions.md#L7-L16) | 输入时间轴不再含 beat；第四部分改为自主内容演绎 / template / pattern 选择；工作顺序新增模板选择落地，保留 design、layout、字幕、必用素材与真实时间约束 |
| [composition handoff 模板](worktree://0e7308a8-795f-4516-a44f-3070c2260479/references/delegation/composition/handoff-template.md#L15-L51) | 区分 template 未选择 / null / 名称；Required References 加模板总览；scene-plan 描述突出 intent / content_plan；删除 beat 动作说法，storyboard 输出要求记录自主选择与偏离理由 |
| [Phase 8](worktree://0e7308a8-795f-4516-a44f-3070c2260479/references/phases/08-composition.md#L64-L109) | 8.0 只准备 layout；模板选择移入被委派 agent 的执行；8.2 / 8.3 更新发现与引用流程；判据明确 template 必须已落地；输入、自检及 8.4 抽查覆盖新的职责 |
| [委派约定](worktree://0e7308a8-795f-4516-a44f-3070c2260479/references/delegation/conventions.md#L38-L45) | 说明模板由 composition 执行中选定后读取，保持用户要求优先及单句派发；说明新规则落地时按需 refresh |
| [模块模板入口](worktree://0e7308a8-795f-4516-a44f-3070c2260479/modules/templates/templates.md#L12-L29) | 明确模板选择者和读取 supported_layouts 的顺序，不改模板注册 / 参数契约 |
| [Jay 组件文档](worktree://0e7308a8-795f-4516-a44f-3070c2260479/modules/components/jay/jay.md#L91-L133) | 删除 timeline beats 映射依赖，把“对应 beat”列去掉（已有“适合的时刻”足够）；保留全部动作与推荐时长 |

事实安全的必要修正：现有 [script 自检](worktree://0e7308a8-795f-4516-a44f-3070c2260479/references/delegation/script/base-instructions.md#L95-L103)与 Phase 6 的“找不到就删掉或标‘据报道’”应收紧为“没有可追溯来源就删除 / 回报上游不足；写‘据报道’也必须有来源”，防止新增戏剧化方法被当作编造事实的许可。

### 3.2 实现与测试

| 文件 / 测试 | 修改内容 |
| --- | --- |
| [scripts/video_contract.py](worktree://0e7308a8-795f-4516-a44f-3070c2260479/scripts/video_contract.py#L1) / [tests/test_video_contract.py](worktree://0e7308a8-795f-4516-a44f-3070c2260479/tests/test_video_contract.py#L1) | 集中已移除 scene 字段的拒绝规则；测试空值也拒绝、正常 cue-only 结构不被完整规划规则误伤 |
| [scripts/pipeline-status.py](worktree://0e7308a8-795f-4516-a44f-3070c2260479/scripts/pipeline-status.py#L199-L202) / [tests/test_pipeline_status.py](worktree://0e7308a8-795f-4516-a44f-3070c2260479/tests/test_pipeline_status.py#L676-L715) | 常量改 7；更新 target / 误差消息、边界与 fixture；scene 检查 intent / content_plan 并拒绝旧字段；移除 BEAT_TYPES 和 beat 校验，timeline 拒绝 beats；Phase 8 template 缺省不算完成 |
| [scripts/align-narration.py](worktree://0e7308a8-795f-4516-a44f-3070c2260479/scripts/align-narration.py#L718) / [tests/test_align_narration.py](worktree://0e7308a8-795f-4516-a44f-3070c2260479/tests/test_align_narration.py#L519) | 删 locate_beats、scene_clock 第三个返回值、beats / beat_count 输出以及帮助文本；直接 timing 输入明确拒绝已移除字段；原段落 / cues / subtitles 行为保持 |
| [scripts/voice-subtitles.py](worktree://0e7308a8-795f-4516-a44f-3070c2260479/scripts/voice-subtitles.py#L8-L15) / [tests/test_voice_subtitles.py](worktree://0e7308a8-795f-4516-a44f-3070c2260479/tests/test_voice_subtitles.py#L1) | 说明去掉 beat；测试真实统一入口不传 speech-rate、输出 timeline 没有 beats；不改 TTS 子命令与后端默认值 |
| [scripts/prepare-handoff.py](worktree://0e7308a8-795f-4516-a44f-3070c2260479/scripts/prepare-handoff.py#L359-L398) / [tests/test_prepare_handoff.py](worktree://0e7308a8-795f-4516-a44f-3070c2260479/tests/test_prepare_handoff.py#L439) | 加模板总览引用、区分未选择与不用、已选模板仍按实际副本校验；调整引用顺序与 null 测试，不再断言无模板时完全看不到 templates 目录 |
| [tests/test_phase_docs.py](worktree://0e7308a8-795f-4516-a44f-3070c2260479/tests/test_phase_docs.py#L453-L471) / [旧 beat 文档测试](worktree://0e7308a8-795f-4516-a44f-3070c2260479/tests/test_phase_docs.py#L587-L614) | 替换旧模板派发前决定、beats authoring / mapping 断言；改验内容规划、自主选择、三句钩子、7 字符/秒及保留 cues 的一致性 |
| [tests/test_phase_docs.py 的 Jay 断言](worktree://0e7308a8-795f-4516-a44f-3070c2260479/tests/test_phase_docs.py#L523-L562) | 去掉“对应 beat”表头与映射依赖断言，继续验证通用演法、动作库和 GitHub 专属叠加没有被误删 |
| [tests/test_template_cues.py](worktree://0e7308a8-795f-4516-a44f-3070c2260479/tests/test_template_cues.py#L50-L106) | 保留真实模板 JS 的必需锚点拒绝、可选锚点隐藏测试；与对齐器 cue-only 回归一起证明没有为了删 beats 破坏模板卡点 |

审稿 gate 的 [状态脚本 instruction](worktree://0e7308a8-795f-4516-a44f-3070c2260479/scripts/pipeline-status.py#L180-L185)也补 content_plan 摘要，与 Phase 6 审稿说明一致；不改变 gate 默认值、产品哈希绑定或批准权限。

fixture 更新要按含义逐个确认：[两段 SCRIPT_TXT](worktree://0e7308a8-795f-4516-a44f-3070c2260479/tests/test_pipeline_status.py#L50-L51)改成各 1050 字符，[三段测试稿与 scene 工厂](worktree://0e7308a8-795f-4516-a44f-3070c2260479/tests/test_pipeline_status.py#L757-L768)改成各 700 字符并补 content_plan；其他手写 scene / 时间轴 fixture 跟随实际消费契约，不改无关秒数。

明确不改：素材抓取与 catalog 实现、design / layout JSON、Jay HTML、模板 HTML、voice-clone 后端实现和 fake 合成速度。历史 `docs/plans/` 是记录，不把其中描述旧方案的文字批量替换成新方案；本文作为后续实施入口。

## 4. Work items 与依赖

| ID | 工作项 | 前置 | 交付 / 完成条件 |
| --- | --- | --- | --- |
| WI-01 | 固定新契约与回归用例 | 无 | content_plan 结构、旧字段拒绝、7 字符预算、template 未选 / null 语义在测试中明确 |
| WI-02 | 完善三句开场指令 | 无 | 共用方法库、短句结构、选用流程、论文边界、事实护栏及自检写入 script 包 |
| WI-03 | 统一稿长估算与 fixture | WI-01 | 状态脚本和文档均为 7 / 420 / 2100；±15% 边界与偏差消息通过；无 speech-rate 透传 |
| WI-04 | 改 scene-plan 产物与验收 | WI-01 | 新字段必填、旧字段拒绝；段落覆盖、素材身份、论文关键图与审稿仍有效 |
| WI-05 | 删除 beat 时间对齐链 | WI-04 | 生成与验收没有 beats / beat_count；cue-only 模板文件、cue 定位和字幕模式通过 |
| WI-06 | 最小调整 composition 与 handoff | WI-01、WI-04、WI-05 | 单次派发可发现模板，agent 自己落地 template、pattern 与演法；不读取已移除字段 |
| WI-07 | 清理模块 / 阶段说明与文档测试 | WI-02 至 WI-06 | Jay、Phase 6 / 7 / 8、两份 handoff 与 overlay 顺序一致，旧正向 beats 断言被替换 |
| WI-08 | 集成验收与实施记录 | WI-03 至 WI-07 | 聚焦测试、完整回归、CLI fake workflow、人工内容检查和范围审查有证据 |

实施建议：先加失败用例，再做最小实现。WI-04 / WI-05 / WI-06 必须作为同一个完整契约变更验收，不能交付“脚本不再写 beats，但下游仍要求 beats”或“说由 composition 选模板，但 handoff 把未选写成不用”的半成品。

### 4.1 Checklist：实施前

- [x] 确认当前分支、远端与无未提交改动，并安全同步远端 main。
- [x] 按同步后的代码重新定位评论，确认 template_scene 已在新主线移除。
- [x] 梳理 writer → 状态校验 → timing → handoff → composition → Jay / 测试的影响链。
- [x] 比较新字段结构、保留 cues 和模板选择交接方案，写出推荐方向与范围边界。
- [x] 实施前再次检查 HEAD / 本地改动，保留其他参与者的新改动；有变动先更新受影响计划项。
- [x] 准备并激活项目 `.venv`，确认 pytest、ffmpeg / ffprobe、Node 和所需测试依赖可用。

### 4.2 Checklist：功能与契约

- [ ] 标准 / 论文模式开头三句内有具体钩子，不靠自我介绍、空泛预告或堆砌术语。（指令已就位；未用真实例稿做内容验收，见 5.3）
- [ ] 剧情、数字、对照、风险与结果都能回溯 brief；假设场景明确标注；开头悬念在正文兑现。（内容验收待做）
- [x] 所有稿长判据按 7 字符/秒计算，标点计数、所有空白不计，目标只来自 inputs.duration。
- [x] 1 / 3 / 5 分钟与 ±15% 内外边界通过；错误消息里的 target / chars/s 同步更新。
- [x] Phase 7 不传固定 speech-rate；未改变真实 TTS 后端默认值与 fake 独立速度。
- [x] 每个完整 scene 有非空字符串 intent / content_plan，且内容规划不是 intent 的复述。（结构由测试强制；是否复述属内容验收，见 5.3）
- [x] 三个已移除字段即使为空也被拒绝，错误指出字段 / scene / 重做责任。
- [x] scene-plan 仍覆盖全部段落；无素材候选为空；论文关键图候选与实际展示要求保留。
- [x] timing 输出和 summary 不再带 beats / beat_count；残留 beats timeline 不被默默验收。
- [x] cue-only template-cues 不要求 content_plan；段落 / cue / 词表映射 / 字幕生成仍正常。
- [x] composition handoff 能区分未选模板与不用模板，始终有模板发现入口。
- [x] composition agent 自己写 inputs.template；完成校验不接受遗漏字段，兼容性检查仍有效。
- [x] template / pattern / 动作不由 script 指定；storyboard 记录选择与重大偏离理由。
- [x] Jay 动作库与防重叠、模板真实锚点、字体、layout 区域及现有渲染 QA 未被削弱。
- [ ] 现有工作区按需 refresh 委派包，刷新前检查自定义副本；不自动迁移或删旧产物。（代码与文档已支持；本仓库没有需要刷新的旧工作区）

## 5. 验证计划

### 5.1 自动化检查（实施后执行）

在仓库根目录，用现有约定的解释器和 venv：

```bash
source .venv/bin/activate && python3 -m pytest -q \
  tests/test_video_contract.py \
  tests/test_pipeline_status.py \
  tests/test_align_narration.py \
  tests/test_prepare_handoff.py \
  tests/test_voice_subtitles.py \
  tests/test_phase_docs.py \
  tests/test_template_cues.py

source .venv/bin/activate && python3 -m pytest -q

git diff --check
```

新增 / 替换的重点测试：

- intent / content_plan 缺失、空字符串、只有空白、非字符串 → Phase 6 corrupt；正常规划通过并可按既定 gate 审稿。
- 三个删除字段各自携带正常内容、空列表或 null → 明确拒绝；不建立“旧 beats 仍通过”的兼容测试。
- 旧 timeline beats → Phase 7 corrupt；新 timeline 仅有段落 / scenes / cues，summary 没有 beat_count。
- 带 / 不带 cues 的新规划都能 timing；匹配不到 cue 时仍有清楚 warning，字幕模式不写 Phase 7 timeline。
- 直接 timing 处理只有 scene_id / paragraphs / cues 的 composition 文件成功，不受完整 scene-plan 的新必填字段阻塞。
- template 缺失可生成未选择 handoff，null 显示不用，合法名称列选中说明；非法 / 不兼容名称在写副本前失败；完成产物齐备但 template 未落地仍不通过 Phase 8。
- template / pattern 决策变化只影响 Phase 8，不让 Phase 6 / 7 因 inputs 视觉字段变化 stale；修改 scene-plan 仍按现有依赖使下游重做。
- script handoff 不读取模板目录 / pattern 推荐；composition handoff 读取模板总览；refresh 更新基础指令，默认仍保护编辑过的副本。

### 5.2 真实入口的确定性小流程（实施后执行）

在测试临时目录构建一份标准无网络素材项目：duration 为 1 分钟、显示稿约 420 字符、合法 lexicon 和新 scene-plan。由测试执行现有脚本，不调用真实模型：

1. `make-narration.py` 生成朗读稿 / 偏移表，`pipeline-status.py` 验收 Phase 6。
2. `voice-subtitles.py <ws> --backend fake` 生成本轮音频 / transcript / timeline，检查无 beats；fake 时长不要求等于目标分钟数。
3. `prepare-handoff.py <ws> composition` 在 template 尚未选时成功；读取生成的真实 handoff，模拟 agent 决定合法 template 或 null 后更新 inputs，验证视觉前置检查。
4. 按 handoff 的原始 `align-narration.py --mode subtitles` 命令生成字幕；再用 cue-only 文件运行 timing 到 composition 专用文件。
5. 比较 Phase 7 timeline 前后的内容哈希，确认 composition 的两次对齐都没有覆盖它。

这段流程验证交接与命令契约，**不冒充真实 composition agent 的设计质量验证，也不冒充完整视频渲染**。测试可以模拟 agent 写回 template，但生产流程不得让 prepare-handoff 自动代选模板。

### 5.3 人工内容验收与最终范围审查

- [ ] 分别审读标准技术解说、论文解读、素材不足三类例稿的前三句，确认张力真实、价值具体、承诺可兑现。
- [ ] 抽查 content_plan 是否同时给出内容对象和演绎方向，且未偷渡 module 名、屏幕文本或动作时间。
- [ ] 抽查 composition storyboard：能从 intent / content_plan 理解决策，模板和 pattern 由 composition 自行选用，重大偏离有理由。
- [ ] 文档测试只证明契约被写清楚；不能拿“包含钩子关键词”当成吸引力或留存验证。
- [ ] 搜索生产 scripts / references / modules 中已移除字段，只允许拒绝规则、禁止说明和负向测试；不残留写入、读取或映射分支。Jay / 模板固有动作名（question、idea 等）不是已移除 schema，不能误删。
- [ ] 完整回归通过；若真实 TTS、实际 agent 执行或渲染未跑，明确记录而非宣称全部验证。
- [ ] 最终 diff 只覆盖本计划必要范围；更新实施记录、命令结果与偏差，不自动提交或 landing。

## 6. 本轮调研 / 文档验证记录

- 已完成：远端 fetch 与安全快进，确认 HEAD 和 origin/main 完全一致；读取同步后的相关文档、脚本和测试；完成外部开场参考调研与方案比较。
- 已完成：新增本计划；新文件 diff 的空白检查通过，Markdown 代码围栏成对；用 jq 校验 JSON 示例结构及无已移除字段，并核算 7 字符/秒的目标与误差边界；全部 47 处本地文件链接与行号范围有效。

## 7. 实施记录

已按本文实施，改动尚未提交。实际做法与本文的差异都属缩小范围的取舍，没有对本文结论做反向变更：

| 项 | 实际结果 |
| --- | --- |
| 开场钩子 | script 包新增「开场钩子（所有模式共用）」：一句白话定义 + 三句结构 + 10 种方法骨架 + 自检；标准模式与论文模式的 Hook 都指向它；自检要求三句内有钩子 |
| 稿长 | `CHARS_PER_SECOND = 7`；文档 / 判定 / 错误消息 / fixture 均为 7、420、2100；`fake_backend` 的 7.5 与 voice-clone 的 `--speech-rate` CLI 保留（见 2.3 的范围区分）；新增一条回归断言“统一入口不传 `--speech-rate`” |
| 新字段 | `intent` / `content_plan` 改为必填非空字符串（比本文的“intent 保留原状”更严）；`cues` 保留并仍是唯一被对齐器读取的 scene 字段 |
| 旧字段 | `video_contract.REMOVED_SCENE_FIELDS` 集中声明，完整 scene-plan 与 composition 的 cue 文件共用同一条拒绝规则；对齐器、状态脚本、completion 校验都拒绝 beats |
| timeline | 不再生成 beats / beat_count；带 beats 的旧 timeline 明确打回，不默默接受 |
| 模板选择 | 按 2.6 方案：layout 仍由主 agent 在 8.0 写回；`template` 缺失时 `prepare-handoff` 仍能生成 handoff，并写“未选择（由本阶段决定）”；agent 写回模板名或 null 后 Phase 8 才能通过；已写但不合法 / 不兼容仍在准备时失败 |
| handoff | composition 的 Required References 永远包含 `modules/templates/templates.md`，已选模板的文档 / JSON 另列；script 仍不读模板目录 |
| Jay | 动作库去掉“对应 beat”列，通用演法改为按旁白时刻自选动作；动作、时长、嘴型与防重叠规则不变 |
| 额外小改 | Phase 1 的“模板是 Phase 8 的画面选择”改为“由 Phase 8 的 composition agent 决定”；委派约定补充“规则更新后按需 `--refresh`” |
| 未做 | 未改 design / layout JSON、模板 HTML、Jay HTML、TTS / ASR 实现、素材抓取与 catalog；未新增 storyboard schema、模板评分器或新的渲染 QA 指标 |

验证证据：

- 全量测试通过：`source .venv/bin/activate && python3 -m pytest -q` → 1145 passed。
- 真实入口小流程（临时工作区，fake TTS）逐项确认：Phase 6 completed（带 `content_plan`）且带 `beats` 被拒；Phase 7 timeline 的键为 `cues,paragraphs,scenes,total_s,version`（无 beats）；`prepare-handoff composition` 在 template 缺省时成功，handoff 写“未选择（由本阶段决定）”并列出 `templates.md`；此时 Phase 8 报 `inputs.json#template: field template is not set`，写入 `null` 后前置条件消失；只含 `scene_id` / `paragraphs` / `cues` 的文件能跑 timing，加了 `beats` 则报“removed field”；subtitle 模式仍能生成字幕单元，且不覆写 Phase 7 的 timeline。
- 未执行：真实 TTS / ASR、真实 composition agent 派发与渲染（需模型与环境）；这三项仍为未验证。
- 未执行：流水线实现、pytest、TTS / ASR、composition agent 派发和渲染。本轮没有项目 `.venv`，未创建环境或安装依赖；这不阻塞计划文档交付。
