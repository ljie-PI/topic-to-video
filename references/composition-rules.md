# Composition Rules

本文件记录 Phase 8 HyperFrames composition 的固定规则。项目变量、实际输入路径、style hint 和用户定制约束来自 `composition-handoff.md`。

## 外部 Skill 优先级

Phase 8 必须读取 `hyperframes`、`hyperframes-animation` 与 `hyperframes-cli`；其中 `hyperframes-animation` 先用于 R18 的能力发现。`hyperframes-keyframes` 及 GSAP / Anime.js / WAAPI / CSS / Lottie / Three.js / TypeGPU 等具体 adapter 按选中的机制加载。若外部 skill 的示例、推荐实践或默认模式与本文件规则冲突，一律以本文件为准。


## Scope and Required References

- 本文件是 Phase 8 hard constraints 的权威来源；HyperFrames sub-agent 必须读取工作区本地副本 `references/composition-rules.md`。
- sub-agent 必须完整读取 `composition-handoff.md`、`references/composition-rules.md`、`references/composition-stage-protocol.md`，并读取 `references/layout-routing.md` 的 required global sections + 当前 scene 命中 sections、`references/animation-routing.md` 中当前 scene 命中的 routing sections，以及 handoff 指定的 `references/design-<theme>.md`（如有）。
- 如果 `composition-handoff.md`、`references/composition-rules.md`、`references/layout-routing.md`、`references/animation-routing.md`、`references/composition-stage-protocol.md` 或指定 design file 不存在 / 不可读，必须停止并反馈主 agent，不得凭默认审美继续制作。
- `composition-handoff.md` 可以补充 user-derived customized rules，但不得修改或覆盖本文件。
- 若 customized rule 与本文件冲突，sub-agent 必须以本文件为底线，并在 `composition/DESIGN.md` 记录冲突处理。

## Hard Rules Index

authoring 前先通读本索引，逐条对照；每条 MUST / MUST-NOT 的完整定义见下方同名小节。
数值阈值统一在 `Shared Thresholds` 定义一次，规则正文只引用标签（如 `T-FIT`），不重述。

| Rule | MUST / MUST-NOT（一行摘要） | 详见 |
| --- | --- | --- |
| R1 | 只用 `voice_clone/narration.mp3`；不重生成 TTS / 不调 HyperFrames TTS；裁剪源片段用 `-an` | [R1](#r1--final-audio-only) |
| R2 | 时间以 `transcribe/transcript.json` 为准；字幕读 `subtitle-units.json`；切换偏移 `<= T-SUB` | [R2](#r2--transcript-timing) |
| R3 | 素材经 `material-catalog.json` 解析；`scene-material-suggestions.json`=硬分配；`scene-text-plan.json` 不覆盖分配、不遮素材 | [R3](#r3--material-catalog) |
| R3a | 生成的旁白 / 字幕 / 屏幕文字 MUST-NOT 出现网页链接或"链接放在下面"类引导 | [R3a](#r3a--no-generated-web-links) |
| R4 | 字体只用本地 `fonts/`，MUST-NOT 依赖系统 `fc-match` | [R4](#r4--local-fonts) |
| R5 | 每 scene 根元素稳定 `data-scene-id/start/end` + `data-layout-role`，跨比例标 `data-cross-aspect-strategy`；素材元素在 scene 内；continuation group 标 `data-continuation-group/index` | [R5](#r5--scene-identity) |
| R6 | 每素材默认恰好一个 scene；`no_match` 用纯排版；仅已声明 continuation group 可跨相邻 scene 复用 | [R6](#r6--material-uniqueness) |
| R7 | 普通 scene `T-DUR`；超时拆分；避免连续微 scene | [R7](#r7--scene-duration) |
| R8 | 每 scene 单独 authoring，MUST-NOT 套统一模板；按 `material × layout_role × visual_role × orientation` 解析 `references/layout-routing.md`；缺失 `layout_role` 按素材 fallback，缺失 `visual_role` 不虚构 | [R8](#r8--scene-specific-layout) |
| R9 | 容器比例来自 catalog `width/height`；素材标 `data-ratio-bucket`；MUST-NOT 默认 16:9 / 错比例 `cover` 裁切 / 拉伸 / letterbox / pillarbox | [R9](#r9--material-aspect-ratio) |
| R10 | 素材容器紧贴无框；MUST-NOT 同写 `width` + `max-height/height`；`viewport_reveal` 外层标 `data-reveal-viewport` | [R10](#r10--material-container) |
| R11 | 素材占内容区主体、清晰完整；cross-aspect 过 `T-FIT` 或转 reveal；scale 落在 `T-MEDIA` | [R11](#r11--media-dominance-and-quality) |
| R12 | 所有元素完整在画面内；前景 MUST-NOT 压素材关键区域（hero 也不例外）；video overlay 受限 | [R12](#r12--bounds-and-overlap) |
| R13 | 分栏两列垂直跨度大致对齐；信息列 MUST-NOT 上堆内容、下留大空白 | [R13](#r13--split-column-vertical-balance) |
| R14 | 文字居中；内容区纯空白 <10%；区域填满或对称留白；MUST-NOT 用 glow 充当层次；满足 `T-GEO` | [R14](#r14--style-constraints) |
| R15 | 字幕安全区贴合实际（`T-SAFE`）；内容区按 `viewport - safe area`；前景 MUST-NOT 进安全区 | [R15](#r15--subtitle-safe-area) |
| R16 | 单个全局字幕容器，底部锚定；横屏单行 / 竖屏最多两行；遮罩 shrink-to-fit，MUST-NOT 固定 `width:100%` | [R16](#r16--global-subtitle) |
| R17 | 字号 / 对比度 / 嵌套 / 字号下限见 `T-FONT`；主标题 MUST-NOT 出现孤行 widow | [R17](#r17--typography-dom-contrast) |
| R18 | 动画按语义 → 主体 → role / layout → continuity → effect → runtime 选择；静态素材须有内容驱动变化；相邻 scene 需转场；MUST-NOT 用统一 fade / Ken Burns 或廉价覆盖层凑动效 | [R18](#r18--semantic-animation-motion-and-transitions) |
| R19 | 多个非素材文本随旁白句子逐个出现，MUST-NOT scene start 全亮；入场需正确初始态 | [R19](#r19--text-timing-and-entrance-state) |
| R20 | `composition/DESIGN.md` 记录每 scene inventory（见 R20 清单） | [R20](#r20--scene-inventory) |
| R21 | peak-state audit：无溢出 / 遮挡 / 压素材 / letterbox；构图均衡；结构型 role 竖屏 MUST-NOT 横排 | [R21](#r21--peak-state-layout-audit) |

## Shared Thresholds

以下命名阈值是规则正文与 `references/composition-stage-protocol.md` 的唯一数值来源；
修改数值只改这里，规则与 stage protocol 用标签引用，避免多处漂移。
`竖向素材` 指 `ratio_bucket` 为 `tall` / `ultra-tall` 的竖图 / 竖视频；分桶分类以 `material-catalog.json` 源 `width` / `height` 为准，不由 authoring 属性改写。

- **T-SUB — 字幕同步**：字幕切换与音频偏移 `<= 0.2 秒`。
- **T-DUR — scene 时长**：普通 scene 目标 `5-8 秒`；超过 `8 秒` 必须拆分；避免连续多个 `< 3 秒` 微 scene。
- **T-RATIO — 素材宽高比分桶**：`r = 源宽 / 源高`，源尺寸取自 `material-catalog.json`。`ultra-wide` / `strip` `r >= 2.4`；`wide` `1.20 <= r < 2.4`；`square-ish` `0.90 <= r < 1.20`；`tall` `0.50 <= r < 0.90`；`ultra-tall` `r < 0.50`。竖向素材 = `tall` + `ultra-tall`，`r < 0.90`。
- **T-REVEAL — `viewport_reveal` 窗口尺寸**：
  - 横屏 reveal 窗口：宽 `0.5-0.7 * CW`、高 `0.75-0.90 * CH`。
  - 竖屏 / 竖向 reveal 窗口：宽 `0.8-1.0 * CW`、高 `0.5-0.8 * CH`。
- **T-FIT — cross-aspect 完整适配显示 `full_fit`**：
  - `full_fit` 只用于 `square-ish` 或接近输出比例的素材。接近输出比例：`|r - r_out| / r_out <= 0.15`，`r_out = 输出宽 / 输出高`。
  - `tall` / `ultra-tall` 只有接近输出比例时可 `full_fit`。其他竖向素材 MUST-NOT 缩宽度硬塞，必须改 `viewport_reveal` / `detail_callout` / 替换素材；仅当完整合法 continuation metadata 已存在时可保持 `media_continuation`。
  - **达标尺寸**：横屏 `MH >= 0.78 * CH`；竖屏 / 竖向 `MW >= 0.80 * CW` 且 `MH >= 0.45 * CH`。
  - **禁止窄条**：full_fit 后 `MW` 由素材原始比例自然推导，剩余侧向 / 上下空间 MUST 构成通过 `T-GEO` column occupancy 的信息区，不得留裸 gutter，也不得把主素材缩成不可读窄条。
- **T-MEDIA — media dominance / 缩放**：
  - 有素材 scene，素材占内容区主体，通常 `>= 50%`。
  - 横屏 16:9 / wide 主证据媒体通常达内容区高度 `70-85%`，低于约 `70%` 必须改布局。
  - 横屏 `<video>` 主媒体必须宽度顶满 `MW >= 0.90 * CW`；仅当 catalog 源尺寸即使放大到 `1.5x` 仍达不到 `0.90 * CW` 时可例外，并记 `composition/DESIGN.md`。横屏宽图 / 截图可用分栏 slab（宽 `>= 0.50 * CW`），不受此宽度要求约束。
  - rendered size 的 scale factor 优先保持原始素材尺寸 `0.8x-1.5x`，超出必须替换素材或调整布局。
  - 多素材并列时，每个素材 `rendered_area / (CW * CH) >= 0.30` 且仍可读。
- **T-GEO — 确定性几何 gate**：命中任一 finding 时，peak-state audit 失败。content coverage 抓"整体内容团太小"，center clustered 抓"内容挤在中间"，interior void 抓"标题在顶 / 内容聚中导致的垂直大断层"（因 union 含顶部标题，coverage 可能虚高，此形态由 interior void 兜底）。

  | Check | Threshold | Finding |
  | --- | --- | --- |
  | 无素材 content coverage | 可见非字幕内容 union 必须 `union_width / CW >= 0.75` 且 `union_height / CH >= 0.75` | `underfilled_content_area` |
  | 有 catalog 素材 content coverage | 可见非字幕内容 union 必须 `union_width / CW >= 0.80` 且 `union_height / CH >= 0.75` | `underfilled_content_area` |
  | 中心聚集 | `union_width < 0.75 * CW`、`union_height < 0.65 * CH`、中心偏移均 `< 0.15` | `center_clustered_layout` |
  | 无素材 outer gutter | 单侧外部空白 horizontal `<= 0.20 * CW`；vertical `<= 0.20 * CH` | `oversized_gutter` |
  | 有 catalog 素材 outer gutter | 单侧外部空白 horizontal `<= 0.15 * CW`；vertical `<= 0.15 * CH` | `oversized_gutter` |
  | 卡片 / 面板内部填充 | 有可见 surface（border / 底色 / shadow）且非整屏的容器，`height_occupancy >= 0.60` | `underfilled_container` |
  | 主文本块 / 卡片 / 节点 gap | 相邻主内容间距 `>= max(min(CW, CH) * 0.02, 20px)` | `tight_text_gap` |
  | 垂直空白带 | 内部空带 `interior / CH <= 0.15`；单侧边缘空白 `edge / CH <= 0.30` | `uneven_vertical_distribution` |
  | 横屏 video 宽度 | `<video>` 主媒体 `MW / CW >= 0.90`（源尺寸放大 `1.5x` 仍不足时例外） | `undersized_media` |

- **T-FONT — 字号 / 对比度 / 嵌套下限**：
  - 字号比例：同一 scene 内最大 / 最小字号 `<= 3:1`；素材 / 文本容器最多 `2` 层嵌套。
  - 颜色对比度：正文 `>= 4.5:1`，大字号标题 `>= 3:1`。
  - 字号下限（横屏 / 竖屏）：decorative metadata / chrome label 可低至 `18-20px`（不承载主信息）；badge / chip / rank label `>=22px / >=24px`；body / supporting detail `>=28px / >=30px`；callout / card text `>=32px / >=34px`；header / eyebrow（scene 语义锚点）`>=28px / >=30px`。
  - 无素材 scene 主信息文字：横屏 `>= 36px`，竖向 / 竖屏 `>= 38px`。低于阈值或文本框明显偏小视为 `undersized_text`。
  - 字号微调最多缩到当前字号的 `0.9` 倍，且不得低于对应文本类型下限。
- **T-SAFE — 字幕安全区**：安全区高度贴合字幕条实际占位（行数 × 行高 + 小边距），不得显著更大。
  - 横屏 `1920x1080`（单行）：约 `9-12%`（1080p 约 `97-130px`）。
  - 竖向 `1080x1440`：约 `150-220px`；竖屏 `1080x1920`：约 `220-300px`。
  - 字幕容器 `bottom` 为视口高度 `3-5%`（1080p 约 `32-54px`）。
  - 最大行数：横屏每单元最多 `1` 行；竖屏 / 竖向每单元最多 `2` 行（禁止第三行及以上）。
- **T-MOTION — 动效重复上限**：同一类图片主运动不得重复超过 `ceil(total_images / 5)` 次。`total_images` 按 catalog 图片在 scene 中的实际使用次数统计；同一合法 `media_continuation` group 内的重复素材合并计为 1 次。每个图片 scene / continuation group 在 `composition/DESIGN.md` 记录一个规范化 `primary_motion_family`：优先使用 HyperFrames rule / effect id；自定义机制使用稳定 kebab-case 名称。仅修改距离、时长、ease 或方向仍视为同一 family。Phase 8.3 必须按该字段做确定性计数。

## Rule Definitions

### Input and source rules

#### R1 — Final audio only

`voice_clone/narration.mp3` 是最终解说音频。不要重新生成 TTS，也不要调用 HyperFrames 的 TTS。若从 catalog 视频裁剪源片段，必须用 `-an` 去掉源音频。

#### R2 — Transcript timing

时间边界以 `transcribe/transcript.json` 为准。scene 切分和非字幕 text beat 出现时机必须绑定到该 transcript 的句子 / 分句边界。最终字幕必须读取 `transcribe/subtitle-units.json`：subtitle unit 的 timing 来自 transcript 句子 / 词时间，display text 以 transcript 文本为底，并可包含 `narration.txt` 高置信度匹配带来的 Latin words 拼写修正。字幕切换与音频偏移不超过 `T-SUB`。

#### R3 — Material catalog

所有以素材为底的视觉都必须通过 `material-catalog.json` 解析；需要 catalog 素材时不得凭空造 stock 视觉。`scene-material-suggestions.json` 如存在，视为素材到 scene 的硬性分配。`scene-text-plan.json` 如存在，视为非字幕屏幕文本块的结构化建议；它不能覆盖素材分配，也不能要求前景文本遮挡素材。

#### R3a — No generated web links

生成的旁白、字幕和屏幕文字不要出现网页链接，也不要说“链接放在下面”“点击下方链接”等链接引导。需要标来源时用“官方文档”“GitHub”、产品名、repo 名或论文名；URL 只留在 metadata 中。此规则只约束生成文本，不处理素材截图或录屏里原本存在的 URL。

#### R4 — Local fonts

字体加载使用 `fonts/` 下的本地资源，确保可复现；不要依赖系统 `fc-match`。

### Scene structure and timing rules

#### R5 — Scene identity

`composition/index.html` 中每个 scene 根元素必须同时有稳定的 `data-scene-id`、`data-scene-start`、`data-scene-end`。所有 `<img>` / `<video>` / `background-image` 素材元素必须位于某个 scene 根元素内部；使用 CSS `background-image` 承载 catalog 素材时，该元素必须带 `data-material-ref` 或等价 material / media 标记，便于 QA 区分素材背景与装饰 shell。属于同一 continuation group 的相邻 scene 必须在 scene 根元素上标记同一个 `data-continuation-group`，值等于 Phase 5.2 的 `continuation_group_id`，并用 1-based `data-continuation-index` 表示 group 内顺序，便于 QA 识别合法连续复用。每个 scene 根元素还 MUST 带 `data-layout-role`。跨比例 scene 根元素 MUST 带 `data-cross-aspect-strategy`，值域为 `full_fit` / `viewport_reveal` / `detail_callout` / `media_continuation` / `replace_material`。重渲修复时，未受影响 scene 的 DOM / CSS / 动画和时间区间必须保持不变。

#### R6 — Material uniqueness

默认每个 catalog 素材（图片 / 视频 clip）在整片中恰好出现在一个 scene，分配以 `scene-material-suggestions.json` 为准；若 scene 使用 `material_refs`，数组内每个素材都视为该 scene 占用。`no_match` scene 用纯排版 / 文字卡片，不借用其他 scene 的素材。例外：论文 figure、技术架构图、UI 截图、流程图等可以在连续的 continuation group 中跨相邻 scene 复用同一 catalog 素材。group 起点可保留主布局角色（如 `media_first` / `video_first` / `viewport_reveal`）并标注 `continuation_group_id`，但不写 `continuation_of`；后续跨 scene 复用素材的 scene 必须标注 `layout_role = "media_continuation"`、相同 `material_ref`、相同 `continuation_group_id`，并用 `continuation_of` 指向 group 起点的 `scene_index`；未声明的跨 scene 素材复用仍视为违规。

#### R7 — Scene duration

普通 scene 目标时长见 `T-DUR`；超过上限必须拆分，连续多个过短的微 scene 应避免。连续同素材合并而成的 scene 可以超过 `T-DUR` 上限，但 scene 内文本信息单元仍须按 `T-DUR` 节奏刷新，并受 R18 / R19 约束。

### Layout and composition rules

#### R8 — Scene-specific layout

每个 scene 必须由 coding sub-agent 按 scene 单独 authoring，不得套统一模板后只替换文字 / 图片。排版输入包括：

- 旁白文本与 `scene-material-suggestions.json` 的 `text_beats` / `material_ref` / `material_refs` / `layout_role`；
- `scene-text-plan.json` 中对应 scene 的 `visual_text_units`（如存在）；
- `material-catalog.json` 中对应素材（单个 `material_ref` 或 `material_refs` 中所有素材）的尺寸、类型、`layout_affordance` 和 `focal_region`（如存在）；
- 内容区尺寸（viewport - 字幕安全区 - scene padding）。

输入解析有以下 hard invariants：`scene-text-plan.json` 与 `scene-material-suggestions.json` 必须按 `scene_index` 对齐，不得按数组位置猜测；先解析素材 assignment / `layout_role` / catalog geometry，再解析 visual text units；`visual_role` 及其中英文直译不得作为可见文案，可见文字只能来自 `display_text` / `supporting_points` / 对应真实内容字段；`priority: primary` 的 unit 必须尝试实现，其他 priority 的降级须记录；`template_hint` 与 role、table / chart shape、素材或 orientation 冲突时必须忽略并记录。只有已有 `chart` unit，或 `data_table` 明确提供可 chart 的 numeric series / highlighted dimensions 时，才能把 table 转为 chart presentation；chart 只能表达可比较数值、趋势、占比或分布，文本密集表不得硬转。small table（≤3 rows、≤3 columns、cells short）可 compact；medium（4–8 rows 或 4–5 columns）必须 highlight / summarize / paginate；large（>8 rows 或 >5 columns）不得整表硬塞，必须 summarize / paginate / split。

Phase 8 必须按素材比例、输出朝向、`layout_role`、text beat 数量和 visual text unit 类型选择 layout。`1080x1440` / `1080x1920` portrait / vertical MUST-NOT 直接复用 landscape 右侧栏 / horizontal side-rail 主结构，即使勉强未触发字号或溢出 finding；必须按纵向信息层级重新组织。role 来源、缺失 fallback、解析顺序、冲突处理和 `material × layout_role × visual_role × orientation` 候选布局见 `references/layout-routing.md`；它是软路由，不得覆盖本文件。建立 scene inventory 后先读其 role authority / fallback definitions / input alignment / resolution order / global density and degradation，再读取当前 scene 命中的 material、layout role、orientation、visual role（如有）及最终 presentation / `cross_aspect_strategy` 行。相邻 scene 不得无理由复用同一主版式，但声明过的 continuation group 应保持同一主素材稳定显示。

下文涉及尺寸阈值时，`CW` / `CH` 是扣除 scene padding 与字幕安全区后的内容区宽 / 高；`MW` / `MH` 是主素材在 peak state 的实际渲染宽 / 高，仅用于 Phase 8 authoring 和 QA 测量。跨比例素材不能只按完整适配显示处理；必须先验证主素材是否达到可读宽高，未达标时切换为 `viewport_reveal`、`detail_callout` 或替换素材；仅当完整合法 continuation metadata 已存在时可保持 `media_continuation`。上游已提供合法 `visual_role` / `layout_role` 时优先执行；缺失 `layout_role` 时按 `references/layout-routing.md` fallback 推导；`scene-material-suggestions.json` 存在时，scene 缺少 `material_ref` / 非空 `material_refs` 且未显式 `no_match: true`，或 `no_match` 与素材 assignment 并存，均是 malformed handoff；不完整 continuation metadata 或未声明的跨 scene 素材复用同样是 handoff conflict，不得 fallback；`media_continuation` 只可在完整合法 metadata 已存在而 role 字段漏标时补全。缺失 `visual_role` 时不得虚构，应按旁白、`semantic_intent`、`primary_subject`、text beats 和素材直接选 layout；role 与 R9–R15 冲突时保留语义意图并选择合法 presentation / `cross_aspect_strategy`，在 `composition/DESIGN.md` 记录，不得静默硬套或随意改写 role。

#### R9 — Material aspect ratio

素材容器比例必须来自 `material-catalog.json` 的 `width` / `height`。将 `width / height` 作为 wrapper `aspect-ratio`；字段为 `null` / 缺失时才 fallback 到运行时实测或 ffprobe。禁止默认 16:9，禁止用错误比例容器 + `object-fit: cover` 裁掉素材，禁止因比例错误产生拉伸、letterbox 或 pillarbox。ultra-wide / strip 使用 `band` 时必须保持足够高度和可读性，不得完整缩成细线；不满足时改 `viewport_reveal`、分时或拆 scene。`viewport_reveal` 外层可使用 scene-appropriate ratio，内层素材仍必须保持原始比例。承载 catalog 素材的 `<img>` / `<video>` / `background-image` 元素 MUST 带 `data-ratio-bucket`；取 `T-RATIO` 分桶值，权威分类仍以源尺寸为准。

#### R10 — Material container

普通素材容器必须紧贴素材：容器无可见 border / outline / padding / shadow / glow / inset / 卡片底色，素材本身填满 wrapper（如 `width: 100%; height: 100%`）。素材尺寸不适合时，调整布局 / 缩放 / 换素材，不用外框或底色遮丑。容器与素材的 transform / 动效必须绑定在同一元素或一组同步元素上，避免素材跑出容器或容器露边。不要在同一素材容器上同时写死 `width` 和 `max-height` / `height`，否则显式尺寸会覆盖 `aspect-ratio` 推导，造成容器底色 / letterbox 暴露。

Recommended authoring pattern:

```css
.media-panel {
  aspect-ratio: <W> / <H>;
  width: min(<availW>px, calc(<availH>px * <W> / <H>));
  height: auto;
  margin: 0 auto;
}
```

`viewport_reveal` authoring pattern:

```css
.reveal-viewport {
  overflow: hidden;
  /* scene-appropriate ratio, not necessarily source ratio */
}
.reveal-viewport > img,
.reveal-viewport > video {
  width: auto;
  height: 100%;
  max-width: none;
  max-height: none;
}
```

`viewport_reveal` 的 marker 是必要声明但不是 eligibility 依据。authoring 可依据 catalog 源尺寸、预估内容区和输出 orientation 暂定 reveal 路由，但该预判不构成 eligibility 或 gate pass；只有 Phase 8.3 按 R9–R11 实测后证明素材为 cross-aspect / 极端比例且 `full_fit` 未通过 `T-FIT`，或 `video_first` / `detail_callout` 有 catalog `focal_region`、start / mid / end / avoid-region 支持的局部窗口需求，才能确认使用。实测未通过时必须重新路由，不能进入 render。符合条件时 scene root MUST 标记 `data-cross-aspect-strategy="viewport_reveal"`，`layout_role = "viewport_reveal"` 时也必须满足同一 eligibility。显式上游 `layout_role` 可保留其语义，实际 presentation 通过该 strategy 声明；不得仅因作者自行添加 marker 就使用 reveal，也不得静默改写上游 role。外层容器可使用适合 scene 的比例并 `overflow: hidden`；内层图片 / 视频必须保持原始宽高比，不得拉伸。短边对齐容器，长边溢出并沿长轴慢速 pan / scroll；必须使用 catalog `focal_region`、start / mid / end 关键区域说明或 avoid-region 来选定 reveal 窗口和 pan 路径。reveal viewport 尺寸见 `T-REVEAL`。不得出现 letterbox / pillarbox / accidental clipping。reveal 外层裁切容器 MUST 带 `data-reveal-viewport`，便于确定性 gate 测量窗口尺寸是否落在 `T-REVEAL`。

#### R11 — Media dominance and quality

有图片 / 视频素材的 scene，素材应占据内容区主体，见 `T-MEDIA`，禁止缩成角落邮票贴在大段文字旁。catalog 中的论文 figure / table / chart 必须保留来源图形和可读结构，只用外置信息解释关键结论；不得重画完整表格，也不得永久遮挡、遗漏或抽取轴线、图例、caption、关键曲线、必要 rows / columns。非 reveal peak frame 必须保持必要结构完整；合法 `viewport_reveal` / `detail_callout` 可在单帧显示局部窗口，但 start / mid / end 或 proof sequence 的聚合覆盖必须遍历所有必要结构。“只保留 primary rows / columns / points”、分页或重组只适用于 `scene-text-plan.json` 提供的 structured `data_table` / `chart` visual unit，不适用于 catalog source graphic；catalog source 需要简化时只能精简外置解释、使用 reveal 遍历必要结构或拆 scene。`video_first` 和 `media_first` 的主媒体应优先最大化可视区域：横屏输出中的横屏视频 / 清晰横图通常宽度对齐内容区；竖屏 / 竖向输出中的横屏视频 / 横图通常作为上半屏或中上部 media slab，避免缩成小图。主媒体尺寸必须同时按内容区可用宽度和高度计算，不能只用固定 max-width 导致横屏 wide media 高度过低；横屏中作为主证据的 16:9 / wide image 或 video slab 的高度占比与低于阈值必须改布局的条件见 `T-MEDIA`。tall / ultra-tall 竖向素材 `full_fit` 只按 `T-FIT`。不满足时不得继续缩宽度，MUST 改宽度驱动 reveal。Catalog 图片 / 视频的 rendered size 按主要可见边或短边计算，scale factor 范围见 `T-MEDIA`；超出范围时必须替换素材或调整布局。多素材 scene 两个素材可用 `comparison_pair`，三个及以上优先 `comparison_sequence` / carousel / 拆 scene；`comparison_sequence` MUST-NOT 默认三等分或不可读小宫格。如必须并列，每个素材占比见 `T-MEDIA` 且仍可读。图片必须清晰、关键信息完整，原图分辨率应覆盖渲染尺寸，不得可见模糊、像素化、JPG artifacts 或裁掉文字、图表轴线、人物面部、UI 主控件等关键信息。

#### R12 — Bounds and overlap

所有视觉元素必须完整位于画面内，不得截断。除全局字幕条覆盖底层画面外，任何前景标题、caption、tag、badge、callout、label、数据块都不得压在图片 / 视频素材关键区域之上，包括 hero 素材。`video_first` 中视频占满或接近占满画面时，允许少量半透明文本框浮在视频上，但必须 shrink-to-fit、短文本、停留时间短、位置稳定，并避开主体动作、鼠标 / 手势、按钮、代码高亮、图表主线、人物脸部和 catalog `focal_region`；不得用长段落或整行遮罩压视频。

#### R13 — Split-column vertical balance

媒体列 + 信息列 / 左右分栏中，两列垂直跨度必须大致对齐；信息列不得只在上部堆内容、下部留大块空白。信息列内容稀疏时，用 `metric_strip` / `list` 等多元素 role 拆出更多条目（随旁白逐个出现）、增高卡片或重新纵向分布，使列内元素纵向均衡填满列高。pills / tag / metadata 等收尾元素不得孤立钉在底边、与上方内容隔一大段空白；应靠近主内容或参与列内纵向分布。单卡仅承载 1-2 短行且四周大留白时，必须增密、并入等高容器或重排，不得作为一列的唯一内容。

#### R14 — Style constraints

文字框内文字应垂直 / 水平居中。内容区不得出现 >10% 视口面积的纯空白；字幕安全区不计入空白统计，也不得为填满而把内容元素铺进该带。任意承载内容的区域 / 列（含无边框 flex / grid 列、文本列）必须填满该区域，或令留白对称分布；不得单边贴边或外侧留大块空白。文本 / 数据应使用整区宽度；区域内容稀疏时，收窄或重新居中容器。配对区域（媒体列与文本列、左右分栏）的外侧边距必须大致对称。如需呼吸空间，用极淡装饰 / 网格 / 角标占位。Moon / 深色技术编辑风默认纯色 + 极淡网格 / 细线 / 低对比结构，禁止 `radial-gradient` spotlight、localized glow、ambient orb、neon halo、发光阴影和用 glow 充当层次感。

确定性几何检查阈值见 `Shared Thresholds` 的 `T-GEO`。

只计入可见文本、素材、图形、卡片和 callout；隐藏元素、透明占位、空容器和撑尺寸 wrapper 不计入 union。deliberate hero / quote / title-card 留白必须同时写入 `composition/DESIGN.md`，并在 scene root 标记 `data-layout-exception="hero"`、`"quote"` 或 `"title-card"`；`data-qa-layout-exception` / `data-geometry-exception` 可用同值。该例外只豁免 `underfilled_content_area`、`center_clustered_layout`、`oversized_gutter`、`underfilled_container`、`uneven_vertical_distribution`、`undersized_media`。

### Subtitle rules

#### R15 — Subtitle safe area

视口底部预留专属字幕安全区，尺寸见 `T-SAFE`：高度必须贴合字幕条实际占位（字幕行数 × 行高 + 上下小边距），不得显著大于字幕条本身，也不得为了"保险"长期预留过大高度。只有双行字幕、较大字号、复杂背景或 subtitle mask 需要更多呼吸空间时才靠近上限。authoring 时内容区必须按 `viewport - subtitle safe area` 计算；除全局字幕条外，任何前景文本 / callout / 素材 / 装饰不得进入该安全区。全幅背景素材可延伸到安全区下方垫底，此时字幕条用半透明遮罩压在其上。

#### R16 — Global subtitle

字幕必须使用单个全局容器，固定锚定在底部字幕安全区内并与安全区上下贴合（容器 `bottom` 值见 `T-SAFE`），全片水平居中且基线稳定。字幕容器必须从安全区底部向上排版（如 `bottom` 锚定 + 文本底对齐），行数变化时基线稳定、不上下跳动。字幕单元来自 `transcribe/subtitle-units.json`。收窄 subtitle safe area 的前提是严格执行 `T-SAFE` 规定的最大行数：横屏每个单元最多 1 行（如 `white-space: nowrap`）；竖屏 / 竖向每个单元最多 2 行（通过 `max-width` 自动换行，明确禁止第三行及以上）。无论横竖屏，如果某个 unit 在该朝向允许的最大行数内仍放不下，必须回到 transcript-timed unit 拆分逻辑，把它拆成更小的 calibrated units；不得扩大 safe area 来容纳第三行，不得靠缩字号到下限、放宽 `max-width`、整行遮罩或塞进多余行数。半透明背景遮罩必须 shrink-to-fit，随文字宽度自适应并保证任意画面背景下可读；禁止固定 `width: 100%`、大 `min-width` 或整行遮罩。

### Typography rules

#### R17 — Typography, DOM, contrast

字号比、嵌套层数、对比度和各文本类型字号下限见 `T-FONT`。主标题优先单行；如果必须两行，每行都应保留有意义词组。禁止第二行只有 1-2 个汉字、一个短英文 token 或孤立标点。遇到标题孤行时，必须通过缩短 `display_text`、扩大文本框、微调字号、调整断句、改为 title + subtitle、或分时 reveal 修复；字号微调下限见 `T-FONT`。

无素材 scene 主信息文字下限见 `T-FONT`；承担主叙事锚点的标题 / 数字 / 核心结论必须明显大于正文。低于阈值，或文本框宽高明显小于内容区可用尺度时，视为 `undersized_text`。`data_block` / `metric_strip` 等数据 role 的数值必须显著突出，并使用 tabular numerals（如 `font-variant-numeric: tabular-nums`）保持变化与对齐稳定。

### Motion and text-timing rules

#### R18 — Semantic animation, motion and transitions

动画必须由 scene 的旁白语义、primary subject、信息变化和 scene handoff 驱动，不得只按 `visual_role`、`layout_role` 或 runtime 名称套固定效果。`references/animation-routing.md` 是候选机制和 runtime 的软路由，不是 `visual_role → effect` 的一对一模板；本节是动画选择与质量底线的权威规则。

**Capability discovery。** authoring 前，HyperFrames sub-agent MUST 加载 `/hyperframes-animation` 并读取其 `rules-index.md`、`blueprints-index.md`、`transitions/overview.md`、`transitions/catalog.md` 与 `techniques.md`，以当前安装版本的 skill 索引作为动画能力 source of truth。需要 shared element / FLIP、path、mask、SVG morph/draw、DOM 3D、Three.js / WebGL keyframes 时再加载 `/hyperframes-keyframes`。先确定候选 effect / blueprint，再读取对应 recipe 和实际使用的 adapter；不得为了“丰富”而无目的混用多个 runtime，也不得只凭记忆反复使用 fade / slide / Ken Burns。

**Selection order。** 每个 scene 必须按以下顺序确定动画：完整旁白句子与 `semantic_intent` → `primary_subject` 及要证明的状态变化 → `visual_role` 提供的信息动画候选 → `layout_role`、素材比例、`focal_region`、continuation 状态施加的运动边界 → orientation、density、可读时间和前后 scene continuity → `signature_mechanism` 与少量 supporting mechanisms → 最后选择最小合适 runtime。允许选择 `references/animation-routing.md` 未列出的 mechanism，前提是更清楚地表达 scene 语义，并在 `composition/DESIGN.md` 记录候选、选择和理由。

**Content-driven progression。** 每个 scene 应有一个可辨认的 `signature_mechanism`，并在 scene 时长内通过 staged reveal、camera intent、UI state change、data progression、focal traversal、annotation progression 或其他主体行为持续推进理解。静态图片必须有这种内容驱动的持续视觉行为；单纯 idle drift、breathing、glow pulse 或无目标缓移不能单独满足本规则。视频素材可视为自带运动；接近静止的视频按静态图片处理。同类图片主运动重复上限见 `T-MOTION`。

**Role / layout semantics。** 存在 `visual_role` 时，它只产生候选机制，不强制固定 effect；同一 role 可因旁白动作、素材、orientation 和 scene continuity 使用不同动画。没有 `scene-text-plan.json` / `visual_role` 的合法 scene 以 `semantic_intent`、`primary_subject` 和要证明的状态变化为主，不得为了路由而虚构 role。`layout_role` 约束运动边界：`media_first` / `video_first` 必须保持素材主体地位；`viewport_reveal` 必须沿长轴覆盖 catalog 记录的 start / mid / end、`focal_region` 或避开 avoid-region；`detail_callout` 只允许外置 annotation 与 focal emphasis；`comparison_pair` / `comparison_sequence` 必须保持各素材可读。portrait / vertical 中 animation geometry 必须跟随 R8 的按朝向布局，不得保留横屏 choreography 后靠缩字号 / 缩素材硬塞。

**Continuity and transitions。** 普通相邻 scene 需要显式 transition / motion handoff，避免无设计的硬切；全片应建立稳定的 primary transition vocabulary，只在 topic change、climax 或 outro 使用少量 accent transition，不得每场随机换一种转场。连续相邻 scene 不得无理由重复完全相同的 `entry + information reveal + transition` 组合；声明过的 continuation group 可保持 motion family，但仍须通过文本、callout、局部标注、`focal_region` emphasis 或信息状态变化推进叙事。`media_continuation` group 内主媒体层必须稳定，不得对主图 / 视频做 full-scene fade、wipe、slide-out、re-enter 或重新加载式入场；只允许文字、callout、局部高亮、轻微镜头推进或信息区替换。

**Runtime discipline。** Runtime 是实现选择，不是视觉丰富度指标。GSAP 是 timeline / stagger / SVG / camera choreography 的默认；CSS animations / WAAPI 用于简单有限 keyframes；Anime.js 仅在明确适合或用户要求时使用；Lottie / dotLottie 需要本地动画资产；Three.js / WebGL 用于真实 depth、camera/object、GLTF 或 shader；TypeGPU 用于明确的 WebGPU / WGSL 需求且渲染环境必须支持。所有 runtime 必须符合 HyperFrames 的 seek-safe、同步注册、有限时长和 deterministic contract。handoff 中的 required / preferred runtime 或 effect 只能补充本规则，不能覆盖它；required runtime 与本规则、可用资产或渲染环境不兼容时，sub-agent 必须在 authoring 前停止并把 handoff conflict 反馈给主 agent，不得静默忽略或降级。

**Anti-patterns。** MUST-NOT 把统一 opacity fade、轻微 translate、scale pop 或 Ken Burns 作为所有 scene 的主要动画语言；MUST-NOT 用横贯 / 纵贯扫描线、扫光、sweep、进度条、无语义粒子、持续呼吸或 glow pulse 等覆盖层凑动效；MUST-NOT 为了覆盖更多 skill 而无意义地混用 GSAP、Lottie、Three.js、TypeGPU 等 runtime。

#### R19 — Text timing and entrance state

多个非素材文本元素必须按完整旁白句子逐个出现，禁止 scene start 一次性全亮。多元素 `visual_role` 内部的条目 / 节点 / 行 / 标注也必须随对应旁白逐个出现，不在 unit 首次出现时一次性全亮。scene title / header / eyebrow 与 `visual_text_units[].display_text` / `supporting_points` 不得重复同一句或同一短语；重复时删除标题、改成上位标签，或改写 unit 文本。文本元素服务于哪一句，就在该句开始前短暂提前显示，保证旁白读到该句时相关文本已可见；若对应句靠近 scene 结尾、可见时间过短，可适度提前到同一语义段的铺垫处。若 `scene-text-plan.json` 存在，`priority: "primary"` 的 `visual_text_units` 必须优先实现；`secondary` / `decorative` 可因安全布局降级，但必须在 `composition/DESIGN.md` 记录。旧 text beat 需要淡出或降级，不能永久累积。入场动画必须有正确初始态，避免元素在 tween 前闪现。

### Authoring record and audit rules

#### R20 — Scene inventory

`composition/DESIGN.md` 必须记录每个 scene 的 `scene_id`、旁白摘要、`material_ref` / `material_refs`、material condition、`layout_role` 及来源（explicit / inferred + fallback reason）、实际存在的 `visual_role` 及来源、命中的 `references/layout-routing.md` sections / rows、素材尺寸 / aspect ratio、`ratio_bucket` / `focal_region`（如有）、text beats、`scene-text-plan.json` 中对应的 `visual_text_units`（如有）、最终 layout presentation、peak-state audit 结果，以及每个非素材元素对应的完整旁白句子和出现时间点。每个 scene 还必须记录 `semantic_intent`、`primary_subject`、`sustained_motion_route`、`signature_mechanism`、supporting mechanisms、considered / selected effects 或 blueprint、最终 runtime、narration triggers、transition / continuity strategy、proof times，以及未采用主要候选或手动指定 preference 时的理由。图片 scene / continuation group 另记规范化 `primary_motion_family` 供 `T-MOTION` 计数。`proof_times` 使用 composition absolute seconds，至少命名并覆盖 `entry`、一个或多个 `semantic_progression`、`peak` 和 `handoff`；不适用项写明原因，不得只给无语义的等间隔采样点。对每个已实现的 visual text unit，记录 `unit_id`、`visual_role`、`display_text`、`priority`、来源 text beat、最终 DOM selector、出现 timing、输出朝向、采用的按朝向布局呈现方式；portrait / vertical 时还必须记录为何没有沿用横屏排列，以及过密信息采用的 role-specific 降级方式（纵向节点链、纵向卡片、分页 / 分时主项、focus window、拆 scene）。若某个 `primary` unit 被降级或未实现，必须记录原因。若 scene 存在输出朝向与素材比例冲突，记录 `cross_aspect_strategy`、`CW` / `CH`、`MW` / `MH` 和阈值判断。若使用 `media_continuation`，记录相邻 scene 如何保持同一主素材稳定显示；若使用 `viewport_reveal`，记录 start / mid / end 可见区域和关键内容是否完整出现。

#### R21 — Peak-state layout audit

动画前必须检查每个 scene 的 peak state：所有非字幕元素都显示时，元素不得溢出 viewport / 内容区、不得互相遮挡、前景元素不得无约束覆盖 catalog 素材、素材不得 letterbox / pillarbox、内容区纯空白不得超过 10%、构图不得明显失衡；主要元素组在水平 / 垂直方向上的分布必须均衡，视觉重心不得明显偏上、偏下、偏左或偏右；不得用超大空容器或空 media panel 填充画面来规避全局空白检查。`media_first` / `video_first` 主素材不得被标题或信息块不必要地压小；跨比例主素材必须通过 R11 的 `MW` / `MH` 阈值，未通过时必须切换 `viewport_reveal` / `detail_callout` / 替换素材；仅当完整合法 continuation metadata 已存在时可保持 `media_continuation`；`comparison_pair` 中每个素材必须仍可读。`tall` / `ultra-tall` 竖向素材 `full_fit` 只按 `T-FIT`，其余必须走 `viewport_reveal`。portrait / vertical 中，`leaderboard`、`data_table`、`chart`、`timeline`、`process_flow`、`architecture_diagram`、`network_graph`、`comparison_matrix`、`pros_cons`、`metric_strip`、`list`、`feature_grid`、`qa`、`code_block`、`terminal_block`、`file_tree`、`state_machine`、`annotated_media` 等多元素 / 结构型 unit 不得被横向硬排到文本窄列、字号过小、多次换行或内容不可读。失败必须先调整布局尺寸、位置、字号、信息密度或拆 scene，不得靠“暂时隐藏元素”掩盖问题。`viewport_reveal` 还必须检查 start / mid / end，确认关键内容不会永久隐藏。

Phase 8 几何审计按 `references/composition-stage-protocol.md` 执行；命中 `underfilled_content_area`、`center_clustered_layout`、`oversized_gutter`、`undersized_text`、`tight_text_gap`、`underfilled_container`、`uneven_vertical_distribution`、`undersized_media`、`tall_media_not_revealed`、`reveal_window_out_of_bounds` 或 `fit_below_threshold` 时，peak-state audit 失败。

## Stage Protocols

Phase 8.3-8.7 必须遵循 `references/composition-stage-protocol.md`。

缺失或无法读取 `references/composition-stage-protocol.md` 时，停止并报告缺失引用；不得自拟 audit 流程。