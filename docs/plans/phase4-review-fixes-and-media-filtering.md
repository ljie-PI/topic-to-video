# Phase 4 review 修复与素材结果筛选计划

状态：已实施。三个 review 修复、Phase 4.c 筛选与下游配套均已落地；未验证项和与计划的偏差见文末「实施记录」。

## 范围与约束

- 三个 review 修复尽量限制为局部改动，不重构登录态、浏览器生命周期或素材 pipeline。
- origin 规范化按用户要求**不新增或扩充自动化测试**；用一次性检查验证，再运行已有测试。
- localStorage 跳转竞态补一条针对性回归；输出示例扩充已有文档测试，不新建测试框架。
- 质量筛选主要是 Phase 4 的执行指令：复用现有元数据、抽帧工具和执行者视觉能力，不新增模糊度算法、模型调用或下载参数。
- 不修改 manifest/catalog schema、素材 ID、pipeline phase ID 或状态脚本。筛选后的 manifest 继续作为下游的唯一素材输入。
- 不删除原始素材文件；不丢失论文 entry、下载失败记录或历史抓取批次。
- 本轮不实施、提交、推送或合入分支。

## 改动位置总览

| 文件 | 改什么 | 怎么改 |
| --- | --- | --- |
| `scripts/harvest-pages.py` | localStorage 跳转竞态 | 在同一次 `evaluate` 内验证当前 origin，再读取数据；不匹配时丢弃并告警 |
| `scripts/harvest-pages.py` | origin 比较 | 规范化主机名和默认端口，去掉 userinfo，保留非默认端口与 IPv6 的正确表示 |
| `tests/test_harvest_pages.py` | 竞态回归 | 模拟选中 A 标签页后跳转 B，验证 B 的数据不会被归入 A；不添加 origin 等价性测试 |
| `references/phases/04-material-harvest.md` | 目录树与输出示例 | 修正两个 slug 和所有关联路径；Playwright 录制示例使用 `.webm` |
| `tests/test_phase_docs.py` | 输出示例校验 | 扩充已有 JSON 示例测试，校验 URL→slug、条目→路径、录制方式→扩展名 |
| `references/phases/04-material-harvest.md` | 新增结果筛选步骤 | 在 4.a 抓取、4.b 下载之后，进入 Phase 5 前执行尺寸与清晰度检查，并保存筛选结果 |
| `references/phases/05-material-catalog.md` | 最小配套 | 说明输入是 Phase 4 筛选后的 manifest，Phase 5 仍负责相关性评分、选片段与最终可用性判断 |
| `references/delegation/catalog/base-instructions.md` | 最小配套 | 不把已剔除素材从磁盘重新加回 catalog；明确未获取与已下载文件损坏的区别，复查所选片段清晰度 |

## Work item 1：修复 localStorage 跨 origin 数据错配

现有位置：[read_local_storage](../../scripts/harvest-pages.py#L463-L480)、[LOCAL_STORAGE_JS](../../scripts/harvest-pages.py#L445-L452)。

当前先检查 `page.url`，再调用 `evaluate`，用户操作或自动跳转可能发生在两步之间。不能把随后从 B 站读出的内容贴上 A 站的标签。

修改方法：

1. Python 侧筛选标签页仍保留，但它只是候选选择，不作为最终安全检查。
2. 将期望的 canonical origin 作为参数传入 `page.evaluate(LOCAL_STORAGE_JS, expected_origin)`，不把 URL 插进 JS 字符串。
3. JS 在一次同步执行中读取 `location.origin`：不匹配就返回拒绝结果，不访问 localStorage；匹配才读取键值。
4. 返回对象包含实际 origin 和数据；Python 再验证 origin，遇到不匹配返回空结果及 warning。
5. warning 只描述 origin 变化/读取失败，不包含存储值或凭据。该站点 localStorage 失败不影响可用 cookies 和其他站点状态。
6. 标签页关闭、执行上下文被销毁等情况沿用异常告警与丢弃规则，不重试导航、不关闭用户标签页。

Checklist：

- [x] 核对 origin 和读取 localStorage 在同一次同步 `evaluate` 内完成。
- [x] A→B 跳转后，B 的数据不会进入 A 的 storage state。
- [x] 不匹配会告警，日志不包含存储值。
- [x] 增加一条竞态回归，使用隔离 Chrome/受控页面，不读取用户实际登录数据。
- [x] 已有同 origin 的登录态继承、录屏 fallback 测试继续通过。

## Work item 2：修复 origin 等价性，不新增测试

现有位置：[page_origin](../../scripts/harvest-pages.py#L455-L460)。

修改方法：

- 使用解析后的 hostname，而不是原始 netloc；主机名统一为小写。
- `http:80`、`https:443` 与未显式写端口的 origin 保持相同；非默认端口保留。
- userinfo 不属于 origin，不把用户名/密码拼进返回值。
- IPv6 hostname 重新加方括号，不错误拼接端口。
- 对缺少有效主机、非法端口等无法解析的输入返回无有效 origin，不在登录态准备阶段抛出未处理异常。
- 如处理国际化主机名，使用现有标准库能力，不为完整 WHATWG URL 支持增加依赖；不擅自移除有语义差异的尾部点。
- JS 内的安全检查使用同一个 canonical origin，避免 Python 候选匹配成功后又因默认端口表示不同被拒绝。

Checklist：

- [x] `https://example.com`、`https://EXAMPLE.com`、`https://example.com:443` 得到同一 origin。
- [x] 非默认端口仍区分不同 origin，IPv6 表示正确，userinfo 不出现在 origin 中。
- [x] 用一次性检查验证上述行为，并运行已有测试；**不新增或扩充 origin 规范化测试用例**。

## Work item 3：修正实际输出示例

现有位置：[Phase 4 输出示例](../../references/phases/04-material-harvest.md#L128-L172)、[现有示例测试](../../tests/test_phase_docs.py#L90-L121)。

修改方法：

- Anthropic 示例 slug 改为 `anthropic-com-news-claude-code-d30296`。
- YouTube 示例 slug 改为 `www-youtube-com-watch-df2c6f`。视频 ID 留在下载文件名/id 中，不插进 slug。
- 同步目录树、manifest、批次 stdout、pending 下载目录、下载结果及 metadata 更新示例中的所有关联路径。
- `method: "playwright"` 的录屏路径改为 `.webm`；`.mp4` 留给 `cdp_screencast`。不为了示例修改实际录制格式。
- 保留现有 JSON 结构，不重写整份文档。扩充已有断言，用现有 `slug_for_url` 检查 slug，并检查媒体路径归属及录制方式与扩展名对应。

Checklist：

- [x] 所有 URL 与 slug 都对应实际生成规则。
- [x] 目录树、JSON、pending 和下载结果的路径一致。
- [x] Playwright→`.webm`，CDP screencast→`.mp4`。
- [x] 所有 JSON 示例仍可解析，示例测试能捕获此次 review 指出的错误。

## Work item 4：在 Phase 4 增加尺寸与清晰度筛选

### 执行位置与职责

在 `04-material-harvest.md` 的 4.b 结束后增加「结果筛选：进入 Phase 5 前执行」小节，并让完成判据/执行后自检指向它。顺序是：

`4.a 页面抓取 → 4.b 外部视频下载 → 结果质量筛选 → Phase 5`

- Phase 4 剔除明显不可用的素材：太小、模糊、关键内容无法辨认、登录/错误页等。
- Phase 5 继续做话题相关性、VLM 评分、选片段和最终展示可用性判断；不在 Phase 4 重做整套视觉分析。
- 只针对本阶段抓取的 web 素材，包含原生视频、外部平台已下载视频与滚动录像。不把新门槛套到 Phase 2/3 的论文图表上。

### 建议的大小条件

以下是制作默认门槛，不声称是行业标准。以实际文件的像素尺寸为准，不用文件字节数、HTML/CSS 显示大小或放大后的尺寸判断。

| 素材 | 默认最低条件 | 用途与原因 |
| --- | --- | --- |
| 位图图片（含 GIF 的画面尺寸） | **宽 ≥500 px，且高 ≥300 px** | 沿用 harvester 现有采集门槛；适合一般配图，排除常见缩略图，不改初抓参数 |
| 已下载视频、滚动录像 | **短边 ≥360 px，且长边 ≥640 px** | 约 360p 的可用下限，横竖屏一致；`640×360`、`360×640` 均通过，`480×270` 不通过 |
| 需要占据主要画面的位图/视频 | **优先短边 ≥720 px、长边 ≥1280 px** | 720p 及以上更适合大画面；这是优选而非所有小配图的硬门槛 |
| SVG / inline SVG | 不套位图像素门槛 | 矢量图不能按声明的天然尺寸淘汰；仍需确认放大后的关键内容清楚，内嵌低清位图不自动豁免 |

说明：

- 此次不改 `--min-image-width/height` 默认值，也不新增视频尺寸参数。视频尺寸门槛写成下载完成后的执行者筛选规则。
- `500×300` 位图门槛是宽高分别比较，不是旋转无关的长短边规则。若以后要改善较窄竖图的初抓选择，单独讨论，不在这轮顺带修改。
- metadata 宽高缺失/null 时先用已有媒体探测能力核实，不能把 null 当成合格，或假造尺寸；媒体损坏按恢复流程处理。
- 不以文件体积、小码率或视频时长单独认定模糊，不新增统一的最短视频时长要求。
- 用户要求必须使用的关键素材质量不够时，优先找高清版本；无法替代就说明不足，不偷偷降低标准或宣称已合格。

### 清晰度检查方法

**图片：** 查看实际下载文件，重点检查视频需要展示的主体、文字、公式、图表标签和 UI。尺寸足够但关键内容糊成一片、压缩块严重、只有占位图或关键部分被遮挡，同样剔除。自然的背景虚化、留白、线条稀疏本身不算不清楚。

**视频/滚动录像：** 先用已有 `extract-frames.py` 抽少量代表帧快速检查，例如 `--max-frames 3`。怀疑某处有问题时，再查看拟使用的具体片段；不能只因三帧不清楚就断言整段没有可用内容。

抽帧工具默认会把宽度缩到 512 px，**不能用这个缩略预览判定原视频模糊**。质量检查时传 `--max-width <实际视频宽度>`，避免抽帧过程自身降清晰度；同时按计划展示大小核对文字/细节是否可辨认。

- 关键内容持续不可辨认、没有清晰可用画面时，剔除整个视频。
- 只有局部运动模糊、低清片段或不可用片头，其他部分清楚时保留视频；Phase 5 在选片段时避开不可用部分。
- 黑屏、登录页、验证码页和错误页不作为可用画面。静态演示或静态图表不因“不运动”被一刀切排除。
- 不新增 OpenCV、Laplacian 模糊阈值、OCR 判分或第二轮 VLM 分析；执行者直接看图/代表帧，避免误伤矢量图、文字图与低纹理素材。

Checklist：

- [x] 小节明确执行顺序、适用对象、尺寸条件和清晰度判断方法。
- [x] 位图沿用 `500×300`；视频采用旋转无关的 `640×360` 下限；主画面优先 720p。
- [x] SVG 和论文素材边界清楚；null 尺寸、损坏文件不被误当作合格。
- [x] 抽帧不会因默认 512 px 降采样而把高清源判成模糊。
- [x] 局部模糊与整段不可用区分处理，不重复 Phase 5 的精细选片工作。

## Work item 5：让筛选结果真正影响下游，保留追溯能力

仅在对话里说“不用这张图”，或只在 notes 中标注但仍把原 manifest 交给 Phase 5，都不足以完成筛选。推荐把**筛选后的媒体列表保存回同一份 manifest**，不另建排除清单或新的 schema。

具体方法写进 Phase 4 文档：

1. 执行者先列出不合格资源及原因：entry slug、媒体 id/相对 local_path、尺寸、`too_small` / `blurred` / `unreadable` 等原因，记入现有 `search-notes.md`。这些只是审计说明，不是新 JSON 字段或状态判据。
2. 对已下载且确认质量不合格的图片/视频，从相应 entry 的 `images[]` / `videos[]` 中移除引用；不合格滚动录像设为 `scroll_recording: null`。同一物理视频被多个 entry 引用时，对所有引用执行一致过滤。
3. 使用现有 `harvest_manifest.load/save` 保存（传实际变更的 `dirty_slugs`），由它统一同步 `manifest.json` 与对应 `metadata.json`，不要手写两份文件。原始媒体文件保留供复查，不重命名 id。
4. 保留 URL/slug、论文 entry、来源 metrics 和 harvest_batches；来源 metrics 描述页面发现情况，不伪装成筛选后数量。可以在 notes 汇总发现/保留/剔除数量及原因。
5. 下载失败的 `download_required: true` 条目不是质量筛选对象，保留原状态及 pending，不能为了让列表干净而删掉；已成功下载却丢失文件则是损坏，走恢复，不静默当作质量不合格跳过。
6. Phase 5/catalog 只消费筛选后的 manifest，不通过扫描原始目录把已剔除素材重新加回。对保留视频的所选片段仍检查清晰度。
7. 筛完不够时按现有搜索额度补找高清来源，补抓后重新筛选；仍不足则如实交付较少 B-roll。对已运行过的阶段按现有 redo/stale 流程重做，不手改 `.pipeline/`。

本项只增加执行指令及最小的下游文档配套，不改 `harvest_manifest.py` 的保存实现、不新增过滤 CLI。

Checklist：

- [x] 不合格资源从下游输入引用中剔除，而非只有口头/notes 标注。
- [x] manifest 与 metadata 镜像通过既有统一入口同步。
- [x] 原始文件、论文 entry、历史批次、失败下载状态保留。
- [x] Phase 5 不把剔除素材从目录重新捡回来；保留片段仍需清晰可用。
- [x] 筛选理由可追溯，数量不足不会靠放宽标准凑数。

## Work item 6：验证与收尾

- [x] 跑竞态回归和现有登录态/录屏测试。
- [x] 一次性验证 origin 等价、默认端口、非默认端口、IPv6 和 userinfo；不提交相关新增测试。
- [x] 跑现有文档 JSON 测试及新增的 slug/扩展名一致性断言。
- [ ] 用受控素材走一次质量筛选：小尺寸、尺寸足够但模糊、清晰合格、SVG、部分模糊的视频、尺寸未知、下载失败与文件丢失分别处理。
- [x] 验证筛选后的 manifest/metadata 一致，剔除资源不会进入下游，原文件和论文 entry 仍保留。
- [x] 运行定向套件、完整套件和差异检查；记录未验证的真实站点或联网下载，不把计划中的检查写成已通过。

```bash
source .venv/bin/activate && python3 -m pytest tests/test_harvest_pages.py tests/test_harvest_manifest.py tests/test_phase_docs.py tests/test_guardrail_docs.py tests/test_doc_references.py -q
source .venv/bin/activate && python3 -m pytest -q
git diff --check
```

本轮只新增这份计划，上述检查尚未执行。既有 `--urls-file` 行为、匿名降级、已打开标签页限定的 localStorage 继承和下载顺序保持不变。

## 实施记录

改动文件：`scripts/harvest-pages.py`、`references/phases/04-material-harvest.md`、`references/phases/05-material-catalog.md`、`references/delegation/catalog/base-instructions.md`、`tests/test_harvest_pages.py`、`tests/test_phase_docs.py`、本计划。

验证结果：

```text
python3 -m pytest tests/test_harvest_pages.py -q                                  -> 10 passed
python3 -m pytest tests/test_phase_docs.py tests/test_guardrail_docs.py tests/test_doc_references.py -q -> 146 passed
python3 -m pytest -q                                                            -> 986 passed
git diff --check                                                                -> clean
```

一次性检查（不新增测试）：

- origin 规范化：`https://example.com` / `https://EXAMPLE.com` / `https://example.com:443` 均为 `https://example.com`；`http://example.com:80` → `http://example.com`；`:8080` 保留；userinfo 被去掉；`http://[::1]:8080` 与 `http://[::1]` 表示正确；非法端口、`file:///...` 与不可解析输入返回 None。
- 竞态：模拟“选中 A 后跳 B”，`read_local_storage` 返回空 + `page navigated to '...' before the read`，日志不含存储值。
- 筛选片段：在临时工作区实际跑了文档里的写回代码，确认不合格图片被移除、滚动录像默认保留、`metadata.json` 镜像与 manifest 一致、原始文件未删。

### 与计划的偏差（重要）

1. **写回接口从 `harvest_manifest.load/save` 改为 `upsert_entries`。** `harvest_manifest.py` 没有 CLI，直接调 `save()` 要自己传 `dirty_slugs`、容易漏同步镜像；`upsert_entries` 内部已经传 `dirty_slugs`，是现有代码路径。仍不改保存实现、不新增过滤 CLI。
2. **文档写回代码里的占位默认值修正了一次。** 初稿用 `if '<scroll-recording-dropped>':`，占位字符串是真值，会把滚动录像默认删掉；改为 `drop_recording = False` 布尔变量。这个 bug 是实跑片段时发现的。
3. 新增两条文档契约测试（筛选小节 + 示例 slug/扩展名一致性），比计划写的“扩充已有断言”多拆了一条，但没有新建测试框架或新依赖。

### 未验证项

- 未用真实模糊 / 清晰素材逐类走查尺寸与清晰度判定（人工视觉判断本身也无法自动化）；尺寸门槛与写回机制已实测，判定标准仍靠执行时看图。
- 未在真实 X / LinkedIn 页面验证登录态采集，也未做真实联网 yt-dlp 下载。
- 本机 Playwright 自带 ffmpeg 缺失，录屏实际均走 `cdp_screencast`；`method: "playwright"` 只在文档示例与测试容忍范围内体现。