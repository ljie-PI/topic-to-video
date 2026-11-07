"""Integration tests for scripts/align-narration.py.

The test seam is the script's command line (repo convention: stdout = one
JSON, exit codes 0 / 1 / 2). Fixture workspaces are built in tmp dirs:
the display draft (script.txt) + lexicon are run through make-narration.py
to produce the narration draft and the offset table, and the ASR
transcript is a hand-written, schema-conformant JSON — so every test is
independent of any real TTS/ASR backend.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'align-narration.py'
MAKE_NARRATION = REPO_ROOT / 'scripts' / 'make-narration.py'
LAYOUTS = REPO_ROOT / 'modules' / 'layouts'
PRESENTER_LAYOUT = LAYOUTS / 'presenter.json'
PORTRAIT_LAYOUT = LAYOUTS / 'portrait.json'


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def align_args(
    tmp_path: Path,
    mode: str,
    *,
    width: int = 1200,
    font_size: int = 42,
    max_lines: int = 1,
    layout: Path | None = None,
    scene_plan=None,
    scenes: Path | None = None,
) -> list[str]:
    """一个 mode 的完整命令行；两个 mode 各自只带自己的输出与参数。"""
    args = [
        '--mode', mode,
        '--transcript', str(tmp_path / 'transcribe' / 'transcript.json'),
        '--narration', str(tmp_path / 'narration.txt'),
        '--offsets', str(tmp_path / 'narration-offsets.json'),
        '--script', str(tmp_path / 'script.txt'),
    ]
    if mode == 'timing':
        args += ['--timeline-output', str(tmp_path / 'transcribe' / 'timeline.json')]
        if scene_plan is not None:
            args += ['--scene-plan', str(tmp_path / 'scene-plan.json')]
        return args
    args += ['--units-output', str(tmp_path / 'transcribe' / 'subtitle-units.json')]
    if scenes is not None:
        args += [
            '--scenes', str(scenes),
            '--narration-audio', str(tmp_path / 'voice_clone' / 'narration.mp3'),
        ]
    elif layout is not None:
        args += ['--layout', str(layout)]
    else:
        args += ['--width', str(width), '--font-size', str(font_size), '--max-lines', str(max_lines)]
    return args


def make_workspace(
    tmp_path: Path,
    script_text: str,
    lexicon: dict[str, str],
    transcript: list,
    *,
    width: int = 1200,
    font_size: int = 42,
    max_lines: int = 1,
    layout: Path | None = None,
    scene_plan=None,
    scenes: Path | None = None,
    subtitle_args: tuple[str, ...] = (),
):
    """Build a fixture workspace and run both align-narration modes on it.

    "subtitles" runs first (it validates the caption spec); "timing" only runs if
    that succeeded. Returns (proc, stdout_json, units_data, timeline_data), where
    stdout_json merges the two modes' summaries and `proc` is the run that failed
    when either did.
    """
    write_text(tmp_path / 'script.txt', script_text)
    write_json(tmp_path / 'tts-lexicon.json', lexicon)
    write_json(tmp_path / 'transcribe' / 'transcript.json', transcript)

    mn = subprocess.run(
        [
            sys.executable,
            str(MAKE_NARRATION),
            '--script', str(tmp_path / 'script.txt'),
            '--lexicon', str(tmp_path / 'tts-lexicon.json'),
            '--output-dir', str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert mn.returncode == 0, mn.stderr

    if scene_plan is not None:
        write_json(tmp_path / 'scene-plan.json', scene_plan)
    if scenes is not None:
        write_json(tmp_path / 'inputs.json', {
            'orientation': 'landscape', 'design': 'default',
        })
        audio = tmp_path / 'voice_clone' / 'narration.mp3'
        audio.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            'ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono',
            '-t', '6', '-c:a', 'libmp3lame', str(audio),
        ], capture_output=True, check=True)

    units_path = tmp_path / 'transcribe' / 'subtitle-units.json'
    timeline_path = tmp_path / 'transcribe' / 'timeline.json'
    proc = run_cli(*align_args(
        tmp_path, 'subtitles', width=width, font_size=font_size, max_lines=max_lines, layout=layout,
        scenes=scenes,
    ), *subtitle_args)
    result = json.loads(proc.stdout)
    timeline_result = None
    if proc.returncode == 0:
        timing_proc = run_cli(*align_args(tmp_path, 'timing', scene_plan=scene_plan))
        if timing_proc.returncode == 0:
            timeline_result = json.loads(timing_proc.stdout)
        else:
            proc = timing_proc
            result = json.loads(timing_proc.stdout)
    if timeline_result is not None:
        units_summary = result.get('summary') or {}
        timing_summary = timeline_result.get('summary') or {}
        merged = {**units_summary, **{k: v for k, v in timing_summary.items() if k != 'warnings'}}
        merged['warnings'] = [
            *(units_summary.get('warnings') or []),
            *(timing_summary.get('warnings') or []),
        ]
        result = {**result, 'summary': merged}
    units_data = json.loads(units_path.read_text(encoding='utf-8')) if units_path.exists() else None
    timeline_data = json.loads(timeline_path.read_text(encoding='utf-8')) if timeline_path.exists() else None
    return proc, result, units_data, timeline_data


def unit_texts(units_data: dict) -> list[str]:
    return [unit['text'] for unit in units_data['units']]


# --- regression: stuck-together tokens (ClaudeCode / 并提 | 交改动) -------------

REGRESSION_SCRIPT = 'Claude Code 发布了 5.4 版本，并提交改动。'
REGRESSION_TRANSCRIPT = [
    {
        'begin': 0,
        'end': 2600,
        'text': 'Claude Code 发布了 5.4 版本，并提交改动。',
        'words': [
            {'text': 'Claude', 'begin': 0, 'end': 300},
            {'text': 'Code', 'begin': 300, 'end': 600},
            {'text': '发布', 'begin': 600, 'end': 900},
            {'text': '了', 'begin': 900, 'end': 1050},
            {'text': '5.4', 'begin': 1050, 'end': 1500},
            {'text': '版本', 'begin': 1500, 'end': 1900},
            # mid-word token splits that used to break lines inside words
            {'text': '并提', 'begin': 1900, 'end': 2150},
            {'text': '交改', 'begin': 2150, 'end': 2400},
            {'text': '动', 'begin': 2400, 'end': 2600},
        ],
    }
]


def test_regression_tokens_without_punctuation_or_spaces(tmp_path: Path):
    proc, result, units_data, timeline_data = make_workspace(
        tmp_path, REGRESSION_SCRIPT, {}, REGRESSION_TRANSCRIPT,
        width=630, font_size=42, max_lines=1,
    )
    assert proc.returncode == 0, proc.stderr
    assert result['success'] is True
    # English words keep their spaces, numerals stay in display form, and
    # the only break falls at the comma — never inside 并提交改动.
    assert unit_texts(units_data) == ['Claude Code 发布了 5.4 版本', '并提交改动']
    assert timeline_data['paragraphs'] == [{'index': 1, 'begin_s': 0.0, 'end_s': 2.6}]


def display_width(text: str) -> float:
    width = 0.0
    for char in text:
        if char.isascii():
            width += 0.55 if char.isalnum() else 0.3
        else:
            width += 1.0
    return width


def test_english_words_never_glued_at_any_width(tmp_path: Path):
    # tight 4-unit cap: English words and the number are never split, and no
    # glue like "ClaudeCode" ever appears.
    proc, result, units_data, _ = make_workspace(
        tmp_path, REGRESSION_SCRIPT, {}, REGRESSION_TRANSCRIPT,
        width=168, font_size=42, max_lines=1,
    )
    assert proc.returncode == 0
    for text in unit_texts(units_data):
        for token in re.findall(r'[A-Za-z0-9.]+', text):
            assert token in {'Claude', 'Code', '5.4'}


# --- token shape tolerance -----------------------------------------------------


def test_tokens_with_attached_punctuation(tmp_path: Path):
    transcript = [
        {
            'begin': 0,
            'end': 1800,
            'text': '大家好，今天天气不错。',
            'words': [
                {'text': '大家好，', 'begin': 0, 'end': 500},
                {'text': '今天', 'begin': 500, 'end': 900},
                {'text': '天气', 'begin': 900, 'end': 1300},
                {'text': '不错。', 'begin': 1300, 'end': 1800},
            ],
        }
    ]
    proc, result, units_data, _ = make_workspace(
        tmp_path, '大家好，今天天气不错。', {}, transcript
    )
    assert proc.returncode == 0, proc.stderr
    assert unit_texts(units_data) == ['大家好，今天天气不错']  # trailing 。 stripped
    assert units_data['units'][0]['fallback'] is False


def test_chinese_and_arabic_numerals_are_equivalent(tmp_path: Path):
    script_text = '一共 13432 个。\n\n第 5.4 版。'
    transcript = [
        {
            'begin': 0,
            'end': 900,
            'text': '一共 13432 个。',
            'words': [
                {'text': '一共', 'begin': 0, 'end': 200},
                {'text': '13432', 'begin': 200, 'end': 700},
                {'text': '个', 'begin': 700, 'end': 900},
            ],
        },
        {
            'begin': 900,
            'end': 1800,
            'text': '第五点四版。',
            'words': [
                {'text': '第', 'begin': 900, 'end': 1100},
                {'text': '五', 'begin': 1100, 'end': 1250},
                {'text': '点', 'begin': 1250, 'end': 1350},
                {'text': '四', 'begin': 1350, 'end': 1500},
                {'text': '版', 'begin': 1500, 'end': 1800},
            ],
        },
    ]
    proc, result, units_data, _ = make_workspace(
        tmp_path,
        script_text,
        {'13432': '一万三千四百三十二', '5.4': '五点四'},
        transcript,
    )
    assert proc.returncode == 0, proc.stderr
    texts = unit_texts(units_data)
    assert any('13432' in text for text in texts)  # display form restored
    assert any('5.4' in text for text in texts)
    assert all('一万三千四百三十二' not in text for text in texts)
    assert all('五点四' not in text for text in texts)


def test_brand_name_restored_to_display_form(tmp_path: Path):
    transcript = [
        {
            'begin': 0,
            'end': 2100,
            'text': 'Open Human 发布了新模型。',
            'words': [
                {'text': 'Open', 'begin': 0, 'end': 300},
                {'text': 'Human', 'begin': 300, 'end': 700},
                {'text': '发布', 'begin': 700, 'end': 1100},
                {'text': '了', 'begin': 1100, 'end': 1250},
                {'text': '新', 'begin': 1250, 'end': 1500},
                {'text': '模型', 'begin': 1500, 'end': 2100},
            ],
        }
    ]
    proc, result, units_data, _ = make_workspace(
        tmp_path, 'OpenHuman 发布了新模型。', {'OpenHuman': 'Open Human'}, transcript
    )
    assert proc.returncode == 0, proc.stderr
    texts = unit_texts(units_data)
    assert texts == ['OpenHuman 发布了新模型']


# --- fallback --------------------------------------------------------------------


def test_tts_extra_content_kept_as_fallback(tmp_path: Path):
    transcript = [
        {
            'begin': 0,
            'end': 1600,
            'text': '今天天气不错哈哈哈',
            'words': [
                {'text': '今天', 'begin': 0, 'end': 300},
                {'text': '天气', 'begin': 300, 'end': 600},
                {'text': '不错', 'begin': 600, 'end': 1000},
                {'text': '哈哈哈', 'begin': 1000, 'end': 1600},
            ],
        }
    ]
    proc, result, units_data, _ = make_workspace(
        tmp_path, '今天天气不错。', {}, transcript
    )
    assert proc.returncode == 0, proc.stderr
    fallback_units = [u for u in units_data['units'] if u['fallback']]
    assert [u['text'] for u in fallback_units] == ['哈哈哈']
    assert units_data['summary']['fallback_units'] == 1
    assert result['summary']['fallback_units'] == 1


def test_tts_skipped_text_dropped_with_warning(tmp_path: Path):
    transcript = [
        {
            'begin': 0,
            'end': 1000,
            'text': '今天天气不错',
            'words': [
                {'text': '今天', 'begin': 0, 'end': 300},
                {'text': '天气', 'begin': 300, 'end': 600},
                {'text': '不错', 'begin': 600, 'end': 1000},
            ],
        }
    ]
    proc, result, units_data, _ = make_workspace(
        tmp_path, '今天天气不错，我们出去走走。', {}, transcript
    )
    assert proc.returncode == 0, proc.stderr
    texts = unit_texts(units_data)
    assert texts == ['今天天气不错']
    assert units_data['summary']['warnings']


# --- segmentation -----------------------------------------------------------------


def test_portrait_allows_two_lines(tmp_path: Path):
    transcript = [
        {
            'begin': 0,
            'end': 2600,
            'text': '今天天气真的很不错适合出门。',
            'words': [
                {'text': '今天天气真的很不错适合出门', 'begin': 0, 'end': 2600},
            ],
        }
    ]
    # 13 display units; one 7-unit line is not enough, two lines are.
    proc, _, units_data, _ = make_workspace(
        tmp_path, '今天天气真的很不错适合出门。', {}, transcript,
        width=294, font_size=42, max_lines=2,
    )
    assert proc.returncode == 0
    assert unit_texts(units_data) == ['今天天气真的很不错适合出门']

    proc2, _, units_data2, _ = make_workspace(
        tmp_path, '今天天气真的很不错适合出门。', {}, transcript,
        width=294, font_size=42, max_lines=1,
    )
    assert proc2.returncode == 0
    assert len(units_data2['units']) > 1


def test_long_chinese_without_soft_punctuation_is_split_mid_sentence(tmp_path: Path):
    # No soft punctuation anywhere in the sentence: the width cap still forces a
    # cut, so a long CJK run can break mid-sentence. Text is not lost.
    script_text = '今天天气真的很不错非常适合出门散步晒太阳感受春天的气息。'
    transcript = [
        {
            'begin': 0,
            'end': 5000,
            'text': script_text,
            'words': [{'text': script_text.rstrip('。'), 'begin': 0, 'end': 5000}],
        }
    ]
    proc, result, units_data, _ = make_workspace(
        tmp_path, script_text, {}, transcript, width=420, font_size=42, max_lines=1
    )

    assert proc.returncode == 0, proc.stderr
    texts = unit_texts(units_data)
    assert len(texts) > 1
    assert ''.join(texts) == script_text.rstrip('。')


def test_a_single_over_wide_token_is_cut_with_a_warning(tmp_path: Path):
    # A token wider than the whole line cannot be broken legally; the script cuts
    # inside it anyway and reports that it did.
    script_text = 'Supercalifragilisticexpialidocious。'
    transcript = [
        {
            'begin': 0,
            'end': 3000,
            'text': script_text,
            'words': [
                {'text': 'Supercalifragilisticexpialidocious', 'begin': 0, 'end': 3000},
            ],
        }
    ]
    proc, result, units_data, _ = make_workspace(
        tmp_path, script_text, {}, transcript, width=126, font_size=42, max_lines=1
    )

    assert proc.returncode == 0, proc.stderr
    assert any('broke inside a token' in warning for warning in result['summary']['warnings'])
    # The pieces are shorter than MIN_UNIT_MS, so they merge back into one unit
    # that exceeds the width cap. Keeping an over-wide subtitle is the documented
    # trade-off; the warning is what says the layout needs fixing.
    texts = unit_texts(units_data)
    assert len(texts) == 1
    assert display_width(texts[0]) > int(126 / 42)


def test_short_units_merged(tmp_path: Path):
    transcript = [
        {
            'begin': 0,
            'end': 4060,
            'text': '深度学习非常非常强真的好啊',
            'words': [
                {'text': '深度学习非常非常强', 'begin': 0, 'end': 4000},
                {'text': '真的', 'begin': 4000, 'end': 4040},
                {'text': '好啊', 'begin': 4040, 'end': 4060},
            ],
        }
    ]
    # 11 display units > cap 10 -> split, but the 20 ms tail merges back.
    proc, _, units_data, _ = make_workspace(
        tmp_path, '深度学习非常非常强真的好啊。', {}, transcript,
        width=420, font_size=42, max_lines=1,
    )
    assert proc.returncode == 0, proc.stderr
    units = units_data['units']
    assert [(unit['text'], unit['begin_s'], unit['end_s']) for unit in units] == [
        ('深度学习非常非常强真的好啊', 0.0, 4.06),
    ]


def test_breaks_at_soft_punctuation_before_width(tmp_path: Path):
    transcript = [
        {
            'begin': 0,
            'end': 3000,
            'text': '人工智能很强大，很好用。',
            'words': [
                {'text': '人工智能很强大', 'begin': 0, 'end': 2000},
                {'text': '很好用', 'begin': 2000, 'end': 3000},
            ],
        }
    ]
    # cap 10: 7 + 1 + 4 = 12 -> must break at the comma, not mid-word.
    proc, _, units_data, _ = make_workspace(
        tmp_path, '人工智能很强大，很好用。', {}, transcript,
        width=420, font_size=42, max_lines=1,
    )
    assert proc.returncode == 0
    # the break falls at the comma; unit-final commas are stripped
    assert unit_texts(units_data) == ['人工智能很强大', '很好用']


# --- timeline -------------------------------------------------------------------


def test_timeline_paragraph_bounds(tmp_path: Path):
    transcript = [
        {
            'begin': 0,
            'end': 1200,
            'text': '第一段内容。',
            'words': [
                {'text': '第', 'begin': 0, 'end': 200},
                {'text': '一', 'begin': 200, 'end': 400},
                {'text': '段', 'begin': 400, 'end': 700},
                {'text': '内容', 'begin': 700, 'end': 1200},
            ],
        },
        {
            'begin': 1200,
            'end': 2500,
            'text': '第二段内容。',
            'words': [
                {'text': '第', 'begin': 1200, 'end': 1400},
                {'text': '二', 'begin': 1400, 'end': 1600},
                {'text': '段', 'begin': 1600, 'end': 1900},
                {'text': '内容', 'begin': 1900, 'end': 2500},
            ],
        },
    ]
    proc, _, _, timeline_data = make_workspace(
        tmp_path, '第一段内容。\n\n第二段内容。', {}, transcript
    )
    assert proc.returncode == 0
    assert timeline_data['paragraphs'] == [
        {'index': 1, 'begin_s': 0.0, 'end_s': 1.2},
        {'index': 2, 'begin_s': 1.2, 'end_s': 2.5},
    ]
    assert timeline_data['total_s'] == 2.5
    assert not {'scenes', 'cues', 'beats'} & timeline_data.keys()


def test_timeline_cue_seconds_with_scene_plan(tmp_path: Path):
    transcript = [
        {
            'begin': 0,
            'end': 1200,
            'text': '第一段内容。',
            'words': [
                {'text': '第', 'begin': 0, 'end': 300},
                {'text': '一', 'begin': 300, 'end': 600},
                {'text': '段', 'begin': 600, 'end': 900},
                {'text': '内容', 'begin': 900, 'end': 1200},
            ],
        }
    ]
    scene_plan = [
        {'scene_id': 's1', 'paragraphs': [1], 'cues': ['第一段']},
        {'scene_id': 's2', 'paragraphs': [1], 'cues': ['不存在的锚点句']},
    ]
    proc, result, _, timeline_data = make_workspace(
        tmp_path, '第一段内容。', {}, transcript, scene_plan=scene_plan
    )
    assert proc.returncode == 0
    assert timeline_data['cues'] == [
        {'scene_id': 's1', 'cue': '第一段', 'begin_s': 0.0, 'end_s': 0.9}
    ]
    # unmatched cue reported as a warning, not a failure
    assert any('s2' in warning for warning in result['summary']['warnings'])


def test_cues_are_located_in_the_display_script_not_the_narration(tmp_path: Path):
    # The display draft says NVIDIA, the TTS reads 英伟达. Cue lookup runs on the
    # restored display text, so a narration-form cue cannot match even though it
    # is word-for-word what the audio says; case and punctuation are normalized.
    script_text = 'NVIDIA 发布了新模型。'
    transcript = [
        {
            'begin': 0,
            'end': 2000,
            'text': '英伟达 发布了新模型。',
            'words': [
                {'text': '英伟达', 'begin': 0, 'end': 700},
                {'text': '发布了新模型', 'begin': 700, 'end': 2000},
            ],
        }
    ]
    scene_plan = [
        {
            'scene_id': 's1',
            'paragraphs': [1],
            'cues': ['NVIDIA 发布了新模型。', '英伟达发布了新模型。', 'nvidia，发布了新模型！'],
        }
    ]
    proc, result, _, timeline_data = make_workspace(
        tmp_path, script_text, {'NVIDIA': '英伟达'}, transcript, scene_plan=scene_plan
    )
    assert proc.returncode == 0, proc.stderr
    assert [cue['cue'] for cue in timeline_data['cues']] == [
        'NVIDIA 发布了新模型。',
        'nvidia，发布了新模型！',
    ]
    assert any(
        'cue not found' in warning and '英伟达发布了新模型。' in warning
        for warning in result['summary']['warnings']
    )


def test_cue_outside_its_scene_paragraphs_is_skipped(tmp_path: Path):
    script_text = '第一段内容。\n\nNVIDIA 发布了新模型。'
    transcript = [
        {
            'begin': 0,
            'end': 1200,
            'text': '第一段内容。',
            'words': [{'text': '第一段内容', 'begin': 0, 'end': 1200}],
        },
        {
            'begin': 1200,
            'end': 3200,
            'text': '英伟达 发布了新模型。',
            'words': [
                {'text': '英伟达', 'begin': 1200, 'end': 1900},
                {'text': '发布了新模型', 'begin': 1900, 'end': 3200},
            ],
        },
    ]
    scene_plan = [
        {'scene_id': 's1', 'paragraphs': [1], 'cues': ['NVIDIA 发布了新模型。']},
        {'scene_id': 's2', 'paragraphs': [2], 'cues': []},
    ]
    proc, result, _, timeline_data = make_workspace(
        tmp_path, script_text, {'NVIDIA': '英伟达'}, transcript, scene_plan=scene_plan
    )
    assert proc.returncode == 0, proc.stderr
    # The text exists in the display draft, but not in the paragraph s1 covers.
    assert timeline_data['cues'] == []
    assert any(
        'cue not found' in warning and 's1' in warning
        for warning in result['summary']['warnings']
    )


@pytest.mark.parametrize('removed', ['beats', 'pattern_hints', 'template_scene'])
def test_scene_plan_fields_of_composition_are_rejected(tmp_path: Path, removed: str):
    """视觉选择归 composition：旧字段不是被忽略，而是明确报错。"""
    transcript = [
        {
            'begin': 0,
            'end': 1200,
            'text': '这里有一个关键思路。',
            'words': [{'text': '这里有一个关键思路', 'begin': 0, 'end': 1200}],
        }
    ]
    scene_plan = [{'scene_id': 's1', 'paragraphs': [1], 'cues': [], removed: []}]

    proc, result, _, timeline_data = make_workspace(
        tmp_path, '这里有一个关键思路。', {}, transcript, scene_plan=scene_plan
    )

    assert proc.returncode == 1
    assert removed in result['error'] and 'scene 0' in result['error']
    assert 'removed field' in result['error']
    assert timeline_data is None


def test_timeline_scene_seconds_with_scene_plan(tmp_path: Path):
    transcript = [
        {
            'begin': 0,
            'end': 1200,
            'text': '第一段内容。',
            'words': [
                {'text': '第', 'begin': 0, 'end': 300},
                {'text': '一', 'begin': 300, 'end': 600},
                {'text': '段', 'begin': 600, 'end': 900},
                {'text': '内容', 'begin': 900, 'end': 1200},
            ],
        },
        {
            'begin': 1200,
            'end': 2500,
            'text': '第二段内容。',
            'words': [
                {'text': '第二段内容', 'begin': 1200, 'end': 2500},
            ],
        },
    ]
    scene_plan = [
        {'scene_id': 's1', 'paragraphs': [1], 'cues': []},
        {'scene_id': 's2', 'paragraphs': [1, 2], 'cues': []},
        {'scene_id': 's3', 'paragraphs': [99], 'cues': []},  # 无对齐段落：警告并跳过
    ]
    proc, result, _, timeline_data = make_workspace(
        tmp_path, '第一段内容。\n\n第二段内容。', {}, transcript, scene_plan=scene_plan
    )
    assert proc.returncode == 0
    assert timeline_data['scenes'] == [
        {'scene_id': 's1', 'begin_s': 0.0, 'end_s': 1.2},
        {'scene_id': 's2', 'begin_s': 0.0, 'end_s': 2.5},
    ]
    assert any('s3' in warning for warning in result['summary']['warnings'])


# --- CLI seam -------------------------------------------------------------------


def test_bad_arguments_exit_2(tmp_path: Path):
    proc = run_cli('--width', '100')
    assert proc.returncode == 2
    result = json.loads(proc.stdout)
    assert result['success'] is False


def test_missing_input_file_exits_1(tmp_path: Path):
    write_text(tmp_path / 'script.txt', '内容。')
    write_json(tmp_path / 'tts-lexicon.json', {})
    write_text(tmp_path / 'narration.txt', '内容。')
    write_json(tmp_path / 'narration-offsets.json', {
        'version': 1, 'script_length': 3, 'narration_length': 3, 'segments': [],
    })
    proc = run_cli(
        '--mode', 'subtitles',
        '--transcript', str(tmp_path / 'transcribe' / 'transcript.json'),
        '--narration', str(tmp_path / 'narration.txt'),
        '--offsets', str(tmp_path / 'narration-offsets.json'),
        '--script', str(tmp_path / 'script.txt'),
        '--units-output', str(tmp_path / 'units.json'),
        '--width', '1200', '--font-size', '42', '--max-lines', '1',
    )
    assert proc.returncode == 1
    result = json.loads(proc.stdout)
    assert result['success'] is False


def test_offsets_without_content_hashes_are_rejected(tmp_path: Path):
    """缺内容哈希的偏移表不能降级成“只比字数”：直接调用对齐也要拒绝。"""
    script_text = '内容。'
    write_text(tmp_path / 'script.txt', script_text)
    write_json(tmp_path / 'tts-lexicon.json', {})
    write_text(tmp_path / 'narration.txt', script_text)
    write_json(tmp_path / 'narration-offsets.json', {
        'version': 1,
        'script_length': len(script_text),
        'narration_length': len(script_text),
        'segments': [{'narration_start': 0, 'narration_end': 3, 'script_start': 0, 'script_end': 3}],
    })
    write_json(tmp_path / 'transcribe' / 'transcript.json', [
        {'begin': 0, 'end': 500, 'text': '内容', 'words': [{'text': '内容', 'begin': 0, 'end': 500}]},
    ])
    proc = run_cli(
        '--mode', 'timing',
        '--transcript', str(tmp_path / 'transcribe' / 'transcript.json'),
        '--narration', str(tmp_path / 'narration.txt'),
        '--offsets', str(tmp_path / 'narration-offsets.json'),
        '--script', str(tmp_path / 'script.txt'),
        '--timeline-output', str(tmp_path / 'timeline.json'),
    )
    assert proc.returncode == 1
    result = json.loads(proc.stdout)
    assert result['success'] is False
    assert 'script_sha256' in result['error']
    assert not (tmp_path / 'timeline.json').exists()


def test_transcript_without_word_timestamps_exit_1(tmp_path: Path):
    write_text(tmp_path / 'script.txt', '内容。')
    write_json(tmp_path / 'tts-lexicon.json', {})
    mn = subprocess.run(
        [sys.executable, str(MAKE_NARRATION),
         '--script', str(tmp_path / 'script.txt'),
         '--lexicon', str(tmp_path / 'tts-lexicon.json'),
         '--output-dir', str(tmp_path)],
        capture_output=True, text=True,
    )
    assert mn.returncode == 0
    write_json(tmp_path / 'transcribe' / 'transcript.json', [
        {'begin': 0, 'end': 500, 'text': '内容', 'words': []},
    ])
    proc = run_cli(
        '--mode', 'subtitles',
        '--transcript', str(tmp_path / 'transcribe' / 'transcript.json'),
        '--narration', str(tmp_path / 'narration.txt'),
        '--offsets', str(tmp_path / 'narration-offsets.json'),
        '--script', str(tmp_path / 'script.txt'),
        '--units-output', str(tmp_path / 'units.json'),
        '--width', '1200', '--font-size', '42', '--max-lines', '1',
    )
    assert proc.returncode == 1
    result = json.loads(proc.stdout)
    assert result['success'] is False


# --- layout region definitions --------------------------------------------------


def layout_cap(layout_path: Path) -> tuple[int, int]:
    """(cap in CJK units, max_lines) recomputed from the layout JSON itself."""
    caption = json.loads(layout_path.read_text(encoding='utf-8'))['caption']
    cap = int(caption['width_px'] / caption['font_size_px']) * caption['max_lines']
    return cap, caption['max_lines']


def test_presenter_layout_caps_every_unit(tmp_path: Path):
    # presenter.json: 1166px / 36px / 1 line. Every unit must fit the display
    # width cap recomputed from the JSON, never a hardcoded number.
    cap, max_lines = layout_cap(PRESENTER_LAYOUT)
    proc, result, units_data, _ = make_workspace(
        tmp_path, REGRESSION_SCRIPT, {}, REGRESSION_TRANSCRIPT,
        layout=PRESENTER_LAYOUT,
    )
    assert proc.returncode == 0, proc.stderr
    assert cap == int(1166 / 36) * 1
    assert max_lines == 1
    for text in unit_texts(units_data):
        assert display_width(text) <= cap


@pytest.mark.parametrize('subtitle_args', [
    pytest.param((), id='layout-only'),
    pytest.param(('--width', '100', '--font-size', '42', '--max-lines', '1'), id='layout-overrides-flags'),
])
def test_portrait_layout_allows_two_lines(tmp_path: Path, subtitle_args):
    # 27 display units: one 22-unit line (940/42) cannot hold the sentence,
    # two lines (cap 44) keep it in a single unit.
    script_text = '今天天气真的很不错非常适合出门散步晒太阳感受春天的气息。'  # 27 units
    transcript = [
        {
            'begin': 0,
            'end': 3000,
            'text': script_text,
            'words': [{'text': script_text.rstrip('。'), 'begin': 0, 'end': 3000}],
        }
    ]
    cap, max_lines = layout_cap(PORTRAIT_LAYOUT)
    assert max_lines == 2
    one_line_cap = cap // max_lines
    assert one_line_cap < display_width(script_text.rstrip('。')) <= cap

    proc, _, units_data, _ = make_workspace(
        tmp_path, script_text, {}, transcript, layout=PORTRAIT_LAYOUT, subtitle_args=subtitle_args,
    )
    assert proc.returncode == 0, proc.stderr
    assert unit_texts(units_data) == [script_text.rstrip('。').rstrip('，')]


def test_timing_mode_needs_no_caption_spec_and_writes_no_units(tmp_path: Path):
    """timing 不读 layout、不要字幕参数，也不产字幕单元。"""
    proc, result, units_data, timeline_data = make_workspace(
        tmp_path, REGRESSION_SCRIPT, {}, REGRESSION_TRANSCRIPT,
    )
    assert proc.returncode == 0, proc.stderr
    assert timeline_data['paragraphs']
    assert units_data['units']
    assert result['mode'] == 'subtitles'

    timing = run_cli(
        '--mode', 'timing',
        '--transcript', str(tmp_path / 'transcribe' / 'transcript.json'),
        '--narration', str(tmp_path / 'narration.txt'),
        '--offsets', str(tmp_path / 'narration-offsets.json'),
        '--script', str(tmp_path / 'script.txt'),
        '--timeline-output', str(tmp_path / 'timeline-only.json'),
    )
    assert timing.returncode == 0, timing.stderr
    payload = json.loads(timing.stdout)
    assert payload['mode'] == 'timing'
    assert payload['timeline_path'].endswith('timeline-only.json')


def test_mode_is_required_and_must_match_the_parameters(tmp_path: Path):
    base = [
        '--transcript', 'x.json', '--narration', 'n.txt', '--offsets', 'o.json', '--script', 's.txt',
    ]
    assert run_cli(*base).returncode == 2
    # timing 不接受按字幕容量算出来的参数
    assert run_cli(*base, '--mode', 'timing', '--layout', 'l.json').returncode == 2
    assert run_cli(*base, '--mode', 'timing', '--width', '100', '--font-size', '40', '--max-lines', '1').returncode == 2
    # subtitles 不写时间轴
    assert run_cli(*base, '--mode', 'subtitles', '--units-output', 'u.json',
                   '--timeline-output', 't.json',
                   '--width', '100', '--font-size', '40', '--max-lines', '1').returncode == 2


def test_caption_spec_required_without_layout(tmp_path: Path):
    # subtitles mode needs either --layout or the explicit width flags.
    proc = run_cli(
        '--mode', 'subtitles',
        '--transcript', 'x.json',
        '--narration', 'n.txt',
        '--offsets', 'o.json',
        '--script', 's.txt',
    )
    assert proc.returncode == 2
    result = json.loads(proc.stdout)
    assert result['success'] is False


def test_layout_file_without_caption_spec_exits_1(tmp_path: Path):
    bad_layout = tmp_path / 'bad-layout.json'
    write_json(bad_layout, {'layout': 'broken', 'canvas': {'width': 1, 'height': 1}})
    proc, result, _, _ = make_workspace(
        tmp_path, REGRESSION_SCRIPT, {}, REGRESSION_TRANSCRIPT,
        layout=bad_layout,
    )
    assert proc.returncode == 1
    assert result['success'] is False


def test_timing_mode_places_template_cue_declarations(tmp_path: Path):
    """模板的入场锚点用同一次对齐取时间：cue 声明 → template-timeline.json。"""
    script_text = 'OpenHuman 是一个项目。\n\n本周它涨了 2000 个 star。\n'
    transcript = [
        {
            'begin': 0,
            'end': 2200,
            'text': script_text.split('\n\n')[0],
            'words': [
                {'text': 'OpenHuman', 'begin': 0, 'end': 700},
                {'text': '是一个项目', 'begin': 700, 'end': 2200},
            ],
        },
        {
            'begin': 2200,
            'end': 4000,
            'text': script_text.split('\n\n')[1].strip(),
            'words': [
                {'text': '本周它涨了', 'begin': 2200, 'end': 3200},
                {'text': '2000', 'begin': 3200, 'end': 3500},
                {'text': '个star', 'begin': 3500, 'end': 4000},
            ],
        },
    ]
    cues = [
        {'scene_id': 'project-cover', 'paragraphs': [1], 'cues': ['OpenHuman']},
        {'scene_id': 'stars', 'paragraphs': [2], 'cues': ['2000 个 star']},
    ]

    proc, _, _, timeline_data = make_workspace(
        tmp_path, script_text, {}, transcript, scene_plan=cues,
    )

    assert proc.returncode == 0, proc.stderr
    located = {cue['scene_id']: cue for cue in timeline_data['cues']}
    assert set(located) == {'project-cover', 'stars'}
    assert located['project-cover']['begin_s'] == 0.0
    # 第二段从 2.2 s 开始，cue 落在该句内：时间来自实际对齐，不是按字数推算的。
    assert 2.2 <= located['stars']['begin_s'] < located['stars']['end_s'] <= 4.0
