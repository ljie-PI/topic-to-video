#!/usr/bin/env python3
"""Search Bilibili videos with Playwright and export Markdown/JSON results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import quote, urljoin

PLAYWRIGHT_IMPORT_ERROR: Exception | None = None

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError as exc:  # pragma: no cover - runtime environment dependent
    PlaywrightTimeoutError = TimeoutError  # type: ignore[assignment]
    sync_playwright = None  # type: ignore[assignment]
    PLAYWRIGHT_IMPORT_ERROR = exc

CARD_SELECTOR = ".bili-video-card, [class*='video-card']"
TITLE_SELECTOR = ".bili-video-card__info--tit"
VIDEO_LINK_SELECTOR = "a[href*='/video/']"
STAT_SELECTOR = ".bili-video-card__info--icon-text"
WAIT_TIMEOUT_MS = 15_000
POST_LOAD_DELAY_MS = 1_500
TOOL_NAME = "search-bilibili"


def log(msg: str) -> None:
    print(f"[{TOOL_NAME}] {msg}", file=sys.stderr)


def emit_result(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


@dataclass
class VideoResult:
    title: str
    url: str
    plays: str = ""
    followers: str = ""
    comments: str = ""


@dataclass
class KeywordResult:
    keyword: str
    search_url: str
    results: list[VideoResult]
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = JsonArgumentParser(description="Search Bilibili and export results as Markdown and JSON.")
    parser.add_argument(
        "--keywords",
        required=True,
        help="Comma-separated search keywords, e.g. 'AI编程,Claude教程'",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Per-keyword result limit (default: 5)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Output directory for bilibili_search_result.md/json (default: current directory)",
    )
    return parser.parse_args()


def parse_keywords(raw_keywords: str) -> list[str]:
    return [keyword.strip() for keyword in raw_keywords.split(",") if keyword.strip()]


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def normalize_url(href: str | None) -> str:
    href = clean_text(href)
    if not href:
        return ""
    if href.startswith("//"):
        return f"https:{href}"
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urljoin("https://search.bilibili.com", href)


def extract_card_data(card) -> dict[str, object] | None:
    return card.evaluate(
        f"""(node) => {{
            const link = node.querySelector({json.dumps(VIDEO_LINK_SELECTOR)});
            if (!link) return null;
            const titleNode = node.querySelector({json.dumps(TITLE_SELECTOR)});
            const stats = Array.from(node.querySelectorAll({json.dumps(STAT_SELECTOR)}))
                .map((item) => (item.textContent || '').trim())
                .filter(Boolean);
            return {{
                href: link.getAttribute('href') || '',
                linkTitle: link.getAttribute('title') || '',
                linkText: link.textContent || '',
                titleAttr: titleNode?.getAttribute('title') || '',
                titleText: titleNode?.textContent || '',
                stats,
            }};
        }}"""
    )


def search_keyword(page, keyword: str, limit: int) -> KeywordResult:
    search_url = f"https://search.bilibili.com/all?keyword={quote(keyword, safe='')}"
    results: list[VideoResult] = []
    seen_urls: set[str] = set()

    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_selector(CARD_SELECTOR, timeout=WAIT_TIMEOUT_MS)
        page.wait_for_timeout(POST_LOAD_DELAY_MS)

        cards = page.locator(CARD_SELECTOR)
        for index in range(cards.count()):
            if len(results) >= limit:
                break

            card_data = extract_card_data(cards.nth(index))
            if not card_data:
                continue

            url = normalize_url(str(card_data.get("href", "")))
            if not url or "/video/" not in url or url in seen_urls:
                continue

            title = clean_text(str(card_data.get("titleAttr", "")))
            if not title:
                title = clean_text(str(card_data.get("titleText", "")))
            if not title:
                title = clean_text(str(card_data.get("linkTitle", ""))) or clean_text(str(card_data.get("linkText", "")))

            stats = [clean_text(str(item)) for item in card_data.get("stats", []) if clean_text(str(item))]
            results.append(
                VideoResult(
                    title=title or "(untitled)",
                    url=url,
                    plays=stats[0] if len(stats) > 0 else "",
                    followers=stats[1] if len(stats) > 1 else "",
                    comments=stats[2] if len(stats) > 2 else "",
                )
            )
            seen_urls.add(url)
    except PlaywrightTimeoutError:
        return KeywordResult(
            keyword=keyword,
            search_url=search_url,
            results=[],
            error="Timed out waiting for Bilibili search results.",
        )
    except Exception as exc:  # pragma: no cover - network/browser dependent
        return KeywordResult(keyword=keyword, search_url=search_url, results=[], error=str(exc))

    return KeywordResult(keyword=keyword, search_url=search_url, results=results)


def escape_markdown_cell(value: str) -> str:
    return clean_text(value).replace("|", "\\|")


def render_markdown(keyword_results: list[KeywordResult]) -> str:
    lines = ["# Bilibili Search Results", ""]
    for item in keyword_results:
        lines.extend([f"## {item.keyword}", "", f"Search URL: {item.search_url}", ""])
        if item.error:
            lines.extend([f"Error: {item.error}", ""])
            continue
        if not item.results:
            lines.extend(["No results found.", ""])
            continue
        lines.extend(
            [
                "| Title | URL | Plays | Followers | Comments |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for result in item.results:
            lines.append(
                "| {title} | {url} | {plays} | {followers} | {comments} |".format(
                    title=escape_markdown_cell(result.title),
                    url=escape_markdown_cell(result.url),
                    plays=escape_markdown_cell(result.plays),
                    followers=escape_markdown_cell(result.followers),
                    comments=escape_markdown_cell(result.comments),
                )
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(output_dir: Path, keyword_results: list[KeywordResult]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "bilibili_search_result.md"
    json_path = output_dir / "bilibili_search_result.json"

    markdown_path.write_text(render_markdown(keyword_results), encoding="utf-8")
    json_payload = {
        "keywords": [
            {
                "keyword": item.keyword,
                "search_url": item.search_url,
                "error": item.error,
                "results": [asdict(result) for result in item.results],
            }
            for item in keyword_results
        ]
    }
    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return markdown_path, json_path


def run_search(keywords: list[str], limit: int) -> list[KeywordResult]:
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not installed. Install it with 'pip install playwright' and 'playwright install chromium'."
        ) from PLAYWRIGHT_IMPORT_ERROR

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            return [search_keyword(page, keyword, limit) for keyword in keywords]
        finally:
            browser.close()


def build_success_payload(keyword_results: list[KeywordResult], output_dir: Path, files: list[str]) -> dict[str, object]:
    return {
        "success": True,
        "output_dir": str(output_dir.resolve()),
        "keywords_searched": len(keyword_results),
        "total_results": sum(len(item.results) for item in keyword_results),
        "files": files,
    }


def main() -> int:
    try:
        args = parse_args()
    except ValueError as exc:
        error = str(exc)
        log(f"Bad arguments: {error}")
        emit_result({"success": False, "error": error})
        return 2

    keywords = parse_keywords(args.keywords)
    if args.limit <= 0:
        error = "--limit must be greater than 0"
        log(f"Bad arguments: {error}")
        emit_result({"success": False, "error": error})
        return 2
    if not keywords:
        error = "--keywords must contain at least one non-empty keyword"
        log(f"Bad arguments: {error}")
        emit_result({"success": False, "error": error})
        return 2

    try:
        for keyword in keywords:
            log(f"Searching: {keyword}")
        keyword_results = run_search(keywords, args.limit)
        markdown_path, json_path = write_outputs(args.output_dir, keyword_results)
        log(f"Wrote: {markdown_path}")
        log(f"Wrote: {json_path}")
        emit_result(build_success_payload(keyword_results, args.output_dir, [markdown_path.name, json_path.name]))
        return 0
    except KeyboardInterrupt:
        error = "Interrupted."
        log(error)
        emit_result({"success": False, "error": error})
        return 1
    except Exception as exc:  # pragma: no cover - runtime environment dependent
        error = str(exc)
        log(error)
        emit_result({"success": False, "error": error})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
