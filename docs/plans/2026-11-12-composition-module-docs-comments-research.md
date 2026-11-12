# Composition 与模块文档 comments 调研

状态：已按当前代码重新校准；已落地的 comment 和基于旧契约的建议已移除。剩余工作拆为可独立实施的 tickets，见 [Composition 与模块文档后续改动实施计划](2026-11-13-composition-module-docs-implementation-tickets.md)。

日期：2026-11-12；校准：2026-11-13。

范围：只保留 `references/delegation/composition/base-instructions.md`、`modules/`、委派 handoff 与相关测试中仍需调整的问题。现行 Phase 8 以逐视觉场景的 `composition/scene-config.json` 为准；本文不再描述旧的全片 `inputs.json.template/layout` 流程。

## 一、剩余结论

1. 需要一份统一的模块选择契约：composition 子 agent 先读 scene 与用户要求；只有用户明确指定，或预定义模块与该 scene 特别匹配时才采用模块，否则按 scene 要求即时设计并生成实现。阅读目录不等于采用模块，storyboard 只记录实际借用及匹配理由。
2. templates/layouts 已有接近这条规则的逐场景选择，patterns/motion 已有按需参考规则，但 components/transitions 尚缺统一说明，各索引的“特别匹配”标准也没有统一。design 仍由 Phase 1 预选并预装字体，若要遵守同一策略，需要单独调整 design 输出、handoff、字体安装和状态验收契约。
3. composition 基础指令开头仍可用显式列表改善可读性，但必须保留“各视觉 scene”“逐场景选择”的语义，也不能把视觉设计空间写成不受输入、素材、字体和 QA 约束。
4. layout preset 的 Markdown 与 JSON 仍需同时保留，但两者当前的实际职责不同于旧流程：JSON 用于注册、独立工具入口和 preset 数值来源；最终流水线消费的是 scene-config 中落盘的实际 `regions/caption`。目前缺少 Markdown 区域表与 JSON 的逐项一致性测试。
5. 组件安装、参数、数据和派生数据命令应归组件文档。当前基础指令已经要求先读 `components/components.md`，剩余问题是 Jay 通用演法与 envelope 命令重复，以及 handoff 只列组件目录而未明确列出组件索引。
6. `modules/modules.md` 是 composition agent 的必读入口，不是 Python 解析的 schema。它应继续保存跨模块初始化、adapter、路径、数据和时间约定，不应为了“精简”把这些跨模块契约拆散。
7. 自主构图、视觉隐喻、静态或动态呈现、按需查阅 patterns/motion 已有明确规则。真正剩余的是 composition 层面对“新增屏幕事实不得脱离上游依据”和“示意不得伪装成证据”的统一约束；不需要给每个 scene 强制增加主打机制或新的 storyboard 字段。
8. design 文档的主要冗余是 token 表、CSS 块与 JSON 三份同值，以及重复的安装和职责表述。当前生产脚本直接消费的是 `min_font_px` 与 `fonts`；`tokens` 由契约测试与 Markdown CSS 对齐。`caption_font_px` 没有生产脚本消费者，可以从仓库内契约移除。
9. 不建议为所有分类索引机械套用同一套四段式。现有 layouts/templates/components/patterns 索引已经承担目录与使用入口；应只做有明确重复或缺口的修改。
10. `transitions` 可以提升为顶级模块类别。移动目录不改变组件 id、工程内文件名、数据键或初始化接口，但必须同步浏览器测试中的真实源码路径和 storyboard 的使用表要求。

## 二、剩余 comment 调研

### 1. 基础指令开头“五部分约束”不清楚

**现状：** `references/delegation/composition/base-instructions.md:9` 仍用连续破折号列出五类约束。后续章节已经对应这五类，问题是开头可读性，不是缺少规则。

**当前语义边界：**

- layout 是“各 scene 的实际区域”，不是全片单一预设；
- template 是逐场景借用，`template: null` 与自由布局是正常路径；
- 视觉 scene 切分、构图、素材摆法、动作与动效属于 composition agent 的设计空间；
- 输入、design、真实语音、必用素材、字体和检查要求仍然是约束，不能用“除此之外没有别的规则”否定它们。

**建议：** 将开头改成五项编号列表，并单独引出工作顺序。用“其余视觉设计由 composition agent 决定”替代绝对的“没有别的规则”。保留现有第四部分标题和锚点，避免破坏 patterns/motion 的链接与文档测试。

### 2. layout Markdown 与 JSON 的职责及一致性

**结论：保留 JSON，但按当前调用链描述它。**

当前实际消费者与入口：

- 注册：`scripts/video_contract.py:199-223` 以 JSON 加同名或同族 Markdown 判断 layout preset 是否注册。
- preset 校验：`scripts/scene_config.py:203-234` 检查 `layout.preset` 是否注册，但区域几何和 caption 校验使用 scene-config 内实际落盘的值，不从 preset JSON 补值。
- 独立字幕工具：`scripts/align-narration.py:394-404` 的 `--layout` 入口读取 JSON 的 `caption`；Phase 8 handoff 使用 `--scene-config`，不走这个旧单布局入口。
- 独立画面检查：`scripts/check-composition.py:97-100`、`:165-179` 保留 `--layout` 入口；Phase 8 使用 `--scene-config`。
- handoff：`scripts/prepare-handoff.py:338-356` 固定引用 `modules/layouts/layouts.md`，具体 preset 的 Markdown/JSON 由 agent 选定后按需阅读，不再预选一份全片 layout JSON。
- `video_contract.layout_file_problem()` 当前只有定义和 `tests/test_video_contract.py` 的直接测试，没有生产调用方；不能再把它描述成 Phase 8 的在线门槛。
- 旧的状态指纹已经删除，layout/design JSON 不再以“上游指纹”理由保留。

**剩余问题：** 各 preset 文档要求区域表与 JSON 数值一致，但现有测试只逐份校验 JSON 契约，没有比较 Markdown 表格中的 rect、canvas、caption 与 JSON。ASCII 示意图也包含数值，但不适合作为稳定解析接口。

**建议：** 增加文档契约测试，以 JSON 为预设数值来源，按固定文档和章节映射解析 Markdown 区域表，逐项比较 rect，并校验 `layouts.md` 汇总表中的 canvas/caption。不要在本轮引入文档生成器，也不要解析 ASCII 图。

**命名维度：** 现有 id 仍是完整 preset 名，而 scene-config 已允许自由布局，因此没有需要立即拆分的机器维度。保留 `presenter/stage/portrait/portrait-3x4`；只有出现真实竖屏主持人 preset 需求时再新增模块，不在本轮改名或新增 `portrait-presenter`。

### 3. 组件使用规则的职责归位

**现状：**

- `base-instructions.md:59` 已明确要求在 storyboard 前读 `modules/components/components.md`，再按需读具体组件文档；`tests/test_prepare_handoff.py:1106-1110` 固定了这一顺序。
- `modules/modules.md:14-70` 统一定义初始化接口与 adapter，`:143-151` 仍有通用组装步骤和 Jay envelope 命令。
- `modules/components/components.md` 提供目录、数据键和共同约定。
- `modules/components/jay/jay.md:79-138` 已说明安装、常驻挂载和逐 scene placements，`:156-198` 给出通用演法，`:225-237` 给出 envelope 命令。
- `base-instructions.md:32` 同时包含 Jay 挂载不变量、通用演法指引和 envelope 命令；`:41` 又重复动作编排规则。
- `scripts/prepare-handoff.py:360-361` 的 Required References 最后一项是 `modules/components/` 目录，未明确列出 `components.md`。

**建议：**

- 基础指令保留跨组件和跨场景不变量：reserved 区只放声明组件；声明 Jay 人物区时必须挂 Jay；无常驻人物区时通过 placements 隐藏。
- 将通用演法、动作去重和 envelope 命令留在 `jay.md`，基础指令只链接，不复制命令。
- 从 `modules.md` 删除 Jay 专属命令，保留跨模块初始化与时间约定。
- handoff 最后一项改为明确的 `modules/components/components.md`，具体组件文档仍按需读取；同步生成脚本、handoff 模板、Phase 8 描述和顺序测试。

### 4. `modules/modules.md` 在哪里被读入

这条是职责确认，不需要单独改代码：

1. `scripts/prepare-handoff.py:333-356` 把它加入 composition Required References，顺序为基础指令 → scene-config → modules → design → layouts → templates → components。
2. `references/delegation/composition/handoff-template.md:17` 与 `references/phases/08-composition.md:107-109` 描述同一条阅读链。
3. `prepare-handoff.py` 物化整个当前 `modules/` 库，agent 阅读工作区副本；`tests/test_prepare_handoff.py:646-664` 校验物化行为。
4. `tests/test_prepare_handoff.py:589-629` 固定 Required References 的实际顺序。

因此，`modules.md` 应继续作为总入口和跨模块契约文档。分类目录和具体安装细节可以下沉，但模块初始化接口、adapter 职责、路径规则及共用数据/时间语义不应分散到每个分类索引。

### 5. 场景表现、创意与事实边界

**已经存在、不需重建的规则：**

- `base-instructions.md:38-43` 已规定逐场景模板/layout、自主设计优先、按需参考、真实语音和偏离理由。
- `modules/motion.md:23-47` 已列 DOM/SVG/GSAP/Canvas/WebGL 等实现候选及确定性要求，`:38-45` 明确不要求每个 scene 有招牌机制或持续运动。
- `modules/patterns/patterns.md:39-44` 已规定定向查阅、局部借用与改写。
- `inputs.json.composition_requests` 已进入 handoff；用户明确要求冲突时报告，而不是静默替换。
- `scene-plan.json` 当前只有叙事字段，没有 `facts`；`references/delegation/script/base-instructions.md:103-124` 与 `tests/test_phase_docs.py:650-658` 明确了这一契约。

**真正缺口：** composition 可以在画面里新增短标签、数字、引文、图示和视觉类比，但基础指令只笼统要求屏幕文字来自显示稿，没有清楚区分“显示稿文字”与“为解释而新增的图形/标注”，也没有统一禁止把示意伪装成证据。

**输入边界：** `research-brief.md` 是 script agent 的输入，不在 composition handoff 的 Agent Inputs 中（`scripts/prepare-handoff.py:369-379`）。本轮不新增这份大文档作为 composition 必读输入；composition 只能沿用 `script.txt`、`scene-plan.json`、适用时的 `material-catalog.json` 和用户明确要求所支撑的内容。需要新增上游事实时报告并回退，不自行补事实。

**建议：** 在基础指令第四部分内增加一个短小节，保留现有标题与锚点：

- 表现机制从语义和素材出发，静态画面也合格；具体 runtime 候选指向 `motion.md`，不复制整张表。
- 创意不得破坏 design、实际 regions、可读性和事实含义。
- 新增屏幕事实、数字、实体和引文必须有当前 composition 输入支撑；图示和类比不得伪装成证据。
- storyboard 继续记录已有 `intent/content_plan`、构图、素材、信息展开和动效，不强制新增“表现意图 / 主打机制 / 事实来源”三列。

### 6. design 开头与具体主题的重复职责句

**现状：** `modules/designs/designs.md:3` 仍使用“不管内容，也不管版面”的否定式；三个具体主题文档开头也重复“这份文档只规定外观”。

**建议：** 总索引用正面表述说明 design 负责配色、字体、字号、背景、形状、图标和动效节奏。具体主题删除通用职责句，只保留主题气质，以及 GitHub/Product Hunt 品牌元素归模板而非 design 的实际分界。

### 7. 索引与 design 文档去重

**当前规模：**

| 文档 | 行数 | 判断 |
| --- | ---: | --- |
| `modules/modules.md` | 195 | 总入口、初始化/adapter、目录、组装、数据、时间和扩展契约；不能只按长度删减 |
| `designs/designs.md` | 164 | 共享 token/schema、字体维护、主题选择和备选配色 |
| `designs/default/default.md` | 192 | 主题规则、token 表、CSS 块及重复安装说明 |
| `designs/github/github.md` | 213 | 同上，另有 slate 和纹理生成细节 |
| `designs/producthunt/producthunt.md` | 192 | 同上 |
| `layouts/layouts.md` | 54 | 已有 preset 目录、逐 scene 规则和数据映射 |
| `templates/templates.md` | 42 | 已有逐场景借用、`preferred_layouts` 和 null 路径 |
| `components/components.md` | 28 | 已有目录与共同约定 |
| `patterns/patterns.md` | 44 | 已有按需查阅规则 |
| `motion.md` | 53 | 已有 runtime 与运动原则 |

**值得改的重复：**

1. 每个主题的 token 值表与 CSS 块、JSON 同值；先删除 Markdown token 值表，保留一份可复制 CSS 块。
2. 字体仓库结构和通用安装命令已在 `designs.md`；主题文档只需保留实际字体栈和 CSS 文件名，通用维护说明指回索引。
3. 三个主题的通用规则相似但不完全相同。字号用途、圆角、图标、动效和 do/don't 含主题差异，不能为了去重全部变成所有未来 design 的全局契约。

**当前 JSON 契约：**

- `check-composition.py:151-162` 读取 `min_font_px.reading/ui`。
- `fonts-download.sh:123-138` 读取 `fonts`；字体安装和刷新不读取 `tokens`。
- 未找到生产脚本读取 design JSON 的 `tokens`；当前值一致性由 `tests/test_design_contract.py:32-65` 保证。
- `caption_font_px` 只出现在三个 JSON、文档和 `test_design_contract.py`，没有生产消费者。实际字幕规格来自每个 scene 在 scene-config 落盘的 `layout.caption`；preset JSON 只是借用时的来源。

**建议边界：**

- 本轮保留 Markdown CSS + JSON 双来源及现有相等测试，不新增 JSON→CSS 生成器。
- 删除具体主题的 token 值表和重复通用安装说明，保留主题差异与一份 CSS 块。
- 另开 ticket 删除 `caption_font_px`，同步三个 JSON、schema 文档、扩展规则和测试；不改 layout/scene-config 字幕行为。
- 不对所有分类索引强行统一四段式，不搬动已经清楚的 layouts/templates/patterns 使用规则。

### 8. transitions 提升为顶级模块类别

**现状：** 唯一转场位于 `modules/components/transitions/tile-wipe/`。文档已经把它作为 scene 交接层，而不是内容部件；其初始化接口、数据键 `VIDEO.cuts`、工程内 `compositions/tile-wipe.*` 和 `data-composition-id="tile-wipe"` 都可以保持不变。

**完整影响范围：**

- 移动 `tile-wipe.md/.html/.mjs`，新增 `modules/transitions/transitions.md`；更新组件文档标题、文件路径和 HTML 注释。
- 更新 `modules.md` 的目录、分层、数据/时间和扩展规则；`components.md` 移除转场行并指向新分类。
- 更新 `motion.md`、`patterns.md`、三个 layout 文档和 `templates/github/github.md` 中的路径。
- `tests/test_scene_components_browser.py:446-450` 直接引用旧源码目录，必须改为 `transitions/tile-wipe`。
- storyboard 目前要求“组件使用表”记录每个组件的数据来源。转场移出 components 后，应同步改成“组件与转场使用表”，保留对 `cuts` 数据来源的记录；涉及基础指令、handoff 模板和对应文档测试。
- transitions 不是每个自由布局都必须使用，handoff 应把 `modules/transitions/` 与 patterns/motion 一起列为按需参考，而不是新增一份无条件全读契约。
- `prepare-handoff.py` 已复制整个 `modules/`，无需为移动本身新增复制逻辑或机器注册表。

**验收重点：** 旧路径在现行模块、references、scripts 和 tests 中清零；浏览器组件测试仍从真实源码加载并渲染 tile-wipe，data id、数据和时长行为不变。

### 9. 委派子 agent 的统一模块选择策略

**当前覆盖并不完整：**

- templates/layouts 已由 composition agent 逐场景选择，且有“非常匹配才采用 / 自由布局”规则。
- patterns/motion 是按需参考，但规则主要写成“已有构想后定向查阅”，尚未与其他类别共用同一条采用边界。
- components 有目录和挂载规则，却没有统一说明“能用”不等于“应该采用”；transitions 也相同。
- designs 仍在 Phase 1 必填并预选，`prepare-handoff.py` 在子 agent 开始前按它安装字体，因此当前并不支持子 agent 选择或即时生成 design。

**统一采用规则：**

1. 先确定用户要求的作用范围，再读该 scene 的叙事目标、素材、画布和实际区域需求。
2. 用户在某 scene 或全片明确指定模块时，在该范围内采用；与朝向、事实或另一条明确要求冲突时报告，不静默替换。
3. 未指定时，只有预定义模块与场景的内容关系、素材形态、画布、可读性和所需交互都特别匹配，并且比即时生成更合适时才采用。仅仅“可以复用”“风格接近”或“目录里有”不够。
4. 没有特别匹配模块时，由 composition agent 按 scene 要求即时生成：不使用模板就写 `template: null`，不借用 layout preset 就写 `preset: null`，不借用 pattern/motion 就不记录借用；组件、转场和视觉机制可用普通 HTML/CSS/SVG/JS 自绘实现，但仍须满足字幕、区域、确定性、事实和 QA 契约。
5. 选中 template/layout 后，它声明的必要组件属于该方案的一部分；如果这些组件不合适，说明该模块并非特别匹配，而不是一方面借用模块、另一方面破坏其 reserved 区约定。
6. Required/Optional References 是阅读入口，不是采用清单。storyboard 只记录实际采用的预定义模块和特别匹配理由；即时生成是默认路径，不需要为未采用模块逐项写理由。

**design 的契约差异：** design 目前是全片级输入，不是 scene-config 字段。目标方案是 Phase 1 只在用户明确点名时记录预定义 design；否则由 composition agent 在开始制作时，根据全片与各 scene 的需求选择特别匹配的预定义 design，或生成自包含的 custom design 契约供检查和 QA 使用。用户明确把某 design 限定到单个 scene 时，只在该 scene 应用其 token 覆盖，不自动传播到全片。

这不能再只靠文档措辞完成：需要移除 Phase 1 的默认预选、把具体 design 文档和字体安装延后到子 agent 选择之后，并新增 composition 自己的 design 产物供 `check-composition --design` 与状态验收读取。实施边界见 SEL-02。

## 三、实施入口

实施工作不在本文展开为批次，而拆成独立 tickets：

1. DOC-01：基础指令开头可读性。
2. SEL-01：逐场景模块的统一选择规则。
3. DOC-02：Jay 与组件文档职责归位、handoff 明确组件索引。
4. DOC-03：视觉表现与新增事实边界。
5. DOC-04：design 表述和 Markdown 去重。
6. DOC-05：layout Markdown/JSON 一致性测试。
7. DOC-06：删除 `caption_font_px`。
8. DOC-07：transitions 顶级目录迁移。
9. SEL-02：design 选择委派与 custom design 契约。

具体文件、步骤、依赖和验收命令见 [实施计划](2026-11-13-composition-module-docs-implementation-tickets.md)。
