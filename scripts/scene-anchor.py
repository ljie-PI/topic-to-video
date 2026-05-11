#!/usr/bin/env python3
"""
Map scene IDs to precise audio timestamps by anchoring each scene to a unique
substring in the ASR word stream.

Usage:
  python3 scene-anchor.py <transcript.json> <scenes.json> <output: scene-timing.json>

scenes.json format:
  [
    {"id": "s1-hook",  "anchor": "Anthropic", "display_text": "...optional onscreen text...",
     "material_ref": {"entry_slug": "...", "kind": "image", "asset_id": "img_001"}},
    {"id": "s2-stat",  "anchor": "他说编程问题",
     "material_ref": {"entry_slug": "...", "kind": "video_clip", "asset_id": "vid_xxx", "clip_index": 0}},
    ...
  ]

The anchor is searched IN ORDER through the joined ASR text. Each scene's
begin = the start time of the word at the matched position; end = the begin
of the next scene (last scene ends at the audio end).

Any extra keys per scene (e.g. `material_ref`, `display_text`, custom labels)
are passed through to the output so the downstream composition agent can read
the full scene record from `scene-timing.json` alone.

Output:
  {
    "total_s": 76.6,
    "scenes": [
      {"id": "s1-hook", "begin_ms": 0,    "begin_s": 0.0,  "duration_s": 4.25, ...},
      ...
    ]
  }
"""
import json
import os
import sys


def print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def log(message: str) -> None:
    print(f'[scene-anchor] {message}', file=sys.stderr)


def main() -> int:
    if len(sys.argv) != 4:
        message = 'Usage: scene-anchor.py <transcript.json> <scenes.json> <output.json>'
        log(message)
        print_json({'success': False, 'error': message})
        return 2

    try:
        transcript_path, scenes_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

        with open(transcript_path, encoding='utf-8') as f:
            sentences = json.load(f)

        words = []
        for sentence in sentences:
            for word in sentence['words']:
                words.append(
                    {
                        'text': word['text'].strip(),
                        'begin': word['begin'],
                        'end': word['end'],
                    }
                )
        if not words:
            raise ValueError('transcript has no words')

        char_to_word = []
        chars = []
        for index, word in enumerate(words):
            for char in word['text']:
                if char.strip():
                    chars.append(char)
                    char_to_word.append(index)
        joined = ''.join(chars)
        joined_lower = joined.lower()
        log(f'transcript = {len(joined)} chars, {len(words)} words')

        with open(scenes_path, encoding='utf-8') as f:
            scenes = json.load(f)

        results = []
        warnings = []
        cursor = 0
        for scene in scenes:
            anchor = scene['anchor']
            anchor_lower = anchor.lower()
            idx = joined_lower.find(anchor_lower, cursor)
            if idx == -1:
                short = anchor_lower[:max(2, len(anchor_lower) // 2)]
                idx = joined_lower.find(short, cursor)
                if idx == -1:
                    warning = f'anchor not found for {scene["id"]!r}: {anchor!r}'
                    warnings.append(warning)
                    log(f'warning: {warning}')
                    continue
            word_idx = char_to_word[idx]
            begin_ms = words[word_idx]['begin']
            result = dict(scene)
            result.update(
                {
                    'matched_text': joined[idx:idx + len(anchor)],
                    'matched_at_char': idx,
                    'matched_word_index': word_idx,
                    'begin_ms': begin_ms,
                    'begin_s': round(begin_ms / 1000, 3),
                }
            )
            results.append(result)
            cursor = idx + len(anchor)

        total_ms = words[-1]['end']
        for index, result in enumerate(results):
            next_begin = results[index + 1]['begin_ms'] if index + 1 < len(results) else total_ms
            result['end_ms'] = next_begin
            result['duration_s'] = round((next_begin - result['begin_ms']) / 1000, 3)
            if index + 1 < len(results):
                result['duration_s'] = round(result['duration_s'] - 0.001, 3)
            log(
                f'{result["id"]:14s} begin={result["begin_s"]:6.2f}s '
                f'dur={result["duration_s"]:5.2f}s'
            )

        out = {'total_s': round(total_ms / 1000, 3), 'scenes': results}
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        log(f'wrote {out_path}')
        print_json(
            {
                'success': True,
                'output_path': os.path.abspath(out_path),
                'scenes_anchored': len(results),
                'warnings': warnings,
            }
        )
        return 0
    except Exception as exc:
        log(f'error: {exc}')
        print_json({'success': False, 'error': str(exc)})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
