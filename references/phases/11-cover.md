# Phase 11 — 生成封面（委派给 coding agent；可选，`inputs.json` 的 `cover = false` 时跳过）

本 phase 默认开启（`inputs.json` 的 `cover` 缺省或为 `true` 时进入）；仅当用户明确不要视频封面、在 `inputs.json` 写入 `cover = false` 时，`pipeline-status` 跳过本阶段。

## 输入

### 主 agent 准备时参考

- `inputs.json`：核对可选布尔开关 `cover`、可选列表 `cover_requests` 及可选 `delegation.cover`。主 agent 负责预取裁净 `cover/assets/` 关键画面，禁手写或修补封面 HTML。
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
- 通过下方 **11.3 主 agent 中心化渲染与验收**（事实与数字口径核实、固定主持人位与 `400px` 缩略图可读性合格）。

## 执行后自检

- **事实与关键帧核对**：对照 `cover/cover-summary.md`、`research-brief.md` 与 `script.txt`，确认两行钩子与 `1–3` 个重要数字均有据可查、无未核实数据或空洞极限词，主体素材确实取自视频前 15 秒及全片核心场景的关键帧（或对应 catalog 高清原图）且已裁净播放态保留区。
- **主题一致与 `400px` 缩略图复核**：抽查 `cover/qa/thumb_*_400w.png`，确认三套尺寸延续 `composition/design.json` 主题配色与本地字体、无顶部信息条或字幕条残留、招手主持人位于固定槽位无遮挡碰撞，且缩到 `400px` 宽时 3 秒可读出钩子、主体占 `45%–65%`、视觉块 ≤ 5。

## 下一步

无——这是最后一个 phase。将最终成片（启用 BGM 时为 `composition/renders/final_with_bgm.mp4`，`bgm = false` 时为 `composition/renders/final.mp4`）、`qa/` 下的 contact sheet，以及 `cover/` 下的多尺寸成品封面与说明一并交给用户过目。

## 护栏

- **禁用图像生成模型写字或直出带字封面。** 一律由 HTML+CSS 排版、复用 `composition/assets/fonts/` 本地字体并经 `scripts/render-cover.py` 确定性截图产出。
- **预取素材 + 单尺寸并行 + 中心化渲染验收**：主 agent 定共享口径并预取裁净 `cover/assets/`（禁手写或修补 `cover/*.html`）；子 agent 按单尺寸并行编写 `cover/cover_{W}x{H}.html`（传参考图须缩至 `≤ 640px` 宽）；渲染与缩略图验收由主 agent 执行。
- **每套尺寸独立固定像素 HTML，招手主持人锁定固定槽位**，禁缩放同一份 HTML 换尺寸、禁用 `vw` / `vh`、禁改动上游旁白 / 配音 / 视频。

---

**主 agent 不读 `references/delegation/cover/base-instructions.md`**。

#### 11.0 — 确认封面约束

- 核对 `inputs.json` 的可选 `cover_requests`（新要求先按 `references/pipeline-control.md` 写入再生成 handoff）；仅改封面只登记 `--redo 11-cover`，不重跑 Phase 8 / 9 / 10。

#### 11.1 — 预取封面素材并生成 handoff

1. **预取素材与定口径**：对照 `research-brief.md`、`script.txt`、`transcribe/timeline.json` 与 `composition/scene-config.json`，按时间坐标从 `composition/renders/final.mp4` 前 15 秒及核心场景截 `1–2` 帧（或取 `material-catalog.json` 原图），按 `regions` 用 Pillow 裁净保留区与黑边写入 `{work_dir}/{topic_name}/cover/assets/`，拷入 `modules/components/presenter/images/presenter-wave.png`，并定下共享两行钩子、`1–3` 个已核实数字与统一底色。
2. **物化委派包与生成 handoff**（请求了阶段模型时先按 `references/delegation/conventions.md` 解析并传 `--resolved-model`）：

```bash
source .venv/bin/activate && python3 scripts/prepare-handoff.py {work_dir}/{topic_name} cover
```

#### 11.2 — 按单尺寸并行委派 cover agent

按返回的 `coding_agent` / `coding_model` 与 `dispatch_prompt`，守 `references/delegation/conventions.md` 对每个目标尺寸各起一个 `--no-session` 子会话并行派发：给定唯一尺寸 `{W}x{H}`、`cover/assets/` 与共享钩子/数字口径，仅落盘 `cover/cover_{W}x{H}.html`（末批一并写 `cover/cover-summary.md`），不内嵌渲染或看图。

#### 11.3 — 主 agent 中心化渲染、验收与最终交付

1. **确定性渲染与缩略图验收**：运行 `cover-handoff.md` 中的 `scripts/render-cover.py {work_dir}/{topic_name}/cover --output {work_dir}/{topic_name}/cover/cover-report.json` 及 `scripts/vision-analyze.py`（核对 `cover/qa/thumb_*_400w.png` 三问）；不合格尺寸派单尺寸小批修复后重跑至 `verdict == "pass"`，确认 `cover/cover-summary.md` 完备。
2. **状态验收与最终交付**：运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}`（redo 时传 `--finish 11-cover`）确认 `next_phase` 为 `null` 后，交付成片（`final_with_bgm.mp4` 或 `final.mp4`）、`qa/` contact sheet（`handed_off` 附未收敛项）、`cover/` 各尺寸成品与 `@2x.png` / HTML / `cover-summary.md`，以及可选 `search-notes.md` 素材限制说明。
