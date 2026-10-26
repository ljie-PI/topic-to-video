#!/usr/bin/env python3
"""Pipeline status driver: scan a project workspace and report pipeline progress.

The script is the single resume entry point of the topic-to-video pipeline.
It validates every phase's products in the workspace (existence, non-empty,
JSON parseability, required fields) and reports the completed phases, the
next phase to run, the phase doc to read for it, and any missing or corrupt
products. A phase whose product was deleted or corrupted falls back to that
phase.

Phase 6's deterministic rules are checked here too, so no agent computes them
by hand: script.txt length against inputs.json's duration, scene-plan
paragraphs against script.txt's paragraphs, and scene-plan material refs
against the catalog. Phase 8 additionally requires the saved
check-composition report to say pass.

Usage:
  python3 scripts/pipeline-status.py <workspace_dir>

workspace_dir is required: the commands in SKILL.md run from the skill root, so
the current directory is never the project workspace. Project workspaces live
outside this repo; only the doc paths in the output are repo-relative.

Output: one JSON document on stdout.
Exit codes: 0 = success (a next phase exists, or the pipeline is complete),
1 = runtime error (workspace unreadable), 2 = invalid arguments.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import cli
import script_text

TOOL_NAME = 'pipeline-status'

SKILL_ROOT = Path(__file__).resolve().parent.parent

STATUS_OK = 'ok'
STATUS_MISSING = 'missing'
STATUS_CORRUPT = 'corrupt'

INPUTS_REQUIRED_FIELDS = [
    'source',
    'input_mode',
    'duration',
    'language',
    'orientation',
    'template',
    'design',
    'layout',
    'coding_agent',
    'fetch_materials',
]

# qa_level is optional: absent means the standard tier. When present it must
# be one of the three enum values.
QA_LEVELS = {'quick', 'standard', 'strict'}

PAPER_MODES = {'paper'}

# Phase 6's length rule: the display draft's non-blank characters must be within
# +-15% of duration x 60 s x 7.5 chars/s (speech_rate=1.4).
CHARS_PER_SECOND = 7.5
SCRIPT_LENGTH_TOLERANCE = 0.15

# A scene-plan clip ref "<video_id>:<start>-<end>" must match a catalog
# selected_clips entry to within this many seconds on both ends.
CLIP_REF_TOLERANCE_S = 0.01

# inputs.json's duration is minutes: a number, or a string of a number plus an
# optional minutes unit ("5min", "5 分钟"). Anything else ("90s", "1h", "3-5 min")
# is rejected rather than read as that many minutes.
DURATION_TEXT = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*(?:min|mins|minute|minutes|分钟|分)?\s*$', re.IGNORECASE)

# The window of a clip ref "<video_id>:<start>-<end>", in seconds, written exactly so.
CLIP_WINDOW = re.compile(r'^(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$')


@dataclass
class CheckResult:
    """Structured outcome of one product check.

    status is one of STATUS_OK / STATUS_MISSING / STATUS_CORRUPT; detail
    carries a human-readable reason and is only meaningful when the status
    is not ok.
    """

    status: str
    detail: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK


OK = CheckResult(STATUS_OK)

# Every product checker has the same signature: (workspace, relpath) -> CheckResult.
Checker = Callable[[Path, str], CheckResult]


log = cli.make_logger(TOOL_NAME)
print_json = cli.print_json


def parse_args() -> argparse.Namespace:
    parser = cli.JsonArgumentParser(
        TOOL_NAME,
        description='Scan a topic-to-video workspace and report the next pipeline phase.'
    )
    parser.add_argument('workspace', help='Project workspace directory ({work_dir}/{topic_name}).')
    return parser.parse_args()


# --- product checkers ----------------------------------------------------------
#
# Each checker receives the workspace root plus the product's workspace-relative
# path, and returns a CheckResult. There is one signature for all checkers; the
# dispatcher holds no special cases.


def check_file_product(ws: Path, relpath: str) -> CheckResult:
    path = ws / relpath
    if not path.exists():
        return CheckResult(STATUS_MISSING)
    if not path.is_file():
        return CheckResult(STATUS_CORRUPT, 'not a regular file')
    if path.stat().st_size == 0:
        return CheckResult(STATUS_CORRUPT, 'empty file')
    return OK


def read_json_product(ws: Path, relpath: str) -> tuple[CheckResult, Any]:
    """Shared helper: file checks + JSON parse. Returns (result, data)."""
    result = check_file_product(ws, relpath)
    if not result.ok:
        return result, None
    try:
        data = json.loads((ws / relpath).read_text(encoding='utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return CheckResult(STATUS_CORRUPT, f'invalid JSON: {exc}'), None
    return OK, data


def read_nonempty_text(ws: Path, relpath: str) -> tuple[CheckResult, str | None]:
    """Shared helper for text products: file must exist and have content."""
    result = check_file_product(ws, relpath)
    if not result.ok:
        return result, None
    text = (ws / relpath).read_text(encoding='utf-8', errors='replace')
    if not text.strip():
        return CheckResult(STATUS_CORRUPT, 'file has no content'), None
    return OK, text


def check_text_product(ws: Path, relpath: str) -> CheckResult:
    result, _ = read_nonempty_text(ws, relpath)
    return result


def check_script_text(ws: Path, relpath: str) -> CheckResult:
    """script.txt: non-empty, and its length is within tolerance of the target
    that inputs.json's duration implies."""
    result, text = read_nonempty_text(ws, relpath)
    if not result.ok:
        return result
    _, inputs = load_inputs(ws)
    minutes = duration_minutes(inputs['duration']) if inputs else None
    if minutes is None:
        return OK  # nothing to compare against; inputs.json is reported on its own
    target = minutes * 60 * CHARS_PER_SECOND
    count = script_text.count_chars(text)
    deviation = (count - target) / target
    if abs(deviation) > SCRIPT_LENGTH_TOLERANCE:
        return CheckResult(
            STATUS_CORRUPT,
            f'{count} characters, target {target:g} ({minutes:g} min x 60 s x {CHARS_PER_SECOND:g} chars/s), '
            f'off by {deviation:+.1%} (limit +-{SCRIPT_LENGTH_TOLERANCE:.0%})',
        )
    return OK


def check_dict_entries_product(ws: Path, relpath: str) -> CheckResult:
    """For JSON objects that must carry a non-empty `entries` list
    (harvest manifest, material catalog)."""
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, dict):
        return CheckResult(STATUS_CORRUPT, 'JSON root is not an object')
    entries = data.get('entries')
    if not isinstance(entries, list) or not entries:
        return CheckResult(STATUS_CORRUPT, 'entries is not a non-empty list')
    return OK


CATALOG_ITEM_KINDS = ('images', 'videos')


def entry_label(index: int, entry: Any) -> str:
    slug = entry.get('slug') if isinstance(entry, dict) else None
    return f'entry {slug!r}' if isinstance(slug, str) and slug else f'entry {index}'


def check_material_catalog(ws: Path, relpath: str) -> CheckResult:
    """material-catalog.json: non-empty `entries`; every image / video has a
    non-empty string `id` and `semantic_description` (Phase 5's contract).
    ids are not required to be unique: harvest-pages numbers each page's
    images from img_001, so the same id recurs across entries."""
    entries_result = check_dict_entries_product(ws, relpath)
    if not entries_result.ok:
        return entries_result
    _, data = read_json_product(ws, relpath)
    for index, entry in enumerate(data['entries']):
        label = entry_label(index, entry)
        if not isinstance(entry, dict):
            return CheckResult(STATUS_CORRUPT, f'{label} is not an object')
        for kind in CATALOG_ITEM_KINDS:
            items = entry.get(kind, [])
            if not isinstance(items, list):
                return CheckResult(STATUS_CORRUPT, f'{label} {kind} is not a list')
            for position, item in enumerate(items):
                where = f'{label} {kind}[{position}]'
                if not isinstance(item, dict):
                    return CheckResult(STATUS_CORRUPT, f'{where} is not an object')
                for field in ('id', 'semantic_description'):
                    value = item.get(field)
                    if not isinstance(value, str) or not value.strip():
                        return CheckResult(
                            STATUS_CORRUPT,
                            f'{where} (id {item.get("id")!r}) has no non-empty string {field}',
                        )
    return OK


@dataclass
class CatalogIndex:
    """What scene-plan refs can point at: every image / video id, plus each
    video's selected clip windows as (start_s, end_s)."""

    ids: set[str]
    clips: dict[str, list[tuple[float, float]]]


def load_catalog_index(ws: Path) -> CatalogIndex | None:
    """The index of material-catalog.json, or None when it is not a valid catalog
    (Phase 5 is reported on its own then)."""
    if not check_material_catalog(ws, 'material-catalog.json').ok:
        return None
    _, data = read_json_product(ws, 'material-catalog.json')
    ids: set[str] = set()
    clips: dict[str, list[tuple[float, float]]] = {}
    for entry in data['entries']:
        for image in entry.get('images', []):
            ids.add(image['id'])
        for video in entry.get('videos', []):
            ids.add(video['id'])
            windows = clips.setdefault(video['id'], [])
            for clip in video.get('selected_clips') or []:
                bounds = [clip.get(key) if isinstance(clip, dict) else None for key in ('start', 'end')]
                if all(isinstance(b, (int, float)) and not isinstance(b, bool) for b in bounds):
                    windows.append((float(bounds[0]), float(bounds[1])))
    return CatalogIndex(ids, clips)


def ref_resolves(ref: str, index: CatalogIndex) -> bool:
    """A material ref is a catalog id, or `<video_id>:<start>-<end>` naming one
    of that video's selected clips."""
    if ref in index.ids:
        return True
    video_id, colon, window = ref.rpartition(':')
    if not colon or video_id not in index.clips:
        return False
    bounds = CLIP_WINDOW.match(window)
    if not bounds:
        return False
    start, end = float(bounds.group(1)), float(bounds.group(2))
    return any(
        abs(start - clip_start) <= CLIP_REF_TOLERANCE_S and abs(end - clip_end) <= CLIP_REF_TOLERANCE_S
        for clip_start, clip_end in index.clips[video_id]
    )


def material_ref_problem(ws: Path, refs: list[str]) -> str | None:
    """Why the scene plan's material refs are unusable, or None."""
    _, inputs = load_inputs(ws)
    if not phase_applies(PHASES_BY_ID['5-material-catalog'], inputs):
        return (
            'material_candidates must be empty when fetch_materials is false (there is no catalog), '
            f'got refs {list(dict.fromkeys(refs))}'
        )
    index = load_catalog_index(ws)
    if index is None:
        return None
    invalid = [ref for ref in dict.fromkeys(refs) if not ref_resolves(ref, index)]
    if invalid:
        return f'material_candidates refs not found in material-catalog.json: {invalid}'
    return None


def check_harvest_manifest(ws: Path, relpath: str) -> CheckResult:
    """Phase 4 needs entries and at least one actual web harvest batch."""
    entries_result = check_dict_entries_product(ws, relpath)
    if not entries_result.ok:
        return entries_result
    _, data = read_json_product(ws, relpath)
    batches = data.get('harvest_batches')
    if not isinstance(batches, list) or not batches:
        return CheckResult(STATUS_CORRUPT, 'harvest_batches is not a non-empty list')
    return OK


def duration_minutes(value: Any) -> float | None:
    """The target length in minutes, or None when `value` is not a positive minutes number."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        minutes = float(value)
    elif isinstance(value, str):
        match = DURATION_TEXT.match(value)
        minutes = float(match.group(1)) if match else 0.0
    else:
        return None
    return minutes if math.isfinite(minutes) and minutes > 0 else None


def is_design_dir(path: Path) -> bool:
    """A design is a dir holding <name>/<name>.md and the fonts.json manifest."""
    return (path / f'{path.name}.md').is_file() and (path / 'fonts.json').is_file()


def available_designs() -> list[str]:
    """Design names under the skill's modules/designs/."""
    root = SKILL_ROOT / 'modules' / 'designs'
    return sorted(d.name for d in root.iterdir() if is_design_dir(d))


def design_problem(ws: Path, design: Any) -> str | None:
    """Why inputs.json's design cannot be used, or None.

    A design removed from the skill is still accepted when the workspace
    already holds its copy (modules/ is materialized there in Phase 8), so
    a project composed with it is not sent back to Phase 1.
    """
    designs = available_designs()
    if isinstance(design, str) and design and '/' not in design:
        if design in designs or is_design_dir(ws / 'modules' / 'designs' / design):
            return None
    return f'field design {design!r} is not an available design (choose one of: {", ".join(designs)})'


def load_inputs(ws: Path) -> tuple[CheckResult, dict[str, Any] | None]:
    """Validate inputs.json and return (result, parsed inputs)."""
    result, data = read_json_product(ws, 'inputs.json')
    if not result.ok:
        return result, None
    if not isinstance(data, dict):
        return CheckResult(STATUS_CORRUPT, 'JSON root is not an object'), None
    missing_fields = [field for field in INPUTS_REQUIRED_FIELDS if field not in data]
    if missing_fields:
        return CheckResult(
            STATUS_CORRUPT, f'missing required fields: {", ".join(missing_fields)}'
        ), None
    if not isinstance(data['fetch_materials'], bool):
        return CheckResult(STATUS_CORRUPT, 'field fetch_materials is not a boolean'), None
    if duration_minutes(data['duration']) is None:
        # Same as a removed design: the rest of inputs.json is still usable for
        # phase applicability, only Phase 1 has to rewrite this field.
        return CheckResult(
            STATUS_CORRUPT,
            'field duration must be the target length in minutes (分钟数): a positive number '
            f'such as 5, or a number with a minutes unit such as "5min", got {data["duration"]!r}',
        ), data
    problem = design_problem(ws, data['design'])
    if problem:
        # e.g. a project created before a theme was removed: back to Phase 1
        # to pick one that still exists. The rest of inputs.json is valid, so
        # it is returned too and phase applicability (paper / fetch) still holds.
        return CheckResult(STATUS_CORRUPT, problem), data
    if 'qa_level' in data and data['qa_level'] not in QA_LEVELS:
        return CheckResult(
            STATUS_CORRUPT,
            f'field qa_level must be one of quick / standard / strict, got {data["qa_level"]!r}',
        ), None
    return OK, data


def check_inputs_product(ws: Path, relpath: str) -> CheckResult:
    result, _ = load_inputs(ws)
    return result


def check_paper_metadata(ws: Path, relpath: str) -> CheckResult:
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, dict):
        return CheckResult(STATUS_CORRUPT, 'JSON root is not an object')
    if data.get('source_type') != 'paper_pdf':
        return CheckResult(STATUS_CORRUPT, 'field source_type is not "paper_pdf"')
    paper_metadata = data.get('paper_metadata')
    if not isinstance(paper_metadata, dict):
        return CheckResult(STATUS_CORRUPT, 'missing paper_metadata')
    # v2 paths are harvest-root-relative; legacy workspaces may hold absolute
    # paths. Both are valid, as is null when MinerU produced no full markdown.
    if 'full_markdown_path' not in paper_metadata or not (
        isinstance(paper_metadata['full_markdown_path'], str)
        or paper_metadata['full_markdown_path'] is None
    ):
        return CheckResult(STATUS_CORRUPT, 'missing paper_metadata.full_markdown_path')
    return OK


def check_lexicon_product(ws: Path, relpath: str) -> CheckResult:
    """tts-lexicon.json: a non-empty JSON object mapping display forms to
    reading forms (both non-empty strings)."""
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, dict) or not data:
        return CheckResult(STATUS_CORRUPT, 'JSON root is not a non-empty object')
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str) or not key or not value:
            return CheckResult(
                STATUS_CORRUPT, f'lexicon entries must be non-empty strings, got {key!r}: {value!r}'
            )
    return OK


# make-narration.py's OFFSETS_VERSION; align-narration refuses any other version.
NARRATION_OFFSETS_VERSION = 1


def check_narration_offsets(ws: Path, relpath: str) -> CheckResult:
    """narration-offsets.json: make-narration's offset table, a required input
    of Phase 7's align-narration. Only the envelope is checked here:
    {version: 1, segments: [...]}."""
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, dict):
        return CheckResult(STATUS_CORRUPT, 'JSON root is not an object')
    if data.get('version') != NARRATION_OFFSETS_VERSION:
        return CheckResult(
            STATUS_CORRUPT, f'version must be {NARRATION_OFFSETS_VERSION}, got {data.get("version")!r}'
        )
    if not isinstance(data.get('segments'), list):
        return CheckResult(STATUS_CORRUPT, 'segments is not a list')
    return OK


def paragraph_type_problem(scenes: list[dict[str, Any]]) -> str | None:
    """Why a scene's `paragraphs` holds something other than integers, or None."""
    for index, scene in enumerate(scenes):
        for number in scene['paragraphs']:
            if isinstance(number, bool) or not isinstance(number, int):
                return f'scene {index} paragraphs must be integers, got {number!r}'
    return None


def paragraph_coverage_problem(scenes: list[dict[str, Any]], paragraph_count: int) -> str | None:
    """Why the scenes' paragraph numbers are not exactly {1..paragraph_count}, or None.

    Scenes may share a paragraph (a scene split mid-paragraph); only the union counts.
    Assumes paragraph_type_problem found nothing.
    """
    covered = {number for scene in scenes for number in scene['paragraphs']}
    missing = sorted(set(range(1, paragraph_count + 1)) - covered)
    out_of_range = sorted(number for number in covered if not 1 <= number <= paragraph_count)
    if not missing and not out_of_range:
        return None
    parts = []
    if missing:
        parts.append(f'missing paragraphs {missing}')
    if out_of_range:
        parts.append(f'out-of-range paragraphs {out_of_range}')
    return f'{"; ".join(parts)} (script.txt has {paragraph_count} paragraphs)'


def check_scene_plan_product(ws: Path, relpath: str) -> CheckResult:
    """scene-plan.json: a non-empty JSON list of scenes; each scene has a
    scene_id and a non-empty paragraphs list (narrative-level plan from the
    delegated script agent). Against script.txt, the paragraphs of all scenes
    must cover its paragraphs exactly."""
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, list) or not data:
        return CheckResult(STATUS_CORRUPT, 'JSON root is not a non-empty list')
    for index, scene in enumerate(data):
        if not isinstance(scene, dict):
            return CheckResult(STATUS_CORRUPT, f'scene {index} is not an object')
        if not scene.get('scene_id'):
            return CheckResult(STATUS_CORRUPT, f'scene {index} missing scene_id')
        paragraphs = scene.get('paragraphs')
        if not isinstance(paragraphs, list) or not paragraphs:
            return CheckResult(STATUS_CORRUPT, f'scene {index} missing paragraphs')
    problem = paragraph_type_problem(data)
    if problem:
        return CheckResult(STATUS_CORRUPT, problem)
    script_result, script = read_nonempty_text(ws, 'script.txt')
    if script_result.ok:  # otherwise script.txt is reported on its own
        problem = paragraph_coverage_problem(data, len(script_text.paragraphs(script)))
        if problem:
            return CheckResult(STATUS_CORRUPT, problem)
    refs: list[str] = []
    for index, scene in enumerate(data):
        candidates = scene.get('material_candidates', [])
        if not isinstance(candidates, list):
            return CheckResult(STATUS_CORRUPT, f'scene {index} material_candidates is not a list')
        for position, candidate in enumerate(candidates):
            ref = candidate.get('ref') if isinstance(candidate, dict) else None
            if not isinstance(ref, str) or not ref:
                return CheckResult(
                    STATUS_CORRUPT,
                    f'scene {index} material_candidates[{position}] has no non-empty string ref',
                )
            refs.append(ref)
    problem = material_ref_problem(ws, refs) if refs else None
    if problem:
        return CheckResult(STATUS_CORRUPT, problem)
    return OK


def check_transcript(ws: Path, relpath: str) -> CheckResult:
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, list) or not data:
        return CheckResult(STATUS_CORRUPT, 'transcript is not a non-empty sentence list')
    for index, sentence in enumerate(data):
        if not isinstance(sentence, dict):
            return CheckResult(STATUS_CORRUPT, f'sentence {index} is not an object')
        missing = [
            field
            for field in ('begin', 'end', 'text', 'words')
            if field not in sentence
        ]
        if missing:
            return CheckResult(
                STATUS_CORRUPT, f'sentence {index} missing fields: {", ".join(missing)}'
            )
        if not isinstance(sentence['words'], list):
            return CheckResult(STATUS_CORRUPT, f'sentence {index} words is not a list')
    return OK


def check_subtitle_units(ws: Path, relpath: str) -> CheckResult:
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, dict):
        return CheckResult(STATUS_CORRUPT, 'JSON root is not an object')
    units = data.get('units')
    if not isinstance(units, list) or not units:
        return CheckResult(STATUS_CORRUPT, 'units is not a non-empty list')
    return OK


def check_timeline(ws: Path, relpath: str) -> CheckResult:
    """timeline.json: {total_s, paragraphs: [{index, begin_s, end_s}]}; cues optional."""
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, dict):
        return CheckResult(STATUS_CORRUPT, 'JSON root is not an object')
    paragraphs = data.get('paragraphs')
    if not isinstance(paragraphs, list) or not paragraphs:
        return CheckResult(STATUS_CORRUPT, 'paragraphs is not a non-empty list')
    for index, paragraph in enumerate(paragraphs):
        if not isinstance(paragraph, dict):
            return CheckResult(STATUS_CORRUPT, f'paragraph {index} is not an object')
        missing = [
            field
            for field in ('index', 'begin_s', 'end_s')
            if not isinstance(paragraph.get(field), (int, float))
        ]
        if missing:
            return CheckResult(
                STATUS_CORRUPT, f'paragraph {index} missing numeric fields: {", ".join(missing)}'
            )
    return OK


def check_directory_product(ws: Path, relpath: str) -> CheckResult:
    """A directory holding at least one visible file at any depth (hidden files
    such as .DS_Store do not count)."""
    path = ws / relpath
    if not path.exists():
        return CheckResult(STATUS_MISSING)
    if not path.is_dir():
        return CheckResult(STATUS_CORRUPT, 'not a directory')
    has_file = any(
        item.is_file() and not any(part.startswith('.') for part in item.relative_to(path).parts)
        for item in path.rglob('*')
    )
    if not has_file:
        return CheckResult(STATUS_CORRUPT, 'directory has no files')
    return OK


def check_composition_report(ws: Path, relpath: str) -> CheckResult:
    """composition/check-composition.json: the saved stdout of the composition
    agent's last check-composition run; its verdict must be pass."""
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, dict):
        return CheckResult(STATUS_CORRUPT, 'JSON root is not an object')
    if data.get('verdict') != 'pass':
        return CheckResult(STATUS_CORRUPT, f'verdict must be "pass", got {data.get("verdict")!r}')
    return OK


def check_qa_report(ws: Path, relpath: str) -> CheckResult:
    """qa/qa-report.json: the Phase 9 QA result, written once fix rounds have
    concluded. Contains exactly `findings` ([{scene_id, check, issue, frame}])
    and `verdict`; verdict must be pass or handed_off (fail means fix rounds
    are still in progress or were exhausted without a user hand-off)."""
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, dict):
        return CheckResult(STATUS_CORRUPT, 'JSON root is not an object')
    if set(data.keys()) != {'findings', 'verdict'}:
        return CheckResult(STATUS_CORRUPT, 'qa-report must contain exactly findings and verdict')
    if not isinstance(data['findings'], list):
        return CheckResult(STATUS_CORRUPT, 'findings is not a list')
    for index, finding in enumerate(data['findings']):
        if not isinstance(finding, dict):
            return CheckResult(STATUS_CORRUPT, f'finding {index} is not an object')
        for field in ('scene_id', 'check', 'issue', 'frame'):
            if field not in finding:
                return CheckResult(STATUS_CORRUPT, f'finding {index} missing {field}')
    if data['verdict'] not in ('pass', 'handed_off'):
        return CheckResult(
            STATUS_CORRUPT,
            f'verdict must be pass or handed_off once fix rounds conclude, got {data["verdict"]!r}',
        )
    return OK


# --- phase definitions ---------------------------------------------------------

# Each product maps its workspace-relative path to a checker.
PHASES: list[dict[str, Any]] = [
    {
        'id': '1-gather-inputs',
        'title': '收集输入',
        'doc': 'references/phases/01-gather-inputs.md',
        'products': {'inputs.json': check_inputs_product},
    },
    {
        'id': '2-paper-parse',
        'title': '解析论文（仅论文模式）',
        'doc': 'references/phases/02-paper-parse.md',
        'conditional': 'paper',
        'products': {'harvest_page/main-paper/metadata.json': check_paper_metadata},
    },
    {
        'id': '3-research',
        'title': '主题调研',
        'doc': 'references/phases/03-research.md',
        'products': {'research-brief.md': check_text_product},
    },
    {
        'id': '4-material-harvest',
        'title': '素材抓取（可选）',
        'doc': 'references/phases/04-material-harvest.md',
        'conditional': 'fetch',
        'products': {'harvest_page/manifest.json': check_harvest_manifest},
    },
    {
        'id': '5-material-catalog',
        'title': '素材 catalog',
        'doc': 'references/phases/05-material-catalog.md',
        'conditional': 'fetch',
        'products': {'material-catalog.json': check_material_catalog},
    },
    {
        'id': '6-script-scene-plan',
        'title': '脚本与场景规划（委派）',
        'doc': 'references/phases/06-script-scene-plan.md',
        'products': {
            'script.txt': check_script_text,
            'tts-lexicon.json': check_lexicon_product,
            'narration.txt': check_text_product,
            'narration-offsets.json': check_narration_offsets,
            'scene-plan.json': check_scene_plan_product,
        },
    },
    {
        'id': '7-voice-subtitles',
        'title': '配音与字幕',
        'doc': 'references/phases/07-voice-subtitles.md',
        'products': {
            'voice_clone/narration.mp3': check_file_product,
            'transcribe/transcript.json': check_transcript,
            'transcribe/subtitle-units.json': check_subtitle_units,
            'transcribe/timeline.json': check_timeline,
        },
    },
    {
        'id': '8-composition',
        'title': 'composition（委派）',
        'doc': 'references/phases/08-composition.md',
        'products': {
            'composition/storyboard.md': check_text_product,
            'composition/index.html': check_file_product,
            'composition/compositions': check_directory_product,
            'composition/check-composition.json': check_composition_report,
            'composition/renders/final.mp4': check_file_product,
        },
    },
    {
        'id': '9-check-mix',
        'title': '检查与混音',
        'doc': 'references/phases/09-check-mix.md',
        'products': {
            'composition/renders/final_with_bgm.mp4': check_file_product,
            'qa/qa-report.json': check_qa_report,
        },
    },
]


PHASES_BY_ID = {phase['id']: phase for phase in PHASES}


def phase_applies(phase: dict[str, Any], inputs: dict[str, Any] | None) -> bool:
    conditional = phase.get('conditional')
    if conditional is None:
        return True
    if inputs is None:
        # inputs.json unreadable: report the full default sequence (standard,
        # with fetching). The next phase will be 1-gather-inputs anyway.
        return conditional == 'fetch'
    if conditional == 'paper':
        return inputs.get('input_mode') in PAPER_MODES
    if conditional == 'fetch':
        return bool(inputs.get('fetch_materials'))
    return True


def validate_phase(ws: Path, phase: dict[str, Any]) -> dict[str, CheckResult]:
    """Run every product checker of a phase; returns {relpath: CheckResult}
    for the products that failed."""
    problems: dict[str, CheckResult] = {}
    for relpath, checker in phase['products'].items():
        result = checker(ws, relpath)
        if not result.ok:
            problems[relpath] = result
    return problems


def scan_workspace(ws: Path) -> dict[str, Any]:
    _, inputs = load_inputs(ws)

    completed: list[str] = []
    skipped: list[str] = []
    missing: list[str] = []
    corrupt: list[str] = []
    next_phase: dict[str, Any] | None = None

    for phase in PHASES:
        if not phase_applies(phase, inputs):
            skipped.append(phase['id'])
            continue
        problems = validate_phase(ws, phase)
        if not problems:
            completed.append(phase['id'])
            continue
        for relpath, result in problems.items():
            if result.status == STATUS_MISSING:
                missing.append(relpath)
            else:
                corrupt.append(relpath)
        if next_phase is None:
            next_phase = {
                'id': phase['id'],
                'title': phase['title'],
                'doc': phase['doc'],
                'problems': {relpath: result.detail for relpath, result in problems.items()},
            }

    return {
        'success': True,
        'workspace': str(ws.resolve()),
        'input_mode': inputs.get('input_mode') if inputs else None,
        'fetch_materials': inputs.get('fetch_materials') if inputs else None,
        'completed_phases': completed,
        'skipped_phases': skipped,
        'next_phase': next_phase,
        'missing_products': missing,
        'corrupt_products': corrupt,
    }


def main() -> int:
    args = parse_args()
    ws = Path(args.workspace)
    try:
        if not ws.exists():
            raise FileNotFoundError(f'workspace does not exist: {ws}')
        if not ws.is_dir():
            raise NotADirectoryError(f'workspace is not a directory: {ws}')
        result = scan_workspace(ws)
        print_json(result)
        if result['next_phase'] is None:
            log('all phases complete')
        else:
            log(f"next phase: {result['next_phase']['id']} -> {result['next_phase']['doc']}")
        return 0
    except (OSError, FileNotFoundError, NotADirectoryError) as exc:
        log(f'error: {exc}')
        print_json({'success': False, 'error': str(exc)})
        return 1


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
