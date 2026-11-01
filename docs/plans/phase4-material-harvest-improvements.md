# Phase 4 素材抓取改进执行计划

状态：已实施。脚本（`scripts/harvest-pages.py`）、阶段文档、catalog 委派包与回归测试均已按本计划修改；手工验收项见 Work item 7 中未勾选的部分。

## 目标与执行约束

- 补齐 Phase 4.a / 4.b 的文档结构，让页面发现、抓取与外部视频下载的职责清楚。
- URL 列表从文件读取，避免命令行长度限制；复用研究来源内容，不直接把研究文件当最终抓取清单。
- 不因需要登录而提前排除相关社交页面；尽量利用用户已登录的共享 Chrome profile。
- 非关键来源访问受限时继续制作，成片交付时再汇总限制与补抓建议，不默认中途要求用户登录。
- 页面抓取、视频下载的目录、stdout 和持久化 JSON 示例都以实际实现为准。
- 保持现有 manifest v2、媒体路径 base、下载顺序、CDP 复用与 pipeline 调度机制不变。
- 本计划的实施不包含提交、推送或合入远端 `main`；落地需要单独授权。

## Review comment 与交付物对应

| Comment | 处理方案 | Work items |
| --- | --- | --- |
| 只有 Phase 4.b，没有 Phase 4.a | 增加同级 Phase 4.a 标题，覆盖 URL 选择、平台搜索与页面抓取 | 1 |
| 社交 feed 不应因登录被排除 | 同步 Phase 3/4 筛选规则；继承登录态；受限来源延后到最终交付说明 | 1、3、5 |
| URL 应从文件读取 | Phase 4 生成 `harvest-urls.txt`；CLI 新增互斥的 `--urls-file` | 2 |
| 页面抓取输出需要示例 | 分别给出目录树、manifest v2、批次 stdout，覆盖普通页与视频直链 | 4 |
| 视频下载输出需要实际格式与示例 | 展示下载文件、成功/失败 stdout、manifest 更新前后与镜像同步 | 4、6 |

## 已确认的现状

以下定位描述的是**实施前**的代码；行号可能因本次改动而位移，现状以源码为准。

1. [Phase 4 文档](../../references/phases/04-material-harvest.md#L45-L116)没有 Phase 4.a 标题，示例通过 `--urls` 展开整个列表，也没有具体输出 JSON 示例。
2. 社交 feed 不只在 Phase 4 被排除：[Phase 3 自检](../../references/phases/03-research.md#L26)和 [Source URLs 筛选](../../references/phases/03-research.md#L118-L121)也提前排除了它们。
3. 研究 brief 的 Source URLs 是带页面类型说明的 Markdown 小节；[Gemini 来源](../../scripts/gemini-deep-research.py#L254-L268)是 `[{title, url}, ...]`，且该文件可能不存在。两者都不是包含 Phase 4 补搜结果的最终抓取列表。
4. [parse_args](../../scripts/harvest-pages.py#L72-L107)只支持必填 `--urls`；[partition_urls](../../scripts/harvest-pages.py#L739-L778)已经负责去重、scheme 检查、slug 分配与视频平台识别，应继续作为共同入口。
5. [new_harvest_context](../../scripts/harvest-pages.py#L404-L419)调用 `browser.new_context()`，没有导入 profile 的 cookies / storage state。Playwright 的新 context 不共享其他 context 的 cookies/cache，复用 Chrome 进程不等于复用登录态。
6. [持久化 manifest](../../scripts/harvest_manifest.py#L42-L49)与 [harvester stdout](../../scripts/harvest-pages.py#L902-L918)的顶层结构不同；后者只返回本次批次，前者保留论文 entry 和历史批次。
7. [video-download 成功 stdout](../../scripts/video-download.py#L180-L190)使用绝对文件路径；[apply_download](../../scripts/harvest_manifest.py#L294-L334)将媒体状态同步到所有引用 entry，保存时路径转为相对 `harvest_page/` 的路径。
8. [check_harvest_manifest](../../scripts/pipeline-status.py#L573-L582)只检查 entries 与非空 harvest_batches，不验证 pending 是否逐项尝试。当前文档关于自动检查下载处理情况的说法不准确。

## 改动范围

| 文件 | 改动方法 |
| --- | --- |
| `references/phases/03-research.md` | 删除对社交 feed 的绝对排除，保留主题相关性、来源质量与用户 URL 优先规则 |
| `references/phases/04-material-harvest.md` | 补 Phase 4.a；改用列表文件；明确登录态、受限来源、自检责任；补页面与下载输出示例 |
| `references/phases/09-check-mix.md` | 最终交付时读取可选素材搜索记录，汇总未获取来源和补抓建议，不增加 QA finding 类型 |
| `scripts/harvest-pages.py` | 增加文件输入；统一输入后复用现有 URL 分流；让主采集与录屏 fallback 继承同一 profile 的可用登录态；修正脚本头部用法/输出说明 |
| `references/delegation/catalog/base-instructions.md` | 最小配套：明确跳过未下载成功或没有可用本地文件的视频，避免受限来源继续制作的规则在 Phase 5 被破坏 |
| `tests/test_harvest_pages.py` | 增加文件输入与真实本地登录态回归；保留现有媒体、录屏、视频直链和多批次测试 |
| `tests/test_phase_docs.py`、`tests/test_guardrail_docs.py`、`tests/test_doc_references.py` | 覆盖阶段结构、筛选一致性、最终提示、示例与实际 CLI 的对应关系 |
| `tests/test_harvest_manifest.py`、`tests/test_video_download.py` | 复用现有输出、路径、镜像和失败不修改 manifest 的覆盖；仅在缺失时补测试 |

不预设需要修改 `scripts/chrome_cdp.py`、`scripts/video-download.py`、`scripts/harvest_manifest.py` 或 `scripts/pipeline-status.py`；若实施发现必须修改，先说明与本计划目标的关系，保持改动最小。

## 关键设计决策

### 1. 生成中间 URL 清单，不解析研究文档作为 harvester 的业务职责

采用 `{work_dir}/{topic_name}/harvest-urls.txt`：Phase 4 的 agent 汇总、筛选后写入，harvester 只读最终 URL。

不直接复用 Gemini JSON：它可能不存在、含未筛选引用，也缺少用户来源和 Phase 4 新增来源。不直接让 harvester 解析 brief：Markdown 带注释，且来源选择需要 agent 判断，放进脚本会耦合研究模板与采集工具。

该文件是可复查的本批输入，不是新的 pipeline 完成产物，不加入状态脚本的必需产物或上游指纹。续跑仍由 `pipeline-status` 决定；不要用该文件判断阶段是否完成。

### 2. 保留独立录屏 context，在内存中继承登录态

优先从 CDP 默认/profile context 取得 `storage_state()`，在内存中传给新建的采集 context。这样保留现有 viewport、媒体请求与 Playwright 录屏配置，也不需要关闭或改造用户的默认 context。

不优先改为直接在默认 context 抓取：它虽能直接使用登录态，但会牵动录屏实现和 context 生命周期，扩大本次改动。

- 在创建任何采集 context 前明确保存 profile context 引用，不能误将后续新建的匿名/临时 context 当作登录来源。
- 每次采集从同一 profile context 读取当前状态；主路径、首次录屏创建失败后的重试路径、CDP screencast fallback 都遵循同一规则。
- 最低兼容范围是当前依赖支持的 cookies 与 localStorage；不为此提高 Playwright 版本要求。
- 不承诺 sessionStorage、特殊 IndexedDB 登录方案、反机器人验证或所有社交视频格式都能处理。
- 默认 context 不存在时仍允许匿名抓取；已有 profile 的状态读取失败时明确报告，不静默伪装为已使用登录态。
- 不新增登录参数、自动登录流程或持久化 auth-state 文件；新增代码不得将 cookies、storage state、凭据写入日志、stdout、manifest 或其他可共享文件。
- 复用 CDP 时 `--profile-dir` 可能被忽略，使用的是实际连接的 Chrome profile；文档保留 `chrome.ignored_flags` 检查，不宣称参数一定切换了 profile。

### 3. 访问限制作为素材获取说明，不伪装为渲染 QA 错误

复用可选的 `search-notes.md`，在 Phase 4 记录来源、尝试方式、结果、限制和替代来源。Phase 9 最终交付时汇总；该文件不变为必需阶段产物，也不写入 `.pipeline/`。

“视频生成完再提示”指登录/访问限制的补抓提示延后，不是推迟抓取尝试。非关键来源失败时继续制作；若缺失的正是用户要求的核心素材、无法合理替代，则遵循现有材料不足的阻塞规则，不谎称请求已完成。

## Work item 1：补齐阶段结构与来源选择规则

文件：`references/phases/03-research.md`、`references/phases/04-material-harvest.md`

- [x] 在页面抓取总述前增加 `### Phase 4.a — 选择 URL 并批量抓取页面`，与 Phase 4.b 同级；不拆 pipeline phase ID。
- [x] 将“构建数组”等表述改为“生成待抓取 URL 文件”，保留按相关性和质量选择、一次批量调用、缺口补搜与搜索额度规则。
- [x] 从 Phase 4 EXCLUDE 中移除社交 feed 的登录理由；在 INCLUDE/说明中允许相关帖子、作者时间线与 feed，优先具体帖子。
- [x] 同步 Phase 3 的自检及 Source URLs 筛选，不让社交来源在上游提前丢失。
- [x] 保留用户提供 URL 的优先性、搜索结果页不作为来源、PDF 走解析工具等既有规则。
- [x] 明确 feed 只采集主题相关内容，避免无关个人内容进入成片；仍需核对出处、内容质量和使用许可。

完成标准：Phase 3/4 的选择规则一致，4.a/4.b 清楚分工，没有将“需要登录”等同于“不允许抓取”。

## Work item 2：实现文件输入与最终清单生成约定

文件：`scripts/harvest-pages.py`、`references/phases/04-material-harvest.md`、`tests/test_harvest_pages.py`

- [x] 将 `--urls` / `--urls-file` 放入必选、互斥的参数组，保留现有 `--urls` 的短列表调用兼容性。
- [x] 定义唯一文件格式：UTF-8（可接受 BOM），一行一个 URL；去掉行首尾空白、忽略空行。不支持 Markdown、JSON 自动识别或行内注释。
- [x] 文件路径支持正常的用户目录展开；无法读取、编码错误、空文件/全空行返回参数错误 JSON 和退出码 2，在启动 Chrome 前失败。
- [x] 文件读取后交给现有 `partition_urls`，保留顺序、去重、scheme 拒绝信息、slug 规则及视频直链短路行为，不顺便改变 URL 校验语义。
- [x] Phase 4 agent 按用户 URL → brief Source URLs → Gemini 未覆盖来源 → 平台搜索/缺口补搜的优先顺序，筛选并生成 `harvest-urls.txt`；Gemini 文件不存在时不阻塞。
- [x] 清单落在主题工作区，不放 scratch；初始批次用整个清单一次调用。补抓时更新清单为本次所需 URL，依旧复用现有批次持久化规则。
- [x] 文档与脚本头部示例改用 `python3 scripts/harvest-pages.py --urls-file ...`，引用带引号的路径，并保留激活 venv 的前提。
- [x] 禁止以 `--urls $(cat file)` 代替文件读取；这仍会展开命令行。

完成标准：大列表通过单个文件路径传入，文件与 CLI 两种输入共用同一 URL 处理规则，现有调用不被破坏。

## Work item 3：让主采集与录屏 fallback 继承 profile 登录态

文件：`scripts/harvest-pages.py`、`tests/test_harvest_pages.py`

- [x] 按关键设计决策保存 profile context 引用，并通过统一 context 创建入口传递内存 storage state。
- [x] 覆盖正常采集、Playwright 录像 context 创建/录制失败后的路径及 CDP screencast fallback，避免 fallback 重新打开匿名页。
- [x] 继续使用采集 context 的 `ctx.request` 下载页面媒体，使请求携带继承到该 context 的可用 cookies。
- [x] 保留当前录屏 viewport、语言、主/备用录制方式、时长和媒体路径约定。
- [x] 只关闭工具新建的采集 context；不得关闭用户默认 context、已有标签页或共享 Chrome profile。
- [x] 纯 YouTube/Bilibili 直链批次仍跳过 Chrome/CDP，不能因新增登录态逻辑变为必须启动浏览器。
- [x] 增加本地受控页面回归：在默认 context 设置登录 cookie 与 localStorage；采集页面能看到登录内容，受 cookie 保护的图片/原生视频能下载。
- [x] 使用可控失败或测试替身验证 fallback 同样看到登录内容；不能仅依赖本机恰好缺少 Playwright ffmpeg 来触发 fallback。
- [x] 测试 profile context 和原有页在采集结束后仍可用；状态读取失败有明确错误，新增代码不输出认证数据。

完成标准：登录态真实影响采集页面及媒体请求，而不只是复用同一个 Chrome 进程；主/备用路径一致且不影响用户现有会话。

## Work item 4：按真实实现补齐抓取与下载输出示例

文件：`references/phases/04-material-harvest.md`、`scripts/harvest-pages.py`（头部说明）、相关文档测试

- [x] 给页面抓取输出增加目录树，包含 `manifest.json`、每 URL 的 `metadata.json`、普通页可能生成的 `page-source.html` / `images/` / `videos/` / `recording/`，不暗示视频直链也生成页面源码或录像。
- [x] 给出完整、可解析的 manifest v2 示例，同批包含普通页面与外部视频直链；覆盖图片、metrics、滚动录像、待下载视频、pending item、harvest_batches 和 updated_at。
- [x] 示例来自受控 fixture 的实际输出并做必要路径/时间脱敏；保持 URL 与生成 slug 对应，不使用 JSON 省略号假装有效输出。
- [x] 单独给出 harvester 本批 stdout 示例，明确它不是磁盘 manifest 的原样输出；`chrome` 等运行信息在 stdout，不是持久化 manifest 顶层字段。
- [x] 说明持久化媒体路径相对 `harvest_page/`；磁盘始终保留 `pending_downloads` 列表，stdout 无待下载项时省略该字段。
- [x] 展示 pending 的 `source_slug`、`suggested_output_dir` 与可选 `also_referenced_by`；同 URL 多处引用只下载一次。
- [x] 给视频下载单独列目录与文件名约定（yt-dlp 视频 ID 与实际扩展名，可选字幕），不复制页面抓取的目录描述。
- [x] 展示成功 stdout 的 `success/output_dir/files/videos/stdout_tail/manifest_updated`；路径为绝对路径，宽高与 duration_seconds 来自 probe，可能为 null。
- [x] 展示下载前后 manifest 的同一视频对象：成功后 `download_required: false`、`downloaded: true`、id/路径/尺寸/时长更新，没有字幕时 `subtitle_path: null`。
- [x] 说明所有引用 entry 与其 `metadata.json` 同步更新、pending 消失，不产生另一份 download manifest；仅使用默认 pending 输出目录的示例不代表 CLI 禁止 `--output-dir` 覆盖。
- [x] 给出失败 `{"success": false, "error": "..."}` 与退出码 1；失败时 manifest 不变，但目录可能留下部分下载文件，不保证失败无产物。
- [x] 修正“纯发现工具”措辞：外部平台视频只登记，图片和可下载原生视频会实际保存。
- [x] 修正 `pipeline-status` 自动检查范围：结构/批次由脚本检查，pending 逐项尝试由执行者自检，不新增下载尝试状态字段。

完成标准：读者可以区分两种工具、磁盘与 stdout、绝对与相对路径，以及成功/失败对既有 manifest 的影响。

## Work item 5：接通访问限制记录与最终交付提示

文件：`references/phases/04-material-harvest.md`、`references/phases/09-check-mix.md`、相关文档测试

- [x] 改写指定平台不可用/需登录的规则：先利用可用登录态尝试；非关键失败记录后继续，不默认立即请用户登录或换来源。
- [x] 在 `search-notes.md` 记录来源 URL、请求平台、尝试方式、成功/失败、限制原因、替代来源及是否需要补抓；不用结构化认证信息，不写凭据。
- [x] 页面返回登录墙也可能被 harvester 标为 success，执行者需核对页面/图片/录像实际内容；登录页、验证码页和错误页不作为可用素材交给下游。
- [x] Phase 4 自检要求用户指定的每个平台请求均有真实执行结果，不能把普通网页搜索说成完成了指定平台搜索。
- [x] Phase 9 输入/最终交付说明中加入可选 `search-notes.md`；没有该文件不阻塞，也不伪造记录。
- [x] 成片与 contact sheet 交付时列出未获取来源、原因与替代处理；提示用户可在实际共享 profile 登录后请求补抓，说明登录不保证能绕过平台其他限制。
- [x] 用户随后要求补抓时走现有 `--redo 4-material-harvest` 与下游 stale/redo 流程，不自动重做、不手改 `.pipeline/`。
- [x] 不把素材获取限制加入渲染 QA 的 findings，也不新增 approval gate。

完成标准：素材限制有可续跑的记录并在交付中可见，但不会让普通登录失败阻断默认自动制作。

## Work item 6：明确未下载视频的下游边界

文件：`references/delegation/catalog/base-instructions.md`、`references/phases/04-material-harvest.md`、相关文档测试

- [x] 在 catalog 委派包的抽帧步骤前明确：`download_required: true`、下载失败或没有可用本地文件的视频不得抽帧、切片或作为可用视频写入 catalog。
- [x] 同一 entry 中已成功的图片/视频照常处理，不因一个视频失败丢掉全部素材。
- [x] 区分“来源素材未获取”与“应有的本地文件损坏/丢失”；后者按已有恢复规则处理，不能用跳过来掩盖损坏。
- [x] Phase 4 不再声称 Phase 5 会靠某个自动检查器忽略失败，而是指明下游执行规则；不改变 catalog schema 或引用契约。

完成标准：失败视频保留待下载状态且不会误进入素材分析，继续制作只使用实际可用的媒体。

## Work item 7：回归测试与验证

- [x] 文件输入：UTF-8/BOM、空白行、顺序、重复 URL、无法读取、编码错误、空文件、缺失输入、两种输入冲突、scheme 拒绝；文件/参数错误或没有有效 URL 时在 Chrome 启动前失败，混合有效/拒绝 URL 时保留现有继续抓取并报告 rejected 的行为。
- [x] 文件输入工作流：使用带 query 参数和重复项的多 URL 文件；与 `--urls` 对同一批 URL 的分流/条目结果一致；大量 URL 不展开到 shell 参数。
- [x] 登录态与录屏：按 Work item 3 的真实本地 cookie/localStorage 页面与受保护媒体验证主/备用路径；同时保留匿名抓取回归。
- [x] 兼容性：现有直链视频无浏览器、多批次不覆盖论文、重复 harvest 保留已完成下载、媒体路径和录屏测试通过。
- [x] 复用 `tests/test_harvest_manifest.py` 与 `tests/test_video_download.py` 的下载成功、镜像同步、多引用、相对路径与失败不修改 manifest 测试；对 subtitle/probe 的 null 行为缺失覆盖时补齐。
- [x] 文档测试验证 4.a/4.b 同级结构、Phase 3/4 筛选一致、文件参数真实存在、受限来源延后提示、自检与自动检查分工、失败视频下游规则；避免仅依赖大段固定文案断言。
- [x] 对输出示例进行 JSON 可解析与关键字段/路径语义检查；不将认证信息写入示例 fixture。
- [x] 运行定向套件、完整套件与差异检查；记录通过/失败/跳过，以及 Chrome/ffmpeg 等依赖导致的未验证项。

```bash
source .venv/bin/activate && python3 -m pytest tests/test_harvest_pages.py tests/test_harvest_manifest.py tests/test_video_download.py tests/test_chrome_cdp.py tests/test_phase_docs.py tests/test_guardrail_docs.py tests/test_doc_references.py tests/test_pipeline_status.py -q
source .venv/bin/activate && python3 -m pytest -q
git diff --check
```

测试必须使用项目 venv；如果不存在，先按项目环境约定准备，不改用未激活的系统 Python。

本次实施使用 Python 3.9.6 新建的 `.venv`（裸机器上没有 3.10+ 解释器）。定向套件与完整套件均通过，见文末「实施记录」。

### 手工验收（不替代自动回归）

- [x] 在受控工作区生成 `harvest-urls.txt`，按文档中的 `--urls-file` 命令执行，核对目录、stdout 与 manifest 示例。
- [ ] 在用户明确允许的已登录共享 profile 中，尝试一个主题相关社交页面；确认采集 context 真正看到已登录内容，核对素材而非仅看 exit code。
- [ ] 访问受限时验证“不默认中途要求登录 → 记录失败/替代 → 最终交付提示”的流程；核心素材无法替代的情形单独按现有规则处理。
- [x] 使用 fake yt-dlp 或获准下载的视频验证 Phase 4.b 输出、pending 移除和所有 metadata 镜像；真实联网下载若未验证须明确注明。
- [ ] 确认用户默认 context、已打开标签页和共享 profile 保留，且新增登录态逻辑没有泄露认证信息。

## 实施顺序与最终 checklist

建议先完成 Work item 2、3 的 CLI/登录态实现，再按其实际行为完成 Work item 1、4、5、6 的文档与配套约定，最后执行 Work item 7。可以分项提交以便 review，但不能把新增参数或登录态写成已可用后单独交付未实现的代码。

- [x] 五条 comment 均有对应改动与验证证据。
- [x] Phase 3/4/9 与 catalog 委派包的规则一致，不只修 comment 所在的一行。
- [x] URL 文件既解决命令行长度问题，也保留来源优先级和 agent 筛选职责。
- [x] 登录态继承覆盖采集、媒体请求和录屏 fallback；没有关闭用户会话。
- [x] 示例与实际工具输出一致，全部 JSON 示例可解析；不混淆磁盘/批次 stdout 与路径 base。
- [x] 访问限制有记录并在最终交付汇总；未执行的平台搜索没有被宣称完成。
- [x] 未获取视频没有进入抽帧/catalog；已完成下载和论文素材没有被覆盖。
- [x] 没有新增 pipeline phase、必需产物、指纹依赖、approval gate、manifest/catalog schema 或下载尝试状态机制。
- [x] 没有新增认证文件、自动登录、yt-dlp cookies 参数或特殊社交视频下载能力。
- [x] 定向测试、完整测试、手工验证与未验证假设已记录；`git diff --check` 通过。

## 不在本次范围 / 后续可能事项

- yt-dlp 使用浏览器 cookies 的能力、地区/年龄限制专项处理。
- sessionStorage、特殊 IndexedDB 会话、反机器人验证或各平台完整登录支持。
- X/LinkedIn 等 blob/HLS/DRM 视频的专用下载器；本次不承诺页面上的所有视频都能下载。
- 新增机器可读的下载尝试记录，让 pipeline-status 自动验证每个 pending 的处理情况。
- 并发下载、重新设计素材筛选/许可体系、重构全流程文档或恢复机制。

## 实施记录

改动文件：`scripts/harvest-pages.py`、`references/phases/{03,04,09}-*.md`、`references/delegation/catalog/base-instructions.md`、`tests/test_harvest_pages.py`、`tests/test_phase_docs.py`、本计划。

验证结果：

```text
python3 -m pytest tests/test_harvest_pages.py -q            -> 9 passed
python3 -m pytest tests/test_phase_docs.py tests/test_guardrail_docs.py tests/test_doc_references.py -q -> 145 passed
python3 -m pytest -q                                        -> 982 passed
git diff --check                                            -> clean
```

### 与计划的偏差（重要）

1. **localStorage 只能从“已打开在该 origin 的标签页”读到。** 计划写的是从默认 context 取 `storage_state()`。实测跨连接（另一个进程连同一个 CDP Chrome）时它返回的 `origins` 是空列表：localStorage 只按本连接跟踪过的导航收集，而登录页早已在其他连接里打开。改用 `page.evaluate` 读同 origin 已有标签页；没有该标签页时只继承 cookies。没有采用“临时开页再导航到 origin 首页”的方案，因为它会给每个 origin 多一次首页请求，并改变现有“一 URL 一次加载”的行为（会让已有回归测试失效）。
2. 因此脚本头部与 Phase 4 文档写的是“cookies 总是继承，localStorage 仅在站点标签页已打开时继承”，而不是无条件的“cookies + localStorage”。

### 未验证项

- 未在真实已登录的社交站点（X / LinkedIn）上验证采集效果；登录态机制只用本地受控页面验证。
- 未做真实联网的 yt-dlp 下载；Phase 4.b 的下载行为依靠现有 fake yt-dlp 测试覆盖。
- 本机 Playwright 自带的 ffmpeg 缺失，所有录屏实际走 `cdp_screencast` 兜底；`method: "playwright"` 主路径未在本机跑过（已有测试对两种后端都容忍）。
