# Composition 与模块文档 comments 调研

状态：调研完成；未修改现有指令、契约或代码。

日期：2026-11-12

范围：记录 `references/delegation/composition/base-instructions.md`、`modules/`、委派 handoff 与相关测试中本轮 comments 提出的问题。结论按“现状 → 问题 → 建议”整理；文末给出统一的模块文档职责和待决策项。

## 一、总结

本轮调研支持这些结论：

1. composition 基础指令的问题主要是**表述和文档职责分散**，不是缺少总体规则。
2. 组件已经有明确的“安装 / 挂载参数 / `window.VIDEO` 数据 / 时间约定”文档，只是这些入口分散在 `modules.md`、`components.md`、组件文档、layout 文档和模板文档里，handoff 只固定列了组件目录，导致“组件怎么使用”不容易一次找到。
3. `modules/modules.md` 不是 Python 脚本读取的行为契约；它由 `prepare-handoff.py` 放进 handoff 的 Required References，给 composition agent 阅读，且测试固定要求它排在委派包基础指令之后、design 文档之前。
4. 模板不用的情况已有契约支持：composition agent 必须显式写 `template: null`。但“先决定模板”的措辞容易让“无模板分支”不够醒目，应该改成“决定是否使用模板”。
5. layout 在 `08-composition.md` 的 8.0 由主 agent 选定、写回 `inputs.json`，再生成 handoff；composition agent 的工作顺序不应该把 layout 当成它自己的待选项。若模板不兼容，应写 `template: null` 或把“改 layout”的请求交回主 agent。
6. 场景表现方式目前没有一份独立的总要求。它由 `scene-plan.json` 的叙事内容、composition 基础指令、patterns、`motion.md`、design/layout 约束、storyboard 和 Phase 9 QA 共同约束；但没有一处明确汇总“可以用 SVG 动画、鼓励有创意、必须符合主题风格、内容必须来自已核实材料且不得捏造”。
7. `/hyperframes-animation` 目前只有两处精确引用： `modules/motion.md` 和 `references/phases/08-composition.md`；本环境可用 skill 列表里也没有该 skill。相关索引文件名 `rules-index.md`、`blueprints-index.md`、`transitions/overview.md`、`transitions/catalog.md`、`techniques.md` 只出现在 `motion.md`。
8. 顶层索引文档确有重复和职责混杂。`modules/modules.md` 同时是总目录、组装流程、数据约定、时间约定和扩展规则；各分类入口（designs/layouts/templates/components/patterns）有目录但没有统一的“怎么挑选、怎么使用具体模块”章节；`designs.md` 同时还是 token 契约、字体维护指南、主题选择指南和备选配色草案。
9. 具体 design 文档和 JSON 的重复较多，但有机器约束：JSON 的 `tokens` / `min_font_px` / `fonts` 被 check-composition、fonts-download 和状态指纹使用；`caption_font_px` 目前只在契约测试里直接消费。design 文档里的 token 表、CSS 代码块和 JSON 是同值重复，现有测试强制 CSS 与 JSON 一致。
10. `transitions` 提升为顶级分类是合理的文档架构调整。它当前嵌在 `components/transitions/`，但概念上它是跨场景交接机制，不是普通内容部件。由于组件没有机器注册表，移动目录主要是文档、引用和测试同步，不改变 `data-composition-id="tile-wipe"` 或 HyperFrames 挂载方式。

## 二、各 comment 调研

### 1. 基础指令开头“五部分约束”不清楚

**Comment：** `base-instructions.md` 开头把“输入契约、必须参考 design、必须遵守 layout 区域、内容演绎与模板选择、模板时间锚点”一次性写在长破折号里，不容易读清。

**现状：** 文档本身确实只有这五类约束和一条工作顺序，见 `references/delegation/composition/base-instructions.md:7`；后续章节标题与这五类基本对应。

**问题：** 问题在表达形式。连续长破折号导致读者要自己切分五类，且“工作顺序”和“约束”混在一起。

**建议：** 改成显式编号或表格，例如：

```markdown
本指令只规定以下五类约束，另附一条工作顺序：

1. 输入契约
2. 必须参考 design
3. 必须遵守 layout 区域
4. 内容演绎与模板选择
5. 模板时间锚点
```

“除此之外没有别的规则”保留，仍然用来声明 scene 切分、模板/pattern、素材摆法、Jay 演法与动效属于执行 agent 的设计空间。

---

### 2. layout 缺少统一选择说明；示意图与 JSON 的关系；`portrait` / `presenter` 维度混乱

#### 2.1 选择说明

**Comment：** 希望像 `designs.md` 一样有一个地方说明 `presenter` / `stage` / `portrait` / `portrait-3x4` 怎么选。

**现状：**

- 目前选择规则散落在 `references/phases/08-composition.md:69`：横屏按是否需要画面人物选 `presenter` 或 `stage`，竖屏按画布比例选 `portrait` / `portrait-3x4`。
- 各 layout 文档只描述自己的区域，没有 `layouts/layouts.md` 目录。
- `modules/modules.md` 只有模块目录和分层，不是具体选择指南。
- `designs.md` 相反，已有“现有主题”和“用户说 → 选哪个”的选择表。

**问题：** 每个分类入口应当说明“这类模块是什么、有哪些具体模块、怎么挑、怎么使用具体模块”。layouts 目前缺前三者中的“怎么挑”。

**建议：** 新增 `modules/layouts/layouts.md`，内容只保留：

- layout 是什么；
- 现有 layout 目录；
- 选择表：`orientation` + 是否需要画面人物 + 模板兼容约束；
- layout 与模板、`orientation`、reserved 组件的关系；
- 指向具体 `<layout>.md/.json` 的入口。

Phase 8 文档和 composition 基础指令只需要指向这份 layouts 目录，不再重复一套规则。

另有一个相邻问题：`08-composition.md:69` 说横屏“有人讲解”时选 `presenter`。这条线上所有视频都有解说配音，容易让 agent 每次都选 presenter。建议改成更明确的分界：

- 用户明确要求画面中出现主持人 / Jay → `presenter`；
- 否则默认 `stage`。

#### 2.2 Markdown 示意图与 JSON 是否都必要

**Comment：** layout 的 `.md` 已经有示意图；`.json` 是否还必须存在？

**结论：当前必须保留 JSON。** 它不是示意图的副本，而是多处脚本读取的机器契约：

- 注册与校验：`scripts/video_contract.py:210-246` 只把“有 JSON 且有对应文档”的 layout 视为注册；`layout_file_problem` 读取 `canvas` / `regions` / `caption`。
- 字幕切分：`scripts/align-narration.py:356-380` 从 JSON 的 `caption` 读取宽度、字号和行数。
- 区域检查：`scripts/check-composition.py` 用 JSON 判断内容是否越界、是否侵入 reserved 区域。
- handoff：`scripts/prepare-handoff.py:309-321` 把 layout JSON 列为必需引用。
- 状态判断：`scripts/pipeline-status.py:834-885` 校验 layout 是否注册、画布是否与 `orientation` 一致；`scripts/pipeline-status.py:1556-1568` 把 layout JSON 纳入 Phase 8 上游指纹。

**建议：** 保持 JSON 为唯一数值来源；Markdown 示意图继续承担人读和视觉解释。现有 layout 文档声称 Markdown 数值与 JSON 必须一致，但当前测试主要校验 JSON 本身和引用行为，未找到逐项比较 Markdown 区域表与 JSON rect 的测试。后续应补一致性测试，或从 JSON 生成 Markdown 区域表，避免长期双源手改。

#### 2.3 `portrait` / `presenter` / `stage` 是不是同一维度

**Comment：** `portrait` 和 `presenter` 不是一个维度；portrait 是否也能有 presenter / stage？

**结论：comment 的判断是对的，但当前代码把 layout 定义成“完整预设”，不是两个维度的组合。**

- `orientation` 在 Phase 1 已确定；`inputs.json` 的 `layout` 在 Phase 8 才确定。
- 现有四个 layout 是四个完整配置：`presenter` / `stage` 是 1920×1080 横屏预设，区别是有无人物区；`portrait` / `portrait-3x4` 是 1080×1920 / 1080×1440 竖屏预设，目前都是无主持人和无顶部导航栏。
- 因此“竖屏 + 人物”在概念上可行，但当前库没有对应 layout；`portrait` 并不能通过现有参数组合出人物区。
- 当前命名把“画布朝向”和“是否有人物”混在同一层级，确实容易误导。

**建议分两步：**

1. **短期：** 保留现有四个扁平 layout id，但在 `layouts.md` 明确它们是“完整预设”，不是可自由组合的维度；需要竖屏人物时新增一个明确命名的 layout，例如 `portrait-presenter`。
2. **长期（有真实需求再做）：** 把 `orientation`、人物模式、界面条配置拆成独立维度。代价较大，会影响 `inputs.json`、layout JSON、模板 `supported_layouts`、状态指纹和 handoff；不建议在当前没有需求时先做。

---

### 3. 组件使用规则不应该堆在 composition 基础指令里

**Comments：**

- “layout 怎么使用组件，不应该在 common instruction 里面写。”
- “组件怎么使用在哪里指定了？”
- 组件命令如“嘴型数据用 xxx 生成”应归组件文档。

**现状与结论：组件用法已经有分层位置，但入口不够集中。**

- 总约定：`modules/modules.md:91-120` 说明“把组件 HTML 拷到 compositions/、按各自文档拷资源、加挂载点、写 `window.VIDEO`”，并解释 `data-variable-values` 与 `window.VIDEO` 两种内容通道。
- 目录：`modules/components/components.md:11-27` 有组件目录、层级、默认数据键和共同约定。
- layout：`modules/layouts/presenter.md:31-42` 用“由谁填”指定 reserved 区域对应组件。
- 组件文档：每个组件都有“安装 / 挂载参数 / 数据 / 限制”；Jay 已在 `modules/components/jay/jay.md:53-64` 说明复制和挂载，在 `jay.md:75-89` 说明 `VIDEO.jay`，在 `jay.md:160-172` 说明 envelope 生成。
- 模板文档：`modules/templates/github/github.md:62-69` 给 GitHub 模板下各组件的参数和数据。
- 时间换算：`base-instructions.md:48` 只说组件数据时间用视频秒、场景内参数用相对秒；这不是完整的组件使用说明。

**问题：**

1. 基础指令第三节在 `base-instructions.md:29` 直接写了 presenter 必须挂 Jay、Jay 通用演法和 envelope 命令，导致组件知识出现第二份来源。
2. 基础指令第四节 `base-instructions.md:37` 又重复“Jay 按 `jay.md` 的通用演法”，与第 29 行重复。
3. handoff 的 Required References 最后只固定列出 `modules/components` 目录，不单独列 `components/components.md`；测试还固定了这个行为（`tests/test_prepare_handoff.py:561-574`）。

**建议职责归位：**

- `base-instructions.md` 只保留跨组件不变量：遵守 layout 的 content/reserved 区域、reserved 区域只放指定组件、组件时间数据用视频秒。
- `components.md` 说明组件是什么、怎么从目录选具体组件、统一挂载入口指向各组件文档。
- 每个组件文档保留安装、参数、数据、派生数据命令。
- `presenter.md` 说明有人物区时 reserved 区域由 `jay` 填；但 Jay 怎么挂、怎么给数据，指向 `jay.md`。
- `github.md` / `github.json` 说明模板支持 `presenter` 及 GitHub 专属组件参数和演法叠加。
- handoff 的 Required References 建议把 `components/components.md` 明确列出，而不是只列 `modules/components` 目录。

`base-instructions.md:29` 的现句可改成类似：

```markdown
- 所有元素只放在所选 layout 的 content 区域；reserved 区域只放其 `component` 指定的模块。组件的安装、挂载参数和数据格式见 `components/components.md` 及对应组件文档。
```

Jay 的 envelope 命令放在 `jay.md`，必要时在那里补一条 composition 场景示例：

```bash
node modules/components/jay/make-envelope.mjs voice_clone/narration.mp3
```

---

### 4. `modules/modules.md` 在哪里被读入和引用

**Comment：** 这份文件在哪里被读入和引用？

**结论：它被 composition agent 通过 handoff 阅读；不是 Python 执行契约。**

调用链：

1. `scripts/prepare-handoff.py:379-422` 在生成 composition plan 时把 `modules/modules.md` 写进 Required References。
2. `references/delegation/composition/handoff-template.md:17` 明确 Required References 的顺序包含 `modules.md`。
3. `prepare-handoff.py` 会把 `modules/`（不含 `examples/`）复制到工作区；composition agent 读的是工作区副本，见 `references/phases/08-composition.md:89-95`。
4. composition 基础指令在组装画面时要求读 `modules/modules.md`，见 `base-instructions.md:58`。

测试证据：

- `tests/test_prepare_handoff.py:561-574` 固定 Required References 顺序：基础指令 → `modules/modules.md` → design → layout → 模板目录 → 模板 → patterns/components。
- `tests/test_prepare_handoff.py:631` 校验 `modules.md` 副本字节与库文件一致。

因此它没有被 Python 解析为 schema，也不是运行时依赖；它是 composition 委派包的必读入口文档。

---

### 5. 场景表现方式怎么生成：SVG、创意、风格、事实准确性

**Comments：** 这两条分别在“内容演绎与模板选择”和“组装画面”处提出同一个问题：哪里有说明场景表现方式怎么生成？例如 SVG 动画、有创意、符合风格、准确说明内容、不捏造事实。

**现状：相关约束存在，但分散，且没有一份总要求。**

已有来源：

- `scene-plan.json` 只到叙事层：`intent` / `content_plan` / `facts` 说明讲什么、怎么展开；script 基础指令明确不写模板、pattern、组件、layout、屏幕文字和动画参数（`references/delegation/script/base-instructions.md:92-115`）。
- composition 基础指令把 scene 切分、模板/pattern、素材摆法、Jay 演法和动效选择留给执行 agent（`base-instructions.md:7`、`31-39`）。
- patterns 给“适用场景、摆法、动效候选”（`modules/patterns/patterns.md:39-44`）。
- `motion.md` 给动画选择顺序、runtime 和全局运动原则（`modules/motion.md:18-62`）。
- design 文档给风格、token、动效节奏；layout 文档给区域边界；storyboard 要记录模板/pattern/组件选择；Phase 9 vision QA 检查画面是否相符、是否符合所选 design（`references/phases/09-check-mix.md:82-91`）。
- 事实准确性在上游约束很强：research / script 阶段要求所有关键事实可追溯到 brief；composition 模板锚点要求没念到的字段不编时间、事实缺失不编值（`base-instructions.md:49`）。

**缺口：**

1. 没有一个 composition 层面的统一要求，明确“视觉表现可以有创意，但内容不能超出 `research-brief.md` / `script.txt` / catalog 支撑的事实”。
2. 没有要求 storyboard 每个 scene 明确“视觉机制如何表达这段事实”。现在只要求记录内容区域、模板/pattern/组件选择与偏离理由。
3. SVG 只在 motion 能力索引和 chart pattern 中作为候选出现，没有被上升为“可选择的表现机制”。
4. 创意没有统一边界。当前有动效原则，但没有明确“创意不能破坏主题、可读性和事实准确”。
5. 用户专项要求有通道：`inputs.json.composition_requests` 会原样进入 handoff，但没有在基础指令里把它和通用质量要求分开。

**建议新增一节“场景表现与事实边界”**，放在 composition 基础指令中，内容保持通用：

- 表现方式可以从 scene 语义出发选择 DOM / SVG / Canvas / CSS / WebGL / 混合实现；先选表达机制，再选 runtime，不为炫技堆效果。
- 视觉创意服务于理解：一个 scene 选一个主打机制，设计 token、layout 区域和可读性优先。
- 所有屏幕上的事实、数字、实体、引文必须能追溯到 `research-brief.md`、`script.txt` 或 `material-catalog.json`；素材 catalog 不支撑的视觉论断不能上屏。
- 图示、类比和示意可以用于解释，但不得伪装成证据；会改变事实含义的构图、标注和动画不用。
- storyboard 每个 scene 增加三项：表现意图、主打机制（含 SVG/GSAP/Canvas 等实现判断）、事实来源。用户提出的 SVG、创意等专项要求写入 `composition_requests`。

不建议把“必须 SVG 动画”写成全局规则；它是实现候选，不是普适质量要求。

---

### 6. 没有合适模板时是否需要跳过选模板

**Comment：** 如果没有合适的模板，是否要跳过选模板？

**结论：已有支持，但措辞需要更明确。**

现有约定：

- `base-instructions.md:35` 说“能配就用；不命中就不用”。
- `base-instructions.md:55` 说“决定用哪个模板或不用”。
- `modules/templates/templates.md:29-31` 说明 template 可为 `null`，并警告不要为了套模板改主题/叙事/朝向/design。
- `08-composition.md:73` 要求 composition agent 最终必须写回模板名或 `null`；缺省不算完成。
- `pipeline-status.py` 会检查 `inputs.json.template` 是否写入、模板是否存在、模板 `supported_layouts` 是否包含当前 layout。

**问题：** “先决定模板”容易被读成必须选一个模板；“不命中就不用”藏在长句里，执行路径不够醒目。

**建议统一改成“决定是否使用模板”：**

1. 有适配当前内容、layout 和用户要求的模板：选模板并读其 `<t>.json` 与 `<t>.md`。
2. 没有适配、内容不匹配、`supported_layouts` 不包含当前 layout、或用户要求与之冲突：写 `template: null`。
3. 写 `null` 后跳过模板文档和模板资源，直接从 layout 的 reserved 组件、组件文档和 patterns 继续组装 storyboard。
4. 不改已经确定的主题、叙事、朝向或 layout 去迁就模板。

---

### 7. 写 storyboard 前是否需要选 layout

**Comment：** “先定模板与 pattern，再写 storyboard”这一段是否需要选 layout？

**结论：composition agent 不需要重新选 layout；它收到的是上游已经选定的 layout。**

调用链：

- Phase 8 的 8.0 由主 agent 根据 `orientation`、用户要求和内容选择 layout，并写回 `inputs.json.layout`，见 `references/phases/08-composition.md:64-75`。
- `prepare-handoff.py composition` 在校验 layout 后把它写进 handoff Inputs 和 Required References。
- composition 基础指令使用“当前 layout / 所选 layout”，不是“从库里挑一个 layout”。
- 状态脚本会在 Phase 8 校验 layout 注册、画布与 `orientation` 一致、模板兼容当前 layout。

**建议：** 工作顺序改为更准确的：

1. 确认 handoff 中已选定的 layout，并读取它的 `.md/.json`；
2. 决定是否使用模板；
3. 选择所需组件和 pattern；
4. 写 storyboard。

若 agent 认为 layout 本身选错，不应在本步骤悄悄改 `inputs.json.layout`；应报告主 agent，由主 agent 按 Phase 8 规则处理。若只是模板与 layout 不兼容，则写 `template: null` 或选择兼容模板，不为了模板改已确定约束。

---

### 8. 删除已不存在的 `/hyperframes-animation`

**Comment：** 现在没有 `/hyperframes-animation` skill，去掉所有相关引用。

**全仓精确搜索结果：**

- `modules/motion.md:9`：要求先加载 `/hyperframes-animation` 并读取 `rules-index.md`、`blueprints-index.md`、`transitions/overview.md`、`transitions/catalog.md`、`techniques.md`。
- `references/phases/08-composition.md:62`：composition agent 使用 `hyperframes`、`hyperframes-cli` 与 `hyperframes-animation` skills。

本线程可用 skills 里确实没有 `hyperframes-animation`。

**建议：** 不只是把名字删掉，还要处理它带出的五个外部索引文件名；否则 motion.md 会留下悬空路径。建议：

1. 从 `motion.md` 的能力发现流程移除 `/hyperframes-animation` 及上述五个索引项。
2. 保留 `motion.md` 的动画选择顺序、runtime 表和全局运动原则；如仍需能力发现入口，改指向当前真实存在的 HyperFrames 文档或只写“以当前 HyperFrames skill / 项目文档为准”。
3. 从 `08-composition.md` 的技能列表删除 `hyperframes-animation`。
4. 更新相关文档测试。

相邻但未包含在本 comment 原文中的项：`modules/motion.md:16` 还引用了 `/hyperframes-keyframes`。当前线程可用 skills 也没有这个 skill。建议另行确认后处理，避免误删仍存在的工具名。

---

### 9. `designs.md` 开头不需要强调“不管内容，不管版面”

**Comment：** 不用强调“不管内容，不管版面”。

**现状：** `modules/designs/designs.md:3` 写了“它不管内容，也不管版面，所以所有类型的视频、所有场景都能用”；具体主题文档开头也重复了类似句子（如 `default.md:5`、`github.md:5`、`producthunt.md:5`）。

**结论：** 这句的功能是防止 agent 把主题选择当内容/版面决策，但否定式表达确实显得啰嗦。删掉不影响模块职责，因为职责可以正面表达。

**建议统一改成正面说法：**

```markdown
设计主题规定配色、字体、字号、背景、形状、图标风格和动效节奏，适用于所有类型的视频和场景。
```

同时从具体主题文档删掉重复的“这份文档只规定外观……”。

---

### 10. 顶层索引文档与 design 文档是否过度冗余、如何重构

**Comment：** `designs/designs.md`、各主题 `<design>.md/.json`，以及 `layouts/layouts.md`、`templates/templates.md`、`components/components.md`、`patterns/patterns.md` 这类索引是否有太多重复，是否需要按“模块是什么、有什么、怎么挑、怎么用”重构。

#### 10.1 现状盘点

当前各索引的长度：

| 文档 | 行数 | 当前承担的内容 |
| --- | ---: | --- |
| `designs/designs.md` | 164 | token 契约、机器 JSON、字体维护、主题目录、选择表、备选配色草案 |
| `designs/default/default.md` | 192 | 主题气质、token 表、对比度、CSS 代码块、字体、字号、背景、形状、图标、通用元素、动效、do/don't |
| `designs/github/github.md` | 213 | 同 default，另有 slate 变体和纸纹生成说明 |
| `designs/producthunt/producthunt.md` | 192 | 同 default |
| `layouts/presenter.md` | 79 | 单 layout 的区域、层级、挂载规则 |
| `layouts/stage.md` | 74 | 单 layout 的区域、层级、挂载规则 |
| `layouts/portrait.md` | 92 | 两个竖屏画布的区域和密度建议 |
| `templates/templates.md` | 31 | 模板职责、现有模板目录、模板文件结构、`supported_layouts`、选择规则 |
| `components/components.md` | 27 | 组件职责、目录、共同约定 |
| `patterns/patterns.md` | 44 | pattern 职责、目录、使用步骤 |
| `modules/modules.md` | 138 | 总目录、读哪份文档、分层、完整组装流程、数据/外观分离、时间约定、扩展约定 |
| `modules/motion.md` | 62 | 动效能力、runtime 选择、全局运动原则 |

#### 10.2 具体重复在哪里

Design 相关的重复最集中：

1. 每个主题同时有 token 表、`:root` CSS 代码块和 `<design>.json` 三份同值 token。
2. 三个主题的“字体 / 字号阶梯 / 竖屏缩放 / 字号下限 / 背景覆盖 / 卡片面板 / 步骤时间线 / 界面条 / 要做不要做”等大量规则几乎相同，只换主题名或微调。
3. `designs.md` 已解释语义色、字体、运动 token、字号下限；具体主题又重复同类解释。
4. 字体安装说明同时出现在 `designs.md` 和每个主题文档。
5. `caption_font_px` 在 design JSON 中存在并被测试要求与主题文档一致，但全仓没有运行时脚本消费；字幕实际以 layout JSON 的 `caption.font_size_px` 为准。

#### 10.3 哪些 JSON 不能简单删

- `check-composition.py` 读取 design JSON 的 `min_font_px`。
- `fonts-download.sh` 读取 design JSON 的 `fonts` 和 theme token。
- `pipeline-status.py` 把 design JSON 纳入 Phase 8 上游指纹。
- `tests/test_design_contract.py` 强制 JSON token 与主题 Markdown CSS 完全一致。

因此不能为了“精简”直接删 JSON；正确方向是把 JSON 作为机器契约，同时减少同一文档内的同值重复。

#### 10.4 建议的重构边界

统一后的目录职责：

| 文档 | 应该只回答 |
| --- | --- |
| `modules/modules.md` | 模块库整体结构、一次视频如何按模块组装、跨模块不变量 |
| `designs/designs.md` | design 是什么、有哪些、怎么挑、token/字号契约在哪里维护 |
| `designs/<design>.md` | 这个主题的气质、与共享规则不同的例外、背景纹理、token 值/代码、动效节奏 |
| `designs/<design>.json` | 机器契约：tokens、min font、fonts |
| `layouts/layouts.md` | layout 是什么、有哪些、怎么挑、与 orientation/模板/组件的关系 |
| `layouts/<layout>.md/.json` | 单个 layout 的区域、层级、挂载规则；JSON 是数值契约 |
| `templates/templates.md` | 模板是什么、有哪些、怎么挑、与 layout 的兼容关系 |
| `templates/<template>.md/.json` | 模板组装方式、组件参数、专属外观/元素、机器声明 |
| `components/components.md` | 组件是什么、有哪些、怎么挑、统一安装/挂载入口 |
| `components/<component>.md/.html` | 单个组件安装、参数、数据、限制 |
| `patterns/patterns.md` | pattern 是什么、有哪些、怎么挑、怎么用 |
| `patterns/<pattern>.md` | 单个 pattern 的摆法、动效候选、用色 |
| `motion.md` | 跨 pattern 的动画选择原则，不放具体模块目录 |

`modules.md` 应瘦身为“总入口 + 组装顺序 + 跨模块契约”，各分类细节下沉到分类索引；分类索引统一用四段式：

1. 这类模块是什么；
2. 现有目录，含“什么时候用哪个”；
3. 选定后怎么使用具体模块；
4. 扩展/维护规则。

Design 精简建议：

- 短期：删掉具体主题中的 token 表，只保留一份可复制 CSS 块；共享的字号阶梯、基础形状、通用元素规则抽到 `designs.md`；具体主题只写差异和气质。
- 中期：以 JSON 为唯一 token 来源，新增脚本从 JSON 生成 CSS 片段或完整主题 CSS；主题文档不再手维护同值代码。
- 评估删除 `caption_font_px`：确认没有外部工具消费后，从三个 JSON、`designs.md` schema 说明和测试中移除；字幕字号继续由 layout JSON 负责。
- 不把“怎么挑主题”从 `designs.md` 删掉；这是索引文档应该保留的内容。

---

### 11. `transitions` 应提升为与 components/designs 等并列的一类模块

**Comment：** transitions 单独作为一类可复用 module，和 components、designs 等并列。

**现状：** `tile-wipe` 目前是 `components/transitions/tile-wipe`，但各文档已经把它当“scene 交接机制”而不是普通内容部件：`motion.md` 明确转场不在运动指南里；layout 文档把转场列为独立层级；模板也单独说明转场参数。

**代码影响判断：**

- 组件/转场没有机器注册表；Python 只识别 layout/design/template 契约。移动目录不会改变 `data-composition-id="tile-wipe"`、工程内 `compositions/tile-wipe.html` 文件名或 HyperFrames 挂载方式。
- `prepare-handoff.py` 复制整个 `modules/`，所以新目录会自动进入工作区。
- 影响主要在文档路径、handoff Required References、示例 HTML 注释、测试断言和引用完整性检查。

**建议结构：**

```text
modules/
  modules.md
  designs/
  layouts/
  templates/
  components/
    components.md
    jay/
    nav-bar/
    caption-bar/
  transitions/
    transitions.md
    tile-wipe/
      tile-wipe.md
      tile-wipe.html
  patterns/
```

同步修改点：

- `modules.md` 目录树、分层表、组装流程和扩展规则；
- `components.md` 删除 tile-wipe 与“以后的转场放 transitions/”规则；
- 新增 `transitions/transitions.md`：转场是什么、有哪些、什么时候用哪个、怎么挂、时间约定、与其他层级关系；
- `motion.md` 和 patterns 链接改到 `transitions/tile-wipe/tile-wipe.md`；
- `github.md` 和示例文档中的资源路径改到 `transitions/`；
- composition handoff 的 Required References 增加 `modules/transitions` 或明确列出 `transitions/transitions.md`；
- composition 基础指令“再选组件”改为“再选组件与转场”；
- 更新 `tests/test_prepare_handoff.py` 对 Required References 的期望和相关文档测试。

## 三、推荐的修改批次

这批 comments 涉及同一套文档职责，建议按以下顺序实施，避免大范围来回改：

1. **第一批：低风险表达修正**
   - 重写 composition 基础指令开头的“五部分约束”；
   - 在 work order 明确“确认已选 layout”；
   - 把“先决定模板”改成“决定是否使用模板”，显式无模板分支；
   - 删除 `/hyperframes-animation` 精确引用和五个悬空索引；
   - 删除 `designs.md` 及各主题文档中的否定式职责句。

2. **第二批：职责归位**
   - composition 基础指令移除 Jay 专属规则，保留跨组件 layout 不变量；
   - handoff Required References 明确列出 `components/components.md`；
   - 在 `jay.md` 补 composition 场景的 envelope 命令示例；
   - 增加“场景表现与事实边界”，并扩展 storyboard scene 模板。

3. **第三批：模块索引重构**
   - 新增 `layouts/layouts.md`；
   - 把 `modules.md` 的组装细节下沉到各分类索引；
   - 按统一四段式重构 designs/layouts/templates/components/patterns 索引；
   - 把 `transitions` 提升为顶级分类并同步引用。

4. **第四批：design 契约精简**
   - 删除具体主题中的重复 token 表；
   - 抽取共享 design 规则；
   - 评估移除 `caption_font_px`；
   - 决定 JSON 与 Markdown 的一致性策略。

## 四、待决策项

1. layout 继续保留四个扁平预设，还是开始引入 `portrait-presenter` 这类新预设？建议短期保留旧 id、按需新增，不做兼容破坏。
2. 是否现在拆分“画布朝向”和“是否有人物”两个维度？建议等有竖屏人物真实需求后再做。
3. design token 的短中期方案：保留 Markdown CSS 块并由测试对齐 JSON，还是让脚本从 JSON 生成 CSS？后者更干净，但需要新增生成/校验工具。
4. 是否确认 `/hyperframes-keyframes` 也已不存在并一并移除？当前 comment 只明确说了 `hyperframes-animation`。
5. 场景表现要求在 storyboard 中增加多少结构？建议只增加“表现意图 / 主打机制 / 事实来源”三项，不把 storyboard 变成新的重型契约。

## 五、主要证据索引

- Composition 基础指令： `references/delegation/composition/base-instructions.md:7-65`
- Phase 8 与委派： `references/phases/08-composition.md:64-111`
- handoff 模板： `references/delegation/composition/handoff-template.md:17-95`
- 模块总入口： `modules/modules.md:16-137`
- Design 索引与主题： `modules/designs/designs.md:7-126`、`modules/designs/*/*.md`、`modules/designs/*/*.json`
- Layout： `modules/layouts/*.md/*.json`
- Components / Jay / tile-wipe： `modules/components/components.md`、`modules/components/jay/jay.md`、`modules/components/transitions/tile-wipe/tile-wipe.md`
- Patterns / motion： `modules/patterns/patterns.md`、`modules/motion.md`
- handoff 生成： `scripts/prepare-handoff.py:309-422`
- Layout 契约： `scripts/video_contract.py:210-246`、`scripts/video_contract.py:386-410`
- Layout JSON 消费： `scripts/align-narration.py:356-380`、`scripts/check-composition.py`、`scripts/pipeline-status.py:834-885`
- Design JSON 消费： `scripts/check-composition.py:25-26`、`scripts/fonts-download.sh:125-137`、`scripts/pipeline-status.py:1556-1568`
- 相关测试： `tests/test_prepare_handoff.py:544-588`、`tests/test_prepare_handoff.py:1126-1155`、`tests/test_phase_docs.py:570-647`、`tests/test_design_contract.py:42-104`
