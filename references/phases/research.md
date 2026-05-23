### Phase 2 — 主题调研（CRITICAL —— 必须在写脚本之前完成）

#### Phase 2a — 解析 PDF（仅 paper mode）

除非 `input_mode = "paper"`，否则跳过。

```bash
# URL 输入（arXiv 等）—— 直接传给 MinerU 云端 API
python3 scripts/parse-pdf.py \
  --url "{pdf_url}" \
  --output-dir {work_dir}/{topic_name}/harvest_page/ \
  --slug "main-paper"

# 本地文件输入
python3 scripts/parse-pdf.py \
  --pdf "{pdf_path}" \
  --output-dir {work_dir}/{topic_name}/harvest_page/ \
  --slug "main-paper"
```

需要环境变量 `MINERU_API_TOKEN`（来自 `.env`）。token 缺失或云端失败时会自动 fallback 到本地 `mineru` CLI。

读取输出的 JSON。它提供 `title`、`abstract`、`full_markdown_path`（完整论文的解析 markdown）。这些会喂给 Phase 2b 的 Deep Research prompt。

重要的输出字段：
- `manifest_entry.source_type = "paper_pdf"`
- `manifest_entry.paper_metadata.full_markdown_path` —— 完整解析文本
- `manifest_entry.paper_metadata.figure_captions` —— figure 描述
- `manifest_entry.paper_metadata.table_captions` —— table 描述
- `manifest_papers.json` 会更新到 harvest 输出目录下，并在 Phase 3 中并入 `manifest.json`。

**Checkpoint：** 如果 `harvest_page/main-paper/metadata.json` 已存在则跳过。

#### Phase 2b — Deep Research（paper mode 变体）

当 `input_mode = "paper"`，把标准研究 prompt 替换为基于解析论文的版本：

```
"Background research for the paper '{title}':
Abstract: {abstract}

Research:
1. What problem does this paper address? What was SOTA before it?
2. Key related works and how they compare
3. Citations and impact since publication
4. Subsequent developments building on this work
5. Community criticisms or limitations
6. Real-world applications
7. arXiv URLs of the most important related papers (for Phase 2c)"
```

论文自身的 markdown 是**主要**内容来源。Deep Research 提供上下文——背景、影响、相关工作对比。Phase 2 的其余部分（用 `web_search` 补漏、合成研究 brief）按常规流程进行。

#### Phase 2c — 解析相关论文（paper mode，可选）

如果 Phase 2b 指出了 1-2 篇有可用 PDF URL 的高相关论文（例如 arXiv）：

```bash
python3 scripts/parse-pdf.py \
  --url "https://arxiv.org/pdf/XXXX.XXXXX" \
  --output-dir {work_dir}/{topic_name}/harvest_page/ \
  --slug "related-{short-name}"
```

最多 2 篇相关论文。如果用户说"只看主论文"或没识别出明显相关工作，则跳过。

**Checkpoint：** 如果 `harvest_page/related-{short-name}/metadata.json` 已存在则跳过。

**永远不要单凭自己的训练数据写脚本。** 60 秒的视频容不下含糊其辞，任何事实错误都会变成 60 秒的错误。每一个论断都要扎根在新鲜、可引用的来源上。

**流程：**

1. **如果用户给了 URL** → 先 `web_fetch` 它。读完整内容。这是整个视频的脊椎。
2. **跑 Gemini Deep Research。** 这是主要的研究主干 —— 它产出的报告远比人工 web 搜索更全面、有出处。
   ```bash
   scripts/gemini-deep-research.py \
     --prompt "Comprehensive overview of [topic]: history, key developments, notable figures, technical details, latest news" \
     --output-dir {work_dir}/{topic_name}/
   ```
   - 输出：`gemini_deep_research.md`（完整报告）+ `gemini_deep_research_sources.json`（引用的 URL）
   - 读这份报告；它会成为首要 source。`sources.json` 会喂给 Phase 3 的素材抓取。
   - **仅在以下情况跳过：** (a) 用户明确说"skip deep research"，或者 (b) 主题只是把用户提供的文本重新讲一遍、没有任何待核实的事实论断。
   - **如果它失败了（selector timeout、运行时错误或其他步骤失败）：** 回退到人工 `web_search` 流程（下面的 step 3-4 变成主路径）。检查错误 JSON 里的 `failed_step` —— 你可以用 `--start-from-step N` 重试，但不要让整个项目卡在消费级 Gemini UI 上。
3. **找空缺。** 不论 Gemini 跑没跑成功，检查：哪些数字、人名、日期或技术细节缺失或没核实？列出来。
4. **做有针对性的搜索。** 用 `web_search` 对每个空缺搜一下 —— 一般：Gemini 跑成功的话 2-4 次（填空），没跑则 3-6 次（完整研究）。示例：
   - "Boris Cherny Anthropic interview Sequoia 2026" → 确认姓名、日期、引文
   - "Claude Code MCP launch date" → 日期细节
   - "GPU vs CPU AI training memory bandwidth" → 技术数字
5. **在 scratchpad 里合成研究 brief**。格式：
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

   ## Source URLs (for Phase 3 harvest)
   - [url] — [page type: official site / blog / GitHub / docs / YouTube]
   - [url] — [page type]
   ...
   ```
   **Source URLs** 一节是关键 —— 它是显式交给 Phase 3 的接口。来源：
   1. 用户提供的 URL（永远第一条）。
   2. 从 `gemini_deep_research_sources.json` 中筛选出符合 Phase 3 INCLUDE 类型的 URL（官方站、GitHub、docs、blog、YouTube —— 不要聚合页或社交 feed）。
   3. 通过 `web_search` 发现的、符合 INCLUDE 类型的 URL。
   目标 **10-15 个 source URL**，覆盖多样的视觉素材类型。
6. **写脚本之前，把研究 brief 给用户看。** 对方可能补充背景、纠正误读或者收窄角度。通常 ~1 轮反馈。

**仅在以下情况跳过研究：**
- 用户明确说"skip research, use this exact text" 且提供了完整内容
- 主题只是把对方已经写好且整段提供的稿子重新念一遍

**反模式：** 搜一次，然后假装 brief 已完整地开始写。真研究是迭代的 —— 找到一个事实，会引出新的疑问，再去搜。计划 2-3 轮。
