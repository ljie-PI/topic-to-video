"""
Map scene IDs to precise audio timestamps by anchoring each scene to a unique
substring in the ASR word stream.

Usage:
  python3 scene-anchor.py <transcript.json> <scenes.json> <output: scene-timing.json>

scenes.json format:
  [
    {"id": "s1-hook",  "anchor": "Anthropic", "display": "...optional onscreen text..."},
    {"id": "s2-stat",  "anchor": "他说编程问题"},
    ...
  ]

The anchor is searched IN ORDER through the joined ASR text. Each scene's
begin = the start time of the word at the matched position; end = the begin
of the next scene (last scene ends at the audio end).

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
import sys


def main():
    if len(sys.argv) != 4:
        print('Usage: scene-anchor.py <transcript.json> <scenes.json> <output.json>')
        sys.exit(2)

    transcript_path, scenes_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

    with open(transcript_path, encoding='utf-8') as f:
        sentences = json.load(f)

    # Flatten word stream
    words = []
    for s in sentences:
        for w in s['words']:
            words.append({
                'text': w['text'].strip(),
                'begin': w['begin'],
                'end': w['end'],
            })
    if not words:
        print('ERR: transcript has no words')
        sys.exit(1)

    # Build clean joined text + per-char index → word index
    # Note: lowercase joined text — Paraformer normalizes English to lowercase,
    # so anchors should be matched case-insensitively.
    char_to_word = []
    chars = []
    for i, w in enumerate(words):
        for c in w['text']:
            if c.strip():
                chars.append(c)
                char_to_word.append(i)
    joined = ''.join(chars)
    joined_lower = joined.lower()
    print(f'[anchor] transcript = {len(joined)} chars, {len(words)} words')

    with open(scenes_path, encoding='utf-8') as f:
        scenes = json.load(f)

    results = []
    cursor = 0
    for scene in scenes:
        anchor = scene['anchor']
        anchor_lower = anchor.lower()
        idx = joined_lower.find(anchor_lower, cursor)
        if idx == -1:
            # Try a shorter softer search
            short = anchor_lower[:max(2, len(anchor_lower) // 2)]
            idx = joined_lower.find(short, cursor)
            if idx == -1:
                print(f'WARN: anchor not found for {scene["id"]!r}: {anchor!r}')
                continue
        word_idx = char_to_word[idx]
        begin_ms = words[word_idx]['begin']
        results.append({
            'id': scene['id'],
            'anchor': anchor,
            'matched_text': joined[idx:idx + len(anchor)],
            'matched_at_char': idx,
            'matched_word_index': word_idx,
            'begin_ms': begin_ms,
            'begin_s': round(begin_ms / 1000, 3),
            'display': scene.get('display'),
        })
        cursor = idx + len(anchor)

    # Compute durations
    total_ms = words[-1]['end']
    for i, r in enumerate(results):
        next_begin = results[i + 1]['begin_ms'] if i + 1 < len(results) else total_ms
        r['end_ms'] = next_begin
        r['duration_s'] = round((next_begin - r['begin_ms']) / 1000, 3)
        # Subtract a hair off the duration to avoid 0.001s float overlap on the
        # next scene's start when both live on the same hyperframes track.
        if i + 1 < len(results):
            r['duration_s'] = round(r['duration_s'] - 0.001, 3)
        print(f'  {r["id"]:14s} begin={r["begin_s"]:6.2f}s dur={r["duration_s"]:5.2f}s')

    out = {'total_s': round(total_ms / 1000, 3), 'scenes': results}
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\n✓ wrote {out_path}')


if __name__ == '__main__':
    main()
