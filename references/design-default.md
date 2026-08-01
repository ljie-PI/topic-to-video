# Style Hint — Frag Note × 安静明亮编辑风

> Phase 8 默认 style hint。未指定主题时，按本文件执行暖白画布、克制薰衣草强调、暖中性色层级与低干扰编辑风。旁白同步、素材、布局、字幕与 QA 仍以 `references/composition-rules.md` 为准。
>
> 本主题源自 Frag Note Design System；下面以 `design-moon.md` 的视频主题格式整理，并保留其全部颜色 token、层级、组件、状态、可访问性与动效语义。

## 配色（只用以下颜色）

### 主题专属标记

- 连续暖白画布 + 单一薰衣草强调：`primary` 表示行动、焦点、选中、当前结论与生成内容上下文。
- 深度主要来自表面色与细分隔线，而不是厚阴影、发光或多色背景。
- 蓝、绿、琥珀、红只能表达真实的 info / success / warning / error 语义，绝不能作为随意装饰。
- 深色 token 只用于代码、终端、媒体局部或遮罩；不把浅色 scene 切成装饰性的深色分区。
- 设计画像保持原意：`redesign-preserve`，面向记录与整理碎片想法的人；语言气质为安静、专注、人性化、轻编辑感；设计变化度 4/10、动效强度 3/10、视觉密度 5/10。内容 / 论断是最强视觉元素，界面 chrome 必须退后。

### 颜色 token 与使用场景

| 类别 | Token | 色值 | 允许使用场景 |
|---|---|---|---|
| 主强调 | `primary` | `#6F5BD3` | 主行动、当前状态、关键链接、品牌标记、当前结论；配白字对比度为 5.11:1。 |
| 主强调 hover | `primary-hover` | `#604CC3` | 交互 hover；视频静态画面不单独模拟 hover。 |
| 主强调 active | `primary-active` | `#513EAD` | 交互 pressed。 |
| 浅紫强调 | `primary-soft` | `#EEEAFE` | 选中态、短标签、弱强调、当前节点底色。 |
| 强浅紫 | `primary-soft-strong` | `#DED7F7` | `primary-soft` 不够明显时的选中 / 计数底色。 |
| 浅紫文字 | `primary-ink` | `#49399B` | 浅紫表面上的短文字与图标。 |
| 禁用紫 | `primary-disabled` | `#D7D1E4` | 仅禁用交互，不承载活动内容。 |
| 主强调反白 | `on-primary` | `#FFFFFF` | `primary` / hover / active 上的文字和图标。 |
| 主画布 | `canvas` | `#FAF9F5` | scene 连续底色、留白、默认页面地板。 |
| 弱表面 | `surface-soft` | `#F6F3EE` | 柔和分组、只读 inset、辅助信息带。 |
| 卡片表面 | `surface-card` | `#F0ECE6` | 无悬浮的强调分组、计数和色调卡片。 |
| 抬升表面 | `surface-raised` | `#FFFEFB` | 有意义的证据卡、短 callout、输入、菜单、dialog。 |
| 选中表面 | `surface-selected` | `#EEEAFE` | 选中导航或行；等同 `primary-soft`，但保留表面语义。 |
| hover 表面 | `surface-hover` | `#F5F1FB` | 中性行 / 图标控件 hover；不作为常规视频底色。 |
| 侧栏表面 | `sidebar` | `#F3F0EA` | 仅表现真实产品 UI 的侧栏；与画布有区别但不形成另一套主题。 |
| 深色表面 | `surface-dark` | `#211F26` | 代码、终端、媒体工具、局部深色 overlay；不作 page section 背景。 |
| 深色抬升 | `surface-dark-elevated` | `#2C2932` | 深色局部中的控件。 |
| 深色弱表面 | `surface-dark-soft` | `#37333E` | 深色局部的 hover / 内嵌区域。 |
| 遮罩 | `overlay` | `#1E1B24` | dialog 或截图遮罩，72% opacity；不可用作不透明正文色。 |
| 主文字 | `ink` | `#1F1D24` | 标题、主论断、重要标签、输入内容。 |
| 强正文 | `body-strong` | `#333039` | 加强正文、次级标题。 |
| 正文 | `body` | `#4D4954` | 普通说明文字。 |
| 辅助文字 | `muted` | `#716C79` | metadata、helper、非活动导航、时间戳；在画布上 4.83:1。 |
| 装饰弱文字 | `muted-soft` | `#8A8491` | 禁用标签、装饰图标、非必要 caption；不可作正文。 |
| 深色主文字 | `on-dark` | `#FAF9F5` | 深色表面的主文字 / 图标。 |
| 深色辅助文字 | `on-dark-soft` | `#B9B4C0` | 深色表面的辅助信息。 |
| 细分隔线 | `hairline` | `#E3DED8` | 默认 divider、低强调 border。 |
| 强分隔线 | `hairline-strong` | `#D4CEC7` | 输入边界、需要更清晰的分界。 |
| 焦点环 | `focus-ring` | `#7965DD` | 键盘 focus 环 / 聚焦输入边；2px 环 + 2px 画布 offset。 |
| 信息 | `info` | `#3D6FA8` | 信息 icon、文字、进度或强填充。 |
| 信息浅底 | `info-soft` | `#EAF2FB` | 信息 notice 背景。 |
| 成功 | `success` | `#397352` | 已确认、已同步、已准备、成功。 |
| 成功浅底 | `success-soft` | `#EAF5ED` | 成功 notice / status 背景。 |
| 注意 | `warning` | `#916019` | 延迟、部分完成、排队、警示。 |
| 注意浅底 | `warning-soft` | `#FBF1DC` | warning notice / status 背景。 |
| 错误 | `error` | `#AD414A` | 失败、破坏性动作、验证错误、录制状态。 |
| 错误浅底 | `error-soft` | `#FBEAEC` | error notice / status 背景。 |

### 颜色使用场景

| 场景 | 前景 | 背景 / 表面 | 规则 |
|---|---|---|---|
| Canvas / scene base | `ink` / `body` / `muted` | `canvas` | 标题与主论断用 `ink`，正文用 `body`，metadata 才用 `muted`。 |
| 证据卡 / callout | `ink` / `body` | `surface-raised` + `hairline` | 仅在信息确需独立层级时使用；不靠一层层卡片填画面。 |
| 色调分组 / 信息带 | `body-strong` / `body` | `surface-soft` / `surface-card` | 无需阴影；用间距和细线优先。 |
| 当前结论 / 当前步骤 | `primary` 或 `primary-ink` | `primary-soft` | 浅紫只包裹短信息，不做全屏紫底或第二套正文色。 |
| 深色代码 / 终端 / 媒体局部 | `on-dark` / `on-dark-soft` | `surface-dark` | 限局部；不可为视觉变化在浅色 scene 中插入深色卡。 |
| Info / success / warning / error | 对应强 token | 对应 soft token | 强 token 作为文字或 icon；状态必须带文字 / 图形，不只靠颜色。 |
| 图片 / 视频标注 | `ink` / `body` | 素材外部的浅色信息区 | tag、badge、caption、callout 不压在素材关键区域上。 |
| 字幕 | 高对比 `ink` / 深色背景时 `on-dark` | shrink-to-fit 的稳定遮罩 | 不用低对比 accent 承担字幕。 |
| 真实产品 shell / sidebar | `body` / `muted` | `canvas` / `sidebar` + `hairline` | 侧栏只比画布略暖，不应抢占内容；仅在展示真实 UI 时复刻。 |
| 导航行：inactive / hover / selected | `body` / `muted`；hover=`body-strong`；selected=`primary-ink` | 透明；hover=`surface-hover`；selected=`surface-selected` | hover 与 selected 是同一控制的离散状态，不能同时叠加。 |
| 导航计数 / resize handle | `body` 或 `primary-ink` | 中性 count=`surface-card`；注意 count=`primary-soft-strong` | resize handle 默认透明，hover 用 `primary-soft-strong`，focus 用 `focus-ring`；这些是 UI 细节，不做视频装饰。 |
| Capture composer / 附件 | `ink` / `body` | `surface-raised + hairline`；附件=`surface-soft`，选中=`primary-soft` | 只在产品 UI scene 使用；周围保持 `canvas`，不在多色底上使用半透明白卡。 |
| Primary action | `on-primary` | `primary`；hover=`primary-hover`；pressed=`primary-active` | 一个 scene 最多一个 primary action；不与大面积 semantic status 色竞争。 |
| Secondary / ghost action | secondary=`body-strong`；ghost=`muted` / `primary-ink` | secondary=`surface-raised + hairline-strong`；ghost 透明 / `surface-hover` / `primary-soft` | 用中性表面区分优先级；不要额外引入蓝、绿、红。 |
| Destructive action | `on-primary` 或 `error` | 即时破坏动作=`error`；需确认动作=中性 secondary 表面 | 红色只用于不可逆风险；不能与普通 primary button 并列作为两个同级主行动。 |
| Text input / 表单 | `ink`；placeholder=`muted`；error helper=`error` | `surface-raised + hairline-strong`；disabled=`surface-soft` | focus 只用 `focus-ring`；label 在上，placeholder 不替代 label。 |
| Content card / hover row / selected row | `body` / `ink` | card=`surface-raised + hairline`；row hover=`surface-hover`；selected=`surface-selected` | hover 只改变表面，不上浮；同一内容组优先用间距和 divider，避免连续卡片造成噪声。 |
| Status badge | local=`body/surface-card`；queued=`warning/warning-soft`；processing=`info/info-soft`；ready=`success/success-soft`；failed=`error/error-soft`；generated=`primary-ink/primary-soft` | 对应 soft surface | 每个 badge 只使用一个状态色和文字；同一行有多个状态时用中性默认 + 一个最重要状态。 |
| Inline notice / toast | 对应 `info` / `success` / `warning` / `error` 强色 | 对应 soft 色；toast 可用 `surface-raised + hairline + shadow-floating` | notice 表示需读的状态，toast 表示短暂结果；不要在同一 scene 同时铺多个不同色 notice。 |
| 深色代码 / terminal / media preview | `on-dark` / `on-dark-soft` | `surface-dark`；控件=`surface-dark-elevated`；内嵌区=`surface-dark-soft` | 仅一个局部深色锚点；紫色只用于短 path / 当前行 / marker，不把整块变成霓虹多色终端。 |
| Modal / screenshot scrim | `on-dark` / `on-dark-soft` | `overlay`，72% opacity | 仅遮罩语义；不能用作不透明正文底或普通 scene 背景。 |
| 对比图 / 数据图 / 状态图例 | `ink` / `body` / `muted` 为基础；一个 focal series 可用 `primary` | `canvas` / `surface-raised` | 只有数据本身需要时才追加一个 semantic 色；避免 purple、blue、green、amber、red 同时成为等权主系列。 |

### 色彩冲突评估与组合规则

- **基础关系：** `canvas`、三档浅表面和暖灰文字占画面绝大多数面积；`primary` 是唯一常规强调色，因此暖白与薰衣草之间稳定、低冲突。
- **状态隔离：** `info`、`success`、`warning`、`error` 都只在对应 soft 底或小型 marker 内使用。它们不与 `primary` 争夺同一元素的主强调权，能避免蓝绿黄红与紫色并列造成的杂乱。
- **单组原则：** 一个 card、callout、chart series、badge 或信息节点最多一个强 accent；允许“`primary` 表当前焦点 + 一个 semantic color 表真实状态”，但两者必须分属不同元素且有清楚标签。
- **面积控制：** 强色用于文字、细线、图标、数字、短 label 或状态 marker；大面积只使用 `canvas`、`surface-soft`、`surface-card`、`surface-raised`。这能维持轻编辑感并避免色块冲突。
- **深色局部：** `surface-dark` 与暖白画布的反差已经足够，深色 panel 内以 `on-dark` / `on-dark-soft` 为主；accent 只做一处路径、错误或当前状态，不与多个 semantic 色同屏堆叠。
- **视频适配：** 连续 scene 可以变换当前 accent 的信息角色，但相邻 scene 应保留暖白画布与文字层级；不要为了每句旁白更换整套强调色。

### 标题配色与高亮 box

- 标题、关键结论与大数字默认使用 `ink`；一个关键词、当前步骤或关键数值可使用 `primary`。
- 高亮 box 使用 `primary-soft + primary-ink`，或 `surface-raised + hairline`；必须紧贴短文本，不做大面积紫色填充。
- 重要状态可以使用 `info` / `success` / `warning` / `error`，但须与其真实语义一致。
- `muted-soft`、`primary-disabled` 不能承担标题、正文、字幕或关键数字。

### `visual_role` 色彩覆盖

| `visual_role` | 配色方式 |
|---|---|
| `title` / `product_card` / `section_divider` | `ink` 标题；可用一个 `primary` 关键词、短 eyebrow 或身份标记。 |
| `leaderboard` / `big_number` / `data_block` / `metric_strip` | 主数字 `ink` / `primary`；确认或风险数值才用 success / warning / error；普通 label 用 `body` / `muted`。 |
| `data_table` / `chart` | focal series 用 `primary`；辅助 series 用暖中性色；info / success / warning / error series 必须表达相应数据语义。 |
| `timeline` / `process_flow` / `state_machine` | 默认节点与连线用 `hairline` / `body`；当前节点用 `primary` / `primary-soft`；失败 / 等待等状态用真实 semantic token。 |
| `architecture_diagram` / `network_graph` | 中性模块用 `surface-soft` / `hairline`；关键路径用 `primary`；状态节点才用语义色。 |
| `comparison_matrix` / `pros_cons` | 中性维度用暖灰；优劣或风险使用 success / error 等真实语义，不给整列铺满 accent。 |
| `list` / `feature_grid` | item label 用 `ink` / `body-strong`；bullet / index 只在有语义时用 `primary` 或 status color。 |
| `callout` / `definition` / `qa` / `quote` | `surface-raised` 或 `primary-soft` 仅在必要时做短信息区；正文保持 `ink` / `body`。 |
| `code_block` / `terminal_block` / `file_tree` | 局部 `surface-dark`；命令、路径、版本号用 `IBMPlexMono`；错误用 `error`。 |
| `annotated_media` | 标注放在素材外部，pin / marker 可用 `primary` 或真实状态色。 |

### 对比度 guardrails

| 前景 / 背景 | 对比度 | 使用场景 |
|---|---:|---|
| `on-primary` / `primary` | 5.11:1 | 主按钮 / 主强调。 |
| `primary-ink` / `primary-soft` | 7.62:1 | 选中导航、badge、短高亮。 |
| `ink` / `canvas` | 15.83:1 | 标题、主内容。 |
| `body` / `canvas` | 8.32:1 | 正文。 |
| `muted` / `canvas` | 4.83:1 | metadata、helper。 |
| `on-dark` / `surface-dark` | 15.47:1 | 深色局部主文字。 |
| `on-dark-soft` / `surface-dark` | 8.03:1 | 深色局部辅助文字。 |
| `info` / `info-soft` | 4.60:1 | 信息 notice。 |
| `success` / `success-soft` | 5.01:1 | 成功 notice。 |
| `warning` / `warning-soft` | 4.81:1 | warning notice。 |
| `error` / `error-soft` | 4.98:1 | error notice。 |

- 正文、表单和字幕目标至少 4.5:1；大号文字、icon、chart stroke、粗 marker 至少 3:1。
- `muted-soft` 与 disabled pairing 仅作装饰 / 禁用态，不能承载正文。
- 状态不能仅用颜色表达；必须有文字、图标、符号或结构辅助。

## 排版

| 用途 | 字体 | 字重 | 语义 |
|---|---|---:|---|
| 中文 / 通用 display | `NotoSansSC` | 600 | 罕用的大主标题或开场结论。 |
| 中文主标题 | `NotoSansSC` | 600 | 对应原 `heading-lg` 的层级。 |
| 中文 section 标题 | `NotoSansSC` | 600 | 对应原 `heading-md` / `heading-sm`。 |
| 中文正文 / 屏幕文字 | `NotoSansSC` | 400 / 500 | 清晰、安静、有编辑感。 |
| 中文字幕 | `NotoSansSC` | 500 | 优先稳定可读。 |
| 数字、代码、ID、路径、来源 | `IBMPlexMono` | 400 / 600 | 对应原 `code`、技术 metadata 与强调数字。 |

原始界面 token 的层级仍然保留：`display` 32px/600、`heading-lg` 24px/600、`heading-md` 20px/600、`heading-sm` 16px/600、`body` 14px/400、`body-compact` 13px/400、`label` 13px/500、`caption` 12px/400、`button` 14px/600、`code` 13px/400。视频实际字号以本文件下方的视频尺寸与 `composition-rules.md` 的下限为准。

- 只加载 `scripts/fonts-download.sh <target_dir> default` 预置的本地 WOFF2；不得依赖系统字体匹配。
- 中文标题、正文、屏幕文字与字幕固定使用 `NotoSansSC`；禁止宋体、衬线中文 fallback、手写字体或其他未预置字体。
- 保持自然句式；不要把全大写、高 letter-spacing 小字作为常规装饰。
- 标题使用 600，正文使用 400/500；避免 700+ 的沉重显示字体。正文保持至少 1.55 行高。
- `IBMPlexMono` 只用于标识符、日志、路径、代码、数字和紧凑 source metadata，不用它排整段中文正文。

## 视频尺寸（覆盖网页常规尺寸）

| 元素 | 1920×1080 | 1080×1440 | 1080×1920 |
|---|---|---|---|
| Hero 标题 | 88-136px | 72-116px | 76-124px |
| Section 标题 | 54-82px | 46-70px | 50-76px |
| 正文 / callout | 30-48px | 28-42px | 28-44px |
| 数据 label / source | 22-32px | 22-30px | 22-32px |
| 代码 / 等宽 | 22-34px | 22-30px | 22-32px |
| 字幕 | 35px | 35px | 35px |
| `.scene` padding | 90px 140px | 90px 80px | 90px 70px |

- 原始 4px spacing rhythm 全部保留：`xxs` 4px、`xs` 8px、`sm` 12px、`md` 16px、`lg` 24px、`xl` 32px、`xxl` 48px。
- 原始 desktop shell 数值只作为真实产品 UI 的参考：sidebar 默认 240px（200-400px）、正文最大可读宽度 896px、desktop gutter 32px、compact gutter 20px、persistent title bar 32px。产品 navigation / 标准 control 高 40px；触摸目标至少 40px，优先 44px。视频不可机械复刻这些尺寸。
- 原始响应式语义保留：Under 720px 收叠 sidebar 为 overlay / icon rail、使用 20px gutter 并堆叠 action row；720-1024px 维持最小 sidebar 与 24px gutter；Over 1024px 使用保存的 sidebar 宽度与 32px gutter。capture composer 宽度流动、上限约 896px；button group 可换行但单个 button label 不换行；form grid 在 Under 720px 时改单列；toast 保持 16px viewport clearance。视频的横竖屏 routing 仍优先服从 `composition-rules.md`。
- 保留有意且对称的暖白呼吸空间，但不得以空白、透明占位或延迟信息出现规避内容覆盖与 peak-state 审计。

## 形状风格

- 紧凑、平面、安静的编辑式 panel；层级由表面色、hairline 和间距形成，不靠玻璃、厚投影或 glow。
- 原始圆角 token：`xs` 4px（微型 progress / inset）、`sm` 6px（紧凑 badge / menu）、`control` 8px（button、input、tab、nav）、`card` 12px（card、menu、dialog）、`feature` 16px（重要容器）、`pill` 9999px（badge、status chip、圆形 icon button）。不可混用任意圆角值。
- 原始 elevation 语义：Floor=`canvas` 无 border / shadow；Grouped=色调表面 + 可选 `hairline`；Raised=`surface-raised + hairline`；Floating=`surface-raised + hairline + tinted shadow`；Overlay=`overlay` 72%。
- 允许的 shadow：`0 1px 2px rgb(31 29 36 / 0.05)`（raised）；floating 为 `0 12px 32px rgb(64 52 86 / 0.12), 0 2px 8px rgb(64 52 86 / 0.08)`。focus 用 ring，不用 glow。
- 图片 / 视频素材默认无可见 card frame、border、outline、padding、shadow、glow 或露底；只有真实产品截图内原有的 UI 框不受此限制。

### 组件与状态语义

- **`app-shell` / sidebar：** shell 用 `canvas`，sidebar 用 `sidebar + hairline`；inactive nav 用 `body` / `muted`，hover 用 `surface-hover + body-strong`，`navigation-item-active` 用 `surface-selected + primary-ink`；中性 count 用 `surface-card`，注意 count 用 `primary-soft-strong + primary-ink`。resize handle 默认透明，hover 用 `primary-soft-strong`，键盘 focus 用 `focus-ring`。
- **`capture-composer`：** `surface-raised + hairline + 16px + shadow-raised`；周围保持 `canvas`；附件用 `surface-soft`，选中附件用 `primary-soft`；不可在多色背景上放半透明白卡。
- **`button-primary`：** primary/on-primary；hover primary-hover；pressed primary-active；focus 为 2px `focus-ring` + 2px canvas offset；disabled 为 primary-disabled/muted，无 shadow。
- **`button-secondary` / ghost：** secondary=`surface-raised + body-strong + hairline-strong`，hover=`surface-hover + ink + primary-soft-strong`，pressed=`primary-soft + primary-ink`；ghost 默认透明/muted，hover=`surface-hover + primary-ink`，active=`primary-soft + primary-ink`。破坏性即时动作才用 error + 白字；需确认的动作用 secondary + error 字。
- **`text-input`：** `surface-raised`、`ink`、`hairline-strong`；placeholder=`muted`；hover border=`primary-soft-strong`；focus=`focus-ring`；error=`error`；disabled=`surface-soft`。label 在 input 上方，placeholder 不代替 label。
- **`content-card` / rows：** 默认 card=`surface-raised + hairline + 12px`；色调组用 `surface-soft` / `surface-card` 无 shadow；hover row 只变 `surface-hover`，不整体上浮；selected row 用 `surface-selected` 加 visible `primary` indicator 或 `primary-ink` icon。信息本已属于同一区域时，优先间距而不是卡片。
- **`badge-accent` / status badge：** local only=`surface-card/body`；queued/partial=`warning-soft/warning`；syncing/processing=`info-soft/info`；ready/complete=`success-soft/success`；failed=`error-soft/error`；selected/generated=`primary-soft/primary-ink`。每个 status 必须带文字。
- **`notice-error` / notices / toasts：** info、success、warning、error 各用对应 soft/strong pair；toast 容器为 `surface-raised + hairline + shadow-floating`；短暂结果用 toast，需要用户处理的错误用 inline notice。
- **Dark / overlay：** 深色只用于截图选择、媒体 preview、modal scrim；主文字用 `on-dark`，辅助用 `on-dark-soft`；禁止为视觉变化孤立插入深色 card。

## 图标

- 使用低调的线性 icon、短 label、细分隔线、节点、箭头与状态 marker；颜色使用 `body`、`primary-ink` 或真实 semantic token。
- icon 与文字基线对齐；icon-only 控件在真实 UI 中必须具备可访问名称。
- 不使用 emoji、3D icon、贴纸、彩色 icon 拼盘、装饰性 logo 墙、手写 icon 或发光 icon。
- 状态 icon 不可单独表达含义，必须和文字 / 数字 / 结构一起出现。

## 动效

- 原始产品交互语义：颜色过渡 120ms ease-out；进出 160-200ms ease-out；pressed 可下移 1px 或 scale 0.98；只 animate opacity / transform；不 animate background blobs、gradient 或装饰 particle；Focus visibility 必须存在且不依赖动画。
- 视频中的这些时长只表达“克制、轻编辑”的角色，不取代叙事 timing。所有 render-critical 动效必须 deterministic、seek-safe，并服从 R18 / R19。
- 文本与信息单元按 transcript 句子 / 语义 beat 出现；禁止 scene 开头用统一 stagger 把所有叙事文本铺开。靠近 scene 结束、可见时间不足的文本可在同一语义段内适度提前。
- 进入动效以短促 opacity + transform 为主；不要使用 bouncy、背景 blob、渐变、粒子、外发光、idle decorative drift、扫描线、sweep 或无意义进度条。
- 素材保持内容驱动的轻微运动；普通 scene 有明确转场；`media_continuation` 的主素材稳定，只更新文字、局部强调或信息区。

## 不要做

- ❌ 不要使用多色 bokeh、mesh background、紫色 gradient、glassmorphism、半透明白卡、outer glow、radial spotlight、ambient orb 或 neon halo。
- ❌ 不要混用 slate / stone 等额外中性色阶；所有颜色必须回到本文件 token。
- ❌ 不要把浅紫 `primary-soft` 配白字，也不要把 `primary-disabled` / `muted-soft` 用于正文、标题或字幕。
- ❌ 不要把状态色用于无关 icon、分类装饰或随机换色；同一元素不叠加多种 accent。
- ❌ 不要让每个内容块都成为 card；能用间距或 divider 解决时不加卡。
- ❌ 不要为视觉多样性在浅色 scene 中插入深色 section；深色仅用于真实代码、终端、媒体局部或 overlay。
- ❌ 不要使用宋体、衬线中文 fallback、系统字体匹配、未预置字体、手写字体或过重 display 字体。
- ❌ 不要压缩文字字号、降低对比度、延后 text beat 或用隐藏元素掩盖布局问题。
- ❌ 不要在图片 / 视频关键区域上压 caption、tag、badge、callout、label 或整行遮罩；说明信息放在素材外部。
- ❌ 不要用 hover、pressed、focus 等产品交互状态替代视频叙事动效；不要让背景装饰自行呼吸或持续运动。

## 实现与可访问性

- 实现时优先使用语义 token / CSS custom properties，不直接散落 raw Tailwind color；先统一画布与 shared control，再处理页面特定部分。
- 现有 UI 映射保持：多色 `capture-bg`、`from-purple-50 via-white to-slate-50`、`bg-slate-50` → `canvas`；白色 card → `surface-raised`；stone sidebar / hover → `sidebar` / `surface-hover`；slate/stone border → `hairline` / `hairline-strong`；purple 600 / hover 700 / purple 50-200 / purple 700-800 / focus ring → 相应 primary token；slate/stone text 900/700/600/500/400 → `ink` / `body-strong` / `body` / `muted` / `muted-soft`；蓝绿黄红 status utilities → 相应 semantic strong / soft token。
- 真实交互 UI 必须有 keyboard focus、逻辑 heading order、可见 label；error 靠近受影响 control，新出现时使用 `role="alert"`。普通 body / form 文字至少 4.5:1；toast 保持 16px viewport clearance，button label 不换行。
- 来源：Frag Note Design System，受 Claude warm-canvas 设计参考的结构与分析启发；保留的高层原则是暖白画布、克制表面层级、稀疏 accent 与色彩驱动的 depth。
