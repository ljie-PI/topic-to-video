# Phase 08：逐场景视觉配置、依赖清理与委派约定重构计划

日期：2026-11-07  
状态：已实施。WI-01 / WI-02 / WI-04 / WI-05 由 #147–#152 交付，WI-03 / WI-06 / WI-07 由 #153 交付；WI-08「必须做」的联网禁令清理已做，自动下载条件项按 10 行门槛评估为「无安全路径」并跳过（结论记录在 #153 完成报告）；WI-09 的集成验收由 #154 完成，验收记录见本节末尾「WI-09 验收记录（#154）」。本文件保留为历史计划与决策依据，现行指令以仓库内 references/ 与 modules/ 文档为准。  
依据：用户对 `docs/phase-08-review-answers.tmp.md` 的本轮 15 条批注；本轮要求优先于临时答复和旧计划。

**本轮只编写 plan。实现、删除、迁移、下载及真实模型调用都留到实施阶段。**

## 1. 目标与范围

把 Phase 08 改成一条清楚的流程：主 agent 准备并派发；composition 子代理根据叙事场景，**逐个视觉场景独立选择 template / layout**，生成 storyboard、字幕和画面，检查后渲染；主 agent 验收。

同时清理全流程指纹追踪、字幕编辑禁令、过度的 HyperFrames 耦合、重复委派说明和演示工程引用。

### 本计划对关键要求的解释

- **storyboard 由 composition 子代理生成**，不是主 agent，也不是 HyperFrames 生成。主 agent 不补写它来替子代理过验收。
- 允许使用 `hyperframes` / `hyperframes-cli` 两个 skill。其他 HyperFrames 扩展 skill、模块目录和 recipe 入口从本项目依赖中移除。
- “不依赖 HyperFrames”落实到可复用模块：项目自己的组件 / 模板不读取 HyperFrames 专用变量接口、不负责注册其时间线。选用 HyperFrames 时，必要的核心工程协议仅存在于生成的视频工程中，不反向成为模块库的公共接口。
- 保留项目自己的 design、layout、组件、模板和素材；这不等于把整个 `modules/` 删掉，也不引入新的渲染框架或多后端插件平台。
- 委派默认值、命令和模型选择规则集中在 `references/delegation/conventions.md`。**不新增临时答复里建议的 `agents.json`。**
- 字体自动下载是有行数上限的条件项；超过 10 行的实现不做，但删除“禁止 / 强调不联网”的表述照常进行。

### 保留的能力

事实与素材引用校验、字数预算、语音对齐、文件 / JSON 基本验收、渲染前实际画面检查、Phase 9 QA 与 BGM 混音、用户审稿和显式重做。删除指纹不是删除这些检查。

## 2. 批注到 work item 的对应

| 批注 | 落地要求 | Work item |
| --- | --- | --- |
| 1：简要说明 Phase 08 的输入 | `script.txt` 补一句显示稿用途；其他输入保持短说明 | WI-06 |
| 2：删除重复说明 | 删除输入后“模板与 layout 都在本阶段确定”的独立段落 | WI-06 |
| 3：谁生成 storyboard | composition 子代理负责；handoff / 基础指令 / 主 agent 验收说明一致 | WI-05、WI-06 |
| 4：清理指纹机制 | 清理报告指纹、全流程打戳、过期、缓存、偏移表哈希和审稿哈希绑定 | WI-01 |
| 5：去掉字体归 HyperFrames 的说法 | 资源由本 skill 提供，composition agent 引入字体 CSS | WI-06 |
| 6：去掉字幕修改禁令 | 默认脚本生成，允许编辑；保留已有用户修改，不增加新的编辑许可门槛 | WI-04、WI-06 |
| 7：场景归 composition agent | 区分叙事规划与画面实施，并在子代理真正读取的指令中说明 | WI-05、WI-06 |
| 8：仅保留两个 HyperFrames skill | 清理其他外部依赖及可复用代码中的专用运行时耦合 | WI-03 |
| 9：不重复默认 Pi 提示 | 各 phase 引用统一约定，不复述默认 agent / 命令 / 模型规则 | WI-05、WI-06 |
| 10：删除动画 skill 引用 | 同步清理阶段文档、motion 入口及其间接引用 | WI-03 |
| 11：顺序正确，且逐场景选择 | 场景级配置替代全片视觉决策；字幕与检查同步消费它 | WI-02、WI-04、WI-05 |
| 12：简化阶段文档 | 只保留输入输出、执行、必要约束、完成条件 | WI-06 |
| 13：清理演示工程 | 删除指定目录及项目内引用，保留与之无关的测试行为 | WI-07 |
| 14：字体实现最多 10 行 | 先删除联网禁令；安全实现不超过上限才做，否则跳过下载行为变更 | WI-08 |
| 15：集中模型说明，支持近似匹配 | 经目标 coding agent CLI 查询真实模型，记录请求与实际选择，传入实际调用 | WI-05 |

## 3. 目标结构与职责

### 3.1 术语

| 术语 | 定义与责任 |
| --- | --- |
| 叙事场景 | Phase 6 的 `scene-plan.json` 条目：段落、intent、content_plan、候选素材和 cues；由 script agent 产出 |
| 视觉场景 | Phase 8 实际展示的一段画面；可以对应一个或多个叙事场景，也可以从一个叙事场景拆出多个 |
| template | 可借用的场景内容 / 组装方案；每个视觉场景单独决定是否采用及采用哪个场景部分 |
| layout | 当前视觉场景的实际区域与字幕规格；可来自现有预设，也可以自主设计 |
| storyboard | composition agent 的画面实施说明：构图、素材、动效、组件及必用素材覆盖，不重复写旁白 |
| scene-config | 供字幕与检查脚本消费的最终视觉场景配置，不存叙事全文或源文件指纹 |

### 3.2 执行流程

```text
主 agent
  按 conventions 解析 agent / 查询并选择实际 model
  整理 composition_requests
  prepare-handoff composition（不预选 template / layout）
  派发 dispatch_prompt
       ↓
composition 子代理
  读显示稿、叙事场景、真实时间、素材和用户要求
  对每个视觉场景：指定要求 → 匹配 template → 匹配 layout → 自主设计
  写 scene-config.json + storyboard.md
  生成缺失的字幕初稿，或沿用 / 编辑已有字幕
  用项目模块实现画面；按需使用允许的两个 HyperFrames skill
  渲染前检查 → 修复 → 渲染 final.mp4
       ↓
主 agent
  pipeline-status 基本验收 + 必用素材 / 关键画面抽查
  不合格交回原 composition agent 定向修复
       ↓
Phase 9
  按实际视觉场景 QA → BGM 混音
```

### 3.3 全片属性与场景属性

- 全片仍统一 `orientation`、画布尺寸、design、配音和显示稿。
- template / layout **不是全片锁定属性**，相邻 scene 可以完全不同。
- Phase 8 不再把选定 template / layout 回写成 `inputs.json` 的全片结果，也不以这两个字段作为准备 handoff 或完成阶段的门槛。
- 用户指定视觉方案继续记在 `composition_requests`，说明作用范围：某个叙事场景、某个视觉场景或整片。不新增一套用户要求 schema。
- 已有工作区的全局视觉字段不能自动复制到每个 scene、冒充用户明确要求；保留原文件，不做未经确认的数据删除，最终决定写入新场景配置。
- 逐场景独立选择不等于每场都必须不同；共享方案可以复用，但不能从第一个 scene 自动继承到所有 scene。

### 3.4 文件结构变化

```text
scripts/
  scene_config.py                         新增：公共场景配置读取 / 校验
  composition_hash.py                     删除：专用指纹实现
  prepare-handoff.py                       更新：不预选视觉方案，接收实际模型
  align-narration.py / check-composition.py 更新：逐场景配置输入

references/delegation/
  conventions.md                          更新：统一目标 / 命令 / 模型选择
  composition/
    base-instructions.md                  更新：子代理职责与逐场景顺序
    handoff-template.md                   更新：输入、产物、执行命令
    scene-config.md                       新增：子代理读取的数据契约

modules/
  components/<name>/<name>.html            保留标记 / 样式，移除 vendor 脚本
  components/<name>/<name>.mjs             新增普通初始化入口
  templates/github/<scene>.html, .mjs      同样拆分场景标记与初始化

<视频工作区>/composition/
  scene-config.json                       新增：子代理产出的逐场景配置
  storyboard.md                           保留：子代理产出的设计说明
  assets/subtitle-units.json              更新：逐场景字幕，允许编辑
  index.html / compositions/ / renders/   保留工程与渲染结果
```

## 4. 数据结构与接口细节

### 4.1 新产物：`composition/scene-config.json`

选择一个机器可读产物作为视觉场景的唯一配置来源。它和 storyboard 由同一个 composition agent 产出：前者存脚本需要的数据，后者存设计说明和理由。

新增公共读取 / 校验模块 `scripts/scene_config.py`，由状态、字幕和渲染前检查共用。统一入口 `load_scene_config(path, *, expected_canvas=None, known_scene_ids=None, modules_root=None)` 返回校验后的配置；调用者传入已经掌握的画布、源场景和模块位置，不在此模块做视觉选择或渲染。避免三个脚本各写一份选择或布局规则。

数据契约写在子代理委派包的 `references/delegation/composition/scene-config.md`，handoff 的 Required References 必须指向其工作区副本。基础指令仅保留使用顺序和该契约的阅读入口，不再次复制完整 schema。文档里的 JSON 示例也通过同一个读取接口测试，不能让本计划成为运行时唯一的格式说明。

结构示例（展示一个完整的自由布局场景）：

```json
{
  "version": 1,
  "canvas": {"width": 1920, "height": 1080},
  "total_s": 8.0,
  "scenes": [
    {
      "scene_id": "visual_001",
      "source_scene_ids": ["scene_1"],
      "begin_s": 0.0,
      "end_s": 8.0,
      "template": null,
      "layout": {
        "preset": null,
        "regions": [
          {
            "id": "main",
            "kind": "content",
            "rect": {"x": 96, "y": 80, "width": 1728, "height": 820}
          },
          {
            "id": "caption",
            "kind": "reserved",
            "component": "caption-bar",
            "rect": {"x": 96, "y": 930, "width": 1728, "height": 120}
          }
        ],
        "caption": {"width_px": 1728, "font_size_px": 36, "max_lines": 2}
      }
    }
  ]
}
```

字段规则：

- `template` 必须明确落地：不用为 `null`；采用时为 `{"name": "github", "scene": "project-cover"}` 这样的模板名 + 场景部分对象。它与 Phase 6 的场景计划是不同 schema。
- `layout.preset` 记录借用的预设名，未借用为 `null`；**实际的 regions / caption 必须完整落盘**，检查不从预设名猜坐标。
- 自由布局不需要注册到 `modules/layouts/`，也不默认加人物、导航或某种固定分区。
- `source_scene_ids` 指向输入叙事场景；合并 / 拆分的映射及理由写在 storyboard。
- 场景区间使用真实语音时间，按 `[begin_s, end_s)` 归属；最后一帧属于最后一场景。主场景区间有序、不重叠，覆盖视频区间；转场视觉重叠由画面实现处理。
- `total_s` 以交付视频的配音时长为边界，包含语音前后的静音画面；不通过改 Phase 7 时间轴来凑时长。
- 校验画布、有限数值、合法时间范围、源场景引用、区域几何、正的字幕规格及模板资源存在性。失败定位到 `scene_id` 和字段。
- 不加入哈希、源文件修改时间、构建版本号或“是否最新”的替代追踪字段。

### 4.2 逐场景的选择顺序

composition agent 对每个视觉场景执行：

1. 先应用该场景的明确用户要求；整片要求仅在其作用范围内应用。
2. 用户指定 template 时先处理它；未指定时，只有非常匹配的 template 才采用。
3. 采用模板后，根据它的推荐布局及用户要求确定本 scene 的布局；没有模板才自由匹配现有 layout。
4. 没有指定或非常匹配的 layout 时，自主构图，写出实际区域与字幕规格。
5. 没有模板并不是失败；`template: null` 加自由布局是正常完成路径。

模板目录从“整支视频锁定一个组装方案”改成“可按场景借用”。`modules/templates/github/github.json` 的 `supported_layouts` 改为推荐性的 `preferred_layouts`，保留场景与真实朗读锚点声明。准备脚本不再据它约束全片；执行者根据内容、画布和实际可读性判断是否适用。

模板的专属配色、人物、导航和转场仅作用于采用它的 scene / 明确要求的区间，不强制传播到其他 scene。用户指定方案与朝向或另一条明确要求冲突时报告冲突，而不是静默换掉要求。

### 4.3 字幕与 QA 消费同一份配置

- `align-narration.py --mode subtitles` 新增 `--scene-config`。与单布局 `--layout` / 显式容量参数互斥；这些原有接口仍用于独立工具调用，不作为流水线的全片布局方案。
- 一次读取和对齐显示稿 / 朗读稿 / transcript，按实际视觉场景分组，再复用现有字幕切分逻辑；各 scene 使用自己的 caption 容量，不重复 ASR，也不取全片最小容量代替场景规格。
- 输出仍是一个 `composition/assets/subtitle-units.json`，保留现有文字、秒 / 毫秒、段落字段，增加 `scene_id`，便于定向编辑和排版。
- 不让自动合并短字幕跨过不同场景的布局切点。对齐 atom 跨切点且不能完整归属时，返回涉及的 scene 与真实可用时间边界，由 composition agent 调整视觉切点或编辑字幕；不静默截断、重复或丢弃文字。
- timing 模式不读场景布局、不覆盖 Phase 7 时间轴；模板额外 cues 继续输出到 composition 自己的时间文件。
- `check-composition.py` 新增 `--scene-config`；按正在检查的 scene 取它的 regions / caption。保留单布局接口作为独立工具能力，不在新 handoff 中使用它。
- 报告继续用现有 finding 形状 `{scene_id, check, issue, time_s, frame}`；保留越界、溢出、字体、资源和当前字幕一致性检查，不检查编辑来源。
- Phase 9 的 `check-render.py` / `make-contact-sheet.py` 通过现有 `--timeline` 参数读取 `scene-config.json` 中的 `scenes`。复用 `scripts/timeline_scenes.py` 的公共字段读取，不再按可能已经拆并前的叙事场景做 QA。

字幕编辑规则采用正向说明：**默认脚本生成初稿，实际制作中可以编辑文本与边界；已有用户编辑是有效输入。** 继续生成只发生在缺失字幕或当前任务明确需要重新生成时；仅改画面 / 重渲染不先覆盖字幕。不新增人工字幕标记、锁文件、编辑许可 gate 或指纹。

### 4.4 可复用模块的 HyperFrames 解耦

清理分为两个层次：

1. 外部依赖只保留允许的两个 skill；删除 animation、keyframes、registry 等其他 HyperFrames 扩展的调用 / 索引 / recipe 指引。扫描后发现同类入口也按此规则清理。
2. 六个现有组件 / 场景保留视觉代码，改为普通 HTML / CSS 加显式初始化入口。

需要调整的六个模块：

- `modules/components/jay/`
- `modules/components/nav-bar/`
- `modules/components/caption-bar/`
- `modules/components/transitions/tile-wipe/`
- `modules/templates/github/project-cover.*`
- `modules/templates/github/trending-overview.*`

建议接口：HTML 保留静态标记和样式，脚本抽到同目录 `<name>.mjs`，导出 `create(root, {params, data, duration, gsap})`，返回暂停的 GSAP timeline。DOM 查询限定在传入的 root，数据与时长显式传入；不读取 `window.__hyperframes`、不找 HyperFrames host 来推断参数、不向 `window.__timelines` 注册。

此处的 seam 是模块初始化接口。普通浏览器可直接初始化和 seek；使用 HyperFrames 的生成工程负责把返回的 timeline 按核心协议注册到其 scene host。这部分是工程的 adapter，不是可复用模块的责任。保留 GSAP 不等于依赖 HyperFrames。

检查脚本通过现有通用入口 `window.__layoutQA.seek(videoSeconds)` 驱动画面。清理快照脚本对 `__hfAnime` / `__timelines` 的枚举和对 `data-composition-id` 的区域归属依赖，改用项目自己的 DOM id / 区域归属属性。入口未实现或 seek 失败时明确报错，不把未 seek 的静态快照当通过。

只在生成工程中使用 HyperFrames 核心协议，不在仓库另建一套 HyperFrames 扩展库。外部安装的 skills、CLI 或用户全局配置不在卸载 / 修改范围内。两个保留 skill 中指向其他扩展的建议，以本项目用户要求优先，不能形成传递依赖。

限制还要进入实际派发方式：在 conventions 中说明仅对本次 composition 调用使用目标 CLI 的 skill 选择能力。Pi 官方支持 `--no-skills` 后显式传入两个 `--skill <实际路径>`；实施先核对本机帮助及路径，再使用它，避免自动发现的额外 HyperFrames skill 被加载。其他委派步骤不因此禁用自己的能力，也不修改用户全局 skill 配置；其他目标使用其本机确实支持的方式，不照搬 Pi 参数。

### 4.5 指纹删除后的状态模型

`pipeline-status.py` 保留适用阶段、产物检查、后续 pending、审稿和显式 redo；删除内容变化探测。

- 删除 `FpCache`、`Fingerprinter`、`Stamps` 及哈希、归一化、比较、协调、重新打戳等专用方法与调用。
- 删除 `--restamp`、自动 `stale/unverified` 分支及相关输出字段；不再读写打戳 / 指纹缓存文件，也不做隔离恢复。
- `check-composition` 报告删除 `sources_sha256`，状态验收只检查实际报告数据与通过结论，不用源文件 mtime 或另一种摘要替代。
- `make-narration.py` 和 `video_contract.offsets_problem()` 删除两个源文本哈希字段及校验；保留偏移表版本、长度和 segments。
- 用户确认按 gate 保存确认事实和时间，不绑定文件哈希。显式重做一个带审稿 gate 的阶段时，清除该 gate 的旧确认；没有请求审稿的阶段仍全自动。
- `--finish` 保留现有登记结束顺序与基本产物验收，去掉“必须所有字节都变过”的验证；不替用户审批。
- 上游改动后的影响由执行 agent 根据已知修改范围显式登记，不从文件变化推断。只要求重做某阶段时不自动登记所有阶段；完整重做要求才逐项处理。

例如，任务要求重新交付完整成片时，Phase 8 重渲染后主 agent 需显式登记 / 执行 Phase 9，更新 QA 与 BGM 结果；用户只要求 Phase 8 时按该范围停止。不能一边删除自动失效，一边继续假设旧 QA / 混音会被状态脚本自动识别出来。

`scripts/composition_hash.py` 整个删除；目录非空检查需要的 `visible_files()` 留在状态检查内部即可，不为一个调用方新增公共模块。

URL 哈希命名、下载结果 mtime 识别、语音时间戳、音画时长和文件非空检查不属于本次删除的指纹追踪。

### 4.6 委派与模型选择的唯一说明

`conventions.md` 集中说明：默认目标、全局 / 阶段覆盖、每个目标的真实 CLI 入口、模型查询和近似选择、实际派发方式。Phase 1 / 5 / 6 / 8 和 handoff 模板只引用它；生成 handoff 仍展示**本次实际 agent / model**，这不是重复默认说明。

保持 `inputs.json.delegation.catalog/script/composition` 的现有 agent / model 字段，不新增默认配置注册表。原始 model 请求保留在输入中，实际模型由主 agent 在生成 handoff **之前**解析：

1. 用目标 coding agent 的 `--help` 核对本机命令，不用当前主 agent 的模型目录替代。
2. Pi 用 `pi --list-models "<请求>"` 查询；结果为空时用 `pi --list-models` 获取其真实候选。其他 agent 使用它自身帮助中声明的查询方式。
3. 有精确原生标识就选精确值；没有时，在 CLI 实际列出的 chat 模型里匹配最接近的名称 / 系列 / 版本 / 变体，满足当前阶段能力需求。
4. 用户明确指定 provider 时优先限定该 provider；未指定时优先目标 CLI 中已有可用认证的候选。catalog / 看图任务需要图像输入能力。
5. 找到明确的近似候选可以直接采用，向用户简短说明“请求 → 实际模型”，不保留旧规则中“只要不是精确匹配就必须停下确认”的要求。
6. CLI 不可用、无可用候选、必须改变明确指定的 provider、或候选无法合理区分时报告阻塞 / 寻求决定；不换成另一个 coding agent，不编造模型 id，不输出凭据。

为保持 handoff 和实际调用一致，在 `prepare-handoff.py` 增加 `--resolved-model <实际原生标识>`：

- 有用户 model 请求时，先完成 CLI 查询，再传入解析结果；未解析时不要生成一份把模糊请求冒充执行模型的 handoff。
- 输入仍保存原始请求；handoff 的 Coding Agent 小节显示请求与实际模型。
- JSON 中 `coding_model` 返回实际值，另返回 `requested_model`；没有 model 请求时二者为 `null`，使用目标 agent 自身配置。
- `scripts/delegation_config.py` 继续做请求校验 / 覆盖解析；CLI 查询与近似判断由主 agent 按统一约定执行，不新增自动 shell 派发或模型发现脚本。

Pi 的实际派发形态仍为 `pi --model "<实际标识>" -p -- "<dispatch_prompt>"`；无模型请求时省略 `--model`。完整路径、带空格参数与 `--` 的引用处理继续保留。

## 5. Work items

各项完成前只勾本项 checklist；全部集成完成才勾最终验收。不要用删除旧测试替代验证保留的行为。

### WI-00 — 基线与精确改动清单

范围：仓库状态、相关脚本 / 文档、现有测试以及本地待清理目录。

- 实施前检查用户已有改动、补读有效 `AGENTS.md`（如新增）；记录本次修改起点，保留用户工作。
- 先跑现有相关测试，记录已有失败；区分已通过、环境缺失和未执行。
- 扫描指纹、外部 HyperFrames 入口、专用变量 / 时间线、字幕编辑禁令、重复 Pi 说明、演示目录引用。

Checklist：
- [ ] 所有修改 / 删除路径可追溯到本计划，不删除宽泛目录或仓库外安装。
- [ ] 既有失败与新回归分开记录。
- [ ] 后续工作使用本轮逐场景要求，而不是旧的全片 layout 计划。

### WI-01 — 删除全流程指纹与新鲜度追踪

依赖：WI-00。

文件：`scripts/pipeline-status.py`、`scripts/check-composition.py`、`scripts/composition_hash.py`、`scripts/make-narration.py`、`scripts/video_contract.py`、相关对齐 / 状态测试。

- 按 4.5 删除生成端、公共契约、消费端、CLI、状态字段和持久化调用，避免只删报告字段。
- 重写审稿的哈希绑定为确认事实，显式 redo 撤销对应旧审批；保留其他 gate 和用户要求。
- 清理旧夹具的哈希构造；移除只测试已删除机制的案例，保留长度、JSON、偏移、redo 与审稿测试。

Checklist：
- [ ] 报告没有源哈希也能通过基本验收；实际 `fail` 报告仍不能通过。
- [ ] 改源文件内容或 mtime 不产生自动过期、隔离、重新打戳要求。
- [ ] 状态不读写指纹状态文件；旧文件损坏也不影响新扫描。
- [ ] 显式 redo / finish、未批准 gate、基本缺失 / 损坏检测仍有效。
- [ ] `--restamp` 从帮助与参数接口消失；专用指纹文件无残留导入。

### WI-02 — 建立逐场景视觉配置

依赖：WI-00；WI-01 集成后不再保留旧视觉指纹。

文件：新增 `scripts/scene_config.py`、`references/delegation/composition/scene-config.md`、`tests/test_scene_config.py`；更新 `scripts/video_contract.py` / `scripts/pipeline-status.py`、`modules/templates/templates.md`、`modules/templates/github/github.json` 及对应测试。

- 实现 4.1 的公共读取 / 结构校验；Phase 8 把 scene-config 作为产物验收，不再以全局 layout / template 作前置条件。
- 调整模板声明和文档为场景级借用及推荐 layout，保留真实锚点与资源说明。
- 仅移除 composition 准备对全局视觉字段的要求；保留 design / orientation 和其他步骤输入规则。

Checklist：
- [ ] 同一片子支持“模板 + 预设”“无模板 + 预设”“无模板 + 自由布局”混合。
- [ ] 视觉场景合并 / 拆分后仍能关联叙事场景和真实时间。
- [ ] 不存在模板 / 布局时允许自由设计；不存在的已声明资源和非法配置有定位明确的错误。
- [ ] 修改一个 scene 的决策不会覆盖其他 scene 或输入的配音 / design / 朝向。
- [ ] 委派包契约示例通过公共读取接口测试；子代理不需要到旧计划里猜格式。

### WI-03 — 清理 HyperFrames 扩展并解耦项目模块

依赖：WI-00；场景组装按 WI-02 的契约集成。

文件：4.4 列出的六个模块、`modules/modules.md`、`modules/components/components.md`、`modules/motion.md`、组件 / 模板文档、`scripts/check-composition-snapshot.js`、模板执行测试。

- 提取普通初始化脚本，参数 / 数据 / 时长显式传入；修改挂载示例和模板参数说明。
- 保留主题、图片、Jay 动作、嘴型生成和原有可读性规则，不以解耦为由重画所有视觉资产。
- 删除其他 HyperFrames skill / recipe 入口；两个保留入口只使用核心能力，项目模块不通过改名后的 vendor 全局变量继续耦合。
- 快照检查使用通用 seek 和项目区域标识，seek 失败可见。

Checklist：
- [ ] 六个模块在不存在 HyperFrames 全局变量的普通浏览器中能初始化 / seek。
- [ ] 同一模块两次挂载，数据、DOM 查询和 timeline 互不串扰。
- [ ] 可复用源码不含 HyperFrames 变量注入、host 参数读取或时间线注册。
- [ ] 如果选用 HyperFrames，生成工程的最小 adapter 能通过其核心检查；不加载其他扩展 skill。
- [ ] 本机 / 仓库外的 skills 和 CLI 安装未被卸载或篡改。

### WI-04 — 逐场景字幕、画面检查和 Phase 9 衔接

依赖：WI-01、WI-02、WI-03。

文件：`scripts/align-narration.py`、`scripts/check-composition.py`、必要的 `scripts/timeline_scenes.py` 说明、`references/phases/09-check-mix.md`、字幕 / 快照 / QA 测试与夹具。

- 实现 4.3 的 scene-config 输入，保持独立工具接口可用，流水线只使用逐场景接口。
- QA 命令读取 composition 的最终场景，不覆盖 `transcribe/timeline.json`。
- 字幕一致性以当前编辑后的文件为准，不以脚本初稿或偏移表哈希证明编辑是否合法。

Checklist：
- [ ] 不同 caption 容量实际生成不同切分，短字幕不会跨不同 layout 被自动合并。
- [ ] 时间边界冲突不会造成文字丢失 / 重复或伪造时间。
- [ ] 三种场景配置分别接受自己的区域检查，不被全片预设误报。
- [ ] 用户手改字幕后，重新检查 / 渲染使用修改结果，不自动恢复初稿。
- [ ] Phase 9 finding / contact sheet 标注最终视觉 scene_id；timing 模式与 Phase 7 字节内容不变。

### WI-05 — 重构统一委派、模型查询与 handoff

依赖：WI-02；与 WI-03 / WI-04 的实际命令集成。

文件：`references/delegation/conventions.md`、三个 `handoff-template.md`、composition 基础指令、`scripts/delegation_config.py`、`scripts/prepare-handoff.py`、委派 / handoff 测试。

- 按 4.6 集中所有目标 / 模型规则；主 agent 查询目标 CLI 再准备 handoff，实际选择与请求分开显示。
- composition 的 STEP_INPUTS_FIELDS、`composition_plan()`、`render_handoff()` 不再预选 / 验证全片视觉方案；Required References 给出模板、布局的发现入口，而不是一个已锁定布局。
- 新增 resolved-model 传递，所有三个委派步骤使用同一规则；不新增 agent 配置注册表或自动派发脚本。
- handoff 明确把 scene-config、storyboard、字幕、画面与渲染交给 composition 子代理；先设计每个 scene，后生成字幕。

Checklist：
- [ ] 没有全局 layout / template 也能准备 composition handoff；输出产物不在准备前被要求存在。
- [ ] 三个阶段分别指定不同模型可保留并实际选中。
- [ ] 精确与近似请求均经目标 CLI 查询；近似选择清楚展示请求和实际值。
- [ ] 未解析请求、CLI 不可用、空候选有明确处理，不静默改 agent 或虚构 id。
- [ ] handoff / JSON / 实际命令使用同一个 resolved model；带空格路径和 prompt 引用仍正确。
- [ ] storyboard 的执行者写在子代理实际读取的文档里，不只写在主 agent 的 phase 说明里。

### WI-06 — 简化 Phase 08 与同步相关指令

依赖：WI-01 至 WI-05。

文件：`references/phases/08-composition.md`、Phase 1 / 5 / 6 / 7 / 9、`SKILL.md`、`references/pipeline-control.md`、相关基础指令与文档测试。

Phase 08 目标结构：

1. 输入 / 输出：每个文件一句用途；`script.txt` 标为显示稿，是字幕、屏幕文字和 cue 的来源。
2. 执行：主 agent 准备并派发 → composition agent 逐场景设计与制作 → 主 agent 验收。
3. 必要约束：真实语音时间、用户要求、叙事 intent / content_plan 和必用素材。
4. 完成条件：配置与产物齐全、实际检查通过、渲染成功；Phase 9 只用一句入口指引。

- 删除重复职责段落、“字体 / scene 归 HyperFrames”、布局先行、全片模板回写、指纹和新鲜度说明。
- 删除字幕不能手改、拆并、排序的禁令，含 Phase 7 的字幕问题处理说明；不把新的绝对禁止句换个位置保留。
- Phase 6 明确输出叙事目标，Phase 8 明确由 composition agent 实现画面；catalog 的下游称谓也同步纠正。
- 各 phase / 模板仅引用 conventions 的委派规则。更新要求硬编码旧措辞 / 默认 Pi 提示的测试。
- 文档结构测试只调整 Phase 08 所需部分，不把它的新组织方式强加给其他 phase。

Checklist：
- [ ] 文档一次阅读能看到主流程，不展开 Phase 9 的完整 QA 或内部状态实现。
- [ ] 阶段、handoff、基础指令对职责、顺序、场景粒度、字幕编辑规则一致。
- [ ] 默认 agent / 命令 / 模型规则只在 conventions 维护；实际 handoff 的本次目标仍清楚。
- [ ] 入口不再把 layout / template 描述为整片唯一决策。

### WI-07 — 删除演示目录、失效引用与旧指导

依赖：WI-03、WI-05、WI-06。

精确目录：`modules/examples/`、`video-modules/examples/`；先核对目录中的用户新增内容，按本计划范围删除，不连带删除整个 `video-modules/`。

- 清理 `modules/modules.md`、Jay / GitHub 模板文档、委派约定、handoff 和复制代码中的目录指引 / 排除参数。
- 移除只测试已删除目录存在或排除的案例；Phase 4 的 JSON 示例测试保留行为，必要时改其含该目录词的英文方法名。
- 旧 `docs/plans/` 不再充当现行指令，标明历史状态并清理仍会指向删除项的要求；不直接删除与本任务无关的历史计划。
- 临时答复和本计划暂存删除路径，便于审阅。实施收尾时整理成不含失效符号 / 目录引用的完成记录，保留需求与验收结论；不因全仓扫描而直接丢弃用户批注材料。

Checklist：
- [ ] 两个指定目录及其隐藏生成产物已清理，非目标资产保留。
- [ ] 源码、测试、工作流文档和最终整理后的项目文档不再引用被删除的演示目录。
- [ ] 不把旧计划中的指纹 / 额外 skill 要求重新带回实际 handoff。
- [ ] 没有用复制 / refresh 自动覆盖已经被用户编辑的视频工作区；已有副本升级先核对再按需 refresh。

### WI-08 — 字体最小改动，执行 10 行门槛

依赖：WI-00；不阻塞其他 work item。

文件：`scripts/fonts-download.sh`、必要时 `scripts/prepare-handoff.py`、Phase 08 / 模块字体说明及字体测试。

**必须做：** 删除“禁止下载 / 强调不联网”的说明；字体来源、CSS 引入和现有错误传递保留。不要把未实现的自动下载写成现有能力。

**条件做：** 只有字体自动补齐的生产代码新增 + 删除合计不超过 10 行，且能安全复用已有下载能力时才实现。必要测试 / 文档单独报告；实现计数包括所有相关生产文件，不能搬代码、压成多语句单行或引入 helper 隐藏超限。

当前 `refresh()` 会替换主题 CSS、调用 `prune_pool()`，不是一个无副作用的单文件补齐函数。因此先检查是否有安全的 ≤10 行路径；如果需要修改多个函数来控制清理、事务或缓存，**跳过自动下载行为变更**，保留现有缺失错误与已有显式下载入口。

Checklist：
- [ ] 禁止联网措辞移除，但真实能力说明准确。
- [ ] 自动下载若实现，生产 diff 计数 ≤10 行；否则明确记录“超过上限 / 无安全路径，未实现”。
- [ ] 不无条件调用仓库维护式 refresh，不意外清理其他字体或用户文件。
- [ ] 本地字体正常安装、缺失处理和 JSON 错误传递仍通过测试。

### WI-09 — 集成验收与完成记录

依赖：全部其他 work item；WI-08 的下载条件项允许按规则跳过。

- 用一个临时工作区跑真实准备脚本、字幕脚本和状态验收；语音可用现有 fake 后端，不调用付费 TTS / ASR。
- 构造至少三场景：采用模板的 scene、另一种预设布局的 scene、自由布局的 scene；在中间 scene 手改字幕。
- 普通浏览器验证模块独立性；使用 HyperFrames 的工程另做核心检查及短片渲染 smoke，验证 adapter，不用 stub 冒充真实渲染。
- 基线失败 / 环境阻塞 / 条件项跳过全部记录，未运行的真实测试明确标为未运行。

Checklist：
- [x] 全部定向测试和全仓测试完成，新增失败均已修复或明确解释。
- [x] 3-scene 集成流程使用逐场景布局、保留手改字幕，进入 Phase 9 后 QA 场景映射正确。
- [x] 不产生指纹状态文件，不触发哈希 / mtime 新鲜度门槛。
- [x] 两个允许 skill 之外无直接或传递加载；生成工程运行协议不泄漏回模块库。
- [x] 更新本计划状态和验收记录，未实施项不标已完成；未经用户要求不提交 / 推送 / 合并。

### WI-09 验收记录（#154）

日期：2026-11-08。基线：main @ 7ed25e5（已含 #147–#153）。临时工作区：
`/tmp/opencode/ttv-154/demo`（standard 模式、fetch_materials=false、1 分钟中文显示稿、
fake TTS/ASR、本机 Chromium + ffmpeg、本机 `pi` 1.4.0）。集成中发现的问题均为
夹具/环境侧，未发现仓库代码 bug，无代码改动。

**交付的接口（真实入口逐一跑通）**
- `make-narration.py` → narration.txt + narration-offsets.json（真实现入口）。
- `voice-clone.py --backend fake` → voice_clone/narration.mp3 + transcribe/transcript.json
  （一次运行同时产出配音与转写，无付费调用）。
- `align-narration.py --mode timing --scene-plan` → transcribe/timeline.json
  （段落 + 叙事 scene + 1 条 cue 秒数，无警告）。
- `prepare-handoff.py <ws> {script,composition} --resolved-model <实际标识>` →
  handoff 同时展示请求模型与实际模型，JSON 返回 coding_model / requested_model /
  单句 dispatch_prompt；composition 步骤物化委派包、modules 副本并预置 design 字体。
  catalog 步骤在本工作区被输入门禁正确拒绝（无 harvest manifest，与
  pipeline-status 的 skipped 一致）。
- `scene_config.load_scene_config`（公共校验）→ 3 视觉 scene 通过
  （canvas 1920×1080、主区间覆盖 [0,54.933]、模板/stage/presenter/自由布局合法）。
- `align-narration.py --mode subtitles --scene-config --narration-audio` →
  16 个字幕单元按各 scene 落盘 caption 规格切分（vs1 4 / vs2 8 / vs3 4，
  vs3 按用户要求用 48px×2 行放大规格），带 scene_id 与 caption_segments。
- 模板锚点：`template-cues.json` + timing 模式 → `template-timeline.json`，
  cue「Phase Runner」真实词时间 2.000s 驱动 github/project-cover 的 nameAt。
- `check-composition.py --scene-config --design --subtitle-units --output`
  （真 Chromium seek 三场景 × 起点/中点/终点）→ verdict pass、0 findings，
  scenes_checked 覆盖 stage / presenter / null 三种 layout。
- `pipeline-status.py` → Phase 8 产物齐后 next_phase 进入 9-check-mix；
  全部产物 `--redo` / `--finish` 语义符合 #147 重做模型。
- `check-render.py --timeline scene-config.json` → 音轨/时长/分辨率/黑屏/冻结
  全过，finding 带视觉 scene_id（修复轮中 vs1/vs2/vs3 的 freeze 均正确映射）。
- `make-contact-sheet.py --timeline scene-config.json` → 3 视觉 scene 中点抽帧
  拼 sheet；`mix-bgm.py` → final_with_bgm.mp4（54.933s、解说轨 + BGM 0.03 垫底）。

**3-scene 集成流程**：vs1 = github/project-cover 模板 + stage 预设（用户要求作用于
本场景）；vs2 = template null + presenter 预设（含 jay 组件）；vs3 = template null +
自由布局（caption 按用户要求放大）。全片 orientation/design/唯一配音保持一致；
storyboard 逐 scene 记录「用户要求 → template → layout → 自主设计」决策与理由。

**中间 scene 手改字幕（AC4）**：手改 vs2 字幕单元（追加「（用户手改…）」）→
只修 vs2 画面（卡片文案）→ 重截 vs2 帧、重渲染、重跑 check-composition（pass）。
验证：subtitle-units.json 手改内容仍在；voice_clone/narration.mp3、
transcribe/transcript.json、transcribe/timeline.json、narration-offsets.json
md5 与基线一致（未重复 TTS/ASR、未覆盖 Phase 7 时间轴）；成片 18.6s 帧可见手改字幕。

**显式重做 QA/混音（#147 redo 模型）**：交付后修订 vs3 → 重渲染 final.mp4，
`--redo 8-composition --reason …` 登记 → `--finish 8-composition` 通过；
`--redo 9-check-mix` → 重做 check-render / contact sheet / qa-report / mix-bgm →
`--finish 9-check-mix` 通过，全阶段 completed。为证明不依赖新鲜度门槛，验收前把
scene-config、index.html、compositions/、字幕、帧、final.mp4、check-composition.json
的 mtime 全部设为 2000-01-01，`--finish` 仍通过；`.pipeline/` 仅有 approvals/redos
状态，scene-config 通过「精确键集合」校验不含哈希/mtime 字段。验收结束时
`.pipeline/` 为空：`--finish` 后 redos.json 按 #147 语义 unlink，approvals 因本流程
未启用审稿 gate 本就不存在——空目录是预期状态，非状态丢失。

**委派一致性（AC7）**：本机 `pi --list-models` 真实查询。请求 kimi-k2 时
pi 候选表无 kimi provider → 按约定属阻塞情形（已记录，未派发）。可解析样例：
catalog 请求 "deepseek"（需图像能力）→ 实际 deepseek/deepseek-flash；
script 请求 "deepseek-v4"（近似匹配）→ 实际 deepseek/deepseek-v4-pro；
composition 请求 "deepseek-flash"（精确匹配）→ 实际 deepseek/deepseek-flash。
三个阶段的 handoff「Coding Agent」小节均展示请求与实际值，命令使用实际值；
composition 委派包仅引用 hyperframes / hyperframes-cli 两个 skill，无演示目录或
旧模块入口引用；conventions.md 仍是默认 agent/命令/模型规则的唯一维护处
（phase 文档只回指约定，pi-coding-agent 仅作 schema 示例值出现）。

**HyperFrames 真实 smoke（AC5）**：`npx hyperframes`（0.9.20，经 npx 临时获取）
在最小工程（blank 模板 + 本 skill 预置 WOFF2 字体 + 真实字幕单元 + 4:3 素材
object-fit）上：`hyperframes check` → Check passed（Motion/Contrast/Craft/Audio
0 errors）；`hyperframes render --end 6` → 真实 6s 1920×1080 h264 MP4；
抽帧验证中文字体（NotoSansSC）正确、字幕单元随 data-start 切换、4:3 素材留边
比例正确。迭代中发现并纠正两处工程侧用法（clip 元素不得用 GSAP 改可见性、
clip 默认需可见由框架按时间隐藏），最终以框架契约方式通过。主工作区画面走
项目自有 Chromium + ffmpeg 渲染（无 stub）。

**独立组件与重复实例（AC5 前半）**：基线 `tests/test_scene_components_browser.py`
（真实 Chromium、普通浏览器无厂商全局 + 最小 adapter）覆盖六模块独立初始化/seek、
双 caption-bar 与双 jay 实例隔离、destroy 重挂无残留；本集成中 check-composition
真 Chromium seek 再次运行该链路（vs1–vs3 × 起点/中点/终点），`__timelines`/
`__hyperframes` 全程为 undefined。

**测试**：定向 18 个测试文件 729 passed；全仓 1232 passed（与基线一致，
无新增失败）。基线失败 / 环境阻塞 / 条件项分别记录（见「遗留与未验证项」）。

**15 条用户批注落实对照**：1–13、15 已由 #147–#153 交付并有对应测试
（输入说明 WI-06、删重复段 WI-06、storyboard 归属 WI-05/06、指纹清理 WI-01、
字体归 skill WI-06、字幕可编辑 WI-04/06、场景归 composition WI-05/06、
仅两 skill WI-03、不重复默认提示 WI-05/06、删动画 skill WI-03、逐场景选择
WI-02/04/05、简化阶段文档 WI-06、清理演示工程 WI-07、集中模型说明 WI-05），
本票经集成流程复核其运行链一致；14（字体 ≤10 行条件项）按 #153 结论跳过
自动下载行为变更，联网禁令措辞清理已完成，不标「自动下载已实现」。

**遗留与未验证项（如实记录）**
- 真实付费 TTS/ASR 与真实 VLM 未调用（按约束使用 fake 后端与本机 vision）；
  fake 配音为静音，混音的「解说可闻」只能验证到音轨结构与 BGM 增益路径
  （mix-bgm 逻辑由 test_mix_bgm 覆盖）。
- 本机未安装 hyperframes/hyperframes-cli 两个 skill（npx CLI 可用）；
  composition 派发的 `--no-skills --skill <path>` 形态未以 skill 文件真实加载过，
  路径核对与命令形态按 conventions 验证。
- catalog 委派阶段的 --resolved-model 路径被输入门禁拒绝（工作区无 catalog），
  模型解析规则本身三阶段一致（见上）。
- handoff 内嵌的 venv 激活路径指向 skill 根的 .venv；本 worktree 无 .venv 时
  需用等价 venv 执行命令（环境差异，非缺陷）。
- `npx hyperframes check` 对主工作区手工 index.html 报 contract lint 错误
  （根节点缺 data-composition-id/__timelines 等）——主工作区画面不是
  HyperFrames 工程，属预期；HF 契约仅存在于最小 HF 工程内，未泄漏回模块库。

## 6. 实施顺序

```text
WI-00
  ├─ WI-01：指纹清理
  ├─ WI-02：场景配置
  ├─ WI-03：模块 / 外部依赖清理
  └─ WI-08：字体行数门槛

WI-02 + WI-03 → WI-04：字幕 / 画面检查 / QA
WI-02 + WI-04 → WI-05：统一委派与新 handoff
WI-01…WI-05 → WI-06：工作流文档收敛
WI-03 + WI-05 + WI-06 → WI-07：目录及历史引用清理
全部 → WI-09：集成验收
```

独立项可以分开验证，但每次集成按完整消费链验收；不留下“文档已经逐场景、脚本仍全片布局”的中间状态作为交付。

## 7. 最终检查 checklist

### 需求与结构
- [ ] 15 条批注全部在 work item 中落地或按明确条件跳过。
- [ ] storyboard / scene-config / 字幕 / 画面由 composition 子代理产出，主 agent 只准备、派发和验收。
- [ ] 每个视觉 scene 独立按“指定要求 → template → layout → 自主设计”执行。
- [ ] 全片只共享用户确定的朝向、design、配音等事实，不共享强制 template / layout。
- [ ] 同一份 scene-config 驱动字幕、渲染前区域检查和 Phase 9 场景映射。

### 清理与安全
- [ ] 指纹生成、校验、缓存、打戳、恢复、审稿哈希绑定及所有调用清理完整。
- [ ] 文件 / JSON / 时长 / 偏移表 / 真实画面检查仍在；显式重做和审稿没有被绕过。
- [ ] 字幕编辑禁令消失，已有用户修改不会被准备或只重渲染流程覆盖。
- [ ] 保留两个允许的 HyperFrames skill，清理其他扩展和模块库的专用运行时依赖。
- [ ] 删除范围精确，没有改外部安装、登录配置、非目标用户资产或未授权的工作区副本。

### 委派与字体
- [ ] conventions 是默认目标、命令和模型选择说明的唯一维护处。
- [ ] 近似模型来自目标 coding agent 的本机 CLI；输入保留请求，handoff 和命令使用同一实际标识。
- [ ] 字体下载行为受 ≤10 行门槛约束；超限时只有文档清理，没有暗中扩大实现。

### 验证方式

实施时先激活项目 venv，再运行实际测试。例如从仓库根目录：

```bash
source .venv/bin/activate
python3 -m pytest tests/test_pipeline_status.py tests/test_video_contract.py tests/test_align_narration.py tests/test_prepare_handoff.py tests/test_delegation_config.py tests/test_template_cues.py tests/test_check_composition.py tests/test_check_composition_snapshots.py tests/test_phase_docs.py tests/test_guardrail_docs.py tests/test_fonts_download.py
python3 -m pytest tests
```

新场景配置 / 模块接口测试随实施加入定向集合。默认测试不自动安装浏览器、不卸载 skills、不下载模型、不发送私有内容或调用付费服务。真实 CLI 列表查询、Chrome 检查和 HyperFrames smoke 单独记录。

## 8. 已核对的依据与待验证事实

- 当前全局 layout 前置：`scripts/video_contract.py` 的 STEP_INPUTS_FIELDS、`scripts/prepare-handoff.py` 的 `composition_plan()` / 视觉校验、`scripts/pipeline-status.py` 的 `check_visual_inputs()`。
- 当前字幕单布局处理：`scripts/align-narration.py` 的 `load_caption_spec()` / `align()` / `build_units()`。
- 当前实际场景 QA 可以复用的读取：`scripts/timeline_scenes.py:15-49` 只消费 `scene_id/begin_s/end_s`。
- 当前字体维护副作用：`scripts/fonts-download.sh` 的 `refresh()` / `prune_pool()`；本轮没有修改或执行它们。
- Pi 官方 [CLI 文档](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/cli.md#models) 已说明 `--list-models [search]`、`--model` 精确 / 模糊匹配与原生 provider/id；[模型文档](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md) 说明可用认证与候选模型。
- HyperFrames 核心契约允许按 scene 注册暂停 timeline；这是生成工程 adapter 的职责，不是其他扩展 skill 的依赖理由。

**本轮仅核对代码 / 文档和公开 CLI 说明；未跑本机 Pi、测试或视频渲染。实施必须以本机目标 CLI 的帮助与实际运行结果为准。**
