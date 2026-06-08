# Composition Brief — <TOPIC>

## Project
- Topic：<Phase 1 中给出的一句话描述>
- Target duration：<N> 秒
- Orientation：<1920x1080 | 1080x1920 | 1080x1440>
- Output：./composition/renders/final.mp4

## Inputs
路径相对于本 brief，本 brief 位于工作区根目录。

- 最终解说音频：voice_clone/narration.mp3
- 解说脚本：narration.txt
- 带词级时间戳的 ASR transcript：transcribe/transcript.json
- 素材 catalog：material-catalog.json
- 场景-素材分配：scene-material-suggestions.json（如存在；按 Upstream Contract #11 视为素材→scene 的硬性分配）
- 已预置字体：fonts/
- 风格规范文件（如适用）：references/design-<theme>.md

## Style Hint
<来自 Phase 1 的自由格式 mood、受众、配色与节奏提示。示例：
"中文解说讲解视频，温暖的手绘笔记本氛围，节奏舒缓。"
"中文 AI/SaaS 技术编辑风，深色严肃语调，信息密集但易读，多 data callout。">

可选的风格路由参考：
- references/design-dawn.md —— 温暖手绘氛围参考
- references/design-moon.md —— 深色技术 / 编辑氛围参考
- references/palettes.md —— 备选的 mood / palette 路由

若上方 Inputs 未指定 design 文件，这些参考是 style hint，不是实现规范
若已指定 design 文件，以 design 文件中的具体数值（配色 hex 值、字体族、字重）为准，Style Hint 的自由格式描述退为补充说明。所有实际的 composition、排版、布局、动画与渲染决策，请走 `hyperframes` skill 和项目自己的 `DESIGN.md` 流程。

## Upstream Contracts
1. 音频已是终稿。不要重新生成 TTS，也不要调用 HyperFrames 的 TTS。
2. 词级时间用 `transcribe/transcript.json`。如果需要一份确定性的 scene 时间轴文件，可以在 `transcribe/` 下生成，但 scene 切分和视觉提示时间归 HyperFrames sub-agent。
3. 所有以素材为底的视觉都必须通过 `material-catalog.json` 解析。需要 catalog 素材的地方，不要凭空造一个 stock 视觉。
4. 如果从 catalog 中切出一段源视频片段，要用 `-an` 剥掉它的原始音频；`narration.mp3` 是最终视频里唯一的解说人声。
5. 字体加载用 `fonts/` 下的本地资源，确保确定性。不要依赖系统的 `fc-match` 字体。
6. 所有 composition、动画、校验与渲染工作都用 `hyperframes` 和 `hyperframes-cli` skills。父 skill `topic-to-video` 只负责上面列出的上游资源。
7. 渲染时必须传 `--workers 1`。多 worker 在本机环境会产生奇数高度帧，导致编码异常。
8. **素材容器宽高比必须匹配素材自身**。每个图片 / 视频在 `material-catalog.json` 里都带 `width` 和 `height`（图片由 harvester 抓取时写入；视频由 `video-download.py` 通过 ffprobe 写入）。把这两个字段读出来算 `aspect-ratio`（`width / height`）应用到包裹该素材的 `<div>` / `<figure>` / `<video>` 容器上——禁止默认 16:9，禁止用 `object-fit: cover` 配上比例错误的容器把素材裁掉。若个别条目的 width/height 为 `null`，再回退到运行时 ffprobe 实测或 `object-fit: contain` 居中适配，不要瞎猜。
9. **素材容器必须紧贴素材，不允许可见间隙 / 错位**：
   - 容器 `padding: 0; margin: 0; border: 0; outline: 0; box-shadow: none; background: transparent`；素材本身 `width: 100%; height: 100%`。
   - **图片 / 视频素材不要做可见卡片框**：禁止给素材或素材容器加可见边框、描边、内边距、投影、glow、inset、卡片底色或其他会让素材像嵌在框里的装饰。素材尺寸不适合时，调整 layout / 缩放 / 换素材，不要用外框或底色遮丑。
   - aspect-ratio 已由 #8 与素材匹配，因此 `object-fit: cover` 或 `fill` 都不会产生 letterbox / 黑边 / 背景色边；**禁止出现 letterbox**。
   - 容器与素材的所有 transform / 动效（Ken Burns、缓移、缩放、淡入、视差）**必须绑定在同一个元素或一组同步元素**上。禁止 "容器静止、素材独立动" 或 "素材静止、容器独立动"——任一情形都会让素材跑出容器或容器露边。
   - ⚠️ **不要在同一素材容器上同时写死 `width` 和 `max-height`/`height`**。CSS 中显式尺寸约束会覆盖 `aspect-ratio`：当 `容器宽 ÷ 素材AR > max-height` 时，高度被钳矮、盒子变得比素材宽，`object-fit: contain` 立刻在左右露出容器底色（即使已声明 aspect-ratio）。按"布局尺寸"定框的布局类最易踩此坑。
   - **防弹写法**（在可用宽 `availW` × 可用高 `availH` 包络内，自动取受限维度，盒子恒等于素材比例）：
     ```css
     .media-panel{
       aspect-ratio: <W> / <H>;                       /* 素材 width/height */
       width: min(<availW>px, calc(<availH>px * <W> / <H>));
       height: auto;                                  /* 由 aspect-ratio 推出 */
       margin: 0 auto;
     }
     ```
     盒子恒等于素材比例，`object-fit` 取 contain / cover / fill 均无空带 / 裁切 / 变形。要限高就调 `availH` 输入，**禁止再单独写 `max-height` 压扁容器**。
10. **每个 scene 根元素必须带稳定 ID 与时间区间**：`composition/index.html` 中每个 scene 的根元素必须同时带这三个 data 属性，供主 agent 在 Phase 8 Visual QA Audit 中把"秒数 / 素材 src"反查到具体 scene：
    - `data-scene-id="s1"`（任意稳定字符串，**跨重渲必须保持不变**；建议 `s1` / `s2` / ... 按时间顺序编号）
    - `data-scene-start="0"`（该 scene 起点秒，相对视频开头，浮点）
    - `data-scene-end="6.5"`（该 scene 终点秒，浮点；与下一 scene 的 `data-scene-start` 相等）
    所有素材标签（`<img>` / `<video>` / 带 `background-image` 的元素）必须位于某个带 `data-scene-id` 的 scene 根元素**内部**。多次重渲只修复部分 scene 时，未修复 scene 的 `data-scene-id` 与其 DOM / CSS / 动画必须**逐字节保持不变**——主 agent 凭此校验 sub-agent 是否只动了被点名的 scene。
11. **素材唯一性**：每个 catalog 素材（图片 / 视频 clip）在整片中**恰好出现在一个 scene**，分配以 `scene-material-suggestions.json` 为准；`no_match` 的 scene 用纯排版 / 文字卡片，不借用其他 scene 的素材。
12. **字幕安全区**：视口底部预留一条高度为视口高度 12–18%（1080p 下约 130–195px）的水平带，**专属底部字幕**（见 Critical #6）。除字幕条外，任何**前景**文本 / 素材 / callout / 装饰元素**禁止进入该带**。所有 scene 的内容元素仅在"内容区 = 视口 − 字幕安全带"内排布。例外：占满画面的**全幅背景素材**可延伸至该带之下垫底（此时字幕条按 #6 的半透明遮罩压在其上，符合 #9 例外 ①）。
    - **字幕容器是全局唯一、固定锚点的单一元素**：字幕条必须是挂在 `<body>` / 根舞台下的**单个全局元素**（不是每个 scene 各写一个），跨所有 scene 复用同一个固定定位的容器，仅替换其文本内容。禁止把字幕嵌进 scene 根元素内部随 scene 布局漂移。
    - **垂直锚点固定**：字幕容器用 `position: fixed`（或相对根舞台 `position: absolute`）+ `bottom` 锚定，`bottom` 取视口高度 **6–9%**（1080p 约 65–97px，对应安全带 12–18% 的中线附近），使字幕**落在字幕安全带内并大致垂直居中**，整片所有字幕单元的基线位置**逐帧一致**。禁止用 `top` / `margin-top` / 跟随内容流的方式定位字幕（会导致字幕忽上忽下、压住内容）。
13. **每个 scene 必须按旁白和素材尺寸单独排版**：生成 scene 前，先读取该 scene 的旁白文本、`scene-material-suggestions.json` 中的 `text_beats` / `material_ref`，以及 `material-catalog.json` 中对应素材的 `width` / `height` / 类型。计算内容区尺寸（viewport − 字幕安全区 − scene padding），根据素材 aspect ratio 和 text beat 数量选择 layout archetype；相邻 scene 不得无理由复用同一主版式。典型路由：横图 / 横视频用宽幅主体 + 外置信息区；竖图用左右分栏；方图用中心素材 + 周边信息块；无素材 scene 用纯排版 / 数据块。
14. **动画前必须做 peak-state layout audit**：先排出该 scene 所有非字幕元素都显示时的最终状态，再检查并在 `composition/DESIGN.md` 记录：元素是否溢出 viewport / 内容区、任意元素块是否互相覆盖、前景文本 / tag / callout 是否覆盖 catalog 素材、素材是否出现 letterbox / pillarbox、内容区空白面积是否 > 10%、构图是否明显失衡 / 不成型。任一项有问题，必须先调整布局尺寸、位置、字号、信息密度或拆 scene；禁止靠“元素暂时隐藏”掩盖布局问题。
15. **`composition/DESIGN.md` 必须记录 scene inventory**：每个 scene 至少记录 `scene_id`、旁白摘要、`material_ref`、素材尺寸与 aspect ratio、text beats、layout archetype、peak-state audit 结果、以及每个非素材元素对应的完整旁白句子和出现时间点。

## Visual Quality Constraints

### 🔴 Critical Constraints — 违反任何一条都必须重渲，HyperFrames sub-agent 不得绕过

1. **每个 scene 5-8 秒**：普通 scene 时长上限 8 秒，超过必须拆分（**单素材合并 scene 例外，见本条下方**）。下限 5 秒以下的微 scene 可以接受（用于强节奏切片），但避免连续多个 < 3 秒的微 scene。
   - **例外（单素材合并 scene）**：由连续同素材合并而成的 scene（见 `scene-material-suggestions.json`），其**素材展示**可连续超过 8s；但 scene 内文本信息单元（标题、要点、callout 等）仍须按每 5–8s 刷新 / 轮换（对应合并前各 `text_beat`），且仍受 #2 / #3 约束。
2. **画面禁止超过 2 秒的静止**：scene 内任意时刻必须有持续视觉动效。**有效动效必须来自内容本身**：素材 Ken Burns / 缓移 / 缩放、文字渐入 / 逐字出现、数据 callout 浮现、装饰元素**极轻微** drift（低对比、不喧宾夺主）。整 scene 静帧 > 2s = 重渲。
   - **禁止用覆盖层"凑"动效**：禁止横贯 / 纵贯画面的扫描线、扫光、sweep、进度扫描条等覆盖在静止画面上的运动条纹来满足本规则。这类廉价手法不计为有效动效，且本身视为视觉缺陷 = 重渲。
3. **多个文本元素必须按句子级节奏逐个出现**：场景内 ≥ 2 个非素材文本元素（标题、要点、数据 callout、标签等）禁止在 scene 开头同时显示。先按 `transcript.json` 中的句号 / 问号 / 感叹号等切出完整句子；某个文本元素服务于哪一句，就在该句开始前短暂提前显示，保证旁白读到这句话时相关文本已经可见。非素材元素初始必须不可见；旧 text beat 要淡出或降级，禁止所有 beat 永久累积。禁止给所有 entrance tween 统一加 `immediateRender:false`；优先用 `fromTo()` 明确 hidden / offset 初态和 visible 终态，或用 CSS 初始隐藏兜底。
4. **图片素材必须有持续动效**：每张图都要有 Ken Burns（缓推 / 缓拉 / 缓移）、缩放、淡入、视差、轻微 translate 等持续动效之一；整段视频中同一类动效不得重复超过 `ceil(total_images / 5)` 次（例：10 张图同款动效最多 2 张）。视频素材视为已自带运动；接近静止的镜头（背景 plate）按图片规则补 Ken Burns。
5. **场景有图片或视频素材时，素材占据画面主体**：素材应占 ≥ 50% 内容区域，文本和装饰让位给素材，**禁止把素材缩成右下角邮票贴在大段排版文字旁边**。允许放大素材以填充画面（上限：原始短边 2x；超出 2x 画质明显劣化，请换素材或降级为缩略图 + 文字补充）。放大时仍受 Upstream Contracts #8 约束（容器宽高比 = 素材 `width/height`，禁止拉变形）；放大后必须配合规则 2 的持续动效，避免大图变成静帧。同 scene 多个素材时，优先**轮播切换**而非同屏小尺寸并列；如必须并列，每个素材 ≥ 30% 内容区域。
6. **底部字幕硬上限 1 行**：视频全程在底部**水平居中**渲染字幕条，**位于 Upstream Contract #12 预留的字幕安全区内**；字幕单元 = `transcript.json` 中按句号 / 问号 / 感叹号切出的单句。每个字幕单元渲染时**必须单行**（`white-space: nowrap` 或等价 CSS 约束），不得换行。切换时机基于 `transcript.json` 词级时间戳，与音频偏移 ≤ 0.2 秒。半透明背景遮罩确保任意画面背景下均可读。
   - 单句仍撑出 1 行时，**继续按 分号 → 逗号 → 顿号 → 自然停顿** 逐级把这一单句拆成更细的字幕单元，每段独立按词级时间戳定时切换轮播。拆分粒度：先 `。` `？` `！`，再 `；`，再 `，`，再 `、`，直到所有字幕单元都满足 1 行。
   - **禁止用以下三种方式 "塞下" 长句**：① 缩字号到下限；② 放宽 `max-width`；③ 允许换行成 2+ 行。任意一种 = 重渲。
   - 拆分后每段时长按其覆盖的词级时间戳起止重算，不要按字符数均分。
   - **背景遮罩宽度随文字自适应（shrink-to-fit）**：字幕的半透明背景框宽度必须**贴合当前文本宽度**——用 `display: inline-block` / `width: fit-content` / `max-content` 等让框宽 = 文字宽 + 左右内边距（建议各 0.6–1em）。**禁止给遮罩条写固定宽度、固定 `width: 100%`、大 `min-width` 或整行遮罩**，否则短句会出现大片空遮罩。框本身仍水平居中，因此短句的遮罩是居中的小块、长句是居中的大块。
   - **行数硬校验**：字幕容器渲染高度必须 ≤ 单行行高（`line-height` × 1 + 上下 padding）。任意字幕单元出现 2 行（容器高度超过单行）= 重渲。
7. **图片必须清晰、内容完整**：场景中显示的图片必须清晰不模糊（原图分辨率 ≥ 容器渲染尺寸，向上放大不超过 2×，禁止可见 JPG artifacts / 像素化），且关键信息（文字、图表轴线、人物面部、UI 主控件）不被裁切。模糊或被裁掉关键信息 = 重渲或换素材。
8. **元素不超界 / 不被截断**：所有视觉元素块（文字、图片、视频、装饰）的可视外边沿必须完全在画面边界（1920×1080 视口）内。禁止靠 `overflow: hidden` 把元素裁掉一半还显示；禁止文字溢出容器；禁止图片 / 视频超出视口边缘。
9. **同时显示的元素不允许重叠**：同一时刻显示的视觉元素块之间禁止 z-index 层叠遮挡。除全局底部字幕条按规则 #6 覆盖底层画面外，任何前景标题、caption、tag、badge、callout、label、数据块都不得压在图片 / 视频素材之上，包括 hero 素材。需要说明素材时，把说明文字放在素材外部信息区；空间不够就换布局、缩字号、拆 scene 或减少同屏信息量。
10. **DOM 层次扁平 + 颜色反差达标**：素材容器 / 文本容器**最多 2 层嵌套**，禁止 "框中套框中再套框" 式装饰堆叠。颜色对比度满足 WCAG AA：正文文字与背景 ≥ 4.5:1，大字号标题（≥ 24px）与背景 ≥ 3:1。
11. **字号 max/min ≤ 3，标题禁止自动换行**：同一 scene 内最大字号与最小字号比值 ≤ 3:1（例：标题 72px 时最小正文字号 ≥ 24px）。大字号标题（占主标题位的元素）禁止因字号过大而自动换行——若标题文本长到需要换行，必须用以下三种手段之一修复，**不允许单个标题文本框内折成 2+ 行**：
    - ① **缩小字号**——降到标题仍单行的尺寸（仍受本条 max/min ≤ 3 约束，不得把正文压到下限以下）；
    - ② **加宽标题文本框宽度**——在不侵入字幕安全区（Upstream Contract #12）、不超出画面边界（Critical #8）的前提下放宽 `max-width`；
    - ③ **拆成多个文本框**——把长标题按语义拆成主标题 + 副标题（或多个并列短块），每个文本框各自单行渲染。
    三种手段可组合使用；目标是任一标题文本框在最终渲染中都不出现 2+ 行折行。

### Style Constraints — 视觉风格相关，sub-agent 可在 DESIGN.md 中说明理由后微调

12. **scene 间有明确过渡**：相邻 scene 之间使用显式转场（淡入淡出、滑动、交叉溶解等），避免硬切造成视觉跳跃。
13. **文字居中 + 无大块留白**：文本框内文字垂直水平居中；**内容区**（视口 − 字幕安全区，见 Upstream Contract #12）任意时刻禁止出现 > 10% 视口面积的纯空白区域（没有任何视觉元素、纯背景色的连续块）。字幕安全区**不计入**空白统计，不得为填满而把内容元素铺进该带。如确需呼吸空间，用极淡的装饰元素 / 网格 / 角标占位。
14. **Moon / 深色技术编辑风禁止 glow 审美漂移**：若使用 `references/design-moon.md` 或深色技术编辑风，背景默认纯色 + 极淡网格 / 细线 / 低对比结构。禁止 `radial-gradient` spotlight、localized glow、ambient orb、neon halo、发光阴影和用 glow 充当层次感。

## Deliverables
- composition/index.html
- composition/DESIGN.md
- composition/renders/final.mp4
- 一段简短的完成总结，包含输出路径、ffprobe 时长和文件大小。
