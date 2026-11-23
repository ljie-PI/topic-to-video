# Phase 8 — composition（委派给 coding agent）

## 输入

### 主 agent 准备时参考

- `inputs.json`：核对全片固定的 `orientation` 与可选 `composition_requests`（脚本同时校验基础字段与可选 `delegation`）。主 agent 不预选 design、视觉 scene、模板或 layout。

### Composition agent 阅读与使用

- `voice_clone/narration.mp3`（Phase 7 配音，唯一音频来源）；
- `transcribe/timeline.json`（含 `total_s` / `paragraphs` 及可选 `scenes` / `cues` 秒数；本阶段只读不改）；
- `material-catalog.json`（catalog 适用时使用；含 `entries` 与论文模式 `required_material_refs`；图片 `local_path` 相对工作区 `harvest_page/`，视频只用相对工作区根的无音轨 `selected_clips[].clip_path`）；
- `clips/`（`selected_clips[].clip_path` 指向的无音轨视频片段）；
- `scene-plan.json`（叙事层场景规划，含 `scene_id`、`paragraphs`、`intent`、`content_plan` 及可选 `cues` / `material_candidates`，供视觉切分与演绎参考）；
- `script.txt`（显示稿，字幕、屏幕文字与 cue 的唯一文本来源，禁止修改）；
- `inputs.json`（读取 `orientation` 与带作用范围的 `composition_requests`）；
- `composition-handoff.md` 及物化到工作区的委派包与 `modules/` 副本（字体由子 agent 选定 design 后安装）。

### 仅供工具读取

- `transcribe/transcript.json`（本轮词级时间戳 transcript）；
- `narration.txt` 与 `narration-offsets.json`（朗读稿与偏移表）。

这三份文件只传给字幕 / cue 对齐命令，子 agent 正常流程不阅读全文（仅在工具报错需诊断时按需查看局部片段），直接消费生成的 `composition/assets/subtitle-units.json` 与 cue 时间。

## 输出

- `composition/design.json`（全片 design 机器契约，规则见 `modules/designs/designs.md`）；
- `composition/scene-config.json`（最终视觉场景机器配置 `{version: 1, canvas, total_s, scenes}`，含完整落盘的 `regions` / `caption`，全片秒）；
- `composition/assets/subtitle-units.json`（按各视觉 scene 的 `caption` 规格生成的字幕单元；保留已有用户编辑）；
- `composition/storyboard.md`；
- `composition/index.html`；
- `composition/compositions/`；
- `composition/check-composition.json`（`check-composition.py --output` 保存的报告）；
- `composition/renders/final.mp4`。

## 完成判据

- `pipeline-status` 校验通过（Phase 8 不再是 `next_phase`）：
- `composition/design.json` 通过公共接口校验（默认用注册 preset，仅 `composition_requests` 要求库外风格时允许 `custom`，tokens 与字号下限合法）；
- `composition/scene-config.json` 通过公共接口校验（画布匹配 `orientation`、`scene_id` 唯一、`[begin_s, end_s)` 有序不重叠覆盖 `[0, total_s]`、`source_scene_ids` 有效、`regions` 几何与 `caption` 合法、声明的模板存在）；
- `composition/assets/subtitle-units.json` 的 `units` 非空且每条具备正时长（`end_s > begin_s`），`composition/storyboard.md` 非空，`composition/index.html` 存在，`composition/compositions/` 非空；
- `composition/check-composition.json` 的 `verdict == "pass"` 且 `scenes_checked` 覆盖当前每个视觉 scene 及其 layout（改过 `scene-config` 或画面须重跑检查并重新渲染）；
- `composition/renders/final.mp4` 存在且非空；
- 通过下方 **8.3 主 agent 校验**（`npx hyperframes check` 无错、storyboard 记录及素材 / 动画演绎合规）。

## 执行后自检

- 渲染前：`check-composition`（默认每场景 8 点密集采样）的阻塞 `findings`（含越界、保留区侵入、HTML 文字裁剪/溢出、大面板文字逃逸 `panel_escape`、最小字号、字幕一致性与非零时长等）已全部清零，非阻塞质量 `warnings`（含超宽 SVG 英文/代码行 `long_svg_text_line`、缩略媒体、缩放致糊、元素重叠/遮挡、跨区文案复读、素材复用等）已逐条修复或在 `storyboard.md` 说明设计意图。
- 渲染后：抽看 1–2 个关键 scene，确认素材宽高比正确、字幕未溢出、音画同步、未违规跨场复用素材、无素材场景已用动态图示演绎 `content_plan`（全面成片检查归 Phase 9）。
- 场景与旁白错位或素材本身不符属上游问题，按 `references/pipeline-control.md` 回退对应阶段，禁只改 HTML 掩盖。

## 下一步

Phase 9（成片检查）：运行 `check-render.py` + `make-contact-sheet.py` + 按 `qa_level` 的 vision 检查（修复轮最多 2 轮），随后进入可选的 Phase 10 混入 BGM 与 Phase 11 生成多尺寸视频封面。

## 护栏

- **字体由 composition agent 选定 design 后通过脚本安装到 `composition/assets/fonts/`**，写入 `composition/design.json` 并引入字体 CSS，禁用系统字体，主 agent 不介入字体与 HTML 编写。
- **字幕默认脚本生成，已有用户编辑不覆盖。** 仅改画面或重渲染时不重跑覆盖已编辑字幕；禁止跨不同版面切点切断英文词或数字。
- **全部画面设计与渲染委派给 coding agent**（仅加载 `hyperframes` 与 `hyperframes-cli` 两个外部 skill，见 `references/delegation/conventions.md`），主 agent 禁手写或修补 `composition/index.html`。
- **单 agent 逐场景拆分子合成写盘，优先消费 catalog 元数据。** 各视觉场景拆成独立 `composition/compositions/<scene>.{html,mjs}` 逐个落盘，防单次拼装巨型 `index.html` 触发 `413` 上限；默认优先读取 `material-catalog.json` 的尺寸、语义与 `focal_region`，仅在元数据不足以确定裁剪边界时按需单张查看原图，禁批量打开 `harvest_page/` 全部原图触发多模态 `400` 上限。

---

**主 agent 不读委派包里的基础指令**（`references/delegation/composition/base-instructions.md` 只给被委派的 composition agent 读）。

#### 8.0 — 确认全片约束与派发前置条件

- 主 agent 只核对 `inputs.json` 的 `orientation` 与可选 `composition_requests`（新提出的画面要求先按 `references/pipeline-control.md` 写入 `composition_requests` 再生成 handoff）；全片 design、视觉切分与逐场景 template / layout 均由 composition agent 在本阶段产出。
- 修改 design、视觉 scenes 或 layout 只登记 `--redo 8-composition` 及受影响的 Phase 9 / 10 / 11 重做，不重建 Phase 7 音频、transcript 与时间轴。

#### 8.1 — 物化委派包与 modules

```bash
source .venv/bin/activate && python3 scripts/prepare-handoff.py {work_dir}/{topic_name} composition
```

脚本将委派包（`conventions.md` + `composition/`）与整个 `modules/` 物化到工作区（已有副本不覆盖，更新规则传 `--refresh`），并生成绝对路径的 `composition-handoff.md`（含 Inputs、Outputs 命令、按叠加顺序排列的 Required References、可选参考 `patterns/` 与 `transitions/`、以及带作用范围的 Additional Instructions；返回 JSON 的 `fonts` 为 `null`）。

#### 8.2 — 委派 composition agent

按 `prepare-handoff.py` 输出 JSON 的 `coding_agent` / `coding_model` 原样派发单句 `dispatch_prompt`（见 `references/delegation/conventions.md`）。

子 agent 自行读取 handoff 与工作区副本：选定 design、初始化工程、安装字体并写 `composition/design.json`；按「用户要求 → 特别匹配模块 → 即时生成」定出视觉切分与逐场景方案，写出 `composition/scene-config.json`；运行 `align-narration.py --mode subtitles --scene-config ... --narration-audio ...` 生成字幕单元；读取实际采用模块的具体 `.md` 文档（禁只看源码猜参数），编写带开头「组件与转场使用表」的 `storyboard.md`、逐场景子合成代码，完成渲染前自查并渲染 `final.mp4`。

#### 8.3 — 主 agent 校验

1. **素材与演绎抽查**（catalog 适用时含素材核对）：
   - 论文模式 `required_material_refs` 关键图 / 表在 storyboard 覆盖表与实际画面中全部出现（禁以“选为候选”冒充已上屏）；
   - 符合场景内容的通用素材已优先考虑采用；真实素材遵守单场景分配（非技术深讲未跨场重复；同一张技术图深入讲解已合并延长场景，或在相邻连续场景间保持无过场衔接并推进局部 zoom 焦点）；
   - 无真实素材的视觉场景均按 `SVG → WebGL → Three.js → GSAP` 优先级或组合生动演绎 `content_plan`，未退化为纯排版文字卡片。
2. **状态脚本验收**：运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name}`。若 `next_phase` 仍为 Phase 8（`missing` / `corrupt` 看 `problems`，`redo` 看 `redo_reason`），原样交回 composition agent 限定范围修复，修完 `--finish` 后重验。
3. **补充项复核**：确认子 agent 报告 `npx hyperframes check` 无错误，且 `storyboard.md` 逐场景完整记录了 template / layout 方案与理由、content 区域、素材分配 / 动画演绎方案及实际借用的模块 `.md` 路径。全部通过后进入 Phase 9。
