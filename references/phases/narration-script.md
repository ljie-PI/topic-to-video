### Phase 5 — 撰写解说脚本

**输入：** Phase 2 的研究 brief + Phase 4 的 `material-catalog.json` + 用户偏好的切入角度与时长。某段自然依赖某个具体视觉素材时，在正文里顺带提到对应的 catalog slug 或资源。**不要**在这里设计 HyperFrames 的 scene、卡片、时间轴或 `info_units`；scene 切分和视觉结构归 Phase 8 的 HyperFrames sub-agent。

目标：

**Paper mode 解说结构**（当 `input_mode = "paper"`）：

解说沿用论文自身的逻辑流，而非通用的主题结构：
1. Hook —— 这篇论文为什么重要 / 它要解决什么问题
2. Background —— 先前的工作和 SOTA（来自 Deep Research）
3. Key insight / approach（来自论文摘要 + 引言，引用论文中的 figure）
4. Method walkthrough（用 `material_ref` 引用论文 figure）
5. Results（用 `material_ref` 引用论文 table / chart）
6. Impact 与后续工作（来自 Deep Research）
7. Takeaway / CTA

论文 figure（`source_type: "paper_pdf"` 条目）是**首选**素材。从 web 抓取的资源作为补充 B-roll。叙述中合适时自然引用图号 / 表号：`"如表一所示..."`。

- 只使用**研究 brief 中的事实**——每个数字、人名、日期和引文都要可追溯。
- 在有用的地方引用收集到的素材，并为每个 scene 标注推荐的视觉资源。
- 3-10 分钟、`speech_rate=1.2` 下约 **7.5 字符/秒** → `3min ≈ 1350 chars`、`5min ≈ 2250 chars`、`10min ≈ 4500 chars`。
- 15-40 段（按目标时长伸缩），段间用空行分隔（每段约对应一个 scene = 6-15 秒音频）。
- 数字用中文字符（表示年份的 `二零二六` 而不是 `2026`，表示大数字的 `一万零三百六十五` 而不是 `10365`）—— TTS 朗读更自然。
- 英文专有名词保留原文（`Anthropic`、`Claude Code`、`Boris`）。
- 英文多个单词之间的 `-`、`_`、`/`、`\` 等改成空格（`Claude Code` 而不是 `Claude_Code`）。
- 数字周围的符号用中文表示（`百分之五` 而不是 `5%`，`负 3` 而不是 `-3`，`约 100` 而不是 `~100`，`200 多` 而不是 `200+`）。
- **避免全角中文冒号 `：`。** 当全角冒号紧跟着一段长复合句时，CosyVoice 偶尔会插入 0.5-1 秒静音，让视频感觉"卡住"。改用破折号 `——`、用逗号断句或者改写。示例：`某品牌：日均消耗一百万` → `某品牌 —— 日均消耗一百万`。
- 如果用户想要社媒风格，最后一段应为 CTA（`点赞、关注、收藏，下期见`）。

**生成 TTS 之前先把脚本给用户看。** 让对方调整语气、增删某段，或者在你花掉 API 预算前否决某个方向。

存到 `narration.txt`。
