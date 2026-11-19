# Phase 2 — 解析论文（仅论文模式，条件步骤）

本 phase 只在 `inputs.json` 的 `input_mode = "paper"` 时进入；标准模式下 pipeline-status 会跳过它。

## 输入

- `inputs.json`（`input_mode = "paper"`，来源是 `.pdf` 文件路径或以 `.pdf` 结尾的 URL）。

## 输出

- `harvest_page/main-paper/metadata.json`（`source_type = "paper_pdf"`，含 `title`、`paper_metadata.full_markdown_path` / `abstract` / `figure_captions` / `table_captions`）；
- 解析出的论文 markdown 与图片；
- 论文 entry（upsert 进 `harvest_page/manifest.json`，Phase 5 从 manifest 建 catalog）。

## 完成判据

- `harvest_page/main-paper/metadata.json` 存在、非空、JSON 可解析，`source_type = "paper_pdf"` 且 `paper_metadata` 字段齐全；
- `harvest_page/manifest.json` 包含 slug 为 `main-paper` 的论文 entry；
- 状态脚本校验上述两项，不通过则回退到本 phase 重跑。

## 执行后自检

核对解析内容质量：

- `title` / `abstract` 与目标论文 URL 或文件名一致，未抓错文献。
- 解析出的 markdown 无明显缺页、整段乱码或公式丢失。
- `figure_captions` / `table_captions` 与图片文件一一对应；明显错配时在进入 catalog 前修正或标注。
- 方法、模型结构、关键实验结果等关键图与表均已抽出（后续进入 catalog 的 `required_material_refs` 并在成片必出）；缺失时先补解析或从 PDF 补提，不带缺图进 catalog。

## 下一步

论文解析并入素材流后，进入 Phase 3（调研）：论文 markdown 是主要内容来源，Deep Research 只提供背景与上下文。

## 护栏

- **MinerU 云端失败时换路径，不要卡在解析上。** token 缺失或失效时让 `parse-pdf.py` 回退到本地 `mineru`；URL 模式超时先把 PDF 下下来，再用 `--pdf` 重试；云端错误 `-60007` 直接本地重试。

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

读取输出的 JSON。它提供 `title`、`abstract`、`full_markdown_path`（完整论文的解析 markdown，相对于 `harvest_page/`），供 Phase 3 的 Deep Research prompt 使用。

重要的输出字段：
- `manifest_entry.source_type = "paper_pdf"`
- `manifest_entry.paper_metadata.full_markdown_path` —— 完整解析文本
- `manifest_entry.paper_metadata.figure_captions` —— figure 描述
- `manifest_entry.paper_metadata.table_captions` —— table 描述
- 论文 entry 会立即 upsert 到统一的 `manifest.json`，并同步 `<slug>/metadata.json`；原始 MinerU 输出保存在 `<slug>/mineru/`。

**论文内容以解析出的正文为准，不要凭记忆写。** 用户给了 PDF 或论文 URL 时，必须先解析主论文，再把论文 figure / table 并入统一素材流；旁白里的事实、数字和方法描述都从解析结果读，不靠模型已有的印象补。
