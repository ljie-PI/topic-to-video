#!/usr/bin/env python3
"""composition 可检查源文件的共享定义。

check-composition.py（把源文件指纹写进报告）与 pipeline-status.py（在后续扫描
中比对这份指纹）必须对“哪些文件决定渲染出的 DOM”有完全一致的判断，因此规则只
在这里写一份。

可检查源文件是 index.html 加上 compositions/ 与 assets/ 下所有可见文件，但
assets/fonts/ 除外：字体是从 resources/fonts/ 原样字节复制而来，重新复制它们
（每次 prepare 都会跑 fonts-download.sh）不应让已保存的检查报告失效。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

# 其可见文件属于可检查源文件的目录（相对于 composition 目录）。
# index.html 存在时总是包含在内。
SOURCE_DIRS = ('compositions', 'assets')
FONT_DIR = 'assets/fonts'


def visible_files(directory: Path) -> list[Path]:
    """`directory` 下任意深度的文件；像 .DS_Store 这样的隐藏文件不计入。"""
    return [
        item
        for item in directory.rglob('*')
        if item.is_file() and not any(part.startswith('.') for part in item.relative_to(directory).parts)
    ]


def composition_source_relpaths(composition_dir: Path) -> list[str]:
    """可检查源文件，表示为相对于 composition_dir 的 posix 路径，已排序。"""
    paths: list[Path] = []
    index = composition_dir / 'index.html'
    if index.is_file():
        paths.append(index)
    for name in SOURCE_DIRS:
        subdir = composition_dir / name
        if subdir.is_dir():
            paths.extend(
                path
                for path in visible_files(subdir)
                if FONT_DIR not in path.relative_to(composition_dir).as_posix().split('/')
            )
    return sorted(path.relative_to(composition_dir).as_posix() for path in paths)


def fingerprint_relpaths(root: Path, relpaths: list[str]) -> str:
    """对排序后的各 relpath 及其当前内容算出一个 sha256。

    已不存在的文件按 <absent> 参与哈希，因此删掉一个源文件却不重新检查，也会
    表现为指纹变化。
    """
    digest = hashlib.sha256()
    for relpath in sorted(relpaths):
        digest.update(relpath.encode('utf-8'))
        digest.update(b'\0')
        path = root / relpath
        if path.is_file():
            with path.open('rb') as handle:
                for chunk in iter(lambda: handle.read(1 << 20), b''):
                    digest.update(chunk)
        else:
            digest.update(b'<absent>')
        digest.update(b'\n')
    return digest.hexdigest()


def composition_sources_fingerprint(composition_dir: Path) -> str:
    """嵌入 check-composition 报告中的源文件指纹。"""
    return fingerprint_relpaths(composition_dir, composition_source_relpaths(composition_dir))
