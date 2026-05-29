"""
Offline tests for transcribe-paraformer.py.

不联网，不调用 DashScope。覆盖：
- argv 个数错误 → exit 2，stdout 是 success:false JSON
- 文件不存在 → exit 1
- 缺 DASHSCOPE_API_KEY → exit 1
- parse_transcription_payload 把 paraformer-v2 JSON 转成项目 schema
- ASR_LANGUAGE_HINTS 解析
- 实际向 dashscope SDK 拿到 OssUtils.upload / Transcription.async_call / wait 的
  正确 signature（防止 SDK 版本不兼容）
"""
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).parent / 'transcribe-paraformer.py'


def load_module():
    spec = importlib.util.spec_from_file_location('transcribe_paraformer', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_cli(args, env=None):
    """Run the script as a subprocess, return (rc, stdout, stderr)."""
    full_env = os.environ.copy()
    if env is not None:
        full_env.update(env)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=full_env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_bad_argv():
    rc, out, _ = run_cli([])
    assert rc == 2
    payload = json.loads(out.strip().splitlines()[-1])
    assert payload['success'] is False
    assert 'Usage' in payload['error']


def test_missing_file():
    env = {'DASHSCOPE_API_KEY': 'sk-fake'}
    rc, out, _ = run_cli(['/nope/does-not-exist.mp3', '/tmp/out.json'], env=env)
    assert rc == 1
    payload = json.loads(out.strip().splitlines()[-1])
    assert payload['success'] is False
    assert 'not found' in payload['error']


def test_missing_api_key(tmp_path):
    audio = tmp_path / 'a.mp3'
    audio.write_bytes(b'\x00')
    out_json = tmp_path / 'out.json'
    env = os.environ.copy()
    env.pop('DASHSCOPE_API_KEY', None)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(audio), str(out_json)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload['success'] is False
    assert 'DASHSCOPE_API_KEY' in payload['error']


def test_parse_transcription_payload():
    module = load_module()
    payload = {
        'transcripts': [
            {
                'channel_id': 0,
                'content_duration_in_milliseconds': 2000,
                'text': '为什么 paraformer-v2 更好。',
                'sentences': [
                    {
                        'begin_time': 0,
                        'end_time': 1200,
                        'text': '为什么 paraformer-v2 更好。',
                        'words': [
                            {'begin_time': 0, 'end_time': 300, 'text': '为什么', 'punctuation': ''},
                            {'begin_time': 300, 'end_time': 1100, 'text': 'paraformer-v2', 'punctuation': ''},
                            {'begin_time': 1100, 'end_time': 1200, 'text': '更好', 'punctuation': '。'},
                        ],
                    },
                ],
            }
        ]
    }
    out = module.parse_transcription_payload(payload)
    assert len(out) == 1
    assert out[0]['begin'] == 0
    assert out[0]['end'] == 1200
    assert out[0]['text'] == '为什么 paraformer-v2 更好。'
    assert out[0]['words'] == [
        {'text': '为什么', 'begin': 0, 'end': 300},
        {'text': 'paraformer-v2', 'begin': 300, 'end': 1100},
        {'text': '更好。', 'begin': 1100, 'end': 1200},
    ]


def test_parse_empty_payload():
    module = load_module()
    assert module.parse_transcription_payload({}) == []
    assert module.parse_transcription_payload({'transcripts': []}) == []
    assert module.parse_transcription_payload(
        {'transcripts': [{'sentences': None}]}
    ) == []


def test_language_hints_default(monkeypatch):
    module = load_module()
    monkeypatch.delenv('ASR_LANGUAGE_HINTS', raising=False)
    assert module.parse_language_hints() == ['zh', 'en']


def test_language_hints_env(monkeypatch):
    module = load_module()
    monkeypatch.setenv('ASR_LANGUAGE_HINTS', '["en"]')
    assert module.parse_language_hints() == ['en']


def test_language_hints_invalid(monkeypatch):
    module = load_module()
    monkeypatch.setenv('ASR_LANGUAGE_HINTS', 'not-json')
    try:
        module.parse_language_hints()
    except ValueError as e:
        assert 'not valid JSON' in str(e)
    else:
        raise AssertionError('expected ValueError')


def test_dashscope_sdk_api_surface():
    """SDK 1.25+ contract check — guards against signature drift."""
    import inspect
    from dashscope.audio.asr import Transcription
    from dashscope.utils.oss_utils import OssUtils

    async_sig = inspect.signature(Transcription.async_call)
    assert 'model' in async_sig.parameters
    assert 'file_urls' in async_sig.parameters

    wait_sig = inspect.signature(Transcription.wait)
    # 关键: 第一参数叫 `task`，不是 `task_id`
    assert 'task' in wait_sig.parameters
    assert 'task_id' not in wait_sig.parameters

    upload_sig = inspect.signature(OssUtils.upload)
    assert 'model' in upload_sig.parameters
    assert 'file_path' in upload_sig.parameters
    assert 'api_key' in upload_sig.parameters


if __name__ == '__main__':
    failures = []
    tests = [v for k, v in globals().items() if k.startswith('test_') and callable(v)]
    for t in tests:
        try:
            # build minimal fixtures for tests that need them
            if 'monkeypatch' in t.__code__.co_varnames:
                class MP:
                    def __init__(self): self._undo = []
                    def setenv(self, k, v):
                        old = os.environ.get(k)
                        os.environ[k] = v
                        self._undo.append((k, old))
                    def delenv(self, k, raising=True):
                        old = os.environ.pop(k, None)
                        self._undo.append((k, old))
                    def undo(self):
                        for k, old in self._undo:
                            if old is None:
                                os.environ.pop(k, None)
                            else:
                                os.environ[k] = old
                mp = MP()
                try:
                    t(mp)
                finally:
                    mp.undo()
            elif 'tmp_path' in t.__code__.co_varnames:
                with tempfile.TemporaryDirectory() as d:
                    t(Path(d))
            else:
                t()
            print(f'PASS {t.__name__}')
        except AssertionError as e:
            failures.append((t.__name__, f'AssertionError: {e}'))
            print(f'FAIL {t.__name__}: {e}')
        except Exception as e:
            failures.append((t.__name__, f'{type(e).__name__}: {e}'))
            print(f'ERROR {t.__name__}: {type(e).__name__}: {e}')
    print(f'\n{len(tests) - len(failures)}/{len(tests)} passed')
    sys.exit(1 if failures else 0)
