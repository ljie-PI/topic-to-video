# 委派约定（统一）

Phase 5（素材 catalog）、Phase 6（脚本与场景规划）与 Phase 8（composition）委派给 coding agent 完成，共用本约定。三个委派包分别是 `references/delegation/catalog/`、`references/delegation/script/`、`references/delegation/composition/`；handoff 都由 `prepare-handoff.py` 生成。

## 委派给谁

- 默认 coding agent 是 **pi-coding-agent**（命令 `pi`）；用户指定全局 agent 时，记入 `inputs.json` 的 `coding_agent` 字段。
- **用户指定某阶段的 agent / model 时必须严格遵循。** 阶段级要求记入可选的 `inputs.json.delegation`，键为 `catalog` / `script` / `composition`，值为包含 `agent` 和 / 或 `model` 的对象，例如 `"delegation": {"catalog": {"agent": "pi-coding-agent", "model": "<provider>/<model-id>"}}`。只覆盖指定字段：未指定 agent 时继承 `coding_agent`，未指定 model 时使用目标 agent 自身的模型配置。素材理解 / 素材匹配指 Phase 5 时记为 `catalog`，场景与素材匹配指 Phase 6 时记为 `script`；范围不清楚先问用户。
- `prepare-handoff.py` 会把有效 agent / model 写入 handoff，并返回 `coding_agent` / `coding_model`，供主 agent 派发时使用；模型未指定时 `coding_model` 为 `null`。不能仅把 model 写进 prompt，实际调用也必须选中它。指定 agent 不可用、模型标识不明确或不支持看图时，向用户说明并确认，不得自动换 agent / model 或悄悄用另一个 VLM。
- 主 agent 自己承担委派职责，按下面的方式派发；**不要**写脚本去 shell 调用 coding agent——委派是主 agent（一个 LLM）的行为，不是仓库脚本的行为。

## 怎么派发

先按本阶段有效的目标 agent 选择派发方式，**不是按主 agent 所在客户端决定目标**。

- **目标是 pi-coding-agent（默认）**：由主 agent 在工作区执行 headless 的 `pi`。已用本机 `pi --help` 核实：
  - `-p` / `--print`：非交互模式，执行 prompt 后打印结果退出；
  - `--model <provider/model-id>`：选择模型；也可用 `--provider <provider> --model <model-id>` 精确指定；
  - 未指定 model：`cd "<ws>" && pi -p "<dispatch_prompt>"`；
  - 指定了 model：`cd "<ws>" && pi --model "<coding_model>" -p "<dispatch_prompt>"`，用返回的模型标识，不用模糊简称猜模型。
  - `pi` 使用当前目录作为项目工作区。handoff 的输入路径都是绝对路径；handoff 里的命令（`source <skill_root>/.venv/bin/activate && python3 <skill_root>/scripts/...`）指向 skill 根目录。派发前确认目标 agent 能读工作区和 skill 根目录，凭据通过目标 agent 支持的登录 / 环境变量提供，不写进 handoff。具体 flag 以本机 `pi --help` 为准，CLI 说明见 https://pi.dev/docs/latest/cli 。
- **用户明确指定其他 agent**：先核实该 agent 的原生委派工具或 headless CLI 与模型选择参数，再按用户指定的 agent / model 派发。本约定不预设其他 agent 的命令或参数，也不因主 agent 所在客户端切换目标。指定目标不可用时先说明并确认，不能用默认 agent 替代。
- **委派 prompt 只有一句话**，由 `prepare-handoff.py` 生成：运行 `source .venv/bin/activate && python3 scripts/prepare-handoff.py <ws> <step>`，把输出 JSON 里的 `dispatch_prompt` 原样派发。例如：

  ```text
  读取 <ws>/script-handoff.md 并按它执行；完成后报告产物路径。
  ```

  被委派的 agent 自己从磁盘读 handoff 与 Required References 里列出的文件；主 agent 不在 prompt 里复述指令内容。

## 指令叠加顺序

委派时，被委派的 agent 按以下顺序读取指令，**后面的补充前面的**，冲突时以后者为准：

1. **委派包的基础指令**（`references/delegation/<step>/base-instructions.md`）；
2. **所选模板的指令**：script 步骤读 `modules/templates/<template>/narration.md`（旁白要求）；composition 步骤读模板的组装说明。未选模板则跳过；
3. **工作区里的项目指令文件**：script 步骤读 `<work_dir>/<topic_name>/narration-instructions.md`，composition 步骤读 `<work_dir>/<topic_name>/composition-instructions.md`。旧项目的 `style-prompt.md` 视为 composition 项目指令的一部分，由 composition 步骤读取；catalog 步骤读 `<work_dir>/<topic_name>/catalog-instructions.md`（素材要求与用户原话，如有）；
4. **用户在对话中提出的要求**，由主 agent 追加写入第 3 项对应的项目指令文件（`catalog-instructions.md` / `narration-instructions.md` / `composition-instructions.md`），再委派。agent / model 的选择另按「委派给谁」记入 `inputs.json`。**追加必须在运行 `prepare-handoff.py` 之前**：Additional Instructions 在生成 handoff 时计算一次，之后才写的指令不会出现在已生成的 handoff 里——这时重新运行一次 `prepare-handoff.py`（幂等；已物化的副本不会被覆盖）再派发。

项目指令文件都是可选的：不存在就跳过，但 handoff 的 Additional Instructions 一节始终保留，写 None 或实际文件列表。

## handoff 模板

每个委派步骤的 handoff 固定包含五个小节，见 `references/delegation/<step>/handoff-template.md`：

1. Coding Agent
2. Inputs
3. Outputs
4. Required References
5. Additional Instructions

handoff 由 `scripts/prepare-handoff.py <ws> <step> [--refresh]` 生成，主 agent 不手写：脚本把本约定和 `references/delegation/<step>/` 拷进 `<ws>/references/delegation/`（composition 另外把 `modules/`（不含 `examples/`）拷进 `<ws>/modules/`，并按所选 design 预置字体），再按模板填出 `<ws>/<step>-handoff.md`。已存在的副本不覆盖，`--refresh` 才覆盖。派发的 prompt 只有上面那一句。

handoff 里的路径全是绝对路径，命令里的 skill 脚本写成 `source <skill_root>/.venv/bin/activate && python3 <skill_root>/scripts/<x>.py ...`，不依赖当前目录。委派包文档里的相对路径：`scripts/` 与 `references/phases/` 相对 skill 根目录；`references/delegation/` 相对工作区（那里有物化的副本）；`modules/` 在 composition 步骤相对工作区副本，在 script 步骤相对 skill 根目录（script 与 catalog 步骤都不拷 modules）。
