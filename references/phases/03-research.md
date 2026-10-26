# Phase 3 — 主题调研（CRITICAL —— 必须在写脚本之前完成）

## 输入

`inputs.json`；论文模式下还有 Phase 2 解析出的论文 markdown（`harvest_page/main-paper/metadata.json` 指向的完整解析文本）。

## 输出

`research-brief.md`（工作区根目录，落盘保存，不能只放在 scratchpad）。论文模式下可选：`harvest_page/related-<short-name>/`（解析出的相关论文，最多 2 篇，论文 entry 已写入 `harvest_page/manifest.json`）。

## 完成判据

`research-brief.md` 存在且非空，包含 Key facts / Quotes / Numbers、Source URLs 等小节。写脚本之前先把 brief 给用户过目（通常 ~1 轮反馈）。

## 下一步

Phase 4（素材抓取，若 `fetch_materials = true`）；`fetch_materials = false` 时，论文模式进 Phase 5（仅论文素材），其余进 Phase 6（脚本与场景规划）。brief 里的 **Source URLs** 一节是交给 Phase 4 的显式接口。

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
   - **自检失败（未登录或入口失效，失败 JSON 带 `failed_step`）→ 不要重试提交，直接回退到人工 `web_search` 流程**（下面的 step 5-6 变成主路径），把 Gemini 的问题告诉用户。
3. **跑 Gemini Deep Research。** 这是主要的研究主干。
   - 论文模式（`input_mode = "paper"`）时，用文末「论文模式」小节里基于解析论文的 prompt 替换下面的标准 prompt。

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
   - **如果它失败了（selector timeout、运行时错误或其他步骤失败）：** 检查错误 JSON 里的 `failed_step` —— 提交前（step ≤ 6）的失败可以用 `--start-from-step N` 重试；提交后的失败用上一条的续跑命令。如果重试仍不通，回退到人工 `web_search` 流程（下面的 step 5-6 变成主路径），但不要让整个项目卡在消费级 Gemini UI 上。
4. **解析相关论文（可选，仅论文模式）。** 如果调研（Deep Research 的第 7 条回答）指出了 1-2 篇有可用 PDF URL 的高相关论文（例如 arXiv）；Deep Research 没跑成时，等第 6 步的 `web_search` 找到相关论文后再回来补做本步：

   ```bash
   python3 scripts/parse-pdf.py \
     --url "https://arxiv.org/pdf/XXXX.XXXXX" \
     --slug "related-{short-name}" \
     --output-dir {work_dir}/{topic_name}/harvest_page/
   ```
   - 最多解析 2 篇。用户说"只看主论文"或没识别出明显相关工作，则跳过。
   - 这一步不受 `fetch_materials` 影响：相关论文的 figure / table 同样写进 manifest，供 Phase 5 使用。
   - 读相关论文解析出的 markdown，把结论（它的方法 / 结果与主论文的关系）写进 `research-brief.md`。
5. **找空缺。** 不论 Gemini 跑没跑成功，检查：哪些数字、人名、日期或技术细节缺失或没核实？列出来。
6. **做有针对性的搜索。** 用 `web_search` 对每个空缺搜一下 —— 一般：Gemini 跑成功的话 2-4 次（填空），没跑则 3-6 次（完整研究）。示例：
   - "Boris Cherny Anthropic interview Sequoia 2026" → 确认姓名、日期、引文
   - "Claude Code MCP launch date" → 日期细节
   - "GPU vs CPU AI training memory bandwidth" → 技术数字
7. **合成研究 brief，落盘为 `research-brief.md`。** 格式：
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
8. **写脚本之前，把 `research-brief.md` 给用户看。** 通常 ~1 轮反馈。

**仅在以下情况跳过研究：**
- 用户明确说"skip research, use this exact text" 且提供了完整内容
- 主题只是把对方已经写好且整段提供的稿子重新念一遍

**研究是迭代的：计划 2-3 轮搜索补漏，不要搜一次就开写。**

---

## 论文模式

`input_mode = "paper"` 时，跑 Gemini Deep Research（step 3）把标准研究 prompt 替换为基于解析论文的版本：

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
