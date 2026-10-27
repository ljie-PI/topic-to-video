# Phase 8 — composition（委派给 coding agent）

## 输入

Phase 7 的 `voice_clone/narration.mp3` + `transcribe/subtitle-units.json` / `transcribe/timeline.json` + `material-catalog.json` 与 `clips/`（Phase 5 切好的无音轨片段；标准模式且 `fetch_materials = false` 时都无）+ `scene-plan.json`（叙事层场景规划，仅作参考）+ `script.txt` + `inputs.json`（design / layout / template）+ `prepare-handoff.py` 生成的 `composition-handoff.md`，以及它物化到工作区的委派包、modules 副本和预置字体。

## 输出

`composition/storyboard.md` + `composition/index.html` + `composition/compositions/` + `composition/check-composition.json`（check-composition 用 `--output` 写出的报告）+ `composition/renders/final.mp4`。

## 完成判据

运行 `pipeline-status` 后，Phase 8 不再是 `next_phase`。状态脚本替你判定：`composition/storyboard.md` 非空；`composition/index.html` 存在；`composition/compositions/` 里至少有一个文件；`composition/check-composition.json` 的 `verdict` 为 `pass`，且覆盖当前 composition——报告里的 `sources_sha256` 必须等于当前 `index.html` / `compositions/` / `assets/`（字体除外）的内容指纹（改过画面就要重跑 check-composition 并用 `--output` 保存报告；旧报告没有指纹时退回 mtime 比较，不保留 mtime 的拷贝可能漏检）；`composition/renders/final.mp4` 存在、非空，且不早于任一源文件（`index.html`、`compositions/`、`assets/`、`storyboard.md`）——比源文件旧的渲染不包含那次修改，要重新渲染。状态脚本不判定的两项由主 agent 抽查（见 8.4）：`npx hyperframes check` 无错误；storyboard 的每个 scene 都标注了所用的 content 区域。

## 下一步

Phase 9（检查与混音）：渲染后 QA（`check-render.py` 确定性检查 + `make-contact-sheet.py` 拼图 + 按 `qa_level` 三档的 vision 检查，修复轮最多 2 轮）通过后混入 BGM，得到最终交付文件。

---

本 phase 整体委派给 coding agent 完成：storyboard、画面组装、渲染前自查与渲染由 composition agent 按委派包独立完成。委派约定见 `references/delegation/conventions.md`（默认 claude-code；派发 prompt 只有一句话，让对方读 handoff）。composition agent 使用 `hyperframes`、`hyperframes-cli` 与 `hyperframes-animation` skills；主 agent 不读委派包里的基础指令。

#### 8.1 — 物化与字体

运行一次（全部落到 `{work_dir}/{topic_name}/` 下）：

```bash
source .venv/bin/activate && python3 scripts/prepare-handoff.py {work_dir}/{topic_name} composition
```

脚本做三件事：

1. **委派包**：复制 `references/delegation/conventions.md` 与 `references/delegation/composition/` → `{work_dir}/{topic_name}/references/delegation/`，保持相对路径不变。
2. **modules 库**：复制整个 `modules/` 目录（**不含 `examples/`**）→ `{work_dir}/{topic_name}/modules/`。已存在的副本不覆盖；要用 skill 里的最新版覆盖，加 `--refresh`。
3. **字体预置**（由 `inputs.json` 的 design 决定）：每次调用都运行 `fonts-download.sh`，把仓库 `resources/fonts/<design>/` 里的字体拷进 `composition/assets/fonts/`，不联网。失败时脚本 exit 1，输出里带 `fonts-download.sh` 的错误 JSON。

design textures、组件和模板资源不在这里拷：用哪些由 composition agent 写完 storyboard 才知道，由它自己从工作区的 `modules/` 拷进 `composition/`。

#### 8.2 — handoff

同一次调用还会生成 `{work_dir}/{topic_name}/composition-handoff.md`：Coding Agent（`inputs.json` 的 `coding_agent`，默认 claude-code）、Inputs、Outputs（含渲染前自查的命令）、Required References（基础指令 → `modules/modules.md` → design 文档 → layout 的 json 与文档 → 模板文档 → pattern / 组件目录，全部指向 8.1 物化的工作区副本）、Additional Instructions（实际存在的 `composition-instructions.md` 和旧项目的 `style-prompt.md`；没有写 None）。路径全是绝对路径，命令里的 skill 脚本从 skill 根目录运行。主 agent 不手写 handoff。

#### 8.3 — 委派 composition agent

把 `prepare-handoff.py` 输出 JSON 里的 `dispatch_prompt` 原样派发，派发方式见 `references/delegation/conventions.md`。

被委派的 agent 自己从磁盘读 handoff 与 Required References 列出的文件（含工作区的委派包与 modules 副本）；主 agent 不在 prompt 里复述指令内容，也**不要**在主 agent 的会话里驱动 composition authoring 或手工 patch `composition/index.html`。

#### 8.4 — 主 agent 校验

composition agent 报告完成后：

1. 运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}`。
2. `next_phase` 仍是 Phase 8 时分两种情况：`reason` 为 `missing` / `corrupt` 时，把 `next_phase.problems`（产物 → 原因）原样反馈给 composition agent；`reason` 为 `stale` 时 `problems` 是空的，真正的原因在 `next_phase.changed_upstream`（变化的上游文件列表）里，把它交给 composition agent，让它重新生成受影响的部分。无论哪种情况都限定范围修复，修完再跑一次。不要自己改产物。
3. Phase 8 不再是 `next_phase` 后，抽查状态脚本不判定的两项：agent 报告的 `npx hyperframes check` 无错误；storyboard 的每个 scene 都写明了所用的 content 区域。

全部通过后进入 Phase 9。
