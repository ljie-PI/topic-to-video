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
paragraphs against script.txt's paragraphs, the scene-plan material refs
against the catalog, and the character counts recorded in
narration-offsets.json against script.txt and narration.txt. Phase 8
additionally requires the saved check-composition report to say pass and not
to be older than index.html or any file under compositions/.

Stale detection: {workspace}/.pipeline/stamps.json (written only by this
script) records, for each completed phase, the sha256 fingerprints of the
upstream files and inputs.json fields it was built from, and of its own
products. A phase whose upstream changed while its products did not is stale:
it was built from an older upstream. A partial redo does not clear the mark:
the phase stays stale until every product has been regenerated (or the phase
is restamped), so a half-finished redo can never silence staleness. Phases
are judged in order; the first one that is missing, corrupt or stale becomes
next_phase, and every later applicable phase is pending: it is not checked,
not stamped and not reported as completed. --restamp <phase_id> accepts the
current products of a phase as built from the current upstream (its products
must pass their checks).

Robustness: scanning never aborts on state-file problems. An unreadable
optional upstream counts as absent; an unusable stamps.json is quarantined
(as stamps.json.quarantined) and reported via stamps_reset instead of being
trusted silently; saving stamps or the fingerprint cache is best-effort and
only warns when the workspace is not writable. inputs.json fields are
normalized before hashing (duration spellings, the default qa_level), and
check-composition freshness compares the sources_sha256 embedded in the
report, not mtimes, so copies that do not preserve mtimes cannot fake a fresh
pass. A size + mtime fingerprint cache (.pipeline/fpcache.json) skips
re-hashing large media files that cannot have changed.

Usage:
  python3 scripts/pipeline-status.py <workspace_dir> [--restamp <phase_id>]

workspace_dir is required: the commands in SKILL.md run from the skill root, so
the current directory is never the project workspace. Project workspaces live
outside this repo; only the doc paths in the output are repo-relative.

Output: one JSON document on stdout. Besides the legacy completed_phases /
skipped_phases / missing_products / corrupt_products it carries
  phases          [{id, status}] for every phase; status is completed,
                  skipped, missing, corrupt, stale or pending
  stale_phases, pending_phases
  stamps_reset      true when stamps.json was unusable and is now quarantined:
                  every phase may be stale; rebuild stamps with --restamp
  next_phase      {id, title, doc, reason, problems}; reason is missing,
                  corrupt or stale, and a stale phase adds changed_upstream
                  (the upstream keys whose fingerprint changed)
Exit codes: 0 = success (a next phase exists, or the pipeline is complete),
1 = runtime error (workspace unreadable or not writable, --restamp on a phase
whose products do not pass), 2 = invalid arguments.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import cli
import script_text
from composition_hash import composition_source_relpaths, composition_sources_fingerprint, visible_files
from harvest_manifest import _stage_json as stage_json

TOOL_NAME = 'pipeline-status'

SKILL_ROOT = Path(__file__).resolve().parent.parent

STATUS_OK = 'ok'
STATUS_MISSING = 'missing'
STATUS_CORRUPT = 'corrupt'

# Phase statuses in the output: a phase whose products are missing or corrupt
# takes the matching STATUS_ value; the rest are named here.
PHASE_COMPLETED = 'completed'
PHASE_SKIPPED = 'skipped'
PHASE_STALE = 'stale'
PHASE_PENDING = 'pending'

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

# {workspace}/.pipeline/ is this script's own state; only this script writes it.
# stamps.json records, per completed phase, the fingerprints of the upstream it
# was built from and of the products it holds. fpcache.json memoizes file
# fingerprints (size + mtime_ns -> sha256) so scans skip re-hashing media
# files that cannot have changed; it is best-effort and never trusted blindly.
STAMPS_PATH = '.pipeline/stamps.json'
STAMPS_VERSION = 1
# An unusable stamps.json is renamed here instead of deleted, and its presence
# keeps later scans from saving freshly-stamped (possibly stale) phases.
QUARANTINED_STAMPS = 'stamps.json.quarantined'
FPCACHE_PATH = '.pipeline/fpcache.json'
FPCACHE_VERSION = 1

# Fingerprint of an upstream file that does not exist (optional upstream).
ABSENT = 'absent'

# An upstream key "inputs.json#<field>" names one field of inputs.json.
INPUTS_FIELD_PREFIX = 'inputs.json#'

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
    parser.add_argument(
        '--restamp',
        metavar='PHASE_ID',
        choices=[phase['id'] for phase in PHASES],
        help=(
            "Accept a phase's current products as built from the current upstream: rewrite its "
            'stamp, then report the status as usual. For a stale phase whose products need no '
            'regeneration. All products of the phase must pass their checks.'
        ),
    )
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
            'material_candidates must be empty when there is no catalog phase '
            f'(fetch_materials is false and input_mode is not paper), got refs {list(dict.fromkeys(refs))}'
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


def check_paper_manifest(ws: Path, relpath: str) -> CheckResult:
    """harvest_page/manifest.json in paper mode: parse-pdf upserts the main
    paper's entry into the shared manifest, and Phase 5 builds the catalog
    from that manifest — a workspace parsed before the manifest existed (or
    whose manifest lost the entry) would otherwise sail into Phase 5 with
    nothing to catalog."""
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, dict):
        return CheckResult(STATUS_CORRUPT, 'JSON root is not an object')
    entries = data.get('entries')
    if not isinstance(entries, list) or not entries:
        return CheckResult(STATUS_CORRUPT, 'entries is not a non-empty list')
    for entry in entries:
        if isinstance(entry, dict) and entry.get('slug') == 'main-paper':
            if entry.get('source_type') != 'paper_pdf':
                return CheckResult(STATUS_CORRUPT, 'the main-paper entry is not source_type "paper_pdf"')
            return OK
    return CheckResult(
        STATUS_CORRUPT,
        'no entry with slug main-paper: run scripts/parse-pdf.py --slug main-paper before Phase 5 '
        'reads this manifest',
    )


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


# The character counts make-narration records in the offset table, and the file each one counts.
OFFSETS_LENGTH_SOURCES = (('script_length', 'script.txt'), ('narration_length', 'narration.txt'))

# Content hashes make-narration records for the exact files it read and wrote.
# Offsets from before these existed carry no hashes; the length check above is
# all that can be done for them.
OFFSETS_HASH_SOURCES = (('script_sha256', 'script.txt'), ('narration_sha256', 'narration.txt'))


def check_narration_offsets(ws: Path, relpath: str) -> CheckResult:
    """narration-offsets.json: make-narration's offset table, a required input
    of Phase 7's align-narration. The envelope is {version: 1, script_length,
    narration_length, segments: [...]} with at least one segment. The recorded
    script_sha256 / narration_sha256 (when the table has them) must equal the
    current files' hashes, which catches a same-length edit the character
    counts cannot see; the two lengths must equal the character counts of
    script.txt and narration.txt as they are now, which catches a script.txt
    edited without re-running make-narration before Phase 7's align-narration
    rejects it."""
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
    if not data['segments']:
        return CheckResult(STATUS_CORRUPT, 'segments is an empty list')
    for field, source in OFFSETS_LENGTH_SOURCES:
        recorded = data.get(field)
        if isinstance(recorded, bool) or not isinstance(recorded, int):
            return CheckResult(STATUS_CORRUPT, f'{field} must be an integer, got {recorded!r}')
        source_result, text = read_nonempty_text(ws, source)
        if source_result.ok and len(text) != recorded:  # otherwise the source is reported on its own
            return CheckResult(
                STATUS_CORRUPT,
                f'{field} is {recorded} but {source} has {len(text)} characters: {source} and this offset '
                'table no longer belong together, re-run scripts/make-narration.py',
            )
    for field, source in OFFSETS_HASH_SOURCES:
        recorded = data.get(field)
        if recorded is None:
            continue  # table predates the content hashes: only the counts apply
        if not isinstance(recorded, str):
            return CheckResult(STATUS_CORRUPT, f'{field} must be a string, got {recorded!r}')
        source_path = ws / source
        if source_path.is_file() and file_sha256(source_path) != recorded:
            return CheckResult(
                STATUS_CORRUPT,
                f'{field} does not match {source}: {source} was edited without re-running '
                'scripts/make-narration.py',
            )
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
    """A directory holding at least one visible file at any depth."""
    path = ws / relpath
    if not path.exists():
        return CheckResult(STATUS_MISSING)
    if not path.is_dir():
        return CheckResult(STATUS_CORRUPT, 'not a directory')
    if not visible_files(path):
        return CheckResult(STATUS_CORRUPT, 'directory has no files')
    return OK


# What determines the rendered picture: index.html, compositions/, assets/
# (fonts excluded — byte-identical re-copies must not invalidate anything) and
# storyboard.md. The saved check report must cover these, and final.mp4 must
# not be older than any of them: a render that predates an edit does not
# contain it.
COMPOSITION_RENDER = 'composition/renders/final.mp4'


def composition_source_paths(ws: Path, *, include_storyboard: bool = True) -> list[Path]:
    """Every file whose freshness matters for the render and its check report.

    storyboard.md is a planning doc the checker never reads, so it belongs to
    the render-freshness set only: editing it forces a re-render, not a re-check.
    """
    composition_dir = ws / 'composition'
    paths = [composition_dir / relpath for relpath in composition_source_relpaths(composition_dir)]
    storyboard = composition_dir / 'storyboard.md'
    if include_storyboard and storyboard.is_file():
        paths.append(storyboard)
    return paths


def newest_composition_source(ws: Path, *, include_storyboard: bool = True) -> Path | None:
    paths = composition_source_paths(ws, include_storyboard=include_storyboard)
    return max(paths, key=lambda path: path.stat().st_mtime_ns, default=None)


def check_composition_report(ws: Path, relpath: str) -> CheckResult:
    """composition/check-composition.json: the saved stdout of the composition
    agent's last check-composition run; its verdict must be pass, and it must
    cover the current composition: the sources_sha256 the checker embedded
    must match the current checkable sources, and final.mp4 must not be older
    than any source file — a pass that predates the last edit, or a render
    that does, says nothing about the current picture. Reports written before
    check-composition recorded sources_sha256 fall back to an mtime
    comparison, which copies that rewrote mtimes can fool."""
    result, data = read_json_product(ws, relpath)
    if not result.ok:
        return result
    if not isinstance(data, dict):
        return CheckResult(STATUS_CORRUPT, 'JSON root is not an object')
    if data.get('verdict') != 'pass':
        return CheckResult(STATUS_CORRUPT, f'verdict must be "pass", got {data.get("verdict")!r}')
    recorded = data.get('sources_sha256')
    if isinstance(recorded, str):
        # Content-based: a copy that did not preserve mtimes cannot fake freshness.
        if recorded != composition_sources_fingerprint(ws / 'composition'):
            return CheckResult(
                STATUS_CORRUPT,
                'sources_sha256 does not match the current composition (index.html / compositions/ / assets/): '
                'the composition changed after check-composition last ran, re-run it and save the report',
            )
    else:
        newest = newest_composition_source(ws, include_storyboard=False)
        if newest is not None and newest.stat().st_mtime_ns > (ws / relpath).stat().st_mtime_ns:
            return CheckResult(
                STATUS_CORRUPT,
                f'older than {newest.relative_to(ws).as_posix()}: the composition changed after check-composition '
                'last ran, re-run it and save the report',
            )
    render = ws / COMPOSITION_RENDER
    newest = newest_composition_source(ws)
    if render.is_file() and newest is not None and newest.stat().st_mtime_ns > render.stat().st_mtime_ns:
        return CheckResult(
            STATUS_CORRUPT,
            f'older than {newest.relative_to(ws).as_posix()}: final.mp4 was rendered before the last composition '
            'edit, re-render it',
        )
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

# Each product maps its workspace-relative path to a checker. A phase that
# only applies in some workspaces carries an `applies(inputs)` predicate and
# an `applies_by_default` fallback for when inputs.json cannot be read (the
# default sequence is reported then: standard, with fetching — the next phase
# is 1-gather-inputs anyway). Keep the predicate and the fallback next to the
# phase so a new conditional phase cannot drift apart from them.
def _applies_always(inputs: dict[str, Any]) -> bool:
    return True


def _applies_when_paper(inputs: dict[str, Any]) -> bool:
    return inputs.get('input_mode') in PAPER_MODES


def _applies_when_fetch(inputs: dict[str, Any]) -> bool:
    return bool(inputs.get('fetch_materials'))


def _applies_fetch_or_paper(inputs: dict[str, Any]) -> bool:
    # The catalog also holds the paper's own figures and tables, which exist
    # whether or not web materials are fetched.
    return bool(inputs.get('fetch_materials')) or inputs.get('input_mode') in PAPER_MODES


APPLICABILITY: dict[str, tuple[Callable[[dict[str, Any]], bool], bool]] = {
    'always': (_applies_always, True),
    'paper': (_applies_when_paper, False),
    'fetch': (_applies_when_fetch, True),
    'fetch_or_paper': (_applies_fetch_or_paper, True),
}

PHASES: list[dict[str, Any]] = [
    {
        'id': '1-gather-inputs',
        'title': '收集输入',
        'doc': 'references/phases/01-gather-inputs.md',
        'applies': 'always',
        'upstream': [],
        'products': {'inputs.json': check_inputs_product},
    },
    {
        'id': '2-paper-parse',
        'title': '解析论文（仅论文模式）',
        'doc': 'references/phases/02-paper-parse.md',
        'applies': 'paper',
        'upstream': ['inputs.json#source', 'inputs.json#input_mode'],
        'products': {
            'harvest_page/main-paper/metadata.json': check_paper_metadata,
            'harvest_page/manifest.json': check_paper_manifest,
        },
    },
    {
        'id': '3-research',
        'title': '主题调研',
        'doc': 'references/phases/03-research.md',
        'applies': 'always',
        'upstream': [
            'inputs.json#source',
            'inputs.json#input_mode',
            'inputs.json#language',
            'harvest_page/main-paper/metadata.json',  # optional: paper mode only
        ],
        'products': {'research-brief.md': check_text_product},
    },
    {
        'id': '4-material-harvest',
        'title': '素材抓取（可选）',
        'doc': 'references/phases/04-material-harvest.md',
        'applies': 'fetch',
        'upstream': ['research-brief.md'],
        'products': {'harvest_page/manifest.json': check_harvest_manifest},
    },
    {
        'id': '5-material-catalog',
        'title': '素材 catalog',
        'doc': 'references/phases/05-material-catalog.md',
        'applies': 'fetch_or_paper',
        'upstream': ['harvest_page/manifest.json', 'research-brief.md'],
        'products': {'material-catalog.json': check_material_catalog},
    },
    {
        'id': '6-script-scene-plan',
        'title': '脚本与场景规划（委派）',
        'doc': 'references/phases/06-script-scene-plan.md',
        'applies': 'always',
        'upstream': [
            'research-brief.md',
            'material-catalog.json',  # optional: absent when fetch_materials is false
            'inputs.json#duration',
            'inputs.json#language',
            'inputs.json#input_mode',
            'inputs.json#template',
            'narration-instructions.md',  # optional
        ],
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
        'applies': 'always',
        'upstream': [
            'narration.txt',
            'narration-offsets.json',
            'script.txt',
            'scene-plan.json',
            'inputs.json#layout',
        ],
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
        'applies': 'always',
        'upstream': [
            'voice_clone/narration.mp3',
            'transcribe/subtitle-units.json',
            'transcribe/timeline.json',
            'material-catalog.json',  # optional: absent when fetch_materials is false
            'scene-plan.json',
            'script.txt',
            'inputs.json#design',
            'inputs.json#layout',
            'inputs.json#template',
            'inputs.json#orientation',
            'composition-instructions.md',  # optional
            'style-prompt.md',  # optional: legacy projects
        ],
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
        'applies': 'always',
        'upstream': ['composition/renders/final.mp4', 'inputs.json#qa_level'],
        'products': {
            'composition/renders/final_with_bgm.mp4': check_file_product,
            'qa/qa-report.json': check_qa_report,
        },
    },
]


PHASES_BY_ID = {phase['id']: phase for phase in PHASES}


def phase_applies(phase: dict[str, Any], inputs: dict[str, Any] | None) -> bool:
    applies, applies_by_default = APPLICABILITY[phase['applies']]
    if inputs is None:
        # inputs.json unreadable: report the phase sequence the default
        # workspace (standard, with fetching) would take. The next phase will
        # be 1-gather-inputs anyway.
        return applies_by_default
    return applies(inputs)


# --- fingerprints and stamps -----------------------------------------------------


class FpCache:
    """Best-effort memo of file fingerprints: {relpath: {size, mtime_ns, sha256}}.

    Re-hashing every product of every completed phase means re-reading hundreds
    of megabytes of media on each scan. A file whose size and mtime_ns match
    the memo cannot have changed (barring deliberate timestamp forgery), so
    its recorded sha256 is reused. The cache is written best-effort and is
    never the source of truth: stamps.json still records content hashes.
    """

    def __init__(self, ws: Path) -> None:
        self.path = ws / FPCACHE_PATH
        self.files: dict[str, dict[str, Any]] = {}
        self._dirty = False
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(data, dict) or data.get('version') != FPCACHE_VERSION:
            return
        files = data.get('files')
        if not isinstance(files, dict):
            return
        for relpath, entry in files.items():
            if (
                isinstance(relpath, str)
                and isinstance(entry, dict)
                and isinstance(entry.get('sha256'), str)
                and isinstance(entry.get('size'), int)
                and isinstance(entry.get('mtime_ns'), int)
            ):
                self.files[relpath] = entry

    def cached(self, relpath: str, stat: os.stat_result) -> str | None:
        entry = self.files.get(relpath)
        if entry and entry['size'] == stat.st_size and entry['mtime_ns'] == stat.st_mtime_ns:
            return entry['sha256']
        return None

    def record(self, relpath: str, stat: os.stat_result, sha256: str) -> None:
        self.files[relpath] = {
            'size': stat.st_size,
            'mtime_ns': stat.st_mtime_ns,
            'sha256': sha256,
        }
        self._dirty = True

    def payload(self) -> dict[str, Any]:
        return {'version': FPCACHE_VERSION, 'files': self.files}

    def save(self) -> None:
        """Best-effort: an unwritable workspace must not lose the scan results."""
        if not self._dirty:
            return
        staged = stage_json(self.path, self.payload())
        os.replace(staged, self.path)
        self._dirty = False


class Fingerprinter:
    """sha256 fingerprints of a workspace's files and inputs.json fields.

    One instance serves one run, so a file used by several phases (final.mp4 is
    a product of Phase 8 and an upstream of Phase 9) is read once. File hashes
    go through the FpCache so unchanged media is not re-read on every scan.
    """

    def __init__(self, ws: Path, cache: FpCache | None = None) -> None:
        self.ws = ws
        self.cache = cache
        self._files: dict[str, str] = {}
        _, data = read_json_product(ws, 'inputs.json')
        self._inputs: dict[str, Any] = data if isinstance(data, dict) else {}

    def file(self, relpath: str) -> str:
        if relpath in self._files:
            return self._files[relpath]
        path = self.ws / relpath
        if not path.is_file():
            self._files[relpath] = ABSENT
            return ABSENT
        try:
            stat = path.stat()
            sha256 = self.cache.cached(relpath, stat) if self.cache else None
            if sha256 is None:
                sha256 = file_sha256(path)
            if self.cache:
                self.cache.record(relpath, stat, sha256)
            self._files[relpath] = sha256
        except OSError:
            # An unreadable file (permissions) must not abort the whole scan:
            # it looks like an absent optional upstream here, and its own
            # phase's product check reports it.
            self._files[relpath] = ABSENT
        return self._files[relpath]

    def inputs_field(self, name: str) -> str:
        if name not in self._inputs:
            if name == 'qa_level':
                return text_sha256(json.dumps('standard', sort_keys=True, ensure_ascii=False))
            return ABSENT
        value = canonical_inputs_field(name, self._inputs[name])
        return text_sha256(json.dumps(value, sort_keys=True, ensure_ascii=False))

    def upstream(self, phase: dict[str, Any]) -> dict[str, str]:
        return {
            key: self.inputs_field(key[len(INPUTS_FIELD_PREFIX):])
            if key.startswith(INPUTS_FIELD_PREFIX)
            else self.file(key)
            for key in phase['upstream']
        }

    def products(self, phase: dict[str, Any]) -> dict[str, str]:
        """Fingerprints of the phase's declared product paths; directory products
        are left out, an unreadable file records ABSENT."""
        return {
            relpath: self.file(relpath)
            for relpath in phase['products']
            if not (self.ws / relpath).is_dir()
        }


def canonical_inputs_field(name: str, value: Any) -> Any:
    """Normalize an inputs.json field before hashing so spelling variants compare equal.

    duration "5min" and 5 are the same target length and must not invalidate a
    phase; other fields hash as-is.
    """
    if name == 'duration':
        minutes = duration_minutes(value)
        return minutes if minutes is not None else value
    return value


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


class Stamps:
    """{ws}/.pipeline/stamps.json: {"version": 1, "phases": {<phase_id>: {upstream, products, stamped_at}}}.

    An unusable stamps.json is quarantined, not deleted, and `reset` stays True
    (and nothing is saved) until the user rebuilds stamps consciously with
    --restamp: blindly trusting the current files would mark every stale phase
    as completed, and an outdated final.mp4 could be delivered.
    """

    def __init__(self, ws: Path) -> None:
        self.path = ws / STAMPS_PATH
        self.quarantine_path = self.path.with_name(QUARANTINED_STAMPS)
        self.phases: dict[str, dict[str, Any]]
        self.reset: bool
        self.phases, self.reset = self._load()
        self._saved = copy.deepcopy(self.phases)

    def _load(self) -> tuple[dict[str, dict[str, Any]], bool]:
        if self.quarantine_path.exists():
            # Already quarantined by an earlier run: staleness stays unknowable
            # until stamps are rebuilt on purpose (see restamp_phase).
            return {}, True
        if not self.path.exists():
            return {}, False
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('version') != STAMPS_VERSION:
                raise ValueError(f'not a version {STAMPS_VERSION} stamp file')
            phases = data.get('phases')
            if not isinstance(phases, dict):
                raise ValueError('phases is not an object')
            for phase_id, stamp in phases.items():
                parts = ('upstream', 'products')
                if not isinstance(stamp, dict) or not all(isinstance(stamp.get(part), dict) for part in parts):
                    raise ValueError(f'the stamp of {phase_id} has no upstream / products objects')
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            # Keep the evidence, stop trusting it, and refuse to persist new
            # stamps taken while staleness was unknowable.
            try:
                os.replace(self.path, self.quarantine_path)
            except OSError:
                pass
            log(f'warning: {STAMPS_PATH} was unusable ({exc}); quarantined as {QUARANTINED_STAMPS}')
            return {}, True
        return phases, False

    def get(self, phase_id: str) -> dict[str, Any] | None:
        return self.phases.get(phase_id)

    def put(self, phase_id: str, upstream: dict[str, str], products: dict[str, str]) -> None:
        self.phases[phase_id] = {
            'upstream': upstream,
            'products': products,
            'stamped_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        }

    def rebuild_from(self, phase_id: str) -> None:
        """A conscious --restamp after a reset: stamps become saveable again."""
        self.reset = False
        try:
            self.quarantine_path.unlink()
        except OSError:
            pass
        log(
            f'warning: stamps were rebuilt from --restamp {phase_id}; phases that were stale '
            f'before {STAMPS_PATH} became unusable are now recorded as current'
        )

    def save(self) -> None:
        """Write the file when a stamp changed; atomically, so a crash never leaves half a file.

        After a reset nothing is written: the scan cannot distinguish a stale
        phase from a fresh one, and persisting it would silence staleness.
        """
        if self.reset:
            if self.phases != self._saved:
                log(
                    f'warning: stamps are not saved while {QUARANTINED_STAMPS} exists; '
                    'rebuild them with --restamp <phase_id> for each phase you verified'
                )
            return
        if self.phases == self._saved:
            return
        staged = stage_json(self.path, {'version': STAMPS_VERSION, 'phases': self.phases})
        os.replace(staged, self.path)
        self._saved = copy.deepcopy(self.phases)


def validate_phase(ws: Path, phase: dict[str, Any]) -> dict[str, CheckResult]:
    """Run every product checker of a phase; returns {relpath: CheckResult}
    for the products that failed."""
    problems: dict[str, CheckResult] = {}
    for relpath, checker in phase['products'].items():
        result = checker(ws, relpath)
        if not result.ok:
            problems[relpath] = result
    return problems


def changed_upstream_keys(stamped: dict[str, str], current: dict[str, str]) -> list[str]:
    """The upstream keys whose fingerprint differs between a stamp and now, in table order.

    Only keys present in both are compared: a key missing from an old stamp
    (because PHASES learned a new upstream) must not invalidate existing
    workspaces, and a removed key simply ages out of the next stamp.
    """
    return [key for key in current if key in stamped and stamped[key] != current[key]]


def reconcile_stamp(phase: dict[str, Any], stamps: Stamps, fingerprints: Fingerprinter) -> list[str]:
    """Compare a phase whose products all pass with its stamp.

    Returns the changed upstream keys when the phase is stale (its upstream
    changed and its products did not), else an empty list. Brings the stamp up
    to date when the phase is first seen, when its products were edited while
    the upstream was unchanged, or when it was fully regenerated after its
    upstream changed. While the upstream is changed the stamp keeps the
    pre-change product fingerprints: the stale mark clears only once every
    product differs from them, so a partial redo — some products regenerated,
    others still the old build — can never silence staleness. Use --restamp
    for the deterministic redo that produces byte-identical products.
    """
    upstream = fingerprints.upstream(phase)
    products = fingerprints.products(phase)
    stamp = stamps.get(phase['id'])
    if stamp is None:
        stamps.put(phase['id'], upstream, products)
        return []
    changed = changed_upstream_keys(stamp['upstream'], upstream)
    if not changed:
        if stamp['products'] != products:
            stamps.put(phase['id'], upstream, products)
        return []
    # Upstream moved. A product whose fingerprint still matches the stamp is
    # the old build; an unreadable one cannot be verified. The phase completes
    # only when every product is demonstrably the new build.
    old_build = [
        relpath
        for relpath, fingerprint in products.items()
        if fingerprint == ABSENT or stamp['products'].get(relpath) == fingerprint
    ]
    if not old_build:
        stamps.put(phase['id'], upstream, products)
        return []
    return changed


def scan_workspace(ws: Path, stamps: Stamps, cache: FpCache) -> dict[str, Any]:
    _, inputs = load_inputs(ws)
    fingerprints = Fingerprinter(ws, cache)

    statuses: list[dict[str, str]] = []
    missing: list[str] = []
    corrupt: list[str] = []
    next_phase: dict[str, Any] | None = None

    for phase in PHASES:
        if not phase_applies(phase, inputs):
            statuses.append({'id': phase['id'], 'status': PHASE_SKIPPED})
            continue
        if next_phase is not None:
            # An earlier phase is unfinished: nothing after it can be trusted yet.
            statuses.append({'id': phase['id'], 'status': PHASE_PENDING})
            continue
        problems = validate_phase(ws, phase)
        if not problems:
            changed_upstream = reconcile_stamp(phase, stamps, fingerprints)
            if not changed_upstream:
                statuses.append({'id': phase['id'], 'status': PHASE_COMPLETED})
                continue
            statuses.append({'id': phase['id'], 'status': PHASE_STALE})
            next_phase = {
                'id': phase['id'],
                'title': phase['title'],
                'doc': phase['doc'],
                'reason': PHASE_STALE,
                'changed_upstream': changed_upstream,
                'problems': {},
            }
            continue
        for relpath, result in problems.items():
            if result.status == STATUS_MISSING:
                missing.append(relpath)
            else:
                corrupt.append(relpath)
        # Missing only when nothing is there to repair; any bad file makes the phase corrupt.
        all_missing = all(result.status == STATUS_MISSING for result in problems.values())
        reason = STATUS_MISSING if all_missing else STATUS_CORRUPT
        statuses.append({'id': phase['id'], 'status': reason})
        next_phase = {
            'id': phase['id'],
            'title': phase['title'],
            'doc': phase['doc'],
            'reason': reason,
            'problems': {relpath: result.detail for relpath, result in problems.items()},
        }

    def ids_with(status: str) -> list[str]:
        return [entry['id'] for entry in statuses if entry['status'] == status]

    return {
        'success': True,
        'workspace': str(ws.resolve()),
        'input_mode': inputs.get('input_mode') if inputs else None,
        'fetch_materials': inputs.get('fetch_materials') if inputs else None,
        'stamps_reset': stamps.reset,
        'phases': statuses,
        'completed_phases': ids_with(PHASE_COMPLETED),
        'skipped_phases': ids_with(PHASE_SKIPPED),
        'stale_phases': ids_with(PHASE_STALE),
        'pending_phases': ids_with(PHASE_PENDING),
        'next_phase': next_phase,
        'missing_products': missing,
        'corrupt_products': corrupt,
    }


def restamp_phase(ws: Path, phase_id: str, stamps: Stamps, cache: FpCache) -> dict[str, Any] | None:
    """Rewrite one phase's stamp from the current files.

    Returns None on success, else the failure payload (nothing is written then).
    """
    phase = PHASES_BY_ID[phase_id]
    _, inputs = load_inputs(ws)
    if not phase_applies(phase, inputs):
        return {'success': False, 'error': f'cannot restamp {phase_id}: the phase is skipped for this workspace'}
    problems = validate_phase(ws, phase)
    if problems:
        return {
            'success': False,
            'error': f'cannot restamp {phase_id}: its products do not pass their checks',
            'problems': {relpath: result.detail or result.status for relpath, result in problems.items()},
        }
    fingerprints = Fingerprinter(ws, cache)
    stamps.put(phase_id, fingerprints.upstream(phase), fingerprints.products(phase))
    stamps.rebuild_from(phase_id)
    log(f'restamped {phase_id}')
    return None


def main() -> int:
    args = parse_args()
    ws = Path(args.workspace)
    try:
        if not ws.exists():
            raise FileNotFoundError(f'workspace does not exist: {ws}')
        if not ws.is_dir():
            raise NotADirectoryError(f'workspace is not a directory: {ws}')
        stamps = Stamps(ws)
        cache = FpCache(ws)
        if args.restamp:
            failure = restamp_phase(ws, args.restamp, stamps, cache)
            if failure is not None:
                log(f"error: {failure['error']}")
                print_json(failure)
                return 1
        result = scan_workspace(ws, stamps, cache)
        # Persisting state is best-effort: a read-only workspace or .pipeline/
        # must not throw away the scan results that were just computed.
        try:
            stamps.save()
            cache.save()
        except OSError as exc:
            log(f'warning: could not save pipeline state: {exc}')
        if stamps.reset:
            log(
                f'warning: {STAMPS_PATH} is quarantined as {QUARANTINED_STAMPS}; phase freshness could not be '
                'verified and nothing was stamped. After checking the phases yourself, rebuild their stamps '
                'with --restamp <phase_id>.'
            )
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
