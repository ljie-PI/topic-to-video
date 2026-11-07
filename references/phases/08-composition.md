# Phase 8 — composition（委派给 coding agent）

## 输入

### 主 agent 准备时参考

- `inputs.json`（只确认全片固定的 `design` / `orientation` 与用户 `composition_requests`；准备 handoff 还校验 `duration` / `language` / `input_mode` / `fetch_materials` / `coding_agent` 与可选 `delegation`）。主 agent 不选择视觉 scene 或 layout，也不要求预先存在 `composition/scenes.json`。

### Composition agent 阅读与使用

- Phase 7 的 `voice_clone/narration.mp3`；
- `transcribe/timeline.json`（含 `total_s` / `paragraphs`，以及可选 `scenes` / `cues` 的段落与 cue 时间；本阶段不改它）；
- `material-catalog.json`（catalog 适用时使用；JSON 对象，含 `entries` 与论文模式下的 `required_material_refs`；schema 见 `references/delegation/catalog/base-instructions.md`）；
- `clips/`（`material-catalog.json` 中视频 `selected_clips[].clip_path` 引用的无音轨片段；相对工作区根目录；标准模式且 `fetch_materials = false` 时不使用，论文无视频素材时可以不创建）；
- `scene-plan.json`（非空 JSON 列表；每个 scene 含 `scene_id`、1 起的段落号 `paragraphs`、非空 `intent` / `content_plan`，以及可选 `cues` / `material_candidates`；仅作参考）；
- `script.txt`（显示稿，字幕与屏幕文字的文本来源，不能改）；
- `inputs.json`（读取固定的 `design` / `orientation` 与 `composition_requests`，写回所选 `template`；旧 `layout` 字段若存在只作单 layout 工程的默认值，新流程不要求它存在）；
- `prepare-handoff.py` 生成的 `composition-handoff.md`，以及它物化到工作区的委派包、modules 副本和预置字体。

### 仅供工具读取

- `transcribe/transcript.json`（本轮 fresh transcript；非空句子列表，每句含 `begin` / `end` / `text` / `words`，时间为整数毫秒；schema 见 Phase 7）；
- `narration.txt` 与 `narration-offsets.json`：前者是 TTS 朗读稿，后者是逐字符映射回显示稿的偏移表（`version: 1`，含两个长度、两个内容哈希与 `segments`；schema 见 `scripts/make-narration.py`）。

这三份文件由 handoff 中的字幕 / cue 对齐命令读取；composition agent 正常流程不阅读或复述其全文，也不将它们当作另一份旁白。运行命令后读取最终 `composition/assets/subtitle-units.json` 与需要的 cue 时间即可。仅在工具报错且必须诊断时读取相关句子或时间窗口，不重复加载全部文本。文件格式、位置及工具参数保持不变；字幕仍在本阶段生成。

素材路径的 base 不同：图片通过 `local_path` 解析，路径相对工作区的 `harvest_page/`；视频只使用 `selected_clips[].clip_path`，路径相对工作区根目录，不使用原视频的 `local_path`。

**最终视觉 scenes、逐 scene layout 与模板都是本阶段才确定的**：它们不在上游阶段里，也不会让旁白或配音阶段重做。派发 handoff 的前置条件只有固定输入与 Phase 7 产物齐全，**不要求 `inputs.json.layout` 或 `composition/scenes.json` 已存在**；后者是 composition agent 的本阶段产物。

## 输出

- `composition/scenes.json`（最终视觉 scenes 与逐 scene layout；`{version: 1, scenes: [{scene_id, begin_s, end_s, layout}]}`，时间为全片秒）；
- `composition/assets/subtitle-units.json`（按各视觉 scene 的有效 layout 生成的字幕单元）；
- `composition/storyboard.md`；
- `composition/index.html`；
- `composition/compositions/`；
- `composition/check-composition.json`（check-composition 用 `--output` 写出的报告）；
- `composition/renders/final.mp4`。

## 完成判据

- 运行 `pipeline-status` 后，Phase 8 不再是 `next_phase`；状态脚本替你判定下面各项：
- 视觉 scenes 可用：`composition/scenes.json` 是非空的最终视觉切分，scene id 唯一、全片秒合法并覆盖实际 narration 时长；每个 `layout` 都是当前库注册的 layout，且它的 `canvas` 等于 `orientation` 对应的尺寸（1920×1080 / 1080×1920 / 1080×1440，三者互不代替）。转场可重叠，但任一时刻的有效字幕 layout 必须唯一。这一类问题报 `corrupt`，原因写在 `next_phase.problems` 的 `composition/scenes.json` 下；
- 模板已决定：`inputs.json` 的 `template` 必须已经写回（模板名或 `null`；缺省表示 agent 还没决定，不算完成），选中的模板声明支持 `composition/scenes.json` 实际使用的**每一个 layout**；问题记在 `inputs.json#template` 下；
- `composition/assets/subtitle-units.json` 的 `units` 是非空列表；
- `composition/storyboard.md` 非空；
- `composition/index.html` 存在；
- `composition/compositions/` 里至少有一个文件；
- `composition/check-composition.json` 的 `verdict` 为 `pass`，且覆盖当前 composition——报告里的 `sources_sha256` 必须等于当前 `scenes.json` / `index.html` / `compositions/` / `assets/`（字体除外）的内容指纹；`visual_contract_sha256` 还必须覆盖视觉声明与全部有效 layout JSON，`scenes_checked` 覆盖每个视觉 scene 及其实际 layout。缺少这些证据时直接判不合格（改过 scenes、有效 layout 或画面就要重跑 check-composition 并用 `--output` 保存报告）；
- `composition/renders/final.mp4` 存在、非空，且不早于任一画面源文件（`index.html`、`compositions/`、`assets/`、`storyboard.md`）。视觉声明与有效外部 layout 的新旧另由内容指纹和 Phase 8 stamp 追踪，不能用相同字节复制造成的 mtime 变化误判；内容确已变化的确定性重做得到相同字节时，按通用 `--finish` / `--restamp` 规则确认；
- 状态脚本不判定的两项由主 agent 抽查（见 8.4）：`npx hyperframes check` 无错误；storyboard 的每个视觉 scene 都标注了 layout 与所用的 content 区域，并说明了表达设计，模板选择与参考库借用记录符合 composition 基础指令第四部分。

## 执行后自检

`pipeline-status` 会检查字幕、报告结论、报告是否覆盖当前源文件、渲染是否比源文件新（见上）。此外：

- 渲染前：`check-composition` 的 finding 是否都已改完，而不是仅在报告里标 pass。
- 渲染后：抽看一两个关键 scene，确认素材按宽高比放对了、字幕没有溢出、画面能对应旁白。全面成片检查归 Phase 9，不要在这里重复全套。
- 发现内容错位（场景和旁白对不上、素材用错）属于叙事或素材问题，按 `references/pipeline-control.md` 回退到对应阶段，而不是只改 HTML。

## 下一步

Phase 9（检查与混音）：渲染后 QA（`check-render.py` 确定性检查 + `make-contact-sheet.py` 拼图 + 按 `qa_level` 三档的 vision 检查，修复轮最多 2 轮）通过后混入 BGM，得到最终交付文件。

## 护栏

- **预先 stage 确定性的 WOFF2 字体。** Phase 8 的 `scripts/prepare-handoff.py` 按所选 design 调用 `scripts/fonts-download.sh`，预置到 composition 工程的 `assets/fonts/`，handoff 指向该目录。
  ↳ DO NOT：让主 agent 处理 composition 的字体 CSS。
- **字体实现归 HyperFrames。** Phase 8 sub-agent 使用本地字体，并按 `hyperframes` skill 中的排版规则处理。
- **字幕边界归脚本，不归 agent。** 字幕单元由 `align-narration.py --mode subtitles --scenes ... --narration-audio ...` 按各视觉 scene 有效 layout 的 `caption` 规格切好，逐单元原样上屏。
  ↳ DO NOT：自己合并、拆分、重排字幕单元，或手改 `composition/assets/subtitle-units.json`。
- **Composition 委派给 coding agent。** 主 agent 只运行 `scripts/prepare-handoff.py <ws> composition`：它生成 `composition-handoff.md`，把 composition 委派包（`references/delegation/composition/`）与 modules（不含 `examples/`）物化到工作区，再按所选 design 预置字体；委派约定与指令叠加顺序见 `references/delegation/conventions.md`。
  ↳ DO NOT：手写 `composition/index.html`、挑选低层 animation / effect skill，或在本 session 里修 HyperFrames lint；除非用户明确指定，否则由 Phase 8 sub-agent 选择。
- **Scene 设计归 HyperFrames。** 最终视觉切分、逐 scene layout、构图、模板选择、素材映射、视觉层级、动画、lint/inspect 与渲染迭代都发生在 Phase 8；视觉声明由 agent 写入 `composition/scenes.json`，模板字段写回 `inputs.json`。主 agent 只固定 orientation / design / 用户约束，不预选 scene layout；参考库的使用由 composition agent 按基础指令第四部分自行判断。

---

本 phase 整体委派给 coding agent 完成：字幕生成、storyboard、画面组装、渲染前自查与渲染由 composition agent 按委派包独立完成。委派约定见 `references/delegation/conventions.md`（默认目标与模型解析只在该约定里维护；派发 prompt 只有一句话，让对方读 handoff）。composition agent 使用 `hyperframes`、`hyperframes-cli`，按具体动画实现需要查阅 `hyperframes-animation` skill；主 agent 不读委派包里的基础指令。

#### 8.0 — 确认全片约束与派发前置条件

主 agent 只核对 `inputs.json` 的 `orientation` / `design` / `composition_requests`：

- **`orientation` 和 `design` 是已经确定的事实**，本阶段不改它们；用户的新画面约束写入 `composition_requests`。
- **视觉 scenes 与 layout 不在这一步决定。** 主 agent 不读 layout 来替 composition agent 做选择，也不预填 `inputs.json.layout`。composition agent 会按每个实际视觉 scene 的内容选择注册 layout，所有 layout 共用符合 orientation 的 canvas。
- **模板不在这一步决定。** 主 agent 不预填 `template: null` 冒充“已决定不用”，也不替它试模板。`prepare-handoff.py composition` 允许 `layout` 与 `template` 缺省，也允许 `composition/scenes.json` 尚不存在；agent 最终决定 scenes / layouts 与模板，并把模板名或 `null` 写回 `inputs.json`。
- **旧输入仍兼容。** 旧单 layout 工程若已有 `inputs.json.layout` / `template`，准备脚本仍校验其注册、canvas 与兼容性；但新 handoff 的命令一律使用本阶段生成的 `composition/scenes.json`，不把旧默认值当成全片限制。

视觉 scenes 或实际使用的 layout 改变只会让本阶段及下游重做：Phase 7 不依赖它们，音频、transcript 和时间轴都不重建。状态指纹记录 `composition/scenes.json`、实际使用的 design / 全部 layout / template JSON；副本内容改变或 `--refresh` 更新了机器契约时同样重做本阶段，复制相同字节则不算变化。标准无素材模式不读取或记录残留 catalog。

用户在本阶段新提出画面要求时，先按 `references/pipeline-control.md` 写进 `inputs.json` 的 `composition_requests`，再生成 handoff。

#### 8.1 — 物化与字体

运行一次（全部落到 `{work_dir}/{topic_name}/` 下）：

```bash
source .venv/bin/activate && python3 scripts/prepare-handoff.py {work_dir}/{topic_name} composition
```

脚本做三件事：

1. **委派包**：复制 `references/delegation/conventions.md` 与 `references/delegation/composition/` → `{work_dir}/{topic_name}/references/delegation/`，保持相对路径不变。
2. **modules 库**：复制整个 `modules/` 目录（**不含 `examples/`**）→ `{work_dir}/{topic_name}/modules/`。已存在的副本不覆盖；要用 skill 里的最新版覆盖，加 `--refresh`。
3. **字体预置**（由 `inputs.json` 的 design 决定）：每次调用都运行 `fonts-download.sh --theme modules/designs/<design>`，把仓库 `resources/fonts/<design>/` 里的 CSS 和它引用的字体（在共用池 `resources/fonts/files/`）拷进 `composition/assets/fonts/`，不联网。失败时脚本 exit 1，输出里带 `fonts-download.sh` 的错误 JSON。

脚本在写任何副本之前先校验：design 是当前库里的；旧 `layout` 若存在，其文件结构与画布尺寸必须对得上朝向；`template` 已写且有值时它必须是当前库里的并有 `supported_layouts` 声明，旧 layout 同时存在时还必须兼容。校验用的就是工作区实际使用的那份文件（不 `--refresh` 时的 `modules/` 副本）。新流程没有 `inputs.json.layout` 也能准备，最终逐 scene 兼容性在 `composition/scenes.json` 生成后检查。

design textures、组件和模板资源不在这里拷：用哪些由 composition agent 写完 storyboard 才知道，由它自己从工作区的 `modules/` 拷进 `composition/`。

#### 8.2 — handoff

同一次调用还会生成 `{work_dir}/{topic_name}/composition-handoff.md`：Coding Agent（按 `inputs.json` 解析本阶段的 agent；有模型请求时同时展示请求与实际解析值，规则见 `references/delegation/conventions.md`）、Inputs、Outputs（含 `composition/scenes.json`、用 `--scenes` 生成字幕与运行 check-composition 的命令，以及渲染前自查）、Required References（基础指令 → `modules/modules.md` → design 文档 → layout 目录 `modules/layouts/layouts.md`（供 agent 逐 scene 选择并继续读对应 JSON / 文档）→ 模板目录 `templates.md` → 已选模板的文档与 `supported_layouts` 声明 → 组件目录，全部指向 8.1 物化的工作区副本；patterns / motion 另列为可选参考）、Additional Instructions（`composition_requests` 逐条列出；没有写 None）。路径全是绝对路径，命令里的 skill 脚本从 skill 根目录运行。主 agent 不手写 handoff。

`template` 缺省时 handoff 写“未选择（由本阶段决定）”，并仍给出模板目录；为 null 时写“无（不使用模板）”，不列具体模板文档；非法或不兼容的模板名会在写任何物化副本之前 exit 1。

#### 8.3 — 委派 composition agent

用 `prepare-handoff.py` 输出 JSON 里的 `coding_agent` / `coding_model` 选择实际 agent / model，把 `dispatch_prompt` 原样派发，派发方式见 `references/delegation/conventions.md`。

被委派的 agent 自己从磁盘读 handoff、Inputs 中标为「Agent 阅读与画面资源」的文件与 Required References（含工作区的委派包与 modules 副本）；「仅供工具读取」的文件只传给现有命令，不要求全文阅读。主 agent 不在 prompt 里复述指令或重复文本，也**不要**在主 agent 的会话里驱动 composition authoring 或手工 patch `composition/index.html`。

agent 先读旁白与叙事规划，决定实际视觉 scenes 及各自 layout，写出 `composition/scenes.json`。接着它读 `modules/templates/templates.md` 决定模板（或不用），确认模板的 `supported_layouts` 覆盖 scenes 实际使用的每一个 layout，并把选择写回 `inputs.json` 的 `template`。

视觉声明与模板确定后，agent 跑 handoff 里的 `align-narration.py --mode subtitles --scenes ... --narration-audio ...`，把最终字幕生成到 `composition/assets/subtitle-units.json`。这份文件在 `assets/` 下，因此会被 composition 源指纹和渲染新鲜度检查覆盖。然后按基础指令第四部分自主设计构图、动作与动效，选择组件并完成 storyboard 和画面；patterns / motion 的查阅和借用也按该部分处理。scene、layout、模板与画面设计都由它自己负责，主 agent 不代为决定。

#### 8.4 — 主 agent 校验

composition agent 报告完成后：

0. catalog 阶段适用时抽查必用素材：storyboard 的覆盖表是否把 `required_material_refs` 每条都落到了具体 scene，实际画面里能不能看到；不能用“选为候选”冒充“已经展示”。
1. 运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}`。
2. `next_phase` 仍是 Phase 8 时分三种情况：`reason` 为 `missing` / `corrupt` 时，把 `next_phase.problems`（产物 → 原因，包括 `composition/scenes.json` 或 `inputs.json#template` → 原因）原样反馈给 composition agent；`reason` 为 `stale` 时 `problems` 是空的，真正的原因在 `next_phase.changed_upstream`（变化的上游文件列表）里，把它交给 composition agent，让它重新生成受影响的部分。无论哪种情况都限定范围修复，修完再跑一次。不要自己改产物。
3. Phase 8 不再是 `next_phase` 后，抽查状态脚本不判定的两项：agent 报告的 `npx hyperframes check` 无错误；storyboard 的每个视觉 scene 都写明了 layout、所用的 content 区域、构图、信息展开与动效安排，模板选择与参考库借用记录符合基础指令第四部分（设计是否合适看画面与内容是否对得上）。

全部通过后进入 Phase 9。
