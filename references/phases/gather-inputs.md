### Phase 1 — 收集输入（一次问用户一个问题）

1. 来源：要抓取的 URL、粘贴的文本，或仅一个主题。
2. 方向：`1920×1080`（横屏）、`1080×1920`（竖屏）或 `1080×1440`（3:4 竖向）。
3. 风格：从用户措辞推断，或在项目工作区里有 `style-prompt.md` 时读取它。`style-prompt.md` 是一份可选的自由文本备注，其内容会覆盖默认的风格推断，并作为 style hint 写入 Phase 8 的 `composition-handoff.md`。
   - 默认：Rosé Pine Dawn 手绘风（`references/design-dawn.md`）
   - 主题是 GitHub trending / repo launch / open source 项目介绍 → **GitHub 预设**（`references/design-github.md`）
   - 主题是 Product Hunt 周榜 / SaaS launch / 新产品发布 → **Product Hunt 预设**（`references/design-producthunt.md`）
   - 用户提到 "moon"、"严肃"、"深色"、"技术感"、"技术评论"、"AI"、"SaaS"、"编程" 且想要严肃风格时，使用 Rosé Pine Moon Serious（`references/design-moon.md`）
   - 主题是 AI/SaaS/编程，但风格没明说，询问对方想要 Dawn 温暖讲解风、Moon 严肃技术编辑风、还是某个品牌预设
4. 时长：通常 3-10 分钟——从用户需求中提取，默认 5 分钟。
5. 语言：默认中文。若用户想要其他语言要询问确认。
6. 询问是否需要搜索视觉素材（图片/视频片段）来丰富场景。默认：是。
7. **输入类型识别：**
   - 来源是 `.pdf` 文件路径 → 置 `input_mode = "paper"`
   - 来源是以 `.pdf` 结尾的 URL（例如 arXiv） → 置 `input_mode = "paper"`，并将该 URL 保留用于 `parse-pdf.py --url`
   - 否则 → `input_mode = "standard"`（默认；后续所有 "paper mode" 段落都跳过）

**如果已经存在一个姊妹项目**（例如用户说 "用和 `claude-code-video/` 一样的风格"），从该项目复制 `composition/DESIGN.md` + `fonts/` 过来，并在 `composition-handoff.md` 里注明 "reuse this DESIGN.md"；HyperFrames sub-agent 会决定该如何复用这个设计。

**工作区发现（checkpoint 入口）：** 确定 `topic_name` slug 之后，检查 `{work_dir}/{topic_name}/` 是否已存在：
```
ls {work_dir}/{topic_name}/ 2>/dev/null
```
如果该目录存在并包含输出文件，按 "Checkpoint & Resume" 一节的 checkpoint 表去扫描，然后向用户报告：
> "Found existing workspace for `{topic_name}`. Detected outputs: [harvest (5 URLs), TTS, ASR, scene-timing]. Resume from Phase 5 (script + scene-material matching)? Or start fresh?"

等用户确认后再继续。

目录不存在时，直接从 Phase 1 开始。
