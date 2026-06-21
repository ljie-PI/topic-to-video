# Composition Stage Protocol

本文件定义 Phase 8.3-8.7 的 HyperFrames composition 执行协议：预渲染自检、渲染要求、sanity check、渲染后 Visual QA、QA report、feedback loop 和 rule coverage matrix。

`references/composition-rules.md` 是硬约束来源。

## Stage Protocols

### Phase 8.3 — Pre-render Self-Audit Rules

首次 HTML-to-video render 前，sub-agent 必须完成 static / layout self-audit，并把结果写入 `composition/DESIGN.md`。失败项先修复并重跑 self-audit；只有 Phase 8.3 pass 后，才能进入 Phase 8.4 的 `hyperframes lint` / `hyperframes inspect` 和 render。

执行方式：

1. **Source pass**：读取 `composition/index.html`、CSS / JS、`composition-handoff.md`、`references/composition-rules.md`、`references/composition-stage-protocol.md`、`material-catalog.json`、`scene-material-suggestions.json`（如存在）、`scene-text-plan.json`（如存在）、`transcribe/transcript.json` 和 `transcribe/subtitle-units.json`，建立 scene inventory，并扫描 forbidden patterns。
2. **Peak-state pass**：对每个 scene 选择一个或多个 peak-state 时间点（所有非字幕元素应可见、主要 text beat 已出现、退出动画未开始），用 HyperFrames / 浏览器可 seek 的预览能力或等价 DOM inspection 打开 `composition/index.html`，seek 到这些时间点。
3. **Geometry measurement**：在每个 peak state 读取 scene root、素材、文本、callout、decor、全局字幕容器的 bounding boxes，并计算 viewport、内容区、字幕安全区；对大型容器还要记录内部子元素 union box、container occupancy ratio、主要元素组视觉中心相对内容区中心的偏移；对每个主要内容列 / 区域（含无边框列）记录内容 bounding box、横向 / 纵向 occupancy、左右 / 上下外侧边距，以及配对列 / 分栏之间的外侧边距差；对主媒体记录 source width / height、rendered width / height、scale factor、占内容区高度比例和面积比例；对主要文本记录 font size、line count 和每行字符 / token 分布。
4. **Rule checks**：用几何数据检查元素溢出、重叠、前景压素材、素材占比、内容区使用率、alignment、margin / padding / gap、素材容器比例 / 露底、字幕安全区侵入和字幕框尺寸；检查素材 aspect ratio 与输出 orientation 是否冲突，若冲突必须记录 tall media column、wide media slab、band、viewport reveal、stacked text 等 cross-aspect treatment；若存在 `scene-text-plan.json`，还必须检查 primary visual text unit 是否实现、结构型 role 是否被合理视觉化、文本是否位于素材外置信息区、轻量浮层或分时轮换区，并按 `visual_role` 和输出朝向检查最终布局是否使用对应的 orientation-specific treatment；portrait / vertical 输出中，多元素 / 结构型 role 不得直接套用横屏 horizontal flow、side rail 或 multi-column grid。对 `media_first` / `video_first` 检查主媒体是否被不必要压小、scale factor 是否在 0.8x-1.5x、主媒体高度 / 面积是否足够；对 `media_continuation` 检查相邻 scene 视觉锚点是否稳定；对 `viewport_reveal` 检查 start / mid / end 可见区域；检查每个主要内容列 / 区域的 occupancy 与外侧边距对称：任一主列内容横向 occupancy < 60% 或纵向 < 55%，或配对列 / 分栏外侧边距明显不对称时，判为 under-utilized，必须重排 / 收窄 / 补内容，hero / quote / title-card 留白例外必须记录；对标题和主要文本检查是否低于文本类型字号下限、是否存在 orphan line / widow word。
5. **Fix loop**：任一检查失败时，sub-agent 必须修改 layout / CSS / DOM / 动画初始态并重新跑 8.3，不得靠隐藏元素、延后显示或动画错开来掩盖 peak-state layout 问题。
6. **Audit output**：把每个 scene 的检查摘要、失败项和修复记录写入 `composition/DESIGN.md`；不能只写 “checked” / “pass”。

`composition/DESIGN.md` 至少记录：

1. **Reference Read Check**：确认已读取 `composition-handoff.md`、`references/composition-rules.md`、`references/composition-stage-protocol.md` 和 handoff 指定的 `references/design-<theme>.md`（如有）。
2. **Scene Layout Inventory**：覆盖每个 scene，满足 R20，并记录每个 scene 的 `layout_role`、所有 `visual_role`、`domain_hint` / `template_hint`（如有）、table / chart shape（如适用）、输出朝向、采用的 orientation-specific layout treatment，以及未采用横屏排列的原因（portrait / vertical 时）；若忽略 `template_hint` 或将 `data_table` 转 chart treatment，记录原因。
3. **Peak-state / Scene Visual Audit**：覆盖每个 scene，满足 R21。记录 viewport / 内容区 / 字幕安全区边界、subtitle safe area 高度、subtitle box 高度、内容区高度、主要元素 bounding boxes、overflow / truncation / overlap、foreground-on-material、内容区使用率、素材主体占比；主媒体 source / rendered width / height、scale factor（0.8x-1.5x；例外记录）、内容区高度 / 面积占比；标题 / 文本块 / 素材 / callout alignment、margin / padding / gap、素材容器贴合、字幕安全区占用。素材 scene 另记 `layout_role`、aspect ratio、`ratio_bucket`、`focal_region`、output orientation、cross-aspect treatment、最终显示尺寸、空白控制、文本信息区位置。大型容器另记 container bbox、内部子元素 union box、container occupancy ratio、主要元素组视觉中心偏移。主要内容列 / 区域另记内容 bbox、横纵 occupancy、外侧边距、配对列外边距差、单边贴边 / 外侧大空白。主要文本另记 font size、line count、每行字符 / token 分布、orphan line / widow word、字号下限。
4. **Layout Fix Record**：记录每个失败项如何通过 layout 尺寸、位置、字号、信息密度、间距、拆 scene 或素材替换修复；不得只写“已修复”。
5. **Sentence-level timing plan**：覆盖 R19；多个非素材文本元素不得在 scene start 一次性全亮。若存在 `scene-text-plan.json`，记录每个 `primary` visual text unit 的实现情况；未实现 / 降级的 unit 必须有原因。
6. **Forbidden pattern scan**：扫描缺失 `transcribe/subtitle-units.json`、字幕直接使用 raw ASR text、固定宽字幕框、字幕 `width:100%` / 大 `min-width`、横屏字幕多行 / 竖屏字幕超过两行、字幕脱离安全区、安全区为不会出现的额外行数预留过大空间、前景元素侵入安全区、字幕切换偏离音频 > 0.2 秒、素材错比例容器、错误 `object-fit: cover` 裁切、`object-fit: contain` 暴露容器底色 / letterbox、普通素材 `width + max-height/height`、未标注 `viewport_reveal` 却使用 `overflow:hidden` 裁素材、素材可见框 / 底色 / padding / shadow / glow、catalog 素材跨 scene 复用（`media_continuation` 记录的连续同素材例外除外）、`no_match` 借用素材、前景覆盖素材关键区域、video overlay 长段落 / 整行遮罩 / 遮挡主体动作或 UI 关键区域、portrait / vertical 输出中多元素 / 结构型 role 直接复用横屏 horizontal flow / side rail / multi-column grid 导致文本窄列、过小字号、多次换行或内容不可读、`radial-gradient` spotlight / ambient orb / localized glow、廉价扫描线 / sweep，以及所有 entrance tween blanket `immediateRender:false`。若使用 `gsap.from()` 做入场动画，应保留默认 immediate render，或用 CSS 初始态兜底。
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

用 ffmpeg scene 滤波或相邻抽帧 perceptual hash 检测内容驱动变化。仅当某 scene 在整个时长内既无素材动效、也无文字 / callout / 多元素逐个出现等内容驱动变化时，记为 `static_frame` finding，并用 `data-scene-start/end` 反查 `scene_id`。

#### Step 3 — 素材跨 scene 复用检测

按 `data-scene-id` 划分 scene，提取 `material_ref` 和 `material_refs` 对应的 catalog 素材 src。任一 catalog src 出现在多个 scene 时，先检查命中的 scene 是否属于同一个已声明的 continuation group：同一 `data-continuation-group`，scene data 中 `material_ref` 相同；`scene-material-suggestions.json` 如存在，还要校验 group 起点与后续 `media_continuation` scene 的 `material_ref` 相同，且后续 scene 的 `continuation_of` 指向 group 起点的 `scene_index`。若是，记为合法 continuation，不报 `reused_material`；若不是，记为 `reused_material` finding，并记录所有命中的 `scene_ids`。通用 UI 贴图 / 装饰纹理 / 蒙版等非 catalog 资源不计。

#### Step 4 — 旁白对齐检测

按 `transcribe/transcript.json` 的句子边界切分。首轮抽样 `M = max(8, scene 数)` 句，并保证每个 scene 至少覆盖 1 句；重渲轮只检查 affected scenes 中的句子。对每句覆盖帧调用 vision 检查画面是否表达旁白含义，`no` / `partial` 记为 `narration_mismatch` finding。

#### Step 5 — 静帧 spot-check

抽样 `N = max(5, ceil(total_seconds / 30))` 张帧。重渲轮只从 affected scenes 覆盖帧抽样，`global` 字幕问题除外。每帧检查：

1. 图片 / 视频清晰、关键信息完整，放大不超过原始短边 2x。
2. 元素不越界、不截断。
3. 同时显示的元素不重叠，前景元素不压素材关键区域；`video_first` 半透明文本框不得遮挡主体动作、UI 关键区域、人物脸部或 `focal_region`。
4. DOM 扁平、颜色对比度达标。
5. 字号比 <= 3。
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
17. layout 不像固定模板硬套，能体现素材横竖 / 方形 / 极端比例、图片 / 视频、输出朝向和 `visual_role` 差异；portrait / vertical 中多元素 / 结构型 role 使用纵向、stacked、paged 或 timed treatment，而不是横向窄列。
18. cross-aspect scene 中，横屏里的竖图 / 竖视频不得缩成小邮票或横向拉伸；竖屏里的横图 / 横视频不得缩成不可读细条或裁掉关键内容；无意义纯空白不得超过 R14 约束，空白应被信息区、轻量结构或 timed treatment 合理利用。
19. 横屏 `media_first` 中 16:9 / wide image 不得因固定 max-width 只占约半屏高度；若主媒体低于内容区高度约 60%，应放大媒体、减少文本、转 timed callout 或拆 scene。素材 rendered size 的 scale factor 应在 0.8x-1.5x；超出范围时必须作为 finding 或在 `composition/DESIGN.md` 中有明确例外说明。
20. 顶部 header / eyebrow 不得在承担主信息时过小或贴近 viewport 顶边；大型容器内部不得过空；主要元素在水平 / 垂直方向上不得明显不均；任一内容列 / 区域不得内容单边贴边、外侧留大空白或列内 occupancy 过低；若有大留白，必须属于明确的 hero / quote / title-card 设计。
21. 承担主信息的文本不得低于对应文本类型字号下限；标题 / callout 不得出现第二行 1-2 个字、孤立英文 token 或孤立标点的 orphan line / widow word。
22. 非素材文字没有大段提前出现，也没有 text beat 累积堆满屏幕；标题 / header / eyebrow 与 visual text unit 文本不重复。
23. 相邻 scene 有明确转场；每个 scene 通过素材动效或多元素随旁白逐个出现等内容驱动变化推进，无整段完全静止无变化的画面。
24. handoff customized rules 中可见规则已被覆盖。
25. 分栏布局（媒体列 + 信息列 / 左右分栏）两列垂直跨度大致对齐；信息列没有"上部堆内容、下部大留白"带；收尾 pills / tag 没有孤立钉在底边；单卡没有 1-2 行 + 四周大留白作为一列唯一内容。

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
| R5-R6 | 为每个 scene 写稳定 data 属性；按 `scene-material-suggestions.json`（如存在）分配 `material_ref` / `material_refs`；`media_continuation` group 写 `data-continuation-group` / index | 检查 scene inventory、素材引用、`no_match` 处理、continuation group 是否显式声明且相邻 | 检测素材跨 scene 复用；声明过的 `media_continuation` group 作为合法例外；用 scene data 反查 finding |
| R7 | authoring 时控制 scene 时长、微 scene、合并 scene 和 text beat 刷新 | `DESIGN.md` 记录时长设计 | 每轮解析 `data-scene-start/end` |
| R8 | 按 scene 旁白、text beats、`scene-text-plan.json` visual text units、素材尺寸 / 类型 / `layout_role` 选择 layout；多素材 scene 读取 `material_refs`；按 Layout routing reference 的 `visual_role × orientation` routing 选择 role-specific layout treatment | Scene Visual Audit 覆盖 bounding boxes、内容区使用率、alignment、margin / padding / gap、overlap / overflow、visual text unit 实现状态、cross-aspect treatment、media\\_continuation 稳定性、viewport\\_reveal start/mid/end、portrait / vertical 不硬套 landscape flow/grid/rail 和失败处理 | spot-check 构图、素材比例、layout\\_role 是否合理、role-specific layout treatment 是否匹配输出朝向、cross-aspect 可读性、结构型文本是否退化 |
| R9-R12 | 用 catalog 尺寸设置普通 wrapper aspect-ratio；素材填满容器且无可见框；仅 `viewport_reveal` 用 scene-ratio reveal viewport + 内层原比例素材；确保素材占主体、清晰完整、media\\_first/video\\_first 最大化可视区域、scale factor 0.8x-1.5x 或记录例外、video overlay 不遮挡关键区域；元素不越界不重叠 | 扫描错比例容器、错误 object-fit、普通素材 `width + max-height/height`、未标注 reveal 的 overflow clipping、素材容器露底；Scene Visual Audit 检查 media dominance、主媒体是否被压小、rendered / source scale factor、video overlay bounds / focal\\_region 避让、comparison 可读性、bounds、overlap | 抽帧检查裁切、变形、letterbox / pillarbox / 容器露底 / 素材框感、画面清晰度、放大比例、重叠、越界、视频浮层遮挡和多素材可读性 |
| R13-R14 | 分栏两列垂直对齐、信息列纵向填满、收尾元素不孤立钉底、稀疏内容增密或重排；按 style hint / design file 实现风格、不使用禁用 glow 模式、大型容器留白必须有明确设计目的 | Scene Visual Audit 检查分栏两列高度差、信息列下部留白带、单卡大留白；扫描 glow / orb / spotlight、内容区大块空白、container occupancy 过低和视觉重心偏移、列 / 区域 occupancy 过低或外侧边距不对称 | spot-check 分栏列高不齐、信息列下半空、pills 孤立钉底、空白、容器过空、元素分布不均、列单边贴边 / 外侧大空白、模板感和深色技术风漂移 |
| R15-R16 | 布局计算排除字幕安全区；使用单个全局字幕容器和 calibrated subtitle units；横屏单行、竖屏最多两行 | 检查安全区、字幕 CSS、按朝向的最大行数与行高、遮罩宽度、`subtitle-units.json` 来源、切换 timing 和非字幕元素侵入 | 抽帧检查字幕位置、行数、遮罩宽度、遮挡和 timing |
| R17 | 字号 / 对比度达标、标题无孤行、DOM 嵌套受限 | 检查 typography、font size、line count、orphan line / widow word、contrast | spot-check 字号、标题孤行、对比度 |
| R18 | 为素材 / 文本 / callout 设计持续动效和转场；`media_continuation` group 内主媒体稳定，只让文本 / callout / 局部强调变化 | 扫描廉价覆盖层动效、缺失转场、continuation 内主媒体 full-scene fade / wipe / re-enter | 静帧检测和 spot-check 扫描线 / sweep / 图片持续 motion / 普通 scene transition / continuation 边界稳定性 |
| R19 | 文本元素绑定完整旁白句子；优先实现 `scene-text-plan.json` 的 primary units；入场有初始态 | 扫描 blanket `immediateRender:false`、text beat 累积和 primary unit 未实现 | 旁白对齐抽样 + spot-check 文本提前 / 累积 / 结构型文本降级 |
| R20-R21 | 写 scene inventory、layout-role rationale、cross-aspect treatment 和 peak-state audit 到 `composition/DESIGN.md` | Scene Layout Inventory 满足 R20；Peak-state / Scene Visual Audit 满足 R21，含 container occupancy ratio、视觉重心偏移、列 / 区域 occupancy | 用 scene data 反查 finding；核对 `DESIGN.md` inventory / audit 完整性 |
| Customized rules | authoring 时逐条覆盖 handoff rules | `DESIGN.md` 记录每条覆盖方式 | 可见规则进入 spot-check / narration alignment |

新增或调整规则时，同步更新本表。
