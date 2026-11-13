# Phase 8 — composition（委派给 coding agent）

## 输入

### 主 agent 准备时参考

- `inputs.json`（确认全片固定的 `orientation`、可选的用户 `design` 约束与 `composition_requests`；准备 handoff 还校验 `duration` / `language` / `input_mode` / `fetch_materials` / `coding_agent` 与可选 `delegation`）。主 agent 不选择视觉 scene、模板或 layout，也不预选默认 design，不要求预先存在 `composition/design.json` / `composition/scene-config.json`。

### Composition agent 阅读与使用

- Phase 7 的 `voice_clone/narration.mp3`；
- `transcribe/timeline.json`（含 `total_s` / `paragraphs`，以及可选 `scenes` / `cues` 的段落与 cue 时间；本阶段不改它）；
- `material-catalog.json`（catalog 适用时使用；JSON 对象，含 `entries` 与论文模式下的 `required_material_refs`；schema 见 `references/delegation/catalog/base-instructions.md`）；
- `clips/`（`material-catalog.json` 中视频 `selected_clips[].clip_path` 引用的无音轨片段；相对工作区根目录；标准模式且 `fetch_materials = false` 时不使用，论文无视频素材时可以不创建）；
- `scene-plan.json`（非空 JSON 列表；每个 scene 含 `scene_id`、1 起的段落号 `paragraphs`、非空 `intent` / `content_plan`，以及可选 `cues` / `material_candidates`；仅作参考）；
- `script.txt`（显示稿，字幕、屏幕文字与 cue 的文本来源，不能改）；
- `inputs.json`（读取 `orientation`、可选的用户 `design` 约束与 `composition_requests`；没有 `design` 时由 composition agent 选择 preset 或生成 custom design。用户画面要求的作用范围以用户表述为准：某个叙事场景、某个视觉场景或整片）；
- `prepare-handoff.py` 生成的 `composition-handoff.md`，以及它物化到工作区的委派包和 modules 副本；字体由 composition agent 选定 design 后安装。

### 仅供工具读取

- `transcribe/transcript.json`（本轮 fresh transcript；非空句子列表，每句含 `begin` / `end` / `text` / `words`，时间为整数毫秒；schema 见 Phase 7）；
- `narration.txt` 与 `narration-offsets.json`：前者是 TTS 朗读稿，后者是逐字符映射回显示稿的偏移表（`version: 1`，含两个长度、两个内容哈希与 `segments`；schema 见 `scripts/make-narration.py`）。

这三份文件由 handoff 中的字幕 / cue 对齐命令读取；composition agent 正常流程不阅读或复述其全文，也不将它们当作另一份旁白。运行命令后读取最终 `composition/assets/subtitle-units.json` 与需要的 cue 时间即可。仅在工具报错且必须诊断时读取相关句子或时间窗口，不重复加载全部文本。文件格式、位置及工具参数保持不变；字幕仍在本阶段生成。

素材路径的 base 不同：图片通过 `local_path` 解析，路径相对工作区的 `harvest_page/`；视频只使用 `selected_clips[].clip_path`，路径相对工作区根目录，不使用原视频的 `local_path`。

## 输出

- `composition/design.json`（全片外观机器契约；根字段恰好为 `version` / `source` / `preset` / `tokens` / `min_font_px`；preset 与注册 JSON 一致，custom 的 `preset` 为 `null` 且同样写完整 tokens 与正整数 reading / ui 字号下限；不含 `fonts` 维护清单）；
- `composition/scene-config.json`（最终视觉场景的机器配置；`{version: 1, canvas, total_s, scenes}`，每个 scene 含唯一 `scene_id`、`source_scene_ids`、`begin_s` / `end_s`、`template`（`null` 或 `{name, scene}`）与落盘完整 `regions` / `caption` 的 `layout`，时间为全片秒）；
- `composition/assets/subtitle-units.json`（按各视觉 scene 落盘的 caption 规格生成的字幕单元；已有用户编辑是有效输入）；
- `composition/storyboard.md`；
- `composition/index.html`；
- `composition/compositions/`；
- `composition/check-composition.json`（check-composition 用 `--output` 写出的报告）；
- `composition/renders/final.mp4`。

## 完成判据

- 运行 `pipeline-status` 后，Phase 8 不再是 `next_phase`；状态脚本替你判定下面各项：
- `composition/design.json` 通过公共读取接口校验：preset / custom 均有完整共享 tokens 与有效字号下限，preset 没有值漂移，custom 不冒用 preset 名；
- scene-config 可用：`composition/scene-config.json` 通过公共读取接口校验（画布等于 `orientation` 对应尺寸、scene id 唯一、`begin_s` / `end_s` 有限且主区间按 `[begin_s, end_s)` 有序、不重叠、覆盖到 `total_s`、源场景引用有效、区域几何合法、caption 规格为正、声明的模板资源存在）。这一类问题报 `corrupt`，原因写在 `next_phase.problems` 的 `composition/scene-config.json` 下；
- `composition/assets/subtitle-units.json` 的 `units` 是非空列表；
- `composition/storyboard.md` 非空；
- `composition/index.html` 存在；
- `composition/compositions/` 里至少有一个文件；
- `composition/check-composition.json` 的 `verdict` 为 `pass`，且覆盖当前 scene-config——`scenes_checked` 覆盖每个视觉 scene 及其实际 layout（preset 名或自由布局的 `null`）。改过 scene-config 或画面就要重跑 check-composition 并用 `--output` 保存报告；状态脚本只验收报告数据本身，不比对源文件哈希或修改时间；
- `composition/renders/final.mp4` 存在、非空。渲染是否覆盖最新画面由执行流程保证：改过画面就重新渲染，不由文件时间充当验收证据；
- 状态脚本不判定的两项由主 agent 抽查（见 8.4）：`npx hyperframes check` 无错误；storyboard 的每个视觉 scene 都标注了 template / layout 方案与所用的 content 区域，并说明了表达设计，模板 / 布局选择的理由与参考库借用记录符合 composition 基础指令第四部分。

## 执行后自检

`pipeline-status` 会检查字幕、报告结论、报告是否覆盖当前源文件、渲染是否比源文件新（见上）。此外：

- 渲染前：`check-composition` 的 finding 是否都已改完，而不是仅在报告里标 pass。
- 渲染后：抽看一两个关键 scene，确认素材按宽高比放对了、字幕没有溢出、画面能对应旁白。全面成片检查归 Phase 9，不要在这里重复全套。
- 发现内容错位（场景和旁白对不上、素材用错）属于叙事或素材问题，按 `references/pipeline-control.md` 回退到对应阶段，而不是只改 HTML。

## 下一步

Phase 9（检查与混音）：渲染后 QA（`check-render.py` 确定性检查 + `make-contact-sheet.py` 拼图 + 按 `qa_level` 三档的 vision 检查，修复轮最多 2 轮）通过后混入 BGM，得到最终交付文件。

## 护栏

- **选定 design 后 stage 确定性的 WOFF2 字体。** `prepare-handoff.py` 不预装字体；composition agent 决定 preset / custom 后按 handoff 的通用命令安装到 `composition/assets/fonts/`，写 `composition/design.json`，再引入实际字体 CSS。项目字体只来自本 skill 已提交的字体包，不用系统字体。
  ↳ DO NOT：让主 agent 处理 composition 的字体 CSS。
- **字幕默认脚本生成，编辑是正常制作行为。** 字幕单元由 `align-narration.py --mode subtitles --scene-config ... --narration-audio ...` 按各视觉 scene 落盘的 `caption` 规格切好；已有用户编辑是有效输入，仅改画面 / 重渲染不自动覆盖字幕，也没有编辑许可 gate。
  ↳ DO NOT：无必要地重新生成已编辑过的字幕，或让合并 / 拆分跨过不同 scene 的切点切断英文词与数字。
- **Composition 委派给 coding agent。** 主 agent 只运行 `scripts/prepare-handoff.py <ws> composition`：它生成 `composition-handoff.md`，把 composition 委派包（`references/delegation/composition/`）与 modules 物化到工作区；design 选择与字体安装由子 agent 完成。委派约定与指令叠加顺序见 `references/delegation/conventions.md`。
  ↳ DO NOT：手写 `composition/index.html`、挑选低层 animation / effect skill，或在本 session 里修 HyperFrames lint；除非用户明确指定，否则由 Phase 8 sub-agent 选择。
- **Scene 设计由 composition agent 负责。** 最终视觉切分、逐场景 template / layout（含自由布局）、构图、素材映射、视觉层级、动画、lint/inspect 与渲染迭代都发生在 Phase 8；`composition/scene-config.json` 与 storyboard 由 agent 写出。主 agent 只固定 orientation、用户明确指定的 design 与其他约束，不预选默认 design 或任何 scene 方案；参考库的使用由 composition agent 按基础指令第四部分自行判断。

---

本 phase 整体委派给 coding agent 完成：字幕生成、storyboard、画面组装、渲染前自查与渲染由 composition agent 按委派包独立完成。委派约定见 `references/delegation/conventions.md`（默认目标与模型解析只在该约定里维护；派发 prompt 只有一句话，让对方读 handoff）。composition agent 只使用 `hyperframes`、`hyperframes-cli` 两个 skill；主 agent 不读委派包里的基础指令。

#### 8.0 — 确认全片约束与派发前置条件

主 agent 只核对 `inputs.json` 的 `orientation`、可选 `design` 与 `composition_requests`：

- **`orientation` 是已经确定的事实**；`design` 只有用户明确指定时才是约束，未指定时不补默认。用户的新画面约束写入 `composition_requests`。
- **视觉 scenes、模板与 layout 不在这一步决定。** 主 agent 不读 layout 来替 composition agent 做选择，不要求预先决定全局 template / layout，也不要求 `composition/scene-config.json` 已存在——它由 composition agent 在本阶段产出。composition agent 按每个实际视觉 scene 的内容选择注册 preset 或自主设计自由布局，所有布局共用符合 orientation 的固定画布。
- **旧输入不作门槛。** 旧工作区的 `inputs.json.layout` / `template` / `design` 原样保留、不做未经确认的数据删除；已有 design 继续作为用户约束，但准备与状态脚本不要求新工作区必须有它，也不拿旧 template / layout 当门槛；新流程的命令一律消费本阶段生成的 `composition/scene-config.json`。

视觉 scenes 或实际使用的 layout 改变只会让本阶段及登记的下游重做：Phase 7 不依赖它们，音频、transcript 和时间轴都不重建。主 agent 核对影响范围后显式登记 `--redo 8-composition`，并按交付范围决定 Phase 9 的 QA / 混音是否重跑；标准无素材模式不读取残留 catalog。

用户在本阶段新提出画面要求时，先按 `references/pipeline-control.md` 写进 `inputs.json` 的 `composition_requests`，再生成 handoff。

#### 8.1 — 物化委派包与 modules

运行一次（全部落到 `{work_dir}/{topic_name}/` 下）：

```bash
source .venv/bin/activate && python3 scripts/prepare-handoff.py {work_dir}/{topic_name} composition
```

脚本做两件事（design 与字体留给子 agent）：

1. **委派包**：复制 `references/delegation/conventions.md` 与 `references/delegation/composition/` → `{work_dir}/{topic_name}/references/delegation/`，保持相对路径不变。
2. **modules 库**：复制整个 `modules/` 目录 → `{work_dir}/{topic_name}/modules/`。已存在的副本不覆盖；要用 skill 里的最新版覆盖，加 `--refresh`。

脚本只在 `design` 出现时校验它是当前库里的注册名；缺省不预选。全局 template / layout 不是准备前提；`design.json` 与 `scene-config.json` 的公共校验在状态验收中使用。

composition agent 先读旁白与叙事规划（`script.txt`、`scene-plan.json`、timeline 与素材目录），再决定 preset / custom，运行 `npx hyperframes init composition/`（仅当 `composition/` 目录不存在时），按 handoff 运行 `fonts-download.sh --theme modules/designs/<design>` 安装字体并写 `composition/design.json`。具体 design textures、组件、转场和模板资源由它选定后自己从工作区的 `modules/` 拷进 `composition/`。

#### 8.2 — handoff

同一次调用还会生成 `{work_dir}/{topic_name}/composition-handoff.md`：Coding Agent（按 `inputs.json` 解析本阶段的 agent；有模型请求时同时展示请求与实际解析值，规则见 `references/delegation/conventions.md`）、Inputs、Outputs（含 `composition/scene-config.json`、用 `--scene-config` 生成字幕与运行 check-composition 的命令，以及渲染前自查）、Required References（基础指令 → scene-config 数据契约 → `modules/modules.md` → `modules/designs/designs.md` 目录（具体 design 文档 / JSON 选定后按需读）→ layout 目录 `modules/layouts/layouts.md`（可借用的 preset）→ 模板目录 `templates.md`（按场景借用）→ 组件索引 `modules/components/components.md`（按需读要挂载的组件文档），全部指向 8.1 物化的工作区副本；patterns / motion / transitions 另列为可选参考）、Additional Instructions（`composition_requests` 逐条列出并说明作用范围；没有写 None）。路径全是绝对路径，命令里的 skill 脚本从 skill 根目录运行。主 agent 不手写 handoff。

用户显式给出的非法 design 名会在写任何物化副本之前 exit 1；缺少 design 不会失败，CLI JSON 的 `fonts` 保持 `null`。

#### 8.3 — 委派 composition agent

用 `prepare-handoff.py` 输出 JSON 里的 `coding_agent` / `coding_model` 选择实际 agent / model，把 `dispatch_prompt` 原样派发，派发方式见 `references/delegation/conventions.md`。

被委派的 agent 自己从磁盘读 handoff、Inputs 中标为「Agent 阅读与画面资源」的文件与 Required References（含工作区的委派包与 modules 副本）；「仅供工具读取」的文件只传给现有命令，不要求全文阅读。主 agent 不在 prompt 里复述指令或重复文本，也**不要**在主 agent 的会话里驱动 composition authoring 或手工 patch `composition/index.html`。

agent 先读旁白与叙事规划（`script.txt`、`scene-plan.json`、timeline 与素材目录），再根据全片与各 scene 需求决定 preset / custom design；`composition/` 目录不存在时先运行 `npx hyperframes init composition/`，再安装字体并写 `composition/design.json`；然后决定实际视觉切分，对每个视觉场景按固定顺序（用户要求 → 特别匹配模块 → 即时生成）定方案，写出 `composition/scene-config.json` 与 storyboard。模板与 preset 按场景借用：只在用户明确指定或与目标 scene 特别匹配时才采用，`template: null` 与 `preset: null` 的即时生成自由布局是正常路径。

scene-config 写出后，agent 跑 handoff 里的 `align-narration.py --mode subtitles --scene-config ... --narration-audio ...`，把字幕生成到 `composition/assets/subtitle-units.json`（已有用户编辑是有效输入）。然后按基础指令第四部分自主设计构图、动作与动效，选择实际需要的组件或转场并完成 storyboard 和画面；storyboard 开头用「组件与转场使用表」逐个记录它们的挂载参数与 `window.VIDEO` 数据来源，采用转场时包括 `cuts`。patterns / motion / transitions 的查阅和借用也按该部分处理，transitions 不是所有 scene 的必读或必用模块。scene、layout、模板与画面设计都由它自己负责，主 agent 不代为决定。

#### 8.4 — 主 agent 校验

composition agent 报告完成后：

0. catalog 阶段适用时抽查必用素材：storyboard 的覆盖表是否把 `required_material_refs` 每条都落到了具体 scene，实际画面里能不能看到；不能用“选为候选”冒充“已经展示”。
1. 运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}`。
2. `next_phase` 仍是 Phase 8 时分两种情况：`reason` 为 `missing` / `corrupt` 时，把 `next_phase.problems`（产物 → 原因，包括 `composition/scene-config.json` → 原因）原样反馈给 composition agent；`reason` 为 `redo` 时把 `redo_reason` 一并交给它。无论哪种情况都限定范围修复，修完由主 agent `--finish` 后再跑一次。不要自己改产物。
3. Phase 8 不再是 `next_phase` 后，抽查状态脚本不判定的两项：agent 报告的 `npx hyperframes check` 无错误；storyboard 的每个视觉 scene 都写明了 template / layout 方案与理由、所用的 content 区域、构图、信息展开与动效安排，必用素材覆盖表齐全，参考库借用记录符合基础指令第四部分（设计是否合适看画面与内容是否对得上）。

全部通过后进入 Phase 9。
