"""The layout Markdown region and summary tables stay consistent with the layout JSON contracts."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path

import pytest

import video_contract

REPO_ROOT = Path(__file__).resolve().parent.parent
LAYOUTS_ROOT = REPO_ROOT / 'modules' / 'layouts'


@dataclass(frozen=True)
class LayoutDocSpec:
    layout: str
    json_file: str
    md_file: str
    section_heading: str


LAYOUT_DOC_SPECS: tuple[LayoutDocSpec, ...] = (
    LayoutDocSpec(
        layout='presenter',
        json_file='presenter.json',
        md_file='presenter.md',
        section_heading='## 区域',
    ),
    LayoutDocSpec(
        layout='stage',
        json_file='stage.json',
        md_file='stage.md',
        section_heading='## 区域',
    ),
    LayoutDocSpec(
        layout='portrait',
        json_file='portrait.json',
        md_file='portrait.md',
        section_heading='## 画布 1080×1920',
    ),
    LayoutDocSpec(
        layout='portrait-3x4',
        json_file='portrait-3x4.json',
        md_file='portrait.md',
        section_heading='## 画布 1080×1440',
    ),
)

POSITION_COLUMN = '位置（左, 上）'
SIZE_COLUMN = '尺寸（宽×高）'


def load_layout_json(spec: LayoutDocSpec) -> dict:
    return json.loads((LAYOUTS_ROOT / spec.json_file).read_text(encoding='utf-8'))


def strip_fenced_code_blocks(markdown: str) -> str:
    return re.sub(r'```.*?```', '', markdown, flags=re.DOTALL)


def extract_section(markdown: str, heading_prefix: str) -> str:
    lines = markdown.splitlines()
    start_idx = next(
        (idx for idx, line in enumerate(lines) if line.strip().startswith(heading_prefix)),
        None,
    )
    if start_idx is None:
        raise ValueError(f'missing section heading starting with {heading_prefix!r}')
    end_idx = len(lines)
    for idx in range(start_idx + 1, len(lines)):
        if lines[idx].startswith('## '):
            end_idx = idx
            break
    return '\n'.join(lines[start_idx + 1 : end_idx])


def parse_markdown_tables(text: str) -> list[tuple[list[str], list[dict[str, str]]]]:
    clean = strip_fenced_code_blocks(text)
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw_line in clean.splitlines():
        line = raw_line.strip()
        if line.startswith('|') and line.endswith('|'):
            current.append(line)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)

    tables: list[tuple[list[str], list[dict[str, str]]]] = []
    for block in blocks:
        if len(block) < 2:
            continue
        headers = [cell.strip() for cell in block[0].strip('|').split('|')]
        rows: list[dict[str, str]] = []
        for row_line in block[2:]:
            cells = [cell.strip() for cell in row_line.strip('|').split('|')]
            if len(cells) != len(headers):
                raise ValueError(f'malformed markdown table row: {row_line!r}')
            rows.append(dict(zip(headers, cells, strict=True)))
        tables.append((headers, rows))
    return tables


def parse_position_cell(value: str) -> tuple[int, int]:
    match = re.fullmatch(r'(\d+)\s*,\s*(\d+)', value.strip())
    if not match:
        raise ValueError(f'invalid position cell {value!r}')
    return int(match.group(1)), int(match.group(2))


def parse_size_cell(value: str) -> tuple[int, int]:
    match = re.fullmatch(r'(\d+)\s*[×x]\s*(\d+)', value.strip())
    if not match:
        raise ValueError(f'invalid size cell {value!r}')
    return int(match.group(1)), int(match.group(2))


def parse_doc_canvas(spec: LayoutDocSpec) -> tuple[int, int]:
    markdown = (LAYOUTS_ROOT / spec.md_file).read_text(encoding='utf-8')
    heading_match = re.search(r'画布\s*(\d+)\s*[×x]\s*(\d+)', spec.section_heading)
    if heading_match:
        for line in markdown.splitlines():
            if line.strip().startswith(spec.section_heading):
                line_match = re.search(r'画布\s*(\d+)\s*[×x]\s*(\d+)', line)
                if line_match:
                    return int(line_match.group(1)), int(line_match.group(2))
    doc_match = re.search(r'画布\s*(\d+)\s*[×x]\s*(\d+)', strip_fenced_code_blocks(markdown))
    if not doc_match:
        raise ValueError(f'missing canvas declaration in {spec.md_file}')
    return int(doc_match.group(1)), int(doc_match.group(2))


def parse_region_table(spec: LayoutDocSpec) -> list[dict[str, object]]:
    markdown = (LAYOUTS_ROOT / spec.md_file).read_text(encoding='utf-8')
    section = extract_section(markdown, spec.section_heading)
    region_tables = [
        rows
        for headers, rows in parse_markdown_tables(section)
        if POSITION_COLUMN in headers and SIZE_COLUMN in headers
    ]
    assert len(region_tables) == 1, (
        f'{spec.layout}: expected exactly 1 region table under {spec.section_heading!r} '
        f'in {spec.md_file}, got {len(region_tables)}'
    )
    parsed: list[dict[str, object]] = []
    for row in region_tables[0]:
        x, y = parse_position_cell(row[POSITION_COLUMN])
        width, height = parse_size_cell(row[SIZE_COLUMN])
        parsed.append({
            'label': row['区域'],
            'rect': {'x': x, 'y': y, 'width': width, 'height': height},
        })
    return parsed


def compare_layout_regions(
    layout: str,
    json_regions: list[dict[str, object]],
    markdown_rows: list[dict[str, object]],
) -> list[str]:
    problems: list[str] = []
    if len(json_regions) != len(markdown_rows):
        problems.append(
            f'layout={layout} field=region_count json={len(json_regions)} markdown={len(markdown_rows)}'
        )
    for region, md_row in zip(json_regions, markdown_rows):
        region_id = region['id']
        row_label = md_row['label']
        json_rect = region['rect']
        md_rect = md_row['rect']
        for field in ('x', 'y', 'width', 'height'):
            json_val = json_rect[field]
            md_val = md_rect[field]
            if json_val != md_val:
                problems.append(
                    f'layout={layout} region={region_id} ({row_label}) '
                    f'field={field} json={json_val} markdown={md_val}'
                )
    return problems


def parse_layouts_summary_table() -> dict[str, dict[str, object]]:
    markdown = (LAYOUTS_ROOT / 'layouts.md').read_text(encoding='utf-8')
    section = extract_section(markdown, '## 可选布局')
    tables = parse_markdown_tables(section)
    assert len(tables) == 1, f'expected 1 summary table in layouts.md, got {len(tables)}'
    _, rows = tables[0]
    summary: dict[str, dict[str, object]] = {}
    for row in rows:
        layout = row['layout'].strip('` ')
        canvas_w, canvas_h = parse_size_cell(row['画布（宽×高，px）'])
        caption_cell = row['字幕：宽 / 字号 / 最大行数']
        match = re.fullmatch(r'(\d+)\s*/\s*(\d+)\s*/\s*(\d+)', caption_cell.strip())
        if not match:
            raise ValueError(f'invalid caption summary cell {caption_cell!r} for layout={layout}')
        summary[layout] = {
            'canvas': {'width': canvas_w, 'height': canvas_h},
            'caption': {
                'width_px': int(match.group(1)),
                'font_size_px': int(match.group(2)),
                'max_lines': int(match.group(3)),
            },
        }
    return summary


def compare_layout_summary_entry(
    layout: str,
    json_data: dict[str, object],
    md_entry: dict[str, object],
) -> list[str]:
    problems: list[str] = []
    json_canvas = json_data['canvas']
    md_canvas = md_entry['canvas']
    for field in ('width', 'height'):
        if json_canvas[field] != md_canvas[field]:
            problems.append(
                f'layout={layout} region=summary.canvas field={field} '
                f'json={json_canvas[field]} markdown={md_canvas[field]}'
            )
    json_caption = json_data['caption']
    md_caption = md_entry['caption']
    for field in ('width_px', 'font_size_px', 'max_lines'):
        if json_caption[field] != md_caption[field]:
            problems.append(
                f'layout={layout} region=summary.caption field={field} '
                f'json={json_caption[field]} markdown={md_caption[field]}'
            )
    return problems


def test_explicit_spec_table_covers_all_registered_layouts():
    spec_layouts = sorted(spec.layout for spec in LAYOUT_DOC_SPECS)
    assert spec_layouts == video_contract.available_layouts(REPO_ROOT)


@pytest.mark.parametrize('spec', LAYOUT_DOC_SPECS, ids=lambda s: s.layout)
def test_markdown_region_table_matches_json_regions_item_by_item(spec: LayoutDocSpec):
    contract = load_layout_json(spec)
    markdown_rows = parse_region_table(spec)
    problems = compare_layout_regions(spec.layout, contract['regions'], markdown_rows)
    assert not problems, '\n'.join(problems)


def test_all_region_kinds_are_covered_across_the_layout_specs():
    covered_ids = {
        region['id']
        for spec in LAYOUT_DOC_SPECS
        for region in load_layout_json(spec)['regions']
    }
    assert covered_ids == {
        'ground',
        'nav-bar',
        'header',
        'main',
        'side',
        'person',
        'caption-bar',
        'caption-text',
    }


@pytest.mark.parametrize('spec', LAYOUT_DOC_SPECS, ids=lambda s: s.layout)
def test_canvas_ground_and_caption_width_invariants_match(spec: LayoutDocSpec):
    contract = load_layout_json(spec)
    canvas = contract['canvas']
    regions_by_id = {region['id']: region['rect'] for region in contract['regions']}

    doc_w, doc_h = parse_doc_canvas(spec)
    assert (canvas['width'], canvas['height']) == (doc_w, doc_h), (
        f'layout={spec.layout} region=canvas field=width/height '
        f'json={canvas["width"]}x{canvas["height"]} markdown={doc_w}x{doc_h}'
    )

    ground = regions_by_id['ground']
    expected_ground = {'x': 0, 'y': 0, 'width': canvas['width'], 'height': canvas['height']}
    for field, expected_val in expected_ground.items():
        actual_val = ground[field]
        assert actual_val == expected_val, (
            f'layout={spec.layout} region=ground field={field} '
            f'json={actual_val} expected={expected_val}'
        )

    caption_text = regions_by_id['caption-text']
    caption_width_px = contract['caption']['width_px']
    assert caption_width_px == caption_text['width'], (
        f'layout={spec.layout} region=caption-text field=width_px '
        f'json_caption={caption_width_px} json_region_width={caption_text["width"]}'
    )


def test_layouts_index_summary_table_matches_every_preset_json():
    summary = parse_layouts_summary_table()
    assert sorted(summary) == sorted(spec.layout for spec in LAYOUT_DOC_SPECS)

    problems: list[str] = []
    for spec in LAYOUT_DOC_SPECS:
        contract = load_layout_json(spec)
        problems.extend(compare_layout_summary_entry(spec.layout, contract, summary[spec.layout]))
    assert not problems, '\n'.join(problems)


def test_compare_layout_regions_reports_layout_region_field_and_both_values():
    spec = LAYOUT_DOC_SPECS[0]  # presenter
    contract = load_layout_json(spec)
    markdown_rows = parse_region_table(spec)
    drifted_rows = [
        {**row, 'rect': dict(row['rect'])}
        for row in markdown_rows
    ]
    # Synthetic drift on person (人物区) width: 420 -> 400
    person_idx = next(
        idx for idx, r in enumerate(contract['regions']) if r['id'] == 'person'
    )
    drifted_rows[person_idx]['rect']['width'] = 400

    problems = compare_layout_regions(spec.layout, contract['regions'], drifted_rows)
    assert len(problems) == 1
    message = problems[0]
    assert 'presenter' in message
    assert 'person' in message
    assert '人物区' in message
    assert 'width' in message
    assert '420' in message
    assert '400' in message
