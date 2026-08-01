# Layout Routing Reference

本文件负责 Phase 8 的 role 解析与布局路由。所有 hard constraints 均来自完整的 `references/composition-rules.md`（包括 R3 material authority、R5–R6 scene / continuation identity、R8–R17 layout、R20–R21 audit）；若冲突，一律以该文件为准。本文件的 `Role sources and authority` / `Input alignment` 是 R8 hard invariants 的导航性重述；material、layout-role、orientation、visual-role 表格是可替换的 presentation 候选，不是一对一模板。

## Reading scope

建立 scene inventory 后先读 `Role sources and authority`、`Fallback precedence and role definitions`、`Input alignment`、`Resolution order` 和全局 `Density and degradation`，再读取当前 scene 命中的 material condition、显式 / 推导 `layout_role`、orientation、实际存在的 `visual_role`，以及最终选择的 presentation / `cross_aspect_strategy` 行。无需为一个 scene 加载无关 role 的候选布局。

## Role sources and authority

### `visual_role`

- 主要来自 `scene-text-plan.json` 的 `visual_text_units[].visual_role`，描述信息形态，不是可见文案，也不是固定模板。
- 上游 role 存在时，Phase 8 读取并视觉化它，不得为了套模板随意把 `chart`、`process_flow`、`architecture_diagram` 等改成普通 `list`。
- `visual_role` 名称及其中英文直译不得作为标题、label、eyebrow 或正文；可见文字只用 `display_text`、`supporting_points` 等真实内容。
- 没有 `scene-text-plan.json` / `visual_role` 时，不得虚构 role；应按旁白、`semantic_intent`、`primary_subject`、text beats 和素材直接选择 layout。

### `layout_role`

- 优先读取 `scene-material-suggestions.json` 的 `layout_role`，并与 `material_ref` / `material_refs` / `no_match`、continuation metadata 一起解析。
- 上游给出合法 role 时优先执行。素材 assignment 不得被 text plan 或模板覆盖。
- role 缺失时，Phase 8 按下方 `Fallback precedence and role definitions` 推导并记录依据，不得只写 “auto”。
- 上游 role 与 R9–R15 的比例、可读性、字幕安全区或 overlap hard constraint 冲突时，不得硬套。保留其语义意图，选择合法 `cross_aspect_strategy` / presentation，并在 `composition/DESIGN.md` 记录；无法兼容时停止并反馈 handoff conflict。

### Fallback precedence and role definitions

只有缺失上游 `layout_role` 时才运行本节；顺序是 continuation metadata → material count / readability → single-material affordance / kind。命中前一项后不再用后项覆盖。

推导前先做输入冲突检查：`no_match: true` 与 `material_ref` / 非空 `material_refs` 并存时，停止并反馈 handoff conflict；continuation metadata 只出现一部分、指向非相邻 scene、material 与 group 起点不同或未满足 R5–R6 时，同样停止，不得靠 fallback 修复。

| Priority | Inferred `layout_role` | Trigger | Semantic meaning | Guard |
| --- | --- | --- | --- | --- |
| 1 | `media_continuation` | 完整合法的 `continuation_group_id` / `continuation_of` 等 metadata 已存在，但后续 scene 只缺 `layout_role` 字段。 | 同一证据继续讲解，保持视觉锚点，只更新解释层。 | 仅补全漏标 role；没有 continuation metadata 的跨 scene 复用是 R6 违规，必须停止，不得推导。 |
| 2 | `no_match` | 没有 `material_ref`，且 `material_refs` 缺失或为空；或上游明确 `no_match: true` 且没有素材 assignment。 | 本 scene 由 typography、data、flow、diagram 等信息结构承担叙事。 | 不得借用其他 scene 的 catalog 素材；与素材 assignment 并存即冲突。 |
| 3 | `comparison_sequence` | 三个及以上素材；或恰好两个素材但并列 / 上下同屏无法满足 R11 可读性。 | 多个证据按时间逐个 / 分组比较。 | 不默认三等分或小宫格；必要时分时或拆 scene。 |
| 4 | `comparison_pair` | 恰好两个需要同等比较的素材，且两者同屏能满足 R11。 | 两个对象并排或上下形成可读对照。 | 一旦实测不可读，改为 `comparison_sequence`，而不是压小。 |
| 5 | `detail_callout` | 单素材；旁白明确解释局部细节，且 catalog `focal_region` / avoid-region 或可验证的关键区域支持该焦点。 | 保留来源素材，以局部窗口与外置 callout 解释一个重点。 | 不能凭作者临时 marker 推导；不得裁掉 catalog source figure 的必要结构。 |
| 6 | `band` | 单个 ultra-wide / strip 素材可在内容区内形成满足 R11 / `T-MEDIA` 的足够高信息带。 | 让长条素材以可读横带成为主体。 | 不能成为细线；不可读时继续评估 `viewport_reveal` / 分时 / 拆 scene。 |
| 7 | `viewport_reveal` | 单素材满足 R10 reveal eligibility，且 traversal / focal-window 本身是 scene 的主要 presentation。 | 通过窗口沿长轴或重点区域阅读极端比例素材。 | `full_fit` 必须未通过 `T-FIT`，或存在 catalog focal-window 证据；marker 不能自证 eligibility。 |
| 8 | `video_first` | 单个主视频，且没有命中更高优先级的 specialized presentation。 | 视频行为 / 时间变化是主证据，文本只作短解释。 | 近静止视频在 motion 上按图片处理，但 layout 仍可保持 video-first。 |
| 9 | `media_first` | 单个主图片 / screenshot / figure，且没有命中更高优先级。 | 图片证据占据内容区主体，信息在外部或分时解释。 | cross-aspect 时可保留 media-first 语义，并另选合法 reveal strategy。 |

`detail_callout` / `band` 是有证据的 single-material specialized fallback，不是仅凭素材数量得到的通用默认。Phase 8 authoring 时使用 catalog 源尺寸、预估内容区和输出 orientation 按 `T-FIT` / `T-MEDIA` 预判；Phase 8.3 必须用实测 `CW` / `CH` / `MW` / `MH` 复核。实测不通过时重新路由，不得用 marker 或 DESIGN.md 说明替代 gate。

## Input alignment

1. 以 `scene_index` 为 key 对齐 `scene-text-plan.json` 与 `scene-material-suggestions.json`；不得按数组位置猜测。
2. 先解析 `material_ref` / `material_refs` / `no_match`、`layout_role` 和 catalog `width` / `height` / kind / `layout_affordance` / `focal_region`，再解析 visual text units。
3. `display_text` 通常映射为标题 / 标签；`supporting_points` 映射为列表项、流程节点、指标、模块、关系节点或代码 / 命令行内容。
4. `priority: primary` 的 unit 必须尝试实现；`secondary` / `decorative` 可合并、缩短、轮换或降级，并在 `composition/DESIGN.md` 记录。
5. `template_hint` 与 role、table / chart shape、素材或 orientation 冲突时忽略，并记录理由。
6. 只有已存在 `chart` unit，或 `data_table` 明确提供可 chart 的 numeric series / highlighted dimensions 时，才能把 table 转为 chart presentation。

## Resolution order

```text
output orientation + content area
→ material assignment / no_match
→ explicit or inferred layout_role
→ material kind / ratio / focal region / continuation
→ visual_role / priority / density / shape（如存在）
→ material-aware constraints
→ layout-role envelope
→ role-specific presentation
→ final layout + cross_aspect_strategy
```

最终选择的是 layout presentation，不是重写 role。例如：

```text
layout_role = media_first
material = ultra-tall
orientation = landscape
→ 保留 media-first 语义
→ cross_aspect_strategy = viewport_reveal
→ 大 reveal viewport + 外置信息区
```

## Material-aware routing

| Scene condition | Landscape | Portrait / vertical |
| --- | --- | --- |
| `no_match` | 按 role 使用 rank list、flow、table / chart、grid / rail、grouped layers 等信息布局。 | 按 role 使用纵向链、行卡 / 分页、纵向卡片、focus window / primary path；避免横向窄列。 |
| 横图 / 横视频 | 宽幅主体 + 外置信息区 / metadata band / 分时区；不得压素材。 | 原比例 wide media slab 放上部或中上部；超宽且重点分散时横向 reveal。 |
| tall / ultra-tall | 按 `T-FIT` 判定；不达标时 key-region-aware `viewport_reveal`，不得缩成窄条。 | 按 `T-FIT` 判定；其余宽度驱动 reveal，沿长轴覆盖重点。 |
| ultra-wide / strip | 使用足够高的 `band` 或横向 reveal。 | 横向 reveal、分时或拆 scene；不得完整缩成细条。 |
| square-ish / UI screenshot | 居中或偏侧主体 + 外置信息块；必要时只实现 primary unit。 | 上下分区或居中主体 + 短 callout；过密时分时。 |
| catalog 论文 figure / table / chart 素材 | 保留来源图形、轴线、图例、caption、关键曲线 / rows；外置解释 1–3 个结论。 | figure slab / reveal + 一次一个外置 callout；reveal 必须遍历所有必要结构，必要时拆 scene；不得裁切、抽取或重画为“只保留 primary rows / points”的新图。 |
| structured `data_table` / `chart` visual unit（不是 catalog source graphic） | small / medium 可 table / chart + highlights；large 分页、摘要或拆 scene。 | 可保留 primary rows / columns / points，使用行卡、分页、分时或拆 scene；table 转 chart 仍须满足 `Input alignment` 第 6 条。 |
| 视频 clip | 视频主体优先；只用短 label、状态或时间点 callout。 | media slab 或安全近全幅背景；复杂结构信息拆到相邻 scene。 |

## Orientation modifiers

| Output | Generic layout behavior |
| --- | --- |
| `1920x1080` | 可用左右分栏、宽幅素材 + 信息区、下方 rail；流程可横向或纵向；list / grid 通常 2–4 项。 |
| `1080x1440` | 优先 60/40、55/45 或其他上下分区；不得直接套横屏右侧栏；流程 / 时间线纵向；table / chart / leaderboard 分页、分时或主项高亮。 |
| `1080x1920` | 优先纵向叙事和分时轮换；避免左右窄栏；architecture / network 使用层级、focus window 或 primary path；metric / data block 最多 2 列。 |

portrait / vertical 的内容区必须先扣除 R15 字幕安全区。信息过密时优先轮换、分页、降级 secondary / decorative 或拆 scene，不得缩字号、缩素材或侵入字幕带。

## Layout-role routing

| `layout_role` | Landscape | Portrait / vertical | Required / forbidden |
| --- | --- | --- | --- |
| `no_match` | 按 `visual_role` 使用 flow、table / chart、grid / rail、cards。 | 纵向节点链、分页 / 分时、纵向卡片或最多 2 列。 | 不借用其他 scene 素材。 |
| `video_first` | 视频尽量接近内容区可用宽高。 | 横视频放上半屏或中上部清晰 slab。 | 只允许短、shrink-to-fit overlay，遵守 R12。 |
| `media_first` | 主图按可用宽高共同计算；极端比例按 `T-FIT` / reveal。 | 横图用 slab + 上下信息区；竖图宽度驱动 reveal。 | 标题 / 信息块不得不必要压小主媒体。 |
| `media_continuation` | 保持主素材位置、尺寸、裁切窗口和视觉锚点。 | 同左。 | 只刷新解释、局部强调或 focal region；不得重新入场。 |
| `viewport_reveal` | 极端比例素材进入 scene-appropriate viewport，沿长轴 pan / scroll。 | 横图横向 reveal；竖图宽度驱动纵向 reveal。 | 窗口满足 `T-REVEAL`，覆盖 start / mid / end 和重点。 |
| `band` | 超宽素材作为足够高的可读信息带。 | 仅在足够高时使用，否则 reveal / 分时 / 拆 scene。 | 不得成为细线。 |
| `detail_callout` | 关键区域 + 外置信息解释。 | 局部窗口 / slab + 一次一个 callout。 | callout 不得压素材关键内容。 |
| `comparison_pair` | 两个素材优先左右并排，统一高度或可读尺度。 | 优先上下或分时。 | 两个素材都必须可读。 |
| `comparison_sequence` | 两个素材无法同屏可读，或三个以上素材时使用 carousel / 分时，必要时拆 scene。 | 一次一个或少量一组。 | 两素材 sequence 也不得同时压小；不默认三等分或小宫格。 |

## Visual-role presentation

| `visual_role` | Landscape | Portrait / vertical |
| --- | --- | --- |
| `title` / `product_card` / `section_divider` | 大标题、身份卡或 product card + 短 metric / tagline。 | 纵向堆叠和 title / subtitle 分层，避免贴顶小字。 |
| `leaderboard` | rank list + detail rail / highlighted row / optional readable preview。 | 纵向榜单、分页 Top N、一次突出一个条目。 |
| `big_number` | 大数字 hero、单指标冲击卡或 summary rail。 | 大数字 + 短解释纵向堆叠，避免多指标同屏。 |
| `data_table` | small（≤3 rows、≤3 columns、cells short）可 compact；medium（4–8 rows 或 4–5 columns）使用 table + highlights / summary；large（>8 rows 或 >5 columns）必须 summarize / paginate / split，只有 R8 允许时才转 chart。 | small 可 compact table / mini-table；medium 转行卡 / 分页；large 只保留 primary rows / columns、分页 dimensions 或拆 scene。 |
| `chart` | single chart、chart + summary rail、2–3 个 small multiples。 | 单 chart、纵向 chart cards、分页 / 分时；避免 3 个以上小图。 |
| `process_flow` / `timeline` / `state_machine` | 可横向或纵向，通常 3–5 个可读节点。 | 优先纵向步骤链 / 路径、分页或分时；禁止 3 个以上横向窄节点。 |
| `architecture_diagram` / `network_graph` | grouped columns、layered bands、readable clusters。 | 模块层级、focus window、primary path；避免 dense full graph。 |
| `data_block` / `metric_strip` | 横向指标条、2x2 grid、compact cards。 | 纵向或最多 2 列；不得靠缩字号塞指标。 |
| `list` / `feature_grid` | 2–4 项 grid / rail，每项短 label + 一行 detail。 | 纵向卡片或最多 2 列；过密时轮换 secondary。 |
| `comparison_matrix` / `pros_cons` | side-by-side matrix / 双列对比。 | 上下分组或分步对比；不得压进窄列。 |
| `code_block` / `terminal_block` / `file_tree` | 单个宽面板 + 短解释，只显示关键行。 | 单个可读面板 + 上下解释；长行截断 / 摘取。 |
| `callout` / `quote` / `annotated_media` / `definition` / `qa` | 外置 rail / band，或 R12 允许的短 overlay。 | 素材外纵向堆叠或一次一个 callout，避免窄 side rail。 |

## Density and degradation

portrait / vertical 中，多元素 / 结构型 role 不得沿用横屏窄列 / 多列硬排。遇到文本框过窄、字号触底、label 多次换行或节点 / 行 / 卡片不可读时：

- `process_flow` / `timeline` / `state_machine` → 纵向节点链；
- `data_table` / `chart` / `leaderboard` → 分页、分时或主项高亮；
- `list` / `feature_grid` / `metric_strip` / `data_block` → 纵向卡片或最多 2 列；
- `architecture_diagram` / `network_graph` → focus window / primary path；
- 仍不可读 → 拆 scene。

不得用缩字号、隐藏 peak-state 元素、延迟显示或压小主素材来掩盖 layout 失败。
