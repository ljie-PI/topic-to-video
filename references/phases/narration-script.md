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
- 3-10 分钟、`speech_rate=1.4` 下约 **7.5 字符/秒** → `3min ≈ 1350 chars`、`5min ≈ 2250 chars`、`10min ≈ 4500 chars`。
- 段间用空行分隔，每段约对应一个 scene = **5-8 秒音频**（在 `speech_rate=1.4` / 7.5 字符/秒下约 37-60 字符/段）。按目标时长伸缩，参考量：3min ≈ 23-36 段、5min ≈ 38-60 段、10min ≈ 75-120 段。
- 数字用中文字符（表示年份的 `二零二六` 而不是 `2026`，表示大数字的 `一万零三百六十五` 而不是 `10365`）—— TTS 朗读更自然。
- **英文复合品牌名里的数字必须展开为单词。** CosyVoice 会把 `2`/`4` 读成"二"/"四"，破坏品牌念法。
  - `X2Y` → `X to Y`（`Idea2Video → Idea to Video`、`Text2Image → Text to Image`、`Img2Img → Image to Image`）
  - `X4Y` → `X for Y`（`Search4U → Search for you`）
  - **视觉里仍写原品牌名** `Idea2Video`；只有 narration（给 TTS 的文本）写展开形式
- **大小写混排品牌名按空格读** —— narration 里 `OpenHuman → Open Human`、`AutoCameo → Auto Cameo`，避免被读成首字母拼读。视觉文件保留原写法。
- 英文专有名词保留原文（`Anthropic`、`Claude Code`、`Boris`）。
- 英文多个单词之间的 `-`、`_`、`/`、`\` 等改成空格（`GPT 5` 而不是 `GPT-5`，`Claude Code` 而不是 `Claude_Code`）。
- 数字周围的符号用中文表示（`百分之五` 而不是 `5%`，`负 3` 而不是 `-3`，`约 100` 而不是 `~100`，`200 多` 而不是 `200+`）。
- **避免全角中文冒号 `：`。** 当全角冒号紧跟着一段长复合句时，CosyVoice 偶尔会插入 0.5-1 秒静音，让视频感觉"卡住"。改用破折号 `——`、用逗号断句或者改写。示例：`某品牌：日均消耗一百万` → `某品牌 —— 日均消耗一百万`。
- 如果用户想要社媒风格，最后一段应为 CTA（`点赞、关注、收藏，下期见`）。

**生成 TTS 之前先把脚本给用户看。** 让对方调整语气、增删某段，或者在你花掉 API 预算前否决某个方向。

存到 `narration.txt`。

### Phase 5.5 — 场景-素材匹配建议

`narration.txt` 经用户确认后，在进入 Phase 6（TTS）之前，主 agent inline 完成此步骤（无需 sub-agent）。

**输入：** `narration.txt` + `material-catalog.json`

**步骤：**

1. 把 `narration.txt` 按空行切分为段落，按顺序处理。
2. 对每个段落，通读其旁白文本，遍历 `material-catalog.json` 中所有图片和视频 clip 的 `semantic_description`，对每个候选素材给出 1-10 的匹配分与理由（理由要对应旁白的具体内容，不要泛泛而谈）。
3. **全局唯一分配**：每个素材（图片 / 视频 clip）最多分配给一个段落。按匹配分做全局贪心分配——分数最高的 (段落, 素材) 配对先定，已被占用的素材不再分配给其他段落；每个段落最终最多得到一个主素材。
4. 段落在 catalog 中没有可用素材（候选分均较低，或合适素材已被占用且无次优）时，显式标记 `"no_match": true`，**不复用已被占用的素材**，留给纯文字 scene。
5. **连续同素材合并**：相邻段落分配到同一素材（同一图片，或同一视频的同一 clip）且旁白都在讲该素材时，合并为一个 scene。合并后该素材连续展示，时长可超过 8s；被合并的每个原段落各自成为该 scene 的一个 `text_beat`，文本信息按原每 5-8s 节奏刷新/轮换。`text_beat` 是 Phase 8 的句子级显示单元：下游根据 transcript 找到对应完整句子的开始时间，并在该句开始前短暂提前显示相关文本信息。
6. 顺序编号最终 scene（`scene_1`, `scene_2`, ...）并输出 `scene-material-suggestions.json`，结构如下：

```json
[
  {
    "scene_index": 1,
    "material_ref": "img_001",
    "reason": "图中展示了 X，与旁白提到的 Y 直接对应",
    "text_beats": [
      {
        "narration_excerpt": "前 20 字...",
        "sentence_excerpt": "用于定位完整句子的短句...",
        "visual_role": "headline | bullet | callout | data_label"
      },
      {
        "narration_excerpt": "前 20 字...",
        "sentence_excerpt": "用于定位完整句子的短句..."
      }
    ]
  },
  {
    "scene_index": 2,
    "material_ref": "2MJDdzSXL74:12.0-18.5",
    "reason": "该片段演示了 Z 流程，配合旁白对 Z 的描述",
    "text_beats": [
      {
        "narration_excerpt": "...",
        "sentence_excerpt": "..."
      }
    ]
  },
  {
    "scene_index": 3,
    "no_match": true,
    "material_ref": null,
    "text_beats": [
      {
        "narration_excerpt": "...",
        "sentence_excerpt": "..."
      }
    ]
  }
]
```

**约束：**
- 每个素材（图片 / 视频 clip）最多用于一个 scene，不复用。
- `no_match` 的 scene 不强行填素材，留空让 HyperFrames sub-agent 用纯排版 / 文字卡片处理。
- 合并 scene 中素材展示可超 8s，但 `text_beats` 仍按原每 5-8s 节奏刷新。
- `text_beats[].sentence_excerpt` 是给 Phase 8 定位完整句子开始时间用的短句，不是版式设计。它应能在 `transcribe/transcript.json` 对应句子中找到；如果省略，Phase 8 用 `narration_excerpt` 自行匹配完整句子。
- `text_beats[].visual_role` 只是语义建议（如 `headline`、`bullet`、`callout`、`data_label`），不指定具体布局；实际排版仍由 Phase 8 根据旁白、素材尺寸和 peak-state audit 决定。

输出到 `scene-material-suggestions.json`（与 `narration.txt` 同级）。
