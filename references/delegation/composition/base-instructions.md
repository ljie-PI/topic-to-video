# composition 委派包 — 基础指令（画面组装与渲染）

你负责为一个解说视频设计并实现**全部画面**：先确定全片 preset / custom design、安装字体并写 `composition/design.json`，再以旁白与叙事场景规划为起点，逐视觉场景独立决定 template / layout（允许自由布局），写 `composition/scene-config.json` 和 storyboard，用 modules 组装画面并渲染成 `final.mp4`。主 agent 只固定全片 orientation、用户明确指定的 design 约束与其他用户要求，不替你预选默认 design 或任何 scene 方案；你独立完成并落盘全部产物。

先读 handoff 的 Inputs 中标为「Agent 阅读与画面资源」的文件，再按下面的约束执行。标为「仅供工具读取」的 transcript、朗读稿与偏移表只传给字幕 / cue 对齐命令，正常流程不阅读或复述其全文；仅在工具报错且必须诊断时读相关句子或时间窗口。旁白理解以 `script.txt` 为准。指令冲突时，按 `references/delegation/conventions.md` 的叠加顺序处理：后读的（scene-config 契约 → 模块文档 → 模板场景说明 → 用户在 `inputs.json` 的 `composition_requests` 里提出的要求）覆盖先读的。

`composition_requests` 里的每条用户要求都带作用范围：用户指明某个叙事场景或某个视觉场景时只在该范围内应用，未说明时按整片应用；与朝向、用户明确指定的 design 或另一条明确要求冲突时报告冲突，不要静默换掉要求。

本指令包含五类约束：

1. 输入、真实语音与素材契约；
2. 所选 design 的 token 与字号约束；
3. 各视觉 scene 实际落盘的 layout regions/caption；
4. 逐场景内容演绎、template/layout 与自主设计；
5. 模板时间锚点只能来自真实朗读。

后文同时给出一条工作顺序。在不违反输入、真实语音、必用素材、落盘 design、所选字体与 QA 检查约束的前提下，其余视觉设计由 composition agent 决定：视觉 scene 怎么切、各用什么 template / layout、构图与视觉隐喻、素材怎么摆、Jay 怎么演、动效怎么编排，是你的设计空间。

## 一、输入契约

- **配音**：只用主 agent 生成的 `voice_clone/narration.mp3`，不重生成 TTS、不用任何其他音频来源；画面与解说的同步以这份音频为最终边界，`scene-config.json` 的 `total_s` 以它为边界（含语音前后的静音画面）。
- **视觉 scenes 与 scene-config**：先读旁白与叙事规划，决定实际视觉切分；对每个视觉场景按「用户要求 → 特别匹配模块 → 即时生成」的顺序确定方案，写 `composition/scene-config.json`。schema 以 `references/delegation/composition/scene-config.md` 契约为准（含可验证示例），它由状态、字幕与检查脚本共同读取校验：`begin_s` / `end_s` 是全片秒，主区间按 `[begin_s, end_s)` 有序、不重叠并覆盖整段视频；每个 scene 的 `layout` 必须落盘完整 `regions` / `caption`，检查不从 `preset` 名猜坐标。它们不要求与 Phase 6 的叙事 scene 一一对应；`source_scene_ids` 记录映射，合并 / 拆分的理由写在 storyboard。模板不用就是 `null`——`template: null` 加自由布局是正常完成路径。
- **字幕**：字幕单元在**本阶段、scene-config 写出后生成**：跑 handoff 里的 `align-narration.py --mode subtitles --scene-config ... --narration-audio ...` 命令，用各 scene 落盘的 `caption` 规格把字幕切到 `composition/assets/subtitle-units.json`。它只根据显示稿、朗读稿、偏移表、本轮 transcript、scene-config 与实际音频生成，不重跑 ASR，也不覆写 Phase 7 timeline。默认由脚本生成初稿；实际制作中可以编辑文本与边界，已有用户编辑是有效输入——仅改画面 / 重渲染时不要去覆盖已有字幕。逐单元原样上屏（每个单元带 `scene_id`，归属的 visual scene）；超宽时优先在 `，；、：——`（含半角 `, ; :`）处断开；不得因 scene 切点切断英文词或数字——工具不会跨「不同版面」的切点自动合并短字幕，切点落在英文 / 数字 token 时间内部时报出涉及的 scene 与真实时间边界，需要调整视觉切点或编辑字幕。
- **时间**：段落与 cue 的起止秒来自 `transcribe/timeline.json`；视觉 scene 的真实配音边界与 cue 锚点以它和 narration 音频为准。本阶段不修改这份时间轴。
- **必用素材**：catalog 阶段适用时，catalog 的 `required_material_refs`（论文模式的关键图 / 表）必须都出现在成片里。在 storyboard 里另起一张覆盖表：每条必用 ref 一行，写明展示它的 scene 与大致秒数；确实无法展示时写原因并报告，不要默默丢掉。
- **素材**：画面素材只来自 `material-catalog.json`。图片 / 视频 ref 用 `<slug>/<id>`，先定位 `entries[*].slug` 对应的 entry，再在该 entry 内按 id 找素材；裸 id 无效。图片解析到该 entry 的 `local_path`：所有相对 `local_path` 都以 `{work_dir}/{topic_name}/harvest_page/` 为 base（不是 `composition/` 或当前目录）。视频 clip 用 `<slug>/<video_id>:<start>-<end>`，一律解析到该 entry 对应的 `selected_clips[].clip_path`（Phase 5 已切好的无音轨片段文件，相对工作区根 `{work_dir}/{topic_name}/`），不使用视频的 `local_path`、不嵌入整段原视频；场景规划只引用了 `<slug>/<video_id>` 时，从该 entry 的视频 `selected_clips` 里挑片段。同一个 video id 出现在多个 entry 时，slug 决定使用哪一个 entry 的片段，不能跨 entry 匹配窗口。读取或复制进 composition 前先按此规则解析。视频仍然静音播放（`<video>` 带 `muted playsinline`）。
- **字体**：先跑 `npx hyperframes init composition/`（仅当 `composition/` 目录不存在时），确定 design 后再安装到 `composition/assets/fonts/`，不依赖系统字体。preset 用对应 `modules/designs/<design>` 字体包；custom 可以复用库内某个现有字体包作为资源，但 token 的字体名必须与实际 CSS 一致。复用字体资源不等于采用该 preset 的视觉设计。通用命令：`bash scripts/fonts-download.sh <ws>/composition/assets/fonts --theme <ws>/modules/designs/<design>`；handoff Outputs 也给出带实际根路径的命令。

## 二、必须选择并落盘 design

- 先读 `modules/designs/designs.md` 与 scene 需求。用户明确指定注册 preset 时按约束采用；未指定时，只有某个 preset 与全片视觉需求特别匹配才采用，否则生成 custom design。库内 preset 是候选，不是默认必选。
- 无论哪条路径都先写 `composition/design.json`，根字段恰好为 `version: 1` / `source` / `preset` / `tokens` / `min_font_px`。`source: "preset"` 时记录注册名，tokens 与字号下限必须和该 preset JSON 完全一致；`source: "custom"` 时 `preset: null`，自行生成完整共享 token 集合与正整数 `reading` / `ui` 下限（`ui` 不低于 22px）。`fonts` 维护清单不写入这份产物。
- 选定 preset 后再按需阅读 `modules/designs/<design>/<design>.md` 与 `<design>.json` 并安装对应字体；custom 也要写完整 tokens / min font，并确保实际 CSS 的字体名与 token 一致。
- 颜色、字体只取落盘 design 的 token；动效的默认时长、缓动与列表间隔跟随主题 token，具体运动方式与编排由你设计。字号守 `composition/design.json` 的 `min_font_px`：面板标题栏、按钮、小标签这类界面小字放在带 `data-text-role="ui"` 的元素里，按界面小字下限检查；其余文字都按阅读文字下限检查。
- 选了模板场景时，模板的专属变量与覆盖值**写在 design 之后**，只能增补主题，不能替换 design 的语义；用户把某 preset 限定到单个 scene 时，只在该 scene 根作用域覆盖相应 token 并在 storyboard 记录，不自动传播到其他 scene。模板的专属配色、人物、导航和转场同样只作用于采用它的 scene。

## 三、必须遵守各 scene 的 layout 区域

- 每个视觉 scene 的画面只能使用它在 `scene-config.json` 里落盘的 `regions`：content 区域自由放内容；reserved 区域只放各自 `component` 声明的组件（如导航栏区只放 `nav-bar`、字幕区只放 `caption-bar`、人物区只放 `jay`）。区域坐标可以来自借用的 preset（`preset` 记录出处），也可以完全自主设计；检查一律以落盘的 rect 为准。
- storyboard 里**每个视觉 scene 都要写明它的区域方案**：借用了哪个 preset（或自主设计）、用了哪些 content 区域、reserved 区各挂什么组件。
- 每个视觉 scene 的根挂载必须带与声明一致的 `data-scene-id`、`data-scene-start`、`data-scene-end`，供 QA 采样使用。
- scene 的 regions 有人物区（`component` 为 `jay` 的 reserved 区）时必须挂 `jay`；Jay 仍是全片唯一常驻实例，没有人物区的 scene 不强制显示 Jay（通过 `placements` 隐藏，如 `visible: false`）。`VIDEO.jay` 的动作与通用演法按 `modules/components/jay/jay.md` 编排，有模板时再叠加模板的演法。

## 四、内容演绎与模板选择

`scene-plan.json` 的 `intent` 与 `content_plan` 说每个 scene 要讲什么、怎样展开，`material_candidates` 给出候选素材。它们只是参考，不是画面指令。

默认即时生成，预定义模块是例外；阅读模块目录不等于采用模块。逐场景选择，顺序固定——对每个视觉 scene 按以下统一顺序与规则执行（用户要求 → 特别匹配模块 → 即时生成）：

1. **先应用用户要求及其作用范围。** 用户在 `composition_requests` 中指定某 scene 或全片使用某个模块时，在该作用范围内采用；与朝向、事实或另一条明确要求冲突时报告冲突，不要静默换掉要求。
2. **未指定时评估“特别匹配”，不是“勉强可用”。** 预定义模块（template、layout preset、component、pattern、motion）只在与目标 scene 特别匹配时才采用，至少同时满足：
   - 模块表达的内容关系与 scene 的叙事目标一致；
   - 素材形态、数据、画布、可读性和交互需求适合该模块；
   - 不需要改旁白、视觉 scene、orientation 或用户要求来迁就模块；
   - 采用它比即时生成更清楚或更可靠，而不只是少写代码。
   采用模板后按它的 `preferred_layouts` 与用户要求确定本 scene 布局（`preferred_layouts` 是建议不是门槛）；先读 `modules/templates/templates.md` 目录，选中某个模板场景时读它的 `<t>.json`（场景与真实朗读锚点声明）和场景文档；不命中就不用，不要为了套模板改主题、叙事、朝向、design 或视觉 scenes。
3. **没有特别匹配就即时生成。** 自主设计优先：先根据旁白要表达的关系、素材实际内容和各 scene 的可用区域，自主构思构图、视觉隐喻、信息展开与动效，根据 scene 要求自行设计 DOM/CSS/SVG/JS、图表、视觉机制或组件，不为使用库而使用库，再写入 storyboard；遇到旁白或 `content_plan` 做了日常类比、多步拆解的难点时，优先用分步揭示或阶段演进的动画把每一步的变化可视化讲清楚（`composition_requests` 另有要求时按用户要求处理）；简洁的静态呈现也是有效选择。
4. **按实际采用落盘。** 不用 template 时写 `template: null`；不借 layout preset 时写 `preset: null` 并落盘完整实际 `regions` / `caption`；不借 pattern / motion 时不产生借用记录；自绘组件仍须满足区域、字幕、确定性、事实和检查契约。模板选择及理由写进 storyboard，不写回 `inputs.json`。
5. **保持模块内部依赖完整。** 一个特别匹配且被采用的 template / layout 所声明的必要组件，属于该方案的一部分；若这些组件不适合，应判定整个方案不够匹配，而不是破坏它的 reserved 区约定。
6. **只记录实际采用。** 参考库按需：`modules/patterns/` 与 `modules/motion.md` 是可跳过的参考库。仅在已有构想对应某个非常匹配的模式 / 动效建议，或有具体的画面 / 动效问题需要参考时，才定向查阅；采用时须与内容关系、素材形态和区域约束高度吻合，并确实改善表达。可以局部借用或改写。默认自主设计，全片不用参考库也完全合格。storyboard 只记录实际借用的模块、用户指定依据或特别匹配理由（只在借用时用一句话记录借用内容与匹配理由）；即时生成不需要“未使用其他模块”的清单，无需填写 pattern 字段或未使用理由。

### 表达与事实边界

- **表现机制选择**：表现机制从旁白语义、素材和实际区域出发；DOM/SVG/CSS/Canvas/WebGL 都是可选实现，简洁的静态呈现也合法，具体 runtime 选择见 `modules/motion.md`。
- **创意边界**：视觉创意服务于理解，不得破坏所选 design token、各 scene 实际落盘的 regions、可读性、真实语音同步或事实含义。
- **新增屏幕事实来源**：画面中新增的屏幕事实、数字、实体、引文和标注必须能由当前 composition 输入支撑（`script.txt`、`scene-plan.json`、适用时的 `material-catalog.json` 及明确的用户要求 `composition_requests`）；需要新增上游事实时向主 agent 报告并建议回退，不得自行编造（也不要求读取未提供的 `research-brief.md`）。
- **示意与证据边界**：图示、类比和示意可用于解释概念或关系，但不得伪装成真实数据或证据；会改变事实含义的构图、标注与动画不使用。

- **时间只取真实语音。** 需要卡准秒数时，从 `timeline.json` 的段落 / cue 取；模板需要额外锚点时按下节自己声明 cue 并跑 timing 模式，不按字数估算、不另建节拍表。
- **偏离要有理由。** 合并 / 拆分 scene、换素材或换演绎方式都行；与 `intent` / `content_plan` 的偏离写在 storyboard 里。发现是叙事或素材本身对不上，报告建议回退到 Phase 6，不要改旁白。

## 五、模板时间锚点只能取自真正被朗读的文字

模板要求的入场时间（项目名、tagline、stars 等）必须来自实际念出来的文字，不能按字数估算、也不能先写一份模板旁白让 Phase 6 去念。

1. 在 `script.txt` 里找到模板需要的字段对应的原文（项目名、tagline、star 数等），确认它确实属于某个 scene 的 `paragraphs`。
2. 把要卡点的原句按 cue 声明的形状（`scene_id` / `paragraphs` / `cues`）写进 `composition/assets/template-cues.json`。cue 必须原样摘自显示稿；这个文件不是完整的场景规划，只需这三个字段。
3. 跑 handoff 里的 `align-narration.py --mode timing --scene-plan composition/assets/template-cues.json --timeline-output composition/assets/template-timeline.json`，用同一套对齐拿到真实秒数。
4. 把结果换算成组件参数：全片组件（`nav-bar` / `caption-bar` / `tile-wipe`）用视频秒；scene 内的参数（`nameAt` / `taglineAt` / `starsAt` 等）用相对该 scene `data-start` 的秒数。
5. 没念到的字段不编时间：`project-cover` 可省略 `taglineAt` / `starsAt`，组件会隐藏相关部分并跳过动画；`nameAt` 和榜单每个项目的 `cue` 是必需锚点，缺失就不用对应场景 / 项目，不采用默认秒数。事实资料缺失也不编造值，更不回去改旁白迁就模板。

## 工作顺序

0. **先决定 preset / custom design，初始化工程，安装字体并写 design 契约。** 按第二部分选择全片基线；`composition/` 目录不存在时先运行 `npx hyperframes init composition/`，再运行 handoff 的通用字体安装命令，把实际 tokens 与字号下限写进 `composition/design.json`；完成这些之后再逐场景选择其他模块。
1. **决定视觉 scenes，逐场景定方案，写 scene-config。** 先读 `script.txt`、`scene-plan.json`、timeline 与素材目录，按实际画面需要合并 / 拆分叙事 scene。对每个视觉场景按第四部分的固定顺序选择方案；可以借用 `modules/layouts/` 的 preset（读 `layouts.md` 目录与对应 JSON / 文档），也可以自主设计自由布局。把最终结果写进 `composition/scene-config.json`（schema 见契约文档），并选定 storyboard 的骨架。
2. **生成字幕初稿**。跑 handoff 里的 `align-narration.py --mode subtitles --scene-config ... --narration-audio ...` 命令，把字幕单元切到 `composition/assets/subtitle-units.json`。已有用户编辑过的字幕是有效输入：只有缺失或当前任务明确要求重新生成时才重新生成，仅改画面 / 重渲染不要覆盖它。
3. **自主构思并写 storyboard**：先读 `modules/components/components.md` 的组件目录，再读要用的组件文档。storyboard 开头先写一张「组件使用表」：每个用到的组件一行，写明挂载参数、驱动它的 `window.VIDEO` 数据从哪来（例如 `captions` 来自 `composition/assets/subtitle-units.json`）。各 reserved 区要求的组件必须出现在表里；常驻组件不用在每个 scene 里重复写，scene 里只写本 scene 额外用到的组件。然后按 scene-config 逐个视觉 scene 写，记录对应的叙事 `intent` / `content_plan`、template / layout 方案（preset 或自主设计）及理由、content 区域，以及素材、构图、信息展开与动效安排；参考库的查阅与借用按第四部分处理。可以改选素材与演绎方式；偏离场景规划的地方写明理由；**旁白不能改**（字幕以显示稿为准，新增屏幕文字与标注守第四部分事实边界）。
4. **组装和编写画面**。按 storyboard 用 modules 组装：读 `modules/modules.md` 入口、落盘 design、契约要求遵守的区域与要用的组件文档（先看 `modules/components/components.md`），实现自己确定的画面与动效。按 storyboard 选定的 design textures、组件和模板资源，由你自己从工作区的 `modules/` 拷进 `composition/`，清单见各模块的文档。
5. **渲染前自查**，全部通过再渲染：
   - 运行 `npx hyperframes check`，修掉所有错误；
   - 运行 check-composition（命令见 handoff 的 Outputs 一节）：它按 `scene-config` 在各 scene 落盘的 regions / caption 下检查越界、侵入 reserved 区域、文字溢出、资源加载失败、字体未加载、字号低于 design 下限、字幕与字幕单元不一致；每条 finding 的形状为 `{scene_id, check, issue, time_s, frame}`，其中 `time_s` 是快照时刻、`frame` 为 null，只修相关 scene；handoff 的命令用 `--scene-config` 指定配置，并用 `--output` 把同一份报告写到 `composition/check-composition.json`（stdout 照常打印，findings 直接看输出）；改过 scene-config 或画面就重跑，**最后一次的报告必须保存在这个路径且 verdict 为 pass**（主 agent 的状态脚本读它）；
   - 在每个视觉 scene 的中点截一张快照，自己目检一遍（区域使用、可读性、与旁白的同步）。
6. **渲染**。用 HyperFrames 渲染出 `composition/renders/final.mp4`。完成后向主 agent 报告 `design.json`、`scene-config.json`、`storyboard.md`、`index.html`、`renders/final.mp4` 的路径，以及 hyperframes check 与 check-composition 的 verdict；主 agent 会复核产物与两个检查的通过情况。

报告前自己先看一两个关键 scene 的渲染结果：素材宽高比是否对、字幕是否溢出、画面能否对应旁白。发现是叙事或素材的问题（场景与旁白对不上、素材用错），在报告里说清楚并建议回退到哪个阶段，不是硬改 HTML 遮过去。
