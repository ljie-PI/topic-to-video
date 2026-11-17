# YouTube 下载、主题质感、`modules/motions` 模块化与画面检查优化计划

日期：2026-11-17

状态：待实施；本计划定义要解决的通用问题、结合现有 skill 框架的实现方法及具体实施步骤。

---

## 1. 要解决的问题与根因

结合仓库现有流水线结构与成片质量问题，本次聚焦解决以下四类通用根因：

| 编号 | 实际问题 | 仓库现有根因 |
| --- | --- | --- |
| **P1** | **YouTube 视频下载频繁失败或误判成功** | ① `yt-dlp` 仍被列为系统依赖而非项目 `.venv` 依赖，且 `04-material-harvest.md` 命令未激活 `.venv`，导致系统 `yt-dlp` 无法加载 `.venv` 内的 PO Token 插件；② `scripts/video-download.py` 在目标目录原地比对变化文件并在无变化时回退读取目录全部旧文件，且缺少 PO Token 仅返回 storyboard 时未校验有效视频流即更新 manifest 为已完成；③ `detect_common_issue()` 仅返回错误字符串、无结构化 `failure_kind`，不利于机器人验证（`LOGIN_REQUIRED` / `Sign in to confirm you’re not a bot`）单次早停。 |
| **P2** | **SVG 画面粗框、纯色单调缺乏质感，且缺少可复用的 `motions` 模块** | ① `modules/designs/designs.md` 规定纯实色 `--c-card` 盖在纸纹上、统一 `2px` 边框且禁微阴影与辅助底纹，导致实底遮死 `#ground` 纸纹，SVG 小节点与辅助线全被画成等粗 `2px` 框（小 `viewBox` 缩放后更粗）；② `modules/motion.md` 只是孤立的可跳过参考文档，`modules/patterns/` 下 18 份文档均为 `## 已有实现：尚无`，缺少与 `components/`、`transitions/` 同构的可复用动态模块。 |
| **P3** | **`landscape-presenter` 主副展示区文案重复** | 横屏主持布局包含 `header`、`main` 和 `side`，文档未明确 `side` 的按需启用原则与跨区信息分工，导致子 agent 习惯同时填满主副两区，将 `main` 中的文字在 `side` 卡片里重复堆砌。 |
| **P4** | **渲染前检查缺少排版/清晰度质量信号，且长片编写缺少容量护栏** | ① Phase 8 `scripts/check-composition.py` 目前未在 `warnings` 中提示 SVG `<text>` 超出承载框、媒体可视区域过小、缩放失真风险、元素重叠、遮挡媒体、跨区文案重复与跨场素材复用；② 多场景长片若在单次输出中拼接巨型单文件或批量用看图工具打开全部原图，易触发模型输出/多模态图片上限（`413` / `400`）。 |

---

## 2. 结合现有 Skill 框架的实现方法

沿用仓库既有模块化与流水线分层结构，通过以下通用方法落地：

1. **把 `motion` 升级为一等模块目录 `modules/motions/`，打通现有 `patterns/`**：
   - 替代孤立的 `modules/motion.md`，采用与 `components/`、`transitions/`、`templates/` 完全一致的组织与说明方式：`modules/motions/motions.md`（总索引、采用规则、接口与扩展约定）+ `modules/motions/<name>/<name>.{md,html,mjs}`（`<template>` 静态标记 + 导出 `init(root, { params, data, duration, gsap })`），首批聚焦 4 个零外部依赖的高频 SVG / 原生 Canvas 模块并内置确定性文本测量与框宽自适应；
   - 现有 `modules/patterns/` 对应文档的 `## 已有实现` 直接指向 `motions/<name>/`，并将 `modules/motions/motions.md` 纳入 Phase 8 handoff `Required References` 发现入口（保留“特别匹配或确能提升表达时采用”原则）。
2. **`designs` 调整细线层级并增加纸纹质感（经 H.264 实片验证）**：
   - 保持现有 `:root` 主题变量与字体配置契约；面向新写场景与 `motions` 模块开放半透明底色透出 `#ground` 纸纹肌理、轻量纸感微阴影与细点阵/微网格衬底，保留主面板外框 `1.5–2px` 防压缩断线、内部辅助网格/引导虚线用 `1–1.25px`（配合 1:1 像素 `viewBox` 或 `vector-effect: non-scaling-stroke`），并通过真实 `ffmpeg` H.264 MP4 渲染确认不断线、纹理清晰。
3. **`landscape-presenter` 默认只排 `header + main`，按需启用 `side`**：
   - 在布局与 composition 规则中明确：`landscape-presenter` 一般不放 `side` 副展示区，仅当存在独立的大块文本/榜单元素，或只放 `header` 和 `main` 导致画面明显太空旷时，才在 `side` 放置与 `main` 不重复的内容。
4. **渲染前 `check-composition.py` 保持确定性 `findings` 稳定，将新增排版/素材检查统一归入非阻塞 `warnings`**：
   - 保持现有 7 项 100% 确定性契约在硬阻塞 `findings`；快照 JS 仅采集元素与媒体几何，由 Python 分析阶段利用 `RegionIndex` 计算元素所属内容区域，保证 `--dump-snapshots` 与 `--snapshots-from` 完全一致；
   - 按快照 `ancestors` 中的模板 `data-composition-id` 精确豁免模板自有子树，以明确数值公式将 SVG 文本出框（`svg_text_overflow`）、缩略媒体（`media_too_small`）、双向缩放失真（`media_blurry_scale`）、同层重叠（`element_overlap`）/ 媒体遮挡（`material_occlusion`）、跨区文本重复（`region_text_duplication`）与跨场复用（`media_reuse`）统一输出到 `warnings`，提示修复并供 Phase 9 重点复核。
5. **闭环 `.venv` 的 `yt-dlp` 调用与临时目录隔离校验，并将长片防超限收进阶段“护栏”**：
   - 将 `yt-dlp` 与 PO Token 插件纳入 `.venv` 依赖并同步阶段激活命令，支持 `YTDLP_BIN` 覆盖且默认优先调用 `Path(sys.executable).with_name('yt-dlp')`；在独立临时子目录中完成有效视频探测后再移入目标目录，统一输出结构化 `failure_kind`；
   - 在 `08-composition.md` `## 护栏` 与基础指令中指导单个 composition agent 逐场景拆分 `compositions/<scene>.{html,mjs}` 落盘，默认优先读取 `material-catalog.json` 元数据并在元数据不足时按需单张核查原图。

---

## 3. 具体实施步骤（Work Items）

拆分为 4 个内聚步骤：`WI-01`、`WI-02`、`WI-03` 相互独立可并行推进，随后由 `WI-04` 串联上下游文档、护栏与 handoff 引用。

---

### WI-01：YouTube 下载 `.venv` 闭环绑定、临时目录隔离与结构化错误归类

**解决**：P1（`.venv` 未闭环导致插件失效、旧文件混淆与 storyboard 假成功、缺少结构化 `failure_kind`）。

**改动文件**：
- `requirements.txt`
- `SKILL.md`、`README.md`
- `scripts/video-download.py`
- `references/phases/04-material-harvest.md`
- `tests/test_video_download.py`

**实施步骤**：
1. **闭环 `.venv` 内的 `yt-dlp` 安装、解析与阶段命令**：
   - 在 `requirements.txt` 增加 `yt-dlp` 与 `bgutil-ytdlp-pot-provider`，同步更新 `requirements.txt` 头部注释、`SKILL.md` 环境预检与 `README.md` 依赖说明，将 `yt-dlp` 归入 `.venv` Python 依赖（宿主所需的 PO Token 服务、cookies 或代理通过外部服务与 `yt-dlp` 原生配置提供；文档如实说明插件绑定解决的是加载隔离，外部解锁仍取决于宿主配置）；
   - 将 `references/phases/04-material-harvest.md` 中的脚本调用示例统一补齐 `source .venv/bin/activate &&` 前缀，与 `SKILL.md` 核心护栏一致；
   - `scripts/video-download.py` 按 `os.environ.get('YTDLP_BIN')` → `Path(sys.executable).with_name('yt-dlp')`（存在时）→ `shutil.which('yt-dlp')` 的顺序解析可执行文件，跨 Linux / macOS（含 `/opt/homebrew/bin`、`/usr/local/bin`）稳定命中当前 `.venv` 二进制。
2. **独立临时子目录下载与有效视频流校验**：
   - 每次下载在 `output_dir` 下创建唯一临时子目录作为 `yt-dlp --output` 目标，非 `--subtitles-only` 模式下加入 `--format "bv*+ba/b"` 排除纯 storyboard 伪格式；
   - 下载结束后仅在本次临时子目录内验证产出了有效视频文件（`ffprobe` 可用时确认正时长与有效宽高）：校验通过后将新文件移入 `output_dir` 并更新 manifest；若仅产出 `.mhtml`/storyboard 或无有效视频流，直接清理该临时子目录并返回失败 JSON（`failure_kind: "storyboard_only"`），避免误删历史合法素材或将旧文件当作本次下载成功。
3. **统一输出结构化 `failure_kind`**：
   - 升级 `detect_common_issue()` 返回 `(failure_kind, error_message)`，失败 JSON 统一包含 `failure_kind`（如 `bot_check`、`storyboard_only`、`login_required`、`rate_limited`、`unavailable`），兼容弯引号 `Sign in to confirm you’re not a bot` / `LOGIN_REQUIRED`；在 `04-material-harvest.md` 明确 `bot_check` / `storyboard_only` 单次尝试即早停、记入 `search-notes.md` 并继续后续流程。
4. **文档与单测更新**：
   - 在 `README.md` 补充 `.venv` 下 PO Token 服务与 `yt-dlp` 原生配置说明及外部依赖边界；
   - 在 `tests/test_video_download.py` 通过 `YTDLP_BIN` 注入测试桩，补充 `Path(sys.executable).with_name('yt-dlp')` 优先解析、临时目录隔离（已有旧视频保留原样且不冒充本次成功）、`failure_kind` 输出与 storyboard 假成功拦截测试。

---

### WI-02：`designs` 细边框与质感升级 + 重构一等模块目录 `modules/motions/`

**解决**：P2（新场景与 SVG 粗黑框及纯色单调、`motion.md` 孤立无实现、`patterns` 缺少对应动态模块）。

**改动文件**：
- `modules/designs/designs.md` 及 `modules/designs/{default/default,github/github,producthunt/producthunt}.md`
- 删除孤立的 `modules/motion.md`，新建一等模块目录 `modules/motions/`：
  - `modules/motions/motions.md`（总索引、采用条件、接口与扩展规范）
  - `modules/motions/<name>/<name>.{md,html,mjs}`（首批精炼为 4 个高频核心模块：`flow-path`、`topology-graph`、`chart-build`、`focus-callout`）
- `modules/modules.md`
- `modules/patterns/patterns.md` 及对应 `modules/patterns/<media|info>/*.md`（更新 `## 已有实现` 与链接）
- `scripts/prepare-handoff.py`、`references/delegation/composition/{handoff-template,base-instructions}.md`、`references/phases/08-composition.md`（同步 `modules/motion.md` → `modules/motions/motions.md` 路径与 `Required References` 入口）
- `tests/test_design_contract.py`、`tests/test_scene_components_browser.py`、`tests/test_prepare_handoff.py`、`tests/test_doc_references.py`、`tests/test_phase_docs.py`

**实施步骤**：
1. **`designs` 调整细线层级、增加纹理质感并做 H.264 实片验证**：
   - 保持现有 `:root` 主题变量与字体配置契约，修改 `modules/designs/designs.md`「纸面、形状、图标与通用元素」及三套主题对应段落（明确新质感与线宽层级面向新写场景与 `motions` 模块，现有模板样式保持稳定）：
     - **纹理与层次质感**：允许卡片、面板和 SVG 节点采用半透明底色（如 `color-mix(in srgb, var(--c-card) 82%, transparent)`）透出底层 `#ground` 纸纹肌理，允许克制的纸张层次微投影与细点阵/微网格辅助底衬；
     - **兼顾防断线的精细线宽阶梯**：主面板外框与主干焦点路径保留 `1.5–2px`，小节点外框用 `1.25–1.5px` `--c-border`，内部刻度/网格/引导虚线用 `1–1.25px`；规定 SVG 画布采用与宿主容器像素 **1:1 对应的 `viewBox`**（或 `vector-effect: non-scaling-stroke`）；
     - **MP4 编码实测**：用真实 `ffmpeg` H.264 渲染测试片段并抽帧检查，确认 `1–1.25px` 辅助线不断裂、半透明纸纹清晰可见。
2. **将 `motions` 建设为标准一等模块目录 `modules/motions/`（首批 4 个核心模块）**：
   - 组织结构、文档体例与接入方式严格对齐 `components/` 与 `transitions/`，仅依赖宿主注入的 `gsap` 与原生 SVG / Canvas 2D：
     - `modules/motions/motions.md`：包含模块定位与统一采用规则（链接 `composition/base-instructions.md` 第四部分）、模块目录表、接入步骤（拷贝 `<name>.html` + `<name>.mjs` 到 `composition/compositions/` 并通过 `init` 接线，或拷入工程后按场景改写）、时间约定与「新 motion 模块扩展约定」；
     - 首批交付 `flow-path`（流程与状态流转描边）、`topology-graph`（架构与模块拓扑激活）、`chart-build`（曲线/柱状/指标动态构建与等宽读数）、`focus-callout`（重点区域视口推拉与外沿引线标注）；
     - **内置确定性文本测量与排版适配**：每个模块均沿用仓库确定性字宽估算（CJK/ASCII 字符宽度模型及 `document.fonts.ready` 校核）自动计算多行折行、字号步进或承载 `<rect>` 宽高，确保横竖屏下长短文案均与承载框匹配。
3. **注册进 `modules.md`、关联现有 `patterns/` 并同步 Handoff 入口**：
   - 在 `modules/modules.md` 的模块分类、目录树、「读哪份文档」、「分层」与「扩展约定」中将 `motions/` 列为标准模块类别；
   - 更新 `modules/patterns/patterns.md` 中对 `motions/motions.md` 的引用，并在 `process-flow`、`architecture`、`chart`、`big-number`、`detail-callout`、`viewport-reveal` 等对应 pattern 文档的 `## 已有实现` 小节直接指向对应的 `motions/<name>/` 模块；
   - 在 `scripts/prepare-handoff.py` 与 `references/delegation/composition/handoff-template.md` 中将 `modules/motions/motions.md` 纳入 `Required References` 作为动态模块发现入口（`可选参考` 保留 `modules/patterns/` 与 `modules/transitions/`），同时将 `references/delegation/composition/base-instructions.md` 与 `references/phases/08-composition.md` 中的旧路径 `modules/motion.md` 同步更新为 `modules/motions/motions.md`（保留“特别匹配或确能提升表达时采用，不为使用模块而硬套”原则）。
4. **契约、文档引用与浏览器多状态验证**：
   - 更新 `tests/test_prepare_handoff.py`、`tests/test_doc_references.py`（加入 `motions/` 相对路径校验）与 `tests/test_phase_docs.py`（将 `modules/motion.md` 更新为 `modules/motions/motions.md`），保证删除旧 `modules/motion.md` 后全仓路径校验一次通过；
   - 运行 `tests/test_design_contract.py` 确认三套主题单文件契约完好；在 `tests/test_scene_components_browser.py` 对 4 个 `motions` 模块验证横竖屏挂载、长短文本自适应、正反向 `seek(t)`、多实例隔离与 `destroy()` 无残留，并通过 `check-composition.py` 检查。

---

### WI-03：Phase 8 `check-composition.py` 几何遥测与非阻塞质量 `warnings` 补齐

**解决**：P3、P4（保持现有确定性 `findings` 契约稳定，由 Python 侧统一计算区域归属、精确豁免模板自有子树，并以明确公式输出排版/素材清晰度 `warnings`）。

**改动文件**：
- `modules/templates/github-trending/project-cover.mjs`
- `scripts/check-composition-snapshot.js`
- `scripts/check-composition.py`
- `tests/test_visual_composition_qa.py`、`tests/test_check_composition.py`、`tests/test_scene_components_browser.py`

**实施步骤**：
1. **快照仅采几何与层级，Python 侧统一计算 Region 归属**：
   - 在 `modules/templates/github-trending/project-cover.mjs` 为 `#pc-side img` 补上 `data-media-role="logo"`；
   - `scripts/check-composition-snapshot.js` 保持现有 `{checks}` 入参不变，只采集客观 DOM 几何与层级数据（确保实时 Chrome、`--dump-snapshots` 与 `--snapshots-from` 行为完全一致）：
     - 对 `<img>` / `<video>` 读取固有尺寸、`objectFit` / `objectPosition`、`data-media-role`、`data-material-ref` 与解析后的文档 URL，计算扣除 `contain` / `scale-down` 留白后的 `paintedRect`、真实缩放比 `scale`、与祖先 `overflow: hidden|clip|scroll|auto` 求交后的 `visibleRect` 及归一化 `cropBox`；
     - 记录 SVG `<text>` 的实测框及同组（`<g>`）内单个候选承载 `<rect>` 的几何框；
     - 为元素分配快照内序号与父节点序号以精确排除父子包含关系，并保留现有 `ancestors`（含 `id` 与 `data-composition-id`）；
   - **Python 分析阶段计算 Region 归属与模板子树豁免**：利用 `RegionIndex.content` 按最大重叠面积为每个可见内容元素确定所属 content region `id`（如 `header`、`main`、`side`）；当视觉 scene 声明了 `template` 时，仅豁免 `ancestors` 命中该 `template["scene"]` `data-composition-id` 的模板自有子树，场景内额外挂载的自由元素照常受检。
2. **优化现有 `findings` 去重粒度**：
   - 保持现有 7 项确定性检查决定 `verdict`；将采样时刻保留在 `time_s` 字段，使 `dedup_findings` 按 `(scene_id, check, issue)` 干净合并同一场景跨采样点的重复项。
3. **以明确数值公式新增非阻塞质量 `warnings`（随 `check-composition.json` 输出提示，保持 `verdict` 由 `findings` 决定）**：
   - `svg_text_overflow`：当同组 `<g>` 内存在唯一面积大于该 `<text>` 的 `<rect>` 且二者相交，而 `<text>` 任一方向超出 `<rect>` 边界 `> 4px` 时提示；
   - `media_too_small`：对非 `logo`/`icon`（`data-media-role` 不在 `{"logo", "icon"}` 且固有宽 `>= 400px`）的内容媒体，设同一 content region 内同屏可见内容媒体数为 `N`，当 `visibleRect.width < (region.width / N) * 0.35` 且 `visibleRect.height < region.height * 0.35`（或面积 `< (region.area / N) * 0.15`）时提示；
   - `media_blurry_scale`：有效渲染缩放比 `scale < 0.45`（固有宽 `> 1920px` 时 `< 0.35`）或低清放大 `scale > 1.25` 时提示；
   - `element_overlap` / `material_occlusion`：排除父子包含关系、常驻组件、转场覆盖层与 `[data-layout-ignore]` 后，同层可见文本/卡片重叠面积 `>= min(areaA, areaB) * 0.20`（且 `>= 64px²`），或压入主媒体向内收缩 `6px` 的 `visibleRect` 达 `>= 64px²` 时提示；
   - `region_text_duplication`：排除父子重复文本与长度 `< 8` 字符的短标签后，`side` 归一化词句在 `main` 或 `header` 中的重合比例 `>= 50%` 时提示；
   - `media_reuse`：优先取 `data-material-ref`，否则将媒体 URL 去除 query/fragment 并解析为相对工作区的规范化路径；跨非相邻视觉场景重复出现，或在相邻场景重复使用 `<video>`、重复使用 `<img>` 且 `cropBox` 中心偏移与尺寸变化均 `< 0.08` 时提示。
4. **单测与模板回归验证**：在 `tests/test_visual_composition_qa.py`、`tests/test_check_composition.py` 与 `tests/test_scene_components_browser.py` 验证 `--dump-snapshots` / `--snapshots-from` 一致性、模板自有子树精确豁免（同时检测同场自由违规元素），以及上述 6 类 `warnings` 公式的准确触发且保持合法场景 `verdict == "pass"`。

---

### WI-04：`landscape-presenter` 区域互补策略、上下游阶段协同与容量护栏同步

**解决**：P3、P4 在布局分工、各阶段制作/复核准则与单 Agent 容量护栏中的端到端闭环（依赖 `WI-02` 的 `motions`/质感规范与 `WI-03` 的角色属性及 `warnings` 信号）。

**改动文件**：
- `modules/layouts/landscape-presenter.md`
- `references/delegation/composition/base-instructions.md`
- `references/delegation/composition/handoff-template.md`
- `references/delegation/catalog/base-instructions.md`、`references/delegation/script/base-instructions.md`
- `references/phases/05-material-catalog.md`、`06-script-scene-plan.md`、`08-composition.md`、`09-check.md`
- `tests/test_doc_references.py`、`tests/test_phase_docs.py`

**实施步骤**：
1. **`landscape-presenter` 区域策略与 Composition 前置制作准则（`landscape-presenter.md` + `composition/base-instructions.md` + `handoff-template.md`）**：
   - **`side` 按需启用且跨区互补**：明确 `landscape-presenter` 默认只排 `header` + `main`，**一般不放 `side` 副展示区**；仅在存在独立大块文本/榜单元素，或只放 `header` 和 `main` 画面明显太空旷时才启用 `side`，且 `side` 内容不得与 `main` 文字重复；SVG 节点框宽高须完整包住文字，同层元素留足间距避免重叠；
   - **素材清晰度、角色标注与检查 `warnings` 复核**：高信息密度长图与竖屏录屏结合 `focal_region` 做局部裁剪视口放大或沿长轴移动视口，小图标显式标 `data-media-role="logo"`，引用 catalog 素材的元素建议标 `data-material-ref`；运行 `check-composition.py` 后除修清 `findings` 外，逐条核对 `warnings`（确属设计意图的保留并在 storyboard 说明，属意外缩略/重叠/复读/复用的当场修掉）。
2. **上游供给、单 Agent 分文件落盘护栏与 Phase 9 视觉复核同步**：
   - Phase 5（`catalog`）：对长图、图表与滚动录屏在有明确视觉依据时标出 `focal_region`，无依据时保持 `null`；
   - Phase 6（`script`）：`content_plan` 写清登场对象、因果/对比关系与分步状态变化，支撑下游动态演绎；
   - Phase 8（`08-composition.md` 的 `## 护栏` 与 `composition/base-instructions.md`）：保持单次委派单个 composition agent 负责全片一致性，指导子 agent **将各视觉场景拆分为独立的 `compositions/<scene>.{html,mjs}` 逐个写盘**（避免单次输出巨型 `index.html` 触发 `413`），且**默认优先读取 `material-catalog.json` 的尺寸、语义与 `focal_region`，仅在元数据不足以确定裁剪边界时按需单张查看原图**（避免批量开图触发 `400`）；
   - Phase 9（`09-check.md`）：vision 检查结合 `check-composition.json` 的 `warnings` 重点复核原片级失焦/缩放模糊、跨区文案冗余、素材跨场复用合理性以及 `designs` 细边框与纸纹质感。
3. **文档结构与路径校验**：运行 `pytest tests/test_doc_references.py tests/test_phase_docs.py tests/test_prepare_handoff.py` 确认全部阶段护栏、章节顺序与本地引用通过。
