# Composition Stage Protocol

`references/composition-rules.md` 是硬约束来源，`references/layout-routing.md` 是 R8 的布局候选软路由，`references/animation-routing.md` 是 R18 的动画候选与 runtime 软路由。规则阈值统一定义在 `references/composition-rules.md` 的 `Shared Thresholds`：`T-SUB` / `T-DUR` / `T-RATIO` / `T-REVEAL` / `T-FIT` / `T-MEDIA` / `T-GEO` / `T-FONT` / `T-SAFE` / `T-MOTION`。本文件引用标签，不重述规则阈值。

## Stage Protocols

### Phase 8.3 — Pre-render Self-Audit Rules

首次 HTML-to-video render 前，sub-agent 必须完成 static / layout self-audit，并把结果写入 `composition/DESIGN.md`。失败项先修复并重跑 self-audit；只有 Phase 8.3 pass 后，才能进入 Phase 8.4 的 `hyperframes lint` / `hyperframes inspect` 和 render。

执行方式：

1. **Source pass**：读取 `composition/index.html`、CSS / JS、`composition-handoff.md`、`references/composition-rules.md`、`references/layout-routing.md`、`references/animation-routing.md`、`references/composition-stage-protocol.md`、`narration.txt`、`material-catalog.json`、`scene-material-suggestions.json`（如存在）、`scene-text-plan.json`（如存在）、`transcribe/transcript.json` 和 `transcribe/subtitle-units.json`，建立 scene inventory，并扫描 forbidden patterns。layout routing 先读 authority / fallback definitions / input alignment / resolution order / global density and degradation，再核对每个 scene 命中的 material / layout role / orientation / visual role（如有）及最终 presentation / `cross_aspect_strategy` 行。
2. **Peak-state pass**：对每个 scene 选择一个或多个 peak-state 时间点（所有非字幕元素应可见、主要 text beat 已出现、退出动画未开始），用 HyperFrames / 浏览器可 seek 的预览能力或等价 DOM inspection 打开 `composition/index.html`，seek 到这些时间点。
3. **Geometry measurement**：在每个 peak state 读取 scene root、素材、文本、callout、decor、全局字幕容器的 bounding boxes，并计算 viewport、内容区、字幕安全区；对大型容器还要记录内部子元素 union box、container occupancy ratio、主要元素组视觉中心相对内容区中心的偏移；对每个主要内容列 / 区域（含无边框列）记录内容 bounding box、横向 / 纵向 occupancy、左右 / 上下外侧边距，以及配对列 / 分栏之间的外侧边距差；对主媒体记录 source width / height、rendered width / height、内容区 `CW` / `CH`、主素材 `MW` / `MH`、派生比值 `MW / CW`、`MH / CH`、scale factor、占内容区高度比例和面积比例；对主要文本记录 font size、line count 和每行字符 / token 分布。
4. **Deterministic geometry gate**：必须运行 `python3 scripts/measure-composition-layout.py {work_dir}/{topic_name}/composition --viewport <WxH> --output {work_dir}/{topic_name}/composition/layout-geometry-report.json`。缺 Chrome / playwright 时停止并报告，不得跳过或手算。脚本按 `T-GEO` / `T-RATIO` / `T-REVEAL` / `T-FIT` 和 scene data 判定布局。命中 `underfilled_content_area`、`center_clustered_layout`、`oversized_gutter`、`undersized_text`、`tight_text_gap`、`underfilled_container`、`uneven_vertical_distribution`、`undersized_media`、`tall_media_not_revealed`、`reveal_window_out_of_bounds`、`fit_below_threshold` 任一 finding 时，Phase 8.3 失败。
5. **Rule checks**：用几何数据检查元素溢出、重叠、前景压素材、素材占比、内容区使用率、alignment、margin / padding / gap、素材容器比例 / 露底、字幕安全区侵入和字幕框尺寸；先检查 `no_match: true` 是否与 `material_ref` / 非空 `material_refs` 并存、continuation metadata 是否完整合法，任一冲突都必须停止并反馈，不得 fallback；检查素材 aspect ratio 与输出 orientation 是否冲突，若冲突必须记录 `cross_aspect_strategy`: `full_fit` / `viewport_reveal` / `detail_callout` / `media_continuation` / `replace_material`，以及竖向素材列、wide media slab、band、`viewport_reveal`、上下文本区等跨比例呈现方式；若存在 `scene-text-plan.json`，还必须检查 primary visual text unit 是否实现、结构型 role 是否被合理视觉化、文本是否位于素材外置信息区、轻量浮层或分时轮换区，并按 `visual_role` 和输出朝向检查最终布局是否使用对应的按朝向布局呈现方式；portrait / vertical 输出中，多元素 / 结构型 role 不得直接套用横屏 horizontal flow、side rail 或 multi-column grid。catalog source figure / table / chart 必须保留来源图形、轴线、图例、caption、关键曲线和必要 rows / columns；“只保留 primary rows / columns / points”只允许用于 structured `data_table` / `chart` visual unit，catalog source 只能精简外置解释、reveal 遍历必要结构或拆 scene。对 `media_first` / `video_first` 检查主媒体是否被不必要压小、scale factor 是否在 `T-MEDIA` 范围、主媒体高度 / 面积是否足够；tall / ultra-tall 素材的 `full_fit` 只按 `T-FIT`，其余必须使用 key-region-aware `viewport_reveal`，且 start / mid / end 可见区域覆盖 catalog 记录的 `focal_region`、关键区域或避开 avoid-region；authoring 阶段基于 catalog 源尺寸的 fallback 预判必须在此用实测 `CW` / `CH` / `MW` / `MH` 复核，不满足时必须重新路由为 `viewport_reveal` / `detail_callout` / 替换素材；只有已存在完整合法 continuation metadata 时才可保持 `media_continuation`，几何失败不能创建该 role；对 `media_continuation` 检查上游 continuation metadata 完整、material 与 group 起点一致、相邻 scene 视觉锚点稳定；若 role 为 inferred，则还必须证明 metadata 已完整且只漏 `layout_role` 字段；对 `viewport_reveal` 检查 start / mid / end 可见区域；检查每个主要内容列 / 区域是否通过 `T-GEO` 的 occupancy 与外侧边距要求，配对列 / 分栏外侧边距不得明显不对称；hero / quote / title-card 留白必须通过 scene data exception 进入脚本；对标题和主要文本检查是否低于文本类型字号下限、是否存在 orphan line / widow word。另须执行 R18 motion semantic check：每个 scene 有明确 `semantic_intent`、`primary_subject`、`signature_mechanism`、narration trigger、transition / continuity 与 runtime 理由；存在 `visual_role` 时 effect 能表达该 role，未提供 role 时以 intent / subject / state change 为准；effect 必须服从 `layout_role`；无连续 generic motion repetition、无无目的 runtime 混用、无未注册 / autoplay / wall-clock 驱动的 render-critical motion。
6. **Fix loop**：任一检查失败时，sub-agent 必须修改 layout / CSS / DOM / 动画初始态并重新跑 8.3，不得靠隐藏元素、延后显示或动画错开来掩盖 peak-state layout 问题。
7. **Audit output**：把每个 scene 的检查摘要、失败项和修复记录写入 `composition/DESIGN.md`；不能只写 “checked” / “pass”。

`composition/DESIGN.md` 至少记录：

1. **Reference Read Check**：确认已读取 `composition-handoff.md`、`references/composition-rules.md`、`references/layout-routing.md` 的 authority / fallback definitions / input alignment / resolution order / global density and degradation 与当前 scenes 命中的 material / role / orientation / presentation sections、`references/animation-routing.md`、`references/composition-stage-protocol.md` 和 handoff 指定的 `references/design-<theme>.md`（如有）；并确认已按 R18 读取 HyperFrames 当前动画能力索引。
2. **Scene Layout Inventory**：覆盖每个 scene，满足 R20，并记录每个 scene 的 material condition、`layout_role` 及来源（explicit / inferred + fallback reason / catalog evidence）、所有实际存在的 `visual_role` 及来源、命中的 `layout-routing.md` sections / rows、`domain_hint` / `template_hint`（如有）、table / chart shape（如适用）、输出朝向、最终 layout presentation / `cross_aspect_strategy`，以及未采用横屏排列的原因（portrait / vertical 时）；没有 visual role 时记录按 `semantic_intent` / `primary_subject` 直接选 layout 的依据，不得虚构 role；若忽略 `template_hint`、改变 presentation 或将 `data_table` 转 chart，记录原因；inferred role 另记 conflict gate、authoring 预判与 Phase 8.3 实测复核结果。
3. **Peak-state / Scene Visual Audit**：覆盖每个 scene，满足 R21。记录 viewport / 内容区 / 字幕安全区边界、subtitle safe area 高度、subtitle box 高度、内容区 `CW` / `CH`、主要元素 bounding boxes、overflow / truncation / overlap、foreground-on-material、内容区使用率、素材主体占比；主媒体 source / rendered width / height、`MW` / `MH`、派生比值 `MW / CW`、`MH / CH`、scale factor、内容区高度 / 面积占比；标题 / 文本块 / 素材 / callout alignment、margin / padding / gap、素材容器贴合、字幕安全区占用。素材 scene 另记 `layout_role`、aspect ratio、`ratio_bucket`、`focal_region`、output orientation、`cross_aspect_strategy`、跨比例呈现方式、阈值判断、最终显示尺寸、空白控制、文本信息区位置。大型容器另记 container bbox、内部子元素 union box、container occupancy ratio、主要元素组视觉中心偏移。主要内容列 / 区域另记内容 bbox、横纵 occupancy、外侧边距、配对列外边距差、单边贴边 / 外侧大空白。主要文本另记 font size、line count、每行字符 / token 分布、orphan line / widow word、字号下限。
4. **Layout Fix Record**：记录每个失败项如何通过 layout 尺寸、位置、字号、信息密度、间距、拆 scene 或素材替换修复；不得只写“已修复”。
5. **Sentence-level timing plan**：覆盖 R19；多个非素材文本元素不得在 scene start 一次性全亮。若存在 `scene-text-plan.json`，记录每个 `primary` visual text unit 的实现情况；未实现 / 降级的 unit 必须有原因。
6. **Motion Plan Audit**：覆盖 R18；逐 scene 记录 `semantic_intent`、`primary_subject`、`sustained_motion_route`、`signature_mechanism`、supporting mechanisms、considered / selected effect 或 blueprint、runtime、narration triggers、transition / continuity strategy、proof times，以及未采用主要候选或手动指定 preference 时的理由。`proof_times` 使用 composition absolute seconds，命名覆盖 `entry`、一个或多个 `semantic_progression`、`peak` 和 `handoff`，不适用项写明原因。存在 `visual_role` 时检查 effect 是否表达该 role；没有 role 时按 intent / subject / state change 检查。另检查 effect 是否服从 `layout_role` / orientation / focal region、相邻 scene 是否无理由重复同一组合、runtime 是否 seek-safe，且 Lottie / Three.js / TypeGPU 等选择有真实资产或机制需求。对每个图片 scene / continuation group 核对规范化 `primary_motion_family`，按 R18 的 `T-MOTION` 定义计算 `total_images` 和各 family 次数，超出 `ceil(total_images / 5)` 即失败。
7. **Forbidden pattern scan**：扫描 `no_match: true` 与素材 assignment 并存、无完整 continuation metadata 却推导 `media_continuation`、catalog source figure / table / chart 被裁切 / 抽取 / 重画成 primary rows / points、缺失 `transcribe/subtitle-units.json`、字幕直接使用 raw ASR text、生成文本 / 字幕 / DOM 中出现网页链接或“链接放在下面”等链接引导、固定宽字幕框、字幕 `width:100%` / 大 `min-width`、字幕超过 `T-SAFE` 最大行数、字幕脱离安全区、安全区为不会出现的额外行数预留过大空间、前景元素侵入安全区、字幕切换偏离音频超过 `T-SUB`、素材错比例容器、错误 `object-fit: cover` 裁切、`object-fit: contain` 暴露容器底色 / letterbox、普通素材 `width + max-height/height`、未标注 `viewport_reveal` 却使用 `overflow:hidden` 裁素材、`tall` / `ultra-tall` 竖向素材 full_fit、cross-aspect full_fit 未通过 `T-FIT`、reveal 窗口尺寸超出 `T-REVEAL`、素材可见框 / 底色 / padding / shadow / glow、未声明 `media_continuation` 的 catalog 素材跨 scene 复用、`no_match` 借用素材、前景覆盖素材关键区域、video overlay 长段落 / 整行遮罩 / 遮挡主体动作或 UI 关键区域、portrait / vertical 输出中多元素 / 结构型 role 直接复用横屏 horizontal flow、side rail 或 multi-column grid 导致文本窄列、过小字号、多次换行或内容不可读、`radial-gradient` spotlight / ambient orb / localized glow、廉价扫描线 / sweep、连续 scene 无理由复用相同 fade + translate + Ken Burns 组合、idle drift / breathing / glow pulse 代替内容驱动变化、无资产 Lottie、无机制需求的 Three.js / TypeGPU、render-critical autoplay / wall-clock / unregistered runtime，以及所有 entrance tween blanket `immediateRender:false`。若使用 `gsap.from()` 做入场动画，应保留默认 immediate render，或用 CSS 初始态兜底。
8. **Structured text-plan coverage**：若存在 `scene-text-plan.json`，逐 scene 核对 `visual_text_units`，记录每个 `unit_id` 的实现 / 降级 / 跳过状态、采用的布局呈现方式、以及是否与素材分离；禁止把 `process_flow`、`architecture_diagram`、`network_graph`、`timeline`、`comparison_matrix` 等结构型 unit 简单退化成一整段普通文本，除非 `composition/DESIGN.md` 明确说明受素材尺寸、字幕安全区或 overlap 约束。
9. **Customized rules coverage**：逐条读取 `composition-handoff.md` 的 `User-derived Customized Rules`，记录每条如何被布局 / 动画 / QA 方案覆盖；冲突按 Scope and Required References 处理。

### Phase 8.4 — HTML-to-video Render Rules

- render 前必须先通过 Phase 8.3 self-audit：`composition/layout-geometry-report.json` 存在且 `verdict` 为 `pass`。
- Phase 8.3 pass 后，必须运行 `hyperframes lint` 和 `hyperframes inspect`，且二者都无错误。
- render 必须使用 `--workers 1`。
- 迭代直到 `composition/renders/final.mp4` 存在，且固定产物齐全：`composition/index.html`、`composition/DESIGN.md`、`composition/layout-geometry-report.json`、`composition/renders/final.mp4`。

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

#### Vision 工具与 VLM key 回退

QA 中所有 vision 检查（Step 4、Step 5）统一通过 `scripts/vision-analyze.py` 调用，按 `VLM_API_KEY` 分流：

- **Mode 1（显式 VLM）：** 设了 `VLM_API_KEY` + `VLM_BASE_URL` + `VLM_MODEL` → 脚本走 OpenAI 兼容调用，返回 `mode:"vlm"` + `analysis`。
- **Mode 2（主 agent 直接分析）：** 未设 `VLM_API_KEY` → 脚本返回 `mode:"delegate_to_agent"` 和帧路径，主 agent 用 `view` 工具直接看帧完成检查，产出同样格式的 finding。无 key 不阻断 QA。

#### Step 0 — DOM geometry QA

先运行确定性几何检查，输出写入 `composition/layout-geometry-report.json`：

```bash
python3 scripts/measure-composition-layout.py \
  {work_dir}/{topic_name}/composition \
  --viewport <WxH> \
  --output {work_dir}/{topic_name}/composition/layout-geometry-report.json
```

即使 Phase 8.3 已通过，Phase 8.6 仍独立运行本检查。

`layout-geometry-report.json` 中 `findings[]` 非空时，把这些 finding 原样合并到最终 `qa-report.json` 的 `layout_geometry_fails`。几何检查失败不跳过后续抽帧 / spot-check；QA 继续收集其它问题，最后统一反馈。

#### Step 1 — 每秒抽帧

```bash
mkdir -p {work_dir}/{topic_name}/composition/qa-frames
ffmpeg -y -i {work_dir}/{topic_name}/composition/renders/final.mp4 \
  -vf fps=1 -q:v 2 \
  {work_dir}/{topic_name}/composition/qa-frames/frame_%04d.jpg
```

#### Step 2 — 静帧检测

用 ffmpeg scene 滤波或相邻抽帧 perceptual hash 只检测 literal stillness。某 scene 在整个时长内无可见像素变化时，记为 `static_frame` finding，并用 `data-scene-start/end` 反查 `scene_id`。pHash 不能判断变化是否有语义，也不能区分 focal traversal 与 idle drift / breathing / glow pulse / 无目标 Ken Burns；这些由 Phase 8.3 source / motion-plan audit 和下方 Motion sequence spot-check 判定。

#### Step 3 — 素材跨 scene 复用检测

按 `data-scene-id` 划分 scene，提取 `material_ref` 和 `material_refs` 对应的 catalog 素材 src。任一 catalog src 出现在多个 scene 时，先检查命中的 scene 是否属于同一个已声明的 continuation group：同一 `data-continuation-group`，scene data 中 `material_ref` 相同；`scene-material-suggestions.json` 如存在，还要校验 group 起点与后续 `media_continuation` scene 的 `material_ref` 相同，且后续 scene 的 `continuation_of` 指向 group 起点的 `scene_index`。若是，记为合法 continuation，不报 `reused_material`；若不是，记为 `reused_material` finding，并记录所有命中的 `scene_ids`。通用 UI 贴图 / 装饰纹理 / 蒙版等非 catalog 资源不计。

#### Step 4 — 旁白对齐检测

按 `transcribe/transcript.json` 的句子边界切分。首轮抽样 `M = max(8, scene 数)` 句，并保证每个 scene 至少覆盖 1 句；重渲轮只检查 affected scenes 中的句子。对每句覆盖帧用 `scripts/vision-analyze.py` 检查画面是否表达旁白含义，`no` / `partial` 记为 `narration_mismatch` finding。

#### Step 5 — 静帧 spot-check

抽样 `N = max(5, ceil(total_seconds / 30))` 张帧。重渲轮只从 affected scenes 覆盖帧抽样，`global` 字幕问题除外。每帧用 `scripts/vision-analyze.py` 检查：

1. 图片 / 视频清晰、关键信息完整，scale factor 符合 `T-MEDIA`；catalog source figure / table / chart 的来源图形、轴线、图例、caption、关键曲线和必要 rows / columns 完整，未被当作 structured unit 裁切、抽取或重画。
2. 元素不越界、不截断。
3. 同时显示的元素不重叠，前景元素不压素材关键区域；`video_first` 半透明文本框不得遮挡主体动作、UI 关键区域、人物脸部或 `focal_region`。
4. DOM 扁平、颜色对比度达标。
5. 字号比符合 `T-FONT`。
6. 内容区无 >10% 纯空白。
7. 字幕安全区无非字幕前景元素侵入。
8. 素材无 letterbox / pillarbox。
9. 无扫描线 / sweep / 进度条等廉价动效覆盖层。
10. 底部字幕位置稳定、水平居中、位于安全区内，文本来自 `transcribe/subtitle-units.json`，切换与音频偏移不超过 `T-SUB`。
11. 横屏字幕单行；竖屏 / 竖向字幕最多两行、无第三行；遮罩 shrink-to-fit，无固定宽度 / 大 `min-width` / 整行遮罩；超出该朝向最大行数时拆分 calibrated units，不靠缩字号或多塞行。
12. 素材无可见 border / padding / 卡片底 / shadow / glow，且无容器露底 / letterbox。
13. 有素材 scene 的素材占内容区主体；`media_first` / `video_first` 主素材没有被标题、信息块或固定模板不必要地压小。
14. 多素材对比可读：`comparison_pair` 中每个素材尺寸足够；两个素材无法同屏可读时使用 `comparison_sequence` / 分时；三个及以上素材未被硬塞成不可读小宫格，必要时使用 `comparison_sequence`。
15. `viewport_reveal` 的 start / mid / end 必须覆盖 catalog 记录的 `focal_region`、关键区域或避开 avoid-region；没有未标注的 accidental clipping。若 reveal 放大了素材但错过重点区域，仍记为失败。
16. `media_continuation` 中同一主素材稳定显示，scene 之间没有过长空档或突兀跳变。
17. layout 不像固定模板硬套，能体现素材横竖 / 方形 / 极端比例、图片 / 视频、输出朝向和 `visual_role` 差异；portrait / vertical 中按 role 检查：流程 / 时间线 / 状态机为纵向节点链，表格 / 图表 / 榜单为分页、分时或主项高亮，列表 / 指标 / 功能项为纵向卡片或最多 2 列，架构 / 网络图为 focus window / primary path；不得横向窄列。
18. cross-aspect scene 中，横屏里的竖向素材不得缩成小邮票或横向拉伸；tall / ultra-tall 素材 `full_fit` 只按 `T-FIT`，其余必须使用 key-region-aware `viewport_reveal`；reveal 窗口尺寸须落在 `T-REVEAL`；竖屏里的横图 / 横视频不得缩成不可读细条或裁掉关键内容；无意义纯空白不得超过 R14 约束，空白应用于信息区、轻量结构、主项高亮、分页 / 分时条目或素材 reveal。
19. 横屏 `media_first` 中 16:9 / wide image 不得因固定 max-width 只占约半屏高度；主媒体高度下限与低于阈值必须改布局的条件见 `T-MEDIA`，应放大媒体、减少文本、转 timed callout 或拆 scene。素材 rendered size 的 scale factor 应在 `T-MEDIA` 范围；超出范围时必须作为 finding 并通过替换素材或调整布局修复。
20. 顶部 header / eyebrow 不得在承担主信息时过小或贴近 viewport 顶边；大型容器内部不得过空；主要元素在水平 / 垂直方向上不得明显不均；任一内容列 / 区域不得内容单边贴边、外侧留大空白或列内 occupancy 过低；竖向素材完整适配显示留出的 side panel 必须有信息填充且通过 `T-GEO` 的 column occupancy 检查。若有大留白，必须属于明确的 hero / quote / title-card 设计。
21. 承担主信息的文本不得低于对应文本类型字号下限；标题 / callout 不得出现第二行 1-2 个字、孤立英文 token 或孤立标点的 orphan line / widow word。
22. 非素材文字没有大段提前出现，也没有 text beat 累积堆满屏幕；标题 / header / eyebrow 与 visual text unit 文本不重复。
23. handoff customized rules 中可见规则已被覆盖。
24. 分栏布局（媒体列 + 信息列 / 左右分栏）两列垂直跨度大致对齐；信息列没有"上部堆内容、下部大留白"带；收尾 pills / tag 没有孤立钉在底边；单卡没有 1-2 行 + 四周大留白作为一列唯一内容。

失败项加入 `spot_check_fails`，每条 finding 必须带 `scene_id`；全局字幕容器问题记为 `global`。

#### Step 5a — Motion sequence spot-check

静帧不能证明 transition、scene-long progression、重复 choreography 或 seek-safe runtime。首轮必须按 `composition/DESIGN.md` 的 `proof_times` 为每个 scene 抽取 entry、一个或多个 semantic progression、peak 和 handoff 的有序 frame sequence；每个普通 scene boundary 另抽取 cut 前 / cut 中 / cut后的连续帧或短 clip。重渲轮只检查 affected scenes 及其相邻 boundary。

使用固定目录与命名，避免实现者自拟 QA 产物：proof frame 写到 `composition/qa-motion/<scene_id>/<state>-<time_ms>.jpg`，其中 `<state>` 为 `entry` / `semantic_progression-<N>` / `peak` / `handoff`，`<time_ms>` 为 DESIGN 中 absolute seconds × 1000 取整；boundary clip 写到 `composition/qa-motion/boundary-<from_scene_id>-<to_scene_id>-<cut_time_ms>.mp4`。逐个 proof time 执行：

```bash
mkdir -p {work_dir}/{topic_name}/composition/qa-motion/<scene_id>
ffmpeg -y -ss <absolute_seconds> \
  -i {work_dir}/{topic_name}/composition/renders/final.mp4 \
  -frames:v 1 -q:v 2 \
  {work_dir}/{topic_name}/composition/qa-motion/<scene_id>/<state>-<time_ms>.jpg
```

对每个普通 boundary，以 `start = max(0, cut_time - 0.35)`、`duration = 0.70` 抽取固定窗口；需要逐帧判断时，再对该 clip 使用 composition fps 抽帧：

```bash
ffmpeg -y -ss <start_seconds> \
  -i {work_dir}/{topic_name}/composition/renders/final.mp4 \
  -t 0.70 -an -c:v libx264 -pix_fmt yuv420p \
  {work_dir}/{topic_name}/composition/qa-motion/boundary-<from>-<to>-<cut_time_ms>.mp4
```

按 `entry → semantic_progression-* → peak → handoff` 和 boundary 时间顺序检查这些 frame / clip；不得用 1fps 全片抽帧替代 proof times，因为短 transition 可能完全落在两个秒点之间。

结合 frame sequence、boundary clip、`composition/index.html` / CSS / JS source、timeline / adapter registration 和本地 animation assets 检查：

1. scene 的 staged reveal、camera intent、UI / data state change、focal traversal、annotation progression 或其他主体行为确实在 narration trigger 推进，而不是只有 idle drift / breathing / glow pulse / 无目标 Ken Burns。
2. 存在 `visual_role` 时动画表达该 role；没有 role 时动画表达 `semantic_intent`、`primary_subject` 和要证明的 state change。流程、图表、架构、榜单等结构型 role 不得统一退化成普通文字 fade。
3. 动画服从 `layout_role`、orientation、素材比例和 `focal_region`；`viewport_reveal` 到达关键区域，`media_continuation` 在 boundary 前后保持主媒体稳定并更新解释层。
4. 相邻 scene 有明确 transition / motion handoff；连续 scene 没有无理由重复完全相同的 `entry + information reveal + transition` 组合。
5. 根据 source 检查 Lottie / Three.js / TypeGPU 等 runtime 有真实资产或机制需求；render-critical motion 同步注册、有限、可 seek，无 wall-clock autoplay / unregistered loop。该项是 source/runtime audit，不从单帧视觉猜测。
6. `proof_times` 命名状态在对应帧中可见，最终状态可读且没有 reset / black tail；图片 `primary_motion_family` 计数满足 `T-MOTION`。

失败项加入 `spot_check_fails`，issue 使用 `missing_motion_plan`、`generic_motion_repetition`、`role_motion_mismatch`、`unmotivated_effect`、`continuity_violation`、`continuation_media_reentry`、`unseekable_animation_runtime`、`focal_region_not_traversed` 或更具体名称，并带 `scene_id` / boundary scene ids 与 proof frame / clip 路径。

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
  "layout_geometry_fails": [
    {"scene_id": "s2", "issue": "center_clustered_layout", "detail": "...", "metrics": {"width_coverage": 0.42}}
  ],
  "spot_check_fails": [
    {"scene_id": "s8", "frame": "frame_0123.jpg", "issue": "字幕遮罩过宽", "detail": "..."}
  ],
  "affected_scenes": ["s3", "s4", "s5", "s7", "s8"],
  "verdict": "fail"
}
```

`affected_scenes` 为所有 finding 的 `scene_id` / `scene_ids` 去重后按时间排序；`global` 固定排在最后。`static_frames`、`reused_materials`、`narration_mismatches`、`layout_geometry_fails`、`spot_check_fails` 都为空时 `verdict = "pass"`，并且 `affected_scenes` 为空。

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
| R5-R6 | 为每个 scene 写稳定 data 属性；按 `scene-material-suggestions.json`（如存在）分配 `material_ref` / `material_refs`；`media_continuation` group 写 `data-continuation-group` / index | 检查 scene inventory、素材引用、`no_match` 不与素材 assignment 并存、continuation group 是否显式声明且相邻；只允许在完整 continuation metadata 已存在时补全漏标的 `media_continuation` role | 检测素材跨 scene 复用；声明过的 `media_continuation` group 作为合法例外；用 scene data 反查 finding |
| R7 | authoring 时控制 scene 时长、微 scene、合并 scene 和 text beat 刷新 | `DESIGN.md` 记录时长设计 | 每轮解析 `data-scene-start/end` |
| R8 | 按 `layout-routing.md` 的 authority / resolution order 解析 role；按 scene 的 material、`layout_role`、`visual_role`（如有）与 orientation 选择 presentation；缺失 role 用 fallback、不改写上游 role | Scene Layout Inventory 记录 role source / explicit-or-inferred / matched routing rows；DOM geometry gate 检查 union、gutter、gap、occupancy、视觉重心 | `layout_geometry_fails` + spot-check 检查 layout / orientation / cross-aspect / 结构型文本与 role-preservation |
| R9-R12 | 用 catalog 尺寸设置普通 wrapper aspect-ratio；素材填满容器且无可见框；`viewport_reveal` 用 scene-ratio reveal viewport + 内层原比例素材；确保素材占主体、清晰完整、media\\_first/video\\_first 最大化可视区域、cross-aspect 素材通过 `T-FIT` 或切换 `viewport_reveal` / `detail_callout` / 替换素材（已有完整合法 continuation metadata 时可保持 `media_continuation`）、catalog source figure / table / chart 保留来源结构且不按 structured unit 裁切 / 重画、scale factor 落在 `T-MEDIA`、video overlay 不遮挡关键区域；元素不越界不重叠 | 扫描错比例容器、错误 object-fit、普通素材 `width + max-height/height`、未标注 reveal 的 overflow clipping、`tall`/`ultra-tall` 竖图 full_fit、full_fit 未达 `T-FIT`、reveal 窗口超出 `T-REVEAL`、素材容器露底；Scene Visual Audit 检查 media dominance、主媒体是否被压小、rendered / source scale factor、`MW / CW`、`MH / CH`、video overlay bounds / focal\\_region 避让、comparison 可读性、bounds、overlap | 抽帧检查裁切、变形、letterbox / pillarbox / 容器露底 / 素材框感、画面清晰度、放大比例、cross-aspect 可读宽高、重叠、越界、视频浮层遮挡和多素材可读性 |
| R13-R14 | 分栏均衡；区域填满或对称留白；禁用 glow 模式 | Scene Visual Audit；DOM geometry gate 检查 coverage / gutter / center / occupancy | `layout_geometry_fails` + spot-check 检查填充不足、挤中间、过大 gutter、容器过空、单边空白 |
| R15-R16 | 布局计算排除字幕安全区；使用单个全局字幕容器和 calibrated subtitle units；横屏单行、竖屏最多两行 | 检查安全区、字幕 CSS、按朝向的最大行数与行高、遮罩宽度、`subtitle-units.json` 来源、切换 timing 和非字幕元素侵入 | 抽帧检查字幕位置、行数、遮罩宽度、遮挡和 timing |
| R17 | 字号 / 对比度达标、标题无孤行、DOM 嵌套受限 | Typography check；DOM geometry gate 检查主信息字号 | `layout_geometry_fails` 覆盖 undersized text；spot-check 字号 / 孤行 / 对比度 |
| R18 | 读取当前 HyperFrames 动画能力索引；按语义 → 主体 → role / layout → continuity → effect → runtime 写 motion plan；静态素材用内容驱动行为；`media_continuation` 主媒体稳定 | Motion Plan Audit；扫描 generic motion repetition、廉价覆盖层、idle filler、缺失 handoff、无资产 / 无机制 runtime、unseekable motion、continuation re-entry | 静帧检测 + spot-check 检查 role-motion 语义、内容驱动 progression、transition vocabulary、runtime 合理性、连续同质动画和 continuation 稳定性 |
| R19 | 文本元素绑定完整旁白句子；优先实现 `scene-text-plan.json` 的 primary units；入场有初始态 | 扫描 blanket `immediateRender:false`、text beat 累积和 primary unit 未实现 | 旁白对齐抽样 + spot-check 文本提前 / 累积 / 结构型文本降级 |
| R20-R21 | `composition/DESIGN.md` 记录 scene inventory、layout rationale、peak-state audit | Scene Layout Inventory；Peak-state / Scene Visual Audit；DOM geometry gate | 用 scene data 反查 finding；`layout_geometry_fails` 进入 feedback loop |
| Customized rules | authoring 时逐条覆盖 handoff rules | `DESIGN.md` 记录每条覆盖方式 | 可见规则进入 spot-check / narration alignment |

新增或调整规则时，同步更新本表。
