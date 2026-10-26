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
2. **先跑 Gemini Deep Research 自检，再提交调研。**
   ```bash
   scripts/gemini-deep-research.py --self-check \
     --profile-dir {work_dir}/chrome_profile
   ```
   - 自检只验证登录状态和 Deep Research 入口，不提交任何 prompt。输出 `{"success": true, "self_check": true}` 才算通过。
   - **自检失败（未登录或入口失效，失败 JSON 带 `failed_step`）→ 不要重试提交，直接回退到人工 `web_search` 流程**（下面的 step 4-5 变成主路径），把 Gemini 的问题告诉用户。
3. **跑 Gemini Deep Research。** 这是主要的研究主干。
   - 论文模式（`input_mode = "paper"`）时，用 Phase 2 文档里基于解析论文的 prompt 替换下面的标准 prompt。

   ```bash
   scripts/gemini-deep-research.py \
     --prompt "关于 [topic] 的全面综述：历史、关键进展、重要人物、技术细节、最新动态" \
     --output-dir {work_dir}/{topic_name}/ \
     --profile-dir {work_dir}/chrome_profile
   ```
   - 脚本会**新开一个浏览器标签页**执行，不会导航走你已打开的标签页。
   - 输出：`gemini_deep_research.md`（完整报告）+ `gemini_deep_research_sources.json`（引用的 URL）
   - **提交 prompt 后，会话 URL 会立即写入** `<output-dir>/gemini_deep_research_state.json`；之后的任何失败（包括超时）JSON 里都会带 `session_url`。
   - 读这份报告；它会成为首要 source。`sources.json` 会喂给 Phase 4 的素材抓取。
   - **仅在以下情况跳过：** (a) 用户明确说"skip deep research"，或者 (b) 主题只是把用户提供的文本重新讲一遍、没有任何待核实的事实论断。
   - **超时或中断后续跑（不白跑）：** 默认完成超时是 1800 秒；超时或进程被杀后，从"等待完成"（step 9）那一步续跑，带上 state 文件里保存的 URL：

     ```bash
     scripts/gemini-deep-research.py --output-dir {work_dir}/{topic_name}/ --resume \
       --profile-dir {work_dir}/chrome_profile
     ```
   - **如果它失败了（selector timeout、运行时错误或其他步骤失败）：** 检查错误 JSON 里的 `failed_step` —— 提交前（step ≤ 6）的失败可以用 `--start-from-step N` 重试；提交后的失败用上一条的续跑命令。如果重试仍不通，回退到人工 `web_search` 流程（下面的 step 4-5 变成主路径），但不要让整个项目卡在消费级 Gemini UI 上。
4. **找空缺。** 不论 Gemini 跑没跑成功，检查：哪些数字、人名、日期或技术细节缺失或没核实？列出来。
5. **做有针对性的搜索。** 用 `web_search` 对每个空缺搜一下 —— 一般：Gemini 跑成功的话 2-4 次（填空），没跑则 3-6 次（完整研究）。示例：
   - "Boris Cherny Anthropic interview Sequoia 2026" → 确认姓名、日期、引文
   - "Claude Code MCP launch date" → 日期细节
   - "GPU vs CPU AI training memory bandwidth" → 技术数字
6. **合成研究 brief，落盘为 `research-brief.md`。** 格式：
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
7. **写脚本之前，把 `research-brief.md` 给用户看。** 通常 ~1 轮反馈。

**仅在以下情况跳过研究：**
- 用户明确说"skip research, use this exact text" 且提供了完整内容
- 主题只是把对方已经写好且整段提供的稿子重新念一遍

**研究是迭代的：计划 2-3 轮搜索补漏，不要搜一次就开写。**
