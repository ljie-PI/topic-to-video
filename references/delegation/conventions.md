# 委派约定（统一）

Phase 5（素材 catalog）、Phase 6（脚本与场景规划）、Phase 8（composition）与 Phase 11（cover）委派给 coding agent 完成，共用本约定。四个委派包分别是 `references/delegation/catalog/`、`references/delegation/script/`、`references/delegation/composition/`、`references/delegation/cover/`；handoff 都由 `prepare-handoff.py` 生成。

## 委派给谁

- 默认 coding agent 是 **pi-coding-agent**（命令 `pi`）；用户指定全局 agent 时，记入 `inputs.json` 的 `coding_agent` 字段。
- **用户指定某阶段的 agent / model 时必须严格遵循。** 阶段级要求记入可选的 `inputs.json.delegation`，键为 `catalog` / `script` / `composition` / `cover`，值为包含 `agent` 和 / 或 `model` 的对象，例如 `"delegation": {"catalog": {"agent": "pi-coding-agent", "model": "<provider>/<model-id>"}}`。只覆盖指定字段：未指定 agent 时继承 `coding_agent`，未指定 model 时使用目标 agent 自身的模型配置。素材理解 / 素材匹配指 Phase 5 时记为 `catalog`，场景与素材匹配指 Phase 6 时记为 `script`；范围不清楚先问用户。
- `prepare-handoff.py` 会把有效 agent 写入 handoff，并返回 `coding_agent` / `coding_model` / `requested_model`，供主 agent 派发时使用。用户请求了模型时，`coding_model` 是经目标 CLI 解析的真实原生标识，`requested_model` 是原始请求；未请求模型时二者都是 `null`，使用目标 agent 自身配置。不能仅把 model 写进 prompt，实际调用也必须选中它。指定 agent 不可用、或候选模型都无法满足本阶段能力时，向用户说明并确认，不得自动换 agent / model 或悄悄用另一个 VLM。
- 主 agent 自己承担委派职责，按下面的方式派发；**不要**写脚本去 shell 调用 coding agent——委派是主 agent（一个 LLM）的行为，不是仓库脚本的行为。

## 怎么派发

1. **先确定目标**：按 `inputs.json.delegation` 的当前阶段要求与全局 `coding_agent` 解析目标（默认 `pi-coding-agent`），以 `prepare-handoff.py` 返回的 `coding_agent` / `coding_model` 实际派发，不得仅把模型名写进 prompt。
2. **再选派发入口**：
   - **当前客户端的原生 sub-agent 工具能直达该目标 agent 并选中指定模型时**：用原生委派工具，仅传简短派发指令与 handoff 路径。
   - **否则调用该目标自身的非交互 CLI**（原生工具若只能跑自身后端，不得替代 `pi` 或用户点名的其他 agent）。Pi 用 `cd <ws> && pi --no-session -p -- "<dispatch_prompt>"`；其他 agent 按其 `--help` 调用；目标未知或不可用时明确报告并询问用户，禁静默换 agent。

Pi 已核实的 flag（`pi --help`）：

- `-p` / `--print`：非交互模式；`--no-session`：临时无状态会话；
- `--`：后续全部作为 message，防 `-` 开头被解析为参数；
- `--model <provider/model-id>`：指定解析后的完整原生模型标识（如 `cd <ws> && pi --no-session --model "<coding_model>" -p -- "<dispatch_prompt>"`；未请求时省略）；
- `--list-models [search]`：列出本机可用 provider / model（含 context、images 列），用于模型解析；
- `--no-skills, -ns` / `--skill <path>`：禁用自动发现 / 显式加载指定 skill（可多次使用）。
- **仅 composition 派发限制加载的 skill**：只允许加载 `hyperframes` 与 `hyperframes-cli`：

  ```text
  cd <ws> && pi --no-session --no-skills --skill <hyperframes skill 实际路径> --skill <hyperframes-cli skill 实际路径> [--model "<coding_model>"] -p -- "<dispatch_prompt>"
  ```

  派发前先核对两个 skill 路径存在，缺失则报告，禁静默退回自动发现。catalog / script / cover 不加此限制，也不改仓库外安装或全局配置。
- 启动目录与访问权限：在 `<ws>` 启动即可读写工作区（handoff 与脚本均用绝对路径）；`pi` 无单独目录授权 flag，额外授权按 `pi --help` 处理并告知用户。
- **派发粒度、并行与 `413` 兜底**：
  - 单批步骤（`catalog`、`script`）原样派发 `source .venv/bin/activate && python3 scripts/prepare-handoff.py <ws> <step>` 输出的 `dispatch_prompt`；
  - 多批步骤（`composition`、`cover`）在 `dispatch_prompt` 后限定本批职责与文件边界（不复述指令或产物正文），独立小批（不同 `scene_id` 子合成、不同尺寸封面 HTML）默认 `--no-session` 并行派发；shell 参数去反引号、每批 `≤ 1KB`，要求子会话仅回复 `done` 与路径清单；
  - 给子会话看的参考图/帧须缩至宽 `≤ 640px`（禁喂多张 `1080p` 全帧）；确定性检查与渲染收归主会话执行，子会话写盘即止；遇 `413` 或“退出码 `0` 但零输出、零落盘”直接拆小批重派，禁原样重试。
  - 子 agent 从磁盘读 handoff、Inputs 与 Required References；「仅供工具读取」的文件只传命令，仅诊断报错时读局部片段。

## 模型查询与近似选择

用户在 `inputs.json.delegation.<step>.model` 请求模型时，保留原始输入不变，主 agent 在**运行 `prepare-handoff.py` 之前**按统一规则解析（catalog / script / composition / cover 通用）：

1. 用目标 CLI 的 `--help` 核对本机命令与模型查询入口，不用主 agent 自身的模型列表代替目标 CLI。
2. 查询目标 CLI 候选：Pi 先跑 `pi --list-models "<请求>"`，为空再跑 `pi --list-models` 取全表。
3. **精确匹配优先**：候选表存在一致的原生 `provider/model-id` 时直接采用。
4. 无精确匹配时，在候选 chat 模型中选同系列 / 版本 / 变体最接近且满足阶段能力的模型（catalog、cover 等含看图验收的任务要求支持图像输入，如 Pi `images` 列为 `yes`）。用户指定了 provider 时仅在该 provider 内选；未指定时优先选已有可用认证的候选。
5. 有明确近似候选时直接采用并简短告知用户「请求 → 实际模型」，无需停下等待确认。
6. **遇以下任一情况明确阻塞并请用户决定**：目标 CLI 不可用或无法列出模型；无满足能力要求的可用模型；需跨出用户明确指定的 provider；多个候选同样接近无法区分。**禁编造模型 id、禁换 coding agent、禁输出凭据 / API key、禁自动安装模型或修改全局认证。**

解析后传 `--resolved-model "<实际原生标识>"` 运行 `prepare-handoff.py`（未解析前禁止生成 handoff；无模型请求时不传该参数）。handoff 与返回 JSON 同时记录 `requested_model` 与实际 `coding_model`，派发时传实际 `coding_model`。

## 指令叠加顺序

子 agent 按以下顺序读取指令，**后者补充并覆盖前者**：

1. **委派包基础指令**（`references/delegation/<step>/base-instructions.md`）；
2. **模板组装说明**（仅 composition 按场景采用某模板时读取 `modules/templates/<template>/<template>.md`，不采用则跳过，不写回 `inputs.json`）；
3. **用户阶段级要求**：旁白要求记 `inputs.json.narration_requests`（script 读），画面要求记 `inputs.json.composition_requests`（composition 读），封面要求记 `inputs.json.cover_requests`（cover 读），素材要求记可选的 `<work_dir>/<topic_name>/catalog-instructions.md`（catalog 读）；
4. 主 agent 先写妥上述要求再运行 `prepare-handoff.py`；生成 handoff 后若有新增要求，重跑一次 `prepare-handoff.py`（幂等，不覆盖已物化副本）再派发。无额外要求时 Additional Instructions 写 `None`（小节保留）。

## handoff 模板

每个委派步骤的 handoff 固定包含五节（见 `references/delegation/<step>/handoff-template.md`）：`Coding Agent`、`Inputs`、`Outputs`、`Required References`、`Additional Instructions`。

主 agent 不手写 handoff，统一由 `scripts/prepare-handoff.py <ws> <step> [--refresh] [--resolved-model <实际标识>]` 生成：脚本将本约定与 `references/delegation/<step>/` 物化到 `<ws>/references/delegation/`（composition 另将 `modules/` 物化到 `<ws>/modules/`；不预选 design、不预装字体），再渲染 `<ws>/<step>-handoff.md`。已存在的工作区副本默认不覆盖，仓库规则更新后需加 `--refresh` 刷新（刷新前先确认副本未被本地改动）。

handoff 内全用绝对路径，skill 脚本写作 `source <skill_root>/.venv/bin/activate && python3 <skill_root>/scripts/<x>.py ...`。文档内相对路径基准：`scripts/` 与 `references/phases/` 相对 skill 根；`references/delegation/` 相对工作区副本；`modules/` 在 composition 相对工作区副本，在 script 相对 skill 根。
