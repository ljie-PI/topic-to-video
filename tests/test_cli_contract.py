"""Cross-entrypoint tests for the shared JSON stdout / exit-code contract."""
from __future__ import annotations

import importlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / 'scripts'
EXCLUDED_ENTRYPOINTS = {'narrate.py', 'tts_qwen.py'}
MAIN_GUARD = re.compile(r"if __name__ == ['\"]__main__['\"]")

ENTRYPOINTS = sorted(
    [
        path
        for path in SCRIPTS_DIR.glob('*.py')
        if path.name not in EXCLUDED_ENTRYPOINTS and MAIN_GUARD.search(path.read_text(encoding='utf-8'))
    ]
    + list(SCRIPTS_DIR.glob('*.sh')),
    key=lambda path: path.name,
)


def run_script(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(script)] if script.suffix == '.py' else ['bash', str(script)]
    return subprocess.run(
        [*command, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def assert_single_json_stdout(proc: subprocess.CompletedProcess[str]) -> dict:
    lines = proc.stdout.splitlines()
    assert len(lines) == 1, f'expected one stdout line, got: {proc.stdout!r}'
    return json.loads(lines[0])


@pytest.mark.parametrize('script', ENTRYPOINTS, ids=lambda path: path.name)
def test_invalid_flag_is_one_json_error_on_stdout(script: Path, tmp_path: Path):
    proc = run_script(script, '--definitely-not-a-flag', cwd=tmp_path)

    assert proc.returncode == 2, proc.stderr
    result = assert_single_json_stdout(proc)
    assert result['success'] is False
    assert 'Traceback' not in proc.stderr


def test_gemini_self_check_runtime_error_is_json_without_output_dir(tmp_path: Path):
    proc = run_script(
        SCRIPTS_DIR / 'gemini-deep-research.py',
        '--self-check',
        '--profile-dir',
        str(tmp_path / 'chrome_profile'),
        '--chrome-path',
        '/nonexistent',
        '--cdp-url',
        'http://127.0.0.1:9',
        cwd=tmp_path,
    )

    assert proc.returncode == 1, proc.stderr
    result = assert_single_json_stdout(proc)
    assert result['success'] is False
    assert 'Traceback' not in proc.stderr
    assert not (tmp_path / 'chrome_profile').exists()


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(str(SCRIPTS_DIR))
    try:
        return importlib.import_module('cli')
    except ModuleNotFoundError as exc:
        pytest.fail(f'scripts/cli.py must be importable: {exc}')


def test_json_argument_parser_error_uses_tool_name_and_exit_2(cli, capsys: pytest.CaptureFixture[str]):
    parser = cli.JsonArgumentParser('example-tool')

    with pytest.raises(SystemExit) as exc_info:
        parser.error('bad 参数')

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == '{"success": false, "error": "bad 参数"}\n'
    assert captured.err == '[example-tool] bad arguments: bad 参数\n'


def test_make_logger_writes_prefixed_stderr(cli, capsys: pytest.CaptureFixture[str]):
    log = cli.make_logger('example-tool')

    log('处理中')

    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err == '[example-tool] 处理中\n'


def test_print_json_writes_one_unicode_json_line(cli, capsys: pytest.CaptureFixture[str]):
    cli.print_json({'success': True, 'message': '你好'})

    captured = capsys.readouterr()
    assert captured.out == '{"success": true, "message": "你好"}\n'
    assert captured.err == ''


@pytest.mark.parametrize('return_value, expected', [(None, 0), (0, 0), (7, 7)])
def test_run_returns_main_exit_code(cli, return_value, expected: int):
    assert cli.run(lambda: return_value, 'example-tool') == expected


def test_run_preserves_system_exit(cli):
    def main():
        raise SystemExit(9)

    with pytest.raises(SystemExit) as exc_info:
        cli.run(main, 'example-tool')

    assert exc_info.value.code == 9


@pytest.mark.parametrize('exception', [RuntimeError('boom'), ImportError('missing dependency')])
def test_run_converts_unhandled_exceptions_to_json(
    cli, exception: Exception, capsys: pytest.CaptureFixture[str]
):
    def main():
        raise exception

    assert cli.run(main, 'example-tool') == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {'success': False, 'error': str(exception)}
    assert len(captured.out.splitlines()) == 1
    assert captured.err == f'[example-tool] error: {exception}\n'
