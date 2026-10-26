"""CLI contract tests for scripts/vision-analyze.py."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'vision-analyze.py'
IMAGE_URL = 'https://example.com/image.jpg'


def run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )


def delegate_env() -> dict[str, str]:
    env = os.environ.copy()
    for name in ('VLM_API_KEY', 'VLM_BASE_URL', 'VLM_MODEL'):
        env.pop(name, None)
    return env


def test_delegate_mode_includes_context_file_content(tmp_path: Path):
    context = '这是一段关于本地优先软件的中文解说视频。\n'
    context_file = tmp_path / 'topic-context.txt'
    context_file.write_text(context, encoding='utf-8')

    proc = run_cli(
        '--prompt', '分析图片与主题的关系',
        '--images', IMAGE_URL,
        '--context-file', str(context_file),
        env=delegate_env(),
    )

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result['mode'] == 'delegate_to_agent'
    assert result['context'] == context


def test_vlm_mode_sends_context_as_first_system_message(tmp_path: Path):
    context = '重点讲解离线同步与端到端加密。'
    context_file = tmp_path / 'topic-context.txt'
    context_file.write_text(context, encoding='utf-8')
    requests: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers['Content-Length']))
            requests.append(json.loads(body))
            response = json.dumps({
                'choices': [{'message': {'role': 'assistant', 'content': '分析结果'}}],
            }).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format, *args):
            pass

    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        env = delegate_env()
        env.update({
            'VLM_API_KEY': 'test-key',
            'VLM_BASE_URL': f'http://127.0.0.1:{server.server_port}/v1',
            'VLM_MODEL': 'test-vlm',
        })
        proc = run_cli(
            '--prompt', '分析图片与主题的关系',
            '--images', IMAGE_URL,
            '--context-file', str(context_file),
            env=env,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert proc.returncode == 0, proc.stderr
    assert len(requests) == 1
    messages = requests[0]['messages']
    assert messages[0] == {'role': 'system', 'content': context}


def test_missing_context_file_is_an_argument_error(tmp_path: Path):
    proc = run_cli(
        '--prompt', '分析图片',
        '--images', IMAGE_URL,
        '--context-file', str(tmp_path / 'missing.txt'),
        env=delegate_env(),
    )

    assert proc.returncode == 2, proc.stderr
    result = json.loads(proc.stdout)
    assert result['success'] is False
    assert 'context' in result['error'].lower()
