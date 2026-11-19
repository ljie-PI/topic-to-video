# Phase 11 — 生成封面（委派给 coding agent；可选，`inputs.json` 的 `cover = false` 时跳过）

本 phase 默认开启（`inputs.json` 的 `cover` 缺省或为 `true` 时进入）；仅当用户明确不要视频封面、在 `inputs.json` 写入 `cover = false` 时，`pipeline-status` 跳过本阶段。

## 输入

### 主 agent 准备时参考

- `inputs.json`：核对可选布尔开关 `cover`、可选列表 `cover_requests` 及可选 `delegation.cover`。主 agent 不手写封面 HTML 或修图。
- `qa/`（`qa/qa-report.json` 与 `qa/sheet_NNN.jpg`）与可选 `search-notes.md`：在本阶段完成后随最终成片与封面统一向用户交付。

### Cover agent 阅读与使用

- `research-brief.md`（已核实的事实、数字与引文，封面文案与数据的唯一事实边界）；
- `script.txt` 与 `scene-plan.json`（Phase 6 显示稿与叙事规划，只读不改）；
- `transcribe/timeline.json` 与 `composition/assets/subtitle-units.json`（定位视频前 15 秒与全片核心内容时刻，只读不改）；
- `composition/design.json` 与 `composition/assets/fonts/`（Phase 8 落盘的外观 token 基线与本地字体，保证主题一致）；
- `composition/scene-config.json` 与 `composition/renders/final.mp4`（截取前 15 秒与全片最重要的 1–2 帧，并按 `regions` 裁净播放态保留区）；
- `material-catalog.json`（catalog 适用时使用；图片 `local_path` 相对 `harvest_page/`，视频片段相对工作区根 `clips/`）；
- `modules/components/presenter/images/presenter-wave.png`（必用招手主持人透明底立绘，按各尺寸固定槽位挂载）；
- `inputs.json` 与 `cover-handoff.md`（读取 `orientation`、语言与 `cover_requests`）。

## 输出

- `cover/cover_{W}x{H}.png`（主题一致 + 点击率优先的 `1×` 成品位图）；未在 `cover_requests` 另行限定尺寸时，默认同时产出 `1080x1440`（竖版 3:4）、`1440x1080`（横版 4:3）、`1920x1080`（横版 16:9）三套尺寸；
- `cover/cover_{W}x{H}@2x.png`（`2W×2H` 高清母版）与独立 HTML 源文件 `cover/cover_{W}x{H}.html`；
- `cover/qa/thumb_{W}x{H}_400w.png`（`400px` 宽缩略图，供三问视觉验收）；
- `cover/cover-report.json`（`scripts/render-cover.py --output` 保存的确定性渲染与 DOM 机器自检报告）；
- `cover/cover-summary.md`（钩子、重要数字、所截关键帧来源与 `400px` 缩略图三问验收记录）。

## 完成判据

- `pipeline-status` 校验通过（Phase 11 不再是 `next_phase`）：
- `cover/cover-report.json` 存在、JSON 可解析、`verdict == "pass"`，`sizes` 覆盖全部要求尺寸（无 `cover_requests` 限定时须包含 `1080x1440`、`1440x1080`、`1920x1080`），且每个尺寸对应的 `.html`、`1× .png`、`@2x.png` 与 `qa/thumb_*_400w.png` 均非空存在；
- `cover/cover-summary.md` 存在且非空；
- 通过下方 **11.3 主 agent 校验**（事实与数字口径核实、固定主持人位与 `400px` 缩略图可读性合格）。

## 执行后自检

- **事实与关键帧核对**：对照 `cover/cover-summary.md`、`research-brief.md` 与 `script.txt`，确认两行钩子与 `1–3` 个重要数字均有据可查、无未核实数据或空洞极限词，主体素材确实取自视频前 15 秒及全片核心场景的关键帧（或对应 catalog 高清原图）且已裁净播放态保留区。
- **主题一致与 `400px` 缩略图复核**：抽查 `cover/qa/thumb_*_400w.png`，确认三套尺寸延续 `composition/design.json` 主题配色与本地字体、无顶部信息条或字幕条残留、招手主持人位于固定槽位无遮挡碰撞，且缩到 `400px` 宽时 3 秒可读出钩子、主体占 `45%–65%`、视觉块 ≤ 5。

## 下一步

无——这是最后一个 phase。将最终成片（启用 BGM 时为 `composition/renders/final_with_bgm.mp4`，`bgm = false` 时为 `composition/renders/final.mp4`）、`qa/` 下的 contact sheet，以及 `cover/` 下的多尺寸成品封面与说明一并交给用户过目。

## 护栏

- **禁用图像生成模型写字或直出带字封面。** 封面一律由 HTML+CSS 排版、复用 `composition/assets/fonts/` 本地字体并通过 `scripts/render-cover.py` 在系统 Chrome 确定性截图产出。
- **全部选帧裁剪、HTML 排版、机器自检与缩略图测试委派给 coding agent 完成**，主 agent 只准备 handoff、派发并验收，禁手写或修补 `cover/*.html`。
- **每套尺寸单独一份固定像素 HTML，招手主持人锁定各尺寸固定槽位**，禁缩放同一份 HTML 换尺寸、禁用 `vw` / `vh`、禁改动上游 `script.txt` / 配音 / 成片视频。

---

**主 agent 不读委派包里的基础指令**（`references/delegation/cover/base-instructions.md` 只给被委派的 cover agent 读）。

#### 11.0 — 确认封面约束与派发前置条件

- 主 agent 核对 `inputs.json` 的可选 `cover_requests`（新提出的尺寸或封面重点要求先按 `references/pipeline-control.md` 写入 `cover_requests` 再生成 handoff）。
- 仅修改封面文案、构图或尺寸时，只登记 `--redo 11-cover`，不重跑 Phase 8 渲染、Phase 9 成片 QA 或 Phase 10 BGM 混音。

#### 11.1 — 物化委派包与生成 handoff

```bash
source .venv/bin/activate && python3 scripts/prepare-handoff.py {work_dir}/{topic_name} cover
```

脚本将委派包（`conventions.md` + `cover/`）物化到工作区（已有副本不覆盖，更新规则传 `--refresh`），并生成绝对路径的 `cover-handoff.md`。用户请求了阶段级模型（`inputs.json.delegation.cover.model`）时，先按 `references/delegation/conventions.md` 经目标 CLI 解析出支持看图的原生标识并传 `--resolved-model`。

#### 11.2 — 委派 cover agent

按 `prepare-handoff.py` 输出 JSON 的 `coding_agent` / `coding_model` 原样派发单句 `dispatch_prompt`（见 `references/delegation/conventions.md`）。

子 agent 自行读取 handoff 与工作区副本：定下两行核心钩子、`1–3` 个重要数字与统一主题配色；从 `final.mp4` 前 15 秒及全片核心场景截取 `1–2` 帧关键画面并用 Pillow 裁净写入 `cover/assets/`，拷入 `presenter-wave.png`；逐尺寸编写独立 HTML 并挂载固定槽位的招手主持人；运行 `scripts/render-cover.py` 清零全部 `findings`（`verdict == "pass"`）；对 `cover/qa/thumb_*_400w.png` 完成 `400px` 缩略图三问验收并写出 `cover/cover-summary.md`。

#### 11.3 — 主 agent 校验与最终交付

1. **状态脚本验收**：运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}`。若 `next_phase` 仍为 Phase 11（`missing` / `corrupt` 看 `problems`，`redo` 看 `redo_reason`），原样交回 cover agent 修复，修完 `--finish 11-cover` 后重验。
2. **内容与缩略图复核**：阅读 `cover/cover-summary.md` 并抽查 `cover/qa/thumb_*_400w.png`，确认钩子与 `1–3` 个重要数字忠实于 `research-brief.md`、关键帧选取贴切、各尺寸在 `400px` 缩略图上清晰易读且无遮挡裁切。不合格项指明原因交回 cover agent 重做。
3. **统一最终交付**：全部通过（`next_phase` 为 `null`）后，向用户交付：
   - 最终视频成片（`final_with_bgm.mp4` 或 `final.mp4`）与 `qa/` contact sheet（若 `qa/qa-report.json` 的 `verdict` 为 `handed_off`，一并附上未收敛 findings 供用户定夺）；
   - `cover/` 下各尺寸成品 `cover_{W}x{H}.png`、对应 `@2x.png`、HTML 源文件及 `cover/cover-summary.md` 摘要；
   - 若工作区存在 `search-notes.md`，按 `references/phases/10-mix.md`「10.2 交付时说明素材限制」一并说明受限来源与补抓入口。
