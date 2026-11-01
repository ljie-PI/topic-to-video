# 委派约定（统一）

Phase 5（素材 catalog）、Phase 6（脚本与场景规划）与 Phase 8（composition）委派给 coding agent 完成，共用本约定。三个委派包分别是 `references/delegation/catalog/`、`references/delegation/script/`、`references/delegation/composition/`；handoff 都由 `prepare-handoff.py` 生成。

## 委派给谁

- 默认 coding agent 是 **pi-coding-agent**，可执行命令为 `pi`；用户在对话中点名其他 agent 时覆盖（记入 `inputs.json` 的 `coding_agent` 字段）。
- 主 agent 自己承担委派职责，按下面的方式派发；**不要**写脚本去 shell 调用 coding agent——委派是主 agent（一个 LLM）的行为，不是仓库脚本的行为。

## 怎么派发

先解析目标，再选手段：两件事不能弄反。

1. **先确定目标**：读 `inputs.json` 的 `coding_agent`（缺省 `pi-coding-agent`）。用户在对话里点名其他 agent 时以 `inputs.json` 为准。
2. **再判断可用工具能不能派发这个目标**：
   - **能明确派发到该目标时**用当前客户端的原生 sub-agent / 委派工具，被委派的 agent 同样只拿到那一句 prompt 与 handoff 路径。
   - **否则用该目标自己的非交互入口**。Pi 的形态是 `cd <ws> && pi -p -- "<dispatch_prompt>"`。

**“有原生 sub-agent 工具”不等于“能派发 Pi”。** 原生工具只能跑它自己那个后端时，它无法代替 `pi`；这时要走 Pi 的入口，而不是用原生工具派发到另一个 agent。

用户点名了其他 agent 时，用那个目标自己的入口（具体 flag 以它的 `--help` 为准），不要仍落到 `pi`。目标未知或该工具不可用时**明确报告**并停下来问用户，不要静默换成别的 agent。

Pi 已核实的 flag（`pi --help`）：

- `-p` / `--print`：非交互模式，处理完 prompt 后退出；
- `--`：后面全部当作 message，prompt 以 `-` 开头也不会被当成参数；
- `--model <pattern>`：指定模型（可选）。
- 命令形态：`cd <ws> && pi -p -- "<dispatch_prompt>"`。在当前目录启动，被委派的 agent 就能直接读写工作区；handoff 与 Required References 里都是绝对路径，skill 侧脚本也用绝对路径调用，不依赖 cwd。
- `pi --help` 里没有单独授予目录访问的 flag，因此不要照搬其他 CLI 的参数；确实需要额外授权时按 `pi --help` 与本地配置处理，并把差异告诉用户。
- **委派 prompt 只有一句话**，由 `prepare-handoff.py` 生成：运行 `source .venv/bin/activate && python3 scripts/prepare-handoff.py <ws> <step>`，把输出 JSON 里的 `dispatch_prompt` 原样派发。例如：

  ```text
  读取 <ws>/script-handoff.md 并按它执行；完成后报告产物路径。
  ```

  被委派的 agent 自己从磁盘读 handoff 与 Required References 里列出的文件；主 agent 不在 prompt 里复述指令内容。

## 指令叠加顺序

委派时，被委派的 agent 按以下顺序读取指令，**后面的补充前面的**，冲突时以后者为准：

1. **委派包的基础指令**（`references/delegation/<step>/base-instructions.md`）；
2. **模板的组装说明**（仅 composition 步骤）：`modules/templates/<template>/<template>.md`。选哪个模板由该步骤的 agent 在开始工作时决定并写回 `inputs.json`，选定后才读它；不选模板则跳过。其他步骤不读它，也不为旁白或场景规划选模板；
3. **用户在对话中提出的要求**，按阶段分开记在 `inputs.json`：旁白要求写进 `narration_requests`（script 步骤读），画面要求写进 `composition_requests`（composition 步骤读）。catalog 步骤不读要求；
4. 这些要求由主 agent 在对应阶段整理后写入 `inputs.json`，再运行 `prepare-handoff.py`：Additional Instructions 在生成 handoff 时计算一次，之后才写的要求不会出现在已生成的 handoff 里——这时重新运行一次 `prepare-handoff.py`（幂等；已物化的副本不会被覆盖）再派发。

要求列表都是可选的：没有就写 `None`，但 handoff 的 Additional Instructions 一节始终保留。

## handoff 模板

每个委派步骤的 handoff 固定包含五个小节，见 `references/delegation/<step>/handoff-template.md`：

1. Coding Agent
2. Inputs
3. Outputs
4. Required References
5. Additional Instructions

handoff 由 `scripts/prepare-handoff.py <ws> <step> [--refresh]` 生成，主 agent 不手写：脚本把本约定和 `references/delegation/<step>/` 拷进 `<ws>/references/delegation/`（composition 另外把 `modules/`（不含 `examples/`）拷进 `<ws>/modules/`，并按所选 design 预置字体），再按模板填出 `<ws>/<step>-handoff.md`。已存在的副本不覆盖，`--refresh` 才覆盖：委派包里的规则更新后，已有工作区要显式 refresh 才会读到新规则（先确认那份副本没有被本地改过）。派发的 prompt 只有上面那一句。

handoff 里的路径全是绝对路径，命令里的 skill 脚本写成 `source <skill_root>/.venv/bin/activate && python3 <skill_root>/scripts/<x>.py ...`，不依赖当前目录。委派包文档里的相对路径：`scripts/` 与 `references/phases/` 相对 skill 根目录；`references/delegation/` 相对工作区（那里有物化的副本）；`modules/` 在 composition 步骤相对工作区副本，在 script 步骤相对 skill 根目录（script 与 catalog 步骤都不拷 modules）。
