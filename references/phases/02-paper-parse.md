# Phase 2 — 解析论文（仅论文模式，条件步骤）

本 phase 只在 `inputs.json` 的 `input_mode = "paper"` 时进入；标准模式下 pipeline-status 会跳过它。

## 输入

`inputs.json`（`input_mode = "paper"`，来源是 `.pdf` 文件路径或以 `.pdf` 结尾的 URL）。

## 输出

`harvest_page/main-paper/metadata.json`（`source_type = "paper_pdf"`，含 `paper_metadata.full_markdown_path` / `figure_captions` / `table_captions`）+ 解析出的论文 markdown 与图片；可选的 `harvest_page/related-<short-name>/metadata.json`（最多 2 篇相关论文）。

## 完成判据

`harvest_page/main-paper/metadata.json` 存在、非空、JSON 可解析，`source_type = "paper_pdf"` 且 `paper_metadata` 字段齐全。状态脚本校验这些；不通过则回退到本 phase 重跑。

## 下一步

论文解析并入素材流后，进入 Phase 3（调研）——论文 markdown 是主要内容来源，Deep Research 只提供背景与上下文。

---

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

读取输出的 JSON。它提供 `title`、`abstract`、`full_markdown_path`（完整论文的解析 markdown）。这些会喂给 Phase 3 的 Deep Research prompt。

重要的输出字段：
- `manifest_entry.source_type = "paper_pdf"`
- `manifest_entry.paper_metadata.full_markdown_path` —— 完整解析文本
- `manifest_entry.paper_metadata.figure_captions` —— figure 描述
- `manifest_entry.paper_metadata.table_captions` —— table 描述
- `manifest_papers.json` 会更新到 harvest 输出目录下，并在 Phase 4（素材抓取）中并入 `manifest.json`。

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
