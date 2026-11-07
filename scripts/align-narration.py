#!/usr/bin/env python3
"""把 ASR 转写对齐到旁白稿，并在需要时构建字幕单元。

两个明确的输出模式，共享同一套对齐核心（字符映射、ASR 归一化、段落 / cue
定位、字幕分段）：

  --mode timing     只生成时间轴（paragraphs / scenes / cues）。不读 layout，
                    不要求字幕宽度 / 字号 / 行数，不产生字幕单元。
  --mode subtitles  按最终 layout 或视觉 scenes 的字幕规格切分字幕单元，写到指定路径。
                    不覆写 Phase 7 的时间轴。

两个模式读同一份显示稿、朗读稿、偏移表和 fresh transcript，所以能在不改音频、
不重做识别的前提下重算其中任何一个。生产调用必须明确给出 mode；无 mode 或模式与
参数组合不合法时返回参数错误，不做隐式推断。

输入：
  --transcript   transcribe/transcript.json —— 稳定的 ASR schema：一个句子列表，
                 每个句子 {begin, end, text, words:[{text, begin, end}]}，时间
                 为毫秒。词 token 可能带标点，也可能把词任意切开。
  --narration    narration.txt —— TTS 旁白稿（实际朗读出来的内容）。
  --offsets      narration-offsets.json —— 逐字符地把旁白位置映射回展示稿位置的
                 表，由 make-narration.py 产出。版本、两个字数与两个内容哈希都是
                 必需字段。
  --script       script.txt —— 展示稿（字幕文本来源）。
  --width / --font-size / --max-lines
                 字幕区域参数（仅 --mode subtitles）：以 CJK 单位计的单行宽度上限
                 是 int(width / font_size)；一个单元最多可占 --max-lines 行
                 （竖屏允许 2）。给出 --layout 时忽略。
  --layout       版面区域定义 JSON（layouts/*.json）的路径（仅 --mode subtitles）；
                 caption 规格取自其 `caption` 对象
                 （{width_px, font_size_px, max_lines}）。
                 --layout 与那三个显式参数二者必居其一。
  --scene-config   Phase 8 composition/scene-config.json（仅 subtitles）：按每个
                 视觉 scene 落盘的 caption 规格计算字幕预算；与 --layout /
                 显式参数互斥。
  --narration-audio
                 视觉 scene 配置的实际配音文件，用于校验 total_s 与实际配音
                 时长一致（含语音前后静音画面）。
  --scene-plan   可选的场景规划 JSON；scene 带 `cues` 时，它们的秒数会写进
                 timeline.json。`scene_id` / `paragraphs` / `cues` 是全部被读取的
                 字段，所以 composition 自己的 cue 声明也能直接传给这个参数。已
                 移除的字段（template_scene / pattern_hints / beats）会被拒绝。

对齐：
  两侧都做归一化（NFKC、转小写、只留字母数字、中文数字 -> 阿拉伯数字），再用
  字符级 SequenceMatcher 对齐。相等的块通过偏移表把旁白字符映射回展示稿，因此
  品牌名和数字会以展示形式重新出现。转写中没有旁白对应的区域（TTS 多读了文本，
  或该区域失真到无法对齐）保留 ASR 文本。没有音频的旁白区域（TTS 跳过了文本）
  会被丢弃并给出警告。

兜底标记：
  transcript schema 没有置信度字段，因此“低置信度”由对齐本身定义：包含来自未
  对齐区域的 ASR 文本的单元带 `"fallback": true`；已对齐的单元为
  `fallback: false`。计数汇总在 `summary.fallback_units` 中。

切分（仅 --mode subtitles）：
  - 先按句末标点切（。！？!?…，以及不在词 / 数字内部的拉丁 .!?）；
  - 去掉每个单元结尾的 ，和 。，保留 ？！；
  - 宽于上限的单元在 ，,；;、：:—— 处断开；断点绝不落在英文词或数字内部
    （禁止在两个拉丁 token 字符之间断开）；
  - 过短的尾部片段（窄于 max(2, 0.2 * cap)）会被重新平衡一次：在离两者中点最近
    的断点处把最后两段重新切开；
  - 短于 0.6 s 的单元并入相邻单元（有前一个就并到前一个）；合并后的单元可能
    超出宽度上限，但与字幕闪烁相比这是较小的恶。

产出（路径来自 --units-output / --timeline-output；只写当前 mode 属于它的那份）：
  subtitle-units.json : {"version": 1, "units": [...], "summary": {...}}
    每个单元：{index, text, begin_ms, end_ms, begin_s, end_s, fallback,
    paragraph} —— 其中 text / begin_s / end_s 字段保持既有的下游字幕单元契约。
    视觉 scenes 模式另含 caption_segments，供组件与 QA 消费同一组派生边界。
  timeline.json : {"version": 1, "total_s", "paragraphs": [{index, begin_s,
    end_s}]}；带 --scene-plan 时还会加上 "scenes" 列表 [{scene_id, begin_s,
    end_s}]（场景边界由各 scene 覆盖的段落推导），以及 "cues" 列表
    [{scene_id, cue, begin_s, end_s}]（无法定位的 scenes / cues 会作为警告
    报告并省略）。

输出约定：
  stdout : 一个 JSON 对象
    success: {"success": true, "mode": ..., "<timeline|units>_path": ...,
              "summary": {...}}
    error:   {"success": false, "error": "..."}
  stderr : 带 [align-narration] 前缀的人类可读日志
  exit   : 0 成功，1 运行时错误，2 参数非法
"""
from __future__ import annotations

import argparse
import bisect
import difflib
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import cli
import media
import scene_config
import video_contract
from script_text import paragraph_spans

TOOL_NAME = 'align-narration'

CHINESE_DIGITS = {
    '零': 0,
    '〇': 0,
    '一': 1,
    '二': 2,
    '两': 2,
    '三': 3,
    '四': 4,
    '五': 5,
    '六': 6,
    '七': 7,
    '八': 8,
    '九': 9,
}
CHINESE_SMALL_UNITS = {'十': 10, '百': 100, '千': 1000}
CHINESE_BIG_UNITS = {'万': 10000, '亿': 100000000}
CHINESE_NUMBER_CHARS = set(CHINESE_DIGITS) | set(CHINESE_SMALL_UNITS) | set(CHINESE_BIG_UNITS)

SENTENCE_FINAL_CHARS = set('。！？!?…')
TRAILING_STRIP_CHARS = {'，', ',', '。'}
SOFT_BREAK_CHARS = {'，', ',', '；', ';', '、', '：', ':', '—', '–', '-'}
MIN_UNIT_MS = 600


@dataclass
class Word:
    text: str
    begin: int
    end: int


@dataclass
class Atom:
    """一个带时间的展示字符（atoms 就是切分的最小单位）。

    borrowed=True 标记那些继承了相邻已对齐字符时间的标点 / 空格 atom；单元边界
    会忽略它们，因此以空格开头的单元不会与前一个单元重叠。
    """

    text: str
    begin_ms: int
    end_ms: int
    fallback: bool
    paragraph: int
    borrowed: bool = False


log = cli.make_logger(TOOL_NAME)
print_json = cli.print_json


def parse_args() -> argparse.Namespace:
    parser = cli.JsonArgumentParser(
        TOOL_NAME,
        description='Align transcript timing onto the display draft, in exactly one output mode.',
    )
    parser.add_argument(
        '--mode',
        required=True,
        choices=('timing', 'subtitles'),
        help=(
            'timing: write timeline.json only (no layout, no caption spec); '
            'subtitles: write subtitle units for the given layout, never the timeline.'
        ),
    )
    parser.add_argument('--transcript', required=True, help='Path to transcribe/transcript.json')
    parser.add_argument('--narration', required=True, help='Path to narration.txt (the TTS narration draft)')
    parser.add_argument('--offsets', required=True, help='Path to narration-offsets.json (from make-narration)')
    parser.add_argument('--script', required=True, help='Path to script.txt (the display draft)')
    parser.add_argument(
        '--units-output',
        default=None,
        help='Output path for subtitle units (default: <transcript dir>/subtitle-units.json); subtitles mode only.',
    )
    parser.add_argument(
        '--timeline-output',
        default=None,
        help='Output path for timeline.json (default: <transcript dir>/timeline.json); timing mode only.',
    )
    parser.add_argument('--width', type=int, default=None, help='Subtitle area width in px (default: none; see --layout).')
    parser.add_argument('--font-size', type=int, default=None, help='Subtitle font size in px (default: none; see --layout).')
    parser.add_argument('--max-lines', type=int, default=None, help='Maximum subtitle lines per unit (default: none; see --layout).')
    parser.add_argument(
        '--layout',
        default=None,
        help='Path to a layout region definition JSON (layouts/*.json); its caption spec overrides --width/--font-size/--max-lines.',
    )
    parser.add_argument(
        '--scene-plan',
        default=None,
        help='Optional scene plan JSON with per-scene cues; enables their seconds in timeline.json.',
    )
    parser.add_argument(
        '--scene-config',
        default=None,
        help='Phase 8 composition/scene-config.json; applies each visual scene caption spec to subtitles.',
    )
    parser.add_argument(
        '--narration-audio',
        default=None,
        help='Narration media used for visual-scene coverage (default: <workspace>/voice_clone/narration.mp3).',
    )
    args = parser.parse_args()
    caption_given = [args.width, args.font_size, args.max_lines, args.layout, args.scene_config]
    explicit = [args.width, args.font_size, args.max_lines]
    if any(value is not None and value <= 0 for value in explicit[:2]) or (
        args.max_lines is not None and args.max_lines < 1
    ):
        parser.error('--width and --font-size must be positive, --max-lines must be >= 1')
    if args.mode == 'timing':
        # 字幕容量属于 subtitles 模式：timing 不按字幕预算做任何事，所以它也不
        # 接受这类参数，以免看起来像是按宽度算过时间轴。
        if any(value is not None for value in caption_given):
            parser.error(
                '--mode timing takes no caption spec (--layout / --scene-config / --width / '
                '--font-size / --max-lines); subtitle layout belongs to --mode subtitles'
            )
        if args.units_output is not None:
            parser.error('--mode timing writes the timeline only; drop --units-output')
        if args.narration_audio is not None:
            parser.error('--narration-audio belongs to --mode subtitles --scene-config')
    else:
        if args.scene_config is not None:
            if args.layout is not None or any(value is not None for value in explicit):
                parser.error('--scene-config is mutually exclusive with --layout/--width/--font-size/--max-lines')
        elif args.layout is None and any(value is None for value in explicit):
            parser.error('--mode subtitles needs a caption spec: pass --scene-config, --layout <path.json> or all of --width/--font-size/--max-lines')
        if args.scene_config is None and args.narration_audio is not None:
            parser.error('--narration-audio requires --scene-config')
        if args.timeline_output is not None:
            parser.error(
                '--mode subtitles writes subtitle units only; the timeline belongs to --mode timing'
            )
    return args


def read_text(path: str) -> str:
    """原始读取：旁白 / 脚本的位置必须与偏移表完全一致。"""
    with open(path, encoding='utf-8') as file:
        return file.read()


def as_int_ms(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{label} is not a numeric timestamp: {value!r}')
    return int(round(value))


def load_transcript(path: str) -> list[Word]:
    with open(path, encoding='utf-8') as file:
        data = json.load(file)
    if not isinstance(data, list) or not data:
        raise ValueError('transcript root must be a non-empty list of sentence objects')
    words: list[Word] = []
    for sentence_index, sentence in enumerate(data, start=1):
        if not isinstance(sentence, dict):
            raise ValueError(f'transcript sentence {sentence_index} is not an object')
        raw_words = sentence.get('words')
        if not isinstance(raw_words, list) or not raw_words:
            raise ValueError(f'transcript sentence {sentence_index} has no word timestamps')
        for word_index, raw_word in enumerate(raw_words, start=1):
            if not isinstance(raw_word, dict):
                raise ValueError(f'sentence {sentence_index} word {word_index} is not an object')
            text = str(raw_word.get('text') or '').strip()
            if not text:
                continue
            begin = as_int_ms(raw_word.get('begin'), f'sentence {sentence_index} word {word_index}.begin')
            end = as_int_ms(raw_word.get('end'), f'sentence {sentence_index} word {word_index}.end')
            if end < begin:
                raise ValueError(f'sentence {sentence_index} word {word_index} has end before begin')
            words.append(Word(text=text, begin=begin, end=end))
    if not words:
        raise ValueError('transcript has no non-empty words')
    return words


# --- 归一化（连续中文数字 -> 阿拉伯数字） ------------------------------------


def parse_chinese_number(text: str) -> int | None:
    if not text:
        return None
    if all(char in CHINESE_DIGITS for char in text):
        return int(''.join(str(CHINESE_DIGITS[char]) for char in text))

    total = 0
    section = 0
    number = 0
    seen = False
    for char in text:
        if char in CHINESE_DIGITS:
            number = CHINESE_DIGITS[char]
            seen = True
        elif char in CHINESE_SMALL_UNITS:
            unit = CHINESE_SMALL_UNITS[char]
            section += (number or 1) * unit
            number = 0
            seen = True
        elif char in CHINESE_BIG_UNITS:
            unit = CHINESE_BIG_UNITS[char]
            section += number
            total += (section or 1) * unit
            section = 0
            number = 0
            seen = True
        else:
            return None
    if not seen:
        return None
    return total + section + number


def append_normalized_number(
    chars: list[str],
    mapping: list[int],
    number_text: str,
    source_start: int,
    source_len: int,
) -> None:
    if not number_text:
        return
    if len(number_text) == 1:
        chars.append(number_text)
        mapping.append(source_start)
        return
    for index, char in enumerate(number_text):
        source_offset = round(index * (source_len - 1) / max(1, len(number_text) - 1))
        chars.append(char)
        mapping.append(source_start + source_offset)


def normalize_with_map(text: str) -> tuple[str, list[int]]:
    """转小写、只留字母数字的字符流；连续的中文数字转成阿拉伯数字。

    返回 (normalized_text, mapping)，其中 mapping[i] 是产出第 i 个归一化字符的
    源字符下标。
    """
    chars: list[str] = []
    mapping: list[int] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char in CHINESE_NUMBER_CHARS:
            end = index + 1
            while end < len(text) and text[end] in CHINESE_NUMBER_CHARS:
                end += 1
            number_value = parse_chinese_number(text[index:end])
            if number_value is not None:
                append_normalized_number(chars, mapping, str(number_value), index, end - index)
                index = end
                continue

        normalized = unicodedata.normalize('NFKC', char).lower()
        for normalized_char in normalized:
            if normalized_char.isalnum():
                chars.append(normalized_char)
                mapping.append(index)
        index += 1
    return ''.join(chars), mapping


def is_latin_token_char(char: str) -> bool:
    return char.isascii() and (char.isalnum() or char in '+._/-')


def is_cjk(char: str) -> bool:
    return (
        '㐀' <= char <= '䶿'
        or '一' <= char <= '鿿'
        or '豈' <= char <= '﫿'
    )


# --- 输入 --------------------------------------------------------------------


def load_caption_spec(args: argparse.Namespace) -> tuple[int, int, int]:
    """解析出字幕宽度 / 字号 / 最大行数。

    --layout 优先于显式参数；没有 --layout 时三个显式参数都必须给出（在
    parse_args 中强制）。layout 文件是带 `caption` 对象的区域定义：
    {width_px, font_size_px, max_lines}。
    """
    if args.layout is not None:
        with open(args.layout, encoding='utf-8') as file:
            layout = json.load(file)
        if not isinstance(layout, dict) or isinstance(layout.get('caption'), dict) is False:
            raise ValueError(f'layout file {args.layout} has no caption object')
        if 'canvases' in layout:
            raise ValueError('multi-canvas layout file; pass a single-canvas variant JSON')
        caption = layout['caption']
        try:
            width = int(caption['width_px'])
            font_size = int(caption['font_size_px'])
            max_lines = int(caption['max_lines'])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f'layout caption spec must be width_px/font_size_px/max_lines integers: {exc}')
        if width <= 0 or font_size <= 0 or max_lines < 1:
            raise ValueError('layout caption width_px/font_size_px must be positive, max_lines >= 1')
        log(f'caption spec from layout {args.layout}: width={width} font_size={font_size} max_lines={max_lines}')
        return width, font_size, max_lines
    assert args.width is not None and args.font_size is not None and args.max_lines is not None
    return args.width, args.font_size, args.max_lines


def load_offsets(
    path: str, script_path: str, narration_path: str
) -> tuple[dict[str, Any], Callable[[int], int]]:
    """偏移表；不合格（含缺内容哈希）时直接报错，不降级到字数比对。

    直接调用本脚本的人工 / 工具路径也要过这份契约，因此不能只靠 pipeline-status
    在阶段层面把关。
    """
    with open(path, encoding='utf-8') as file:
        data = json.load(file)
    problem = video_contract.offsets_problem(
        data, script_path=Path(script_path), narration_path=Path(narration_path),
    )
    if problem:
        raise ValueError(f'offsets table {path} is unusable: {problem}')
    segments = sorted(data['segments'], key=lambda seg: seg['narration_start'])
    starts = [seg['narration_start'] for seg in segments]

    def to_script(position: int) -> int:
        index = bisect.bisect_right(starts, position) - 1
        if index < 0:
            raise ValueError(f'narration position {position} not covered by offset table')
        segment = segments[index]
        span = max(0, segment['script_end'] - segment['script_start'] - 1)
        return segment['script_start'] + min(position - segment['narration_start'], span)

    return data, to_script


# --- 对齐 --------------------------------------------------------------------


def interpolate_timing(word: Word, offset: int, count: int) -> tuple[int, int]:
    """在 ``count`` 个字符的 token 内，插值出第 ``offset`` 个字符的时间区间。"""
    duration = word.end - word.begin
    begin = word.begin + round(duration * offset / count)
    end = word.begin + round(duration * (offset + 1) / count)
    return begin, end


def build_display_atoms(
    script_text: str,
    narration_map: list[int],
    to_script: Callable[[int], int],
    narr_start: int,
    narr_end: int,
    asr_start: int,
    asr_norm_times: list[tuple[int, int]],
    paragraph: int,
) -> list[Atom]:
    """把一个已对齐的（按段落的）相等块转成展示稿 atoms。

    展示切片覆盖该块所及的那段稿子字符；其中的标点与空格会重新出现在字幕文本里
    （这正是英文词之间保持空格、数字保持展示形式的原因）。未对齐的展示字符借用
    最近的已对齐字符的时间。
    """
    display_start = to_script(narration_map[narr_start])
    display_end = to_script(narration_map[narr_end - 1]) + 1
    # 把最后一个已对齐字符之后的句末标点一并吞掉
    while display_end < len(script_text) and script_text[display_end] in SENTENCE_FINAL_CHARS:
        display_end += 1
    display = script_text[display_start:display_end]
    aligned_count = narr_end - narr_start
    aligned_of: list[int | None] = [None] * len(display)
    for offset in range(aligned_count):
        position = to_script(narration_map[narr_start + offset]) - display_start
        if 0 <= position < len(display):
            aligned_of[position] = offset
    aligned_of_direct = list(aligned_of)
    last: int | None = None
    for position in range(len(display)):
        if aligned_of[position] is not None:
            last = aligned_of[position]
        elif last is not None:
            aligned_of[position] = last
    for position in range(len(display) - 1, -1, -1):
        if aligned_of[position] is None and position + 1 < len(display):
            aligned_of[position] = aligned_of[position + 1]
    atoms: list[Atom] = []
    for position, char in enumerate(display):
        offset = aligned_of[position]
        if offset is None:  # 偏移表未覆盖的展示文本
            continue
        begin_ms, end_ms = asr_norm_times[asr_start + offset]
        atoms.append(Atom(text=char, begin_ms=begin_ms, end_ms=end_ms,
                          fallback=False, paragraph=paragraph,
                          borrowed=aligned_of_direct[position] is None))
    return atoms


def build_atoms(
    script_text: str,
    narration_text: str,
    to_script: Callable[[int], int],
    words: list[Word],
    spans: list[tuple[int, int]],
    warnings: list[str],
) -> list[Atom]:
    """字符级对齐 -> 带时间的展示 atoms。

    相等的块产出展示稿 atoms（fallback=False）；仅转写有的块保留 ASR 文本
    （fallback=True）；仅旁白有的块会被丢弃并给出警告（它们没有对应音频）。
    """
    narration_norm, narration_map = normalize_with_map(narration_text)

    asr_chars: list[str] = []
    asr_norm_times: list[tuple[int, int]] = []
    word_span_starts: list[int] = []
    for word in words:
        word_norm, _ = normalize_with_map(word.text)
        word_span_starts.append(len(asr_chars))
        count = max(1, len(word_norm))
        for offset, char in enumerate(word_norm):
            asr_chars.append(char)
            asr_norm_times.append(interpolate_timing(word, offset, count))
    asr_norm = ''.join(asr_chars)

    span_starts = [span[0] for span in spans]

    def paragraph_of(narration_char_index: int) -> int:
        index = bisect.bisect_right(span_starts, narration_char_index) - 1
        return index + 1  # 从 1 开始

    def words_touching(asr_start: int, asr_end: int) -> list[int]:
        """归一化字符区间与 [asr_start, asr_end) 有重叠的词下标。"""
        first = max(0, bisect.bisect_right(word_span_starts, asr_start) - 1)
        return [
            index
            for index in range(first, len(words))
            if word_span_starts[index] < asr_end
        ]

    def atoms_from_equal_run(narr_start: int, narr_end: int, asr_start: int, asr_end: int) -> list[Atom]:
        # 一个相等块可能跨段落边界（换行已被归一化掉）；
        # 因此按段落拆成子块分别处理
        run_atoms: list[Atom] = []
        offset = 0
        while offset < narr_end - narr_start:
            paragraph = paragraph_of(narration_map[narr_start + offset])
            sub_end = offset + 1
            while sub_end < narr_end - narr_start and paragraph_of(narration_map[narr_start + sub_end]) == paragraph:
                sub_end += 1
            run_atoms.extend(
                build_display_atoms(
                    script_text, narration_map, to_script,
                    narr_start + offset, narr_start + sub_end, asr_start + offset,
                    asr_norm_times, paragraph,
                )
            )
            offset = sub_end
        return run_atoms

    def atoms_from_transcript_only(asr_start: int, asr_end: int, atoms_so_far: list[Atom]) -> list[Atom]:
        # 没有旁白对应的 ASR 文本：保留，并标记为 fallback。
        paragraph = atoms_so_far[-1].paragraph if atoms_so_far else 1
        block_atoms: list[Atom] = []
        for word_index in words_touching(asr_start, asr_end):
            word = words[word_index]
            count = max(1, len(word.text))
            for offset, char in enumerate(word.text):
                begin, end = interpolate_timing(word, offset, count)
                block_atoms.append(Atom(text=char, begin_ms=begin, end_ms=end,
                                        fallback=True, paragraph=paragraph))
        return block_atoms

    def record_dropped_narration(narr_start: int, narr_end: int) -> None:
        dropped_start = narration_map[narr_start]
        dropped_end = narration_map[narr_end - 1] + 1
        dropped = narration_text[dropped_start:dropped_end].strip()
        if dropped:
            warning = f'narration text has no audio and was dropped: {dropped[:40]}'
            warnings.append(warning)
            log(f'warning: {warning}')

    atoms: list[Atom] = []
    matcher = difflib.SequenceMatcher(None, narration_norm, asr_norm, autojunk=False)
    for tag, narr_start, narr_end, asr_start, asr_end in matcher.get_opcodes():
        if tag == 'equal':
            atoms.extend(atoms_from_equal_run(narr_start, narr_end, asr_start, asr_end))
        elif tag in ('replace', 'insert'):
            atoms.extend(atoms_from_transcript_only(asr_start, asr_end, atoms))
        else:  # 删除
            record_dropped_narration(narr_start, narr_end)

    return atoms


# --- 切分 --------------------------------------------------------------------


def char_width(char: str) -> float:
    if is_cjk(char):
        return 1.0
    if char.isascii():
        if char.isalnum():
            return 0.55
        if char.isspace():
            return 0.3
        return 0.4
    return 1.0


def atoms_width(atoms: list[Atom]) -> float:
    return sum(char_width(atom.text) for atom in atoms)


def break_allowed(left: Atom, right: Atom) -> bool:
    # 绝不在英文词或数字内部断开
    return not (is_latin_token_char(left.text) and is_latin_token_char(right.text))


def unit_text(atoms: list[Atom]) -> str:
    text = ''.join(atom.text for atom in atoms).rstrip()
    while text and text[-1] in TRAILING_STRIP_CHARS:
        text = text[:-1].rstrip()
    return text


def unit_bounds(atoms: list[Atom]) -> tuple[int, int] | None:
    """有效 (begin_ms, end_ms)：边缘上借用的标点 / 空格 atom 被忽略，因此相邻
    单元不会因为借来的时间而重叠。"""
    anchors = [atom for atom in atoms if not atom.borrowed]
    if not anchors:
        anchors = atoms
    return anchors[0].begin_ms, anchors[-1].end_ms


def find_cut(current: list[Atom], overflow: Atom) -> int | None:
    """应在哪个 atom 之后切开的索引；没有合法切点时返回 None。

    切点可以落在 ``current`` 的最末尾（此时切点之后的 atom 就是 ``overflow``）；
    两个拉丁 token 字符之间的切点永远不允许，因此英文词和数字绝不会被拆开。
    """
    def right_of(index: int) -> Atom:
        return current[index + 1] if index + 1 < len(current) else overflow

    for index in range(len(current) - 1, -1, -1):
        if current[index].text in SOFT_BREAK_CHARS and break_allowed(current[index], right_of(index)):
            return index
    for index in range(len(current) - 1, -1, -1):
        if break_allowed(current[index], right_of(index)):
            return index
    return None


def atoms_budget(cap: float | Callable[[int, int], float], atoms: list[Atom]) -> float:
    """一组 atoms 在整个实际显示期间必须共同满足的最小字幕预算。"""
    if not callable(cap):
        return cap
    bounds = unit_bounds(atoms)
    return cap(*bounds) if bounds is not None else 0.0


def rebalance(
    segments: list[list[Atom]], cap: float | Callable[[int, int], float]
) -> list[list[Atom]]:
    """通过重新切开最后两段，修正过短的尾部片段。"""
    if len(segments) < 2:
        return segments
    last_width = atoms_width(segments[-1])
    if last_width >= max(2.0, 0.2 * atoms_budget(cap, segments[-1])):
        return segments
    combined = segments[-2] + segments[-1]
    cuts = [
        index
        for index in range(len(combined) - 1)
        if break_allowed(combined[index], combined[index + 1])
    ]
    if not cuts:
        return segments
    half = atoms_width(combined) / 2
    best = min(cuts, key=lambda index: abs(atoms_width(combined[:index + 1]) - half))
    head, tail = combined[:best + 1], combined[best + 1:]
    if not tail or atoms_width(tail) <= last_width + 0.01:
        return segments  # 没有改善
    if callable(cap) and (
        atoms_width(head) > atoms_budget(cap, head) or atoms_width(tail) > atoms_budget(cap, tail)
    ):
        return segments  # 仅动态 scene 模式追加硬预算保护；旧入口保持原行为
    return segments[:-2] + [head, tail]


def split_sentence(
    sentence: list[Atom],
    cap: float | Callable[[int, int], float],
    warnings: list[str],
    *,
    strict_tokens: bool = False,
) -> list[list[Atom]]:
    if atoms_width(sentence) <= atoms_budget(cap, sentence) or len(sentence) < 2:
        return [sentence]
    segments: list[list[Atom]] = []
    current: list[Atom] = []
    current_width = 0.0
    for atom in sentence:
        width = char_width(atom.text)
        while current and current_width + width > atoms_budget(cap, [*current, atom]):
            cut = find_cut(current, atom)
            if cut is None:
                token = ''.join(item.text for item in current) + atom.text
                if strict_tokens:
                    raise ValueError(
                        f'caption budget cannot fit token without breaking it: {token[:80]!r}; '
                        'choose a wider caption layout or larger font budget'
                    )
                cut = len(current) - 1  # 旧单 layout 入口保留原诊断与兜底
                warnings.append(f'segment exceeds width cap; broke inside a token: {current[0].text[:20]}')
            segments.append(current[:cut + 1])
            current = current[cut + 1:]
            current_width = atoms_width(current)
        current.append(atom)
        current_width += width
    if current:
        segments.append(current)
    return rebalance(segments, cap)


def split_into_sentences(atoms: list[Atom]) -> list[list[Atom]]:
    sentences: list[list[Atom]] = []
    current: list[Atom] = []
    for index, atom in enumerate(atoms):
        current.append(atom)
        next_char = atoms[index + 1].text if index + 1 < len(atoms) else ''
        is_final = atom.text in SENTENCE_FINAL_CHARS or (
            atom.text in '.!?' and not is_latin_token_char(next_char)
        )
        if is_final:
            sentences.append(current)
            current = []
    if current:
        sentences.append(current)
    return sentences


def merge_short_units(
    units: list[list[Atom]],
    cap: float | Callable[[int, int], float],
    warnings: list[str],
    *,
    respect_budget: bool = False,
) -> tuple[list[list[Atom]], int]:
    """把短于 MIN_UNIT_MS 的单元并入相邻单元（优先并入前一个）。

    旧单 layout 入口保留“最短显示时长优先”的历史兼容行为。视觉 scene 模式中
    布局预算是硬约束：若合并会超预算，就保留较短的单元并给出诊断。
    """
    merged_count = 0
    changed = True
    while changed:
        changed = False
        index = 0
        while index < len(units):
            atoms = units[index]
            if atoms and atoms[-1].end_ms - atoms[0].begin_ms < MIN_UNIT_MS and len(units) > 1:
                target = index - 1 if index > 0 else index + 1
                candidate = units[target] + atoms if index > 0 else atoms + units[target]
                if respect_budget and atoms_width(candidate) > atoms_budget(cap, candidate):
                    warnings.append(
                        f'short subtitle unit was not merged because it would exceed the scene caption budget: '
                        f'{unit_text(atoms)[:40]!r}'
                    )
                    index += 1
                    continue
                units[min(index, target):max(index, target) + 1] = [candidate]
                index = min(index, target)
                merged_count += 1
                changed = True
            index += 1
    return units, merged_count


# --- timeline 的 scenes 与 cues ----------------------------------------------


def locate_scenes(
    scene_plan: list[dict[str, Any]],
    atoms_by_paragraph: dict[int, list[Atom]],
    warnings: list[str],
) -> list[dict[str, Any]]:
    """scene 的起止秒数，由各 scene 覆盖的段落推导。"""
    scenes: list[dict[str, Any]] = []
    for scene in scene_plan:
        if not isinstance(scene, dict):
            continue
        scene_id = scene.get('scene_id') or scene.get('id')
        paragraphs = scene.get('paragraphs') or []
        begins: list[int] = []
        ends: list[int] = []
        for paragraph in paragraphs:
            atoms = atoms_by_paragraph.get(int(paragraph), [])
            if atoms:
                begins.append(min(atom.begin_ms for atom in atoms))
                ends.append(max(atom.end_ms for atom in atoms))
        if not begins:
            warning = f'scene {scene_id!r} covers no aligned paragraphs; missing from timeline'
            warnings.append(warning)
            log(f'warning: {warning}')
            continue
        scenes.append(
            {
                'scene_id': scene_id,
                'begin_s': round(min(begins) / 1000, 3),
                'end_s': round(max(ends) / 1000, 3),
            }
        )
    return scenes


def locate_text(
    text: str,
    paragraphs: list[int],
    atoms_by_paragraph: dict[int, list[Atom]],
) -> tuple[int, int] | None:
    """在该 scene 已对齐的段落中定位归一化后的展示文本。"""
    text_norm, _ = normalize_with_map(text)
    if not text_norm:
        return None
    for paragraph in paragraphs:
        atoms = atoms_by_paragraph.get(int(paragraph), [])
        norm_chars: list[str] = []
        norm_atom: list[Atom] = []
        for atom in atoms:
            for char in normalize_with_map(atom.text)[0]:
                norm_chars.append(char)
                norm_atom.append(atom)
        haystack = ''.join(norm_chars)
        position = haystack.find(text_norm)
        if position != -1:
            first = norm_atom[position]
            last = norm_atom[position + len(text_norm) - 1]
            return first.begin_ms, last.end_ms
    return None


def _locate_scene_texts(
    scene_plan: list[dict[str, Any]],
    atoms_by_paragraph: dict[int, list[Atom]],
    item_key: str,
    text_for: Callable[[Any], str],
) -> list[tuple[Any, Any, str, tuple[int, int] | None]]:
    located = []
    for scene in scene_plan:
        if not isinstance(scene, dict):
            continue
        scene_id = scene.get('scene_id') or scene.get('id')
        paragraphs = scene.get('paragraphs') or []
        for item in scene.get(item_key) or []:
            text = text_for(item)
            found = locate_text(text, paragraphs, atoms_by_paragraph)
            located.append((scene_id, item, text, found))
    return located


def locate_cues(
    scene_plan: list[dict[str, Any]],
    atoms_by_paragraph: dict[int, list[Atom]],
    warnings: list[str],
) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    for scene_id, cue, text, found in _locate_scene_texts(
        scene_plan, atoms_by_paragraph, 'cues', str
    ):
        if found is None:
            warning = f'cue not found for scene {scene_id!r}: {text[:40]!r}'
            warnings.append(warning)
            log(f'warning: {warning}')
            continue
        cues.append(
            {
                'scene_id': scene_id,
                'cue': cue,
                'begin_s': round(found[0] / 1000, 3),
                'end_s': round(found[1] / 1000, 3),
            }
        )
    return cues


# --- 主流程 ------------------------------------------------------------------


def group_atoms_by_paragraph(atoms: list[Atom]) -> dict[int, list[Atom]]:
    atoms_by_paragraph: dict[int, list[Atom]] = {}
    for atom in atoms:
        atoms_by_paragraph.setdefault(atom.paragraph, []).append(atom)
    return atoms_by_paragraph


def paragraphs_in_order(
    atoms_by_paragraph: dict[int, list[Atom]],
) -> list[tuple[int, list[Atom]]]:
    return [(paragraph, atoms_by_paragraph[paragraph]) for paragraph in sorted(atoms_by_paragraph)]


def build_units(
    atoms_by_paragraph: dict[int, list[Atom]],
    cap: float | Callable[[int, int], float],
    warnings: list[str],
    *,
    scene_budgets: bool = False,
) -> tuple[list[dict[str, Any]], int, int]:
    """把 atoms 切成字幕单元；返回 (units, fallback_units, merged_units)。"""
    units: list[dict[str, Any]] = []
    fallback_units = 0
    merged_total = 0
    previous_end = -1
    for paragraph, paragraph_atoms in paragraphs_in_order(atoms_by_paragraph):
        segments: list[list[Atom]] = []
        for sentence in split_into_sentences(paragraph_atoms):
            segments.extend(split_sentence(sentence, cap, warnings, strict_tokens=scene_budgets))
        segments, merged = merge_short_units(segments, cap, warnings, respect_budget=scene_budgets)
        merged_total += merged
        for segment in segments:
            if scene_budgets and atoms_width(segment) > atoms_budget(cap, segment):
                raise ValueError(
                    f'caption segment exceeds its visual-scene budget after split/merge: '
                    f'{unit_text(segment)[:80]!r}'
                )
            text = unit_text(segment)
            if not text:
                continue
            bounds = unit_bounds(segment)
            if bounds is None:
                continue
            begin_ms, end_ms = bounds
            if begin_ms < previous_end:
                raise ValueError('unit timing overlaps previous unit')
            previous_end = end_ms
            fallback = any(atom.fallback for atom in segment)
            if fallback:
                fallback_units += 1
            units.append(
                {
                    'index': len(units) + 1,
                    'text': text,
                    'begin_ms': begin_ms,
                    'end_ms': end_ms,
                    'begin_s': round(begin_ms / 1000, 3),
                    'end_s': round(end_ms / 1000, 3),
                    'fallback': fallback,
                    'paragraph': paragraph,
                }
            )
    return units, fallback_units, merged_total


def build_timeline(
    atoms_by_paragraph: dict[int, list[Atom]],
    span_count: int,
    warnings: list[str],
) -> tuple[list[dict[str, Any]], float]:
    """逐段落的起止秒数，以及总时长。"""
    paragraphs: list[dict[str, Any]] = []
    total_ms = 0
    for paragraph, paragraph_atoms in paragraphs_in_order(atoms_by_paragraph):
        paragraph_begin = min(atom.begin_ms for atom in paragraph_atoms)
        paragraph_end = max(atom.end_ms for atom in paragraph_atoms)
        total_ms = max(total_ms, paragraph_end)
        paragraphs.append(
            {
                'index': paragraph,
                'begin_s': round(paragraph_begin / 1000, 3),
                'end_s': round(paragraph_end / 1000, 3),
            }
        )
    for paragraph_index in range(1, span_count + 1):
        if paragraph_index not in atoms_by_paragraph:
            warning = f'paragraph {paragraph_index} has no aligned audio; missing from timeline'
            warnings.append(warning)
            log(f'warning: {warning}')
    return paragraphs, round(total_ms / 1000, 3)


def scene_clock(
    scene_plan_path: str | None,
    atoms_by_paragraph: dict[int, list[Atom]],
    warnings: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """可选的 scene-plan 推导出的 (scenes, cues) 时间。"""
    if not scene_plan_path:
        return [], []
    with open(scene_plan_path, encoding='utf-8') as file:
        scene_plan = json.load(file)
    if not isinstance(scene_plan, list):
        raise ValueError(f'scene plan {scene_plan_path} root must be a list')
    removed = video_contract.removed_scene_fields_problem(scene_plan)
    if removed:
        raise ValueError(f'scene plan {scene_plan_path}: {removed}')
    return (
        locate_scenes(scene_plan, atoms_by_paragraph, warnings),
        locate_cues(scene_plan, atoms_by_paragraph, warnings),
    )


def load_scene_caption_segments(args: argparse.Namespace) -> list[dict[str, Any]]:
    """读取 Phase 8 scene-config，并派生字幕工具与组件共用的有效布局区间。"""
    transcript_path = Path(args.transcript).resolve()
    ws = transcript_path.parent.parent
    audio_path = Path(args.narration_audio).resolve() if args.narration_audio else ws / 'voice_clone' / 'narration.mp3'
    duration_s = media.probe_duration(audio_path)
    try:
        inputs = json.loads((ws / 'inputs.json').read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'cannot read {ws / "inputs.json"} for scene canvas validation: {exc}') from exc
    if not isinstance(inputs, dict):
        raise ValueError(f'{ws / "inputs.json"} root must be an object')
    orientation = inputs.get('orientation')
    expected_canvas = video_contract.orientation_canvas(orientation)
    if expected_canvas is None:
        raise ValueError(f'inputs.json field orientation must be a canonical orientation, got {orientation!r}')
    config_path = Path(args.scene_config).resolve()
    try:
        config = scene_config.load_scene_config(
            config_path,
            expected_canvas=expected_canvas,
            known_scene_ids=workspace_scene_ids(ws),
            modules_root=Path(__file__).resolve().parent.parent,
        )
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    total_s = config['total_s']
    if abs(total_s - duration_s) > scene_config.DURATION_TOLERANCE_S + 0.05:
        raise ValueError(
            f'scene-config total_s {total_s} does not match narration duration {duration_s}; '
            'total_s bounds the delivered video at the narration length'
        )
    segments = scene_config.caption_layout_segments(config['scenes'])
    for segment in segments:
        caption = segment['layout_data']['caption']
        log(
            f'caption scene={segment["scene_id"]} [{segment["begin_s"]}, {segment["end_s"]}) '
            f'layout={segment["layout"]} width={caption["width_px"]} '
            f'font_size={caption["font_size_px"]} max_lines={caption["max_lines"]}'
        )
    return segments


def workspace_scene_ids(ws: Path) -> set[str] | None:
    """scene-plan.json 的叙事 scene_id 集合；缺失或损坏时不阻塞字幕生成。"""
    try:
        plan = json.loads((ws / 'scene-plan.json').read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(plan, list):
        return None
    ids = {
        scene['scene_id'] for scene in plan
        if isinstance(scene, dict) and isinstance(scene.get('scene_id'), str)
    }
    return ids or None


def caption_budget(segments: list[dict[str, Any]]) -> Callable[[int, int], float]:
    """整个显示区间触及的所有 scene 中，取最严格的字幕预算。"""
    def between(begin_ms: int, end_ms: int) -> float:
        begin_s, end_s = begin_ms / 1000, end_ms / 1000
        if end_s <= begin_s:
            end_s = begin_s + 0.001
        active = [
            item for item in segments
            if item['begin_s'] < end_s and item['end_s'] > begin_s
        ]
        if not active:
            raise ValueError(
                f'subtitle timing [{begin_s}, {end_s}) is not covered by visual scenes'
            )
        return min(
            int(item['layout_data']['caption']['width_px'] / item['layout_data']['caption']['font_size_px'])
            * item['layout_data']['caption']['max_lines']
            for item in active
        )
    return between


def public_caption_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """写入字幕产物的派生显示契约；不让 agent 手算视觉边界。"""
    result = []
    for segment in segments:
        layout = segment['layout_data']
        caption_region = scene_config.caption_region(layout)
        result.append({
            'scene_id': segment['scene_id'], 'begin_s': segment['begin_s'], 'end_s': segment['end_s'],
            'layout': segment['layout'], 'caption': dict(layout['caption']),
            'caption_rect': dict(caption_region['rect']) if isinstance(caption_region, dict) and isinstance(caption_region.get('rect'), dict) else None,
        })
    return result


def aligned_atoms(args: argparse.Namespace, warnings: list[str]) -> tuple[dict[int, list[Atom]], int]:
    """两个 mode 共用的前半部分：读输入、校验偏移表、把时间映射到显示稿。"""
    narration_text = read_text(args.narration)
    if not narration_text.strip():
        raise ValueError('narration text is empty')
    script_text = read_text(args.script)
    if not script_text.strip():
        raise ValueError('display draft (script) is empty')
    words = load_transcript(args.transcript)
    _, to_script = load_offsets(args.offsets, args.script, args.narration)

    spans = paragraph_spans(narration_text)
    if not spans:
        raise ValueError('narration has no paragraphs')

    atoms = build_atoms(script_text, narration_text, to_script, words, spans, warnings)
    log(f'paragraphs={len(spans)} asr_words={len(words)} atoms={len(atoms)}')
    return group_atoms_by_paragraph(atoms), len(spans)


def align(args: argparse.Namespace) -> dict[str, Any]:
    """按 mode 生成属于它的那一份产物。"""
    warnings: list[str] = []
    atoms_by_paragraph, span_count = aligned_atoms(args, warnings)

    if args.mode == 'timing':
        # 时间轴与字幕容量无关：不读 layout，也不要求任何 caption 参数。
        paragraphs, total_s = build_timeline(atoms_by_paragraph, span_count, warnings)
        scenes, cues = scene_clock(args.scene_plan, atoms_by_paragraph, warnings)
        return {
            'timeline': {
                'version': 1,
                'total_s': total_s,
                'paragraphs': paragraphs,
                **({'scenes': scenes} if args.scene_plan else {}),
                **({'cues': cues} if args.scene_plan else {}),
            },
            'summary': {
                'paragraph_count': len(paragraphs),
                'total_s': total_s,
                'cue_count': len(cues),
                'warnings': warnings,
            },
        }

    segments = load_scene_caption_segments(args) if args.scene_config is not None else None
    if segments is not None:
        cap: float | Callable[[int, int], float] = caption_budget(segments)
    else:
        caption_width, caption_font_size, caption_max_lines = load_caption_spec(args)
        cap = int(caption_width / caption_font_size) * caption_max_lines
        log(f'cap={cap}')
    units, fallback_units, merged_total = build_units(
        atoms_by_paragraph, cap, warnings, scene_budgets=segments is not None,
    )
    if not units:
        raise ValueError('alignment produced no subtitle units')
    return {
        'units': {
            'version': 1,
            'units': units,
            'summary': {},
            **({'caption_segments': public_caption_segments(segments)} if segments is not None else {}),
        },
        'summary': {
            'unit_count': len(units),
            'fallback_units': fallback_units,
            'merged_units': merged_total,
            'warnings': warnings,
        },
    }


def output_path(args: argparse.Namespace) -> tuple[str, str]:
    """(payload 键, 输出路径)：每个 mode 只写属于自己的那一份。"""
    transcript_dir = os.path.dirname(os.path.abspath(args.transcript))
    if args.mode == 'timing':
        return 'timeline', args.timeline_output or os.path.join(transcript_dir, 'timeline.json')
    return 'units', args.units_output or os.path.join(transcript_dir, 'subtitle-units.json')


def main() -> int:
    args = parse_args()
    key, output = output_path(args)
    result = align(args)
    payload = result[key]
    if key == 'units':
        payload['summary'] = result['summary']
    output_dir = os.path.dirname(os.path.abspath(output))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output, 'w', encoding='utf-8') as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write('\n')
    log(f'wrote {output}')
    print_json(
        {
            'success': True,
            'mode': args.mode,
            f'{key}_path': os.path.abspath(output),
            'summary': result['summary'],
        }
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
