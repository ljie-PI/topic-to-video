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

`pipeline-status` 只检查简报存在、各必需小节都在。下面这几项要自己判断：

- 要用的每个关键事实、数字、日期和引文都能指到具体出处，不是从记忆里补的。
- 没核实的点已经删掉，或在 `Open questions / contradictions` 里写清楚，不会当成事实写进旁白。
- 用这些材料能就用户关心的几个问题讲成一段连贯的话；讲不成就是材料不够，继续搜或找用户缩小范围，不要硬写。
- **Source URLs** 里的页面能用来找画面（官方站、文档、仓库、演示视频），不是聚合页或社交 feed。

内容确实不够或讲不通时，改简报并重跑状态脚本；需要时补搜（在上面的额度内）。用户说这稿不行、但又没说改什么时先问清；确认要重写而暂无文件变化时，按 `references/pipeline-control.md` 用 `--redo 3-research` 登记，改完再 `--finish`。

## 下一步

Phase 4（素材抓取，若 `fetch_materials = true`）；`fetch_materials = false` 时，论文模式进 Phase 5（仅论文素材），其余进 Phase 6（脚本与场景规划）。brief 里的 **Source URLs** 一节是交给 Phase 4 的显式接口。

## 护栏

- **Chrome over CDP。** `harvest-pages.py` 和 `gemini-deep-research.py` 必须显式传 `--profile-dir {work_dir}/chrome_profile`。复用已运行的 CDP 时，启动参数不会生效；检查 stderr warning 和输出 JSON 的 `chrome.ignored_flags`，需要新配置就先关闭复用的 Chrome。Chrome 启动即退出通常是 profile 被别的进程占着：关掉冲突进程或换 `--profile-dir`；9222 被占用时传另一个 `--cdp-url`，比如 `http://localhost:9223`。
- **Gemini UI 自动化很脆，失败就换调研方式。** `gemini-deep-research.py` 驱动的是消费级 web UI，selector 或流程一变就报 selector timeout / failed step / 运行时错误；这种情况不要反复重试提交，退回有针对性的 `web_search` 并把问题告诉用户。

---

**每个论断都要扎根在新鲜、可引用的来源上，不要凭记忆写。**

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
4. **解析相关论文（可选，仅论文模式）。** 如果 Deep Research 的第 7 条回答指出了 1-5 篇有可用 PDF URL 的高相关论文（例如 arXiv），在这一步解析：

   ```bash
   python3 scripts/parse-pdf.py \
     --url "https://arxiv.org/pdf/XXXX.XXXXX" \
     --slug "related-{short-name}" \
     --output-dir {work_dir}/{topic_name}/harvest_page/
   ```
   - 最多解析 5 篇。用户说"只看主论文"或没识别出明显相关工作，则跳过。
   - 这一步不受 `fetch_materials` 影响：相关论文的 figure / table 同样写进 manifest，供 Phase 5 使用。
   - 读相关论文解析出的 markdown（`harvest_page/related-<short-name>/metadata.json` 的 `paper_metadata.full_markdown_path`，相对 `harvest_page/`），把结论（它的方法 / 结果与主论文的关系）写进 `research-brief.md`。
5. **找空缺。** 不论 Gemini 跑没跑成功，先列出这段视频要讲的几个核心问题，再标出每处缺什么：定义、关键数字、原始出处，还是某个结论有冲突。写不成一句话的“核心问题”说明还没想清楚，先问用户或继续看材料。
6. **按缺口搜索。** 每次只为最影响讲解的一个缺口搜一次：先说清这次要解决什么，再写关键词。读完结果做三件事——打开重要出处核实（搜索摘要不能当证据）、把已确认的事实补进简报草稿、据此删掉没依据的结论或标为“据报道”。然后看还有没有影响讲解的缺口，有明确目标才继续。关键词可以按结果改写：换概念的别名、直接找原始来源、限定年份或机构、找图示或演示视频。示例：
   - "Claude Code MCP launch date" → 确认发布日期
   - "Boris Cherny Anthropic interview Sequoia" → 核实姓名与引文
   - "GPU vs CPU AI training memory bandwidth" → 技术数字

   **什么时候停（三种情况都算正常结束）：**

   - **资料够了：** 要讲的核心问题已有足够信息，能组织成连贯的讲解；要用的数字、日期、人名和引文都能指到出处；有争议的结论已有对照说明。三项都满足就停，用了两次也是正常。
   - **没进展：** 连续两轮换了关键词或来源，仍只得到重复、无关或不能核实的信息，就停。能舍弃的枝节舍弃；缺的正好是用户要听的核心内容时，说明缺什么，请用户补材料或确认缩小范围——不能宣布调研合格。
   - **到上限：** 一次制作里 agent 主动搜索合计最多 8 次（调研与素材补搜共用这份次数），用满就停，未解决的问题写进简报。不要为了凑次数或凑来源数量继续搜。

   计数：一次搜索查询并读完结果算一次；一批发出多个查询时每个分别计。打开来源核实不算；Gemini 自己的搜索不纳入。续跑沿用已用次数，不因换对话而重置。查过什么、为什么停，简单记在工作区的 `search-notes.md` 即可（不是阶段产物，不参与状态判断）。
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

   数量按需要来：按相关性和来源质量挑，能盖住主要视觉来源就够；不为凑数添无关页面，也不要求每个讲解点都有对应页面。
8. **跑状态脚本，默认自动继续。** 只有 `next_phase.reason` 为 `awaiting_approval` 且 `gate` 为 `research-brief` 时，把 `research-brief.md` 给用户看，明确确认后运行 `python3 scripts/pipeline-status.py {work_dir}/{topic_name} --approve research-brief`。未确认前不要自己批准或进入下游；用户明确授权后续全自动时，把 `inputs.json` 的 `approval_gates` 改为 `[]` 再跑状态脚本，不用 `--approve` 代替。未启用此 gate 时，不额外找用户审稿。

**仅在以下情况跳过研究：**
- 用户明确说"skip research, use this exact text" 且提供了完整内容
- 主题只是把对方已经写好且整段提供的稿子重新念一遍

---

## 论文模式

`input_mode = "paper"` 时，跑 Gemini Deep Research（step 3）把标准研究 prompt 替换为基于解析论文的版本。`{title}` 和 `{abstract}` 从磁盘读 `harvest_page/main-paper/metadata.json`：顶层 `title` 和 `paper_metadata.abstract`（都是 parse-pdf 写出的字段；恢复会话或开新会话后 stdout 已不存在，必须从这个文件取）：

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
