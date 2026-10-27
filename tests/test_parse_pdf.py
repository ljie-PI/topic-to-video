"""Local MinerU subprocess tests for parse-pdf.py; no network or API token."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'parse-pdf.py'

FAKE_MINERU = r'''#!/usr/bin/env python3
import base64
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
pdf = Path(args[args.index('-p') + 1])
out = Path(args[args.index('-o') + 1]) / pdf.stem / 'auto'
if os.environ.get('FAKE_MINERU_NESTED'):
    out = out / 'nested'
(out / 'images').mkdir(parents=True)
(out / 'full.md').write_text('# Fixture Paper\n\n# Abstract\nA local fixture.\n', encoding='utf-8')
(out / f'{pdf.stem}_content_list.json').write_text(json.dumps([
    {'type': 'image', 'img_path': 'images/fig1.png', 'image_caption': ['Figure 1']},
]), encoding='utf-8')
(out / 'images' / 'fig1.png').write_bytes(base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk'
    '+A8AAQUBAScY42YAAAAASUVORK5CYII='
))
'''


def install_fake_mineru(
    tmp_path: Path, **env_overrides: str,
) -> tuple[Path, Path, dict[str, str]]:
    fake_bin = tmp_path / 'bin'
    fake_bin.mkdir()
    mineru = fake_bin / 'mineru'
    mineru.write_text(FAKE_MINERU, encoding='utf-8')
    mineru.chmod(0o755)
    pdf = tmp_path / 'paper.pdf'
    pdf.write_bytes(b'%PDF-1.4\n%%EOF\n')
    harvest_dir = tmp_path / 'harvest_page'
    env = dict(os.environ)
    env.pop('MINERU_API_TOKEN', None)
    env['PATH'] = f'{fake_bin}{os.pathsep}{env["PATH"]}'
    env.update(env_overrides)
    return pdf, harvest_dir, env


def test_local_mineru_upserts_v2_manifest_with_dimensions_and_relative_paths(tmp_path: Path):
    pdf, harvest_dir, env = install_fake_mineru(tmp_path)

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), '--pdf', str(pdf), '--output-dir', str(harvest_dir)],
        capture_output=True, text=True, env=env, timeout=60, check=False,
    )

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result['backend'] == 'local_pipeline'
    manifest = json.loads((harvest_dir / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['version'] == 2
    assert len(manifest['entries']) == 1
    entry = manifest['entries'][0]
    assert entry['slug'] == 'paper'
    assert entry['paper_metadata']['full_markdown_path'] == 'paper/mineru/full.md'
    assert entry['images'][0]['local_path'] == 'paper/images/img_001.png'
    assert entry['images'][0]['width'] == 1
    assert entry['images'][0]['height'] == 1
    assert json.loads((harvest_dir / 'paper' / 'metadata.json').read_text(encoding='utf-8')) == entry
    assert (harvest_dir / 'paper' / 'mineru' / 'full.md').is_file()
    assert (harvest_dir / 'paper' / 'mineru' / 'images' / 'fig1.png').is_file()
    assert not (harvest_dir / 'manifest_papers.json').exists()
    assert not (tmp_path / 'mineru_output').exists()

    def check_paths(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {'local_path', 'subtitle_path', 'suggested_output_dir', 'full_markdown_path'} and isinstance(item, str):
                    assert not Path(item).is_absolute(), (key, item)
                check_paths(item)
        elif isinstance(value, list):
            for item in value:
                check_paths(item)
    check_paths(manifest)


def test_main_and_related_paper_material_ids_remain_bare(tmp_path: Path):
    pdf, harvest_dir, env = install_fake_mineru(tmp_path)
    base_cmd = [sys.executable, str(SCRIPT), '--pdf', str(pdf), '--output-dir', str(harvest_dir)]

    main = subprocess.run(base_cmd + ['--slug', 'main-paper'], capture_output=True, text=True, env=env, timeout=60)
    assert main.returncode == 0, main.stderr
    related = subprocess.run(
        base_cmd + ['--slug', 'related-foo'], capture_output=True, text=True, env=env, timeout=60
    )
    assert related.returncode == 0, related.stderr

    manifest = json.loads((harvest_dir / 'manifest.json').read_text(encoding='utf-8'))
    entries = {entry['slug']: entry for entry in manifest['entries']}
    assert entries['main-paper']['images'][0]['id'] == 'img_001'
    assert entries['main-paper']['images'][0]['local_path'] == 'main-paper/images/img_001.png'
    assert entries['main-paper']['paper_metadata']['figure_captions'] == {'img_001': 'Figure 1'}
    assert entries['related-foo']['images'][0]['id'] == 'img_001'
    assert entries['related-foo']['images'][0]['local_path'] == 'related-foo/images/img_001.png'
    assert entries['related-foo']['paper_metadata']['figure_captions'] == {'img_001': 'Figure 1'}


def test_nested_mineru_full_markdown_keeps_a_resolvable_relative_path(tmp_path: Path):
    pdf, harvest_dir, env = install_fake_mineru(tmp_path, FAKE_MINERU_NESTED='1')

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), '--pdf', str(pdf), '--output-dir', str(harvest_dir)],
        capture_output=True, text=True, env=env, timeout=60, check=False,
    )

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    relative = result['manifest_entry']['paper_metadata']['full_markdown_path']
    assert relative == 'paper/mineru/nested/full.md'
    assert (harvest_dir / relative).is_file()


def test_invalid_flag_does_not_import_pillow(tmp_path: Path):
    proc = subprocess.run(
        [sys.executable, '-S', str(SCRIPT), '--definitely-not-a-flag'],
        cwd=tmp_path, capture_output=True, text=True, timeout=30, check=False,
    )

    assert proc.returncode == 2, proc.stderr
    assert len(proc.stdout.splitlines()) == 1
    result = json.loads(proc.stdout)
    assert result['success'] is False
    assert result['error']
    assert 'Traceback' not in proc.stderr
