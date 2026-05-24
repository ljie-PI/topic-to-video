### Phase 8 — 委派 HyperFrames Composition + Render

从这一步开始，composition 由一个使用 `hyperframes` 与 `hyperframes-cli` skills 的 coding sub-agent 拥有。`topic-to-video` 主 agent 只负责准备上游资源、写一份精简的 handoff brief、调用 sub-agent，并对返回的 MP4 做 sanity check。

HyperFrames sub-agent 拥有以下工作：
- 基于 `narration.txt` 和 `transcribe/transcript.json` 切分 scene
- 可选的 scene 时间轴文件生成
- 基于 `material-catalog.json` 完成 material-to-scene 映射
- 视觉信息设计、布局、排版、动画与转场
- `composition/index.html` 和 `composition/DESIGN.md`
- `hyperframes lint`、`hyperframes inspect`，以及渲染迭代

#### 8.1 — 写 `composition-brief.md`

从 `references/composition-brief-template.md` 出发，写出 `{work_dir}/{topic_name}/composition-brief.md`，填入项目 metadata、输入路径，以及来自 Phase 1 的 style hint。 brief 要简短。

#### 8.2 — 调用一个 coding sub-agent

优先使用当前客户端 / runtime 原生的 sub-agent 或委派工具。prompt 要简短，且应让 sub-agent 自己从磁盘读 brief 文件，而不是把整份 brief 拼进 shell 命令里。

Prompt 示例：

```text
Read composition-brief.md in the current workspace and produce the deliverables.
Use the hyperframes and hyperframes-cli skills. You own scene segmentation,
material mapping, composition design, animation, lint/inspect fixes, and final
rendering. Iterate until composition/renders/final.mp4 exists and HyperFrames
lint/inspect have no errors. Render with `--workers 1` to avoid
odd-height frame issues on this machine.
```

如果环境里没有原生 sub-agent 工具，仅当 CLI fallback 能把上面那段 prompt 原样传过去、并让 coding sub-agent 自己去读 `composition-brief.md` 时，才可以接受。

**不要**在主 agent 的会话里驱动 composition。

#### 8.3 — sanity-check 结果

sub-agent 返回后，从主 agent 验证：

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 \
  {work_dir}/{topic_name}/composition/renders/final.mp4
ls -la {work_dir}/{topic_name}/composition/renders/final.mp4
```

预期：duration 接近目标解说时长，文件大小 > 1 MB，且包含一条音频流。如果有异常，把症状反馈给 HyperFrames sub-agent。**不要**在主 agent 里手工 patch `composition/index.html`。
