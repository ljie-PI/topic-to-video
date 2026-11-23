# cover 委派包 — 基础指令（视频封面设计与确定性渲染）

你负责为已渲染完成的视频设计并生成**可直接发布的多尺寸位图封面**。封面一律用 HTML + CSS 排版、复用项目本地字体并经 `scripts/render-cover.py` 在系统 Chrome 确定性截图产出，禁用图像生成模型写字。主 agent 不预写 HTML；**严格按当前派发指令声明的尺寸与文件边界落盘，完成后立即停止并仅回复 `done` 与落盘路径清单**。

先读 handoff 的 `## Inputs` 与 `## Additional Instructions`（即 `inputs.json` 的 `cover_requests`），再按下面的约束执行。指令冲突时，按 `references/delegation/conventions.md` 的叠加顺序处理：用户在 `cover_requests` 里提出的明确要求覆盖默认规则。上游关键输入缺失或损坏时立即停止并向主 agent 报告缺项，禁自行编造。

## 一、目标与主题契约（主题一致 + 点击率优先）

- **单版融合交付**：每个目标尺寸产出一张融合「系列主题一致」与「高点击率」的成品封面。未在 `Additional Instructions` 另行指定尺寸时，默认同时产出 `1080x1440`（竖版 3:4）、`1440x1080`（横版 4:3）、`1920x1080`（横版 16:9）三套尺寸。
- **继承 `composition/design.json`，统一单套底色**：
  - 颜色与字体取自 `composition/design.json` 的 `tokens`（`--c-canvas`、`--c-card`、`--c-surface`、`--c-ink`、`--c-focus`、`--c-positive`、`--c-border`）与 `--font-sans` / `--font-mono`；通过 `<link rel="stylesheet" href="../composition/assets/fonts/<css_filename>">` 引入本地 WOFF2 字体，数字启用 `font-variant-numeric: tabular-nums`。
  - 选定**一套统一的底色与明暗方案**贯穿全部尺寸（直接沿用主题底色，或为强化压图反差统一采用同色系深底），不为不同平台拆成多套底色。
  - 主题一致与点击率冲突时：色板语义与字体服从主题一致；构图聚焦度、背景压暗幅度与信息精简度服从点击率（保证缩到 `400px` 宽时 3 秒内读出钩子）。
- **剥离播放态与冗余条带**：正片的 `nav-bar`、`caption-bar`、页脚说明及顶部品牌信息条（**禁放 `.bar`**）一律不上封面。整张封面只保留四类核心要素：两行钩子主标题、`1–3` 个重要数字、关键画面主体、固定位招手主持人。

## 二、钩子与重要数字

1. **主标题钩子（`<h1>`）**：对齐正片开场钩子逻辑，提炼视频开头最抓眼球的核心支点——可以是**反常识反转**（直觉与真实结果正面相撞）、**最大数字落差**（同一尺度下的强反差）、**真实困境 / 两难突破**，或**最有解释价值的已验证结果**：
   - 固定拆成 **2 行短句**，文案目标每行 **≤ 8 字**（机器检查按行非空白字符硬上限 **≤ 10**），每行必须声明 `white-space: nowrap`；
   - 第二行可用 `--c-focus` 主色文字或实底色块突出 **1 个核心词或数字**；拒绝无信息量的定语堆砌。
2. **重要数字（`.stats` 内的 `1–3` 个 `[data-num]`）**：从 `research-brief.md` 与 `script.txt` 挑出 **`1–3` 个最关键的已核实数字**（如核心性能指标、同口径对照 `50.0% → 95.8%`、耗时/成本/规模数据），每个独立数字项标注 `data-num`（总数 `1..3`；仅调研简报确无核实数字时传 `--allow-zero-num`）。
3. **证据边界**：所有事实、数字、单位与对照条件必须可追溯到 `research-brief.md` 且与 `script.txt` 口径一致；禁用 `Open questions / contradictions` 中的未核实数据，禁用“震惊 / 最强 / 碾压 / 彻底颠覆”等无出处形容词。

## 三、关键帧截取与素材预处理

1. **截取前 15 秒与全片最重要的 `1–2` 帧**：对照 `script.txt`、`transcribe/timeline.json` 与 `composition/scene-config.json`，从 `composition/renders/final.mp4` 的**前 15 秒（开场钩子画面）以及全片最核心的内容场景**中截取最具代表性的 **`1–2` 帧关键画面**（若 `material-catalog.json` 中有对应场景的更高清原图，可结合使用；图片 `local_path` 相对 `harvest_page/`）。
2. **Pillow 裁净保留区与黑边**：所有预处理文件写入 `{ws}/cover/assets/`，严禁修改上游原文件：
   - 对照 `scene-config.json` 对应场景的 `regions`，裁掉正片 `nav-bar`、`caption-bar` 及内嵌 `presenter` 保留区（避免与封面主持人重影），并切掉录制黑边（逐行/逐列像素均值 `< 12`）；
   - 避开明显遮挡主体的鼠标指针或系统 HUD 残影，按目标构图框用 `PIL.Image` 裁出清晰局部特写（单帧大图，或主次分明的 1–2 帧组合），禁把远景小字原图直接塞进小框。
3. **准备招手主持人立绘**：将 `modules/components/presenter/images/presenter-wave.png` 原样复制到 `cover/assets/presenter-wave.png`（`1:1` 透明底 PNG，禁止裁切或改比例）。

## 四、分尺寸版式、固定主持人位与 DOM 契约

每个目标尺寸单独编写一份 `cover/cover_{W}x{H}.html`，禁缩放同一份 HTML 充当多尺寸：

- **画布与选择器规则**：
  - `html, body` 锁死精确像素尺寸：`width: {W}px; height: {H}px; margin: 0; padding: 0; overflow: hidden; position: relative;`；**严禁使用 `vw` / `vh` 视口单位**。
  - 所有 `<img>` 样式选择器末端必须带显式类名、ID 或属性（如 `.hero img.bg`、`.presenter img.presenter-art`），**严禁写 `img` 或 `.hero img` 等裸 `img` 选择器**。
- **DOM 语义与几何硬指标**：
  - 顶层视觉块显式标注 `data-block`（`<h1>`、`[data-subject]`、`.stats`、`.presenter` 及可选角标总数 **`1..5`**）；
  - `[data-subject]` 主体区可视面积占画布 **`45%–65%`**（竖版 `1080x1440` 建议 `55%–65%`）；
  - `<h1 data-block>` 内固定两个 `<span data-line>` 子元素（均设 `white-space: nowrap`），标题文字与实际背景的中位明度差 **`>= 60%`**（标题压在图或深底上时，叠加径向暗化 + 文字侧线性压暗 + `--c-focus` 低透明叠色至少三层背景处理）；
  - `.stats`（加 `data-block`）承载 `1–3` 个 `[data-num]` 数字项，与 `<h1>`、`.presenter` 互不重叠；
  - **横版（`1440x1080`、`1920x1080`）统一左文右图分栏**：左栏排 `<h1>` 与 `.stats`，右栏排 `[data-subject]`，`<h1>` 各行右缘与 `[data-subject]` 左缘保持 **`>= 40px`** 水平净距；
  - **`1920x1080` 右下角避让**：右下 **`190×80px`（`x >= 1730, y >= 1000`）** 留给平台时长角标，`<h1>`、`.stats`、`[data-num]`、`.presenter` 与任何 `.cta` 均不得侵入。
- **招手主持人（`.presenter`）固定位置与缩放比例**：
  每份封面必须挂载 `<div class="presenter" data-block><img class="presenter-art" src="assets/presenter-wave.png" alt=""></div>`，设 `position: absolute; z-index: 20; pointer-events: none;`，内部图片设 `width: 100%; height: 100%; object-fit: contain; display: block;`，严格锁定以下固定像素框（机器自检容差 `±2px`，防止跨次生成位置大小不一致）：

  | 画布尺寸 | `.presenter` 固定像素框（`left / top / width / height`） | 版面配合 |
  |---|---|---|
  | `1080x1440` | `left: 724px; top: 1084px; width: 320px; height: 320px;` | 右下固定位（右/下边距 `36px`）；左侧 `x <= 700px` 排 `.stats`，`<h1>` 排上方 |
  | `1440x1080` | `left: 1064px; top: 704px; width: 340px; height: 340px;` | 右下固定位（右/下边距 `36px`）；左栏排 `<h1>` + `.stats`，右栏排 `[data-subject]` |
  | `1920x1080` | `left: 1320px; top: 664px; width: 380px; height: 380px;` | 底边距 `36px`，右缘 `1700px` 避让右下时长角标；左栏排 `<h1>` + `.stats` |

  （若用户指定了其他自定义尺寸：竖版 `W <= H` 取 `size = round(W * 0.296)`、右/下边距 `round(W * 0.033)`；16:9 横版取 `size = round(H * 0.352)`、`left = W - max(220, round(W * 220 / 1920)) - size`、下边距 `round(H * 0.033)`；其他横版取 `size = round(H * 0.315)`、右/下边距 `round(H * 0.033)`。）

## 五、工作顺序（按派发批次边界执行）

默认采用「主会话预取 `cover/assets/` + 子会话按单尺寸并行写 `cover_{W}x{H}.html` + 主会话中心化渲染验收」（确需目检参考图时先缩至宽 `≤ 640px` 单张查看）：

1. **定内容与选帧**：主会话已预取 `cover/assets/` 并给定钩子/数字口径时直接复用；未预取时通读 `research-brief.md`、`script.txt`、`timeline.json`、`design.json`、`scene-config.json` 与 `cover_requests` 定下两行钩子、`1–3` 个重要数字与统一底色，截取 `1–2` 帧裁净存入 `cover/assets/` 并拷入 `cover/assets/presenter-wave.png`。
2. **编写独立 HTML**：按第四部分契约编写本批指定的 `cover/cover_{W}x{H}.html`（限定单尺寸派发时写完即停，不内嵌第 3–4 步）。
3. **确定性渲染与机器自检（默认主会话执行）**：运行 handoff 中的 `scripts/render-cover.py` 命令生成 `cover_{W}x{H}@2x.png`、`cover_{W}x{H}.png`、`cover/qa/thumb_{W}x{H}_400w.png` 与 `cover/cover-report.json`。逐条修复全部 `findings` 并复核收紧 `warnings`，每次改完重跑，确保最终 `verdict == "pass"`。
4. **`400px` 缩略图三问验收**：对每张 `cover/qa/thumb_{W}x{H}_400w.png` 运行 `scripts/vision-analyze.py`（配置了 `VLM_API_KEY` 走 Mode 1；返回 `delegate_to_agent` 时用自身看图工具直接查看），逐张核对三个客观问题：
   - **3 秒内读到的第一句话是什么？**（须等于设定的两行钩子；若遇 `400px` 小图中文近形字误认，对照 `@2x.png` 与 HTML 原文确认无截断/叠字，勿误改已核实文案）
   - **画面主体是什么、占画面大概多少？**（须能清晰辨认所截核心画面与右下招手主持人，主体占 `45%–65%`）
   - **整张图有几个明显的视觉块？**（须 `<= 5`，且标题与数字对比清晰）
   任一项不达标即回退调整构图、裁剪或压暗后重跑第 3–4 步。
5. **写出摘要并报告**：写出 `{ws}/cover/cover-summary.md`（写明钩子文案、`1–3` 个重要数字口径、所截 `1–2` 帧的时间点与场景来源、各尺寸成品路径及 `400px` 缩略图三问结论），向主 agent 报告 `cover/cover-report.json`、`cover/cover-summary.md` 与各尺寸封面路径。
