#!/usr/bin/env python3
"""Parse SRT/VTT subtitle files and print JSON.

Usage:
  python3 subtitle-parse.py subtitles.srt
  python3 subtitle-parse.py subtitles.vtt --keywords "AI,machine learning"
"""

import argparse
import json
import os
import re
import sys

TIMESTAMP_RE = re.compile(r'^([\d:.,]+)\s*-->\s*([\d:.,]+)')
HTML_TAG_RE = re.compile(r'<[^>]+>')
BLOCK_SPLIT_RE = re.compile(r'\n\n+')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Parse SRT/VTT subtitle files and print JSON.')
    parser.add_argument('file_path', help='Path to a .srt or .vtt subtitle file')
    parser.add_argument(
        '--keywords',
        help='Comma-separated keywords for case-insensitive filtering',
    )
    return parser.parse_args()



def normalize_timestamp(value: str) -> str:
    return value.replace(',', '.')



def timestamp_to_seconds(value: str) -> float:
    normalized = normalize_timestamp(value)
    parts = normalized.split(':')
    if len(parts) != 3:
        raise ValueError(f'Invalid timestamp: {value}')
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds



def strip_html(text: str) -> str:
    return HTML_TAG_RE.sub('', text).strip()



def parse_block(block: str) -> dict | None:
    lines = [line.strip() for line in block.split('\n') if line.strip()]
    if len(lines) < 2:
        return None

    index_line = lines[0]
    timestamp_line = lines[1]
    text_lines = lines[2:]

    if not index_line.isdigit():
        if TIMESTAMP_RE.match(index_line):
            timestamp_line = index_line
            text_lines = lines[1:]
            index_value = None
        else:
            return None
    else:
        index_value = int(index_line)

    match = TIMESTAMP_RE.match(timestamp_line)
    if not match:
        return None

    start_time = normalize_timestamp(match.group(1))
    end_time = normalize_timestamp(match.group(2))
    text = '\n'.join(strip_html(line) for line in text_lines).strip()

    return {
        'index': index_value,
        'start_time': start_time,
        'end_time': end_time,
        'start_seconds': timestamp_to_seconds(match.group(1)),
        'end_seconds': timestamp_to_seconds(match.group(2)),
        'text': text,
    }



def parse_srt(content: str) -> list[dict]:
    entries = []
    for block in BLOCK_SPLIT_RE.split(content.strip()):
        if not block.strip():
            continue
        entry = parse_block(block)
        if entry is not None:
            entries.append(entry)
    for i, entry in enumerate(entries, start=1):
        if entry['index'] is None:
            entry['index'] = i
    return entries



def parse_vtt(content: str) -> list[dict]:
    content = content.lstrip('\ufeff')
    if content.startswith('WEBVTT'):
        lines = content.split('\n')
        start_index = 1
        while start_index < len(lines) and lines[start_index].strip():
            start_index += 1
        content = '\n'.join(lines[start_index + 1:])
    return parse_srt(content)



def filter_entries(entries: list[dict], keywords_arg: str | None) -> tuple[list[dict], list[str]]:
    if not keywords_arg:
        return entries, []

    keywords = [keyword.strip().lower() for keyword in keywords_arg.split(',') if keyword.strip()]
    if not keywords:
        return entries, []

    filtered = [
        entry for entry in entries
        if any(keyword in entry['text'].lower() for keyword in keywords)
    ]
    return filtered, keywords



def parse_file(file_path: str) -> list[dict]:
    ext = os.path.splitext(file_path)[1].lower()
    with open(file_path, encoding='utf-8') as file:
        content = file.read().replace('\r\n', '\n').replace('\r', '\n')

    if ext == '.srt':
        return parse_srt(content)
    if ext == '.vtt':
        return parse_vtt(content)
    raise ValueError('Unsupported subtitle format. Use .srt or .vtt files.')



def main() -> None:
    args = parse_args()

    try:
        entries = parse_file(args.file_path)
    except FileNotFoundError:
        print(json.dumps({'error': f'File not found: {args.file_path}'}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    filtered_entries, keywords = filter_entries(entries, args.keywords)

    output = {
        'total_entries': len(entries),
        'entries': filtered_entries,
    }
    if keywords:
        output['matched_entries'] = len(filtered_entries)

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
