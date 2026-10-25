# Phase 6 — 脚本与场景规划（委派给 coding agent）

本 phase 整体委派给 coding agent 完成：旁白（显示稿 + 词表）与叙事层场景规划由 script agent 按委派包独立完成。委派约定见 `references/delegation/conventions.md`（默认 claude-code；派发 prompt 只有一句话，让对方读 handoff）。

## 输入

Phase 3 的 `research-brief.md` + Phase 5 的 `material-catalog.json`（若 `fetch_materials = false` 则没有 catalog，按“无素材”路径写纯旁白）+ `inputs.json`（目标时长、语言、input_mode、所选模板）+ 模板旁白要求（`modules/templates/<template>/narration.md`，如有）+ 项目指令 `narration-instructions.md`（如有）。

## 输出

`script.txt`（非空，显示稿）+ `tts-lexicon.json`（非空 JSON map，显示形式 → 朗读形式）+ `narration.txt`（非空，由 make-narration 生成）+ `narration-offsets.json`（偏移表）+ `scene-plan.json`（叙事层场景规划，非空列表）。

## 完成判据

四个主产物都通过状态脚本的校验（`script.txt` / `narration.txt` 存在非空；`tts-lexicon.json` 是可解析的非空 JSON map，键值都是非空字符串；`scene-plan.json` 是非空列表，每个 scene 有 `scene_id` 和非空 `paragraphs`）；字数与目标时长的偏差在 ±15% 以内；场景规划覆盖 `script.txt` 的全部段落；素材引用都存在于 catalog 中。校验通过后，把旁白和场景摘要交给用户确认，再进入 TTS。

## 下一步

Phase 7（TTS）：只对 `narration.txt` 配音。

---

## Phase 6.1 — 委派 script agent

**主 agent 不读委派包里的基础指令**（`references/delegation/script/base-instructions.md` 只给被委派的 agent 读）。主 agent 做三件事：

1. 按 `references/delegation/script/handoff-template.md` 写出 `{work_dir}/{topic_name}/script-handoff.md`：填入 Coding Agent（`inputs.json` 的 `coding_agent`，默认 claude-code）、Inputs（research-brief / material-catalog / inputs.json 的实际路径）、Outputs、Required References（基础指令 → 模板旁白要求 → 项目指令，按叠加顺序）、Additional Instructions（实际存在的指令文件，没有写 None）。
2. 按 `references/delegation/conventions.md` 派发，prompt 一句话：

   ```text
   读取 {work_dir}/{topic_name}/script-handoff.md 并按它执行；完成后报告产物路径。
   ```

3. script agent 返回后做 **Phase 6.2 的确定性校验**。

## Phase 6.2 — 主 agent 校验与用户确认

script agent 报告完成后，主 agent 逐项校验（不修改产物，不合格就打回）：

1. **产物齐全**：`script.txt`、`tts-lexicon.json`、`narration.txt`、`narration-offsets.json`、`scene-plan.json` 都存在且非空（状态脚本也会校验）。
2. **字数 ±15%**：`script.txt` 总字数（去掉空白）与目标时长的换算偏差在 ±15% 以内。换算：`speech_rate=1.4` 下约 7.5 字符/秒（3min ≈ 1350、5min ≈ 2250、10min ≈ 4500）。
3. **段落全覆盖**：`scene-plan.json` 所有 scene 的 `paragraphs` 并集恰好覆盖 `script.txt` 的全部段落（1 起编号，无遗漏、无越界）。
4. **素材引用有效**：`material-catalog.json` 存在时，`scene-plan.json` 里所有 `material_candidates[].ref` 都能在 catalog 中找到对应素材 id 或 `selected_clips` 的 `<video_id>:<start>-<end>` 引用；引用了不存在的素材即不合格。

全部通过后，把旁白和场景摘要（每个 scene 的 `scene_id` + `intent`）交给用户确认；用户确认前不要进入 Phase 7。

## Phase 6.3 — 生成朗读稿

显示稿和词表确认后，运行：

```bash
python3 scripts/make-narration.py \
  --script {work_dir}/{topic_name}/script.txt \
  --lexicon {work_dir}/{topic_name}/tts-lexicon.json \
  --output-dir {work_dir}/{topic_name}/
```

产出 `narration.txt`（朗读稿，可直接交给 Phase 7 的 TTS 脚本，不需要任何修改）和 `narration-offsets.json`（偏移表）。不要手改 `narration.txt`；要改就改显示稿或词表后重新生成（改了显示稿需重新过一遍 6.2 校验与用户确认）。
