# PR review 修复与旧项目兼容删除：执行计划

## 状态、基线与优先级

- 状态：已按本文实施（工作区改动，未提交、未推送）。验收证据与实际偏差见文末「实施记录」。
- 基线：实施时已从 `237aca2a43d3282f6a33bef04d389b934c74019a` 快进到 `main` / `origin/main` 的 `c40e28a`（含 Phase 7 执行 / 恢复说明、论文说明与对应测试），本线程未提交的 PR 改动全部保留（未用 reset / checkout 覆盖）。
- 本计划是后续执行入口，替代 `phase-inputs-and-pi-delegation.md` 中“layout 留在 Phase 1”、旧项目兼容及相关验收安排；原计划只作为历史记录。
- 明确要求：Phase 1 不决定、不指引 layout，也不添加解释布局归属的段落；layout 与 template 由 Phase 8 决定。
- 明确要求：删除以旧视频项目、旧产物格式或旧状态续跑兼容为目的的实现、降级分支、文档及正向兼容测试，不新增自动迁移方案。
- 保持：默认 3 分钟；普通竖屏 1080×1440、显式 9:16 才用 1080×1920；默认 Pi；QA 保留简短说明、默认 standard、不主动问；论文关键图必须全部纳入视频。
- 本轮只写本文，不修改实现、安装依赖、调用 coding agent、提交、推送或合并。未来实施完成也不自动获得 landing 授权。

## 1. 范围与统一规则

### 1.1 删除的兼容

1. v1 / 无版本 manifest 的读取、`manifest_papers.json` 合并与自动升级。
2. 已持久化的 manifest、catalog、论文 metadata 里绝对素材路径的兼容读取。
3. design / layout 已不在当前库中时，退回工作区历史副本的资源兜底。
4. 偏移表缺内容哈希时只比字数、composition 报告缺指纹时退回 mtime 的降级验收。
5. 旧 stamps 缺少当前上游键时忽略变化、继续信任旧构建的特殊待遇。
6. 字体脚本旧 positional style 调用及配套的旧项目示例。
7. 指导继续使用旧项目格式的文档与“旧格式仍通过”的测试。

不满足当前契约的数据应明确报缺失、损坏或不支持，并指出应重新生成的阶段；不读取备用旧文件、不猜字段、不降低完成判据，也不删除用户现有产物。

### 1.2 保留的正常行为

- 当前契约下的中断续跑、stale、redo、审稿与损坏隔离恢复。
- 当前项目显式保留工作区副本及 `--refresh` 更新副本的物化策略；它不用于找回当前库已经删除的资源。
- 当前契约规定的可选字段与默认值，例如要求列表、QA、审稿策略。
- 渲染新鲜度的 mtime 检查、哈希缓存、源内容指纹；删除的是旧报告降级分支，不是全部时间检查。
- 用户提供的绝对 PDF 输入路径、handoff 里的绝对路径，以及生产者把内部生成路径规范化成持久化相对路径的行为。
- Python 3.9 支持、第三方库接口支持、OpenAI 兼容 API、TTS / ASR 后端 fallback。环境变量旧别名属于工具配置兼容，不在“旧视频项目数据兼容”的本次删除范围。
- ASR 文本差异的 `fallback` 标记、无可用 VLM 时 agent 看图、解析失败重试等当前失败处理。

不得仅按“旧”“兼容”“fallback”字符串机械删除代码。

## 2. 目标阶段与产物契约

### 2.1 阶段责任

| 阶段 | 责任 | 不做的事 |
| --- | --- | --- |
| Phase 1 | 保存来源、模式、时长、语言、orientation、design、coding agent、素材策略、QA / 审稿策略和用户要求 | 不生成 layout；不选模板；不指引字幕容量；正文不出现布局说明 |
| Phase 6 | 根据简报、catalog 和 narration_requests 写显示稿与叙事规划 | 不读取模板旁白要求，不预先选择视觉模板或布局 |
| Phase 7 | 配音、fresh transcript、显示稿与音频时间对齐 | 不读取最终 layout，不确定字幕宽度、字号、行数或容量 |
| Phase 8 | 规划画面，选择 layout / template，按最终排版生成字幕和模板时间锚点，再渲染 | 不重配音，不改写旁白，不覆盖 Phase 7 的时间轴 |
| Phase 9 | 确定性检查、按 QA 档位做视觉检查，核对关键图，混音 | 不用候选引用冒充实际展示 |

上表是实施计划，不抄进 Phase 1 解释后续字幕流程。

### 2.2 当前格式与路径

| 数据 | 当前契约 |
| --- | --- |
| `inputs.json` 基础字段 | source、input_mode、duration、language、orientation、design、coding_agent、fetch_materials；要求列表与 QA / 审稿策略按现有可选规则 |
| `inputs.json` 视觉字段 | Phase 8 明确写入 layout 和 template；template 为 null 表示已决定不使用模板，缺省表示尚未决定 |
| `harvest_page/manifest.json` | version 2；不存在时创建新的 v2 manifest，存在但版本缺失或非 v2 时拒绝，不合并旧文件 |
| 素材持久化路径 | POSIX 相对路径；素材 / PDF markdown 以 harvest_page 为基准，clip_path 以视频工作目录为基准；不接受绝对路径或越出基准目录的路径 |
| `narration-offsets.json` | 当前 version、长度、segments、script_sha256 和 narration_sha256 均须满足 make-narration 当前输出契约 |
| Phase 7 产物 | voice_clone/narration.mp3、transcribe/transcript.json、transcribe/timeline.json |
| Phase 8 字幕产物 | composition/assets/subtitle-units.json，由确定性脚本生成；放在 assets 下以纳入现有 composition 源指纹和渲染新鲜度检查 |
| 模板声明 | 计划新增 modules/templates/github/github.json，声明当前支持的 layout；不从旧模板文档猜测机器契约 |
| 模板专用锚点 | 如需要，使用 composition/assets/template-cues.json 和 composition/assets/template-timeline.json，前者复用 scene-plan 的 scene_id / paragraphs / cues 结构，后者由现有时间定位逻辑生成；不修改上游 scene-plan / timeline |
| composition 检查报告 | 必须有 sources_sha256，且匹配当前 index / compositions / assets 内容；无指纹报告拒绝 |
| stamps | 只接受当前状态版本和结构；依赖键集合的新增、移除也按契约变化处理，不保留旧戳免失效分支 |

模板专用锚点是当前 composition 的生成数据，不是旧项目迁移产物，也不引入一套新的文本对齐算法。

### 2.3 对齐脚本的两个明确输出模式

复用 `align-narration.py` 的字符映射、ASR 归一化、段落 / cue / beat 定位和字幕分段算法，新增明确的 `--mode timing|subtitles`：

- timing：只生成时间轴，不要求 caption 参数、不调用按容量分段、不生成 subtitle-units。
- subtitles：根据最终 layout 生成字幕单元，只写指定字幕产物，不覆盖 Phase 7 时间轴。
- 生产调用明确指定 mode；无 mode 或模式与参数组合不合法时返回参数错误，不保留旧项目调用的隐式推断路径。
- 两种模式读取同一份显示稿、朗读稿、偏移表和 fresh transcript。允许复用确定性对齐计算，不重做 TTS / ASR。
- 模板额外 cues 需要时间时，在 Phase 8 用 timing 模式处理 composition 自己的 cue 声明，输出到 composition 自己的时间文件。

现状依据：[对齐与字幕分段目前耦合在 align 中](worktree://5a5c3e0d-8bdb-4b1c-b719-0062e34170b1/scripts/align-narration.py#L891-L979)，[Phase 7 目前依赖 layout 且拥有字幕产物](worktree://5a5c3e0d-8bdb-4b1c-b719-0062e34170b1/scripts/pipeline-status.py#L1274-L1317)。本次需一起调整调用、产物归属和状态检查，不能只删文档。

## 3. Work items 与执行依赖

| ID | 工作项 | 前置 |
| --- | --- | --- |
| WI-01 | 定义当前公共契约与失败用例 | 无 |
| WI-02 | 删除旧 manifest、素材路径兼容 | WI-01 |
| WI-03 | 删除旧哈希报告、旧 stamps 验收兼容 | WI-01 |
| WI-04 | 从 Phase 1 完全移除 layout | WI-01 |
| WI-05 | 改为布局无关的配音与时间对齐 | WI-03、WI-04 |
| WI-06 | 修正有效布局校验、当前资源解析和字体调用 | WI-01 |
| WI-07 | 将最终字幕生成与验收归到 composition | WI-05、WI-06 |
| WI-08 | 补齐模板匹配与模板时间锚点 | WI-06、WI-07 |
| WI-09 | 修正必用素材的适用范围与引用身份 | WI-02 |
| WI-10 | 修正要求列表、handoff 和步骤字段校验 | WI-01、WI-07 |
| WI-11 | 按选定 coding agent 派发 | WI-10 |
| WI-12 | 清理执行文档、替换旧兼容测试 | 各对应实现项 |
| WI-13 | 集成、完整回归与范围审查 | WI-02 至 WI-12 |

每项先加入失败用例，再做最小实现并跑聚焦测试。WI-04、WI-05、WI-07 的阶段契约必须作为同一个完整变更验收，不能交付“Phase 1 删了 layout，但后续命令仍必需它”的半成品。

### Review 问题覆盖索引

| Review 问题 | Work items |
| --- | --- |
| Phase 1 布局指引与错误的 3:4 layout 名称 | WI-04、WI-05、WI-07 |
| 换布局后对齐成功但仍卡在 Phase 7 | WI-05、WI-07 |
| 旧戳忽略新增要求 | WI-03、WI-10 |
| 校验的不是实际使用的布局副本 | WI-06 |
| 3:4 与 9:16 混用 | WI-01、WI-06、WI-07 |
| 模板 / 布局冲突、缺模板时间锚点 | WI-08 |
| 无素材模式被残留 catalog 阻塞、等价 clip 引用误报 | WI-09 |
| 缺省要求与 [] 不等价、literal braces 误报 | WI-10 |
| 步骤字段隐藏必填 | WI-01、WI-10 |
| 实际派发与 coding_agent 不一致 | WI-11 |
| 删除旧项目兼容及配套指引 | WI-02、WI-03、WI-06、WI-12 |

## 4. 具体执行项

### WI-01 — 公共契约与回归骨架

新增：`scripts/video_contract.py`、`tests/test_video_contract.py`。

修改：`scripts/pipeline-status.py`、`scripts/prepare-handoff.py`、`scripts/check-render.py` 及对应测试。

- [ ] 实施前核对 HEAD、远端与未提交改动；安全同步时保留本地代码和计划，核对新增 Phase 7 恢复说明、论文规则与测试，刷新受影响的 work items 后再实现。
- [ ] 集中定义 Phase 1 基础字段、catalog / script / composition 实际需要的字段、两个要求列表、合法名称和 orientation → 尺寸映射。
- [ ] Phase 1 的基础必填集合与 handoff 的逐步骤必填集合分开定义；不把整个项目输入表强加给 catalog / script，后者只校验和读取该步骤实际使用的字段。
- [ ] 三种规范 orientation 对应 1920×1080、1080×1920、1080×1440；不在多处复制映射。
- [ ] 要求列表缺省有效值为 []；非空元素必须是非空白字符串。
- [ ] 仅统一契约，不创建自动迁移器、通用插件框架或 agent 启动器。
- [ ] 新增规范画布接受、两种竖屏互配拒绝、列表类型与缺省值测试，保持 Python 3.9 可运行。

验收：后续读取与检查从同一份当前契约取值，字段声明和实际读取不再各自维护。

### WI-02 — 删除旧 manifest 与持久化路径兼容

修改：`scripts/harvest_manifest.py`、`scripts/cut-clips.py`、`scripts/pipeline-status.py`，按调用影响核对 `scripts/parse-pdf.py`、`scripts/harvest-pages.py`、`scripts/video-download.py`。

测试：`tests/test_harvest_manifest.py`、`tests/test_cut_clips.py`、`tests/test_parse_pdf.py`、`tests/test_harvest_pages.py`、`tests/test_video_download.py`、`tests/test_pipeline_status.py`。

- [ ] manifest 不存在时仍允许正常建立 v2；已经存在时必须声明当前版本，删除 manifest_papers 合并、无版本接收与旧版本自动升级。
- [ ] 读取持久化素材路径时拒绝绝对路径、~ 展开和越出基准目录的 .. 路径；按当前格式解析，不猜 base。
- [ ] 生产者内部产生绝对路径时，写入前仍规范化为合法相对路径；与“接受旧持久化绝对路径”区别处理。
- [ ] 同步限制论文 metadata 的 full_markdown_path；当前确实无 markdown 的 null 仍按现有合法输出处理，不把 null 当旧格式。
- [ ] 字幕、视频下载 suggested_output_dir、论文图片与 clip 消费者共用相同路径规则。
- [ ] 把旧格式正向测试改成明确拒绝；补当前 v2 写入 / 读取 / upsert / 原子保存与幂等测试。

验收：没有合并旧文件、读取绝对素材路径或根据旧数据猜测目录的分支；当前下载与 PDF 解析仍输出正确路径。

### WI-03 — 删除哈希降级与旧 stamps 特殊待遇

修改：`scripts/pipeline-status.py`、`scripts/align-narration.py`，按需核对 `scripts/make-narration.py` 和 `scripts/check-composition.py` 的生产契约。

测试：`tests/test_pipeline_status.py`、`tests/test_align_narration.py`、`tests/test_make_narration.py`、`tests/test_check_composition.py`。

- [ ] narration offsets 的当前版本、两个长度与两个哈希必填，删除缺哈希只比长度和缺长度默认接受的分支；直接调用对齐脚本也必须校验，不能只依赖 pipeline-status。
- [ ] composition 报告无 sources_sha256 直接判不合格；删除旧报告 mtime 降级，但保留 final.mp4 与源文件的新鲜度检查。
- [ ] 删除 changed_upstream_keys 的共有键过滤，键集合新增、移除和已有值变化均可见；不新增 backfill 或自动迁移路径。
- [ ] 状态结构 / 阶段契约改变时更新当前状态版本和测试夹具；旧状态不得自动转成当前状态或继续报告可信完成。
- [ ] 保留当前损坏隔离与单阶段显式重建机制。--restamp 仍需当前产物全部合格，不接受缺哈希旧产物。
- [ ] 为不可读指纹文件补直接异常注入测试，替代之前删除的覆盖；不能用“旧夹具不再适用”放弃底层错误处理验证。

验收：缺证据的旧格式被明确拒绝；新要求不因旧戳缺键而永久忽略；当前 redo、审稿、隔离恢复不被放宽。

### WI-04 — Phase 1 完全不涉及布局

修改：`references/phases/01-gather-inputs.md`、`SKILL.md`、`references/pipeline-control.md`、`scripts/pipeline-status.py`、公共契约。

测试：`tests/test_phase_docs.py`、`tests/test_guardrail_docs.py`、`tests/test_pipeline_status.py`。

- [ ] 删除 Phase 1 的 layout 字段行、整项选择步骤、区域文档路径、相关护栏文字和姊妹项目 layout 复用指引，重排编号。
- [ ] 不补“layout 在其他阶段决定”、Phase 7 或字幕容量解释；Phase 1 不包含 layout 指引。
- [ ] Phase 1 完成判据只校验基础输入和当前可选配置，不要求 layout / template，也不因为尚未选择视觉配置而回退。
- [ ] 用户说过的画面要求仍原样保存到 composition_requests，不因此丢掉“要主持人”等原话，但不把它转换成布局决策。
- [ ] SKILL 入口和调度表把布局决策 / 反馈归到 Phase 8；保持原有默认值、QA 与不强制提问规则。
- [ ] 旧正向的“Phase 1 选择 presenter”测试替换为“Phase 1 没有布局指引、无 layout 也能完成”的测试。

验收：新输入无 layout / template，Phase 1 可以完成；阶段文档不出现 layout 或后续字幕流程说明。

### WI-05 — 配音与时间对齐不依赖最终布局

修改：`scripts/align-narration.py`、`scripts/voice-subtitles.py`、`scripts/pipeline-status.py`、`references/phases/07-voice-subtitles.md`。

测试：`tests/test_align_narration.py`、`tests/test_voice_subtitles.py`、`tests/test_pipeline_status.py`、`tests/test_cli_contract.py`、`tests/test_phase_docs.py`。

- [ ] 实现第 2.3 节的两个显式模式，复用 build_atoms、build_timeline、locate_scenes / cues / beats 等已有核心，不复制对齐算法。
- [ ] timing 模式不读取 layout、不要求 width / font-size / max-lines、不执行 build_units，不产生最终字幕文件。
- [ ] voice-subtitles 改为基本输入检查、TTS / fresh transcript、timing 模式；不从 orientation 推导字幕预算，也不选择临时 layout。
- [ ] Phase 7 的 products 只保留音频、transcript、timeline，移除 layout 上游和 subtitle-units 产物。
- [ ] --align-only 保留为“复用音频 / transcript，重建时间轴”，仅用于真正的时间对齐输入变化，不用于布局变化。
- [ ] 各模式只写属于自己的输出；输入缺失、错误 mode 或参数组合在写输出前失败。
- [ ] 用 fake 后端跑无 layout 输入，验证 Phase 7 完成；paragraph / cue / beat 时间与已有规则相符。

验收：没有 layout 的项目能完成音频与时间轴准备；不存在提前字幕容量、重配音或改写显示稿的隐式行为。

### WI-06 — 有效布局、当前资源与字体调用

修改：`scripts/prepare-handoff.py`、`scripts/pipeline-status.py`、`scripts/fonts-download.sh`、公共契约。

测试：`tests/test_prepare_handoff.py`、`tests/test_pipeline_status.py`、`tests/test_fonts_download.py`、`tests/test_video_contract.py`。

- [ ] 只接受当前库注册的 design / layout / template；删除库中不存在时找工作区历史资源的兜底，以及字体准备中的已移除 design fallback。
- [ ] 对当前注册资源按明确物化策略选择有效文件：不 refresh 且副本存在用副本，否则用库文件。校验的文件必须是最终 handoff 会引用的文件。
- [ ] 先检查有效 layout 的当前结构、canvas 与完整 orientation 尺寸，再写副本或装字体；保留当前 portrait-3x4 共用 portrait.md 的文档关系，它不是旧格式兼容。
- [ ] 为 Phase 8 增加输入前置校验，与输出产物检查分开：视觉配置缺失或非法留在 Phase 8，不能回退 Phase 1，也不能把整份 inputs.json 当 Phase 8 生成产物。
- [ ] 字体安装使用明确 --theme 参数，删除 legacy positional style（包括旧 positional all 调用）和相关示例；保留显式 --theme all 的维护操作、正常本地字体安装、dry-run 与维护 refresh，不让普通生成联网下载字体。
- [ ] 覆盖有效副本方向错误、refresh 修正副本、当前库不存在的名称、两种竖屏互配、校验失败无写入等用例。

验收：检查对象与使用对象一致；不存在历史资源回退；3:4 与 9:16 的尺寸契约实际生效。

### WI-07 — 最终字幕在 composition 中生成

修改：`scripts/prepare-handoff.py`、`scripts/pipeline-status.py`、`scripts/check-composition.py`、`scripts/check-render.py`、composition 委派包、Phase 8 / 9 文档。核对 `scripts/composition_hash.py` 现有 assets 收集规则，优先通过放置新产物复用它，不扩展一套单独的指纹机制。

测试：`tests/test_prepare_handoff.py`、`tests/test_pipeline_status.py`、`tests/test_check_composition.py`、`tests/test_check_composition_snapshots.py`、`tests/test_check_render.py`、`tests/test_voice_subtitles.py`。

- [ ] Phase 8 输入加入 fresh transcript、narration.txt 与 offsets 的路径，以支持确定性字幕生成；不要求已存在最终字幕。
- [ ] 确定 layout 后调用 subtitles 模式，把结果写到 composition/assets/subtitle-units.json；handoff Outputs 给出绝对路径、正确 shell 引号的完整命令。
- [ ] 生成后仍逐单元原样上屏，不能由 agent 自由改文本或边界；排版参数由画面阶段确定，分段由脚本完成。
- [ ] 将最终字幕纳入 Phase 8 的 products / 校验，移除其作为 Phase 8 上游 Phase 7 产物的旧引用；加入实际生成所依赖的 transcript / offsets / 朗读稿上游。
- [ ] check-composition、handoff、组件目录和字幕使用说明都读取新位置；assets 位置应被 composition 内容哈希和渲染新鲜度覆盖。
- [ ] 渲染检查复用完整画布契约，拒绝错误分辨率；QA 主时间轴仍使用 Phase 7 的不可变时间轴。
- [ ] 布局改变仅要求 Phase 8 重做，不修改或 restamp Phase 7。确定性重做产生同字节时，保留现有核对后接受该阶段的规则，不伪造无关变化。

验收：最终字幕与实际布局相符；换布局后 Phase 6 / 7 保持完成，音频与 transcript 哈希不变，字幕和报告不会被旧版本误用。

### WI-08 — 模板匹配与真实时间锚点

新增：`modules/templates/github/github.json`（当前支持布局声明）。

修改：`modules/templates/templates.md`、`modules/templates/github/github.md`、`project-cover.md`、`trending-overview.md`（位于该模板目录）、composition 委派包、Phase 8 文档、准备 / 状态校验。

测试：`tests/test_prepare_handoff.py`、`tests/test_phase_docs.py`、`tests/test_align_narration.py`、`tests/test_doc_references.py`、模板声明的新回归。

- [ ] 为当前唯一模板声明 supported_layouts = [presenter]；库入口、准备脚本与 agent 使用同一份声明，不在多处硬编码不同规则。
- [ ] Phase 8 根据内容、orientation 与用户画面要求一起选模板 / layout；未命中或不能满足约束时写 template: null，不保留冲突 Required References。
- [ ] GitHub 普通横屏在允许主持人时可以选择 presenter；用户禁止主持人或项目竖屏时使用通用画面，可保留 GitHub design，不能为套模板改朝向。
- [ ] 读取实际 script / transcript / timeline，选确实被朗读的项目名、tagline、stars 等原文锚点；根据模板字段的含义生成 composition 自己的 cue 声明。
- [ ] 用 timing 模式和已有文本定位逻辑生成模板 cue 时间，再转换为组件的 cue / nameAt / taglineAt / starsAt（区分全片秒数与 scene 内相对秒数）；不直接猜 ASR 文本等于显示稿。
- [ ] 未朗读到的字段不编造时间；省略对应动画或不用该场景 / 模板。事实资料缺失不编造值，也不回去改旁白迁就模板。
- [ ] 不重新引入 github/narration.md 或模板对 Phase 6 的依赖。
- [ ] 测试无模板 cues、数字归一化、重复文本的 scene 范围、缺锚点、禁止主持人、竖屏 fallback、合法 presenter 模板和无矛盾 handoff。

验收：模板适配与时间来源都有明确规则，不只以 handoff 成功或旧文件被删除作为证据。

### WI-09 — 必用素材按适用范围与解析身份检查

修改：`scripts/pipeline-status.py`、catalog / script / composition 委派包、Phase 5 / 6 / 8 / 9 文档。

测试：`tests/test_pipeline_status.py`、`tests/test_cut_clips.py`（确认新字段保存不丢）、`tests/test_phase_docs.py`。

- [ ] catalog 阶段不适用时不读取残留 catalog 的必用清单；标准无素材模式候选仍为空，paper 模式仍检查关键图。
- [ ] 将引用解析成 catalog entry / item / selected clip 的身份，候选覆盖与必用清单共用解析规则，不做原始字符串集合比较。
- [ ] clip 匹配复用现有 0.01 秒容差和窗口规则；数值书写差异等价，引用无法解析或有无法消除的歧义明确失败。
- [ ] 当前 paper catalog 必须明确声明 required_material_refs（没有适用图时可明确为空）；标准模式按当前可选契约。重复判断使用解析后的身份。
- [ ] 候选覆盖只是确定性最低条件，关键图识别和实际画面覆盖由 catalog / script / composition 自检与 QA 核对。
- [ ] 覆盖切换无素材但保留 catalog、paper 不联网、空 / 错误 / 重复清单、12-18.5 与 12.00-18.50、缺候选、关键图正确候选但未展示的自检规则。

验收：同版本项目切换素材策略不会无解，等价引用不会误报遗漏，论文关键图的正向要求不被削弱。

### WI-10 — 要求列表、handoff 替换与步骤输入

修改：`scripts/prepare-handoff.py`、`scripts/pipeline-status.py`、公共契约、script / composition handoff 模板、`references/pipeline-control.md`。

测试：`tests/test_prepare_handoff.py`、`tests/test_pipeline_status.py`、`tests/test_video_contract.py`。

- [ ] narration_requests / composition_requests 缺省和 [] 使用相同的有效值、handoff 内容和指纹，非空要求变化仍只影响对应阶段。
- [ ] fill 先检查原模板中的占位符键，缺键报错，然后一次替换；不再扫描替换值，不将用户文字解释为模板。
- [ ] 多行要求作为一个列表项正确缩进，不能意外生成新的 handoff 顶级小节；内容仍可读，中文与字面量 {{name}} 不丢失。
- [ ] 只按声明的步骤必填字段读取；orientation / layout / template 不在 catalog 或 script 里隐藏必填或作视觉校验。
- [ ] 保留五个 handoff 小节、绝对路径和 shell 引号规则；catalog Additional Instructions 仍为 None，不读取两个要求列表。
- [ ] 测试缺省 ↔ []、非空变化、literal braces、真正缺失模板变量、多行要求、步骤最小输入、非法值、带空格目录、正常错误诊断。

验收：接口声明与实现一致，要求保存、渲染与指纹表达同一条规则。

### WI-11 — 按实际 coding agent 目标派发

修改：`references/delegation/conventions.md`、Phase 5 / 6 / 8 派发说明；准备脚本输出目标信息（确有必要时）。

测试：`tests/test_prepare_handoff.py`、`tests/test_phase_docs.py`、`tests/test_guardrail_docs.py` 中路由与默认值断言。

- [ ] 先解析 inputs.json 的 coding_agent，默认 pi-coding-agent，再判断可用工具能否派发这个目标。
- [ ] 原生工具仅在能明确派发选定目标时使用；存在任意原生 subagent 工具不等于能派发 Pi。
- [ ] Pi CLI 路径保留 pi -p -- 和正确 cwd / 引号；显式其他 agent 使用该目标实际入口，不仍落到 Pi。
- [ ] 未知目标或目标工具不可用明确报告，不静默替换；具体 CLI flag 以目标帮助为准。
- [ ] 不创建自动调用 LLM 的 Python 启动器，不改模型、秘钥或客户端持久设置。
- [ ] 自动测试使用目标元数据、文档路由断言及 stub argv，不产生真实付费 agent 调用；真实路由作为单独手工验收。

验收：默认目标、用户覆盖和实际派发方式一致，而不只是 handoff 显示的名称正确。

### WI-12 — 文档与测试按当前契约收口

修改：`SKILL.md`、`references/phases/` 涉及文档、`references/delegation/`、`references/pipeline-control.md`、`modules/designs/designs.md`、`modules/modules.md`、模板和字幕组件说明，以及对应测试。

- [ ] 保留最新远端 Phase 2–9 的列表格式与已移入各 phase 的失败恢复规则，不恢复 gotchas。
- [ ] 删除仍指导接受旧 manifest / 路径 / hash / theme / fonts 调用 / stamps 的说明。
- [ ] 输入 / 输出 / 完成判据 / 委派包 / PHASES 产物表按目标契约一致更新；不留旧字幕路径和 Phase 1 layout 提示。
- [ ] 原“旧格式通过”用例改为当前契约的拒绝 / 失败诊断测试，旧指令文件不再被读取的负向测试可以保留。
- [ ] 断言行为和有效契约，不为过测试改无关措辞、不删测试隐藏问题。
- [ ] 旧计划中的已实施结论仅作历史，不将其 layout 保留或兼容设计当新执行指令。

验收：执行者只读当前阶段与 handoff 就能按新契约运行，所有文档引用有真实当前目标。

### WI-13 — 完整集成与最终审查

- [ ] 汇总所有 work items，确认没有把布局决定放回 Phase 1，也没有临时 / 保守字幕预算。
- [ ] 核对旧项目兼容清理清单，没有旧格式自动迁移、降级哈希、历史资源兜底或旧戳免失效。
- [ ] 完整保留当前策略下的 redo、finish、restamp、审稿和状态损坏隔离用例。
- [ ] 运行第 5 节命令与 fake 集成路径；记录失败、跳过和依赖不可用，不以文档测试替代实际命令链。
- [ ] 检查所有新增文件都有对应测试、引用和必要目录，不创建可提交秘钥或私有素材文件。
- [ ] 审查 diff 的范围和所有权；不覆盖用户同时编辑的改动，不顺便修改后端、动画、设计 token 或其他旧接口。
- [ ] 报告实际执行的检查、未执行项和剩余风险；不自行提交、推送或合并。

## 5. 验证命令与真实使用路径

以下命令是未来实施验收，不是本轮已执行的结果。均在 skill 根目录激活 .venv，用 python3，不截断测试输出。

### 聚焦检查

```bash
source .venv/bin/activate && python3 -m pytest \
  tests/test_video_contract.py \
  tests/test_harvest_manifest.py \
  tests/test_pipeline_status.py \
  tests/test_prepare_handoff.py \
  tests/test_align_narration.py \
  tests/test_voice_subtitles.py \
  tests/test_cut_clips.py \
  tests/test_fonts_download.py \
  tests/test_check_composition.py \
  tests/test_check_composition_snapshots.py \
  tests/test_check_render.py \
  tests/test_phase_docs.py \
  tests/test_guardrail_docs.py \
  tests/test_doc_references.py -q
```

新测试文件须在对应 work item 建立后才运行上述合并命令；单项执行先使用各项列出的测试。

### 完整检查

```bash
source .venv/bin/activate && python3 -m pytest -q
git diff --check
```

### 必须验证的命令链

1. 新工作区 inputs.json 不含 layout / template → Phase 1 完成 → 无素材 script → fake TTS / fresh transcript / timing → Phase 7 完成 → Phase 8 才选择视觉配置和生成最终字幕。
2. 同一音频先做 stage，再改 presenter → 只有 Phase 8 待重做，Phase 6 / 7 不 stale，音频 / transcript / Phase 7 timeline 哈希不变；最终字幕、报告和渲染依据更新。
3. 普通竖屏 3:4 和显式 9:16 分别生成正确尺寸的布局与最终字幕；交叉匹配失败发生在写工程前。
4. GitHub presenter 模板的真实已有文字产生正确组件秒数；无 cues、无 spoken stars 等情况按声明 fallback；竖屏和禁止主持人时不留不兼容模板。
5. 当前项目切换为无素材模式，即使目录中留有 catalog 也能推进；paper + fetch_materials=false 仍需关键图清单与覆盖。
6. 缺省要求与 [] 的来回切换不触发重做；非空旁白 / 画面要求改变影响正确阶段；包含 {{name}} 和多行要求正常进入 handoff。
7. 构造旧 manifest、缺 hash 偏移表、无指纹报告、库中已删除的资源和旧 stamps：明确拒绝或要求重新生成，不自动迁移、不错误宣布完成、不删除原产物。
8. 当前格式的中断、审稿等待、redo、确定性同字节恢复与损坏隔离仍按原职责正常运行。

真实 Pi 派发、真实 TTS / ASR、HyperFrames 渲染和真实论文关键图展示需单独记录。没有工具、认证或用户提供的素材时明确标记未跑；不得在普通测试里自动发送私有内容或调用外部付费服务。

## 6. 完成标准

- [ ] 十项 P2 和 Phase 1 layout 边界均有对应实现与行为回归，不只修文档、标签或示例。
- [ ] 当前数据格式与生产者一致；旧项目兼容删除范围无漏项，当前失败恢复未被误删。
- [ ] Phase 7 不依赖布局，最终字幕与模板只属于 Phase 8，所有消费路径和状态依赖一致。
- [ ] 有效布局、副本策略、朝向尺寸和模板支持声明使用一致来源，hand off 不包含矛盾指令。
- [ ] 模板 timing 来自实际朗读，不靠先编字幕容量、先写模板旁白、猜时间或重配音过关。
- [ ] 素材引用按适用范围与真实身份检查，要求的持久化、handoff 文本和指纹语义一致。
- [ ] 真实派发目标遵循 coding_agent；未知或不可用目标不静默换 agent。
- [ ] 聚焦与完整测试、命令链、格式检查都有实际证据，未执行的真实服务验证单列。

## 7. 首次实施记录（后续 review 发现不足，不能作为全部完成结论）

### 已实施

- 新增 `scripts/video_contract.py`（Phase 1 字段、逐步骤字段、朝向→画布、要求列表缺省值、库注册发现、layout / 模板声明、偏移表契约），`tests/test_video_contract.py` 覆盖。
- Phase 1 完全去 layout：字段行、选择步骤、护栏文字、姊妹项目指引全部删掉，不补解释；文本步骤重新编号为 1–9。
- Phase 7 与布局无关：`voice-subtitles.py` 不再读 `layout`，只产出音频 / transcript / timeline；`align-narration.py` 改为必选 `--mode timing|subtitles`，两种模式互斥写各自的输出。
- 最终字幕归 Phase 8：产物移到 `composition/assets/subtitle-units.json`（被 composition 源指纹与渲染新鲜度覆盖），handoff 给出完整生成命令；Phase 8 新增视觉输入前置校验（`inputs.json#layout` / `inputs.json#template`）。
- 布局校验改为校验“实际会被引用的那份文件”（不 `--refresh` 时是工作区副本），画布尺寸按朝向精确比对；删掉 design / layout / 模板 / 字体的历史资源兜底。
- 模板与 layout 的兼容关系统一写在 `modules/templates/github/github.json` 的 `supported_layouts`，状态脚本与 handoff 准备读同一份；模板时间锚点用 `template-cues.json` + `timing` 模式生成 `template-timeline.json`。
- 必用素材只在 catalog 阶段适用时参与要求；比对改用解析后的身份（clip 按 0.01 秒容差归一）；论文模式必须显式声明 `required_material_refs`（可为 `[]`）。
- 要求列表缺省与 `[]` 同值同指纹；`fill` 只扫描模板、一次替换，多行要求缩进为同一个列表项。
- 派发先解析 `coding_agent` 再选手段，原生工具不能派发 Pi 时不代替它。
- 删除旧项目兼容：manifest 版本必须声明（不再合并 `manifest_papers.json`）、持久化路径必须相对且不跨出基准目录、偏移表必须有内容哈希、check-composition 报告必须有 `sources_sha256`、旧戳缺键 / 多键均判变化、字体脚本只接受 `--theme`。对应正向兼容测试已改为明确拒绝测试。

### 与本文的偏差

- 更正：首次实施记录中“template 缺省与 null 指纹等价”的说明不符合代码。二者未被归一化，按字段值保持区分；Phase 8 首次写入决策时尚未打戳，不需要为避免自失效而改变这条语义。
- 未提升已有的 stamps 版本号：阶段契约变化通过“上游键集合变化即 stale”暴露，旧戳会被显式重做，而不是升级。
- check-composition 报告只有聚合指纹，所以“composition 变了”的报错不点名具体文件。为保留可读性，测试改为断言指纹不符，而不是文件名。

### 未执行（需真实环境）

- 真实 Pi 派发、真实 TTS / ASR、HyperFrames 渲染、真实论文关键图的展示。
- 上述项在无工具 / 无认证 / 无素材时未跑，不以自动测试冒充；实际执行的命令与结果见下。

### 实际执行的验证

- 聚焦：`tests/test_video_contract.py`、`test_harvest_manifest.py`、`test_pipeline_status.py`、`test_prepare_handoff.py`、`test_align_narration.py`、`test_voice_subtitles.py`、`test_cut_clips.py`、`test_fonts_download.py`、`test_phase_docs.py`、`test_guardrail_docs.py`、`test_doc_references.py`、`test_cli_contract.py`、`test_every_script_tested.py`。
- 完整：`python3 -m pytest -q` → 1075 passed（含实施中新增的回归）；`git diff --check` 干净。
- 命令链（真实脚本 + fake TTS 后端）：
  1. 无 `layout` 的 inputs.json → Phase 1 完成 → Phase 7 完成（只产音频 / transcript / timeline）。
  2. 写入 `layout` / `template` → `prepare-handoff.py composition` 成功（预置 122 个字体文件）→ handoff 里的 `--mode subtitles` 命令能生成 `composition/assets/subtitle-units.json` → Phase 8 完成。
  3. 换 `layout` → 只有 Phase 8 `stale`（`changed_upstream` = `inputs.json#layout`），Phase 7 仍 completed，音频 / transcript / timeline 的 sha256 不变。
  4. 横屏项目写 `layout: portrait` → Phase 8 报 `corrupt`（`inputs.json#layout`，1080x1920 vs 1920x1080），`prepare-handoff.py` 在写任何副本前 exit 1。
  5. 竖屏 + `template: github` → exit 1（`supports layouts presenter`）。

## 8. 本轮产出说明

本轮产出为工作区中的实现与测试，未提交、未推送、未合并。旧计划 `phase-inputs-and-pi-delegation.md` 保留为历史。

## 9. 后续 review 的九项补修

| Review 项 | 修复与行为回归 |
| --- | --- |
| 1. CRLF 哈希不一致 | 生产者和消费者都对源文件原始字节算哈希，字数仍按文本模式；状态与直接对齐共用校验。新增 CRLF → make-narration → fake 配音 / timing → composition subtitles 命令链，等长改字仍拒绝 |
| 2. 旧 manifest / 绝对路径仍被接受 | 读取、upsert、handoff 与状态验收共用当前 manifest / 路径校验；旧版本与持久化绝对路径明确拒绝且不改原文件；生产者内部路径规范化保留 |
| 3. 模板校验读错副本 | 状态与 handoff 都按 effective_resource 选择实际模板 JSON；不 refresh 时拒绝不兼容的副本，refresh 后恢复库声明 |
| 4. 输入阶段边界越界 | 视觉错误留在 Phase 8；handoff 只校验和返回 STEP_INPUTS_FIELDS 声明的字段及本步骤要求，不读取其他步骤的视觉配置 / 要求 |
| 5. layout 副本变化没有 stale | Phase 8 记录实际 design / layout / template JSON 的内容指纹；副本改变使本阶段 stale，相同字节物化不 stale，Phase 7 字节和状态不受影响 |
| 6. 渲染比例未精确校验 | check-render 使用共享 orientation → 精确画布映射；真实 ffmpeg 视频覆盖 3:4 / 9:16 双向错配拒绝与正确分辨率接受 |
| 7. 省略锚点仍播放默认动画 | 删除模板时间锚点默认值；project-cover 必需 nameAt，可选 taglineAt / starsAt 缺失时隐藏相应部分；榜单项目 cue 必填，不再按序号排秒数；实际组件 JS 的 Node 回归覆盖 |
| 8. 引用歧义与语义重复 | 多重 clip 容差匹配 / 重复限定 id 明确报 ambiguous；必用清单按解析身份判重，跨 entry 同 id 仍合法 |
| 9. 无素材仍依赖残留 catalog | catalog 适用性同时控制输入、必用清单及 Phase 6 / 8 指纹；残留 catalog 改动或损坏不影响标准无素材流程，paper 模式仍依赖 catalog |

新增测试：`tests/test_pr_review_regressions.py`、`tests/test_template_cues.py`；原有恢复、切片、字体、对齐、输入和渲染测试按当前契约保留。

最终验收：`source .venv/bin/activate && python3 -m pytest -q` → **1122 passed**；`git diff --check` 通过。聚焦回归也已通过，包含真实脚本的 CRLF → fake 配音 → timing → composition subtitles、ffmpeg 成片精确尺寸检查，以及实际模板 JS 的 Node 执行。

真实 Pi、付费 TTS / ASR、完整 HyperFrames 渲染和论文关键图展示仍未执行，不以 fake 后端或组件 stub 冒充。本轮未提交、未推送、未合并。
