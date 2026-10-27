# composition 委派包 — 基础指令（画面组装与渲染）

你负责为一个解说视频设计并实现**全部画面**：以场景规划为起点，自己写 storyboard，用 modules 组装画面并渲染成 `final.mp4`。主 agent 不会替你做这些决定；你独立完成并落盘产物。

先读工作区里的输入（handoff 的 Inputs 一节列出的文件），再按下面的约束执行。指令冲突时，按 `references/delegation/conventions.md` 的叠加顺序处理：后读的（模板组装说明 → 项目指令 → 用户追加要求）覆盖先读的。

本指令只有四部分约束——输入契约、必须参考 design、必须遵守 layout 区域、语义节拍映射——和一条工作顺序。除此之外你没有别的规则：scene 怎么切、素材怎么摆、动效怎么选，是你的设计空间。

## 一、输入契约

- **配音**：只用主 agent 生成的 `voice_clone/narration.mp3`，不重生成 TTS、不用任何其他音频来源；画面与解说的同步以这份音频为最终边界。
- **字幕**：字幕文本来自 `transcribe/subtitle-units.json` 的字幕单元，逐字使用，不自己改写、不重新断句。字幕单元已按句末标点分段，句内只在 `，；、：——`（含半角 `, ; :`）处断开、绝不在单词或数字中间切断：单元边界不可改动（禁止重新排序、合并或拆分），逐单元原样上屏。
- **时间**：段落、cue 与语义节拍 beat 的起止秒来自 `transcribe/timeline.json`；scene 切分、cue 锚点和 beat 对齐以它为准。
- **素材**：画面素材只来自 `material-catalog.json`。图片 / 视频 ref 用 `<slug>/<id>`，先定位 `entries[*].slug` 对应的 entry，再在该 entry 内按 id 找素材；裸 id 无效。图片解析到该 entry 的 `local_path`：catalog 沿用 v2 harvest manifest 的路径，所有相对 `local_path` 都以 `{work_dir}/{topic_name}/harvest_page/` 为 base（不是 `composition/` 或当前目录），旧 catalog 的绝对路径原样使用。视频 clip 用 `<slug>/<video_id>:<start>-<end>`，一律解析到该 entry 对应的 `selected_clips[].clip_path`（Phase 5 已切好的无音轨片段文件，相对工作区根 `{work_dir}/{topic_name}/`），不使用视频的 `local_path`、不嵌入整段原视频；场景规划只引用了 `<slug>/<video_id>` 时，从该 entry 的视频 `selected_clips` 里挑片段。同一个 video id 出现在多个 entry 时，slug 决定使用哪一个 entry 的片段，不能跨 entry 匹配窗口。读取或复制进 composition 前先按此规则解析。视频仍然静音播放（`<video>` 带 `muted playsinline`）。
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

## 四、把语义节拍落到画面

读取 `timeline.json` 的 `beats`，按下表落到画面上。动作从 `begin_s` 开始；和其他 Jay 动作时间冲突时，后一个顺延（`jay.md` 的动作库也有这条规则）。

| type | 有 Jay（presenter） | 没有 Jay |
|---|---|---|
| question | `["question", 2400]` | 按所选 design 第 6、7 节的强调写法，强调对应的提问文字 |
| idea | `["idea", 2400]` | 按所选 design 的强调写法，强调关键句或图示 |
| caveat | `["think", 2000]` 加一条不超过 4 个字的 `thoughts`，或 `["sigh", 2600]` | 对应信息用 `--c-warning` 左线的 callout 出现 |
| highlight | 数字类用 `["eureka", 2700]`，其他用 `["smile", 2200]` | 按所选 design 的强调写法，强调数字或关键词 |
| negation | `["shake", 1600]` | 对应项打 ✗，文字降为 `--c-ink2` |
| confirm | `["nod-small", 1000]` | 不加额外动效 |

## 工作顺序

1. **写 storyboard**，分两小步：
   1. **先选组件**。读 `modules/components/components.md` 的组件目录，再读要用的组件文档。
   2. **写 storyboard**。开头先写一张「组件使用表」：每个用到的组件一行，写明挂载参数、驱动它的 `window.VIDEO` 数据从哪来（例如 `captions` 来自 `transcribe/subtitle-units.json`）。layout 的 reserved 区要求的组件必须出现在表里；常驻组件不用在每个 scene 里重复写，scene 里只写本 scene 额外用到的组件。然后以 `scene-plan.json` 为起点逐个 scene 写：可以合并或拆分视觉 scene、改选素材和 pattern；偏离场景规划的地方写明理由；**旁白不能改**（字幕与屏幕文字都以显示稿为准）。
2. **组装和编写画面**。按 storyboard 用 modules 组装：读 `modules/modules.md` 入口、所选 design / layout 文档、需要的 pattern 文档（`modules/patterns/`，只作建议）与组件文档（`modules/components/`）；动效选择参考 `modules/motion.md`。按 storyboard 选定的 design textures、组件和模板资源，由你自己从工作区的 `modules/` 拷进 `composition/`，清单见各模块的文档。
3. **渲染前自查**，全部通过再渲染：
   - 运行 `npx hyperframes check`，修掉所有错误；
   - 运行 check-composition（命令见 handoff 的 Outputs 一节）：它按 layout 区域定义检查越界、侵入 reserved 区域、文字溢出、资源加载失败、字体未加载、字号低于 design 下限、字幕与字幕单元不一致；每条 finding 的形状为 `{scene_id, check, issue, time_s, frame}`，其中 `time_s` 是快照时刻、`frame` 为 null，只修相关 scene；handoff 的命令用 `--output` 把同一份报告写到 `composition/check-composition.json`（stdout 照常打印，findings 直接看输出）；改过画面就重跑，**最后一次的报告必须保存在这个路径且 verdict 为 pass**（主 agent 的状态脚本读它）；
   - 在每个 scene 的中点截一张快照，自己目检一遍（区域使用、可读性、与旁白的同步）。
4. **渲染**。用 HyperFrames 渲染出 `composition/renders/final.mp4`。完成后向主 agent 报告 `storyboard.md`、`index.html`、`renders/final.mp4` 的路径，以及 hyperframes check 与 check-composition 的 verdict；主 agent 会复核产物与两个检查的通过情况。
