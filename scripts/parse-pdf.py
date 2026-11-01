#!/usr/bin/env python3
"""基于 MinerU 的 PDF 论文解析器，输出与 harvest-manifest 兼容的结果。

以 MinerU 云 API 为主、本地 CLI 作为兜底，从学术 PDF 中抽取图、表、图表和完整的
markdown。

用法：
  python3 scripts/parse-pdf.py --url https://arxiv.org/pdf/2605.03675 \\
    --output-dir ./harvest_page/ --slug main-paper

  python3 scripts/parse-pdf.py --pdf /path/to/paper.pdf \\
    --output-dir ./harvest_page/ --slug main-paper

依赖：
  export MINERU_API_TOKEN="..."   （走云端路径时）
  或 PATH 上有 `mineru` CLI      （走本地兜底时）

输出约定：
  stdout : 带 metadata + manifest entry 的 JSON 结果
  stderr : 带 [parse-pdf] 前缀的人类可读进度
  exit   : 0 成功，1 运行时错误，2 参数非法
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

import cli
import harvest_manifest

TOOL_NAME = 'parse-pdf'
POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 300
API_BASE = 'https://mineru.net/api/v4'


# ---------------------------------------------------------------------------
# I/O 辅助函数
# ---------------------------------------------------------------------------

log = cli.make_logger(TOOL_NAME)


def parse_args() -> argparse.Namespace:
    p = cli.JsonArgumentParser(TOOL_NAME, description='MinerU PDF paper parser.')
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--url', help='Public URL to a PDF.')
    group.add_argument('--pdf', help='Local path to a PDF file.')
    p.add_argument('--output-dir', required=True, help='harvest_page directory.')
    p.add_argument('--slug', default=None, help='Slug for output subdirectory (auto-derived if omitted).')
    p.add_argument('--model-version', default='vlm', help='MinerU model version (default: vlm).')
    return p.parse_args()


# ---------------------------------------------------------------------------
# 云 API 辅助函数
# ---------------------------------------------------------------------------

def cloud_headers(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


def cloud_extract_url(url: str, token: str, model_version: str) -> str:
    """提交一个 URL 抽取任务。返回 task_id。"""
    import requests

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
    """上传本地文件并提交抽取。返回 task_id。"""
    import requests

    filename = os.path.basename(pdf_path)

    # 步骤 1：获取预签名的上传 URL
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

    # 步骤 2：把文件上传到预签名 URL
    oss_url = file_urls[0]
    log(f'uploading {filename} to cloud storage...')
    with open(pdf_path, 'rb') as f:
        put_resp = requests.put(oss_url, data=f, timeout=120)
    put_resp.raise_for_status()
    log('upload complete')

    # 步骤 3：提交批量抽取
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
    """轮询直到任务完成或超时。返回任务结果数据。"""
    import requests

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
    """下载并解压云端结果。返回解压后输出目录的路径。"""
    import requests

    zip_url = task_data.get('full_zip_url')
    if not zip_url:
        raise RuntimeError(f'no full_zip_url in task data: {task_data}')
    log('downloading result zip...')
    resp = requests.get(zip_url, timeout=120, stream=True)
    resp.raise_for_status()
    zip_path = os.path.join(dest_dir, 'result.zip')
    size = 0
    with open(zip_path, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            size += len(chunk)
    log(f'downloaded {size} bytes, extracting...')
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.namelist():
            resolved = os.path.realpath(os.path.join(dest_dir, member))
            if not resolved.startswith(os.path.realpath(dest_dir) + os.sep) and resolved != os.path.realpath(dest_dir):
                raise RuntimeError(f'zip entry escapes dest_dir: {member}')
        zf.extractall(dest_dir)
    os.remove(zip_path)
    return dest_dir


# ---------------------------------------------------------------------------
# 云端路径（首选）
# ---------------------------------------------------------------------------

def run_cloud(args: argparse.Namespace, token: str) -> str:
    """运行云端抽取。返回 MinerU 输出目录的路径。"""
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
        # 失败时做清理，避免兜底运行时留下临时目录
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


# ---------------------------------------------------------------------------
# 本地兜底
# ---------------------------------------------------------------------------

def run_local(args: argparse.Namespace) -> tuple:
    """运行本地 mineru CLI。返回 (output_dir, tmp_root) 供清理使用。"""
    if not shutil.which('mineru'):
        raise RuntimeError('mineru CLI not found on PATH')

    tmp_dir = tempfile.mkdtemp(prefix='mineru-local-')
    try:
        pdf_path = args.pdf

        # 若给的是 URL，先下载 PDF
        if args.url:
            import requests

            log(f'downloading PDF from {args.url}...')
            resp = requests.get(args.url, timeout=120, stream=True)
            resp.raise_for_status()
            pdf_path = os.path.join(tmp_dir, 'input.pdf')
            size = 0
            with open(pdf_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    size += len(chunk)
            log(f'downloaded {size} bytes')

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

        # MinerU 本地输出位于 {tmp_dir}/{pdf_stem}/auto/
        pdf_stem = Path(pdf_path).stem
        auto_dir = os.path.join(tmp_dir, pdf_stem, 'auto')
        output_dir = auto_dir if os.path.isdir(auto_dir) else tmp_dir
        return output_dir, tmp_dir
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


# ---------------------------------------------------------------------------
# 处理：MinerU 输出 -> harvest 格式
# ---------------------------------------------------------------------------

def find_content_list(mineru_dir: str) -> str | None:
    """在 MinerU 输出中查找 *_content_list.json（带 UUID 前缀）。"""
    matches = glob.glob(os.path.join(mineru_dir, '**', '*_content_list.json'), recursive=True)
    return matches[0] if matches else None


def find_full_md(mineru_dir: str) -> str | None:
    """在 MinerU 输出中查找 full.md。"""
    matches = glob.glob(os.path.join(mineru_dir, '**', 'full.md'), recursive=True)
    return matches[0] if matches else None


def extract_title(md_text: str) -> str:
    """从第一个 # 标题中提取标题。"""
    m = re.search(r'^#\s+(.+)$', md_text, re.MULTILINE)
    return m.group(1).strip() if m else ''


def extract_abstract(md_text: str) -> str:
    """提取 # Abstract 与下一个 # 标题之间的文本。"""
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
    """把 MinerU 输出处理成 harvest 兼容格式。返回 manifest entry。"""
    from PIL import Image

    output_path = Path(output_dir)
    slug_dir = output_path / slug
    images_dir = slug_dir / 'images'
    images_dir.mkdir(parents=True, exist_ok=True)

    # 把完整的 MinerU 原始输出保留在它所产出条目的旁边。
    mineru_archive = slug_dir / 'mineru'
    if Path(mineru_dir).resolve() != mineru_archive.resolve():
        shutil.copytree(mineru_dir, mineru_archive, dirs_exist_ok=True)
    mineru_dir = str(mineru_archive)

    # 定位关键文件
    content_list_path = find_content_list(mineru_dir)
    full_md_path = find_full_md(mineru_dir)

    if not content_list_path and not full_md_path:
        raise RuntimeError(f'MinerU output missing both full.md and content_list.json in {mineru_dir}')

    md_text = ''
    if full_md_path:
        with open(full_md_path, 'r', encoding='utf-8', errors='replace') as f:
            md_text = f.read()

    content_list: list[dict[str, Any]] = []
    if content_list_path:
        with open(content_list_path, 'r', encoding='utf-8', errors='replace') as f:
            content_list = json.load(f)

    title = extract_title(md_text)
    abstract = extract_abstract(md_text)
    text_excerpt = abstract[:2000] if abstract else md_text[:2000]

    # 处理图、表、图表
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

        # 确定源图片路径
        img_path_raw = item.get('img_path', '')
        if not img_path_raw:
            continue
        # img_path 可能是相对于 MinerU 输出目录的路径
        src_path = Path(img_path_raw)
        if not src_path.is_absolute():
            src_path = Path(mineru_dir) / img_path_raw
        if not src_path.exists():
            log(f'  image not found: {src_path}')
            continue

        # 确定 caption
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
        else:  # 图表
            chart_idx += 1
            file_id = f'chart_{chart_idx:03d}'
            caption_list = item.get('chart_caption', [])
            if not isinstance(caption_list, list):
                caption_list = [caption_list] if caption_list else []
            caption = caption_list[0] if caption_list else ''
            img_type = 'raster'
            figure_captions[file_id] = caption

        # 以顺序命名的文件名复制图片
        ext = src_path.suffix or '.jpg'
        dest_name = f'{file_id}{ext}'
        dest_path = images_dir / dest_name
        shutil.copy2(src_path, dest_path)

        with Image.open(dest_path) as image:
            width, height = image.size
        meta: dict[str, Any] = {
            'id': file_id,
            'local_path': dest_path.relative_to(output_path).as_posix(),
            'type': img_type,
            'caption': caption,
            'width': width,
            'height': height,
        }
        if item_type == 'table':
            table_body = item.get('table_body', '')
            if table_body:
                meta['table_body_html'] = table_body
        images_meta.append(meta)

    # 构建 manifest entry
    entry_url = source_url or ''
    if not entry_url and pdf_path:
        entry_url = Path(pdf_path).resolve().as_uri()
    full_md_archive = Path(full_md_path) if full_md_path else None
    full_md_rel = full_md_archive.relative_to(output_path).as_posix() if full_md_archive else None
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

    return entry


def update_manifest(output_dir: str, entry: dict[str, Any]) -> dict[str, Any]:
    """通过共享的 v2 manifest 写入器做 upsert。"""
    manifest = harvest_manifest.upsert_entries(output_dir, [entry])
    log(f'manifest.json updated ({len(manifest["entries"])} entries)')
    return manifest


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # 校验输入
    if args.pdf and not os.path.isfile(args.pdf):
        cli.fail(TOOL_NAME, f'PDF file not found: {args.pdf}', exit_code=2)

    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    slug = args.slug or harvest_manifest.slug_for_pdf(args.url, args.pdf)
    if '/' in slug or '\\' in slug or '..' in slug:
        cli.fail(TOOL_NAME, f'invalid slug (contains path separators or ..): {slug}', exit_code=2)
    log(f'slug={slug} output_dir={output_dir}')

    token = os.environ.get('MINERU_API_TOKEN', '')
    mineru_dir = None
    tmp_root = None
    backend = 'unknown'

    # 优先尝试云端路径
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

    # 本地兜底
    if mineru_dir is None:
        if not token:
            log('MINERU_API_TOKEN not set, using local CLI')
        try:
            mineru_dir, tmp_root = run_local(args)
            backend = 'local_pipeline'
            log(f'local extraction succeeded: {mineru_dir}')
        except Exception as exc:
            cli.fail(TOOL_NAME, f'both cloud and local extraction failed: {exc}')

    # 处理输出
    try:
        entry = process_mineru_output(
            mineru_dir, output_dir, slug,
            source_url=args.url,
            pdf_path=args.pdf,
        )
    except Exception as exc:
        cli.fail(TOOL_NAME, f'post-processing failed: {exc}')

    # 更新 manifest
    update_manifest(output_dir, entry)

    # 统计图 / 表数量
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
    cli.print_json(result)
    log(f'done: {figure_count} figures, {table_count} tables')

    # 清理临时目录
    if tmp_root and os.path.realpath(tmp_root).startswith(os.path.realpath(tempfile.gettempdir())):
        shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
