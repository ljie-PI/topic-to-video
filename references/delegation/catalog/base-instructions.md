# catalog 基础指令（Phase 5 — 素材理解与筛选）

遍历 Phase 4 产出的 `harvest_page/manifest.json["entries"]`。对每一条 entry，在 `{work_dir}/{topic_name}/material-catalog.json` 里建一个 "material entry"。

**路径 base（必须保持一致）：** manifest 里的 `local_path` / `subtitle_path`（包括 `scroll_recording.local_path`）都相对于 `{work_dir}/{topic_name}/harvest_page/`，不是相对于当前目录或 workspace root；它们只能是这个目录内的相对路径，绝对路径或其他 base 的路径不符合当前格式，直接报错。调用抽帧、字幕解析和视觉分析工具时，相对路径必须加上这个 `harvest_page/` 前缀。写入 `material-catalog.json` 时仍原样保留 manifest 的相对路径。

## 输入与执行角色

先读 handoff 中的 `inputs.json`（用户来源输入与阶段级 agent / model 要求）、`research-brief.md`（调研结果）、`vision_analyze/topic-context.txt`（用户输入、调研结果和叙事角度的 summary），以及 Additional Instructions 中的 `catalog-instructions.md`（用户素材要求，如有）。再按 manifest 读取实际图片、视频、字幕、页面摘录与论文 metadata。

**先判断能不能用：** 只有本地文件真实存在的媒体才能进入 catalog。视频带 `download_required: true`、下载失败、或 `local_path` 缺失 / 文件不存在时，跳过这个视频（不抽帧、不选片段、不写进 catalog），同一 entry 里已成功的图片 / 视频照常处理。来源未获取（地区限制、需登录、已下线）与“应该有的本地文件丢了”不同：后者是工作区损坏，按恢复流程处理，不能用跳过来掩盖。

**只按 manifest 工作：** Phase 4.c 已把太小、看不清的 web 素材从 `images[]` / `videos[]` 中剔除。不要扫描 `images/` / `videos/` 目录把已被剔除的文件重新加回 catalog。保留的素材如果实际不可用（模糊、内容认不出），不要写进 catalog 凑数。论文 entry 不受这条影响。


本文件中的**执行 agent**指承担 Phase 5 的 catalog coding agent；未委派时才是调用它的主 agent。下面的 Mode 2 由执行 agent 自己看图，不是把看图任务交回调用者。用户指定的 agent / model 优先于默认值与环境配置；无法用指定模型看图时先说明，不得无声替换。

## 公共视觉分析方式

图片、视频帧、缺失 caption 的论文图表共用这两种方式，具体任务分别见下文：

- **Mode 1（显式 VLM）：** 用户选择此路径，或没有限定分析模型且环境已设置 `VLM_API_KEY`、`VLM_BASE_URL`、`VLM_MODEL` 时，运行 `scripts/vision-analyze.py`，走 OpenAI 兼容的 `/chat/completions`。指定视觉模型时用 `--model <model-id>` 精确传入；不可仅因环境里有另一个 `VLM_MODEL` 就替换用户指定的模型。设置了 key 但缺 URL / model 会报错，不会自动回退。
- **Mode 2（执行 agent 直接分析）：** 未设置 `VLM_API_KEY` 时，脚本返回 `delegate_to_agent`、图片路径列表、`prompt` 和 `context`。执行 agent 用自身的 Read / view 图片工具和当前指定的多模态模型完成分析，再写入 catalog；不额外调用 VLM API。若用户指定使用执行 agent 自身模型，而环境已有不同的 VLM 配置，直接走自身看图路径，不让环境配置覆盖用户要求。

两种方式使用相同的任务 prompt、话题 summary 与评分量表。脚本本身没有固定评分 prompt，也不生成 catalog：Mode 1 的 `analysis` 是模型返回的文本，执行 agent 负责解析、核对和写入。

每次脚本调用都传入 `--prompt`、`--images` 和 `--context-file vision_analyze/topic-context.txt`。**单次最多 10 张图（脚本硬限制）；视频粗看每请求最多 8 帧，局部细看每请求只输入一张 4×4 拼图。**SVG 先栅格化为 PNG 再输入，保留原 SVG 的 catalog 引用。脚本默认 `--detail low`；仅作概览时可用，读取小字、图表、关键 UI 与焦点区域时用 `--detail high`，并提供足够清晰的原图 / 局部图，不能靠 prompt 补回已缩掉的细节。

### 分开理解、匹配与展示建议

每个任务的 prompt 分三个明确部分；可一次调用返回三部分，不要求为了分层额外调用模型：

1. **视觉理解：** 只记录可见事实（对象、文字、图表结构、动作 / 状态变化、视觉风格、关键区域）及看不清 / 不确定之处，不根据话题猜画面。论文有 caption 时用 caption 作为文本依据，不声称已看图。
2. **话题语义匹配：** 对照用户输入与话题 summary，指出可支撑的具体概念 / 论点、画面证据和使用限制，生成 `semantic_description` 并按下表打分。不是只问“相关不相关”。
3. **展示建议：** 根据内容、比例和可读性给出 `layout_affordance` / `focal_region`，理由要能追溯到第 1 步。没有证据就不标注，不把展示能力当成相关性分数。

理解结果、匹配理由与分项评分保存在 `vision_analyze/<slug>/`；catalog 保持下文 schema，提供下游需要的叙事锚点与布局提示。

### 适配度评分与过滤（图片 / 视频 / 缺失 caption 的论文图表）

`score` 是 **1–10 的解说素材适配度**，不是审美评分。各项相加（全为 0 时记 1），记录分项与理由：

| 维度 | 分值 | 判断依据 |
|---|---|---|
| 话题相关性 | 0–4 | 0 偏题；1 只有同名 / 同类；2 可作背景但不能解释核心概念；3 直接支撑一个核心概念；4 直接支撑本视频的核心论点 |
| 画面证据 / 解释力 | 0–3 | 0 没有可用信息；1 只有 logo / 标语 / 泛化画面；2 可见一个明确机制、操作或结果；3 能清楚解释关键机制、变化或比较，且不需猜测 |
| 可读性 / 可用性 | 0–2 | 0 关键内容看不清或缺失；1 局部放大 / reveal 后可读；2 可直接清楚展示 |
| 具体使用价值 | 0–1 | 0 与已有素材重复且无新作用；1 能指出一个明确的讲解用途 |

**过滤阈值为 7 分：`score <7/10` 或偏题的非必用素材不进入 catalog，7 分可保留。** 达标切题的通用素材尽量保留，供下游在符合场景内容时优先考虑选用，不要无故筛掉有讲解价值的真实画面；`required_material_refs` 中的论文关键图 / 表属于成片必用素材，不因评分低而剔除；缺失或看不清时如实报告，不静默省略。 关键证据看不清、caption 与画面矛盾等情况要标明不确定，不用高分掩盖。带非空 caption 的论文图表按「论文」节沿用 `score: 8` 的 caption 默认值，不把它说成模型评分。

### 展示能力判断标准

这些是素材能力提示，不是最终 layout。标准来自 skill 根目录下 `modules/patterns/media/` 的对应 pattern；catalog 阶段不复制 modules，下面列出执行时需要的要点：

| affordance | 可标注的条件 | 对应 pattern |
|---|---|---|
| `media_first` | 一张图能作为主要证据，等比放大后主体可读，文字只需少量辅助 | `media-first.md` |
| `video_first` | 动作、操作或时间变化本身是主要证据，关键动作 / UI 在所选片段内可见 | `video-first.md` |
| `viewport_reveal` | 极端比例素材完整缩放后不可读，沿长轴 / 重点区域逐步阅读合理，能标出阅读顺序与关键区域 | `viewport-reveal.md` |
| `band` | 超宽 / 长条素材完整展示仍能形成可读的信息带，不会缩成细线 | `band.md` |
| `detail_callout` | 需要解释一个可验证的局部，能保留全貌并放大该局部，不裁掉必要轴线 / 图例 | `detail-callout.md` |
| `comparison_pair` | 有明确的比较对象与共同比较维度，两个素材同屏仍可读 | `comparison.md` |
| `comparison_sequence` | 有明确比较关系，但对象有三个及以上，或两个对象同屏不可读，适合按时间逐个 / 分组展示 | `comparison.md` |

单个素材只能提示“可作为比较的一侧”；若其他素材或同一视频中的状态可构成比较，在分析结果中写明对应对象 / 时间段和比较维度，不能看到两帧就判为 comparison。比例分桶只是候选信号，实际内容与可读性才决定是否适用。`focal_region` / avoid-region 必须基于可见区域；关键动作、UI、图例和数据不应被文字浮层遮挡。

## 图片

对非论文 entry 的 `images`（光栅图与栅格化后的 SVG），按 URL 聚合，每批最多 10 张，共享同一话题 summary。prompt 按公共三部分组织，逐张输出，带原素材 `id` / 路径以免批量结果串图：

- **理解：** 图中实际内容、可读文字、图表结构与视觉风格；标出关键局部和不可读部分。
- **匹配：** “这张图可用于解释话题 summary 中哪个具体概念 / 论点？画面中的依据是什么？”输出叙事锚点描述、分项分数与总分。
- **展示：** 透传 `width` / `height`，计算比例分桶，按上表判断布局能力。tall / ultra-tall 素材给出 reveal 候选；能确认关键区域时写 `focal_region`、start / mid / end 阅读顺序或 avoid-region，否则写 `null` 并注明限制。

## 视频与滚动录像

对 `entry.videos` 和 `entry.scroll_recording`（如有）分别处理，不能把不同视频的帧混成一段动作。

### 抽帧与字幕

```bash
scripts/extract-frames.py <video> \
  {work_dir}/{topic_name}/extract_frames/<slug>/<video-name>/ \
  --max-frames 16 --max-width 512
```

**当前抽帧不是固定频率：** 不给时间窗口时，以视频时长 `D`（秒）计算 `interval_s = max(1, floor(D / max_frames))`，ffmpeg 使用 `fps=1/interval_s`，最多输出 `max_frames` 张。CLI 自身默认 `max_frames=20`，但本阶段显式传 16；默认最大输出宽度为 512 px。例如 60 秒视频每 3 秒一帧，300 秒每 18 秒一帧，1200 秒每 75 秒一帧。这是粗看，既可能漏掉短动作，也不保证覆盖最后一帧。

传 `--start-time` 或 `--end-time` 时固定 **1 秒一帧（1 fps）**，仍受 `--max-frames` 限制。定位候选片段后，保存抽帧 JSON，再按每张最多 16 帧拼成 4×4 图。例如 20 秒窗口抽 20 帧，生成 16 + 4 两张拼图，不因单图上限丢掉后半段：

```bash
mkdir -p {work_dir}/{topic_name}/extract_frames/<slug>/<video-name>-detail/
scripts/extract-frames.py <video> \
  {work_dir}/{topic_name}/extract_frames/<slug>/<video-name>-detail/ \
  --start-time 00:01:30 --end-time 00:01:50 --max-frames 20 --max-width 1280 \
  > {work_dir}/{topic_name}/extract_frames/<slug>/<video-name>-detail/frames.json
python3 scripts/stitch-frames.py \
  --frames-json {work_dir}/{topic_name}/extract_frames/<slug>/<video-name>-detail/frames.json \
  --output-dir {work_dir}/{topic_name}/extract_frames/<slug>/<video-name>-detail/sheets/
```

`stitch-frames.py` 读取 `extract-frames.py` 的 JSON，按 `t_s` 排序，输出带帧号与时间戳的 PNG；每图最多 16 帧，从左到右、从上到下排列。不足 16 帧的格子标为 `EMPTY`，超过 16 帧自动生成多张图，原帧不修改。默认每格最大宽度 640 px，可用 `--cell-width` 调整，保持原比例且不裁切。stdout 与输出目录的 `manifest.json` 内容一致，`sheets[*]` 含 `path`、`start_s` / `end_s`（首末采样时刻，不是 clip 边界）、原帧映射 `frames` 和分析用的 `prompt`；每次运行先在临时目录完整生成 PNG，再发布到独立的 `generation-*` 目录，最后原子切换根目录 `manifest.json`，不覆盖旧代图片；生成或发布中途失败不会留下旧 manifest 引用新图片的混合状态。旧代图片保留，重跑时只按当前 manifest 的 `sheets` 列表分析，不扫描旧拼图。

每次抽帧使用独立输出目录，脚本会清理该目录的旧帧。帧文件名带时间戳（如 `frame_t0012.50s.jpg`）；输出 JSON 的 `frames` 含绝对路径 `path` 与 `t_s`（源时间轴上的采样网格秒数），prompt 必须显式附上按序的帧号与 `t_s`，不能期待模型读取文件名 metadata。网格时间不是逐帧精确的源 PTS；粗采样只能提名候选时间段，`selected_clips` 的边界需结合局部帧 / 字幕核对。

带 sidecar 字幕时运行：

```bash
scripts/subtitle-parse.py <subtitle> --keywords '<terms from research brief>'
```

输出的 `entries` 含 `text`、`begin_s` / `end_s` 和原始时间戳；无法解析时间戳的 cue 会被跳过并记入 `warnings`。字幕用于缩小候选窗口，不能单靠字幕声称画面中有某个动作。

### 默认流程：多帧粗看 → 候选片段局部细看

**默认流程：粗看每请求最多 8 张独立帧；局部细看每请求一张由最多 16 帧组成的 4×4 拼图，作为时序整体理解，不逐帧独立评分。** 同一视频按下面顺序处理：

1. **多帧粗看。** 用上面的全视频命令抽最多 16 帧，最大宽度 512 px；将返回的 `frames` 按 `t_s` 排序，每请求最多 8 帧（实际有 16 帧时分成 8 + 8 两批）。每批 prompt 附同一视频信息、帧号 / 时间表、话题 summary，以及前一批的简短时序摘要。显式 VLM 的粗看使用 `--detail low`，只判断全局内容、镜头 / 状态变化与可见时间段，不据此读小字或确定精确片段边界。Mode 2 读取同一组有序帧后跨帧综合，不逐帧单独打分。
2. **提名候选窗口。** 合并各批的时序理解，再结合话题 summary 与字幕提名有明确讲解用途的时间段，记录对应概念 / 论点和粗帧依据。粗看结果只用来定位候选，不直接写成最终 `selected_clips`。
3. **候选片段局部细看。** 只对拟选用的候选窗口运行上面的局部抽帧和拼接命令：1 fps、原帧最大宽度 1280 px，每张 4×4 拼图最多 16 帧；显式 VLM 使用 `--detail high`。**每请求只输入一张拼图，使用该图的 `sheets[*].prompt` 作为任务 prompt 前缀**，再补充候选窗口信息、话题匹配 / 评分 / 展示要求和上一张拼图的时序摘要，并传入同一话题 context。脚本生成的 prompt 明确告诉模型：这是同一视频的连续多帧拼接结果，应从左到右、从上到下作为整体理解，并列出该图的源视频时间范围与帧号 / 时间表；空格不是视频内容。Mode 2 也读取整张拼图并使用相同 prompt，不把它当作单帧画面。每个窗口使用独立输出目录；20 秒窗口使用 `--max-frames 20`，更长窗口分段处理或增大帧数上限，不能因上限截断而漏看后半段；拼接脚本按每图 16 帧自动分页。不对整段视频密集抽帧。核对关键动作 / UI、小字和起止边界；采样间隙内无法确认的变化写明不确定。
4. **合成视频级结果。** 将粗看上下文与局部细看证据合并，写出 `semantic_description`、分项评分和 `selected_clips`；最终片段的 `start` / `end` 与 `reason` 依据局部帧及可用字幕，`frame_paths` 引用局部核对帧。视频级 `score` 评价实际选用的片段集合，不用整段平均质量掩盖低质片段，也不把逐帧分数相加。按公共表判断展示能力，标注关键动作 / UI 与不应遮挡的区域，再按 7 分阈值筛选。

## 论文

**Paper-origin entries** 指 manifest 中 `source_type: "paper_pdf"` 的 entry。写进 catalog 后按 slug 辨认：`main-paper` 是主论文，`related-*` 是相关论文；catalog schema 没有 `source_type` 字段。

- **文本依据：** PDF caption（`paper_metadata.figure_captions` / `table_captions`）非空时，直接作为 `semantic_description`，默认 `score: 8`，不做视觉分析。这是 caption 复用规则，不表示模型已验证图表内容。
- **缺失 caption：** **caption 为空字符串等同没有 caption**；parse-pdf 会为没抽到 caption 的图表写 `''`。此时按公共 Mode 1 / Mode 2 看图：先识别坐标轴、图例、模块、表头与可见结果，再结合话题 summary 匹配和评分，不写空的 `semantic_description`，不编造实验含义。
- **展示建议：** `width` / `height` 由 parse-pdf 用 PIL 实测，按下文推导比例；论文高表格给 `viewport_reveal` 候选。没看图时 `focal_region` 写 `null`（或按可验证的表格内容人工标注），不要把 caption 当作精确坐标证据。

### 仅论文素材（`input_mode = "paper"` 且 `fetch_materials = false`）

Phase 4 被跳过，manifest 只有主论文与已解析的相关论文，没有 web 页面、视频和滚动录像。论文自己的 figure / table 是首选素材；按本节处理（带非空 caption 时 `score: 8`，缺失或为空时走公共视觉分析），没有视频就不抽帧、不解析字幕、不写 `selected_clips`。布局与焦点信息也按本节处理，不另设一套流程。

## 组合与切片段

每条 harvest entry 对应一个 catalog entry；把 `entry.text_excerpt`、图片的叙事锚点描述与视频级理解结果组合，过滤低于 7 分或偏题的非必用素材，达标可用的通用素材尽量保留；论文必用关键图 / 表按 `required_material_refs` 规则保留。对视频写 `selected_clips`，元素形如 `{start, end, reason, frame_paths[]}`，只保留核对过的片段；`clip_path` 由 `cut-clips.py` 写入。

**所有 entry 写完后运行一次：**

```bash
scripts/cut-clips.py {work_dir}/{topic_name}
```

对 catalog 里每个视频的每个 `selected_clip`，切出 `{work_dir}/{topic_name}/clips/<video_id>_<start:.2f>-<end:.2f>.mp4`（`-an` 去掉音轨，libx264 重编码），在该 clip 上写入 `clip_path`（相对工作区），并原地更新 `material-catalog.json`（原子写、保留原文件权限）。视频的 `local_path` 以 `harvest_page/` 为 base。目标文件已存在且非空时跳过，所以改过 catalog 后可以直接重跑。输出 JSON：`{"success": true, "clips": [{"ref": "<slug>/<video_id>:<start>-<end>", "clip_path": ..., "skipped": false}], "errors": []}`；只要有一个 clip 失败就退出 1（已切好的保留且 catalog 增量写回），按 `errors` 里的 `ref` 与原因修 catalog（窗口、`local_path`）后重跑。

**`required_material_refs`（论文模式必填）：** 一个 ref 列表，声明“成片必须出现”的论文关键图 / 表——方法图、模型结构图、关键实验结果的图表。用与 `material_candidates` 相同的 `<slug>/<id>` 格式，指向本 catalog 的 entry。它不重复、不写裸 id；状态脚本会校验每条都能解析。不要因为评分低就把关键图 / 表从清单里去掉：真要有图缺失或看不清，在报告里说明，而不是偷偷省掉。

**`material-catalog.json` 的结构：**

```json
{
  "topic_name": "...",
  "required_material_refs": ["main-paper/fig_001", "main-paper/tab_001"],
  "entries": [
    {
      "url": "...", "slug": "...", "title": "...", "page_type": "...",
      "text_excerpt": "...",
      "images": [
        {
          "id": "img_001",
          "local_path": "example/images/img_001.webp",
          "width": 1280, "height": 720,
          "aspect_ratio": 1.7778,
          "ratio_bucket": "wide",
          "layout_affordance": ["media_first", "comparison_pair"],
          "focal_region": null,
          "semantic_description": "...", "score": 8
        }
      ],
      "videos": [
        {
          "id": "2MJDdzSXL74",
          "local_path": "example/videos/2MJDdzSXL74.webm",
          "width": 1920, "height": 1080,
          "aspect_ratio": 1.7778,
          "ratio_bucket": "wide",
          "layout_affordance": ["video_first", "comparison_sequence"],
          "focal_region": {"x": 0.12, "y": 0.18, "w": 0.74, "h": 0.62, "reason": "关键 UI 操作区域"},
          "duration_seconds": 312.4,
          "semantic_description": "...", "score": 8,
          "selected_clips": [
            {"start": 12.0, "end": 18.5, "reason": "...", "frame_paths": [...],
             "clip_path": "clips/2MJDdzSXL74_12.00-18.50.mp4"}
          ]
        }
      ]
    }
  ]
}
```

- `entries[*].slug` 在每个 URL 上唯一，与 harvest 输出目录名一致。
- 每张图 / 每个视频都带一个 `id`（harvester 写出的文件 stem，例如 `img_001` 或 YouTube video id），只在所属 entry 内唯一，不改 harvester / manifest 的 id。Phase 6 起通过 **`material_ref`** 引用素材：图片 / 视频用 `<slug>/<id>`，视频 clip 用 `<slug>/<video_id>:<start>-<end>`（秒，与该 slug entry 的 `selected_clips` 对应），裸 id 无效。Phase 8 的 composition agent 负责按 slug + id 解析 `material_ref`：图片解析到该 catalog entry 的 `local_path`，视频 clip 一律解析到该 entry 的 `selected_clips[].clip_path`（见下），不再使用视频的 `local_path`；主 agent 永远不直接碰 `local_path`。
- `selected_clips[].clip_path` 指向无音轨的片段文件，相对**工作区根**（不同于图片 / 视频 `local_path` 的 `harvest_page/` base）；Phase 6 的 `<slug>/<video_id>:<start>-<end>` 引用对应的就是它。composition 嵌入视频时只用 `clip_path`。
- `semantic_description` 是结合话题 context 生成的叙事锚点描述（"适合用于说明 X 概念 / Y 论点"），而非纯粹的图像内容描述；Phase 6 的场景规划（`material_candidates`）和 Phase 8 的 composition agent 都依赖它做匹配决策。
- **`width` / `height` 必须透传**：图片由 harvester 抓取时记录；视频由 `video-download.py --harvest-dir` 通过 ffprobe 写入 manifest，构建 catalog 时直接搬过来。Phase 8 的 HyperFrames sub-agent 用这两个字段为每个素材容器设置正确的宽高比，**禁止猜或假设 16:9**。个别素材确实取不到时（例如抓取失败），catalog 里写 `null` 而不是省略字段。
- `aspect_ratio`、`ratio_bucket`、`layout_affordance`、`focal_region` 是布局提示字段，由 Phase 5 根据 `width` / `height`、视觉分析和 topic context 写入；`ratio_bucket` 建议按 `r = width / height` 判定：`ultra-wide` / `strip` `r >= 2.4`；`wide` `1.20 <= r < 2.4`；`square-ish` `0.90 <= r < 1.20`；`tall` `0.50 <= r < 0.90`；`ultra-tall` `r < 0.50`。`tall` / `ultra-tall` 素材给出 `viewport_reveal` 候选；是否适用及焦点信息按公共判断标准与对应的图片 / 论文流程填写。
- `layout_affordance` 只表示素材适合的展示方式，不等于最终 layout；composition 阶段根据旁白和 scene 需求自由决定呈现方式。可选值包括 `video_first`、`media_first`、`viewport_reveal`、`band`、`detail_callout`、`comparison_pair`、`comparison_sequence`。
- `focal_region` 使用归一化坐标 `{x, y, w, h, reason}` 描述关键区域或应避免遮挡的区域；它不是自动裁切命令，只用于 Phase 8 设计 reveal viewport、半透明文本浮层避让和 QA 检查。

**输出：** `extract_frames/<slug>/<video-name>/`、`vision_analyze/<slug>/`、`material-catalog.json`、`clips/`。

报告前核对：`semantic_description` 是否描述真实用途；分项评分是否有依据（<7 的非必用素材已过滤，论文 caption 默认分不当作模型评分）；`selected_clips` 的边界是否有局部帧 / 字幕依据；论文 caption 路径与缺失 caption 的视觉路径是否区分清楚。
