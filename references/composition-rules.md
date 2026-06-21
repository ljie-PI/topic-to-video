# Composition Rules

本文件记录 Phase 8 HyperFrames composition 的固定规则。项目变量、实际输入路径、style hint 和用户定制约束来自 `composition-handoff.md`。

## Scope and Required References

- 本文件是 Phase 8 hard constraints 的权威来源；HyperFrames sub-agent 必须读取工作区本地副本 `references/composition-rules.md`。
- sub-agent 必须读取 `composition-handoff.md`、`references/composition-rules.md`、`references/composition-stage-protocol.md`，以及 handoff 指定的 `references/design-<theme>.md`（如有）。
- 如果 `composition-handoff.md`、`references/composition-rules.md`、`references/composition-stage-protocol.md` 或指定 design file 不存在 / 不可读，必须停止并反馈主 agent，不得凭默认审美继续制作。
- `composition-handoff.md` 可以补充 user-derived customized rules，但不得修改或覆盖本文件。
- 若 customized rule 与本文件冲突，sub-agent 必须以本文件为底线，并在 `composition/DESIGN.md` 记录冲突处理。

## Rule Definitions

### Input and source rules

#### R1 — Final audio only

`voice_clone/narration.mp3` 是最终解说音频。不要重新生成 TTS，也不要调用 HyperFrames 的 TTS。若从 catalog 视频裁剪源片段，必须用 `-an` 去掉源音频。

#### R2 — Transcript timing

时间边界以 `transcribe/transcript.json` 为准。scene 切分和非字幕 text beat 出现时机必须绑定到该 transcript 的句子 / 分句边界。最终字幕必须读取 `transcribe/subtitle-units.json`：subtitle unit 的 timing 来自 transcript 句子 / 词时间，display text 以 transcript 文本为底，并可包含 `narration.txt` 高置信度匹配带来的 Latin words 拼写修正。字幕切换和音频偏移 <= 0.2 秒。

#### R3 — Material catalog

所有以素材为底的视觉都必须通过 `material-catalog.json` 解析；需要 catalog 素材时不得凭空造 stock 视觉。`scene-material-suggestions.json` 如存在，视为素材到 scene 的硬性分配。`scene-text-plan.json` 如存在，视为非字幕屏幕文本块的结构化建议；它不能覆盖素材分配，也不能要求前景文本遮挡素材。

#### R4 — Local fonts

字体加载使用 `fonts/` 下的本地资源，确保可复现；不要依赖系统 `fc-match`。

### Scene structure and timing rules

#### R5 — Scene identity

`composition/index.html` 中每个 scene 根元素必须同时有稳定的 `data-scene-id`、`data-scene-start`、`data-scene-end`。所有 `<img>` / `<video>` / `background-image` 素材元素必须位于某个 scene 根元素内部。属于同一 continuation group 的相邻 scene 必须在 scene 根元素上标记同一个 `data-continuation-group`（等于 Phase 5.2 的 `continuation_group_id`），并用 1-based `data-continuation-index` 表示 group 内顺序，便于 QA 识别合法连续复用。重渲修复时，未受影响 scene 的 DOM / CSS / 动画和时间区间必须保持不变。

#### R6 — Material uniqueness

默认每个 catalog 素材（图片 / 视频 clip）在整片中恰好出现在一个 scene，分配以 `scene-material-suggestions.json` 为准；若 scene 使用 `material_refs`，数组内每个素材都视为该 scene 占用。`no_match` scene 用纯排版 / 文字卡片，不借用其他 scene 的素材。例外：论文 figure、技术架构图、UI 截图、流程图等可以在连续的 continuation group 中跨相邻 scene 复用同一 catalog 素材。group 起点可保留主布局角色（如 `media_first` / `video_first` / `viewport_reveal`）并标注 `continuation_group_id`，但不写 `continuation_of`；后续跨 scene 复用素材的 scene 必须标注 `layout_role = "media_continuation"`、相同 `material_ref`、相同 `continuation_group_id`，并用 `continuation_of` 指向 group 起点的 `scene_index`；未声明的跨 scene 素材复用仍视为违规。

#### R7 — Scene duration

普通 scene 目标时长为 5-8 秒；超过 8 秒必须拆分，连续多个 < 3 秒的微 scene 应避免。连续同素材合并而成的 scene 可以超过 8 秒，但 scene 内文本信息单元仍须按 5-8 秒节奏刷新，并受 R18 / R19 约束。

### Layout and composition rules

#### R8 — Scene-specific layout

每个 scene 必须由 coding sub-agent 按 scene 单独 authoring，不得套统一模板后只替换文字 / 图片。排版输入包括：

- 旁白文本与 `scene-material-suggestions.json` 的 `text_beats` / `material_ref` / `material_refs` / `layout_role`；
- `scene-text-plan.json` 中对应 scene 的 `visual_text_units`（如存在）；
- `material-catalog.json` 中对应素材（单个 `material_ref` 或 `material_refs` 中所有素材）的尺寸、类型、`layout_affordance` 和 `focal_region`（如存在）；
- 内容区尺寸（viewport - 字幕安全区 - scene padding）。

Phase 8 必须按素材比例、输出朝向、`layout_role`、text beat 数量和 visual text unit 类型选择 layout；解析顺序与 routing 见下方 `Layout routing reference`。相邻 scene 不得无理由复用同一主版式，但声明过的 continuation group 应保持同一主素材稳定显示。

### Layout routing reference

`scene-text-plan.json` 的解释流程：

1. 以 `scene_index` 为 key，把 text-plan scene 与 `scene-material-suggestions.json` scene 对齐；不得按数组位置猜测。
2. 对齐后先解析 `material_ref` / `material_refs` / `no_match`、`layout_role` 和 catalog `width` / `height` / 素材 kind / `layout_affordance` / `focal_region`（如有），再解析 `visual_text_units`。
3. 把每个 unit 映射为一个或多个非字幕信息元素：`display_text` 通常是标题 / 标签；`supporting_points` 通常是列表项、流程节点、指标、模块、关系节点或代码/命令行内容。
4. `visual_role` 只定义信息形态，不定义具体布局模板。Phase 8 必须根据素材比例、画幅、字幕安全区和 density 选择最终 layout。`visual_role` 名称不得作为可见文字渲染：标题 / 标签 / 正文 / eyebrow 不得出现 `data_block`、`callout`、`leaderboard`、`process_flow` 等 role 名及其中文直译（数据块 / 标注 / 排行榜 / 流程图等）；可见文字只用 `display_text` / `supporting_points` 等真实内容。
5. `priority: "primary"` 的 unit 必须尝试实现；`secondary` / `decorative` 可合并、缩短、轮换或降级，但必须在 `composition/DESIGN.md` 记录。

Role resolution order：

1. 读取输出朝向和内容区尺寸（按 R15 排除字幕安全区）。
2. 读取 `material_ref` / `material_refs` / `no_match` 和 `layout_role`，决定素材主导程度。
3. 读取 `visual_text_units[].visual_role`、`priority`、`supporting_points`、density 和 shape（如 row / column count、chart series count）。
4. 按 Material-aware、Media layout-role、Role-to-layout 三组 routing 选择适合当前朝向的呈现方式。
5. 若 `template_hint` 与 `visual_role`、table / chart shape 或当前朝向冲突，忽略 `template_hint`，并在 `composition/DESIGN.md` 记录。
6. Phase 8 只有在 `chart` unit 已存在，或 `data_table` 明确提供可 chart 的 numeric series / highlighted dimensions 时，才能把 table 呈现方式转为 chart 呈现方式。

Material-aware routing：

| Scene condition | Landscape | Portrait |
| --- | --- | --- |
| `no_match: true` | 按 `visual_role` 选择信息图、cards、flow、table / chart 等呈现方式；可横向展开。 | 按 `visual_role` 选择纵向 stack、stepper、paged / timed 呈现方式；避免 3+ 横向窄列和宽表硬缩。 |
| 横图 / 横视频 | 素材作为宽幅主体；承载对应 `visual_role` 的外置信息区、metadata band、轻量浮层或分时轮换区不得压素材。 | 使用 wide media slab：素材按原比例占内容区宽度，高度自然推导，放在上部或中上部；其余区域承载对应 `visual_role`。若素材超宽且关键内容分散，可用 `viewport_reveal` 横向 pan。 |
| 竖图 / 竖视频 | 使用 tall media column：素材按原比例占满内容区高度的 80-100%，宽度自然推导；剩余横向空间承载对应 `visual_role`。若素材过高且关键内容分布在长轴，可用 `viewport_reveal` 纵向 pan。 | 素材可居中作为主视觉，文本上下堆叠；如内容太长，用 `viewport_reveal` 纵向 pan。 |
| ultra-wide strip | 使用 `band` 或 `viewport_reveal`；band 必须足够高可读，不能变成细线。 | 优先 `viewport_reveal` 横向 pan 或拆分为 timed sequence；不得完整缩成不可读细条。 |
| 方图 / UI 截图 | 素材居中或偏一侧；周边信息块围绕但不压素材，必要时只实现 primary unit。 | 上下分区或居中主体 + 短 callout；信息过密时分时出现或只保留 primary。 |
| 论文 figure / table / chart | 保持 figure/table/chart 可读；用外置信息区解释 1-3 个关键结论，不重画完整表格，不遮挡轴线、图例、caption 或关键曲线。 | figure slab / reveal + 一次一个外置 callout；table/chart 过密时只显示 primary rows / columns / points 或拆 scene。 |
| 视频 clip | 视频主体优先；文本使用短标签、状态说明或时间点 callout。复杂流程 / 架构图应放到相邻 `no_match` 或低素材密度 scene，而不是遮挡视频。 | 视频作为 media slab 或安全的近全幅背景；复杂信息拆到 `no_match` / continuation，避免长段 overlay。 |

Orientation-aware routing：

| Output orientation | Layout routing |
| --- | --- |
| 横屏 `1920x1080` | 可用左右分栏、宽幅素材 + 右侧信息区、下方 info rail。横图 / 横视频可占内容区主体宽度；多 unit 可横向排列为 metric strip / timeline。 |
| 竖向 `1080x1440` | 不要直接套横屏右侧栏。优先上下分区：上方 / 中部放素材主体，下方或顶部放 shrink-to-fit 信息带；也可使用 60/40 或 55/45 的上下 split。竖图 / 竖视频可左右窄分栏，但必须给字幕安全区留足空间。复杂 `process_flow` / `architecture_diagram` 优先改成纵向节点链、stacked modules、分页轮换，而不是横向大图。 |
| 竖屏 `1080x1920` | 优先纵向叙事：素材、标题、callout、data blocks 依次堆叠或分时轮换；避免左右分栏导致文本过窄。结构型 unit 用纵向 timeline / stepper / module stack；多指标用 2 列以内卡片。 |

对 `1080x1440` 和 `1080x1920`，字幕安全区通常比横屏更高；素材和非字幕文本都必须按 R15 计算在内容区内，不得为了塞更多 text units 侵入底部字幕区域。若 `visual_text_units` 过多，优先分时轮换或降级 `secondary` / `decorative` units，而不是缩小字体到不可读。

Media layout-role routing：

| `layout_role` | Landscape | Portrait | Notes / forbidden |
| --- | --- | --- | --- |
| `no_match` | 按 `visual_role` 选择信息图、cards、flow、table/chart 等承载内容。 | 按 `visual_role` 选择 vertical stack、stepper、paged/timed sequence；避免横向窄列。 | 不借用其他 scene 素材。 |
| `video_first` | 视频作为主体，横屏 / 16:9 视频通常宽度和高度都接近内容区可用空间。 | 横屏视频通常作为上半屏或中上部清晰 media slab；文本只用短标签、状态说明、关键数字或一句短结论。 | 视频占满或接近占满画面时仅允许短、shrink-to-fit overlay，遵守 R12。 |
| `media_first` | 清晰大图作为主体，优先按内容区可用宽高共同计算，避免只用固定 max-width 压低高度。 | 横图用 media slab + stacked text；竖图用居中主视觉 + 上下 text；信息多时分时、外置、降级或转 continuation。 | 主媒体不得被固定标题区或信息块不必要压小。 |
| `media_continuation` | 保持相近位置、尺寸、裁切窗口和动效，只刷新解释文本、局部强调或 `focal_region`。 | 同左，尤其保持主素材在相邻 scene 中稳定。 | 避免素材长时间消失后再出现，也避免硬切到完全不同版式。 |
| `viewport_reveal` | 极端比例素材进入 reveal viewport，按长轴慢速 pan / scroll。 | 同左，但竖屏横图优先横向 reveal，横屏竖图优先纵向 reveal。 | 必须记录 intentional reveal、start / mid / end 可见区域和关键内容。 |
| `band` | 超宽素材作为横向信息带，如 logo row、timeline、UI strip、长表头。 | 仅当足够高可读；否则改用 reveal、sequence 或拆 scene。 | band 不能显示成细线。 |
| `detail_callout` | 显示素材关键区域，并用外置信息解释重点。 | 使用局部窗口或 media slab + 一次一个外置 callout。 | 不得把 callout 压在素材关键内容上。 |
| `comparison_pair` | 两个素材同屏对比，优先左右并排，统一高度或统一可读尺度。 | 优先上下分区或分时对比，避免两个详细截图被压成窄列。 | 每个素材仍必须可读。 |
| `comparison_sequence` | 三个及以上素材用分时 / carousel 展示；必要时拆 scene。 | 一次一个或一组少量素材，paged/timed 展示。 | 不默认三等分或小宫格。 |

Role-to-layout routing：

| `visual_role` | 横屏 `1920x1080` | 竖向 `1080x1440` / 竖屏 `1080x1920` |
| --- | --- | --- |
| `title` / `product_card` / `section_divider` | title 可作为大标题或身份卡；product card 可配 metric / CTA / tagline。 | title / product card 纵向堆叠，避免贴顶小字；必要时 title + subtitle 分层。 |
| `leaderboard` | 可 rank list + detail rail / highlighted row / optional media preview。 | stacked rank cards、paged Top N、一次突出一个条目；带素材时素材 preview 必须保持可读，不得多列窄排。 |
| `big_number` | 大数字 hero、单指标冲击卡或与 summary rail 并排。 | 大数字 + 短解释纵向堆叠；避免过多指标同屏。 |
| `data_table` | Small table（≤3 rows, ≤3 columns, cells short）可 compact table；medium table（4-8 rows 或 4-5 columns）可 table + highlights / summary rail；large table（>8 rows 或 >5 columns）不得整表硬塞，必须 highlight / summarize / paginate / split，或按数值维度拆成 2-3 个 charts。 | small table 可 compact table 或 stacked mini-table；medium table 转 stacked rows/cards、paged rows，或在数据适合时转 1 个 chart；large table 只显示 primary rows/columns、cards、paged columns、一次一个 chart 或拆 scene。 |
| `chart` | single chart、chart + summary rail、small multiples（通常 2-3 个）。 | single chart、stacked chart cards、paged / timed chart sequence；避免同屏 3 个以上小图。Chart 只能表达可比较的数值、趋势、占比或分布；文本密集表不得硬转 chart。 |
| `process_flow` / `timeline` / `state_machine` | 可横向 flow 或纵向 flow；横向节点必须保持可读，节点数通常 3-5。 | 必须优先 vertical stepper、stacked path、paged / timed nodes；禁止 3 个及以上横向窄节点。 |
| `architecture_diagram` / `network_graph` | 可用 grouped columns、layered bands、readable graph clusters。 | 用 stacked modules / layers、focus window、primary path；避免 dense full graph。 |
| `data_block` / `metric_strip` | 可用横向指标条、2x2 grid、compact cards；数值必须突出，使用 tabular nums。 | stacked cards 或最多 2 列；不得靠缩小字号塞很多 metric。 |
| `list` / `feature_grid` | 2-4 项 grid / rail；每项短 label + 一行 detail，避免长段落。 | stacked cards 或最多 2 列；过密时轮换 secondary items。 |
| `comparison_matrix` / `pros_cons` | side-by-side matrix 或双列对比。 | stacked / sequenced comparison；不得把详细矩阵压进窄列。 |
| `code_block` / `terminal_block` / `file_tree` | 宽面板，可配短解释；只展示关键行，避免完整文件 / 长日志。 | 单个可读面板 + stacked explanation；长行截断 / 摘取关键行，避免多面板小字。 |
| `callout` / `quote` / `annotated_media` / `definition` / `qa` | 外置 rail / band，或 R12 允许的短 overlay；不能压在图片 / 视频主体上。 | 素材外纵向堆叠或一次一个 callout；避免窄 side rail。 |

portrait / vertical 输出中，多元素 / 结构型 role（`leaderboard`、`data_table`、`chart`、`timeline`、`process_flow`、`architecture_diagram`、`network_graph`、`comparison_matrix`、`pros_cons`、`metric_strip`、`list`、`feature_grid`、`qa`、`code_block`、`terminal_block`、`file_tree`、`state_machine`、`annotated_media`）不得沿用横屏窄列 / 多列硬排。若文本框过窄、字号触底、label 多次换行或节点 / 行 / 卡片不可读，必须改用纵向堆叠、vertical stepper、stacked cards、focus window、paged / timed rotation 或拆 scene。不得用缩字号、隐藏 peak-state 元素或延迟显示来掩盖布局失败。

#### R9 — Material aspect ratio

素材容器比例必须来自 `material-catalog.json` 的 `width` / `height`（图片由 harvester 写入，视频由下载 / ffprobe 流程写入）。将 `width / height` 作为 `aspect-ratio` 应用于包裹素材的 wrapper；只有字段为 `null` / 缺失时才 fallback 到运行时实测或 ffprobe。禁止默认 16:9，禁止用错误比例容器 + `object-fit: cover` 裁掉素材，禁止因比例错误产生拉伸、letterbox 或 pillarbox。唯一例外是 R10 的 intentional `viewport_reveal`：外层 reveal viewport 可使用 scene-appropriate ratio，但内层素材仍必须保持原始比例。

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

Intentional `viewport_reveal` exception:

```css
.reveal-viewport {
  overflow: hidden;
  /* scene-appropriate ratio, not necessarily source ratio */
}
.reveal-viewport > img,
.reveal-viewport > video {
  width: auto;
  height: 100%; /* or width: 100% for ultra-tall assets */
  max-width: none;
  max-height: none;
}
```

`viewport_reveal` 只适用于 `layout_role = "viewport_reveal"` 或需要局部可视窗口的 `video_first` / `detail_callout`。外层容器可使用适合 scene 的比例并 `overflow: hidden`；内层图片 / 视频必须保持原始宽高比，不得拉伸。短边对齐容器，长边溢出并沿长轴慢速 pan / scroll；如果只展示局部，必须使用 catalog `focal_region` 或在 `composition/DESIGN.md` 说明设计理由。该例外是有意 reveal，不是 letterbox / pillarbox / accidental clipping。

#### R11 — Media dominance and quality

有图片 / 视频素材的 scene，素材应占据内容区主体（通常 >= 50%），禁止缩成角落邮票贴在大段文字旁。`video_first` 和 `media_first` 的主媒体应优先最大化可视区域：横屏输出中的横屏视频 / 清晰横图通常宽度对齐内容区；竖屏 / 竖向输出中的横屏视频 / 横图通常作为上半屏或中上部 media slab，避免缩成小图。主媒体尺寸必须同时按内容区可用宽度和高度计算，不能只用固定 max-width 导致横屏 wide media 高度过低；横屏中作为主证据的 16:9 / wide image 或 video slab 通常应达到内容区高度的 65-85%，若低于约 60%，必须有文本密度、素材质量或构图原因，并在 `composition/DESIGN.md` 记录。Catalog 图片 / 视频的 rendered size 按主要可见边或短边计算，优先保持在原始素材尺寸的 0.8x-1.5x 范围内，并在 `composition/DESIGN.md` 记录口径；超出范围时必须记录原因、素材替代尝试和 QA 结论。多素材 scene 两个素材可用 `comparison_pair`，三个及以上优先 `comparison_sequence` / carousel / 拆 scene；如必须并列，每个素材 >= 30% 内容区且仍可读。图片必须清晰、关键信息完整，原图分辨率应覆盖渲染尺寸，不得可见模糊、像素化、JPG artifacts 或裁掉文字、图表轴线、人物面部、UI 主控件等关键信息。

#### R12 — Bounds and overlap

所有视觉元素必须完整位于画面内，不得截断。除全局字幕条覆盖底层画面外，任何前景标题、caption、tag、badge、callout、label、数据块都不得压在图片 / 视频素材关键区域之上，包括 hero 素材。`video_first` 中视频占满或接近占满画面时，允许少量半透明文本框浮在视频上，但必须 shrink-to-fit、短文本、停留时间短、位置稳定，并避开主体动作、鼠标 / 手势、按钮、代码高亮、图表主线、人物脸部和 catalog `focal_region`；不得用长段落或整行遮罩压视频。

#### R13 — Split-column vertical balance

媒体列 + 信息列 / 左右分栏中，两列垂直跨度必须大致对齐；信息列不得只在上部堆内容、下部留大块空白。信息列内容稀疏时，用 `metric_strip` / `list` 等多元素 role 拆出更多条目（随旁白逐个出现）、增高卡片或重新纵向分布，使列内元素纵向均衡填满列高。pills / tag / metadata 等收尾元素不得孤立钉在底边、与上方内容隔一大段空白；应靠近主内容或参与列内纵向分布。单卡仅承载 1-2 短行且四周大留白时，必须增密、并入等高容器或重排，不得作为一列的唯一内容。

#### R14 — Style constraints

文字框内文字应垂直 / 水平居中。内容区不得出现 >10% 视口面积的纯空白；字幕安全区不计入空白统计，也不得为填满而把内容元素铺进该带。除全局内容区空白外，还必须检查大型 card / panel / callout / media shell 的内部 container occupancy。普通信息容器占据大面积时，内部子元素 bounding boxes 不得只占很小比例；若故意使用 hero number / quote / title-card 留白，必须在 `composition/DESIGN.md` 记录为 deliberate hero 留白。任意承载内容的区域 / 列（含无边框 flex / grid 列、文本列），内容必须横向 / 纵向填满该区域，或令该区域留白对称分布；不得把内容单边对齐贴住一侧而令对侧或外侧留大块空白。文本 / 数据应使用整区宽度；区域内容确实稀疏时，收窄或重新居中该区域容器使留白对称，不留单边空白。配对区域（媒体列与文本列、左右分栏）的外侧边距必须大致对称，一侧外边距不得明显大于另一侧。如需呼吸空间，用极淡装饰 / 网格 / 角标占位。Moon / 深色技术编辑风默认纯色 + 极淡网格 / 细线 / 低对比结构，禁止 `radial-gradient` spotlight、localized glow、ambient orb、neon halo、发光阴影和用 glow 充当层次感。

### Subtitle rules

#### R15 — Subtitle safe area

视口底部预留专属字幕安全区，高度必须贴合字幕条实际占位（字幕行数 × 行高 + 上下小边距），不得显著大于字幕条本身。本次收紧仅针对横屏单行场景：横屏（`1920x1080`）字幕固定单行，安全区从原 12-18% 收紧到约 9-12%（1080p 约 97-130px）；竖屏 / 竖向因允许字幕最多两行，安全区按实际 subtitle box 高度单独预留，`1080x1440` 建议约 150-220px，`1080x1920` 建议约 220-300px。只有双行字幕、较大字号、复杂背景或 subtitle mask 需要更多呼吸空间时才靠近上限；不得为了“保险”长期预留 18% 高度。authoring 时内容区必须按 `viewport - subtitle safe area` 计算；除全局字幕条外，任何前景文本 / callout / 素材 / 装饰不得进入该安全区。全幅背景素材可延伸到安全区下方垫底，此时字幕条用半透明遮罩压在其上。

#### R16 — Global subtitle

字幕必须使用单个全局容器，固定锚定在底部字幕安全区内并与安全区上下贴合（建议 bottom 为视口高度 3-5%，1080p 约 32-54px），全片水平居中且基线稳定。字幕容器必须从安全区底部向上排版（如 `bottom` 锚定 + 文本底对齐），行数变化时基线稳定、不上下跳动。字幕单元来自 `transcribe/subtitle-units.json`。收窄 subtitle safe area 的前提是严格执行最大行数：横屏每个单元最多 1 行（如 `white-space: nowrap`）；竖屏 / 竖向每个单元最多 2 行（通过 `max-width` 自动换行，明确禁止第三行及以上）。无论横竖屏，如果某个 unit 在该朝向允许的最大行数内仍放不下，必须回到 transcript-timed unit 拆分逻辑，把它拆成更小的 calibrated units；不得扩大 safe area 来容纳第三行，不得靠缩字号到下限、放宽 `max-width`、整行遮罩或塞进多余行数。半透明背景遮罩必须 shrink-to-fit，随文字宽度自适应并保证任意画面背景下可读；禁止固定 `width: 100%`、大 `min-width` 或整行遮罩。

### Typography rules

#### R17 — Typography, DOM, contrast

同一 scene 内最大 / 最小字号比 <= 3:1；素材 / 文本容器最多 2 层嵌套。正文对比度 >= 4.5:1，大字号标题对比度 >= 3:1。decorative metadata / chrome label 可低至 18-20px，但不得承载主信息；badge / chip / rank label 建议 >=22px（横屏）/ >=24px（竖屏）；body / supporting detail 建议 >=28px（横屏）/ >=30px（竖屏）；callout / card text 建议 >=32px（横屏）/ >=34px（竖屏）；承担 scene 语义锚点的 header / eyebrow 建议 >=28px（横屏）/ >=30px（竖屏）。主标题优先单行；如果必须两行，每行都应保留有意义词组。禁止第二行只有 1-2 个汉字、一个短英文 token 或孤立标点。遇到标题孤行时，必须通过缩短 `display_text`、扩大文本框、微调字号、调整断句、改为 title + subtitle、或分时 reveal 修复。字号微调最多缩小到当前字号的 0.9 倍，且不得低于对应文本类型的字号下限。

### Motion and text-timing rules

#### R18 — Motion

有效动效必须来自内容本身，如素材 Ken Burns / 缓移 / 缩放、文字渐入、数据 callout 浮现、多元素随旁白逐个出现或极轻微低对比装饰 drift。每张图片素材都需要持续动效，同一类图片动效不得重复超过 `ceil(total_images / 5)` 次；视频素材视为自带运动，接近静止的视频按图片处理。普通相邻 scene 需要显式转场，避免硬切。`media_continuation` group 内主媒体层必须稳定，不得对主图 / 视频做 full-scene fade、wipe、slide-out、re-enter 或重新加载式入场；只允许文字、callout、局部高亮、`focal_region` emphasis、轻微镜头推进或信息区替换。禁止用横贯 / 纵贯扫描线、扫光、sweep、进度条等覆盖层凑动效。

#### R19 — Text timing and entrance state

多个非素材文本元素必须按完整旁白句子逐个出现，禁止 scene start 一次性全亮。多元素 `visual_role` 内部的条目 / 节点 / 行 / 标注也必须随对应旁白逐个出现，不在 unit 首次出现时一次性全亮。scene title / header / eyebrow 与 `visual_text_units[].display_text` / `supporting_points` 不得重复同一句或同一短语；重复时删除标题、改成上位标签，或改写 unit 文本。文本元素服务于哪一句，就在该句开始前短暂提前显示，保证旁白读到该句时相关文本已可见。若 `scene-text-plan.json` 存在，`priority: "primary"` 的 `visual_text_units` 必须优先实现；`secondary` / `decorative` 可因安全布局降级，但必须在 `composition/DESIGN.md` 记录。旧 text beat 需要淡出或降级，不能永久累积。入场动画必须有正确初始态，避免元素在 tween 前闪现。

### Authoring record and audit rules

#### R20 — Scene inventory

`composition/DESIGN.md` 必须记录每个 scene 的 `scene_id`、旁白摘要、`material_ref` / `material_refs`、`layout_role`、素材尺寸 / aspect ratio、`ratio_bucket` / `focal_region`（如有）、text beats、`scene-text-plan.json` 中对应的 `visual_text_units`（如有）、布局呈现方式、peak-state audit 结果，以及每个非素材元素对应的完整旁白句子和出现时间点。对每个已实现的 visual text unit，记录 `unit_id`、`visual_role`、`display_text`、`priority`、来源 text beat、最终 DOM selector、出现 timing、输出朝向、采用的按朝向布局呈现方式；portrait / vertical 时还必须记录为何没有沿用横屏排列，以及过密信息如何降级（stack / page / rotate / split scene）。若某个 `primary` unit 被降级或未实现，必须记录原因。若使用 `media_continuation`，记录相邻 scene 如何保持同一主素材稳定显示；若使用 `viewport_reveal`，记录 start / mid / end 可见区域和关键内容是否完整出现。

#### R21 — Peak-state layout audit

动画前必须检查每个 scene 的 peak state：所有非字幕元素都显示时，元素不得溢出 viewport / 内容区、不得互相遮挡、前景元素不得无约束覆盖 catalog 素材、素材不得 letterbox / pillarbox、内容区纯空白不得超过 10%、构图不得明显失衡；主要元素组在水平 / 垂直方向上的分布必须均衡，视觉重心不得明显偏上、偏下、偏左或偏右；不得用超大空容器或空 media panel 填充画面来规避全局空白检查。`media_first` / `video_first` 主素材不得被标题或信息块不必要地压小；`comparison_pair` 中每个素材必须仍可读。portrait / vertical 中，多元素 / 结构型 unit（`leaderboard`、`data_table`、`chart`、`timeline`、`process_flow`、`architecture_diagram`、`network_graph`、`comparison_matrix`、`pros_cons`、`metric_strip`、`list`、`feature_grid`、`qa`、`code_block`、`terminal_block`、`file_tree`、`state_machine`、`annotated_media`）不得被横向硬排到文本窄列、字号过小、多次换行或内容不可读。失败必须先调整布局尺寸、位置、字号、信息密度或拆 scene，不得靠“暂时隐藏元素”掩盖问题。`viewport_reveal` 还必须检查 start / mid / end，确认关键内容不会永久隐藏。

## Stage Protocols

Phase 8.3-8.7 必须遵循 `references/composition-stage-protocol.md`。

缺失或无法读取 `references/composition-stage-protocol.md` 时，停止并报告缺失引用；不得自拟 audit 流程。