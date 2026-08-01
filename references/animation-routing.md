# Animation Routing Reference

本文件是 Phase 8 的动画软路由。`references/composition-rules.md` 的 R18 决定必须如何选择、记录和验证动画；本文件只提供候选机制、布局约束与 runtime 选择提示，**不是 `visual_role → effect` 的一对一模板**。

## Source of truth and discovery

HyperFrames 当前安装版本的动画能力以外部 skills 为准。authoring 前先加载 `/hyperframes-animation`，读取：

- `rules-index.md`：原子 motion recipes；
- `blueprints-index.md`：多阶段 scene choreography；
- `transitions/overview.md` 与 `transitions/catalog.md`：scene handoff；
- `techniques.md`：SVG、Canvas、CSS 3D、Lottie、MotionPath、shader 等技术菜单。

需要 shared element / FLIP、path、mask、SVG morph/draw、DOM 3D、Three.js / WebGL keyframes 时，再加载 `/hyperframes-keyframes`。确定 effect / blueprint 后只读取对应 recipe 和实际 runtime adapter；不要预读全部实现文件，也不要把本文件当作 HyperFrames 能力全集。

## Selection model

每个 scene 按以下顺序选择动画：

1. 完整旁白句子与 `semantic_intent`；
2. `primary_subject` 及需要证明的状态变化；
3. `visual_role` 提供的信息动画候选；
4. `layout_role`、素材比例、`focal_region`、continuation 状态施加的运动边界；
5. orientation、density、可读时间与前后 scene continuity；
6. 选一个 `signature_mechanism`，按需增加少量 supporting mechanisms；
7. 最后选择最小合适 runtime。

候选机制可以组合、替换或不用。未采用表中候选时，只要替代方案更能表达 scene 语义，并在 `composition/DESIGN.md` 记录理由，即为合法。

## Visual-role candidates

| `visual_role` | Primary candidates | Optional supporting mechanisms | Avoid |
| --- | --- | --- | --- |
| `title` / `section_divider` | waterfall entry、masked line reveal、kinetic type、fixed-anchor reveal | variable-font axis、zoom-through、titlecard reveal | 整场只有低速 opacity fade |
| `product_card` | card morph anchor、anchored expand、surface assemble | Lottie brand asset、HTML-as-texture hero、cursor press | 无产品行为的空泛 3D spin |
| `big_number` | count-up、dynamic scale、single stat hit | ring / bar fill、camera landing、keyword emphasis | 所有数字同时出现后 idle pulse |
| `data_block` / `metric_strip` | staggered metric reveal、stat bars / fills | count-up chord、active metric stepping | 把数据只做成普通文字 fade-in |
| `chart` | SVG / path draw、bar / area build | chart scrub readout、marker travel、camera focus | 图表整张一次淡入且无数据推进 |
| `data_table` | row / column reveal、primary-row highlight、pagination | shared-axis state change、detail zoom、summary rail | 大表整体缩小后逐字淡入 |
| `process_flow` / `timeline` | ordered node reveal + connector draw | MotionPath follower、camera follow、stage focus | 所有节点与连线一次全亮 |
| `state_machine` | explicit state transitions、active-path progression | shared element / FLIP、control-target sync | 只有装饰粒子、不表现状态变化 |
| `architecture_diagram` | layer assemble、primary-path reveal | depth scatter、camera journey、rack focus | dense full diagram 统一 scale pop |
| `network_graph` | node cascade + connector draw | constellation hub、cluster focus、3D depth | 全节点同速漂浮或呼吸 |
| `list` / `feature_grid` | waterfall / grid assemble、ordered reveal | focus cycle、nudge curve、item status change | 所有条目 scene start 全亮 |
| `leaderboard` | ordered rank reveal、active-row progression | count-up、fixed-anchor cycle、rank swap | 每行相同 fade，没有主项变化 |
| `comparison_matrix` / `pros_cons` | mirrored reveal、shared-axis comparison | shared element / FLIP、card morph、split tilt | 两侧无因果的相反方向乱飞 |
| `code_block` / `terminal_block` | discrete typing、line-by-line reveal、execution state | cursor tracking、keyword highlight、camera focus | 完整文件 / 日志一次出现 |
| `file_tree` | branch expansion、selection path | panel live-sync、shared element、focus window | 所有层级一起淡入 |
| `callout` / `annotated_media` | marker draw、connector draw、focal emphasis | tracking box、rack focus、cursor point | callout 覆盖素材关键区域 |
| `quote` / `definition` / `qa` | line / word reveal、fixed-anchor cycle | focus-blur resolve、shared-axis handoff | 长段文字逐字符拖慢可读性 |

## Layout-role motion constraints

| `layout_role` | Motion envelope | Required / forbidden behavior |
| --- | --- | --- |
| `no_match` | 可自由使用 typography、data、SVG、DOM 3D、Canvas / WebGL | 仍需由信息关系驱动，不因无素材就堆装饰 effects |
| `media_first` | camera intent、focal traversal、外置 annotation、分时信息 | 主媒体保持视觉主体；文字动画不得抢占或覆盖关键区域 |
| `video_first` | 视频承担主要运动，辅以短 label、状态、局部 emphasis | 不额外叠长段 overlay；近静止视频按静态图片处理 |
| `media_continuation` | 主素材保持位置、尺寸、裁切窗口与视觉锚点；更新解释层 | 禁止主媒体 full-scene fade、wipe、slide-out、re-enter 或重新加载式入场 |
| `viewport_reveal` | 沿素材长轴 pan / scroll，按 transcript 到达重点 | 必须覆盖 catalog 的 start / mid / end、`focal_region` 或避开 avoid-region |
| `band` | 沿长轴 reveal、scrub、highlight stepping | 不得用 3D 倾斜或过小缩放降低 band 可读性 |
| `detail_callout` | focal shift + 一次一个外置 callout | 可用 marker / connector / rack focus；不得遮关键内容 |
| `comparison_pair` | mirrored、shared-axis、同步 scrub、FLIP | 两个素材保持同等可读权重；portrait 优先上下或分时 |
| `comparison_sequence` | pagination、carousel、fixed-anchor cycle | 一次突出一个或少量素材；不得三等分小宫格硬塞 |

## Orientation modifiers

- Landscape 可使用横向 flow、左右 shared-axis、宽 chart scrub 和横向 camera travel，但仍须遵守素材比例与字幕安全区。
- Portrait / vertical 中，流程、时间线、状态机优先纵向推进；榜单、表格、图表优先分页 / 分时 / 主项高亮；架构和网络图优先 focus window / primary path。
- orientation 只改变运动几何和信息密度，不改变 scene 的 semantic intent。不得靠缩字号或缩素材保留横屏 choreography。

## Runtime selection

Runtime 是实现选择，不是视觉丰富度指标。不要为了“充分利用能力”而在同一视频无意义覆盖所有 runtime。

| Runtime | Use when | Do not choose merely because |
| --- | --- | --- |
| GSAP | 默认 timeline、stagger、transform、SVG、camera choreography、semantic labels | 想给所有 scene 统一 fade / slide |
| CSS animations / WAAPI | 单元素、有限 keyframes、简单装饰或生成式 DOM keyframes | 复杂 scene sequencing 可以勉强拆成 delays |
| Anime.js | 用户明确要求、已有 Anime.js recipe，或其 API 明显更小更清楚 | 只是为了和 GSAP 不同 |
| Lottie / dotLottie | 已有本地 `.json` / `.lottie` 资产或明确的 AE export | 没有资产却想让普通 DOM 动画显得高级 |
| Three.js / WebGL | 真实 depth、camera/object motion、GLTF、shader、canvas internal motion | 普通卡片 tilt / scale 已能证明语义 |
| TypeGPU / WebGPU | 明确需要 WGSL、compute、GPU particles、liquid / glass，且环境支持 | 只需要普通背景或简单粒子 |

HTML-as-texture、shader、Three.js、TypeGPU 等 hero treatment 通常只用于少量关键 beat；其余 scene 使用清晰、可读、可维护的 DOM / SVG choreography，让 hero beat 的差异真正成立。

## Global motion palette

- 全片建立可复用的 motion vocabulary，而不是每场使用全新 effect。
- ordinary seams 使用稳定的 primary transition；topic change、climax、outro 才使用 accent transition。
- scene 之间可复用同一 motion family，但连续 scene 不得无理由重复完全相同的 `entry + information reveal + transition` 组合。
- 一个 scene 通常选择一个 signature mechanism，并按需增加少量 supporting mechanisms；effect 数量不是质量指标。
- 静态素材的持续视觉行为必须推进理解，例如 focal traversal、staged annotation、camera intent、detail reveal；idle drift、breathing、glow pulse 不能单独满足 R18。

## Example resolutions

```text
chart + no_match + portrait + narration explains a trend
→ single vertical chart
→ SVG path draw
→ marker follows narrated points
→ numeric readout updates
→ choose GSAP + SVG only after mechanism is fixed
```

```text
architecture_diagram + media_continuation + landscape
→ keep the same diagram and viewport stable
→ draw / emphasize one primary path per sentence
→ rack focus between layers if needed
→ do not fade or re-enter the diagram at the scene boundary
```

```text
annotated_media + detail_callout + vertical
→ move reveal viewport to the catalog focal region
→ draw an external connector
→ reveal one short callout at the sentence onset
→ keep all foreground elements outside the subtitle safe area
```
