# Phase 8 — composition（委派给 coding agent）

## 输入

Phase 7 的 `voice_clone/narration.mp3` + `transcribe/subtitle-units.json` / `transcribe/timeline.json` + `material-catalog.json`（若 `fetch_materials = false` 则无）+ `scene-plan.json`（叙事层场景规划，仅作参考）+ `script.txt` + `inputs.json`（design / layout / template）+ 主 agent 写的 `composition-handoff.md` 与物化到工作区的委派包、modules 副本和预置字体。

## 输出

`composition/storyboard.md` + `composition/index.html` + `composition/compositions/` + `composition/renders/final.mp4`。

## 完成判据

`composition/renders/final.mp4` 存在且非空；`composition/index.html` 与 `composition/compositions/` 存在；`npx hyperframes check` 无错误；`check-composition` 的 verdict 为 pass；storyboard 的每个 scene 都标注了所用的 content 区域。

## 下一步

Phase 9（检查与混音）：渲染后 QA（`check-render.py` 确定性检查 + `make-contact-sheet.py` 拼图 + 按 `qa_level` 三档的 vision 检查，修复轮最多 2 轮）通过后混入 BGM，得到最终交付文件。

---

本 phase 整体委派给 coding agent 完成：storyboard、画面组装、渲染前自查与渲染由 composition agent 按委派包独立完成。委派约定见 `references/delegation/conventions.md`（默认 claude-code；派发 prompt 只有一句话，让对方读 handoff）。composition agent 使用 `hyperframes`、`hyperframes-cli` 与 `hyperframes-animation` skills；主 agent 不读委派包里的基础指令。

#### 8.1 — 物化到工作区

主 agent 做四步准备，全部落到 `{work_dir}/{topic_name}/` 下：

1. **委派包**：复制 `references/delegation/conventions.md` 与 `references/delegation/composition/`（基础指令 + handoff 模板）→ `{work_dir}/{topic_name}/references/delegation/`，保持相对路径不变。
2. **modules 库**：复制整个 `modules/` 目录（**不含 `examples/`**）→ `{work_dir}/{topic_name}/modules/`。modules 内部的相对路径不变，`modules.md`、design / layout / pattern / component 文档与机器可读的区域定义 JSON 都以相同路径出现在工作区。
3. **所选模块资源**：按各模块文档把所选 design 的 textures、所用组件的图片 / HTML、模板资源复制进 composition 工程（如 `composition/assets/textures/`、`composition/compositions/`、`composition/assets/brand/`）；复制清单见 `modules/modules.md` 的「组装一支视频」与所选模块各自的文档。
4. **字体预置**（由所选 design 决定）：每次准备都运行一次（字体从仓库的 `resources/fonts/` 拷贝，不联网，很快；重跑也会补上旧工程缺的新文件名）：

   ```bash
   bash scripts/fonts-download.sh {work_dir}/{topic_name}/composition/assets/fonts \
     --theme modules/designs/<inputs.json 的 design 字段>
   ```

#### 8.2 — 写 `composition-handoff.md`

按 `references/delegation/composition/handoff-template.md` 写出 `{work_dir}/{topic_name}/composition-handoff.md`：填入 Coding Agent（`inputs.json` 的 `coding_agent`，默认 claude-code）、Inputs（上述输入的实际路径）、Outputs、Required References（基础指令 → `modules/modules.md` → 所选 design 文档 → 所选 layout 的 json + 文档 → 模板 / pattern / 组件文档，全部指向 8.1 物化的工作区副本）、Additional Instructions（实际存在的 `composition-instructions.md`，旧项目的 `style-prompt.md` 视为其中一部分；没有写 None）。

#### 8.3 — 委派 composition agent

按 `references/delegation/conventions.md` 派发，prompt 一句话：

```text
读取 {work_dir}/{topic_name}/composition-handoff.md 并按它执行；完成后报告产物路径。
```

被委派的 agent 自己从磁盘读 handoff 与 Required References 列出的文件（含工作区的委派包与 modules 副本）；主 agent 不在 prompt 里复述指令内容，也**不要**在主 agent 的会话里驱动 composition authoring 或手工 patch `composition/index.html`。

#### 8.4 — 主 agent 校验

composition agent 报告完成后，主 agent 逐项校验（不修改产物，不合格就把 findings 反馈回去限定范围修复）：

1. **产物齐全**：`composition/storyboard.md`、`composition/index.html`、非空的 `composition/compositions/`、`composition/renders/final.mp4` 都存在。
2. **渲染前自查通过**：sub-agent 报告的 `npx hyperframes check` 无错误、`check-composition` verdict 为 pass（命令见 composition handoff 模板的渲染前自查一节；可直接重跑核验，或核验其报告的 verdict）。
3. **storyboard 区域标注**：每个 scene 都写明了所用的 content 区域（抽查）。

全部通过后进入 Phase 9。
