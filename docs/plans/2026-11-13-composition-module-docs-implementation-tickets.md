# Composition 与模块文档后续改动实施计划

日期：2026-11-13  
状态：待实施；本计划只拆分工作，不修改现行指令、模块契约或代码。  
调研依据：[Composition 与模块文档 comments 调研](2026-11-12-composition-module-docs-comments-research.md)。

## 1. 目标与当前基线

把剩余的 composition / modules 文档问题拆成可独立验收的 tickets，并建立一条统一的模块采用规则：

> composition 子 agent 只在用户明确指定，或预定义模块与目标 scene 特别匹配时才采用它；否则根据 scene 的叙事、素材、画布和可读性要求即时设计并生成实现。阅读模块目录不等于采用模块。

除 SEL-02 明确调整的 design 选择、字体准备和验收契约外，保持以下现行行为不变：

- 主 agent 固定全片 `orientation` 和用户约束，不预选全片 template/layout；design 的现有预选流程只由 SEL-02 修改。
- composition agent 逐视觉场景决定 template/layout，可借用 preset，也可自由布局。
- 每个 scene 的 template、实际 `regions` 和 `caption` 写入 `composition/scene-config.json`；不写回 `inputs.json`。
- 模板 JSON 使用建议性的 `preferred_layouts`，不是 `supported_layouts` 硬门槛。
- composition agent 只使用 `hyperframes` 与 `hyperframes-cli` 两个外部 skill。
- patterns/motion 是按需参考；自主设计、静态场景和全片不用参考库都合法。
- 用户明确指定的视觉要求互相冲突时报告冲突，不通过静默改 template/layout 消解。

### 不在本次范围内

- 不恢复全片 `inputs.json.template/layout` 决策或旧状态指纹。
- 不新增 `portrait-presenter`，不改现有 layout id，不把 orientation 与人物模式拆成新机器维度。
- 不统一重写所有分类索引，不要求它们机械使用相同四段式。
- 不新增 JSON→CSS 生成器；本轮保留 Markdown CSS 与 design JSON 的自动相等测试。
- 不把 `research-brief.md` 新增为 composition 必读输入，不给 storyboard 增加三个强制字段。
- 不修改组件 `init` 接口、HyperFrames adapter、`data-composition-id`、工程内 compositions 文件名或数据键。
- SEL-02 不把 design 塞进每个 scene-config scene；scene 限定的 design 要求通过该 scene 的 token 覆盖和 storyboard 记录实现。

## 2. Ticket 总览与依赖

| Ticket | 交付内容 | 主要风险 | 依赖 |
| --- | --- | --- | --- |
| DOC-01 | 基础指令开头改为清楚的五类约束 | 误写成全片 template/layout | 无 |
| SEL-01 | 所有 scene 级模块的统一采用规则 | 把阅读目录误写成必须采用，或削弱自定义路径 | DOC-01 |
| DOC-02 | Jay 细节归组件文档；handoff 明确组件索引 | 丢失 Jay 挂载/隐藏不变量 | SEL-01 |
| DOC-03 | 补视觉创意与新增事实边界 | 过度限制静态/自主设计，新增重复 storyboard 契约 | SEL-01 |
| DOC-04 | design 正面表述与 Markdown 去重 | 误删唯一 CSS 块或主题差异 | 无 |
| DOC-05 | layout 文档与 JSON 数值一致性测试 | 测试误解析 ASCII 图或 prose | 无 |
| DOC-06 | 删除无消费者的 `caption_font_px` | 误改实际字幕来源或遗留测试引用 | DOC-04 |
| DOC-07 | transitions 升为顶级模块类别 | 漏改真实浏览器测试和 cuts 使用表要求 | SEL-01、DOC-02 |
| SEL-02 | design 选择委派与 custom design 契约 | handoff 前仍预选 design/装字体，custom design 无法验收 | DOC-02、DOC-04、DOC-06 |

推荐实施顺序：主文档链为 `DOC-01 → SEL-01 → DOC-02 → DOC-03`；独立完成 `DOC-04 → DOC-06` 和 `DOC-05`；然后做 `DOC-07`，最后实施会改输入与验收契约的 `SEL-02`。每个 ticket 仍可单独提交，但依赖 ticket 未落地时不要提前改下游文案。

每个 ticket 完成后应单独通过自己的验收；全部结束后执行第 10 节的总验收。

## SEL-01：所有 scene 级模块的统一采用规则

### 问题与证据

当前规则分散且覆盖不一致：

- `base-instructions.md:38` 已对 template/layout 使用“非常匹配 / 自由布局”。
- `patterns/patterns.md` 与 `motion.md` 已允许不查阅，但尚未和其他模块共用同一条采用定义。
- `components/components.md` 只有目录与共同约定，没有说明“可复用”不等于“应该采用”。
- Required/Optional References 规定阅读入口，不应被理解为必须使用的模块清单。

### 改动文件

- `references/delegation/composition/base-instructions.md`
- `references/delegation/composition/handoff-template.md`
- `references/phases/08-composition.md`
- `modules/modules.md`
- `modules/templates/templates.md`
- `modules/layouts/layouts.md`
- `modules/components/components.md`
- `modules/patterns/patterns.md`
- `modules/motion.md`
- `tests/test_phase_docs.py`
- `tests/test_prepare_handoff.py`

### 目标选择算法

对每个视觉 scene 按以下顺序执行，并把同一原则写到基础指令第四部分；分类索引只补充本类别的匹配信号，不复制整套算法：

1. **先应用用户要求及其作用范围。** 用户指定某 scene 或全片使用某个模块时，在该范围内采用；与朝向、事实或另一条明确要求冲突时报告冲突。
2. **未指定时评估“特别匹配”，不是“勉强可用”。** 至少同时满足：
   - 模块表达的内容关系与 scene 的叙事目标一致；
   - 素材形态、数据、画布和可读性适合该模块；
   - 不需要改旁白、视觉 scene、orientation 或用户要求来迁就模块；
   - 采用它比即时生成更清楚或更可靠，而不只是少写代码。
3. **没有特别匹配就即时生成。** composition agent 根据 scene 要求自行设计 DOM/CSS/SVG/JS、图表、视觉机制或组件，不为使用库而使用库。
4. **按实际采用落盘。** 不用 template 时写 `template: null`；不借 layout preset 时写 `preset: null` 并落盘实际 regions/caption；不借 pattern/motion 时不产生借用记录；自绘组件仍须满足区域、字幕、确定性和检查契约。
5. **保持模块内部依赖完整。** 一个特别匹配且被采用的 template/layout 所声明的必要组件，属于该方案的一部分；若这些组件不适合，应判定整个方案不够匹配，而不是破坏它的 reserved 区约定。
6. **只记录实际采用。** storyboard 记录实际借用的模块、用户指定依据或特别匹配理由；即时生成不需要“未使用其他模块”的清单。

### 各类别如何落地

| 类别 | 子 agent 如何选择 | 无特别匹配时 |
| --- | --- | --- |
| template | 用户指定，或模板场景与内容、真实锚点、布局需求特别匹配 | `template: null`，自主实现场景 |
| layout | 用户指定，或 preset 区域与素材/信息密度特别匹配；模板 `preferred_layouts` 只作建议 | `preset: null`，即时设计 regions/caption |
| component | 用户指定、被已采用方案声明为必要，或组件本身与需求特别匹配 | 自绘所需部件；不为了目录完整而挂 Jay/nav/转场等 |
| pattern | 用户指定，或已有构想与 pattern 的形态和触发信号特别匹配 | 不借用，自主构图 |
| motion | 用户指定，或具体运动问题与参考建议特别匹配 | 不查阅/不借用，自主设计运动或保持静态 |
| transition（DOC-07 后） | 用户指定，或 scene 交接确实受益于现有转场机制 | 简单接缝或即时生成交接，不强制 tile-wipe |
| design | 由 SEL-02 单独迁移；SEL-01 不改现有固定 design 契约 | 见 SEL-02 的 custom design 路径 |

### 实施步骤

1. 在基础指令第四部分写一次上述算法，并明确“默认即时生成，预定义模块是例外”。
2. 在 `modules.md` 总入口说明“目录/必读引用是发现入口，不是采用清单”，并链接到统一选择规则。
3. 各分类索引只保留本类别的匹配信号和选中后的文档入口；删除任何暗示“每 scene 都要选一个模块”的措辞。
4. handoff 和 Phase 8 将执行顺序统一为“用户要求 → 特别匹配模块 → 即时生成”，同时保留 scene-config 的实际字段要求。
5. 文档测试覆盖两条正常路径：特别匹配/用户指定才借用，以及完全不借用的即时生成路径；不得把 Required References 中存在某个目录断言成必须采用它。

### 明确不改

- 不修改 scene-config 字段；现有 `template: null` 与 `preset: null` 已能表达不采用。
- 不要求为每个未采用模块写理由，不要求每个 scene 使用动画或参考库。
- 不在 SEL-01 改变 design 的现有上游契约。
- 不删除被采用 template/layout 所需的 reserved 组件约束。

### 验收

```bash
source .venv/bin/activate && pytest \
  tests/test_phase_docs.py \
  tests/test_prepare_handoff.py
```

人工检查一个没有任何特别匹配模块的 scene：最终可以全部为即时生成，`template: null`、`preset: null`、无 pattern/motion 借用记录，且仍满足字幕、区域和 QA 要求。

## SEL-02：design 选择委派与 custom design 契约

### 问题与证据

design 目前没有走子 agent 选择路径：

- `references/phases/01-gather-inputs.md:20`、`:63-69` 要求 Phase 1 选定注册 design，未指定时默认 default。
- `scripts/video_contract.py:20-38` 把 design 作为基础输入和 composition handoff 的必填字段。
- `scripts/prepare-handoff.py:184-217`、`:327-392` 在派发前校验具体 design、固定其文档并预装字体。
- handoff 的 check-composition 命令固定指向工作区里的预定义 `<design>.json`。
- `scripts/pipeline-status.py:689-735` 把缺失或已移除的 design 退回 Phase 1。

因此，只补一句“子 agent 可以选择 design”不足以支持用户目标，也不支持没有特别匹配主题时的 custom design。

### 目标行为

- Phase 1 不再替 composition 预选默认 design。只有用户明确点名注册 design 时才在 `inputs.json.design` 保存该约束；其他风格要求继续记入 `composition_requests`。
- composition 子 agent 读取 scene 需求和 design 目录后：
  - 用户明确指定预定义 design：按作用范围采用；
  - 未指定但某预定义 design 与全片视觉需求特别匹配：采用它；
  - 否则：根据各 scene 需求即时生成一套全片 custom design。
- design 的机器基线仍是一份全片契约，不加入 scene-config。用户明确把某预定义 design 限定到单个 scene 时，在该 scene 根作用域覆盖相应 token，并在 storyboard 记录；不自动传播到其他 scene。
- 无论 preset 或 custom，都产出 `composition/design.json`，供检查和状态验收入口统一读取。

### 改动文件

- `references/phases/01-gather-inputs.md`
- `references/phases/08-composition.md`
- `references/phases/09-check-mix.md`
- `references/pipeline-control.md`
- `references/delegation/conventions.md`
- `references/delegation/composition/base-instructions.md`
- `references/delegation/composition/handoff-template.md`
- `modules/designs/designs.md`
- `modules/modules.md`
- `scripts/video_contract.py`
- `scripts/prepare-handoff.py`
- `scripts/pipeline-status.py`
- 新增 `scripts/composition_design.py`
- `tests/test_prepare_handoff.py`
- `tests/test_pipeline_status.py`
- `tests/test_visual_pipeline_status.py`
- `tests/test_phase_docs.py`
- `tests/test_design_contract.py`
- 新增 `tests/test_composition_design.py`

### composition design 契约

新增 `composition/design.json`，固定形状如下：

```json
{
  "version": 1,
  "source": "preset",
  "preset": "github",
  "tokens": {"--c-canvas": "...", "--font-sans": "...", "--ground": "..."},
  "min_font_px": {"reading": 26, "ui": 22}
}
```

规则：

- 根字段恰好为 `version/source/preset/tokens/min_font_px`。
- `source: "preset"` 时，`preset` 是库中注册名，tokens/min font 必须与该 preset 当前 JSON 一致；`source: "custom"` 时，`preset` 必须为 `null`，tokens 由子 agent 按 scene 需求生成。
- 两种路径都必须定义完整共享 token 集合和正整数 reading/ui 下限。
- `fonts` 不进入这个产物：它描述本次画面的机器契约，不是 Google Fonts 维护清单。实际字体文件与 CSS 仍在 `composition/assets/fonts/`。
- `check-composition.py` 已只读取 `min_font_px`，可以继续接收这个文件；不破坏独立工具直接传库内 preset JSON 的旧入口。

### 实施步骤

1. **建立公共读取校验。** 新增 `scripts/composition_design.py`，校验上述根字段、source/preset 组合、完整 tokens 和 min font；preset 时与库内 JSON 比对。将共享 token 名集合放到 `video_contract.py` 供该校验和 design 契约测试共同使用，不再让测试从 Markdown 反推机器 token 集合。
2. **Phase 1 取消默认预选。** 从 `INPUTS_BASE_FIELDS` 和 composition 的 `STEP_INPUTS_FIELDS` 移除 design；`inputs.json.design` 变成可选的用户明确约束，出现时仍校验注册名。Phase 1 不再把“没有现有风格”强行映射成 default。
3. **状态输入校验同步。** `pipeline-status.load_inputs()` 只在 design 出现时检查它，不因缺失退回 Phase 1。旧工作区已有 design 原样保留，视为已有约束，不擅自删除。
4. **handoff 不再预选或预装。** `prepare-handoff.py` 只物化委派包和 modules；composition Required References 固定包含 `designs/designs.md`，具体主题文档/JSON由子 agent 选定后按需阅读。无用户指定 design 时 Inputs 显示“未预选”，而不是 default。
5. **字体安装延后到选择之后。** 删除 composition 派发前 `install_fonts()` 的调用；保留 CLI JSON 的 `fonts: null` 兼容形状并更新说明。基础指令/handoff 给子 agent 通用命令：选定 preset 后用对应 `modules/designs/<design>` 安装；custom 可选择一个现有字体包作为字体资源，但 token 的字体名必须与实际 CSS 一致。复用字体资源不等于采用该 preset 的视觉设计；仍禁止系统字体。
6. **子 agent 产出 design。** 工作顺序改为先决定 preset/custom design、安装字体并写 `composition/design.json`，再逐场景选择其他模块。custom design 也必须写完整 tokens 和 min font，不能仅写一份散文故事板。
7. **检查命令改指统一产物。** handoff 的 `--design` 改为 `composition/design.json`；Phase 8 Outputs/完成判据增加该文件，`pipeline-status` 经公共读取器校验。Phase 9 的“符合所选 design”改为同时支持 preset 与 custom，并检查 scene 限定 token 覆盖没有外泄。
8. **文档职责同步。** `designs.md` 说明“库内 preset 是候选，不是默认必选”；`modules.md`、Phase 8、pipeline-control 和 conventions 不再声称主 agent 固定 design 或在派发前预装字体。
9. **测试迁移。** 删除“缺 design 即损坏/回 Phase 1”的旧断言，新增：
   - 无 `inputs.json.design` 也能生成 composition handoff，且不预装某个 preset 的字体；
   - 用户明确指定的 design 仍作为约束进入 handoff；
   - preset 与 custom 两种 `composition/design.json` 都能被公共读取器和 Phase 8 验收；
   - custom 缺 token、非法 source/preset、preset 值漂移都会被拒绝；
   - check-composition 从该产物读取相同 min font；
   - 旧工作区已有 design 不被自动删除。

### 明确不改

- 不把 design 加进 scene-config，不允许 scene 任意改变 canvas/orientation。
- 不删除库内 designs，不要求所有视频都 custom。
- 不新增在线字体搜索或新字体依赖；custom 使用仓库已有字体资源。
- 不修改 check-composition 的实际文字测量算法，只更换 Phase 8 的 design 输入产物。
- 不自动迁移或清理旧工作区的 `inputs.json.design`。

### 验收

```bash
source .venv/bin/activate && pytest \
  tests/test_composition_design.py \
  tests/test_design_contract.py \
  tests/test_prepare_handoff.py \
  tests/test_pipeline_status.py \
  tests/test_visual_pipeline_status.py \
  tests/test_check_composition.py \
  tests/test_phase_docs.py
```

至少做两次真实 handoff 集成检查：一次 inputs 不含 design，确认不被 default 预选且不预装字体；一次用户明确指定 github，确认该约束保留。再用 custom `composition/design.json` 跑一次 check-composition，证明不是只通过 JSON import 或单元编译。

## 3. DOC-01：基础指令开头改为五类约束列表

### 问题与证据

`references/delegation/composition/base-instructions.md:9` 仍用连续破折号列出五类约束。当前行文已经包含逐场景语义，改写时不能退回“全片当前 layout”的旧模型。

### 改动文件

- `references/delegation/composition/base-instructions.md`
- `tests/test_phase_docs.py`

### 实施步骤

1. 把开头长句改成五项编号列表，语义限定为：
   1. 输入、真实语音与素材契约；
   2. 所选 design 的 token 与字号约束；
   3. 各视觉 scene 实际落盘的 layout regions/caption；
   4. 逐场景内容演绎、template/layout 与自主设计；
   5. 模板时间锚点只能来自真实朗读。
2. 单独用一句话引出后面的工作顺序，不把工作顺序混进五项约束。
3. 将“除此之外你没有别的规则”改为“其余视觉设计由 composition agent 决定”一类有限定的表述；保留 scene 切分、构图、素材摆法、动作与动效的自主性。
4. 保留现有章节标题，尤其是 `## 四、内容演绎与模板选择`；patterns/motion 的链接片段和现有测试依赖它。
5. 在 `test_phase_docs.py` 增加一个聚焦开头语义的文档测试：断言保留“各视觉 scene”和“逐场景”，且不存在“主 agent 已选定 layout”“写回 inputs.json”之类旧流程表述。不要对整段文案做过宽的全字符串快照。

### 明确不改

- 不改 scene-config schema、工作顺序编号或实际选择顺序。
- 不把 `preferred_layouts` 改回兼容门槛。
- 不删除输入、素材、字体、字幕或检查约束。

### 验收

```bash
source .venv/bin/activate && pytest tests/test_phase_docs.py
```

人工检查开头五项能一一映射到后文五个编号章节，并明确 template/layout 是逐视觉 scene 决策。

## 4. DOC-02：Jay 细节归组件文档，handoff 明确组件索引

### 问题与证据

- `base-instructions.md:32` 混合了 Jay 挂载不变量、通用演法指引和 envelope 命令，`:41` 又重复动作编排。
- `modules/components/jay/jay.md:156-198` 已是通用演法来源，`:225-237` 已是 envelope 命令来源。
- `modules/modules.md:151` 也复制了 Jay 专属命令。
- `base-instructions.md:59` 已要求读 `components/components.md`，但 `scripts/prepare-handoff.py:360-361` 的 Required References 只列组件目录。

### 改动文件

- `references/delegation/composition/base-instructions.md`
- `references/delegation/composition/handoff-template.md`
- `references/phases/08-composition.md`
- `modules/components/jay/jay.md`
- `modules/modules.md`
- `scripts/prepare-handoff.py`
- `tests/test_prepare_handoff.py`
- `tests/test_phase_docs.py`

### 实施步骤

1. **基础指令只保留跨场景不变量。**
   - reserved 区只放其 `component` 声明的组件；
   - scene 有 `component: jay` 的人物区时必须挂 Jay；
   - Jay 仍是全片唯一常驻实例，无人物区的 scene 通过 `placements` 隐藏；
   - 动作与演法指向 `jay.md`，模板专属演法仍按模板叠加。
   删除基础指令中的具体 envelope 命令和重复“动作自己排”段落。
2. **组件文档承接全部 Jay 细节。**
   - 在 `jay.md` 的 envelope 小节保留通用用法，并补一个从仓库根目录运行的 composition 示例：`node modules/components/jay/make-envelope.mjs voice_clone/narration.mp3 > composition/assets/jay-envelope.json`。
   - 说明示例输出需进入 `VIDEO.jay.envelope`，`envelopeFps` 与生成参数一致；该示例路径不是新增的阶段产物门槛。
   - 保留“换配音需重新生成 envelope 并重排时间”的现有规则。
3. **总入口去组件化细节。** 从 `modules.md` 的组装步骤删除 Jay 命令，改为指向 `components/jay/jay.md`；保留模块初始化接口、adapter 和时间约定。
4. **handoff 指向索引文件而非泛目录。** 将 `composition_plan()` 最后一项从 `modules/components/` 改为 `modules/components/components.md`，文案仍为“组件索引：按需读要挂载的组件文档”。
5. 同步 `handoff-template.md` 的 Required References 占位符说明与 Phase 8 的 8.2 描述。具体组件文档仍按需阅读，不把所有组件文档加入全读列表。
6. 更新 `tests/test_prepare_handoff.py` 中 Required References 的最后一项和文案断言；保留 `components.md` 在 storyboard 组件使用表之前阅读的测试。
7. 更新 `test_phase_docs.py` 的 Jay 测试：挂载/隐藏不变量仍在基础指令；通用演法与 composition envelope 示例只在 `jay.md`，基础指令不再复制命令。

### 明确不改

- 不删除“有 Jay 区必须挂、无 Jay 区要隐藏”的规则。
- 不把 Jay 改成每 scene 重复挂载。
- 不改 `VIDEO.jay`、`placements`、`envelope` 的数据结构或组件实现。

### 验收

```bash
source .venv/bin/activate && pytest \
  tests/test_prepare_handoff.py \
  tests/test_phase_docs.py
```

在临时工作区测试生成的 handoff 中，最后一个 Required Reference 必须是实际存在的 `modules/components/components.md` 文件，且顺序仍位于 templates 之后。

## 5. DOC-03：补视觉表现与新增事实边界

### 问题与证据

自主构图和 runtime 选择已有规则，但 composition 可以新增短标签、数字、引文、图示或类比，现有指令没有统一说明这些新增内容的事实边界。`research-brief.md` 不是 composition handoff 输入，不能要求 agent 每场景引用一份未提供的文件。

### 改动文件

- `references/delegation/composition/base-instructions.md`
- `tests/test_phase_docs.py`

### 实施步骤

1. 在现有 `## 四、内容演绎与模板选择` 内、靠近“自主设计优先”的位置增加短小节“表达与事实边界”。不要新增顶层编号章节，不改变现有锚点。
2. 写入四条通用规则：
   - 表现机制从旁白语义、素材和实际区域出发；DOM/SVG/CSS/Canvas/WebGL 都是可选实现，静态呈现也合法，具体 runtime 选择指向 `motion.md`。
   - 创意服务于理解，不得破坏 design token、实际 regions、可读性、真实语音同步或事实含义。
   - 新增屏幕事实、数字、实体、引文和标注必须能由当前 composition 输入支撑：`script.txt`、`scene-plan.json`、适用时的 `material-catalog.json` 及明确的用户要求；需要新增上游事实时报告并建议回退，不自行编造。
   - 图示、类比和示意可用于解释，但不得伪装成证据；会改变事实含义的构图、标注与动画不使用。
3. 保留“简洁的静态呈现也是有效选择”“参考库可跳过”“无需填写 pattern 字段或未使用理由”等现有句子。
4. 在 `test_phase_docs.py` 扩展自主设计测试，断言事实边界和静态/按需参考同时存在，防止新规则演变成强制动效或强制参考库。

### 明确不改

- 不新增 storyboard 的“表现意图 / 主打机制 / 事实来源”必填字段；现有 `intent/content_plan`、素材、构图、信息展开与动效记录已足够。
- 不要求每个 scene 使用 SVG、动画或唯一招牌机制。
- 不新增 Phase 8 机器 gate，不把 `research-brief.md` 加进 composition handoff。
- 不修改 Phase 9 的四项 vision 检查结构。

### 验收

```bash
source .venv/bin/activate && pytest tests/test_phase_docs.py
```

人工用一个无素材静态 scene 和一个含新增数字标注的 scene 对照规则：前者不能被规则强制加动画，后者必须能找到当前输入中的依据或触发上游回报。

## 6. DOC-04：design 正面表述与 Markdown 去重

### 问题与证据

`designs.md` 与三个主题文档重复通用职责和安装说明；每个主题还同时维护 token 值表、CSS 块和 JSON。现有 `tests/test_design_contract.py:32-65` 要求每份主题文档恰好一个 `:root` CSS 块，并与 JSON 完全一致。

### 改动文件

- `modules/designs/designs.md`
- `modules/designs/default/default.md`
- `modules/designs/github/github.md`
- `modules/designs/producthunt/producthunt.md`
- 如确需强化文档结构断言，再小范围更新 `tests/test_design_contract.py`；不要为删表而削弱现有相等测试。

### 实施步骤

1. 将 `designs.md:3` 改为正面职责说明：design 规定配色、字体、字号、背景、形状、图标风格和动效节奏。不再写“不管内容，也不管版面”。
2. 删除三个主题文档开头重复的“这份文档只规定外观”。保留各自气质，以及 GitHub/Product Hunt 品牌元素归模板的实际分界。
3. 删除三个主题的“主题变量值”Markdown 数值表；保留一份可复制 `:root` CSS 块，并让相邻文字直接指向 JSON/共享 token 语义。
4. 保留主题特有的对比度、变体、纹理、字体角色、字号用途、圆角、图标、动效和 do/don't。不要把当前三个纸感主题的共同点上升为所有未来 design 的强制规范。
5. 将重复的字体仓库结构和通用安装命令替换为指向 `designs.md` 的链接；主题文档只保留自己的实际字体栈、`css_filename` 和工程引入说明。委派场景的字体预置规则不改。
6. 调整因删表产生的章节编号和交叉引用，例如 default 的“安装方式见 1.4”、GitHub 的“见 1.5”。
7. 保持三份 JSON 和所有 token 值不变；保持 `test_design_contract.py` 对唯一 CSS 块、token 集合和值的校验有效。

### 明确不改

- 本轮不生成 CSS、不删除 JSON、不改变任何 token 值。
- 不把字号阶梯、形状和通用元素全部搬到 `designs.md`。
- 不改备选配色、主题选择表或字体下载行为。

### 验收

```bash
source .venv/bin/activate && pytest \
  tests/test_design_contract.py \
  tests/test_design_docs.py
```

再检查三份主题文档各只剩一个 CSS 值来源，所有相对链接和章节引用有效，JSON 与 CSS 的 token 字典仍完全相等。

## 7. DOC-05：增加 layout Markdown/JSON 一致性测试

### 问题与证据

preset 文档声称区域表与 JSON 一致，但现有 `tests/test_video_contract.py:178-210` 只验证 JSON 契约。流水线最终读取 scene-config 落盘值，因此本 ticket 是 preset 库的质量门禁，不改变运行时数据流。

### 改动文件

- 新增 `tests/test_layout_docs.py`。
- 仅当测试发现真实文档漂移时，修正对应 `modules/layouts/*.md` 或 `modules/layouts/layouts.md`；预设数值有争议时以当前 JSON 为基准，不在本 ticket 改设计。

### 实施步骤

1. 用显式用例表描述四份 JSON 与文档的对应关系：
   - `presenter.json` → `presenter.md` 的唯一区域表；
   - `stage.json` → `stage.md` 的唯一区域表；
   - `portrait.json` → `portrait.md` 的 1080×1920 章节；
   - `portrait-3x4.json` → `portrait.md` 的 1080×1440 章节。
2. 只解析区域表中的“位置（左, 上）”和“尺寸（宽×高）”列，按表内顺序映射 JSON `regions[]`；逐项比较 `{x,y,width,height}`。覆盖 ground、header/main/side、person、nav-bar、caption-bar、caption-text，而不只检查主内容区。
3. 校验 JSON `canvas` 与 ground rect、文档所属画布一致；`caption.width_px` 与 `caption-text` rect 宽度一致。
4. 解析 `layouts.md` 汇总表，校验每个 preset 的 canvas、字幕宽度、字号和最大行数与 JSON 一致。
5. 测试失败信息包含 layout、region id（或表内行名）、字段和两边数值，便于直接修文档。
6. 不解析 ASCII 示意图，不把所有含数字的 prose 变成脆弱契约，不为本测试引入第三方 Markdown 依赖。

### 明确不改

- 不改变 scene-config 的实际区域来源，不要求运行时反向读取 preset。
- 不删除独立工具的 `--layout` 入口。
- 不顺手删除 `layout_file_problem()` 或调整其生产调用；那是另一项代码清理。

### 验收

```bash
source .venv/bin/activate && pytest \
  tests/test_layout_docs.py \
  tests/test_video_contract.py \
  tests/test_scene_config.py
```

用一个临时 mismatched rect 调用比较辅助函数，确认测试不仅能在当前文档上通过，也会报告具体漂移。

## 8. DOC-06：删除冗余的 `caption_font_px`

### 问题与证据

三个 design JSON 都带 `caption_font_px: 36`，但生产脚本没有读取它。实际字幕规格来自 scene-config 每个 scene 的 `layout.caption`；`check-composition` 只从 design JSON 读取 `min_font_px`，`fonts-download` 只读取 `fonts`。

### 改动文件

- `modules/designs/default/default.json`
- `modules/designs/github/github.json`
- `modules/designs/producthunt/producthunt.json`
- `modules/designs/designs.md`
- `modules/designs/default/default.md`
- `modules/designs/github/github.md`
- `modules/designs/producthunt/producthunt.md`
- `modules/modules.md`
- `tests/test_design_contract.py`

### 实施步骤

1. 从三个 design JSON 删除顶层 `caption_font_px`，不改 `tokens`、`min_font_px` 或 `fonts`。
2. 从 `designs.md` 的机器契约说明和 JSON 示例删除该字段；明确字幕字号不属于 design JSON。
3. 从 `modules.md` 的新主题扩展规则删除该字段。
4. 修改三个主题文档的“字号下限”行：保留 reading/ui 下限，删除“字幕 36px”这一 design 值，改为指向实际 scene 的 `layout.caption.font_size_px`；可说明借用 preset 时来自对应 layout JSON。
5. 将 `test_font_floors_and_caption_size_match_the_markdown` 改成只检查 reading/ui 下限，删除 caption 正则和相等断言；增加 `caption_font_px not in contract` 的回归断言。
6. 搜索现行 `modules/`、`references/`、`scripts/`、`tests/`，确保没有遗留消费或 schema 要求。历史计划/调研中的字段说明不算运行时代码引用。

### 兼容性与明确不改

- 旧工作区副本即使仍带这个字段也不受影响，因为生产脚本不读取它；无需迁移或删除旧工作区文件。
- 本 ticket 只保证仓库内契约，不声称审计了不可见的外部工具。
- 不改 layout JSON、scene-config、字幕切分、字幕组件或 QA 行为。

### 验收

```bash
source .venv/bin/activate && pytest \
  tests/test_design_contract.py \
  tests/test_design_docs.py \
  tests/test_scene_config.py \
  tests/test_scene_subtitles.py
```

## 9. DOC-07：将 transitions 提升为顶级模块类别

### 问题与证据

`tile-wipe` 当前位于 `modules/components/transitions/tile-wipe/`，但它承担 scene 交接层。移动本身不改变运行接口；容易遗漏的是 `tests/test_scene_components_browser.py:449` 的真实源码路径，以及 storyboard 对 `VIDEO.cuts` 数据来源的记录要求。

### 目标结构

```text
modules/
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
      tile-wipe.mjs
```

### 改动文件

- 移动上述 `tile-wipe` 三个文件，新增 `modules/transitions/transitions.md`。
- `modules/modules.md`
- `modules/components/components.md`
- `modules/motion.md`
- `modules/patterns/patterns.md`
- `modules/layouts/presenter.md`
- `modules/layouts/stage.md`
- `modules/layouts/portrait.md`
- `modules/templates/github/github.md`
- `references/delegation/composition/base-instructions.md`
- `references/delegation/composition/handoff-template.md`
- `references/phases/08-composition.md`
- `tests/test_prepare_handoff.py`
- `tests/test_phase_docs.py`
- `tests/test_scene_components_browser.py`

### 实施步骤

1. 用保留历史的目录移动把 `modules/components/transitions/tile-wipe/` 移到 `modules/transitions/tile-wipe/`；不复制出两套实现。
2. 新增 `transitions/transitions.md`，只说明：
   - 转场的职责与现有目录；
   - 什么时候采用或保持简单接缝；
   - 选定后读具体模块文档、复制 HTML/MJS 和接线；
   - 常驻挂载的视频秒与工程局部秒规则；
   - 自由布局不强制使用转场。
3. 更新 tile-wipe 文档标题、文件/复制路径和 HTML 顶部文档注释。`data-composition-id="tile-wipe"`、根 id、`VIDEO.cuts`、z-index、工程内文件名和 `init` 签名全部不变。
4. 更新 `modules.md` 的目录、分层、组装与扩展规则；避免写死“四类”这类易过期计数。`components.md` 删除 tile-wipe 行，并把“这四个组件”等数量和迁移列表改成实际剩余的 Jay/nav-bar/caption-bar。
5. 更新 motion、patterns、三个 layout 和 GitHub 模板中的旧路径；layout 的“组件 transitions/tile-wipe”改为“转场 tile-wipe”。
6. storyboard 的“组件使用表”改为“组件与转场使用表”：每个实际使用的组件或转场一行，继续记录挂载参数和 `window.VIDEO` 数据来源，因此 `cuts` 不会因分类移动而漏记。同步基础指令、handoff Outputs 和文档测试。
7. 基础指令在需要转场时指向 `modules/transitions/transitions.md` 和具体模块文档；组装资源清单同时涵盖 transitions。
8. handoff 的“可选参考”从 patterns/motion 扩为 patterns/motion/transitions；Phase 8 的 8.2 描述同步。不要把 transitions 变成所有场景的无条件必读或必用模块。
9. 更新 `test_prepare_handoff.py` 的可选参考路径集合；更新 `test_scene_components_browser.py` 的 mount source 为 `transitions/tile-wipe`。
10. 在现行 `modules/`、`references/`、`scripts/`、`tests/` 搜索 `components/transitions` 和 `transitions/tile-wipe`：前者应清零，后者只能表示新的顶级相对路径 `modules/transitions/...`，不能残留 `modules/components/transitions/...`。历史 docs 不作为现行引用处理。

### 明确不改

- 不新增机器注册表，不改 `prepare-handoff.py` 的整库物化逻辑。
- 不改转场视觉、时间参数、数据格式或渲染方式。
- 不要求所有自由布局使用 tile-wipe，不新增其他转场实现。

### 验收

```bash
source .venv/bin/activate && pytest \
  tests/test_prepare_handoff.py \
  tests/test_phase_docs.py \
  tests/test_scene_components_browser.py
```

浏览器测试必须实际执行 tile-wipe 用例，不能把 skip 当作通过；确认加载的是新路径、没有旧路径副本，并仍验证 timeline 暂停/seek、无旧 HyperFrames 全局耦合和组件实例行为。

## 10. 总验收与交付要求

所有 ticket 完成后：

1. 运行完整测试套件：

   ```bash
   source .venv/bin/activate && pytest
   ```

2. 对文档改动做链接与语义检查：
   - patterns/motion 指向 composition 第四部分的链接仍解析；
   - handoff 的每个 Required/Optional Reference 都存在，且 Required 顺序与测试一致；
   - 所有模块类别都遵守“用户指定或特别匹配才采用，否则即时生成”，阅读索引不等于采用；
   - 不出现主 agent 预选全片 template/layout、`supported_layouts` 硬门槛或 composition 必须读 research brief 的新表述；
   - SEL-02 后，无用户指定 design 的 inputs 不再默认选择 default，custom design 与 preset 都经 `composition/design.json` 验收；
   - design token 值、min font、字体清单、layout 数值和 scene-config schema 没有被非目标 ticket 改到。
3. 对 DOC-07 检查浏览器测试真实运行，不只是收集或通过 skip；对 SEL-02 检查无预设 design 和 custom design 两条真实命令路径。
4. 最终 diff 只包含本计划要求的文档、测试、handoff/状态/契约脚本、composition design 读取器和 transitions 移动；不生成视频、字体、缓存或临时报告。
5. 若某个 ticket 的测试失败，只在该 ticket 范围修复；不把失败通过删除契约断言或缩小测试覆盖来处理。

## 11. 实施假设

- 当前仓库内调用链是本次兼容边界；不可见的外部消费者不在审计能力内，尤其是 design JSON 的冗余字段。
- Markdown CSS + JSON 的自动相等测试在本轮足以防止库内 token 漂移；生成式单一来源留到有独立需求时再立项。
- design 的机器基线保持全片一份；用户明确限定到单个 scene 的 design 采用局部 token 覆盖，不把全片契约改成逐 scene 大字段。
- 旧工作区已有 `inputs.json.design` 视为既有用户约束并保留；新工作区未明确指定时不再自动写 default。
- 文档测试用于固定职责与关键不变量，不做整篇文案快照，也不把 ASCII 图变成解析接口。
- 每个 ticket 可单独提交；依赖关系只用于避免语义回归和同文件冲突，不要求合并成一次大重构。
