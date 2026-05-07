#!/usr/bin/env python3
"""Flag CJK text rendered by Latin-only handwriting fonts in HyperFrames HTML."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
UNSAFE_FONT_NAME_RE = re.compile(r"(?:Caveat|PatrickHand)", re.IGNORECASE)
CSS_RULE_RE = re.compile(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]+)\}", re.MULTILINE)
CLASS_SELECTOR_RE = re.compile(r"\.([A-Za-z_][A-Za-z0-9_-]*)")
CSS_VAR_DECL_RE = re.compile(r"(?P<name>--[A-Za-z0-9_-]+)\s*:\s*(?P<value>[^;{}]+)")
CSS_VAR_USE_RE = re.compile(r"var\(\s*(--[A-Za-z0-9_-]+)")
FONT_FAMILY_DECL_RE = re.compile(r"font-family\s*:\s*(?P<value>[^;{}]+)", re.IGNORECASE)


@dataclass(frozen=True)
class Finding:
    line: int
    col: int
    source: str
    text: str


def extract_unsafe_css_variables(html: str) -> set[str]:
    variables: dict[str, str] = {}
    for rule in CSS_RULE_RE.finditer(html):
        for declaration in CSS_VAR_DECL_RE.finditer(rule.group("body")):
            variables[declaration.group("name")] = declaration.group("value")

    unsafe_vars: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, value in variables.items():
            if name in unsafe_vars:
                continue
            if UNSAFE_FONT_NAME_RE.search(value) or any(var_name in unsafe_vars for var_name in CSS_VAR_USE_RE.findall(value)):
                unsafe_vars.add(name)
                changed = True
    return unsafe_vars


def has_unsafe_font_family(style: str, unsafe_vars: set[str]) -> bool:
    for declaration in FONT_FAMILY_DECL_RE.finditer(style):
        value = declaration.group("value")
        if UNSAFE_FONT_NAME_RE.search(value):
            return True
        if any(var_name in unsafe_vars for var_name in CSS_VAR_USE_RE.findall(value)):
            return True
    return False


def extract_unsafe_classes(html: str, unsafe_vars: set[str]) -> set[str]:
    classes: set[str] = set()
    for rule in CSS_RULE_RE.finditer(html):
        if not has_unsafe_font_family(rule.group("body"), unsafe_vars):
            continue
        for class_name in CLASS_SELECTOR_RE.findall(rule.group("selectors")):
            classes.add(class_name)
    return classes


class CjkFontParser(HTMLParser):
    def __init__(self, unsafe_classes: set[str], unsafe_vars: set[str]) -> None:
        super().__init__(convert_charrefs=True)
        self.unsafe_classes = unsafe_classes
        self.unsafe_vars = unsafe_vars
        self.stack: list[tuple[str, list[str]]] = []
        self.findings: list[Finding] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name: value or "" for name, value in attrs}
        inherited = self.stack[-1][1].copy() if self.stack else []
        sources = inherited + self._sources_for_element(tag, attr_map)
        self.stack.append((tag, sources))

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if not self.stack or not CJK_RE.search(data):
            return
        sources = self.stack[-1][1]
        if not sources:
            return
        line, col = self.getpos()
        text = " ".join(data.split())
        if text:
            self.findings.append(Finding(line=line, col=col, source=", ".join(sources), text=text))

    def _sources_for_element(self, tag: str, attr_map: dict[str, str]) -> list[str]:
        sources: list[str] = []
        inline_style = attr_map.get("style", "")
        if has_unsafe_font_family(inline_style, self.unsafe_vars):
            sources.append(f"<{tag}> inline style")

        for class_name in attr_map.get("class", "").split():
            if class_name in self.unsafe_classes:
                sources.append(f".{class_name}")
        return sources


def check_file(path: Path) -> list[Finding]:
    html = path.read_text(encoding="utf-8")
    unsafe_vars = extract_unsafe_css_variables(html)
    parser = CjkFontParser(extract_unsafe_classes(html, unsafe_vars), unsafe_vars)
    parser.feed(html)
    return parser.findings


def main() -> int:
    arg_parser = argparse.ArgumentParser(
        description="Detect Chinese text inside elements styled with Caveat or PatrickHand."
    )
    arg_parser.add_argument("html_file", type=Path, help="Path to a HyperFrames HTML file, usually index.html")
    args = arg_parser.parse_args()

    findings = check_file(args.html_file)
    if not findings:
        print(f"OK: no CJK text found in Caveat/PatrickHand contexts: {args.html_file}")
        return 0

    print(f"ERROR: CJK text is using Latin-only font contexts in {args.html_file}", file=sys.stderr)
    for finding in findings:
        print(
            f"  line {finding.line}:{finding.col} via {finding.source}: {finding.text}",
            file=sys.stderr,
        )
    print(
        "Fix: split mixed text into spans and use MaShanZheng/LongCang for Chinese, Caveat/PatrickHand only for Latin/numbers.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
