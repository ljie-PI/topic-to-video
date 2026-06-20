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

#### R8 — Scene-specific layout

每个 scene 必须由 coding sub-agent 按 scene 单独 authoring，不得套统一模板后只替换文字 / 图片。排版输入包括：

- 旁白文本与 `scene-material-suggestions.json` 的 `text_beats` / `material_ref` / `material_refs` / `layout_role`；
- `scene-text-plan.json` 中对应 scene 的 `visual_text_units`（如存在）；
- `material-catalog.json` 中对应素材（单个 `material_ref` 或 `material_refs` 中所有素材）的尺寸、类型、`layout_affordance` 和 `focal_region`（如存在）；
- 内容区尺寸（viewport - 字幕安全区 - scene padding）。

Phase 8 必须按素材比例、输出朝向、`layout_role`、text beat 数量和 visual text unit 类型选择 layout；具体 routing 见下表。相邻 scene 不得无理由复用同一主版式，但声明过的 continuation group 应保持同一主素材稳定显示。

`scene-text-plan.json` 的解释流程：

1. 以 `scene_index` 为 key，把 text-plan scene 与 `scene-material-suggestions.json` scene 对齐；不得按数组位置猜测。
2. 对齐后先解析 `material_ref` / `material_refs` / `no_match`、`layout_role` 和 catalog `width` / `height` / 素材 kind / `layout_affordance` / `focal_region`（如有），再解析 `visual_text_units`。
3. 把每个 unit 映射为一个或多个非字幕信息元素：`display_text` 通常是标题 / 标签；`supporting_points` 通常是列表项、流程节点、指标、模块、关系节点或代码/命令行内容。
4. `visual_role` 只定义信息形态，不定义具体布局模板。Phase 8 必须根据素材比例、画幅、字幕安全区和 density 选择最终 layout。
5. `priority: "primary"` 的 unit 必须尝试实现；`secondary` / `decorative` 可合并、缩短、轮换或降级，但必须在 `composition/DESIGN.md` 记录。

Material-aware routing：

| Scene condition | Layout routing |
| --- | --- |
| `no_match: true` | 用纯排版信息图承载 `visual_text_units`；至少尝试一个结构型 unit（`process_flow` / `architecture_diagram` / `timeline` / `comparison_matrix` / `network_graph`）或 2-4 个短文本 / data units。 |
| 横图 / 横视频 | 素材作为宽幅主体；文本进入右侧 / 下方外置信息区、顶部 metadata band、轻量浮层或分时轮换 callout。不得无约束覆盖素材主体。 |
| 竖图 / 竖视频 | 根据输出朝向选择左右分栏或上下分区；素材保持完整比例，文本组织为 stacked callouts / data blocks / list。 |
| 方图 / UI 截图 | 素材居中或偏一侧；周边信息块围绕但不压素材，必要时只实现 primary unit。 |
| 论文 figure / table / chart | 保持 figure/table 可读；用外置信息区解释 1-3 个关键结论，不重画完整表格，不用文本遮挡轴线、图例、caption 或关键曲线。 |
| 视频 clip | 视频主体优先；文本使用短标签、状态说明或时间点 callout。复杂流程 / 架构图应放到相邻 `no_match` 或低素材密度 scene，而不是遮挡视频。 |

Orientation-aware routing：

| Output orientation | Layout routing |
| --- | --- |
| 横屏 `1920x1080` | 可用左右分栏、宽幅素材 + 右侧信息区、下方 info rail。横图 / 横视频可占内容区主体宽度；多 unit 可横向排列为 metric strip / timeline。 |
| 竖向 `1080x1440` | 不要直接套横屏右侧栏。优先上下分区：上方 / 中部放素材主体，下方或顶部放 shrink-to-fit 信息带；也可使用 60/40 或 55/45 的上下 split。竖图 / 竖视频可左右窄分栏，但必须给字幕安全区留足空间。复杂 `process_flow` / `architecture_diagram` 优先改成纵向节点链、stacked modules、分页轮换，而不是横向大图。 |
| 竖屏 `1080x1920` | 优先纵向叙事：素材、标题、callout、data blocks 依次堆叠或分时轮换；避免左右分栏导致文本过窄。结构型 unit 用纵向 timeline / stepper / module stack；多指标用 2 列以内卡片。 |

对 `1080x1440` 和 `1080x1920`，字幕安全区通常比横屏更高；素材和非字幕文本都必须按 R13 计算在内容区内，不得为了塞更多 text units 侵入底部字幕区域。若 `visual_text_units` 过多，优先分时轮换或降级 `secondary` / `decorative` units，而不是缩小字体到不可读。

Media layout-role routing：

| `layout_role` | Preferred layout treatment |
| --- | --- |
| `video_first` | 视频作为 scene 主体，优先最大化可视区域。横屏输出中的横屏 / 16:9 视频通常宽度对齐内容区；竖屏 / 竖向输出中的横屏视频通常放在上半屏或中上部作为清晰 media slab（约占内容区 40-55%，按字幕安全区、padding 和文本密度调整）。文本只用短标签、状态说明、关键数字或一句短结论；视频占满画面时允许少量半透明文本框，但必须遵守 R16。 |
| `media_first` | 清晰大图作为 scene 主体，优先最大化可视区域。不是无文本：Phase 5.3 应生成少量辅助文本，通常为 1 个短标题 / 标签 + 0-2 个短 callout 或 data point；信息多时分时、外置、降级或转为 `media_continuation`，不得用固定标题区压缩主图。 |
| `media_continuation` | 相邻 scene 沿用同一主图 / 视频作为稳定视觉锚点，保持相近位置、尺寸、裁切窗口和动效，只刷新解释文本、局部强调或 `focal_region`。避免图片 / 视频长时间消失后再出现，也避免硬切到完全不同版式。 |
| `viewport_reveal` | 极端比例图片 / 视频进入 reveal viewport：外层窗口可使用 scene 适合比例并 `overflow: hidden`，内层素材保持原始比例，短边对齐容器，长边溢出并慢速 pan / scroll。必须记录这是 intentional reveal，不能伪装成普通裁切。 |
| `band` | 超宽素材作为横向信息带，如 logo row、timeline、UI strip、长表头。band 必须足够高以可读；如果只能显示成细线，应改用 `viewport_reveal` 或 `comparison_sequence`。 |
| `detail_callout` | 显示素材关键区域，并用外置信息解释重点。不得把 callout 压在素材关键内容上；如用局部窗口，需记录 `focal_region` 和理由。 |
| `comparison_pair` | 两个素材同屏对比。横屏优先左右并排，竖屏 / 竖向优先上下分区；统一高度或统一可读尺度，避免厚边框和过大间距。 |
| `comparison_sequence` | 同一 scene 内三个及以上素材，或两个素材同屏后不可读时，用分时 / carousel 展示，且需要 2 个以上 `material_refs`。若改为拆 scene，拆出的 scene 使用各自真实主角色（如 `media_first` / `video_first` / `viewport_reveal` / `detail_callout`），并在 `layout_reason` 说明它属于同一对比序列。不要默认三等分或小宫格。 |

Role-to-layout routing：

| `visual_role` | 横屏 `1920x1080` | 竖向 `1080x1440` / 竖屏 `1080x1920` |
| --- | --- | --- |
| `process_flow` / `timeline` / `state_machine` | 可横向 flow 或纵向 flow；横向节点必须保持可读，节点数通常 3-5。 | 必须优先 vertical stepper、stacked path、paged / timed nodes；禁止 3 个及以上横向窄节点。 |
| `architecture_diagram` / `network_graph` | 可用 grouped columns、layered bands、readable graph clusters。 | 用 stacked modules / layers、focus window、primary path；避免 dense full graph。 |
| `data_block` / `metric_strip` | 可用横向指标条、2x2 grid、compact cards；数值必须突出，使用 tabular nums。 | stacked cards 或最多 2 列；不得靠缩小字号塞很多 metric。 |
| `list` / `feature_grid` | 2-4 项 grid / rail；每项短 label + 一行 detail，避免长段落。 | stacked cards 或最多 2 列；过密时轮换 secondary items。 |
| `comparison_matrix` | side-by-side matrix 或双列对比。 | stacked / sequenced comparison；不得把详细矩阵压进窄列。 |
| `code_block` / `terminal_block` / `file_tree` | 宽面板，可配短解释；只展示关键行，避免完整文件 / 长日志。 | 单个可读面板 + stacked explanation；长行截断 / 摘取关键行，避免多面板小字。 |
| `callout` / `quote` / `paper_figure_callout` | 外置 rail / band，或 R16 允许的短 overlay；不能压在图片 / 视频主体上。 | 素材外纵向堆叠或一次一个 callout；避免窄 side rail。 |

对 portrait / vertical 输出，layout 在几何上能塞进 viewport 不代表合格。如果文本框因为沿用横屏布局而过窄、字号被迫降到下限、label 多次换行、或流程节点变成 3 个及以上横向窄列，Phase 8 必须改用纵向堆叠、vertical stepper、paged / timed rotation、或拆 scene。不得用缩字号、隐藏 peak-state 元素或延迟显示来掩盖布局失败。

#### R9 — Scene inventory

`composition/DESIGN.md` 必须记录每个 scene 的 `scene_id`、旁白摘要、`material_ref` / `material_refs`、`layout_role`、素材尺寸 / aspect ratio、`ratio_bucket` / `focal_region`（如有）、text beats、`scene-text-plan.json` 中对应的 `visual_text_units`（如有）、layout treatment、peak-state audit 结果，以及每个非素材元素对应的完整旁白句子和出现时间点。对每个已实现的 visual text unit，记录 `unit_id`、`visual_role`、`display_text`、`priority`、来源 text beat、最终 DOM selector、出现 timing、输出朝向、采用的 orientation-specific layout treatment；portrait / vertical 时还必须记录为何没有沿用横屏排列，以及过密信息如何降级（stack / page / rotate / split scene）。若某个 `primary` unit 被降级或未实现，必须记录原因。若使用 `media_continuation`，记录相邻 scene 如何保持同一主素材稳定显示；若使用 `viewport_reveal`，记录 start / mid / end 可见区域和关键内容是否完整出现。

#### R10 — Peak-state layout audit

动画前必须检查每个 scene 的 peak state：所有非字幕元素都显示时，元素不得溢出 viewport / 内容区、不得互相遮挡、前景元素不得无约束覆盖 catalog 素材、素材不得 letterbox / pillarbox、内容区纯空白不得超过 10%、构图不得明显失衡；`media_first` / `video_first` 主素材不得被标题或信息块不必要地压小；`comparison_pair` 中每个素材必须仍可读。portrait / vertical 中，`process_flow`、`timeline`、`state_machine`、`architecture_diagram`、`network_graph`、`comparison_matrix` 等结构型 unit 不得被横向硬排到文本窄列、字号过小、多次换行或节点不可读。失败必须先调整布局尺寸、位置、字号、信息密度或拆 scene，不得靠“暂时隐藏元素”掩盖问题。`viewport_reveal` 还必须检查 start / mid / end，确认关键内容不会永久隐藏。

### Media, subtitle, and layout rules

#### R11 — Material aspect ratio

素材容器比例必须来自 `material-catalog.json` 的 `width` / `height`（图片由 harvester 写入，视频由下载 / ffprobe 流程写入）。将 `width / height` 作为 `aspect-ratio` 应用于包裹素材的 wrapper；只有字段为 `null` / 缺失时才 fallback 到运行时实测或 ffprobe。禁止默认 16:9，禁止用错误比例容器 + `object-fit: cover` 裁掉素材，禁止因比例错误产生拉伸、letterbox 或 pillarbox。唯一例外是 R12 的 intentional `viewport_reveal`：外层 reveal viewport 可使用 scene-appropriate ratio，但内层素材仍必须保持原始比例。

#### R12 — Material container

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

#### R13 — Subtitle safe area

视口底部预留专属字幕安全区，高度必须贴合字幕条实际占位（字幕行数 × 行高 + 上下小边距），不得显著大于字幕条本身。本次收紧仅针对横屏单行场景：横屏（`1920x1080`）字幕固定单行，安全区从原 12-18% 收紧到约 9-12%（1080p 约 97-130px）；竖屏 / 竖向（`1080x1920`、`1080x1440`）因允许字幕最多两行，安全区按两行高度单独预留，约 14-18%（1920 高约 270-345px，1440 高约 200-260px），不随横屏一起收紧。authoring 时内容区必须按 `viewport - subtitle safe area` 计算；除全局字幕条外，任何前景文本 / callout / 素材 / 装饰不得进入该安全区。全幅背景素材可延伸到安全区下方垫底，此时字幕条用半透明遮罩压在其上。

#### R14 — Global subtitle

字幕必须使用单个全局容器，固定锚定在底部字幕安全区内并与安全区上下贴合（建议 bottom 为视口高度 3-5%，1080p 约 32-54px），全片水平居中且基线稳定。字幕容器必须从安全区底部向上排版（如 `bottom` 锚定 + 文本底对齐），行数变化时基线稳定、不上下跳动。字幕单元来自 `transcribe/subtitle-units.json`。横屏每个单元必须单行显示（如 `white-space: nowrap`）；竖屏 / 竖向允许每个单元最多两行（通过 `max-width` 自动换行，明确禁止第三行及以上）。无论横竖屏，如果某个 unit 在该朝向允许的最大行数内仍放不下，必须回到 transcript-timed unit 拆分逻辑，把它拆成更小的 calibrated units；不得靠缩字号到下限、放宽 `max-width` 或塞进多余行数。半透明背景遮罩必须 shrink-to-fit，随文字宽度自适应并保证任意画面背景下可读；禁止固定 `width: 100%`、大 `min-width` 或整行遮罩。

#### R15 — Media dominance and quality

有图片 / 视频素材的 scene，素材应占据内容区主体（通常 >= 50%），禁止缩成角落邮票贴在大段文字旁。`video_first` 和 `media_first` 的主媒体应优先最大化可视区域：横屏输出中的横屏视频 / 清晰横图通常宽度对齐内容区；竖屏 / 竖向输出中的横屏视频 / 横图通常作为上半屏或中上部 media slab，避免缩成小图。允许放大素材填充画面，但原始短边放大不超过 2x；多素材 scene 两个素材可用 `comparison_pair`，三个及以上优先 `comparison_sequence` / carousel / 拆 scene；如必须并列，每个素材 >= 30% 内容区且仍可读。图片必须清晰、关键信息完整，原图分辨率应覆盖渲染尺寸，不得可见模糊、像素化、JPG artifacts 或裁掉文字、图表轴线、人物面部、UI 主控件等关键信息。

#### R16 — Bounds and overlap

所有视觉元素必须完整位于画面内，不得截断。除全局字幕条覆盖底层画面外，任何前景标题、caption、tag、badge、callout、label、数据块都不得压在图片 / 视频素材关键区域之上，包括 hero 素材。`video_first` 中视频占满或接近占满画面时，允许少量半透明文本框浮在视频上，但必须 shrink-to-fit、短文本、停留时间短、位置稳定，并避开主体动作、鼠标 / 手势、按钮、代码高亮、图表主线、人物脸部和 catalog `focal_region`；不得用长段落或整行遮罩压视频。

#### R17 — Typography, DOM, contrast

同一 scene 内最大 / 最小字号比 <= 3:1；主标题文本框不得折成 2+ 行。素材 / 文本容器最多 2 层嵌套。正文对比度 >= 4.5:1，大字号标题对比度 >= 3:1。

### Motion, text, and style rules

#### R18 — Motion

最终画面不得连续静止超过 2 秒。有效动效必须来自内容本身，如素材 Ken Burns / 缓移 / 缩放、文字渐入、数据 callout 浮现或极轻微低对比装饰 drift。每张图片素材都需要持续动效，同一类图片动效不得重复超过 `ceil(total_images / 5)` 次；视频素材视为自带运动，接近静止的视频按图片处理。普通相邻 scene 需要显式转场，避免硬切。`media_continuation` group 内主媒体层必须稳定，不得对主图 / 视频做 full-scene fade、wipe、slide-out、re-enter 或重新加载式入场；只允许文字、callout、局部高亮、`focal_region` emphasis、轻微镜头推进或信息区替换。禁止用横贯 / 纵贯扫描线、扫光、sweep、进度条等覆盖层凑动效。

#### R19 — Text timing and entrance state

多个非素材文本元素必须按完整旁白句子逐个出现，禁止 scene start 一次性全亮。文本元素服务于哪一句，就在该句开始前短暂提前显示，保证旁白读到该句时相关文本已可见。若 `scene-text-plan.json` 存在，`priority: "primary"` 的 `visual_text_units` 必须优先实现；`secondary` / `decorative` 可因安全布局降级，但必须在 `composition/DESIGN.md` 记录。旧 text beat 需要淡出或降级，不能永久累积。入场动画必须有正确初始态，避免元素在 tween 前闪现。

#### R20 — Style constraints

文字框内文字应垂直 / 水平居中。内容区不得出现 >10% 视口面积的纯空白；字幕安全区不计入空白统计，也不得为填满而把内容元素铺进该带。如需呼吸空间，用极淡装饰 / 网格 / 角标占位。Moon / 深色技术编辑风默认纯色 + 极淡网格 / 细线 / 低对比结构，禁止 `radial-gradient` spotlight、localized glow、ambient orb、neon halo、发光阴影和用 glow 充当层次感。

## Stage Protocols

Detailed Phase 8.3-8.7 execution protocol lives in `references/composition-stage-protocol.md`.

Phase 8 must use that protocol for pre-render self-audit, render requirements, sanity check, post-render Visual QA, QA report, feedback loop, stop-loss handling, and the Rule Coverage Matrix.

If `references/composition-stage-protocol.md` is missing or unreadable in the project workspace, the HyperFrames sub-agent must stop and report the missing required reference rather than inventing an audit process.
