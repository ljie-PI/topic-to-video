# Deprecated: Composition Brief Template

`composition-brief-template.md` 是旧版 Phase 8 handoff 模板，已被拆分为：

- `references/composition-rules.md`：固定规则集合，包含 upstream contracts、visual quality constraints、QA expectations 与 deliverables。
- `references/composition-handoff-template.md`：每个项目的 handoff 结构、输入路径、style hint 与 user-derived customized rules。

新项目必须生成 `composition-handoff.md`，并在调用 HyperFrames sub-agent 前把 `composition-rules.md` 和选中的 design 文件复制到项目工作区的 `references/` 下。

旧项目中已经存在的 `composition-brief.md` 只作为 legacy fallback；不要再用本文件创建新项目 brief。
