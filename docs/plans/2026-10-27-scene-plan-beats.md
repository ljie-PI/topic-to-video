# Scene-plan Semantic Beats Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Carry script-authored semantic beats through `scene-plan.json` and `timeline.json`, validate them, and map them to presenter or non-presenter visuals.

**Architecture:** Reuse the existing cue normalization/location path for beat timing, adding `timeline.beats` only when `--scene-plan` is supplied. Add focused product validation in `pipeline-status.py`; document the authoring and composition contracts without changing cues or adding Jay actions.

**Tech Stack:** Python 3 CLI scripts, pytest subprocess integration tests, Markdown delegation/module docs.

---

### Task 1: Align semantic beats

**Files:**
- Modify: `tests/test_align_narration.py`
- Modify: `scripts/align-narration.py`

1. Add subprocess tests for located beat timestamps, unmatched-beat warning/omission, and no `beats` key without `--scene-plan`.
2. Run `python3 -m pytest tests/test_align_narration.py -k 'beat or no_cues_without_scene_plan' -q`; confirm the new beat assertions fail because the field is absent.
3. Extract the shared normalized text locator from `locate_cues`, use it for beats, and add `beat_count`; migrate the edited script to `scripts/cli.py` helpers.
4. Re-run the focused tests and then the full `tests/test_align_narration.py` file.

### Task 2: Validate beat products

**Files:**
- Modify: `tests/test_pipeline_status.py`
- Modify: `scripts/pipeline-status.py`

1. Add CLI tests for non-list scene beats, invalid type, missing/empty text, text absent from `script.txt`, valid beats with script approval, and malformed/missing/valid timeline beat timestamps.
2. Run the new tests with `python3 -m pytest tests/test_pipeline_status.py -k 'beat' -q`; confirm corruption/validation assertions fail on current behavior.
3. Add minimal scene-plan and timeline validators, including numeric checks that reject booleans.
4. Re-run the beat tests and then the full `tests/test_pipeline_status.py` file.

### Task 3: Document authoring and visual contracts

**Files:**
- Modify: `tests/test_phase_docs.py`
- Modify: `references/delegation/script/base-instructions.md`
- Modify: `references/delegation/composition/base-instructions.md`
- Modify: `modules/components/jay/jay.md`
- Modify: `modules/templates/github/narration.md`
- Modify: `references/phases/06-script-scene-plan.md`
- Modify: `references/phases/07-voice-subtitles.md`
- Modify: `references/delegation/composition/handoff-template.md`

1. Add focused documentation assertions for beat rules, mapping rows, the Jay “对应 beat” column/generic-row replacement, and the cues/beats distinction.
2. Run the new documentation test and confirm it fails before editing docs.
3. Add the exact issue #116 schema, mapping table, and notes; update affected output references.
4. Run `python3 -m pytest tests/test_phase_docs.py tests/test_doc_references.py -q`.

### Task 4: Verify and commit

1. Inspect the diff for scope, preserved delegation/approval behavior, and no skipped tests.
2. Run only the focused test files above.
3. Commit all issue #116 changes with a message referencing `#116`; do not push or merge.
