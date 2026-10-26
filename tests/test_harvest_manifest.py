"""Direct-import tests for the single harvest manifest persistence module."""
from __future__ import annotations

import json
from pathlib import Path

import harvest_manifest


URL = 'https://www.youtube.com/watch?v=shared123'


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def web_entry(harvest_dir: Path, slug: str, url: str = URL) -> dict:
    return {
        'slug': slug,
        'url': f'https://example.com/{slug}',
        'success': True,
        'images': [],
        'videos': [{
            'url': url,
            'platform': 'youtube',
            'download_required': True,
            'suggested_output_dir': str(harvest_dir / slug / 'videos'),
        }],
        'scroll_recording': None,
    }


def test_upsert_is_idempotent_and_writes_relative_manifest_and_mirror(tmp_path: Path):
    entry = web_entry(tmp_path, 'one')
    entry['images'] = [{
        'id': 'img_001',
        'local_path': str(tmp_path / 'one' / 'images' / 'img_001.png'),
    }]

    harvest_manifest.upsert_entries(tmp_path, [entry])
    harvest_manifest.upsert_entries(tmp_path, [entry])

    manifest = read_json(tmp_path / 'manifest.json')
    assert manifest['version'] == 2
    assert len(manifest['entries']) == 1
    assert manifest['entries'][0]['images'][0]['local_path'] == 'one/images/img_001.png'
    assert manifest['pending_downloads'] == [{
        'url': URL,
        'platform': 'youtube',
        'suggested_output_dir': 'one/videos',
        'source_slug': 'one',
    }]
    assert read_json(tmp_path / 'one' / 'metadata.json') == manifest['entries'][0]
    assert manifest['harvest_batches'] == []
    assert manifest['updated_at']


def test_later_batches_preserve_papers_and_applied_downloads(tmp_path: Path):
    paper = {
        'slug': 'main-paper', 'success': True, 'source_type': 'paper_pdf',
        'paper_metadata': {'full_markdown_path': 'main-paper/mineru/full.md'},
        'images': [], 'videos': [],
    }
    first = web_entry(tmp_path, 'first')
    harvest_manifest.upsert_entries(tmp_path, [paper, first])
    harvest_manifest.record_harvest_batch(tmp_path, {
        'urls': [first['url']], 'succeeded': 1, 'failed': 0, 'rejected': [],
    })
    harvest_manifest.apply_download(tmp_path, URL, {
        'files': [str(tmp_path / 'first' / 'videos' / 'clip.mp4')],
        'videos': [{
            'path': str(tmp_path / 'first' / 'videos' / 'clip.mp4'),
            'width': 640, 'height': 360, 'duration_seconds': 1.0,
        }],
    })

    second = web_entry(tmp_path, 'second', 'https://youtu.be/second123')
    harvest_manifest.upsert_entries(tmp_path, [second])
    harvest_manifest.record_harvest_batch(tmp_path, {
        'urls': [second['url']], 'succeeded': 1, 'failed': 0, 'rejected': [],
    })

    manifest = harvest_manifest.load(tmp_path)
    assert {entry['slug'] for entry in manifest['entries']} == {'main-paper', 'first', 'second'}
    assert len(manifest['harvest_batches']) == 2
    first_video = next(e for e in manifest['entries'] if e['slug'] == 'first')['videos'][0]
    assert first_video['download_required'] is False
    assert first_video['local_path'] == 'first/videos/clip.mp4'
    assert [item['url'] for item in manifest['pending_downloads']] == ['https://youtu.be/second123']


def test_apply_download_fans_out_to_all_references_and_mirrors(tmp_path: Path):
    harvest_manifest.upsert_entries(tmp_path, [web_entry(tmp_path, 'one'), web_entry(tmp_path, 'two')])
    before = harvest_manifest.load(tmp_path)
    assert before['pending_downloads'][0]['also_referenced_by'] == ['two']
    video = tmp_path / 'one' / 'videos' / 'shared123.mp4'
    subtitle = tmp_path / 'one' / 'videos' / 'shared123.en.srt'
    ignored = tmp_path / 'one' / 'videos' / 'shared123.ass'

    harvest_manifest.apply_download(tmp_path, URL, {
        'files': [str(video), str(subtitle), str(ignored)],
        'videos': [{'path': str(video), 'width': 1280, 'height': 720, 'duration_seconds': 2.5}],
    })

    manifest = read_json(tmp_path / 'manifest.json')
    assert manifest['pending_downloads'] == []
    for slug in ('one', 'two'):
        entry = next(e for e in manifest['entries'] if e['slug'] == slug)
        downloaded = entry['videos'][0]
        assert downloaded == {
            **web_entry(tmp_path, slug)['videos'][0],
            'suggested_output_dir': f'{slug}/videos',
            'download_required': False,
            'downloaded': True,
            'local_path': 'one/videos/shared123.mp4',
            'subtitle_path': 'one/videos/shared123.en.srt',
            'id': 'shared123',
            'width': 1280,
            'height': 720,
            'duration_seconds': 2.5,
        }
        assert read_json(tmp_path / slug / 'metadata.json') == entry


def test_load_legacy_absolute_paths_and_paper_manifest_then_saves_relative(tmp_path: Path):
    legacy_video = str(tmp_path / 'legacy' / 'videos' / 'old.mp4')
    legacy_markdown = str(tmp_path / 'main-paper' / 'mineru' / 'full.md')
    (tmp_path / 'manifest.json').write_text(json.dumps({
        'entries': [{
            'slug': 'legacy', 'success': True, 'images': [],
            'videos': [{'url': URL, 'local_path': legacy_video, 'download_required': False}],
        }],
        'pending_downloads': [],
    }), encoding='utf-8')
    (tmp_path / 'manifest_papers.json').write_text(json.dumps({
        'entries': [{
            'slug': 'main-paper', 'success': True, 'source_type': 'paper_pdf',
            'paper_metadata': {'full_markdown_path': legacy_markdown}, 'images': [], 'videos': [],
        }],
    }), encoding='utf-8')

    manifest = harvest_manifest.load(tmp_path)
    assert {entry['slug'] for entry in manifest['entries']} == {'legacy', 'main-paper'}
    assert harvest_manifest.resolve(tmp_path, legacy_video) == Path(legacy_video)
    assert harvest_manifest.resolve(tmp_path, 'legacy/videos/old.mp4') == tmp_path / 'legacy/videos/old.mp4'
    harvest_manifest.save(tmp_path, manifest)

    saved = read_json(tmp_path / 'manifest.json')
    assert saved['version'] == 2
    assert saved['entries'][0]['videos'][0]['local_path'] == 'legacy/videos/old.mp4'
    paper = next(e for e in saved['entries'] if e['slug'] == 'main-paper')
    assert paper['paper_metadata']['full_markdown_path'] == 'main-paper/mineru/full.md'


def test_v2_entries_take_precedence_over_stale_legacy_papers_after_upsert(tmp_path: Path):
    stale_paper = {
        'slug': 'main-paper', 'title': 'stale legacy title', 'success': True,
        'source_type': 'paper_pdf', 'images': [], 'videos': [],
    }
    (tmp_path / 'manifest.json').write_text(json.dumps({'entries': []}), encoding='utf-8')
    (tmp_path / 'manifest_papers.json').write_text(
        json.dumps({'entries': [stale_paper]}), encoding='utf-8',
    )
    harvest_manifest.save(tmp_path, harvest_manifest.load(tmp_path))

    newer_paper = {**stale_paper, 'title': 'new unified title'}
    harvest_manifest.upsert_entries(tmp_path, [newer_paper])
    assert read_json(tmp_path / 'manifest.json')['entries'][0]['title'] == 'new unified title'

    reloaded = harvest_manifest.load(tmp_path)
    assert reloaded['entries'][0]['title'] == 'new unified title'


def test_slug_helpers_and_extensions_have_one_owner():
    assert harvest_manifest.slug_for_url('https://Example.com/A Path') == 'example-com-a-path-3b79fb'
    assert harvest_manifest.slug_for_pdf('https://arxiv.org/pdf/My Paper.123.pdf', None) == 'my-paper-123'
    assert harvest_manifest.slug_for_pdf(None, '/tmp/My Paper.pdf') == 'my-paper'
    assert '.mp4' in harvest_manifest.VIDEO_EXTS
    assert harvest_manifest.SUBTITLE_EXTS == {'.srt', '.vtt'}
