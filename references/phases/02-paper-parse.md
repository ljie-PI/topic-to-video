# Phase 2 — 解析论文（仅论文模式，条件步骤）

本 phase 只在 `inputs.json` 的 `input_mode = "paper"` 时进入；标准模式下 pipeline-status 会跳过它。

## 输入

`inputs.json`（`input_mode = "paper"`，来源是 `.pdf` 文件路径或以 `.pdf` 结尾的 URL）。

## 输出

`harvest_page/main-paper/metadata.json`（`source_type = "paper_pdf"`，含 `paper_metadata.full_markdown_path` / `figure_captions` / `table_captions`）+ 解析出的论文 markdown 与图片；可选的 `harvest_page/related-<short-name>/metadata.json`（最多 2 篇相关论文）。

## 完成判据

`harvest_page/main-paper/metadata.json` 存在、非空、JSON 可解析，`source_type = "paper_pdf"` 且 `paper_metadata` 字段齐全。状态脚本校验这些；不通过则回退到本 phase 重跑。

## 下一步

论文解析并入素材流后，进入 Phase 3（调研）：Deep Research 用下面「调研 prompt（paper mode）」，论文 markdown 是主要内容来源，Deep Research 只提供背景与上下文；再往后 Phase 6 写旁白时用本文档的「论文模式解说结构」。

---

## 调研 prompt（paper mode）

Phase 3 跑 Gemini Deep Research 时，把标准研究 prompt 替换为基于解析论文的版本：

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

论文自身的 markdown 是**主要**内容来源。Deep Research 提供上下文——背景、影响、相关工作对比。调研的其余部分（用 `web_search` 补漏、合成 `research-brief.md`）按 Phase 3 常规流程进行。

## 论文模式解说结构

Phase 6 撰写旁白时，论文模式沿用论文自身的逻辑流，而非通用的主题结构：

1. Hook —— 这篇论文为什么重要 / 它要解决什么问题
2. Background —— 先前的工作和 SOTA（来自 Deep Research）
3. Key insight / approach（来自论文摘要 + 引言，引用论文中的 figure）
4. Method walkthrough（用 `material_ref` 引用论文 figure）
5. Results（用 `material_ref` 引用论文 table / chart）
6. Impact 与后续工作（来自 Deep Research）
7. Takeaway / CTA

论文 figure（`source_type: "paper_pdf"` 条目）是**首选**素材。从 web 抓取的资源作为补充 B-roll。叙述中合适时自然引用图号 / 表号：`"如表一所示..."`。

## 解析主论文

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

读取输出的 JSON。它提供 `title`、`abstract`、`full_markdown_path`（完整论文的解析 markdown，相对于 `harvest_page/`；旧工作区也可能是绝对路径）。这些会喂给 Phase 3 的 Deep Research prompt。

重要的输出字段：
- `manifest_entry.source_type = "paper_pdf"`
- `manifest_entry.paper_metadata.full_markdown_path` —— 完整解析文本
- `manifest_entry.paper_metadata.figure_captions` —— figure 描述
- `manifest_entry.paper_metadata.table_captions` —— table 描述
- 论文 entry 会立即 upsert 到统一的 `manifest.json`，并同步 `<slug>/metadata.json`；原始 MinerU 输出保存在 `<slug>/mineru/`。

**永远不要单凭自己的训练数据写脚本。** 用户给了 PDF 或论文 URL 时，必须先解析主论文，再把论文 figure / table 并入统一素材流。

## 解析相关论文（可选）

如果 Phase 3 的调研指出了 1-2 篇有可用 PDF URL 的高相关论文（例如 arXiv）：

```bash
python3 scripts/parse-pdf.py \
  --url "https://arxiv.org/pdf/XXXX.XXXXX" \
  --output-dir {work_dir}/{topic_name}/harvest_page/ \
  --slug "related-{short-name}"
```

最多 2 篇相关论文。如果用户说"只看主论文"或没识别出明显相关工作，则跳过。
