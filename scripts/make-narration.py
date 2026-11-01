#!/usr/bin/env python3
"""从展示稿与 TTS 词典生成 TTS 旁白稿。

流水线的脚本阶段产出展示稿（`script.txt`，按段落分隔，用于字幕与画面）和词典
（`tts-lexicon.json`，品牌名、数字、年份等的展示形式 -> 读音形式映射）。本脚本
确定性地推导出旁白稿（`narration.txt`），因此需要手写的只有展示稿和词典。

替换规则（确定性）：
  从左到右扫描展示稿。在每个位置，凡展示形式与该位置起始文本相匹配的词典条目
  中，最长（LONGEST）的展示形式获胜。长度相同时按展示形式字符串本身比较决定。
  若没有条目匹配，该字符原样复制。换行与段落结构保持原样。

偏移表（`narration-offsets.json`）：每个旁白字符位置都能映射回展示稿中的位置。
该表是一份有序、连续的段列表，覆盖 [0, len(narration))：

  {"version": 1,
   "script_length": S, "narration_length": N,
   "script_sha256": "...", "narration_sha256": "...",
   "segments": [{"narration_start": a, "narration_end": b,
                 "script_start": c, "script_end": d}]}

  两个哈希是构建该表时所用的那份 script.txt / narration.txt 的 sha256；
  pipeline-status 用它拒绝仅靠字符数看不出来的等长编辑。

  旁白位置 i 映射回
  script_start + min(i - narration_start, script_end - script_start - 1)。

用法：
  python3 scripts/make-narration.py \
    --script {work_dir}/{topic_name}/script.txt \
    --lexicon {work_dir}/{topic_name}/tts-lexicon.json \
    --output-dir {work_dir}/{topic_name}/

  产出（路径由 --output-dir 推导）：
    <output-dir>/narration.txt          TTS 旁白稿
    <output-dir>/narration-offsets.json 偏移表

输出约定：
  stdout : 单个 JSON 对象
    success: {"success": true, "narration_path": "...",
              "offsets_path": "...", "script_length": N,
              "narration_length": N, "replacement_count": N}
    error:   {"success": false, "error": "..."}
  stderr : 带 `[make-narration]` 前缀的人类可读进度
  exit   : 0 成功，1 运行时错误，2 参数非法
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import cli

TOOL_NAME = 'make-narration'
OFFSETS_VERSION = 1

log = cli.make_logger(TOOL_NAME)


def parse_args() -> argparse.Namespace:
    p = cli.JsonArgumentParser(
        TOOL_NAME,
        description='Derive the TTS narration draft from the display draft + lexicon.',
    )
    p.add_argument('--script', required=True, help='Path to the display draft (script.txt).')
    p.add_argument('--lexicon', required=True, help='Path to the TTS lexicon (tts-lexicon.json).')
    p.add_argument('--output-dir', required=True, help='Directory for narration.txt and narration-offsets.json.')
    return p.parse_args()


def load_lexicon(path: Path) -> dict[str, str]:
    """载入并校验词典：一个非空 str -> 非空 str 的 JSON 对象。"""
    if not path.is_file():
        raise FileNotFoundError(f'lexicon file not found: {path}')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'lexicon is not valid JSON: {exc}') from exc
    if not isinstance(data, dict):
        raise ValueError('lexicon root is not a JSON object (display form -> reading form map)')
    lexicon: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError(f'lexicon entries must be strings, got {key!r}: {value!r}')
        if not key or not value:
            raise ValueError(f'lexicon entries must be non-empty strings, got {key!r}: {value!r}')
        lexicon[key] = value
    return lexicon


def build_matches(lexicon: dict[str, str]) -> list[tuple[str, str]]:
    """为确定性扫描排好序的词典条目：
    展示形式长度降序，再按展示形式字符串升序。"""
    return sorted(lexicon.items(), key=lambda kv: (-len(kv[0]), kv[0]))


def render(script_text: str, lexicon: dict[str, str]) -> tuple[str, list[dict[str, int]], int]:
    """确定性地把词典条目替换进展示稿。

    返回 (narration_text, segments, replacement_count)。segments 把连续的旁白
    区间映射回连续的展示稿区间；两侧都包含换行，因此段落结构能对齐。
    """
    matches = build_matches(lexicon)
    narration_chars: list[str] = []
    segments: list[dict[str, int]] = []
    replacement_count = 0

    n = len(script_text)
    i = 0
    seg_n_start = 0
    seg_s_start = 0

    def flush_segment(until_n: int, until_s: int) -> None:
        if until_n > seg_n_start:
            segments.append({
                'narration_start': seg_n_start,
                'narration_end': until_n,
                'script_start': seg_s_start,
                'script_end': until_s,
            })

    while i < n:
        hit: tuple[str, str] | None = None
        for display, reading in matches:
            if script_text.startswith(display, i):
                hit = (display, reading)
                break
        if hit is not None:
            display, reading = hit
            # 替换之前先冲刷掉待定的 1:1 区间
            flush_segment(len(narration_chars), i)
            narration_chars.extend(reading)
            segments.append({
                'narration_start': len(narration_chars) - len(reading),
                'narration_end': len(narration_chars),
                'script_start': i,
                'script_end': i + len(display),
            })
            seg_n_start = len(narration_chars)
            seg_s_start = i + len(display)
            replacement_count += 1
            i += len(display)
        else:
            narration_chars.append(script_text[i])
            i += 1

    flush_segment(len(narration_chars), n)
    return ''.join(narration_chars), segments, replacement_count


def main() -> None:
    args = parse_args()

    script_path = Path(args.script).expanduser()
    lexicon_path = Path(args.lexicon).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    narration_path = output_dir / 'narration.txt'
    offsets_path = output_dir / 'narration-offsets.json'

    if not script_path.is_file():
        raise FileNotFoundError(f'script file not found: {script_path}')
    script_text = script_path.read_text(encoding='utf-8')
    if not script_text.strip():
        raise ValueError(f'script file is empty: {script_path}')

    lexicon = load_lexicon(lexicon_path)
    log(f'Loaded {len(lexicon)} lexicon entries from {lexicon_path}')

    narration_text, segments, replacement_count = render(script_text, lexicon)

    narration_path.write_text(narration_text, encoding='utf-8')
    offsets_payload = {
        'version': OFFSETS_VERSION,
        'script_length': len(script_text),
        'narration_length': len(narration_text),
        # 脚本自身的字节：文本模式读取会翻译换行，因此哈希必须取自文件，
        # 而不是取自解码后的文本。
        'script_sha256': hashlib.sha256(script_path.read_bytes()).hexdigest(),
        'narration_sha256': hashlib.sha256(narration_path.read_bytes()).hexdigest(),
        'segments': segments,
    }
    offsets_path.write_text(
        json.dumps(offsets_payload, indent=2, ensure_ascii=False), encoding='utf-8'
    )

    log(f'Narration written to {narration_path} ({len(narration_text)} chars, '
        f'{replacement_count} replacements)')
    log(f'Offset table written to {offsets_path} ({len(segments)} segments)')

    cli.print_json({
        'success': True,
        'narration_path': str(narration_path),
        'offsets_path': str(offsets_path),
        'script_length': len(script_text),
        'narration_length': len(narration_text),
        'replacement_count': replacement_count,
    })


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
