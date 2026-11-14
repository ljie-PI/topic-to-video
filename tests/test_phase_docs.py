"""Structural contracts between phase/module docs, PHASES products, and scripts."""
from __future__ import annotations

import json
import re
from pathlib import Path

import harvest_manifest  # scripts/ 由 conftest.py 加入 sys.path
from cli_helpers import load_script_module

REPO_ROOT = Path(__file__).resolve().parent.parent
PHASE_DOCS = sorted((REPO_ROOT / 'references' / 'phases').glob('*.md'))
RECORDING_EXTENSIONS = {'playwright': '.webm', 'cdp_screencast': '.mp4'}


def doc_text(relpath: str) -> str:
    return (REPO_ROOT / relpath).read_text(encoding='utf-8')


PHASES = load_script_module('pipeline-status.py', 'pipeline_status').PHASES


def section_text(text: str, heading: str) -> str:
    match = re.search(rf'^## {re.escape(heading)}\n(.*?)(?=^## |^---\s*$|\Z)', text, re.MULTILINE | re.DOTALL)
    assert match, f'missing "## {heading}" section'
    return match.group(1)


def test_every_phase_doc_names_checked_products_self_check_and_guardrails():
    merged_phase_doc = '07-voice-subtitles.md'
    missing_products: list[str] = []
    for phase in PHASES:
        text = doc_text(phase['doc'])
        outputs = section_text(text, '输出')
        missing = [relpath for relpath in phase['products'] if relpath not in outputs]
        if missing:
            missing_products.append(f'{phase["doc"]} "## 输出" does not name: {missing}')

        headings = re.findall(r'^## (.+)$', text, flags=re.MULTILINE)
        next_step_idx = headings.index('下一步')
        assert headings[next_step_idx + 1] == '护栏', phase['doc']
        assert section_text(text, '护栏').strip() != '无', phase['doc']

        criteria = text.index('## 完成判据')
        next_step = text.index('## 下一步')
        assert criteria < next_step, f'{phase["doc"]} puts the self-check elsewhere'
        if phase['doc'].endswith(merged_phase_doc):
            assert '## 执行后自检' not in text, f'{phase["doc"]} splits the check again'
            criteria_section = text[criteria:next_step]
            assert '状态脚本校验' in criteria_section and '执行者核对' in criteria_section
            continue
        assert '## 执行后自检' in text, f'{phase["doc"]} has no "## 执行后自检"'
        assert criteria < text.index('## 执行后自检') < next_step, phase['doc']
    assert not missing_products, '\n'.join(missing_products)


def test_phase_4_output_examples_are_parseable_and_match_slugs_and_backends():
    harvest = doc_text('references/phases/04-material-harvest.md')
    blocks = [json.loads(raw) for raw in re.findall(r'```json\n(.*?)```', harvest, re.DOTALL)]

    manifest = next(block for block in blocks if 'version' in block)
    assert manifest['version'] == 2
    assert set(manifest) == {
        'version', 'entries', 'pending_downloads', 'harvest_batches', 'updated_at',
    }
    page_entry, video_entry = manifest['entries']
    assert page_entry['images'] and page_entry['scroll_recording']
    assert video_entry['images'] == [] and video_entry['scroll_recording'] is None
    assert video_entry['videos'][0]['download_required'] is True
    assert manifest['pending_downloads'][0]['source_slug'] == video_entry['slug']

    batch = next(block for block in blocks if 'batch_size' in block)
    assert 'chrome' in batch and 'version' not in batch
    assert len(batch['entries']) == batch['batch_size']

    download = next(block for block in blocks if 'files' in block)
    assert download['manifest_updated'] is True
    assert all(path.startswith('/') for path in download['files'])
    updated = next(block for block in blocks if 'download_required' in block and 'id' in block)
    assert updated['download_required'] is False and updated['downloaded'] is True

    for entry in manifest['entries']:
        assert entry['slug'] == harvest_manifest.slug_for_url(entry['url'])
        for image in entry['images']:
            assert image['local_path'].startswith(f'{entry["slug"]}/')
        for video in entry['videos']:
            assert video['suggested_output_dir'] == f'{entry["slug"]}/videos'
        recording = entry['scroll_recording']
        if recording is not None:
            assert recording['local_path'].startswith(f'{entry["slug"]}/recording/')
            expected = RECORDING_EXTENSIONS[recording['method']]
            assert recording['local_path'].endswith(expected), (
                f'{recording["method"]} 录制应是 {expected}'
            )

    video_slug = manifest['pending_downloads'][0]['source_slug']
    assert download['output_dir'].endswith(f'{video_slug}/videos')
    assert all(f'{video_slug}/videos/' in path for path in download['files'])
    assert updated['local_path'].startswith(f'{video_slug}/videos/')
    assert updated['id'] in updated['local_path']


def test_composition_reference_links_resolve_from_the_markdown_file():
    docs = (
        'modules/modules.md',
        'modules/templates/templates.md',
        'modules/layouts/layouts.md',
        'modules/components/components.md',
        'modules/motion.md',
        'modules/patterns/patterns.md',
    )
    expected_target = (REPO_ROOT / 'references/delegation/composition/base-instructions.md').resolve()
    for doc in docs:
        match = re.search(r'\[composition 基础指令第四部分\]\(([^)]+)\)', doc_text(doc))
        assert match, doc
        relative_path, _, fragment = match.group(1).partition('#')
        target = (REPO_ROOT / doc).parent / relative_path
        assert target.resolve() == expected_target, doc
        assert target.is_file(), doc
        assert fragment == '四内容演绎与模板选择', doc


def test_every_executable_script_is_documented_at_its_point_of_use():
    scripts = REPO_ROOT / 'scripts'
    expected = {
        path.name
        for path in scripts.glob('*.py')
        if re.search(r"^if __name__ == ['\"]__main__['\"]:", path.read_text(encoding='utf-8'), flags=re.MULTILINE)
    }
    expected.add('fonts-download.sh')
    docs = [doc_text('SKILL.md'), doc_text('references/pipeline-control.md')]
    docs += [path.read_text(encoding='utf-8') for path in PHASE_DOCS]
    docs += sorted(
        path.read_text(encoding='utf-8')
        for path in (REPO_ROOT / 'references' / 'delegation').glob('**/*.md')
    )
    documented = {name for name in expected if any(name in text for text in docs)}
    assert documented == expected
