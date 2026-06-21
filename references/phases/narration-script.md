### Phase 5 — 生成解说脚本、匹配场景素材并规划屏幕文本块

Phase 5 包含三个步骤：`Phase 5.1 — 撰写解说脚本` 产出 `narration.txt`；`Phase 5.2 — 场景-素材匹配建议` 基于脚本和 `material-catalog.json` 产出 `scene-material-suggestions.json`；`Phase 5.3 — 屏幕文本块规划` 基于已匹配素材产出 `scene-text-plan.json`。

#### Phase 5.1 — 撰写解说脚本

**输入：** Phase 2 的研究 brief + Phase 4 的 `material-catalog.json` + 用户偏好的切入角度与时长。某段自然依赖某个具体视觉素材时，在正文里顺带提到对应的 catalog slug 或资源。**不要**在这里设计 HyperFrames 的 scene、卡片、时间轴或 `info_units`；scene 切分和视觉结构归 Phase 8 的 HyperFrames sub-agent。

目标：

**Paper mode 解说结构**（当 `input_mode = "paper"`）：

解说沿用论文自身的逻辑流，而非通用的主题结构：

1. Hook —— 这篇论文为什么重要 / 它要解决什么问题
2. Background —— 先前的工作和 SOTA（来自 Deep Research）
3. Key insight / approach（来自论文摘要 + 引言，引用论文中的 figure）
4. Method walkthrough（用 `material_ref` 引用论文 figure）
5. Results（用 `material_ref` 引用论文 table / chart）
6. Impact 与后续工作（来自 Deep Research）
7. Takeaway / CTA

论文 figure（`source_type: "paper_pdf"` 条目）是**首选**素材。从 web 抓取的资源作为补充 B-roll。叙述中合适时自然引用图号 / 表号：`"如表一所示..."`。

- 只使用**研究 brief 中的事实**——每个数字、人名、日期和引文都要可追溯。
- 在有用的地方引用收集到的素材，并为每个 scene 标注推荐的视觉资源。
- 3-10 分钟、`speech_rate=1.4` 下约 **7.5 字符/秒** → `3min ≈ 1350 chars`、`5min ≈ 2250 chars`、`10min ≈ 4500 chars`。
- 段间用空行分隔，每段约对应一个 scene = **5-8 秒音频**（在 `speech_rate=1.4` / 7.5 字符/秒下约 37-60 字符/段）。按目标时长伸缩，参考量：3min ≈ 23-36 段、5min ≈ 38-60 段、10min ≈ 75-120 段。
- 数字用中文字符（表示年份的 `二零二六` 而不是 `2026`，表示大数字的 `一万零三百六十五` 而不是 `10365`）。
- **英文复合品牌名里的数字必须展开为单词。**
    - `X2Y` → `X to Y`（`Idea2Video → Idea to Video`、`Text2Image → Text to Image`、`Img2Img → Image to Image`）
    - `X4Y` → `X for Y`（`Search4U → Search for you`）
    - **视觉里仍写原品牌名** `Idea2Video`；只有 narration（给 TTS 的文本）写展开形式
- **大小写混排品牌名按空格读** —— narration 里 `OpenHuman → Open Human`、`AutoCameo → Auto Cameo`，避免被读成首字母拼读。视觉文件保留原写法。
- 英文专有名词保留原文（`Anthropic`、`Claude Code`、`Boris`）。
- **TTS 朗读效果差的常见英文品牌 / 机构名改用中文。** 例如 `NVIDIA` / `Nvidia` → `英伟达`。视觉文件 / 字幕中仍保留原写法，只有 narration（给 TTS 的文本）写中文念法。
- 英文多个单词之间的连字符、下划线、斜杠或反斜杠等改成空格（例如 `GPT-5` → `GPT 5`，`Claude_Code` → `Claude Code`）。
- 数字周围的符号用中文表示（`百分之五` 而不是 `5%`，`负 3` 而不是 `-3`，`约 100` 而不是 `~100`，`200 多` 而不是 `200+`）。
- **避免全角中文冒号 `：`。** 改用破折号 `——`、用逗号断句或者改写。示例：`某品牌：日均消耗一百万` → `某品牌 —— 日均消耗一百万`。
- 如果用户想要社媒风格，最后一段应为 CTA（`点赞、关注、收藏，下期见`）。

仅当用户要求审核脚本时，先展示 `narration.txt`。

存到 `narration.txt`。

#### Phase 5.2 — 场景-素材匹配建议

`narration.txt` 写入后，在进入 Phase 6（TTS）之前，主 agent inline 完成此步骤（无需 sub-agent）。

**输入：** `narration.txt` + `material-catalog.json`

**步骤：**

1. 把 `narration.txt` 按空行切分为段落，按顺序处理。
2. 对每个段落，通读其旁白文本，遍历 `material-catalog.json` 中所有图片和视频 clip 的 `semantic_description`、`width` / `height`、`ratio_bucket`、`layout_affordance` 和可选 `focal_region`，对每个候选素材给出 1-10 的匹配分与理由（理由要对应旁白的具体内容，不要泛泛而谈）。
3. **全局唯一分配**：每个素材（图片 / 视频 clip）最多分配给一个段落。按匹配分做全局贪心分配——分数最高的 (段落, 素材) 配对先定，已被占用的素材不再分配给其他段落；每个段落最终最多得到一个主素材。多素材对比 scene 可额外占用对比素材，但必须写入 `material_refs` 并把数组内每个素材都视为已占用。例外：连续同素材合并或相邻 `media_continuation` 可沿用同一素材作为稳定视觉锚点；拆成多个相邻 scene 时，group 起点标注 `continuation_group_id`，后续 continuation scene 同时标注 `continuation_group_id` 和 `continuation_of`。
4. 为已分配素材选择 `layout_role`。不要因为极端比例就降低语义优先级；但如果素材是 `ultra-wide` / `ultra-tall` / `strip`，或同一 scene 需要多素材对比，必须显式选择 `layout_role` 并写出 `layout_reason`。可选角色：`video_first`、`media_first`、`media_continuation`、`viewport_reveal`、`band`、`detail_callout`、`comparison_pair`、`comparison_sequence`。普通 scene 使用 `material_ref`；同一 scene 内的 `comparison_pair` 或 carousel / 分时 `comparison_sequence` 使用 `material_refs`。
5. 段落在 catalog 中没有可用素材（候选分均较低，或合适素材已被占用且无次优）时，显式标记 `"no_match": true`，**不复用已被占用的素材**，留给纯文字 scene。如果该段只是延续解释上一 scene 的同一主素材，优先标记为 `"layout_role": "media_continuation"` 并沿用该素材作为视觉锚点，而不是普通 `no_match`。
6. **连续同素材合并 / continuation**：相邻段落分配到同一素材（同一图片，或同一视频的同一 clip）且旁白都在讲该素材时，优先合并为一个 extended scene；merged single scene 只需要多个 `text_beats`，不需要 `continuation_group_id` / `continuation_of`。如果为了句子节奏、局部强调或屏幕文本密度必须拆多个 scene，则输出相邻 `media_continuation` scene：group 起点可保留主布局角色并标注 `continuation_group_id`，但不写 `continuation_of`；后续 continuation scene 使用相同 `continuation_group_id`，并用 `continuation_of` 指向 group 起点的 `scene_index`。continuation scene 必须让主素材稳定显示，不得让图片 / 视频长时间消失后再出现。
7. 顺序编号最终 scene（`scene_1`, `scene_2`, ...）并输出 `scene-material-suggestions.json`，结构如下：

```json
[
  {
    "scene_index": 1,
    "material_ref": "img_001",
    "layout_role": "media_first",
    "continuation_group_id": "fig_img_001_walkthrough",
    "layout_reason": "清晰横向大图适合作为主视觉，文本应少量辅助而不是压缩图片",
    "reason": "图中展示了 X，与旁白提到的 Y 直接对应",
    "text_beats": [
      {"narration_excerpt": "前 20 字..."},
      {"narration_excerpt": "前 20 字..."}
    ]
  },
  {
    "scene_index": 2,
    "material_ref": "img_001",
    "layout_role": "media_continuation",
    "continuation_group_id": "fig_img_001_walkthrough",
    "continuation_of": 1,
    "layout_reason": "继续解释同一张技术图，主图保持稳定，只刷新解释文本和局部强调",
    "reason": "这一段继续讲 img_001 中的第二个关键模块",
    "text_beats": [
      {"narration_excerpt": "..."}
    ]
  },
  {
    "scene_index": 3,
    "material_ref": "2MJDdzSXL74:12.0-18.5",
    "layout_role": "video_first",
    "layout_reason": "该片段是核心演示，需要最大化视频可视区域",
    "reason": "该片段演示了 Z 流程，配合旁白对 Z 的描述",
    "text_beats": [
      {"narration_excerpt": "..."}
    ]
  },
  {
    "scene_index": 4,
    "material_ref": "img_010",
    "material_refs": ["img_010", "img_011"],
    "layout_role": "comparison_pair",
    "layout_reason": "两张截图需要同屏对比，material_refs[0] 作为 primary material",
    "reason": "旁白在比较两个界面的差异",
    "text_beats": [
      {"narration_excerpt": "..."}
    ]
  },
  {
    "scene_index": 5,
    "no_match": true,
    "material_ref": null,
    "text_beats": [
      {"narration_excerpt": "..."}
    ]
  }
]
```

**约束：**

- 每个素材（图片 / 视频 clip）最多用于一个 scene，不复用；`material_refs` 中每个素材都算已占用。连续同素材合并或相邻 `media_continuation` 是例外。merged single scene 不需要 continuation 字段；拆成相邻 scene 时，group 起点只需要 `continuation_group_id`，后续 continuation scene 的 `continuation_of` 指向 group 起点的 `scene_index`，并保持视觉连续。
- `no_match` 的 scene 不强行填素材；Phase 5.3 会为它规划更高密度的纯排版信息图 / 文本块，Phase 8 再据此实现。
- `layout_role` 是 Phase 8 的布局决策输入，不是固定模板。`media_first` / `video_first` 仍可有少量文本配合；`viewport_reveal` 必须保留关键区域可见；同一 scene 内的 `comparison_pair` 必须用 2 个 `material_refs`，`comparison_sequence` 只用于同一 scene 内的 carousel / 分时多素材展示，必须用 2 个以上 `material_refs`。若对比内容拆成多个 scene，拆出的每个 scene 使用自己的真实主角色（如 `media_first` / `video_first` / `viewport_reveal` / `detail_callout`），不标为 `comparison_sequence`，并在 `layout_reason` 说明它属于同一对比序列。若同时保留 `material_ref`，它必须等于 `material_refs[0]`。
- `media_continuation` 允许相邻 scene 沿用同一素材作为稳定视觉锚点，只刷新解释文本、局部强调或 `focal_region`；不得把它当作素材复用违规。它主要用于论文 figure、技术架构图、UI 截图、流程图等需要围绕同一图讲多个点的场景。
- 合并 scene 中素材展示可超 8s，但 `text_beats` 仍按原每 5-8s 节奏刷新。

输出到 `scene-material-suggestions.json`（与 `narration.txt` 同级）。

#### Phase 5.3 — 屏幕文本块规划

屏幕文本密度取决于已匹配素材的 `layout_role`、尺寸、比例和语义。`media_first` / `video_first` scene 不是无文本，而是主媒体优先、少量文本辅助；如果文本会压缩或遮挡主媒体，应分时出现、降级、外置，或生成相邻 `media_continuation` scene。

Phase 5.3 在 Phase 5.2 之后、Phase 6（TTS）之前执行。它不重新匹配素材，也不设计 HyperFrames HTML / CSS / 坐标 / 动画；只把已写入的旁白段落和已匹配素材转成结构化的非字幕屏幕文本建议，供 Phase 8 HyperFrames sub-agent 读取、实现和审计。

**输入：**

- `narration.txt`
- `scene-material-suggestions.json`
- `material-catalog.json`

**输出：** `scene-text-plan.json`

**目标：**

1. 让每个 scene 都有清晰的屏幕信息意图，而不是只靠 Phase 8 从旁白临场猜。
2. 让 `no_match` scene 主动变成纯排版信息图，而不是退化成单个大标题卡。
3. 让有素材 scene 生成素材外置的解释文本、callout、data block 或标签，避免遮挡 catalog 素材。
4. 给 Phase 8 提供可记录、可 QA 的 `visual_text_units`，但不越权规定最终 layout。

**`scene-text-plan.json` schema：**

```json
[
  {
    "scene_index": 3,
    "material_ref": null,
    "no_match": true,
    "scene_intent": "用纯排版解释从主题到视频的处理链路。",
    "density_hint": "high",
    "visual_text_units": [
      {
        "unit_id": "scene_3_unit_1",
        "source_text_beat_index": 0,
        "narration_excerpt": "用户输入主题后，系统先做调研，再写脚本，最后交给 HyperFrames 渲染。",
        "visual_role": "process_flow",
        "domain_hint": "technical_explainer",
        "template_hint": "pipeline_steps",
        "display_text": "从主题到视频的四步链路",
        "supporting_points": [
          {"label": "输入", "detail": "主题 / URL / 文本"},
          {"label": "调研", "detail": "Deep Research + web search"},
          {"label": "脚本", "detail": "narration.txt + text beats"},
          {"label": "渲染", "detail": "HyperFrames composition"}
        ],
        "priority": "primary",
        "timing_hint": "appear_with_sentence"
      }
    ]
  }
]
```

字段说明：

| 字段 | 作用 |
| --- | --- |
| `scene_index` | 对齐 `scene-material-suggestions.json` 的 scene |
| `material_ref` / `material_refs` / `no_match` | 透传 Phase 5.2 结果，沿用 `scene-material-suggestions.json` 的字段名；`material_refs` 只用于多素材对比，`material_ref` 保持为 primary / 单素材入口 |
| `layout_role` | 透传 Phase 5.2 的布局角色：`video_first` / `media_first` / `media_continuation` / `viewport_reveal` / `band` / `detail_callout` / `comparison_pair` / `comparison_sequence`；用于控制文本密度和素材展示策略 |
| `scene_intent` | 这场景屏幕信息要帮助观众理解什么 |
| `density_hint` | `low` / `medium` / `high`，影响非字幕信息元素数量 |
| `visual_text_units[]` | 每个建议出现的文本块 / callout / data block / 图示信息单元 |
| `visual_role` | 通用视觉角色，例如 `title` / `callout` / `data_block` / `metric_strip` / `list` / `feature_grid` / `process_flow` / `architecture_diagram` / `network_graph` / `timeline` / `comparison_matrix` / `code_block` / `terminal_block` / `file_tree` / `state_machine` / `annotated_media` / `quote` / `definition` / `qa` / `pros_cons` / `section_divider` |
| `domain_hint` | 可选领域：`github_repo` / `product_hunt` / `paper_reading` / `code_explainer` / `technical_explainer` / `general` |
| `template_hint` | 可选模板提示，例如 `repo_identity_card`、`repo_metrics`、`launch_stats`、`paper_method_pipeline`、`api_sequence` |
| `display_text` | 面向屏幕的短文本，不等同于 TTS 旁白原文 |
| `supporting_points` | 列表项、流程节点、架构组件、关系节点或数据字段 |
| `priority` | `primary` / `secondary` / `decorative` |
| `timing_hint` | 与旁白句子的相对出现关系；最终秒级 timing 由 Phase 8 结合 ASR 决定 |

**Role alignment contract：**

- `layout_role` 是 scene / 素材展示策略，来源是 Phase 5.2 的 `scene-material-suggestions.json`；Phase 5.3 只透传，不重新决定。
- `visual_role` 是单个 `visual_text_units[]` 的信息形态。
- `domain_hint` 只说明内容领域，不参与素材占比或安全区计算。
- `template_hint` 只作弱语义提示，不作模板 ID 或最终 layout 指令。
- Phase 5.3 负责把大表是否拆成多个 `chart` units 规划清楚；Phase 8 只实现已有 `data_table` / `chart` units，只在有 `data_table` / numeric 数据时使用 chart，否则不凭空发明 chart。
- Phase 8 必须先按 `scene_index` join Phase 5.2 和 Phase 5.3，再组合读取 `layout_role`、素材比例、输出朝向、`visual_text_units[]` 和 density / shape，决定最终 layout treatment。

**通用 `visual_role`：**

| `visual_role` | 适用内容 | 常见 `supporting_points` | 出场 |
| --- | --- | --- | --- |
| `leaderboard` | 排名、Top N、榜单、周榜、产品榜、repo 榜 | rank、name、metric、why it matters、optional material ref | 逐个 |
| `product_card` | 产品 / repo / paper / 项目身份卡 | name、tagline、category、metric、CTA | 整体 |
| `big_number` | 单个关键数字、hero stat、冲击性指标 | value、unit、label、context | 整体 |
| `data_table` | 成本表、硬件表、benchmark 表、pricing 表、结构化多行多列表格 | columns、rows、highlighted cells、summary | 逐个 |
| `chart` | 趋势、分布、数值对比、benchmark、成本 / 速度 / 占比可视化 | chart_type、series、axis labels、highlighted points、summary | 逐个 |
| `timeline` | 发布时间线、版本演进、研究脉络、产品发布节奏、项目历史 | 时间点、事件、影响 | 逐个 |
| `process_flow` | 步骤、pipeline、用户旅程、处理链路、方法流程 | step label、输入、输出 | 逐个 |
| `architecture_diagram` | 系统结构、模块分层、技术栈、论文方法组件 | 模块、层、数据流 | 逐个 |
| `network_graph` | 依赖关系、生态、人物 / 组织关系、repo 关联、引用关系 | 节点、边、关系类型 | 逐个 |
| `comparison_matrix` | 竞品对比、before / after、方法对比、优缺点 | 维度、选项、差异 | 逐个 |
| `pros_cons` | 单一主体的正反两面：推荐 / 避免、利 / 弊、正确 / 错误、do / don't | positives、negatives、label | 逐个 |
| `data_block` | stars、upvotes、benchmark、成本、速度、增长率、排名 | label、value、unit、context | 整体 |
| `metric_strip` | 多个轻量指标并列展示 | 指标名、数值、变化 | 逐个 |
| `list` | 功能点、卖点、限制、适用场景、takeaways | item label、detail | 逐个 |
| `feature_grid` | 产品功能、repo 能力、技术模块能力 | feature name、benefit、proof | 逐个 |
| `callout` | 关键结论、风险、反常识、注意事项、亮点 | claim、reason、evidence | 整体 |
| `definition` | 术语 / 概念 + 释义、展开说明 | term、definition、example / note | 整体 |
| `qa` | 问答 / FAQ：问题 + 回答 | question、answer、note | 逐个 |
| `code_block` | API 示例、配置、核心函数、diff 前后对比 | language、snippet、highlight | 逐个 |
| `terminal_block` | 安装命令、运行输出、CLI 工作流 | command、output、status | 逐个 |
| `file_tree` | repo 结构、项目目录、论文代码组织 | path、purpose | 逐个 |
| `state_machine` | 状态流转、任务生命周期、agent loop、错误恢复 | state、transition、trigger | 逐个 |
| `annotated_media` | 图片 / 截图 / figure 上打点、箭头、标注 + 外置解释（论文 figure 为其一） | marker / pin、label、why it matters | 逐个 |
| `quote` | 用户评价、论文结论、作者观点、产品 tagline | quote、source | 整体 |
| `section_divider` | 章节分隔 / 转场标题卡（长视频分段） | chapter label、kicker、index | 整体 |

`出场` 列：逐个 = 条目 / 节点 / 行 / 标注随对应旁白逐个出现，禁止 unit 首次出现时一次性全亮；整体 = 整体出现即可。

**通用触发规则：**

这些规则覆盖不依赖特定领域的基础语义；领域专项触发规则可以继续细化 `domain_hint` / `template_hint`。

1. 旁白出现“第一、第二、然后、最后、步骤、链路、流程” → `process_flow`。
2. 旁白出现“过去、现在、未来、从 X 到 Y、演进、版本、发布、时间线、历史、阶段、里程碑” → `timeline`。
3. 旁白解释“系统、模块、层、pipeline、输入输出、组件” → `architecture_diagram`。
4. 旁白解释“关系、依赖、生态、传播、连接、谁影响谁” → `network_graph`。
5. 旁白有多个并列点、功能点、限制或 takeaway，每项仅 item + 一行 detail → `list`；每项有独立标题 + benefit + proof → `feature_grid`。
6. Top N、排名、榜单、周榜、产品榜、repo 榜 → `leaderboard`。
7. 产品身份、repo 身份、paper identity、Product Hunt item → `product_card` 或现有 `title`。
8. 单个关键数字、hero stat、成本 / 速度 / 显存 / 排名作为 hook → `big_number`。
9. 表格、pricing、benchmark table、hardware matrix、cost table → `data_table`。
10. 趋势、benchmark curve、成本对比、速度对比、占比、分布 → `chart`。
11. 大表中出现多个独立数值维度，且旁白分别讨论这些维度 → 可拆成多个 `chart` units。
12. 旁白包含数字、比例、排名、增长、成本、时长、性能、分数 → `data_block` 或 `metric_strip`；如果是单个冲击性数字，用 `big_number`。
13. 旁白出现“相比、对比、before/after、旧方案/新方案、优缺点、取舍、vs” → `comparison_matrix`。
14. 旁白出现命令、安装、运行、日志、输出、终端、CLI → `terminal_block`。
15. 旁白出现代码、函数、API、配置、diff、片段、参数 → `code_block`。
16. 旁白出现目录、文件、路径、package、模块文件组织 → `file_tree`。
17. 旁白出现状态、生命周期、重试、失败恢复、状态流转、agent loop → `state_machine`。
18. 旁白引用用户评价、作者原话、论文结论、tagline 或明确引文 → `quote`。
19. 旁白是关键判断、风险、反常识、结论 → `callout`。
20. 已匹配素材是图表 / table / figure 时，优先生成外置信息区和解释 callout，不覆盖素材。
21. 已匹配素材是视频 clip 时，生成简短标签 / 状态说明，不做过重图示阻挡主体；若 `layout_role = "video_first"`，文本应控制为短标签、关键数字或一句短结论。
22. `no_match` scene 应至少生成 2-4 个 `visual_text_units`，避免 Phase 8 退化成单个大标题卡。
23. `layout_role = "media_first"` 时，仍应生成少量文本辅助观众理解图片，通常为 1 个短标题 / 标签 + 0-2 个短 callout 或 data point；不得生成压缩主图的大段文本。
24. `layout_role = "media_continuation"` 时，文本应承接上一 scene，只刷新解释重点或局部强调；主素材必须在相邻 scene 中保持稳定显示。
25. `layout_role = "viewport_reveal"` 或带独立文本列的 split 场景，文本列规划 ≥3-4 个 unit 且每个带 detail / value，使文本填满列宽与列高，不只放标题 + 短标签。
26. 旁白出现“所谓、指的是、定义为、即、名词解释、概念” → `definition`。
27. 旁白是“问题 → 回答”、FAQ、常见疑问、Q&A → `qa`。
28. 旁白出现“优点 / 缺点、利弊、该做 / 不该做、推荐 / 避免、do / don't”，针对单一主体的正反两面 → `pros_cons`；多选项多维度对比仍用 `comparison_matrix`。
29. 长视频出现章节切换、“接下来、第 N 部分、下一章” → `section_divider`。

**领域专项触发规则：**

GitHub repo 解析 / GitHub 项目介绍：

1. 出现 `owner/repo`、仓库名、GitHub、开源、stars、forks、issues、PR、license、release → `domain_hint = "github_repo"`。
2. 仓库身份 / 一句话用途 → `visual_role = "title"`，`template_hint = "repo_identity_card"`。
3. stars / forks / contributors / issues / releases / commits → `visual_role = "metric_strip"` 或 `data_block`，`template_hint = "repo_metrics"`。
4. 语言、框架、依赖、技术栈 → `visual_role = "architecture_diagram"` 或 `network_graph`，`template_hint = "language_stack"` / `"dependency_graph"`。
5. 安装、quickstart、命令行 → `visual_role = "terminal_block"`，`template_hint = "quickstart_command"`。
6. 目录、核心文件、monorepo、packages → `visual_role = "file_tree"`。
7. issue → PR → merge、CI、release → `visual_role = "process_flow"`，`template_hint = "contribution_flow"`。
8. 项目历史、版本、最近更新 → `visual_role = "timeline"`，`template_hint = "release_timeline"`。

Product Hunt 产品介绍：

1. 出现 Product Hunt、launch、upvote、maker、rank、product、tagline → `domain_hint = "product_hunt"`。
2. 产品一句话价值 → `visual_role = "title"`，`template_hint = "product_card"`。
3. upvotes、排名、今日榜单、增长 → `visual_role = "data_block"` 或 `metric_strip`，`template_hint = "launch_stats"`。
4. 目标用户、使用场景 → `visual_role = "list"`，`template_hint = "audience_segments"`。
5. 功能点、卖点 → `visual_role = "list"` 或 `comparison_matrix`，`template_hint = "feature_grid"`。
6. 价格、套餐、免费 / 付费 → `visual_role = "comparison_matrix"`，`template_hint = "pricing_cards"`。
7. 竞品 / 替代方案 → `visual_role = "comparison_matrix"`，`template_hint = "competitor_comparison"`。
8. 注册、试用、CTA → `visual_role = "callout"`，`template_hint = "cta_card"`。

论文阅读 / paper mode：

1. 论文标题、作者、会议、年份 → `visual_role = "title"`，`template_hint = "paper_identity"`。
2. 问题、motivation、gap、SOTA 局限 → `visual_role = "callout"` 或 `comparison_matrix`，`template_hint = "problem_gap"`。
3. method、approach、pipeline、framework、algorithm → `visual_role = "process_flow"` 或 `architecture_diagram`，`template_hint = "paper_method_pipeline"`。
4. ablation、benchmark、accuracy、latency、score、table → `visual_role = "data_block"` 或 `comparison_matrix`，`template_hint = "results_summary"`。
5. 匹配素材是论文 figure → `visual_role = "annotated_media"`，外置信息区解释 figure，不覆盖图本身。
6. 匹配素材是论文 table → `visual_role = "data_block"` / `comparison_matrix`，提取最重要 1-3 个结论，不重画完整表格。
7. related work / citations / lineage → `visual_role = "timeline"` 或 `network_graph`，`template_hint = "research_lineage"`。
8. limitation / future work → `visual_role = "list"`、`callout` 或 `pros_cons`，`template_hint = "limitations"`。

代码与技术讲解：

1. 函数、API、SDK、配置、代码片段 → `visual_role = "code_block"`，`template_hint = "highlighted_snippet"`。
2. 命令、安装、运行、日志、测试输出 → `visual_role = "terminal_block"`，`template_hint = "cli_trace"`。
3. 请求、响应、鉴权、数据库、队列、缓存 → `visual_role = "process_flow"` 或 `architecture_diagram`，`template_hint = "api_sequence"` / `"system_stack"`。
4. 状态、生命周期、retry、失败恢复、agent loop → `visual_role = "state_machine"`。
5. 依赖、包、服务关系、调用链 → `visual_role = "network_graph"`，`template_hint = "dependency_graph"`。
6. 性能、耗时、成本、吞吐、错误率 → `visual_role = "data_block"`，`template_hint = "performance_metrics"`。
7. before / after、旧方案 / 新方案、tradeoff → `visual_role = "comparison_matrix"` 或 `pros_cons`，`template_hint = "before_after"` / `"tradeoff_matrix"`。

**选择优先级：**

1. 有明确素材 figure / table / screenshot：先生成素材相关外置信息区，避免挡住素材。
2. 有数字：至少生成一个 `data_block` 或 `metric_strip`。
3. 有步骤 / pipeline：优先 `process_flow`。
4. 有模块 / 系统：优先 `architecture_diagram`。
5. 有实体关系：优先 `network_graph`。
6. 有时间顺序：优先 `timeline`。
7. 只是并列卖点：用 `list` / `feature_grid`。
8. 只是结论或风险：用 `callout`。
9. 有术语需要解释：用 `definition`。
10. 有问答结构：用 `qa`。
11. 单一主体正反 / 利弊：用 `pros_cons`。
12. 长视频章节切换：用 `section_divider`。

每个 scene 不应无限堆角色：

- 有素材 scene：1 个 primary unit + 1-2 个 secondary units。
- `no_match` scene：2-4 个 units，其中至少 1 个多元素 / 结构型 role（`leaderboard` / `data_table` / `chart` / `timeline` / `process_flow` / `architecture_diagram` / `network_graph` / `comparison_matrix` / `pros_cons` / `metric_strip` / `list` / `feature_grid` / `qa` / `code_block` / `terminal_block` / `file_tree` / `state_machine` / `annotated_media`）。
- 密集技术 scene：允许 4-6 个 units，但 Phase 8 可为了安全布局降级 secondary / decorative units。
