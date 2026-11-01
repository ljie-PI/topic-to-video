# Phase 8 — composition（委派给 coding agent）

## 输入

- Phase 7 的 `voice_clone/narration.mp3`；
- `transcribe/transcript.json`（本轮 fresh transcript）、`narration.txt` 与 `narration-offsets.json`：本阶段自己跑字幕时要用；
- `transcribe/timeline.json`（段落与 cue 时间；本阶段不改它）；
- `material-catalog.json` 与 `clips/`（Phase 5 切好的无音轨片段；标准模式且 `fetch_materials = false` 时都无；论文模式下的 `required_material_refs` 列出必用图表）；
- `scene-plan.json`（叙事层场景规划，每个 scene 的 `intent` / `content_plan` 说明讲什么、怎样展开；仅作参考）；
- `script.txt`；
- `inputs.json`（本阶段写入 `layout` 与 `template`；读 `design` / `orientation` / `composition_requests`）；
- `prepare-handoff.py` 生成的 `composition-handoff.md`，以及它物化到工作区的委派包、modules 副本和预置字体。

**模板与 layout 都是本阶段才确定的**（见 8.0）：它们不在上游阶段里，也不会让旁白或配音阶段重做。

## 输出

- `composition/assets/subtitle-units.json`（按最终 layout 生成的字幕单元）；
- `composition/storyboard.md`；
- `composition/index.html`；
- `composition/compositions/`；
- `composition/check-composition.json`（check-composition 用 `--output` 写出的报告）；
- `composition/renders/final.mp4`。

## 完成判据

- 运行 `pipeline-status` 后，Phase 8 不再是 `next_phase`；状态脚本替你判定下面各项：
- 视觉配置可用：`inputs.json` 的 `layout` 是当前库注册的 layout，且它的 `canvas` 等于 `orientation` 对应的尺寸（1920×1080 / 1080×1920 / 1080×1440，三者互不代替）；`template` 必须已经写回（模板名或 `null`；缺省表示 agent 还没决定，不算完成），选中的模板声明支持这个 layout。这一类问题报 `corrupt`，原因写在 `next_phase.problems` 的 `inputs.json#layout` / `inputs.json#template` 下；
- `composition/assets/subtitle-units.json` 的 `units` 是非空列表；
- `composition/storyboard.md` 非空；
- `composition/index.html` 存在；
- `composition/compositions/` 里至少有一个文件；
- `composition/check-composition.json` 的 `verdict` 为 `pass`，且覆盖当前 composition——报告里的 `sources_sha256` 必须等于当前 `index.html` / `compositions/` / `assets/`（字体除外）的内容指纹；报告没有 `sources_sha256` 时直接判不合格（改过画面就要重跑 check-composition 并用 `--output` 保存报告）；
- `composition/renders/final.mp4` 存在、非空，且不早于任一源文件（`index.html`、`compositions/`、`assets/`、`storyboard.md`）——比源文件旧的渲染不包含那次修改，要重新渲染；
- 状态脚本不判定的两项由主 agent 抽查（见 8.4）：`npx hyperframes check` 无错误；storyboard 的每个 scene 都标注了所用的 content 区域，并写明了模板 / pattern 的选择与理由。

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
- **字幕边界归脚本，不归 agent。** 字幕单元由 `align-narration.py --mode subtitles` 按 layout 的 `caption` 规格切好，逐单元原样上屏。
  ↳ DO NOT：自己合并、拆分、重排字幕单元，或手改 `composition/assets/subtitle-units.json`。
- **Composition 委派给 coding agent。** 主 agent 只运行 `scripts/prepare-handoff.py <ws> composition`：它生成 `composition-handoff.md`，把 composition 委派包（`references/delegation/composition/`）与 modules（不含 `examples/`）物化到工作区，再按所选 design 预置字体；委派约定与指令叠加顺序见 `references/delegation/conventions.md`。
  ↳ DO NOT：手写 `composition/index.html`、挑选低层 animation / effect skill，或在本 session 里修 HyperFrames lint；除非用户明确指定，否则由 Phase 8 sub-agent 选择。
- **Scene 设计归 HyperFrames。** 切分、构图、模板与 pattern 选择、素材映射、视觉层级、动画、lint/inspect 与渲染迭代都发生在 Phase 8；模板字段由被委派的 agent 写回 `inputs.json`。

---

本 phase 整体委派给 coding agent 完成：字幕生成、storyboard、画面组装、渲染前自查与渲染由 composition agent 按委派包独立完成。委派约定见 `references/delegation/conventions.md`（默认 pi-coding-agent（命令 `pi`）；派发 prompt 只有一句话，让对方读 handoff）。composition agent 使用 `hyperframes`、`hyperframes-cli` 与 `hyperframes-animation` skills；主 agent 不读委派包里的基础指令。

#### 8.0 — 选 layout

layout 在这一步定，之后才准备 handoff。读 `research-brief.md`、`script.txt`、`scene-plan.json` 和 `inputs.json` 的 `orientation` / `design` / `composition_requests` 决定：

- **`orientation` 和 `design` 是已经确定的事实**，本阶段不改它们。
- **按 `orientation` 选 layout**：横屏用 `presenter`（用户明确要求主持人、有人讲解或 Jay）或 `stage`（其他横屏）；竖屏用 `portrait`（9:16）或 `portrait-3x4`（3:4）。只用 `modules/layouts/` 里注册的 layout；三个朝向的画布尺寸互不代替。
- **约束优先于模板**：用户禁止人物、或朝向只能用竖屏时，选对应 layout，把冲突交给 composition agent（不可能套模板时它会写 `template: null`）；不要偷偷改朝向或 design。
- **写入 `inputs.json`**：只把选定的 `layout` 写回字段，再跑 `prepare-handoff.py composition`。

**模板不在这一步决定。** 选哪个模板、或不用模板，是 composition agent 在 8.3 执行时的设计决定：主 agent 不预填 `template: null` 冒充“已决定不用”，也不替它试模板。`prepare-handoff.py composition` 允许 `template` 缺省（handoff 会写“未选择（由本阶段决定）”）；agent 必须在 `inputs.json` 写回模板名或 `null`，否则 Phase 8 不会通过完成判据。

layout 的改变只会让本阶段重做：Phase 7 不依赖它，音频、transcript 和时间轴都不重建。状态指纹还记录实际使用的 design / layout / template JSON；副本内容改变或 `--refresh` 更新了机器契约时同样重做本阶段，复制相同字节则不算变化。标准无素材模式不读取或记录残留 catalog。

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

脚本在写任何副本之前先校验：design / layout 都是当前库里的，layout 文件的结构与画布尺寸对得上朝向；`template` 已写且有值时它必须是当前库里的，并声明支持这个 layout。校验用的就是 handoff 接下来会引用的那份文件（不 `--refresh` 时的 `modules/` 副本）。

design textures、组件和模板资源不在这里拷：用哪些由 composition agent 写完 storyboard 才知道，由它自己从工作区的 `modules/` 拷进 `composition/`。

#### 8.2 — handoff

同一次调用还会生成 `{work_dir}/{topic_name}/composition-handoff.md`：Coding Agent（按 `inputs.json` 解析本阶段的 agent / model，默认 pi-coding-agent，命令 `pi`）、Inputs、Outputs（含生成字幕、check-composition 与渲染前自查的命令）、Required References（基础指令 → `modules/modules.md` → design 文档 → layout 的 json 与文档 → 模板目录 `templates.md`（供 agent 选模板）→ 已选模板的文档与 `supported_layouts` 声明 → pattern / 组件目录，全部指向 8.1 物化的工作区副本）、Additional Instructions（`composition_requests` 逐条列出；没有写 None）。路径全是绝对路径，命令里的 skill 脚本从 skill 根目录运行。主 agent 不手写 handoff。

`template` 缺省时 handoff 写“未选择（由本阶段决定）”，并仍给出模板目录；为 null 时写“无（不使用模板）”，不列具体模板文档；非法或不兼容的模板名会在写任何物化副本之前 exit 1。

#### 8.3 — 委派 composition agent

用 `prepare-handoff.py` 输出 JSON 里的 `coding_agent` / `coding_model` 选择实际 agent / model，把 `dispatch_prompt` 原样派发，派发方式见 `references/delegation/conventions.md`。

被委派的 agent 自己从磁盘读 handoff 与 Required References 列出的文件（含工作区的委派包与 modules 副本）；主 agent 不在 prompt 里复述指令内容，也**不要**在主 agent 的会话里驱动 composition authoring 或手工 patch `composition/index.html`。

agent 的第一件事是跑 handoff 里的 `align-narration.py --mode subtitles`，把最终字幕生成到 `composition/assets/subtitle-units.json`。这份文件在 `assets/` 下，因此会被 composition 源指纹和渲染新鲜度检查覆盖。

接着它读 `modules/templates/templates.md` 决定模板（或不用）、把选择写回 `inputs.json` 的 `template`，再读选中模板的文档与 `supported_layouts`，然后按基础指令的第四部分选择 pattern、动作与演绎方式。模板、pattern 与动作的选择都由它自己负责，主 agent 不代为决定。

#### 8.4 — 主 agent 校验

composition agent 报告完成后：

0. catalog 阶段适用时抽查必用素材：storyboard 的覆盖表是否把 `required_material_refs` 每条都落到了具体 scene，实际画面里能不能看到；不能用“选为候选”冒充“已经展示”。
1. 运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}`。
2. `next_phase` 仍是 Phase 8 时分三种情况：`reason` 为 `missing` / `corrupt` 时，把 `next_phase.problems`（产物 → 原因，或 `inputs.json#layout` / `inputs.json#template` → 原因）原样反馈给 composition agent；`reason` 为 `stale` 时 `problems` 是空的，真正的原因在 `next_phase.changed_upstream`（变化的上游文件列表）里，把它交给 composition agent，让它重新生成受影响的部分。无论哪种情况都限定范围修复，修完再跑一次。不要自己改产物。
3. Phase 8 不再是 `next_phase` 后，抽查状态脚本不判定的两项：agent 报告的 `npx hyperframes check` 无错误；storyboard 的每个 scene 都写明了所用的 content 区域，并记录了模板 / pattern 的选择与理由（模板选择是否合适看画面与内容是否对得上）。

全部通过后进入 Phase 9。
