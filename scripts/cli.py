"""Shared command-line JSON output and exit-code helpers."""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from typing import Any


class JsonArgumentParser(argparse.ArgumentParser):
    def __init__(self, tool_name: str, **kwargs: Any) -> None:
        self.tool_name = tool_name
        super().__init__(**kwargs)

    def error(self, message: str) -> None:
        print(f'[{self.tool_name}] bad arguments: {message}', file=sys.stderr)
        print_json({'success': False, 'error': message})
        self.exit(2)


def make_logger(tool_name: str) -> Callable[[str], None]:
    def log(message: str) -> None:
        print(f'[{tool_name}] {message}', file=sys.stderr)

    return log


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def run(main: Callable[[], int | None], tool_name: str) -> int:
    try:
        result = main()
        return 0 if result is None else result
    except SystemExit:
        raise
    except Exception as exc:
        print(f'[{tool_name}] error: {exc}', file=sys.stderr)
        payload = {'success': False, 'error': str(exc)}
        stderr_tail = getattr(exc, 'stderr_tail', None)
        if stderr_tail is not None:
            payload['stderr_tail'] = stderr_tail
        print_json(payload)
        return 1
