# Phase 3 — 主题调研（CRITICAL —— 必须在写脚本之前完成）

## 输入

`inputs.json`；论文模式下还有 Phase 2 解析出的论文 markdown（`harvest_page/main-paper/metadata.json` 指向的完整解析文本）。

## 输出

`research-brief.md`（工作区根目录，落盘保存，不能只放在 scratchpad）。

## 完成判据

`research-brief.md` 存在且非空，包含 Key facts / Quotes / Numbers、Source URLs 等小节。写脚本之前先把 brief 给用户过目（通常 ~1 轮反馈）。

## 下一步

Phase 4（素材抓取，若 `fetch_materials = true`）或 Phase 6（脚本与场景规划）。brief 里的 **Source URLs** 一节是交给 Phase 4 的显式接口。

---

**永远不要单凭自己的训练数据写脚本。** 每一个论断都要扎根在新鲜、可引用的来源上。

**流程：**

1. **如果用户给了 URL** → 先 `web_fetch` 它。读完整内容。这是整个视频的脊椎。
2. **跑 Gemini Deep Research。** 这是主要的研究主干。
   - 论文模式（`input_mode = "paper"`）时，用 Phase 2 文档里基于解析论文的 prompt 替换下面的标准 prompt。

   ```bash
   scripts/gemini-deep-research.py \
     --prompt "Comprehensive overview of [topic]: history, key developments, notable figures, technical details, latest news" \
     --output-dir {work_dir}/{topic_name}/
   ```
   - 输出：`gemini_deep_research.md`（完整报告）+ `gemini_deep_research_sources.json`（引用的 URL）
   - 读这份报告；它会成为首要 source。`sources.json` 会喂给 Phase 4 的素材抓取。
   - **仅在以下情况跳过：** (a) 用户明确说"skip deep research"，或者 (b) 主题只是把用户提供的文本重新讲一遍、没有任何待核实的事实论断。
   - **如果它失败了（selector timeout、运行时错误或其他步骤失败）：** 回退到人工 `web_search` 流程（下面的 step 3-4 变成主路径）。检查错误 JSON 里的 `failed_step` —— 你可以用 `--start-from-step N` 重试，但不要让整个项目卡在消费级 Gemini UI 上。
3. **找空缺。** 不论 Gemini 跑没跑成功，检查：哪些数字、人名、日期或技术细节缺失或没核实？列出来。
4. **做有针对性的搜索。** 用 `web_search` 对每个空缺搜一下 —— 一般：Gemini 跑成功的话 2-4 次（填空），没跑则 3-6 次（完整研究）。示例：
   - "Boris Cherny Anthropic interview Sequoia 2026" → 确认姓名、日期、引文
   - "Claude Code MCP launch date" → 日期细节
   - "GPU vs CPU AI training memory bandwidth" → 技术数字
5. **合成研究 brief，落盘为 `research-brief.md`。** 格式：
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
   **Source URLs** 一节是关键 —— 它是显式交给 Phase 4 的接口。来源：
   1. 用户提供的 URL（永远第一条）。
   2. 从 `gemini_deep_research_sources.json` 中筛选出符合 Phase 4 INCLUDE 类型的 URL（官方站、GitHub、docs、blog、YouTube —— 不要聚合页或社交 feed）。
   3. 通过 `web_search` 发现的、符合 INCLUDE 类型的 URL。
   目标 **10-15 个 source URL**，覆盖多样的视觉素材类型。
6. **写脚本之前，把 `research-brief.md` 给用户看。** 通常 ~1 轮反馈。

**仅在以下情况跳过研究：**
- 用户明确说"skip research, use this exact text" 且提供了完整内容
- 主题只是把对方已经写好且整段提供的稿子重新念一遍

**研究是迭代的：计划 2-3 轮搜索补漏，不要搜一次就开写。**
