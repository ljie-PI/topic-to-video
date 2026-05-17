#!/usr/bin/env python3
"""MinerU-based PDF paper parser for harvest-manifest-compatible output.

Wraps MinerU cloud API (primary) with local CLI fallback to extract
figures, tables, charts, and full markdown from academic PDFs.

Usage:
  python3 parse-pdf.py --url https://arxiv.org/pdf/2605.03675 \\
    --output-dir ./harvest_page/ --slug main-paper

  python3 parse-pdf.py --pdf /path/to/paper.pdf \\
    --output-dir ./harvest_page/ --slug main-paper

Requires:
  export MINERU_API_TOKEN="..."   (for cloud path)
  or `mineru` CLI on PATH         (for local fallback)

Output convention:
  stdout : JSON result with metadata + manifest entry
  stderr : human-readable progress prefixed with [parse-pdf]
  exit   : 0 success, 1 runtime error, 2 invalid arguments
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

TOOL_NAME = 'parse-pdf'
POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 300
API_BASE = 'https://mineru.net/api/v4'


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

class ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        log(f'Argument error: {message}')
        print(json.dumps({'success': False, 'error': message}, ensure_ascii=False))
        self.exit(2)


def log(message: str) -> None:
    print(f'[{TOOL_NAME}] {message}', file=sys.stderr)


def fail(message: str, exit_code: int = 1) -> None:
    log(message)
    print(json.dumps({'success': False, 'error': message}, ensure_ascii=False))
    raise SystemExit(exit_code)


def parse_args() -> argparse.Namespace:
    p = ArgumentParser(description='MinerU PDF paper parser.')
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--url', help='Public URL to a PDF.')
    group.add_argument('--pdf', help='Local path to a PDF file.')
    p.add_argument('--output-dir', required=True, help='harvest_page directory.')
    p.add_argument('--slug', default=None, help='Slug for output subdirectory (auto-derived if omitted).')
    p.add_argument('--model-version', default='vlm', help='MinerU model version (default: vlm).')
    return p.parse_args()


def derive_slug(url: str | None, pdf_path: str | None) -> str:
    """Derive a slug from URL or filename: lowercase alphanumeric + hyphens."""
    if url:
        parsed = urlparse(url)
        base = Path(parsed.path).stem or 'paper'
    else:
        base = Path(pdf_path).stem
    slug = re.sub(r'[^a-z0-9]+', '-', base.lower()).strip('-')
    return slug[:80] or 'paper'


# ---------------------------------------------------------------------------
# Cloud API helpers
# ---------------------------------------------------------------------------

def cloud_headers(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


def cloud_extract_url(url: str, token: str, model_version: str) -> str:
    """Submit a URL extraction task. Returns task_id."""
    resp = requests.post(
        f'{API_BASE}/extract/task',
        headers=cloud_headers(token),
        json={
            'url': url,
            'model_version': model_version,
            'enable_formula': True,
            'enable_table': True,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get('code') not in (0, None):
        raise RuntimeError(f'cloud error code={data.get("code")} msg={data.get("msg")}')
    task_id = data.get('data', {}).get('task_id')
    if not task_id:
        raise RuntimeError(f'no task_id in response: {data}')
    log(f'cloud task submitted: {task_id}')
    return task_id


def cloud_extract_file(pdf_path: str, token: str, model_version: str) -> str:
    """Upload a local file and submit extraction. Returns task_id."""
    filename = os.path.basename(pdf_path)

    # Step 1: get pre-signed upload URL
    resp = requests.post(
        f'{API_BASE}/file-urls/batch',
        headers=cloud_headers(token),
        json={'file_names': [filename], 'model_version': model_version},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get('code') not in (0, None):
        raise RuntimeError(f'cloud batch error code={data.get("code")} msg={data.get("msg")}')
    batch_id = data.get('data', {}).get('batch_id')
    file_urls = data.get('data', {}).get('file_urls', [])
    if not batch_id or not file_urls:
        raise RuntimeError(f'no batch_id/file_urls in response: {data}')

    # Step 2: upload file to pre-signed URL
    oss_url = file_urls[0]
    log(f'uploading {filename} to cloud storage...')
    with open(pdf_path, 'rb') as f:
        put_resp = requests.put(oss_url, data=f, timeout=120)
    put_resp.raise_for_status()
    log('upload complete')

    # Step 3: submit batch extraction
    resp = requests.post(
        f'{API_BASE}/extract/task/batch',
        headers=cloud_headers(token),
        json={'batch_id': batch_id},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get('code') not in (0, None):
        raise RuntimeError(f'cloud batch extract error code={data.get("code")} msg={data.get("msg")}')
    task_id = data.get('data', {}).get('task_id')
    if not task_id:
        raise RuntimeError(f'no task_id in batch response: {data}')
    log(f'cloud task submitted: {task_id}')
    return task_id


def cloud_poll(task_id: str, token: str) -> dict[str, Any]:
    """Poll until task is done or timeout. Returns task result data."""
    deadline = time.time() + POLL_TIMEOUT_S
    while time.time() < deadline:
        resp = requests.get(
            f'{API_BASE}/extract/task/{task_id}',
            headers=cloud_headers(token),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get('code') not in (0, None):
            raise RuntimeError(f'poll error code={data.get("code")} msg={data.get("msg")}')
        task_data = data.get('data', {})
        state = task_data.get('state', '')
        log(f'poll: state={state}')
        if state == 'done':
            return task_data
        if state in ('failed', 'error'):
            raise RuntimeError(f'cloud task failed: {task_data}')
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError(f'cloud task {task_id} did not complete within {POLL_TIMEOUT_S}s')


def cloud_download_zip(task_data: dict[str, Any], dest_dir: str) -> str:
    """Download and unzip cloud result. Returns path to extracted output dir."""
    zip_url = task_data.get('full_zip_url')
    if not zip_url:
        raise RuntimeError(f'no full_zip_url in task data: {task_data}')
    log(f'downloading result zip...')
    resp = requests.get(zip_url, timeout=120)
    resp.raise_for_status()
    zip_path = os.path.join(dest_dir, 'result.zip')
    with open(zip_path, 'wb') as f:
        f.write(resp.content)
    log(f'downloaded {len(resp.content)} bytes, extracting...')
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.namelist():
            resolved = os.path.realpath(os.path.join(dest_dir, member))
            if not resolved.startswith(os.path.realpath(dest_dir) + os.sep) and resolved != os.path.realpath(dest_dir):
                raise RuntimeError(f'zip entry escapes dest_dir: {member}')
        zf.extractall(dest_dir)
    os.remove(zip_path)
    return dest_dir


# ---------------------------------------------------------------------------
# Cloud path (primary)
# ---------------------------------------------------------------------------

def run_cloud(args: argparse.Namespace, token: str) -> str:
    """Run cloud extraction. Returns path to MinerU output directory."""
    tmp_dir = tempfile.mkdtemp(prefix='mineru-cloud-')
    try:
        if args.url:
            task_id = cloud_extract_url(args.url, token, args.model_version)
        else:
            task_id = cloud_extract_file(args.pdf, token, args.model_version)
        task_data = cloud_poll(task_id, token)
        cloud_download_zip(task_data, tmp_dir)
        return tmp_dir
    except Exception:
        # Cleanup on failure so temp doesn't leak when fallback runs
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


# ---------------------------------------------------------------------------
# Local fallback
# ---------------------------------------------------------------------------

def run_local(args: argparse.Namespace) -> tuple:
    """Run local mineru CLI. Returns (output_dir, tmp_root) for cleanup."""
    if not shutil.which('mineru'):
        raise RuntimeError('mineru CLI not found on PATH')

    tmp_dir = tempfile.mkdtemp(prefix='mineru-local-')
    try:
        pdf_path = args.pdf

        # If URL, download the PDF first
        if args.url:
            log(f'downloading PDF from {args.url}...')
            resp = requests.get(args.url, timeout=120)
            resp.raise_for_status()
            pdf_path = os.path.join(tmp_dir, 'input.pdf')
            with open(pdf_path, 'wb') as f:
                f.write(resp.content)
            log(f'downloaded {len(resp.content)} bytes')

        log(f'running mineru CLI on {pdf_path}...')
        result = subprocess.run(
            ['mineru', '-p', pdf_path, '-o', tmp_dir, '-b', 'pipeline'],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            stderr_tail = (result.stderr or '')[-500:]
            raise RuntimeError(f'mineru CLI failed (rc={result.returncode}): {stderr_tail}')
        log('mineru CLI completed')

        # MinerU local output is in {tmp_dir}/{pdf_stem}/auto/
        pdf_stem = Path(pdf_path).stem
        auto_dir = os.path.join(tmp_dir, pdf_stem, 'auto')
        output_dir = auto_dir if os.path.isdir(auto_dir) else tmp_dir
        return output_dir, tmp_dir
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


# ---------------------------------------------------------------------------
# Processing: MinerU output -> harvest format
# ---------------------------------------------------------------------------

def find_content_list(mineru_dir: str) -> str | None:
    """Find *_content_list.json in the MinerU output (has UUID prefix)."""
    matches = glob.glob(os.path.join(mineru_dir, '**', '*_content_list.json'), recursive=True)
    return matches[0] if matches else None


def find_full_md(mineru_dir: str) -> str | None:
    """Find full.md in the MinerU output."""
    matches = glob.glob(os.path.join(mineru_dir, '**', 'full.md'), recursive=True)
    return matches[0] if matches else None


def extract_title(md_text: str) -> str:
    """Extract title from first # heading."""
    m = re.search(r'^#\s+(.+)$', md_text, re.MULTILINE)
    return m.group(1).strip() if m else ''


def extract_abstract(md_text: str) -> str:
    """Extract text between # Abstract and the next # heading."""
    m = re.search(
        r'^#\s+Abstract\s*\n(.*?)(?=^#\s|\Z)',
        md_text,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    return m.group(1).strip() if m else ''


def process_mineru_output(
    mineru_dir: str,
    output_dir: str,
    slug: str,
    source_url: str | None,
    pdf_path: str | None,
) -> dict[str, Any]:
    """Process MinerU output into harvest-compatible format. Returns manifest entry."""
    output_path = Path(output_dir)
    work_dir = output_path.parent  # parent of harvest_page
    slug_dir = output_path / slug
    images_dir = slug_dir / 'images'
    images_dir.mkdir(parents=True, exist_ok=True)

    # Archive raw MinerU output
    mineru_archive = work_dir / 'mineru_output' / slug
    mineru_archive.mkdir(parents=True, exist_ok=True)

    # Find key files
    content_list_path = find_content_list(mineru_dir)
    full_md_path = find_full_md(mineru_dir)

    md_text = ''
    if full_md_path:
        with open(full_md_path, 'r', encoding='utf-8', errors='replace') as f:
            md_text = f.read()
        shutil.copy2(full_md_path, mineru_archive / 'full.md')

    content_list: list[dict[str, Any]] = []
    if content_list_path:
        with open(content_list_path, 'r', encoding='utf-8', errors='replace') as f:
            content_list = json.load(f)
        shutil.copy2(content_list_path, mineru_archive / 'content_list.json')

    title = extract_title(md_text)
    abstract = extract_abstract(md_text)
    text_excerpt = abstract[:2000] if abstract else md_text[:2000]

    # Process figures, tables, charts
    images_meta: list[dict[str, Any]] = []
    figure_captions: dict[str, str] = {}
    table_captions: dict[str, str] = {}
    img_idx = 0
    tbl_idx = 0
    chart_idx = 0

    for item in content_list:
        item_type = item.get('type', '')
        if item_type not in ('image', 'table', 'chart'):
            continue

        # Determine source image path
        img_path_raw = item.get('img_path', '')
        if not img_path_raw:
            continue
        # img_path may be relative to the MinerU output dir
        src_path = Path(img_path_raw)
        if not src_path.is_absolute():
            src_path = Path(mineru_dir) / img_path_raw
        if not src_path.exists():
            log(f'  image not found: {src_path}')
            continue

        # Determine caption
        if item_type == 'image':
            img_idx += 1
            file_id = f'img_{img_idx:03d}'
            caption_list = item.get('image_caption', [])
            if not isinstance(caption_list, list):
                caption_list = [caption_list] if caption_list else []
            caption = caption_list[0] if caption_list else ''
            img_type = 'raster'
            figure_captions[file_id] = caption
        elif item_type == 'table':
            tbl_idx += 1
            file_id = f'tbl_{tbl_idx:03d}'
            caption_list = item.get('table_caption', [])
            if not isinstance(caption_list, list):
                caption_list = [caption_list] if caption_list else []
            caption = caption_list[0] if caption_list else ''
            img_type = 'table_screenshot'
            table_captions[file_id] = caption
        else:  # chart
            chart_idx += 1
            file_id = f'chart_{chart_idx:03d}'
            caption_list = item.get('chart_caption', [])
            if not isinstance(caption_list, list):
                caption_list = [caption_list] if caption_list else []
            caption = caption_list[0] if caption_list else ''
            img_type = 'raster'
            figure_captions[file_id] = caption

        # Copy image with sequential name
        ext = src_path.suffix or '.jpg'
        dest_name = f'{file_id}{ext}'
        dest_path = images_dir / dest_name
        shutil.copy2(src_path, dest_path)

        local_path = str(dest_path.resolve())
        meta: dict[str, Any] = {
            'id': file_id,
            'local_path': local_path,
            'type': img_type,
            'caption': caption,
        }
        if item_type == 'table':
            table_body = item.get('table_body', '')
            if table_body:
                meta['table_body_html'] = table_body
        images_meta.append(meta)

    # Build manifest entry
    entry_url = source_url or ''
    if not entry_url and pdf_path:
        entry_url = Path(pdf_path).resolve().as_uri()
    full_md_archive = mineru_archive / 'full.md'
    full_md_rel = str(full_md_archive.resolve()) if full_md_archive.exists() else None
    entry: dict[str, Any] = {
        'url': entry_url,
        'slug': slug,
        'success': True,
        'title': title,
        'text_excerpt': text_excerpt,
        'source_type': 'paper_pdf',
        'metrics': {'image_count': len(images_meta), 'table_count': tbl_idx},
        'paper_metadata': {
            'abstract': abstract,
            'full_markdown_path': full_md_rel,
            'figure_captions': figure_captions,
            'table_captions': table_captions,
        },
        'images': images_meta,
        'videos': [],
        'scroll_recording': None,
    }

    # Write per-slug metadata.json
    (slug_dir / 'metadata.json').write_text(
        json.dumps(entry, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    return entry


def update_manifest(output_dir: str, entry: dict[str, Any]) -> dict[str, Any]:
    """Read/create manifest_papers.json and upsert entry by slug. Returns full manifest."""
    manifest_path = os.path.join(output_dir, 'manifest_papers.json')
    manifest: dict[str, Any] = {
        'success': True,
        'entries': [],
        'pending_downloads': [],
    }
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
        except Exception as exc:
            log(f'warning: failed to read existing manifest: {exc}')

    # Dedup by slug (replace existing entry on re-run)
    manifest['entries'] = [e for e in manifest['entries'] if e.get('slug') != entry['slug']]
    manifest['entries'].append(entry)
    manifest['success'] = any(e.get('success') for e in manifest['entries'])

    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    log(f'manifest_papers.json updated ({len(manifest["entries"])} entries)')
    return manifest


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # Validate inputs
    if args.pdf and not os.path.isfile(args.pdf):
        fail(f'PDF file not found: {args.pdf}', exit_code=2)

    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    slug = args.slug or derive_slug(args.url, args.pdf)
    if '/' in slug or '\\' in slug or '..' in slug:
        fail(f'invalid slug (contains path separators or ..): {slug}', exit_code=2)
    log(f'slug={slug} output_dir={output_dir}')

    token = os.environ.get('MINERU_API_TOKEN', '')
    mineru_dir = None
    tmp_root = None
    backend = 'unknown'

    # Try cloud path first
    if token:
        log('attempting cloud extraction...')
        try:
            mineru_dir = run_cloud(args, token)
            tmp_root = mineru_dir
            backend = f'cloud_{args.model_version}'
            log(f'cloud extraction succeeded: {mineru_dir}')
        except Exception as exc:
            log(f'cloud extraction failed: {exc}')
            log('falling back to local CLI...')
            mineru_dir = None

    # Local fallback
    if mineru_dir is None:
        if not token:
            log('MINERU_API_TOKEN not set, using local CLI')
        try:
            mineru_dir, tmp_root = run_local(args)
            backend = f'local_{args.model_version}'
            log(f'local extraction succeeded: {mineru_dir}')
        except Exception as exc:
            fail(f'both cloud and local extraction failed: {exc}')

    # Process output
    try:
        entry = process_mineru_output(
            mineru_dir, output_dir, slug,
            source_url=args.url,
            pdf_path=args.pdf,
        )
    except Exception as exc:
        fail(f'post-processing failed: {exc}')

    # Update manifest
    update_manifest(output_dir, entry)

    # Count figures/tables
    figure_count = sum(1 for img in entry['images'] if img['type'] == 'raster')
    table_count = sum(1 for img in entry['images'] if img['type'] == 'table_screenshot')

    result = {
        'success': True,
        'slug': slug,
        'title': entry['title'],
        'abstract': entry['paper_metadata']['abstract'],
        'full_markdown_path': entry['paper_metadata']['full_markdown_path'],
        'figure_count': figure_count,
        'table_count': table_count,
        'backend': backend,
        'manifest_entry': entry,
    }
    print(json.dumps(result, ensure_ascii=False))
    log(f'done: {figure_count} figures, {table_count} tables')

    # Cleanup temp dirs
    if tmp_root and os.path.realpath(tmp_root).startswith(os.path.realpath(tempfile.gettempdir())):
        shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == '__main__':
    main()
