# 委派约定（统一）

Phase 5（素材 catalog）与 Phase 6（脚本与场景规划）这类 context 消耗大的步骤，委派给 coding agent 完成。两个委派步骤共用本约定。

## 委派给谁

- 默认 coding agent 是 **claude-code**；用户在对话中点名其他 agent 时覆盖（记入 `inputs.json` 的 `coding_agent` 字段）。
- 主 agent 自己承担委派职责，按下面的方式派发；**不要**写脚本去 shell 调用 coding agent——委派是主 agent（一个 LLM）的行为，不是仓库脚本的行为。

## 怎么派发

- **主 agent 运行在 Claude Code 里**：用 Claude Code 原生的 sub-agent / 委派工具（如 `subagent` / Task 工具）派发。
- **主 agent 运行在其他客户端里**：在工作区里执行 headless 的 claude CLI。已核实的可用 flag（`claude --help`）：
  - `-p` / `--print`：非交互模式，执行 prompt 后打印结果退出；
  - `--add-dir <dir>`：额外授予工具访问的目录（工作区在仓库外时需要）；
  - `--model <model>`：指定模型；
  - `--permission-mode <mode>`：权限模式（headless 下通常配合环境预先配置）。
  - 命令形态：`claude -p "<prompt>" --add-dir <work_dir>`。具体 flag 以本机 `claude --help` 为准。
- **委派 prompt 只有一句话**：让被委派的 agent 去读对应的 handoff 文件。例如：

  ```text
  读取 <work_dir>/<topic_name>/script-handoff.md 并按它执行；完成后报告产物路径。
  ```

  被委派的 agent 自己从磁盘读 handoff 与 Required References 里列出的文件；主 agent 不在 prompt 里复述指令内容。

## 指令叠加顺序

委派时，被委派的 agent 按以下顺序读取指令，**后面的补充前面的**，冲突时以后者为准：

1. **委派包的基础指令**（`references/delegation/<step>/base-instructions.md`）；
2. **所选模板的指令**：script 步骤读 `modules/templates/<template>/narration.md`（旁白要求）；composition 步骤读模板的组装说明。未选模板则跳过；
3. **工作区里的项目指令文件**，每步一份：script 步骤读 `<work_dir>/<topic_name>/narration-instructions.md`，composition 步骤读 `<work_dir>/<topic_name>/composition-instructions.md`。旧项目的 `style-prompt.md` 视为 composition 项目指令的一部分，由 composition 步骤读取；
4. **用户在对话中提出的要求**，由主 agent 追加写入第 3 项对应的项目指令文件（`narration-instructions.md` / `composition-instructions.md`），再委派。

项目指令文件都是可选的：不存在就跳过，但 handoff 的 Additional Instructions 一节始终保留，写 None 或实际文件列表。

## handoff 模板

每个委派步骤的 handoff 固定包含五个小节，见 `references/delegation/<step>/handoff-template.md`：

1. Coding Agent
2. Inputs
3. Outputs
4. Required References
5. Additional Instructions

主 agent 按模板填出 `<work_dir>/<topic_name>/<step>-handoff.md`，派发的 prompt 只有上面那一句。
