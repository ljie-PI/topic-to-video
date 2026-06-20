# Composition Stage Protocol

This file defines Phase 8.3-8.7 execution protocol for HyperFrames composition: pre-render self-audit, render requirements, sanity check, post-render Visual QA, QA report, feedback loop, and rule coverage matrix.

`references/composition-rules.md` remains the hard-constraint source. This protocol explains how those rules are checked and enforced during Phase 8.

## Stage Protocols

### Phase 8.3 — Pre-render Self-Audit Rules

首次 HTML-to-video render 前，sub-agent 必须完成 static / layout self-audit，并把结果写入 `composition/DESIGN.md`。失败项先修复并重跑 self-audit；只有 Phase 8.3 pass 后，才能进入 Phase 8.4 的 `hyperframes lint` / `hyperframes inspect` 和 render。

执行方式：

1. **Source pass**：读取 `composition/index.html`、CSS / JS、`composition-handoff.md`、`references/composition-rules.md`、`references/composition-stage-protocol.md`、`material-catalog.json`、`scene-material-suggestions.json`、`scene-text-plan.json`（如存在）、`transcribe/transcript.json` 和 `transcribe/subtitle-units.json`，建立 scene inventory，并扫描 forbidden patterns。
2. **Peak-state pass**：对每个 scene 选择一个或多个 peak-state 时间点（所有非字幕元素应可见、主要 text beat 已出现、退出动画未开始），用 HyperFrames / 浏览器可 seek 的预览能力或等价 DOM inspection 打开 `composition/index.html`，seek 到这些时间点。
3. **Geometry measurement**：在每个 peak state 读取 scene root、素材、文本、callout、decor、全局字幕容器的 bounding boxes，并计算 viewport、内容区、字幕安全区。
4. **Rule checks**：用几何数据检查元素溢出、重叠、前景压素材、素材占比、内容区使用率、alignment、margin / padding / gap、素材容器比例 / 露底、字幕安全区侵入和字幕框尺寸；若存在 `scene-text-plan.json`，还必须检查 primary visual text unit 是否实现、结构型 role 是否被合理视觉化、文本是否位于素材外置信息区、轻量浮层或分时轮换区，并按 `visual_role` 和输出朝向检查最终布局是否使用对应的 orientation-specific treatment；portrait / vertical 输出中不得把横屏 horizontal flow、side rail 或 multi-column grid 直接套用到结构型 unit。对 `media_first` / `video_first` 检查主媒体是否被不必要压小；对 `media_continuation` 检查相邻 scene 视觉锚点是否稳定；对 `viewport_reveal` 检查 start / mid / end 可见区域。
5. **Fix loop**：任一检查失败时，sub-agent 必须修改 layout / CSS / DOM / 动画初始态并重新跑 8.3，不得靠隐藏元素、延后显示或动画错开来掩盖 peak-state layout 问题。
6. **Audit output**：把每个 scene 的检查摘要、失败项和修复记录写入 `composition/DESIGN.md`；不能只写 “checked” / “pass”。

`composition/DESIGN.md` 至少记录：

1. **Reference Read Check**：确认已读取 `composition-handoff.md`、`references/composition-rules.md`、`references/composition-stage-protocol.md` 和 handoff 指定的 `references/design-<theme>.md`（如有）。
2. **Scene Layout Inventory**：覆盖每个 scene，满足 R9，并记录每个 scene 的 `visual_role`、输出朝向、采用的 orientation-specific layout treatment，以及未采用横屏排列的原因（portrait / vertical 时）。
3. **Peak-state / Scene Visual Audit**：覆盖每个 scene，满足 R10，并记录 viewport / 内容区 / 字幕安全区边界、主要元素 bounding boxes、元素是否溢出 / 截断 / 重叠、前景文本 / caption / tag / callout 是否压素材、内容区使用率、素材主体占比、标题 / 文本块 / 素材 / callout alignment、margin / padding / gap 是否一致、素材容器是否紧贴素材、字幕安全区是否只被全局字幕条使用；若 scene 有素材，记录 `layout_role`、aspect ratio、`ratio_bucket`、`focal_region`（如有）、文本信息区相对素材的位置（侧栏 / 下方带 / 顶部 band / 周边块 / 轻量浮层 / 分时轮换）、以及为什么该角色适合当前输出朝向。
4. **Layout Fix Record**：记录每个失败项如何通过 layout 尺寸、位置、字号、信息密度、间距、拆 scene 或素材替换修复；不得只写“已修复”。
5. **Sentence-level timing plan**：覆盖 R19；多个非素材文本元素不得在 scene start 一次性全亮。若存在 `scene-text-plan.json`，记录每个 `primary` visual text unit 的实现情况；未实现 / 降级的 unit 必须有原因。
6. **Forbidden pattern scan**：扫描缺失 `transcribe/subtitle-units.json`、字幕直接使用 raw ASR text、固定宽字幕框、字幕 `width:100%` / 大 `min-width`、横屏字幕多行 / 竖屏字幕超过两行、字幕脱离安全区、安全区为不会出现的额外行数预留过大空间、前景元素侵入安全区、字幕切换偏离音频 > 0.2 秒、素材错比例容器、错误 `object-fit: cover` 裁切、`object-fit: contain` 暴露容器底色 / letterbox、普通素材 `width + max-height/height`、未标注 `viewport_reveal` 却使用 `overflow:hidden` 裁素材、素材可见框 / 底色 / padding / shadow / glow、catalog 素材跨 scene 复用（`media_continuation` 记录的连续同素材例外除外）、`no_match` 借用素材、前景覆盖素材关键区域、video overlay 长段落 / 整行遮罩 / 遮挡主体动作或 UI 关键区域、portrait / vertical 输出中直接复用横屏 horizontal flow / side rail / multi-column grid 导致文本窄列、过小字号、多次换行或结构节点不可读、`radial-gradient` spotlight / ambient orb / localized glow、廉价扫描线 / sweep，以及所有 entrance tween blanket `immediateRender:false`。若使用 `gsap.from()` 做入场动画，应保留默认 immediate render，或用 CSS 初始态兜底。
7. **Structured text-plan coverage**：若存在 `scene-text-plan.json`，逐 scene 核对 `visual_text_units`，记录每个 `unit_id` 的实现 / 降级 / 跳过状态、采用的 layout treatment、以及是否与素材分离；禁止把 `process_flow`、`architecture_diagram`、`network_graph`、`timeline`、`comparison_matrix` 等结构型 unit 简单退化成一整段普通文本，除非 `composition/DESIGN.md` 明确说明受素材尺寸、字幕安全区或 overlap 约束。
8. **Customized rules coverage**：逐条读取 `composition-handoff.md` 的 `User-derived Customized Rules`，记录每条如何被布局 / 动画 / QA 方案覆盖；冲突按 Scope and Required References 处理。

### Phase 8.4 — HTML-to-video Render Rules

- render 前必须先通过 Phase 8.3 self-audit。
- Phase 8.3 pass 后，必须运行 `hyperframes lint` 和 `hyperframes inspect`，且二者都无错误。
- render 必须使用 `--workers 1`。
- 迭代直到 `composition/renders/final.mp4` 存在，且固定产物齐全：`composition/index.html`、`composition/DESIGN.md`、`composition/renders/final.mp4`。

### Phase 8.5 — Sanity Check Rules

render 后，主 agent 对 `composition/renders/final.mp4` 做确定性 sanity-check：

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 \
  {work_dir}/{topic_name}/composition/renders/final.mp4
ls -la {work_dir}/{topic_name}/composition/renders/final.mp4
ffprobe -v error -select_streams a:0 -show_entries stream=codec_type -of csv=p=0 \
  {work_dir}/{topic_name}/composition/renders/final.mp4
```

预期：duration 接近目标解说时长，文件大小 > 1 MB，且包含一条音频流。异常时把症状反馈给 HyperFrames sub-agent；主 agent 不手工 patch HTML。

### Phase 8.6 — Post-Render Visual QA Rules

sanity-check 通过后，主 agent 对 final.mp4 做视觉 QA。

#### QA mode

- **首轮 = 全量审计**：全片抽帧；静帧 / 复用 / spot-check 全片跑，旁白对齐抽样。
- **重渲轮 = 限定范围审计**：昂贵 vision 检查只覆盖上一轮 `affected_scenes`；静帧 / 复用等无 vision 成本检查仍全片跑。若 `affected_scenes` 含 `global`，字幕相关检查恢复全片抽样。

#### Step 1 — 每秒抽帧

```bash
mkdir -p {work_dir}/{topic_name}/composition/qa-frames
ffmpeg -y -i {work_dir}/{topic_name}/composition/renders/final.mp4 \
  -vf fps=1 -q:v 2 \
  {work_dir}/{topic_name}/composition/qa-frames/frame_%04d.jpg
```

#### Step 2 — 静帧检测

用 ffmpeg scene 滤波或相邻抽帧 perceptual hash 检测连续静止。任意连续 >= 3 张 1fps 抽帧低变化（约 >= 2 秒）记为 `static_frame` finding，并用 `data-scene-start/end` 反查 `scene_id`。

#### Step 3 — 素材跨 scene 复用检测

按 `data-scene-id` 划分 scene，提取 `material_ref` 和 `material_refs` 对应的 catalog 素材 src。任一 catalog src 出现在多个 scene 时，先检查命中的 scene 是否属于同一个已声明的 continuation group：同一 `data-continuation-group`，group 起点与后续 `media_continuation` scene 的 `scene-material-suggestions.json` 均具有相同 `material_ref`，且后续 scene 的 `continuation_of` 指向 group 起点的 `scene_index`。若是，记为合法 continuation，不报 `reused_material`；若不是，记为 `reused_material` finding，并记录所有命中的 `scene_ids`。通用 UI 贴图 / 装饰纹理 / 蒙版等非 catalog 资源不计。

#### Step 4 — 旁白对齐检测

按 `transcribe/transcript.json` 的句子边界切分。首轮抽样 `M = max(8, scene 数)` 句，并保证每个 scene 至少覆盖 1 句；重渲轮只检查 affected scenes 中的句子。对每句覆盖帧调用 vision 检查画面是否表达旁白含义，`no` / `partial` 记为 `narration_mismatch` finding。

#### Step 5 — 静帧 spot-check

抽样 `N = max(5, ceil(total_seconds / 30))` 张帧。重渲轮只从 affected scenes 覆盖帧抽样，`global` 字幕问题除外。每帧检查：

1. 图片 / 视频清晰、关键信息完整，放大不超过原始短边 2x。
2. 元素不越界、不截断。
3. 同时显示的元素不重叠，前景元素不压素材关键区域；`video_first` 半透明文本框不得遮挡主体动作、UI 关键区域、人物脸部或 `focal_region`。
4. DOM 扁平、颜色对比度达标。
5. 字号比 <= 3，主标题不折行。
6. 内容区无 >10% 纯空白。
7. 字幕安全区无非字幕前景元素侵入。
8. 素材无 letterbox / pillarbox。
9. 无扫描线 / sweep / 进度条等廉价动效覆盖层。
10. 底部字幕位置稳定、水平居中、位于安全区内，文本来自 `transcribe/subtitle-units.json`，切换与音频偏移 <= 0.2 秒。
11. 横屏字幕单行；竖屏 / 竖向字幕最多两行、无第三行；遮罩 shrink-to-fit，无固定宽度 / 大 `min-width` / 整行遮罩；超出该朝向最大行数时拆分 calibrated units，不靠缩字号或多塞行。
12. 素材无可见 border / padding / 卡片底 / shadow / glow，且无容器露底 / letterbox。
13. 有素材 scene 的素材占内容区主体；`media_first` / `video_first` 主素材没有被标题、信息块或固定模板不必要地压小。
14. 多素材对比可读：`comparison_pair` 中每个素材尺寸足够；三个及以上素材未被硬塞成不可读小宫格，必要时使用 `comparison_sequence`。
15. `viewport_reveal` 的 start / mid / end 至少覆盖完整内容或关键区域；没有未标注的 accidental clipping。
16. `media_continuation` 中同一主素材稳定显示，scene 之间没有过长空档或突兀跳变。
17. layout 不像固定模板硬套，能体现素材横竖 / 方形 / 极端比例、图片 / 视频、输出朝向和 `visual_role` 差异；portrait / vertical 中结构型 unit 使用纵向、stacked、paged 或 timed treatment，而不是横向窄列。
18. 非素材文字没有大段提前出现，也没有 text beat 累积堆满屏幕。
19. 相邻 scene 有明确转场；图片素材有持续动效。
20. handoff customized rules 中可见规则已被覆盖。

失败项加入 `spot_check_fails`，每条 finding 必须带 `scene_id`；全局字幕容器问题记为 `global`。

#### Step 6 — 汇总 QA report

写到 `composition/qa-report.json`：

```json
{
  "static_frames": [
    {"scene_id": "s4", "start_s": 12, "end_s": 17, "duration_s": 5}
  ],
  "reused_materials": [
    {"src": "materials/example.png", "scene_ids": ["s3", "s7"]}
  ],
  "narration_mismatches": [
    {"scene_id": "s5", "sentence": "...", "frames": ["frame_0034.jpg"], "verdict": "partial", "reason": "..."}
  ],
  "spot_check_fails": [
    {"scene_id": "s8", "frame": "frame_0123.jpg", "issue": "字幕遮罩过宽", "detail": "..."}
  ],
  "affected_scenes": ["s3", "s4", "s5", "s7", "s8"],
  "verdict": "fail"
}
```

`affected_scenes` 为所有 finding 的 `scene_id` / `scene_ids` 去重后按时间排序；`global` 固定排在最后。四类 finding 都为空时 `verdict = "pass"`，并且 `affected_scenes` 为空。

同时追加 `composition/qa-history.md`，记录轮次、模式、finding 数量、affected scenes 和反馈给 sub-agent 的修复摘要。

### Phase 8.7 — QA Feedback Loop

维护 `round`（从 1 起）和 `prev_total_findings`（首轮初始化为 `+inf`）。

- `verdict == "pass"`：在 `qa-history.md` 末尾写人类可读总结，然后进入 Phase 9。
- `verdict == "fail"`：先判止损，再决定是否重渲。

止损条件：

1. `round >= 3`。
2. `round > 1` 且本轮 finding 总数 `>= prev_total_findings`。
3. 同一 `affected_scenes` 集合连续 2 次重渲仍 fail。

命中止损时停止，把 `qa-report.json` 和总结交还用户。未止损时，把 `qa-report.json` 与症状原文反馈给 HyperFrames sub-agent，并要求：

1. 先写 `composition/qa-fix-plan-round-<N>.md`，说明共因和修复策略。
2. 只修改 `affected_scenes` 中的 scene；未受影响 scene 的 DOM / CSS / 动画 / 时间区间保持不变。
3. `global` 只允许修改全局字幕容器等全局部件，不应连带重写各 scene。
4. 若必须重排整片时间轴，sub-agent 必须明确说明并升级为整片重渲。
5. 修复后 `round += 1`、更新 `prev_total_findings`，回到 Phase 8.5 + 8.6，直到 pass 或止损。

## Rule Coverage Matrix

| Rule | Authoring / source check | Pre-render check | Post-render QA / feedback |
| --- | --- | --- | --- |
| R1-R4 | 读取 handoff 指定输入；只使用本地音频、transcript、subtitle units、catalog 和 fonts | Reference Read Check | Phase 8.5 audio sanity-check；Phase 8.6 narration / material spot-check |
| R5-R6 | 为每个 scene 写稳定 data 属性；按 `scene-material-suggestions.json` 分配 `material_ref` / `material_refs`；`media_continuation` group 写 `data-continuation-group` / index | 检查 scene inventory、素材引用、`no_match` 处理、continuation group 是否显式声明且相邻 | 检测素材跨 scene 复用；声明过的 `media_continuation` group 作为合法例外；用 scene data 反查 finding |
| R7 | authoring 时控制 scene 时长、微 scene、合并 scene 和 text beat 刷新 | `DESIGN.md` 记录时长设计 | 每轮解析 `data-scene-start/end` |
| R8-R10 | 按 scene 旁白、text beats、`scene-text-plan.json` visual text units、素材尺寸 / 类型 / `layout_role` 选择 layout；多素材 scene 读取 `material_refs`；按 `visual_role × orientation` routing 选择 role-specific layout treatment；写 inventory、layout-role rationale 和 peak-state audit | Scene Visual Audit 覆盖 bounding boxes、内容区使用率、alignment、margin / padding / gap、overlap / overflow、visual text unit 实现状态、media-first/video-first 尺寸、comparison 可读性、media_continuation 稳定性、viewport_reveal start/mid/end、portrait / vertical 不硬套 landscape flow/grid/rail 和失败处理 | spot-check 构图、空白、溢出、重叠、素材比例、layout_role 是否合理、role-specific layout treatment 是否匹配输出朝向、结构型文本是否退化 |
| R11-R12 | 用 catalog 尺寸设置普通 wrapper aspect-ratio；素材填满容器且无可见框；仅 `viewport_reveal` 可用 scene-ratio reveal viewport + 内层原比例素材 | 扫描错比例容器、错误 object-fit、普通素材 `width + max-height/height`、未标注 reveal 的 overflow clipping、素材容器露底和可见框模式 | 抽帧检查裁切、变形、letterbox / pillarbox / 容器露底 / 素材框感 / intentional reveal 是否安全 |
| R13-R14 | 布局计算排除字幕安全区；使用单个全局字幕容器和 calibrated subtitle units；横屏单行、竖屏最多两行 | 检查安全区、字幕 CSS、按朝向的最大行数与行高、遮罩宽度、`subtitle-units.json` 来源、切换 timing 和非字幕元素侵入 | 抽帧检查字幕位置、行数、遮罩宽度、遮挡和 timing |
| R15-R17 | 确保素材占主体、清晰完整、media_first/video_first 最大化可视区域、video overlay 不遮挡关键区域、元素不越界不重叠、字号/对比度达标 | Scene Visual Audit 检查 media dominance、主媒体是否被压小、video overlay bounds / focal_region 避让、comparison 可读性、bounds、overlap、typography 和 contrast | spot-check 画面清晰度、放大比例、重叠、越界、字号、对比度、视频浮层遮挡和多素材可读性 |
| R18 | 为素材 / 文本 / callout 设计持续动效和转场；`media_continuation` group 内主媒体稳定，只让文本 / callout / 局部强调变化 | 扫描廉价覆盖层动效、缺失转场、continuation 内主媒体 full-scene fade / wipe / re-enter | 静帧检测和 spot-check 扫描线 / sweep / 图片持续 motion / 普通 scene transition / continuation 边界稳定性 |
| R19 | 文本元素绑定完整旁白句子；优先实现 `scene-text-plan.json` 的 primary units；入场有初始态 | 扫描 blanket `immediateRender:false`、text beat 累积和 primary unit 未实现 | 旁白对齐抽样 + spot-check 文本提前 / 累积 / 结构型文本降级 |
| R20 | 按 style hint / design file 实现风格；不使用禁用 glow 模式 | 扫描 glow / orb / spotlight 和内容区大块空白 | spot-check 空白、模板感和深色技术风漂移 |
| Customized rules | authoring 时逐条覆盖 handoff rules | `DESIGN.md` 记录每条覆盖方式 | 可见规则进入 spot-check / narration alignment |

新增或调整规则时，同步更新本表。
