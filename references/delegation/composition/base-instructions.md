# composition 委派包 — 基础指令（画面组装与渲染）

你负责为一个解说视频设计并实现**全部画面**：以场景规划为起点，自己写 storyboard，用 modules 组装画面并渲染成 `final.mp4`。主 agent 不会替你做这些决定；你独立完成并落盘产物。

先读工作区里的输入（handoff 的 Inputs 一节列出的文件），再按下面的约束执行。指令冲突时，按 `references/delegation/conventions.md` 的叠加顺序处理：后读的（模板组装说明 → 项目指令 → 用户追加要求）覆盖先读的。

本指令只有三部分约束——输入契约、必须参考 design、必须遵守 layout 区域——和一条工作顺序。除此之外你没有别的规则：scene 怎么切、素材怎么摆、动效怎么选，是你的设计空间。

## 一、输入契约

- **配音**：只用主 agent 生成的 `voice_clone/narration.mp3`，不重生成 TTS、不用任何其他音频来源；画面与解说的同步以这份音频为最终边界。
- **字幕**：字幕文本来自 `transcribe/subtitle-units.json` 的字幕单元，逐字使用，不自己改写、不重新断句。字幕单元已按句末标点分段，句内只在 `，；、：——`（含半角 `, ; :`）处断开、绝不在单词或数字中间切断：单元边界不可改动（禁止重新排序、合并或拆分），逐单元原样上屏。
- **时间**：段落与 cue 的起止秒来自 `transcribe/timeline.json`；scene 切分和 cue 锚点对齐以它为准。
- **素材**：画面素材只来自 `material-catalog.json`（图片用素材 id、视频 clip 用 `<video_id>:<start>-<end>` 解析到 `local_path`）；catalog 沿用 v2 harvest manifest 的路径，所有相对 `local_path` 都以 `{work_dir}/{topic_name}/harvest_page/` 为 base（不是 `composition/` 或当前目录），旧 catalog 的绝对路径原样使用；读取或复制进 composition 前先按此规则解析。视频素材一律静音播放（`<video>` 带 `muted playsinline`）。
- **字体**：只用主 agent 预置的字体目录（`composition/assets/fonts/`，由所选 design 决定），不依赖系统字体。

## 二、必须参考 design

- 颜色、字体、动效只取所选 design 的 token（token 契约见 `modules/designs/designs.md` 与 `modules/designs/<design>/<design>.md`）。
- 字号守所选 design 的「字号下限」：面板标题栏、按钮、小标签这类界面小字放在带 `data-text-role="ui"` 的元素里，按界面小字下限检查；其余文字都按阅读文字下限检查。
- 选了模板时，模板的专属变量与覆盖值**写在 design 之后**，只能增补主题，不能替换 design 的语义。

## 三、必须遵守 layout 区域

- 先读所选布局的区域定义 `modules/layouts/<layout>.json`：画布尺寸、区域列表（每个区域有 id、kind（content / reserved）、rect；reserved 区域写明对应组件）与字幕规格。文档版 `modules/layouts/<layout>.md` 与 JSON 一一对应。
- storyboard 里**每个 scene 都要写明用了哪些 content 区域**。
- 所有元素只放在 content 区域内；reserved 区域只放各自对应的组件（如导航栏区只放 `nav-bar`、字幕条区只放 `caption-bar`）。

## 工作顺序

1. **写 storyboard**。以 `scene-plan.json` 为起点：可以合并或拆分视觉 scene、改选素材和 pattern；偏离场景规划的地方写明理由；**旁白不能改**（字幕与屏幕文字都以显示稿为准）。
2. **组装和编写画面**。按 storyboard 用 modules 组装：读 `modules/modules.md` 入口、所选 design / layout 文档、需要的 pattern 文档（`modules/patterns/`，只作建议）与组件文档（`modules/components/`）；动效选择参考 `modules/motion.md`。
3. **渲染前自查**，全部通过再渲染：
   - 运行 `npx hyperframes check`，修掉所有错误；
   - 运行 check-composition（命令见 handoff 的 Outputs 一节）：它按 layout 区域定义检查越界、侵入 reserved 区域、文字溢出、资源加载失败、字体未加载、字号低于 design 下限、字幕与字幕单元不一致；每条 finding 的形状为 `{scene_id, check, issue, time_s, frame}`，其中 `time_s` 是快照时刻、`frame` 为 null，只修相关 scene；stdout 按 handoff 的命令重定向保存为 `composition/check-composition.json`，改过画面就重跑，**最后一次的结果必须保存在这个路径且 verdict 为 pass**（主 agent 的状态脚本读它）；
   - 在每个 scene 的中点截一张快照，自己目检一遍（区域使用、可读性、与旁白的同步）。
4. **渲染**。用 HyperFrames 渲染出 `composition/renders/final.mp4`。完成后向主 agent 报告 `storyboard.md`、`index.html`、`renders/final.mp4` 的路径，以及 hyperframes check 与 check-composition 的 verdict；主 agent 会复核产物与两个检查的通过情况。
