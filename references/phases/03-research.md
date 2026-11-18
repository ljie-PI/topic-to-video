# Phase 3 — 主题调研（CRITICAL —— 必须在写脚本之前完成）

## 输入

- `inputs.json`；
- 论文模式下还有 Phase 2 解析出的论文 markdown（`harvest_page/main-paper/metadata.json` 指向的完整解析文本）。

## 输出

- `research-brief.md`（工作区根目录，落盘保存，不能只放在 scratchpad）；
- 论文模式下可选：`harvest_page/related-<short-name>/`（解析出的相关论文，最多 5 篇，论文 entry 已写入 `harvest_page/manifest.json`）。

## 完成判据

- `research-brief.md` 存在且非空，并且含下面四个小节（标题按模板写）：`## Key facts`、`## Quotes`、`## Numbers`、`## Source URLs`；`## Open questions / contradictions` 可选；
- 小节里的内容是否可信由执行后自检判断，脚本只保证下游能按小节取；
- 校验合格后默认自动继续；只有 `inputs.json` 的 `approval_gates` 包含 `research-brief` 时，才先把 brief 给用户过目并确认。

## 执行后自检

`pipeline-status` 仅校验文件与必需小节，执行者须核对内容：

- 每个关键事实、数字、日期和引文均有明确出处，禁凭记忆补充。
- 未核实信息已删去，或归入 `Open questions / contradictions`（禁在旁白中当作既定事实）。
- 现有材料足以连贯回答核心问题；不足时在搜索额度内补搜或请用户缩小范围，禁硬写。
- **Source URLs** 均为适合取画面的具体页面（官网、文档、仓库、演示视频、具体相关社交帖），不含搜索结果页、聚合榜单或无关社交时间线。

材料不足时补搜并更新简报；用户要求重写但文件未变时，按 `references/pipeline-control.md` 用 `--redo 3-research` 登记，改完 `--finish`。

## 下一步

`fetch_materials = true` 进 Phase 4（素材抓取，消费 brief 的 **Source URLs**）；`fetch_materials = false` 时论文模式进 Phase 5（仅论文素材），其余进 Phase 6。

## 护栏

- **Chrome over CDP。** `harvest-pages.py` 与 `gemini-deep-research.py` 必须显式传 `--profile-dir {work_dir}/chrome_profile`。复用已运行 CDP 时启动参数不生效（检查 stderr warning 与输出 JSON 的 `chrome.ignored_flags`，需新配置先关闭复用的 Chrome）；启动即退通常因 profile 被占用（关冲突进程或换目录），9222 端口占用时传 `--cdp-url`（如 `http://localhost:9223`）。
- **Gemini UI 自动化失败即回退。** `gemini-deep-research.py` 遇 selector timeout / failed step / 运行时错误且重试不通时，切回定向 `web_search` 并告知用户，不卡在消费级网页 UI 上。

---

**每个论断必须扎根在新鲜、可引用的来源上，禁凭记忆写。**

**流程：**

1. **用户提供了 URL** → 先 `web_fetch` 读完原文，作为全片主干。
2. **Gemini Deep Research 自检**（仅验登录态与入口，不提交 prompt；输出 `{"success": true, "self_check": true}` 为通过）：
   ```bash
   scripts/gemini-deep-research.py --self-check \
     --profile-dir {work_dir}/chrome_profile
   ```
   - 自检失败（返回 `failed_step`）→ **不重试提交**，直接切到 step 5–6 的 `web_search` 主路径并告知用户。
3. **运行 Gemini Deep Research**（论文模式改用文末「论文模式」prompt）：
   ```bash
   scripts/gemini-deep-research.py \
     --prompt "关于 [topic] 的全面综述：历史、关键进展、重要人物、技术细节、最新动态" \
     --output-dir {work_dir}/{topic_name}/ \
     --profile-dir {work_dir}/chrome_profile
   ```
   - 脚本新开浏览器标签页执行，产出 `gemini_deep_research.md`（首要事实来源）+ `gemini_deep_research_sources.json`（供 Phase 4 筛选）。
   - 提交后会话 URL 立即写入 `<output-dir>/gemini_deep_research_state.json`，后续超时（默认 1800s）或中断后可从等待完成（step 9）续跑：
     ```bash
     scripts/gemini-deep-research.py --output-dir {work_dir}/{topic_name}/ --resume \
       --profile-dir {work_dir}/chrome_profile
     ```
   - 失败恢复：提交前（`failed_step <= 6`）可用 `--start-from-step N` 重试，提交后用 `--resume`；仍不通则回退到 step 5–6 的 `web_search`。
   - **仅在以下情况跳过**：(a) 用户明确要求 "skip deep research"；(b) 纯复述用户给定文本且无待核实事实论断。
4. **解析相关论文（可选，仅论文模式）。** 若 Deep Research 第 7 条给出 1–5 篇带可用 PDF URL（如 arXiv）的高相关论文（用户要求只看主论文或无明显相关工作则跳过）：
   ```bash
   python3 scripts/parse-pdf.py \
     --url "https://arxiv.org/pdf/XXXX.XXXXX" \
     --slug "related-{short-name}" \
     --output-dir {work_dir}/{topic_name}/harvest_page/
   ```
   - 最多 5 篇，不受 `fetch_materials` 影响（figure / table 同步写入 manifest 供 Phase 5 使用）。
   - 读取 `harvest_page/related-<short-name>/metadata.json` 中 `paper_metadata.full_markdown_path`（相对 `harvest_page/`），将方法 / 结果对比结论写入 `research-brief.md`。
5. **列出缺口。** 无论 Gemini 是否成功，先列出视频要回答的核心问题，标出缺失的定义、关键数字、原始出处或冲突结论（核心问题写不清楚时先看材料或问用户）。
6. **按缺口定向 `web_search`。** 每次只针对最关键的一个缺口搜索：先明确目标再拟关键词（可换概念别名、查原始出处、限定年份/机构、找图示/演示视频）。每次搜索后必须打开重要原始出处核实（禁把搜索摘要当证据），将核实事实补入简报，删去无据结论或标为“据报道”。示例：
   - `"Claude Code MCP launch date"` → 确认发布日期
   - `"Boris Cherny Anthropic interview Sequoia"` → 核实姓名与引文
   - `"GPU vs CPU AI training memory bandwidth"` → 技术数字

   **停止条件（满足任一即停）：**
   - **资料充足**：核心问题可连贯讲清，所用数字、日期、人名与引文均有出处，争议结论已有对照说明。
   - **连续无进展**：连续两轮改换关键词或来源仍无新核实信息；舍弃枝节，若缺失的是核心内容则向用户说明并请其补材料或缩小范围（不得直接判合格）。
   - **达到上限**：单次制作主动搜索最多 **8 次**（调研与 Phase 4 补搜共用，按单条查询计，打开原网页核实与 Gemini 内部搜索不计，续跑沿用已用次数）；用满即停，未解问题记入简报。查询与停搜原因简要记入 `search-notes.md`（非阶段产物）。
7. **合成落盘 `research-brief.md`：**
   ```
   ## Key facts (verified)
   - [fact, source]
   - [fact, source]

   ## Quotes (verbatim if possible)
   - "..." — Person, source

   ## Numbers / dates
   - [N], [unit], [source]

   ## Open questions / contradictions
   - [thing you couldn't verify cleanly — flag in script as "据报道" or remove]

   ## Source URLs (for Phase 4 harvest)
   - [url] — [page type: official site / blog / GitHub / docs / YouTube]
   - [url] — [page type]
   ...
   ```
   **Source URLs** 是交给 Phase 4 的显式接口，按以下来源挑高质量视觉页（不为凑数添无关页，也不因“可能需登录”提前排除——登录态由 Phase 4 用共享 profile 尝试）：
   1. 用户提供的 URL（若有时排第一条）；
   2. `gemini_deep_research_sources.json` 中符合 Phase 4 INCLUDE 类型的 URL；
   3. `web_search` 发现的 INCLUDE 类型 URL。
8. **运行状态脚本。** 仅当 `next_phase.reason == "awaiting_approval"` 且 `gate == "research-brief"` 时展示 `research-brief.md` 请用户确认，确认后运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name} --approve research-brief`（用户授权后续全自动时将 `inputs.json.approval_gates` 置 `[]` 再跑状态脚本）。未启用此 gate 时自动继续。

**跳过整个 Phase 3 的唯一条件：** 用户明确要求 `"skip research, use this exact text"` 且提供了完整定稿，或任务仅是原样朗读用户提供的成稿。

---

## 论文模式

`input_mode = "paper"` 时，从磁盘 `harvest_page/main-paper/metadata.json` 读取顶层 `title` 与 `paper_metadata.abstract`（恢复会话后 stdout 已不存在，必须读文件），将 step 3 的研究 prompt 替换为：

```
"围绕论文《{title}》的背景调研：
摘要：{abstract}

请调研：
1. 这篇论文解决什么问题？此前的最优方法（SOTA）是什么？
2. 关键相关工作和它们与本工作的对比
3. 发表以来的引用与影响力
4. 基于本工作的后续进展
5. 社区对本工作的批评或局限
6. 现实世界的应用
7. 最重要相关论文的 arXiv URL（供本 phase 解析相关论文）"
```

论文自身的 markdown 是**主要**内容来源。Deep Research 提供上下文——背景、影响、相关工作对比。调研的其余部分（解析相关论文、用 `web_search` 补漏、合成 `research-brief.md`）按上面的常规流程进行。
