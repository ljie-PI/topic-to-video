# Composition Rules

本文件记录 Phase 8 HyperFrames composition 的固定规则。项目变量、实际输入路径、style hint 和用户定制约束来自 `composition-handoff.md`。

## Rule Boundary

- 本文件是 Phase 8 hard constraints 的权威来源；HyperFrames sub-agent 必须读取工作区本地副本 `references/composition-rules.md`。
- `composition-handoff.md` 可以补充 user-derived customized rules，但不得修改或覆盖本文件。
- 若 customized rule 与本文件冲突，sub-agent 必须以本文件为底线，并在 `composition/DESIGN.md` 记录冲突处理。
- 如果 `composition-handoff.md` 或 `references/composition-rules.md` 不存在 / 不可读，必须停止并反馈主 agent，不得凭默认审美继续制作。

## Rule Definitions

### R1 — Final audio only

`voice_clone/narration.mp3` 是最终解说音频。不要重新生成 TTS，也不要调用 HyperFrames 的 TTS。若从 catalog 视频裁剪源片段，必须用 `-an` 去掉源音频。

### R2 — Transcript timing

词级时间以 `transcribe/transcript.json` 为准。scene 切分、字幕切换和 text beat 出现时机必须绑定到该 transcript 的句子 / 词级时间。

### R3 — Material catalog

所有以素材为底的视觉都必须通过 `material-catalog.json` 解析；需要 catalog 素材时不得凭空造 stock 视觉。`scene-material-suggestions.json` 如存在，视为素材到 scene 的硬性分配。

### R4 — Local fonts

字体加载使用 `fonts/` 下的本地资源，确保可复现；不要依赖系统 `fc-match`。

### R5 — Scene identity

`composition/index.html` 中每个 scene 根元素必须有稳定的 `data-scene-id`、`data-scene-start`、`data-scene-end`。所有 `<img>` / `<video>` / `background-image` 素材元素必须位于某个 scene 根元素内部。重渲修复时，未受影响 scene 的 DOM / CSS / 动画和时间区间必须保持不变。

### R6 — Material uniqueness

每个 catalog 素材在整片中恰好出现在一个 scene；`no_match` scene 用纯排版 / 文字视觉，不借用其他 scene 的素材。

### R7 — Scene duration

普通 scene 目标时长为 5-8 秒。连续同素材合并而成的 scene 可以超过 8 秒，但 scene 内文本信息单元仍须按 5-8 秒节奏刷新，并受 R15 / R16 约束。

### R8 — Material aspect ratio

素材容器比例必须来自 `material-catalog.json` 的 `width` / `height`；缺失时才 fallback 到实测。禁止默认 16:9，禁止因比例错误产生裁切、拉伸、letterbox 或 pillarbox。

### R9 — Material container

素材容器必须紧贴素材：无可见 border / outline / padding / shadow / glow / inset / 卡片底色，且容器和素材 transform 必须同步。不要在同一素材容器上同时写死 `width` 和 `max-height` / `height`。

Recommended authoring pattern:

```css
.media-panel {
  aspect-ratio: <W> / <H>;
  width: min(<availW>px, calc(<availH>px * <W> / <H>));
  height: auto;
}
```

### R10 — Subtitle safe area

视口底部预留 12-18% 高度作为字幕安全区。authoring 时内容区必须按 `viewport - subtitle safe area` 计算；除全局字幕条外，任何前景文本 / callout / 素材 / 装饰不得进入该安全区。全幅背景素材可延伸到安全区下方。

### R11 — Global subtitle

字幕必须使用单个全局容器，固定锚定在底部字幕安全区内（建议 bottom 为视口高度 6-9%）。字幕单元必须单行、水平居中、背景遮罩 shrink-to-fit。长句先按句号 / 问号 / 感叹号，再按分号 / 逗号 / 顿号 / 自然停顿拆分，直到单行可读。

### R12 — Scene-specific layout

每个 scene 必须按旁白文本、素材尺寸 / 类型、text beats 和内容区尺寸单独排版；相邻 scene 不得无理由复用同一主版式。

### R13 — Scene inventory

`composition/DESIGN.md` 必须记录每个 scene 的 `scene_id`、旁白摘要、`material_ref`、素材尺寸 / aspect ratio、text beats、layout archetype、peak-state audit 结果，以及每个非素材元素对应的完整旁白句子和出现时间点。

### R14 — Peak-state layout audit

动画前必须检查每个 scene 的 peak state：所有非字幕元素都显示时，元素不得溢出 viewport / 内容区、不得互相遮挡、前景元素不得覆盖 catalog 素材、素材不得 letterbox / pillarbox、内容区纯空白不得超过 10%、构图不得明显失衡。失败必须先修布局，不得靠“暂时隐藏元素”掩盖问题。

### R15 — Motion

最终画面不得连续静止超过 2 秒。有效动效必须来自内容本身，如素材 Ken Burns / 缓移 / 缩放、文字渐入、数据 callout 浮现或极轻微低对比装饰 drift。禁止用横贯 / 纵贯扫描线、扫光、sweep、进度条等覆盖层凑动效。

### R16 — Text timing and entrance state

多个非素材文本元素必须按完整旁白句子逐个出现，禁止 scene start 一次性全亮。旧 text beat 需要淡出或降级，不能永久累积。入场动画必须有正确初始态，避免元素在 tween 前闪现。

### R17 — Media dominance and quality

有图片 / 视频素材的 scene，素材应占据内容区主体（通常 >= 50%）。图片必须清晰、关键信息完整，不得可见模糊、像素化、JPG artifacts 或裁掉关键信息。

### R18 — Bounds and overlap

所有视觉元素必须完整位于画面内，不得截断。除全局字幕条覆盖底层画面外，任何前景标题、caption、tag、badge、callout、label、数据块都不得压在图片 / 视频素材之上，包括 hero 素材。

### R19 — Typography, DOM, contrast

同一 scene 内最大 / 最小字号比 <= 3:1；主标题文本框不得折成 2+ 行。素材 / 文本容器最多 2 层嵌套。正文对比度 >= 4.5:1，大字号标题对比度 >= 3:1。

### R20 — Style constraints

文字框内文字应垂直 / 水平居中，内容区不得出现 >10% 视口面积的纯空白。Moon / 深色技术编辑风默认纯色 + 极淡网格 / 细线 / 低对比结构，禁止 `radial-gradient` spotlight、localized glow、ambient orb、neon halo、发光阴影和用 glow 充当层次感。

## Stage Usage Matrix

| Rule | Authoring application | Pre-render check | Visual QA check |
| --- | --- | --- | --- |
| R1-R4 | 读取 handoff 指定输入；只使用本地音频、transcript、catalog 和 fonts | Reference Read Check | sanity-check 音频流；spot-check 画面是否与素材 / 旁白一致 |
| R5-R6 | 为每个 scene 写稳定 data 属性；按分配使用素材 | 检查 scene inventory 和素材引用 | 检测素材跨 scene 复用；用 scene data 反查 finding |
| R7 | authoring 时控制 scene 时长和 text beat 刷新 | `DESIGN.md` 记录时长设计 | 每轮解析 `data-scene-start/end` |
| R8-R9 | 用 catalog 尺寸设置素材容器比例；无可见素材框 | 扫描破坏 aspect-ratio 的 CSS 和可见框模式 | 抽帧检查 letterbox / pillarbox / 素材框感 |
| R10-R11 | 布局计算排除字幕安全区；使用单个全局字幕容器 | 检查非字幕元素是否进入安全区；检查字幕 CSS | 抽帧检查字幕位置、单行、遮罩宽度和遮挡 |
| R12-R14 | 按 scene 内容选择 layout；写 inventory 和 peak-state audit | `composition/DESIGN.md` 必须覆盖每个 scene | spot-check 构图、空白、溢出、重叠、素材比例 |
| R15 | 为素材 / 文本 / callout 设计持续动效和转场 | 扫描廉价覆盖层动效 | 静帧检测和 spot-check 扫描线 / sweep |
| R16 | 文本元素绑定完整旁白句子；入场有初始态 | 扫描 blanket `immediateRender:false` 和 text beat 累积 | 旁白对齐抽样 + spot-check 文本提前 / 累积 |
| R17-R19 | 确保素材占主体、清晰、元素不越界不重叠、字号/对比度达标 | peak-state audit | spot-check 画面清晰度、重叠、越界、字号、对比度 |
| R20 | 按 style hint / design file 实现风格；不使用禁用 glow 模式 | 扫描 glow / orb / spotlight | spot-check 空白、模板感和深色技术风漂移 |
| Customized rules | authoring 时逐条覆盖 handoff rules | `DESIGN.md` 记录每条覆盖方式 | 可见规则进入 spot-check / narration alignment |

## Phase 8.2 — Sub-agent Execution Rules

- 如果用户 query 指定了 coding agent / 委派目标，优先使用该目标；否则使用当前客户端 / runtime 原生 sub-agent 或委派工具。
- sub-agent 必须读取 `composition-handoff.md`、`references/composition-rules.md` 和 handoff 指定的 `references/design-<theme>.md`（如有）。
- composition authoring、HTML/CSS/GSAP、HyperFrames lint/inspect 和 HTML-to-video render 都由 HyperFrames coding sub-agent 执行。
- 主 agent 不在自己的会话里手工 patch `composition/index.html`；视觉修复必须反馈给 sub-agent。

## Phase 8.3 — Pre-render Self-Audit Rules

首次 HTML-to-video render 前，sub-agent 必须完成 static / layout self-audit，并把结果写入 `composition/DESIGN.md`。失败项先修复，再 render。

`composition/DESIGN.md` 至少记录：

1. **Reference Read Check**：确认已读取 `composition-handoff.md`、`references/composition-rules.md` 和 handoff 指定的 `references/design-<theme>.md`（如有）。
2. **Scene Layout Inventory**：覆盖每个 scene，满足 R13。
3. **Peak-state layout audit**：覆盖每个 scene，满足 R14。
4. **Sentence-level timing plan**：覆盖 R16；多个非素材文本元素不得在 scene start 一次性全亮。
5. **Forbidden pattern scan**：扫描固定宽字幕框、字幕 `width:100%` / 大 `min-width`、素材 `width + max-height/height`、素材可见框、前景覆盖素材、`radial-gradient` spotlight / ambient orb / localized glow、廉价扫描线 / sweep，以及所有 entrance tween blanket `immediateRender:false`。若使用 `gsap.from()` 做入场动画，应保留默认 immediate render，或用 CSS 初始态兜底。
6. **Customized rules coverage**：逐条读取 `composition-handoff.md` 的 `User-derived Customized Rules`，记录每条如何被布局 / 动画 / QA 方案覆盖；冲突按 Rule Boundary 处理。

## Phase 8.4 — HTML-to-video Render Rules

这里的 render 指从 `composition/index.html` 渲染为 `composition/renders/final.mp4`，不是生成 HTML。

- render 前必须先通过 Phase 8.3 self-audit。
- `hyperframes lint` 和 `hyperframes inspect` 必须无错误。
- render 必须使用 `--workers 1`。
- 迭代直到 `composition/renders/final.mp4` 存在，且固定产物齐全：`composition/index.html`、`composition/DESIGN.md`、`composition/renders/final.mp4`。

## Phase 8.5 — Sanity Check Rules

render 后，主 agent 对 `composition/renders/final.mp4` 做确定性 sanity-check：

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 \
  {work_dir}/{topic_name}/composition/renders/final.mp4
ls -la {work_dir}/{topic_name}/composition/renders/final.mp4
ffprobe -v error -select_streams a:0 -show_entries stream=codec_type -of csv=p=0 \
  {work_dir}/{topic_name}/composition/renders/final.mp4
```

预期：duration 接近目标解说时长，文件大小 > 1 MB，且包含一条音频流。异常时把症状反馈给 HyperFrames sub-agent；主 agent 不手工 patch HTML。

## Phase 8.6 — Post-Render Visual QA Rules

sanity-check 通过后，主 agent 对 final.mp4 做视觉 QA。

### QA mode

- **首轮 = 全量审计**：全片抽帧；静帧 / 复用 / spot-check 全片跑，旁白对齐抽样。
- **重渲轮 = 限定范围审计**：昂贵 vision 检查只覆盖上一轮 `affected_scenes`；静帧 / 复用等无 vision 成本检查仍全片跑。若 `affected_scenes` 含 `global`，字幕相关检查恢复全片抽样。

### Step 1 — 每秒抽帧

```bash
mkdir -p {work_dir}/{topic_name}/composition/qa-frames
ffmpeg -y -i {work_dir}/{topic_name}/composition/renders/final.mp4 \
  -vf fps=1 -q:v 2 \
  {work_dir}/{topic_name}/composition/qa-frames/frame_%04d.jpg
```

### Step 2 — 静帧检测

用 ffmpeg scene 滤波或相邻抽帧 perceptual hash 检测连续静止。任意连续 >= 3 张 1fps 抽帧低变化（约 >= 2 秒）记为 `static_frame` finding，并用 `data-scene-start/end` 反查 `scene_id`。

### Step 3 — 素材跨 scene 复用检测

按 `data-scene-id` 划分 scene，提取 catalog 素材 src。任一 catalog src 出现在多个 scene，记为 `reused_material` finding，并记录所有命中的 `scene_ids`。通用 UI 贴图 / 装饰纹理 / 蒙版等非 catalog 资源不计。

### Step 4 — 旁白对齐检测

按 `transcribe/transcript.json` 的句子边界切分。首轮抽样 `M = max(8, scene 数)` 句，并保证每个 scene 至少覆盖 1 句；重渲轮只检查 affected scenes 中的句子。对每句覆盖帧调用 vision 检查画面是否表达旁白含义，`no` / `partial` 记为 `narration_mismatch` finding。

### Step 5 — 静帧 spot-check

抽样 `N = max(5, ceil(total_seconds / 30))` 张帧。重渲轮只从 affected scenes 覆盖帧抽样，`global` 字幕问题除外。每帧检查：

1. 图片清晰、关键信息完整。
2. 元素不越界、不截断。
3. 同时显示的元素不重叠，前景元素不压素材。
4. DOM 扁平、颜色对比度达标。
5. 字号比 <= 3，主标题不折行。
6. 内容区无 >10% 纯空白。
7. 字幕安全区无非字幕前景元素侵入。
8. 素材无 letterbox / pillarbox。
9. 无扫描线 / sweep / 进度条等廉价动效覆盖层。
10. 底部字幕位置稳定、水平居中、位于安全区内。
11. 字幕单行、遮罩 shrink-to-fit。
12. 素材无可见 border / padding / 卡片底 / shadow / glow。
13. layout 不像固定模板硬套，能体现素材横竖 / 方形比例差异。
14. 非素材文字没有大段提前出现，也没有 text beat 累积堆满屏幕。
15. handoff customized rules 中可见规则已被覆盖。

失败项加入 `spot_check_fails`，每条 finding 必须带 `scene_id`；全局字幕容器问题记为 `global`。

### Step 6 — 汇总 QA report

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

## Phase 8.7 — QA Feedback Loop

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

## Phase 8.8 — QA Coverage Mapping

| Rule | Coverage |
| --- | --- |
| R1-R4 | Phase 8.2 reference read + Phase 8.5 audio sanity-check + Phase 8.6 narration/material checks |
| R5 | Phase 8.3 scene inventory + Phase 8.6 scene reverse lookup |
| R6 | Phase 8.6 Step 3 |
| R7 | Phase 8.3 timing plan + Phase 8.6 affected-scene time parsing |
| R8-R9 | Phase 8.3 forbidden pattern scan + Phase 8.6 Step 5 items 8/12 |
| R10-R11 | Phase 8.3 layout audit + Phase 8.6 Step 5 items 7/10/11 |
| R12-R14 | Phase 8.3 scene inventory / peak-state audit + Phase 8.6 Step 5 items 2/3/6/13 |
| R15 | Phase 8.6 Step 2 + Step 5 item 9 |
| R16 | Phase 8.3 timing plan / `immediateRender:false` scan + Phase 8.6 Step 4 and Step 5 item 14 |
| R17 | Phase 8.3 layout inventory + Phase 8.6 Step 5 item 1 |
| R18 | Phase 8.3 peak-state audit + Phase 8.6 Step 5 items 2/3 |
| R19 | Phase 8.3 peak-state audit + Phase 8.6 Step 5 items 4/5 |
| R20 | Phase 8.3 forbidden pattern scan + Phase 8.6 Step 5 items 6/9/13 |
| Customized rules | Phase 8.3 customized coverage + Phase 8.6 visible-rule spot-checks |

新增或调整规则时，同步更新 Stage Usage Matrix 与本覆盖表。
