# composition 委派包 — 基础指令（画面组装与渲染）

你负责为一个解说视频设计并实现**全部画面**：以场景规划为起点，自己写 storyboard，用 modules 组装画面并渲染成 `final.mp4`。主 agent 不会替你做这些决定；你独立完成并落盘产物。

先读工作区里的输入（handoff 的 Inputs 一节列出的文件），再按下面的约束执行。指令冲突时，按 `references/delegation/conventions.md` 的叠加顺序处理：后读的（模板组装说明 → 用户在 `inputs.json` 的 `composition_requests` 里提出的要求）覆盖先读的。

本指令只有五部分约束——输入契约、必须参考 design、必须遵守 layout 区域、内容演绎与模板选择、模板时间锚点——和一条工作顺序。除此之外你没有别的规则：scene 怎么切、用什么模板与 pattern、素材怎么摆、Jay 怎么演、动效怎么选，是你的设计空间。

## 一、输入契约

- **配音**：只用主 agent 生成的 `voice_clone/narration.mp3`，不重生成 TTS、不用任何其他音频来源；画面与解说的同步以这份音频为最终边界。
- **字幕**：字幕单元在**本阶段生成**：先按 handoff 里的 `align-narration.py --mode subtitles` 命令，用最终 layout 的 `caption` 规格把字幕切到 `composition/assets/subtitle-units.json`。生成后逐字使用，不自己改写、不重新断句、不重新排序、不合并或拆分，逐单元原样上屏。超宽时优先在 `，；、：——`（含半角 `, ; :`）处断开；只有单个 token 本身超宽才会切断单词或数字。
- **时间**：段落与 cue 的起止秒来自 `transcribe/timeline.json`；scene 切分与 cue 锚点以它为准。本阶段不修改这份时间轴。
- **必用素材**：catalog 阶段适用时，catalog 的 `required_material_refs`（论文模式的关键图 / 表）必须都出现在成片里。在 storyboard 里另起一张覆盖表：每条必用 ref 一行，写明展示它的 scene 与大致秒数；确实无法展示时写原因并报告，不要默默丢掉。
- **素材**：画面素材只来自 `material-catalog.json`。图片 / 视频 ref 用 `<slug>/<id>`，先定位 `entries[*].slug` 对应的 entry，再在该 entry 内按 id 找素材；裸 id 无效。图片解析到该 entry 的 `local_path`：所有相对 `local_path` 都以 `{work_dir}/{topic_name}/harvest_page/` 为 base（不是 `composition/` 或当前目录）。视频 clip 用 `<slug>/<video_id>:<start>-<end>`，一律解析到该 entry 对应的 `selected_clips[].clip_path`（Phase 5 已切好的无音轨片段文件，相对工作区根 `{work_dir}/{topic_name}/`），不使用视频的 `local_path`、不嵌入整段原视频；场景规划只引用了 `<slug>/<video_id>` 时，从该 entry 的视频 `selected_clips` 里挑片段。同一个 video id 出现在多个 entry 时，slug 决定使用哪一个 entry 的片段，不能跨 entry 匹配窗口。读取或复制进 composition 前先按此规则解析。视频仍然静音播放（`<video>` 带 `muted playsinline`）。
- **字体**：只用主 agent 预置的字体目录（`composition/assets/fonts/`，由所选 design 决定），不依赖系统字体。

## 二、必须参考 design

- 颜色、字体、动效只取所选 design 的 token（token 契约见 `modules/designs/designs.md`、`modules/designs/<design>/<design>.md` 与同目录的 `<design>.json`）。
- 字号守所选 design JSON 的 `min_font_px`：面板标题栏、按钮、小标签这类界面小字放在带 `data-text-role="ui"` 的元素里，按界面小字下限检查；其余文字都按阅读文字下限检查。
- 选了模板时，模板的专属变量与覆盖值**写在 design 之后**，只能增补主题，不能替换 design 的语义。

## 三、必须遵守 layout 区域

- 先读所选布局的区域定义 `modules/layouts/<layout>.json`：画布尺寸、区域列表（每个区域有 id、kind（content / reserved）、rect；reserved 区域写明对应组件）与字幕规格。文档版 `modules/layouts/<layout>.md` 与 JSON 一一对应。
- storyboard 里**每个 scene 都要写明用了哪些 content 区域**。
- 所有元素只放在 content 区域内；reserved 区域只放各自对应的组件（如导航栏区只放 `nav-bar`、字幕条区只放 `caption-bar`）。
- layout 有人物区（presenter）时必须挂 `jay`；`VIDEO.jay` 按 `jay.md` 的通用演法编排，有模板时再叠加模板的演法；嘴型数据用 `node modules/components/jay/make-envelope.mjs voice_clone/narration.mp3` 生成。

## 四、内容演绎与模板选择

`scene-plan.json` 的 `intent` 与 `content_plan` 说每个 scene 要讲什么、怎样展开，`material_candidates` 给出候选素材。它们只是参考，不是画面指令。

- **模板归你选。** 先读 `modules/templates/templates.md`：有适配这类视频的模板就读它的 `<t>.json`，确认 `supported_layouts` 包含当前 layout，能配就用；不命中就不用，不要为了套模板改主题、叙事、朝向或 design。决定后把 `template` 字段写回 `inputs.json`（模板名或 `null`），并在 storyboard 里写明选择与理由。用户 `composition_requests` 的要求优先于模板。
- **pattern 是建议。** `modules/patterns/` 按 storyboard 需要自行阅读和选用；scene-plan 不再给 pattern 提示。
- **动作自己排。** Jay 按 `jay.md` 的通用演法，根据旁白内容从动作库挑动作；同一时间只做一个，后一个顺延。
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

0. **生成最终字幕**。先跑 handoff 里的 `align-narration.py --mode subtitles` 命令，把字幕单元切到 `composition/assets/subtitle-units.json`。它只根据显示稿、朗读稿、偏移表和本轮 transcript 生成，不重做语音识别。
1. **先定模板与 pattern，再写 storyboard**，分三小步：
   1. **先决定模板**。读 `modules/templates/templates.md`，按内容、layout 与用户要求决定用哪个模板或不用；选中就读它的 `<t>.json` 确认 `supported_layouts`，把 `template`（模板名或 `null`）写回 `inputs.json`，再读模板文档。
   2. **再选组件**。读 `modules/components/components.md` 的组件目录，再读要用的组件文档。
   3. **写 storyboard**。开头先写一张「组件使用表」：每个用到的组件一行，写明挂载参数、驱动它的 `window.VIDEO` 数据从哪来（例如 `captions` 来自 `composition/assets/subtitle-units.json`）。layout 的 reserved 区要求的组件必须出现在表里；常驻组件不用在每个 scene 里重复写，scene 里只写本 scene 额外用到的组件。然后以 `scene-plan.json` 的 `intent` / `content_plan` 为起点逐个 scene 写：可以合并或拆分视觉 scene、改选素材、pattern 与演绎方式；偏离场景规划的地方写明理由；**旁白不能改**（字幕与屏幕文字都以显示稿为准）。
2. **组装和编写画面**。按 storyboard 用 modules 组装：读 `modules/modules.md` 入口、所选 design / layout 文档、需要的 pattern 文档（`modules/patterns/`，只作建议）与组件文档（`modules/components/`）；动效选择参考 `modules/motion.md`。按 storyboard 选定的 design textures、组件和模板资源，由你自己从工作区的 `modules/` 拷进 `composition/`，清单见各模块的文档。
3. **渲染前自查**，全部通过再渲染：
   - 运行 `npx hyperframes check`，修掉所有错误；
   - 运行 check-composition（命令见 handoff 的 Outputs 一节）：它按 layout 区域定义检查越界、侵入 reserved 区域、文字溢出、资源加载失败、字体未加载、字号低于 design 下限、字幕与字幕单元不一致；每条 finding 的形状为 `{scene_id, check, issue, time_s, frame}`，其中 `time_s` 是快照时刻、`frame` 为 null，只修相关 scene；handoff 的命令用 `--output` 把同一份报告写到 `composition/check-composition.json`（stdout 照常打印，findings 直接看输出）；改过画面就重跑，**最后一次的报告必须保存在这个路径且 verdict 为 pass**（主 agent 的状态脚本读它）；
   - 在每个 scene 的中点截一张快照，自己目检一遍（区域使用、可读性、与旁白的同步）。
4. **渲染**。用 HyperFrames 渲染出 `composition/renders/final.mp4`。完成后向主 agent 报告 `storyboard.md`、`index.html`、`renders/final.mp4` 的路径，以及 hyperframes check 与 check-composition 的 verdict；主 agent 会复核产物与两个检查的通过情况。

报告前自己先看一两个关键 scene 的渲染结果：素材宽高比是否对、字幕是否溢出、画面能否对应旁白。发现是叙事或素材的问题（场景与旁白对不上、素材用错），在报告里说清楚并建议回退到哪个阶段，不是硬改 HTML 遮过去。
