# Composition Rules

本文件记录 Phase 8 HyperFrames composition 的固定规则。项目变量、实际输入路径、style hint 和用户定制约束来自 `composition-handoff.md`。

## Scope and Required References

- 本文件是 Phase 8 hard constraints 的权威来源；HyperFrames sub-agent 必须读取工作区本地副本 `references/composition-rules.md`。
- sub-agent 必须读取 `composition-handoff.md`，以及 handoff 指定的 `references/design-<theme>.md`（如有）。
- 如果 `composition-handoff.md`、`references/composition-rules.md` 或指定 design file 不存在 / 不可读，必须停止并反馈主 agent，不得凭默认审美继续制作。
- `composition-handoff.md` 可以补充 user-derived customized rules，但不得修改或覆盖本文件。
- 若 customized rule 与本文件冲突，sub-agent 必须以本文件为底线，并在 `composition/DESIGN.md` 记录冲突处理。

## Rule Definitions

### Input and source rules

#### R1 — Final audio only

`voice_clone/narration.mp3` 是最终解说音频。不要重新生成 TTS，也不要调用 HyperFrames 的 TTS。若从 catalog 视频裁剪源片段，必须用 `-an` 去掉源音频。

#### R2 — Transcript timing

时间边界以 `transcribe/transcript.json` 为准。scene 切分和非字幕 text beat 出现时机必须绑定到该 transcript 的句子 / 分句边界。最终字幕必须读取 `transcribe/subtitle-units.json`：subtitle unit 的 timing 来自 transcript 句子 / 词时间，display text 以 transcript 文本为底，并可包含 `narration.txt` 高置信度匹配带来的 Latin words 拼写修正。字幕切换和音频偏移 <= 0.2 秒。

#### R3 — Material catalog

所有以素材为底的视觉都必须通过 `material-catalog.json` 解析；需要 catalog 素材时不得凭空造 stock 视觉。`scene-material-suggestions.json` 如存在，视为素材到 scene 的硬性分配。

#### R4 — Local fonts

字体加载使用 `fonts/` 下的本地资源，确保可复现；不要依赖系统 `fc-match`。

### Scene structure and timing rules

#### R5 — Scene identity

`composition/index.html` 中每个 scene 根元素必须同时有稳定的 `data-scene-id`、`data-scene-start`、`data-scene-end`。所有 `<img>` / `<video>` / `background-image` 素材元素必须位于某个 scene 根元素内部。重渲修复时，未受影响 scene 的 DOM / CSS / 动画和时间区间必须保持不变。

#### R6 — Material uniqueness

每个 catalog 素材（图片 / 视频 clip）在整片中恰好出现在一个 scene，分配以 `scene-material-suggestions.json` 为准。`no_match` scene 用纯排版 / 文字卡片，不借用其他 scene 的素材。

#### R7 — Scene duration

普通 scene 目标时长为 5-8 秒；超过 8 秒必须拆分，连续多个 < 3 秒的微 scene 应避免。连续同素材合并而成的 scene 可以超过 8 秒，但 scene 内文本信息单元仍须按 5-8 秒节奏刷新，并受 R18 / R19 约束。

#### R8 — Scene-specific layout

每个 scene 必须由 coding sub-agent 根据该 scene 的旁白文本、`scene-material-suggestions.json` 中的 `text_beats` / `material_ref`、以及 `material-catalog.json` 中对应素材的尺寸 / 类型定制 authoring，再按内容区尺寸（viewport - 字幕安全区 - scene padding）单独排版。禁止套用统一模板后只替换文字 / 图片；相邻 scene 不得无理由复用同一主版式。根据素材比例和 text beat 数量选择 layout archetype：横图 / 横视频用宽幅主体 + 外置信息区，竖图用左右分栏，方图用中心素材 + 周边信息块，无素材 scene 用纯排版 / 数据块。

#### R9 — Scene inventory

`composition/DESIGN.md` 必须记录每个 scene 的 `scene_id`、旁白摘要、`material_ref`、素材尺寸 / aspect ratio、text beats、layout archetype、peak-state audit 结果，以及每个非素材元素对应的完整旁白句子和出现时间点。

#### R10 — Peak-state layout audit

动画前必须检查每个 scene 的 peak state：所有非字幕元素都显示时，元素不得溢出 viewport / 内容区、不得互相遮挡、前景元素不得覆盖 catalog 素材、素材不得 letterbox / pillarbox、内容区纯空白不得超过 10%、构图不得明显失衡。失败必须先调整布局尺寸、位置、字号、信息密度或拆 scene，不得靠“暂时隐藏元素”掩盖问题。

### Media, subtitle, and layout rules

#### R11 — Material aspect ratio

素材容器比例必须来自 `material-catalog.json` 的 `width` / `height`（图片由 harvester 写入，视频由下载 / ffprobe 流程写入）。将 `width / height` 作为 `aspect-ratio` 应用于包裹素材的 wrapper；只有字段为 `null` / 缺失时才 fallback 到运行时实测或 ffprobe。禁止默认 16:9，禁止用错误比例容器 + `object-fit: cover` 裁掉素材，禁止因比例错误产生拉伸、letterbox 或 pillarbox。

#### R12 — Material container

素材容器必须紧贴素材：容器无可见 border / outline / padding / shadow / glow / inset / 卡片底色，素材本身填满 wrapper（如 `width: 100%; height: 100%`）。素材尺寸不适合时，调整布局 / 缩放 / 换素材，不用外框或底色遮丑。容器与素材的 transform / 动效必须绑定在同一元素或一组同步元素上，避免素材跑出容器或容器露边。不要在同一素材容器上同时写死 `width` 和 `max-height` / `height`，否则显式尺寸会覆盖 `aspect-ratio` 推导，造成容器底色 / letterbox 暴露。

Recommended authoring pattern:

```css
.media-panel {
  aspect-ratio: <W> / <H>;
  width: min(<availW>px, calc(<availH>px * <W> / <H>));
  height: auto;
  margin: 0 auto;
}
```

#### R13 — Subtitle safe area

视口底部预留专属字幕安全区，高度必须贴合字幕条实际占位（字幕行数 × 行高 + 上下小边距），不得显著大于字幕条本身：横屏（`1920x1080`）字幕固定单行，安全区约 9-12%（1080p 约 97-130px）；竖屏 / 竖向（`1080x1920`、`1080x1440`）允许字幕最多两行，安全区按两行高度预留，约 14-18%（1920 高约 270-345px，1440 高约 200-260px）。authoring 时内容区必须按 `viewport - subtitle safe area` 计算；除全局字幕条外，任何前景文本 / callout / 素材 / 装饰不得进入该安全区。全幅背景素材可延伸到安全区下方垫底，此时字幕条用半透明遮罩压在其上。安全区高度按该朝向字幕最大行数（横屏 1 行、竖屏 2 行）计算，不得为不会出现的额外行预留空间。

#### R14 — Global subtitle

字幕必须使用单个全局容器，固定锚定在底部字幕安全区内并与安全区上下贴合（建议 bottom 为视口高度 3-5%，1080p 约 32-54px；字幕条顶缘应接近安全区顶缘，安全区内不得留出明显空带导致字幕悬高），全片水平居中且基线稳定。字幕容器必须从安全区底部向上排版（如 `bottom` 锚定 + 文本底对齐），行数变化时基线稳定、不上下跳动。字幕单元来自 `transcribe/subtitle-units.json`。横屏每个单元必须单行显示（如 `white-space: nowrap`）；竖屏 / 竖向允许每个单元最多两行（通过 `max-width` 自动换行，明确禁止第三行及以上）。无论横竖屏，如果某个 unit 在该朝向允许的最大行数内仍放不下，必须回到 transcript-timed unit 拆分逻辑，把它拆成更小的 calibrated units；不得靠缩字号到下限、放宽 `max-width` 或塞进多余行数。半透明背景遮罩必须 shrink-to-fit，随文字宽度自适应并保证任意画面背景下可读；禁止固定 `width: 100%`、大 `min-width` 或整行遮罩。

#### R15 — Media dominance and quality

有图片 / 视频素材的 scene，素材应占据内容区主体（通常 >= 50%），禁止缩成角落邮票贴在大段文字旁。允许放大素材填充画面，但原始短边放大不超过 2x；多素材 scene 优先轮播切换，如必须并列，每个素材 >= 30% 内容区。图片必须清晰、关键信息完整，原图分辨率应覆盖渲染尺寸，不得可见模糊、像素化、JPG artifacts 或裁掉文字、图表轴线、人物面部、UI 主控件等关键信息。

#### R16 — Bounds and overlap

所有视觉元素必须完整位于画面内，不得截断。除全局字幕条覆盖底层画面外，任何前景标题、caption、tag、badge、callout、label、数据块都不得压在图片 / 视频素材之上，包括 hero 素材。

#### R17 — Typography, DOM, contrast

同一 scene 内最大 / 最小字号比 <= 3:1；主标题文本框不得折成 2+ 行。素材 / 文本容器最多 2 层嵌套。正文对比度 >= 4.5:1，大字号标题对比度 >= 3:1。

### Motion, text, and style rules

#### R18 — Motion

最终画面不得连续静止超过 2 秒。有效动效必须来自内容本身，如素材 Ken Burns / 缓移 / 缩放、文字渐入、数据 callout 浮现或极轻微低对比装饰 drift。每张图片素材都需要持续动效，同一类图片动效不得重复超过 `ceil(total_images / 5)` 次；视频素材视为自带运动，接近静止的视频按图片处理。相邻 scene 需要显式转场，避免硬切。禁止用横贯 / 纵贯扫描线、扫光、sweep、进度条等覆盖层凑动效。

#### R19 — Text timing and entrance state

多个非素材文本元素必须按完整旁白句子逐个出现，禁止 scene start 一次性全亮。文本元素服务于哪一句，就在该句开始前短暂提前显示，保证旁白读到该句时相关文本已可见。旧 text beat 需要淡出或降级，不能永久累积。入场动画必须有正确初始态，避免元素在 tween 前闪现。

#### R20 — Style constraints

文字框内文字应垂直 / 水平居中。内容区不得出现 >10% 视口面积的纯空白；字幕安全区不计入空白统计，也不得为填满而把内容元素铺进该带。如需呼吸空间，用极淡装饰 / 网格 / 角标占位。Moon / 深色技术编辑风默认纯色 + 极淡网格 / 细线 / 低对比结构，禁止 `radial-gradient` spotlight、localized glow、ambient orb、neon halo、发光阴影和用 glow 充当层次感。

## Stage Protocols

### Phase 8.3 — Pre-render Self-Audit Rules

首次 HTML-to-video render 前，sub-agent 必须完成 static / layout self-audit，并把结果写入 `composition/DESIGN.md`。失败项先修复并重跑 self-audit；只有 Phase 8.3 pass 后，才能进入 Phase 8.4 的 `hyperframes lint` / `hyperframes inspect` 和 render。

执行方式：

1. **Source pass**：读取 `composition/index.html`、CSS / JS、`composition-handoff.md`、`material-catalog.json`、`scene-material-suggestions.json`、`transcribe/transcript.json` 和 `transcribe/subtitle-units.json`，建立 scene inventory，并扫描 forbidden patterns。
2. **Peak-state pass**：对每个 scene 选择一个或多个 peak-state 时间点（所有非字幕元素应可见、主要 text beat 已出现、退出动画未开始），用 HyperFrames / 浏览器可 seek 的预览能力或等价 DOM inspection 打开 `composition/index.html`，seek 到这些时间点。
3. **Geometry measurement**：在每个 peak state 读取 scene root、素材、文本、callout、decor、全局字幕容器的 bounding boxes，并计算 viewport、内容区、字幕安全区。
4. **Rule checks**：用几何数据检查元素溢出、重叠、前景压素材、素材占比、内容区使用率、alignment、margin / padding / gap、素材容器比例 / 露底、字幕安全区侵入和字幕框尺寸。
5. **Fix loop**：任一检查失败时，sub-agent 必须修改 layout / CSS / DOM / 动画初始态并重新跑 8.3，不得靠隐藏元素、延后显示或动画错开来掩盖 peak-state layout 问题。
6. **Audit output**：把每个 scene 的检查摘要、失败项和修复记录写入 `composition/DESIGN.md`；不能只写 “checked” / “pass”。

`composition/DESIGN.md` 至少记录：

1. **Reference Read Check**：确认已读取 `composition-handoff.md`、`references/composition-rules.md` 和 handoff 指定的 `references/design-<theme>.md`（如有）。
2. **Scene Layout Inventory**：覆盖每个 scene，满足 R9。
3. **Peak-state / Scene Visual Audit**：覆盖每个 scene，满足 R10，并记录 viewport / 内容区 / 字幕安全区边界、主要元素 bounding boxes、元素是否溢出 / 截断 / 重叠、前景文本 / caption / tag / callout 是否压素材、内容区使用率、素材主体占比、标题 / 文本块 / 素材 / callout alignment、margin / padding / gap 是否一致、素材容器是否紧贴素材、字幕安全区是否只被全局字幕条使用。
4. **Layout Fix Record**：记录每个失败项如何通过 layout 尺寸、位置、字号、信息密度、间距、拆 scene 或素材替换修复；不得只写“已修复”。
5. **Sentence-level timing plan**：覆盖 R19；多个非素材文本元素不得在 scene start 一次性全亮。
6. **Forbidden pattern scan**：扫描缺失 `transcribe/subtitle-units.json`、字幕直接使用 raw ASR text、固定宽字幕框、字幕 `width:100%` / 大 `min-width`、横屏字幕多行 / 竖屏字幕超过两行、字幕脱离安全区、安全区为不会出现的额外行数预留过大空间、前景元素侵入安全区、字幕切换偏离音频 > 0.2 秒、素材错比例容器、错误 `object-fit: cover` 裁切、`object-fit: contain` 暴露容器底色 / letterbox、素材 `width + max-height/height`、素材可见框 / 底色 / padding / shadow / glow、catalog 素材跨 scene 复用、`no_match` 借用素材、前景覆盖素材、`radial-gradient` spotlight / ambient orb / localized glow、廉价扫描线 / sweep，以及所有 entrance tween blanket `immediateRender:false`。若使用 `gsap.from()` 做入场动画，应保留默认 immediate render，或用 CSS 初始态兜底。
7. **Customized rules coverage**：逐条读取 `composition-handoff.md` 的 `User-derived Customized Rules`，记录每条如何被布局 / 动画 / QA 方案覆盖；冲突按 Scope and Required References 处理。

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

按 `data-scene-id` 划分 scene，提取 catalog 素材 src。任一 catalog src 出现在多个 scene，记为 `reused_material` finding，并记录所有命中的 `scene_ids`。通用 UI 贴图 / 装饰纹理 / 蒙版等非 catalog 资源不计。

#### Step 4 — 旁白对齐检测

按 `transcribe/transcript.json` 的句子边界切分。首轮抽样 `M = max(8, scene 数)` 句，并保证每个 scene 至少覆盖 1 句；重渲轮只检查 affected scenes 中的句子。对每句覆盖帧调用 vision 检查画面是否表达旁白含义，`no` / `partial` 记为 `narration_mismatch` finding。

#### Step 5 — 静帧 spot-check

抽样 `N = max(5, ceil(total_seconds / 30))` 张帧。重渲轮只从 affected scenes 覆盖帧抽样，`global` 字幕问题除外。每帧检查：

1. 图片清晰、关键信息完整，放大不超过原始短边 2x。
2. 元素不越界、不截断。
3. 同时显示的元素不重叠，前景元素不压素材。
4. DOM 扁平、颜色对比度达标。
5. 字号比 <= 3，主标题不折行。
6. 内容区无 >10% 纯空白。
7. 字幕安全区无非字幕前景元素侵入。
8. 素材无 letterbox / pillarbox。
9. 无扫描线 / sweep / 进度条等廉价动效覆盖层。
10. 底部字幕位置稳定、水平居中、位于安全区内，文本来自 `transcribe/subtitle-units.json`，切换与音频偏移 <= 0.2 秒。
11. 横屏字幕单行；竖屏 / 竖向字幕最多两行、无第三行；遮罩 shrink-to-fit，无固定宽度 / 大 `min-width` / 整行遮罩；超出该朝向最大行数时拆分 calibrated units，不靠缩字号或多塞行。
12. 素材无可见 border / padding / 卡片底 / shadow / glow，且无容器露底 / letterbox。
13. 有素材 scene 的素材占内容区主体；多素材并列时每个素材尺寸足够。
14. layout 不像固定模板硬套，能体现素材横竖 / 方形比例差异。
15. 非素材文字没有大段提前出现，也没有 text beat 累积堆满屏幕。
16. 相邻 scene 有明确转场；图片素材有持续动效。
17. handoff customized rules 中可见规则已被覆盖。

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
| R5-R6 | 为每个 scene 写稳定 data 属性；按 `scene-material-suggestions.json` 分配素材 | 检查 scene inventory、素材引用、`no_match` 处理 | 检测素材跨 scene 复用；用 scene data 反查 finding |
| R7 | authoring 时控制 scene 时长、微 scene、合并 scene 和 text beat 刷新 | `DESIGN.md` 记录时长设计 | 每轮解析 `data-scene-start/end` |
| R8-R10 | 按 scene 旁白、text beats、素材尺寸 / 类型选择 layout；写 inventory 和 peak-state audit | Scene Visual Audit 覆盖 bounding boxes、内容区使用率、alignment、margin / padding / gap、overlap / overflow 和失败处理 | spot-check 构图、空白、溢出、重叠、素材比例 |
| R11-R12 | 用 catalog 尺寸设置 wrapper aspect-ratio；素材填满容器且无可见框 | 扫描错比例容器、错误 object-fit、`width + max-height/height`、素材容器露底和可见框模式 | 抽帧检查裁切、变形、letterbox / pillarbox / 容器露底 / 素材框感 |
| R13-R14 | 布局计算排除字幕安全区；使用单个全局字幕容器和 calibrated subtitle units；横屏单行、竖屏最多两行 | 检查安全区、字幕 CSS、按朝向的最大行数与行高、遮罩宽度、`subtitle-units.json` 来源、切换 timing 和非字幕元素侵入 | 抽帧检查字幕位置、行数、遮罩宽度、遮挡和 timing |
| R15-R17 | 确保素材占主体、清晰完整、元素不越界不重叠、字号/对比度达标 | Scene Visual Audit 检查 media dominance、bounds、overlap、typography 和 contrast | spot-check 画面清晰度、放大比例、重叠、越界、字号、对比度 |
| R18 | 为素材 / 文本 / callout 设计持续动效和转场 | 扫描廉价覆盖层动效和缺失转场 | 静帧检测和 spot-check 扫描线 / sweep / 图片持续 motion / scene transition |
| R19 | 文本元素绑定完整旁白句子；入场有初始态 | 扫描 blanket `immediateRender:false` 和 text beat 累积 | 旁白对齐抽样 + spot-check 文本提前 / 累积 |
| R20 | 按 style hint / design file 实现风格；不使用禁用 glow 模式 | 扫描 glow / orb / spotlight 和内容区大块空白 | spot-check 空白、模板感和深色技术风漂移 |
| Customized rules | authoring 时逐条覆盖 handoff rules | `DESIGN.md` 记录每条覆盖方式 | 可见规则进入 spot-check / narration alignment |

新增或调整规则时，同步更新本表。
