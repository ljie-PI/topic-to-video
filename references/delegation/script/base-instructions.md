# script 委派包 — 基础指令（旁白 + 场景规划）

你负责为一个解说视频撰写**显示稿、词表和叙事层的场景规划**。主 agent 不会替你做这些决定；你独立完成并落盘产物。

先读工作区里的输入（Inputs 一节列出的文件），再按下面的结构写作。指令冲突时，按 `references/delegation/conventions.md` 的叠加顺序处理：后读的（模板旁白要求 → 项目指令 → 用户追加要求）覆盖先读的。

## 叙事结构

### 标准模式（`input_mode = "standard"` / `topic` / `article` / `text"`）

按目标时长伸缩，整体遵循：

1. **开场（约占 5–10%）**：一句话点题 + 为什么值得看。可以用一个反常识、一个数字或一个场景化问题切入。
2. **背景 / 问题（约占 10–15%）**：观众需要知道的上下文——现状是什么、缺口在哪。
3. **主体展开（约占 60–70%）**：按逻辑分 2–4 个部分推进，每部分若干段落；每个部分开头一句话交代这一部分要回答什么。并列点用清楚的层次（首先 / 其次 / 最后），因果关系写明因果。
4. **亮点 / 对比（视内容可选）**：数据、对比、取舍——把最有说服力的证据放在这里，而不是堆在开头。
5. **结尾（约占 5–10%）**：回扣开头的钩子，给出结论或行动建议。用户要求社媒风格时，最后一段可用“点赞、关注、收藏，下期见”；用户不要 CTA 就不要写。

### 论文模式（`input_mode = "paper"`）

Phase 6 撰写旁白时，论文模式沿用论文自身的逻辑流，而非通用的主题结构：

1. Hook —— 这篇论文为什么重要 / 它要解决什么问题
2. Background —— 先前的工作和 SOTA（来自 Deep Research）
3. Key insight / approach（来自论文摘要 + 引言，引用论文中的 figure）
4. Method walkthrough（用 `material_ref` 引用论文 figure）
5. Results（用 `material_ref` 引用论文 table / chart）
6. Impact 与后续工作（来自 Deep Research）
7. Takeaway / CTA

论文 figure（`source_type: "paper_pdf"` 条目）是**首选**素材。从 web 抓取的资源作为补充 B-roll。叙述中合适时自然引用图号 / 表号：`"如表一所示..."`。

### 通用要求

- 只使用**研究 brief 中的事实**——每个数字、人名、日期和引文都要可追溯。
- 3–10 分钟、`speech_rate=1.4` 下约 **7.5 字符/秒** → `3min ≈ 1350 chars`、`5min ≈ 2250 chars`、`10min ≈ 4500 chars`（按显示稿字数估算，去掉所有空白）。按目标时长伸缩：目标字数 = 分钟数 × 450，状态脚本会把偏差超过 ±15% 的显示稿打回。
- 段间用空行分隔。段落是叙事单元：一个段落讲清一个意思，长短按内容自然伸缩，**不要**按“每段 = 一个 scene / 5–8 秒”硬切——scene 切分由场景规划按语义决定。
- **不要**设计 HyperFrames 的 scene 卡片、时间轴、布局或屏幕文字；画面设计归 composition 阶段。场景规划只到叙事层（见下）。
- 不要在旁白里引导网页链接（“链接放在下面”“见简介链接”等）。

## 显示稿与词表的写法要求

TTS 朗读稿由 `scripts/make-narration.py` 按词表确定性生成，不要手写。以下规则约束显示稿和词表：

- 品牌名、数字、年份在**显示稿**里一律写原始写法（`OpenHuman`、`NVIDIA`、`2026 年`、`5%`）。
- 数字在**朗读形式**里用中文字符（年份 `二零二六`，大数字 `一万零三百六十五`），映射写进词表。
- 英文复合品牌名里的数字展开为单词：`X2Y` → `X to Y`、`X4Y` → `X for Y`（`"Idea2Video": "Idea to Video"`）。显示稿保留原写法。
- 大小写混排品牌名按空格读：`"OpenHuman": "Open Human"`、`"AutoCameo": "Auto Cameo"`。
- TTS 朗读效果差的常见英文品牌 / 机构名改用中文（`"NVIDIA": "英伟达"`）。
- 英文单词间的连字符、下划线、斜杠改成空格（`"GPT-5": "GPT 5"`）。
- 数字周围的符号在朗读形式里用中文（`"5%": "百分之五"`、`"200+": "200 多"`）。
- **显示稿和朗读形式都避免全角中文冒号 `：`**，改用破折号 `——`、逗号断句或改写。
- 词表条目重叠时最长显示形式优先；优先用带上下文的长条目（`2026 年`）避免歧义。

## 产物与 schema

全部写到工作区根目录（与 handoff 同级的 `{work_dir}/{topic_name}/`）：

1. **`script.txt`（显示稿）**：纯文本，段间空行分隔。字幕与画面共用这份文本。
2. **`tts-lexicon.json`（词表）**：JSON map，显示形式 → 朗读形式，键值都是非空字符串。TTS 念不顺的写法全部在这里声明。
3. **`scene-plan.json`（叙事层场景规划）**：JSON 列表，只作参考，composition 阶段可自由合并 / 拆分 / 改选素材。每项：

   ```json
   {
     "scene_id": "scene_1",
     "paragraphs": [1, 2],
     "intent": "这一段帮助观众理解什么",
     "template_scene": "trending-overview",
     "pattern_hints": ["leaderboard"],
     "facts": ["数字、实体、列表、代码等关键事实"],
     "material_candidates": [
       {"ref": "example/img_001", "score": 8, "reason": "对应旁白提到的 X"}
     ],
     "cues": ["模板需要的锚点句摘录"],
     "beats": [{"type": "idea", "text": "原样取自显示稿的一小段"}]
   }
   ```

   - `scene_id`：`scene_1`, `scene_2`, ... 顺序编号。
   - `paragraphs`：覆盖的**段落序号（1 起）**；所有 scene 的段落并集必须覆盖 `script.txt` 的全部段落，段落可以属于多个 scene（合并 / 拆分时）。
   - `intent`：这场景要帮观众理解什么。
   - `template_scene` / `pattern_hints`：可选。选了模板时，`cues` 按模板的旁白要求（`modules/templates/<template>/narration.md`）摘录需要的锚点句——这些句子会用来从配音里算出秒数，务必原样取自显示稿。
   - `beats`：可选的语义节拍列表，每项含 `type` 和 `text`。`type` 只能取 `question`（抛出问题）、`idea`（关键思路 / 原理）、`caveat`（限制 / 注意事项）、`highlight`（亮点 / 关键数字）、`negation`（否定 / 不推荐）、`confirm`（认同 / 讲完一个要点）。`text` 必须逐字取自显示稿，落在该 scene 的 `paragraphs` 范围内，长度 8–30 个字符。全片平均每分钟不超过 4 个；同一个 scene 里，两个 beat 的文本不能重叠。没有合适的时刻就不写，这个字段可以省略。
   - `facts`：这一段旁白依赖的关键事实（数字、实体、列表、代码）。
   - `material_candidates`：候选素材引用，每项含 `ref`、`score`（1–10）、`reason`。**只是候选，不做排他分配**；同一素材可以被多个 scene 候选。`ref` 的格式（即上面论文结构里说的 `material_ref`）：图片和视频用 `<slug>/<id>`，视频 clip 用 `<slug>/<video_id>:<start>-<end>`；`slug` 必须等于 catalog 的 `entries[*].slug`，id 只需存在于该 entry，裸 id 无效。即使两个 entry 都有 `img_001` 或同一个 video id，也必须用各自 slug 区分。clip 秒数与该 entry 的 `selected_clips` 对应——数字间不加空格，起止时间要与某一项相差不超过 0.01 秒。没有 catalog（`fetch_materials = false` 且不是论文模式）时留空列表。
   - **不包含** `layout_role` / `visual_role` / `display_text`——那是 composition 阶段的设计空间。

## 完成后

运行 `scripts/make-narration.py` 生成 `narration.txt` 与 `narration-offsets.json`（命令见 handoff 的 Outputs 一节），然后向主 agent 报告五个产物路径：`script.txt`、`tts-lexicon.json`、`scene-plan.json`、`narration.txt`、`narration-offsets.json`。主 agent 会运行状态脚本做确定性校验（字数 / 段落覆盖 / 素材引用），不通过就把原因交还给你修复，通过后交给用户确认。
