#!/usr/bin/env python3
"""Search YouTube with Playwright and save markdown + JSON results.

Usage:
  python3 search-youtube.py --keywords "Claude Code tutorial,AI agent demo" --limit 5 --output-dir materials

Prerequisites:
  source .venv/bin/activate
  pip install playwright
  playwright install chromium
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError as exc:  # pragma: no cover - import guard for CLI use
    print("ERR: playwright is not installed. Install with: pip install playwright && playwright install chromium", file=sys.stderr)
    raise SystemExit(1) from exc

YOUTUBE_BASE_URL = "https://www.youtube.com"
SEARCH_TIMEOUT_MS = 15_000
CONSENT_SELECTORS = [
    'button:has-text("Accept all")',
    'button:has-text("I agree")',
    'button:has-text("Accept")',
    'button:has-text("Agree")',
    'button[aria-label*="Accept" i]',
    'button[aria-label*="agree" i]',
    'tp-yt-paper-button:has-text("Accept all")',
    'tp-yt-paper-button:has-text("I agree")',
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search YouTube for one or more keywords and save results.")
    parser.add_argument(
        "--keywords",
        required=True,
        help="Comma-separated search keywords, e.g. 'Claude Code tutorial,AI agent demo'",
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
        help="Directory for youtube_search_result.md/json (default: current directory)",
    )
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    return args


def normalize_keywords(raw_keywords: str) -> list[str]:
    keywords = [keyword.strip() for keyword in raw_keywords.split(",") if keyword.strip()]
    if not keywords:
        raise ValueError("No valid keywords provided")
    return keywords


def dismiss_cookie_consent(page: Any) -> None:
    for frame in page.frames:
        for selector in CONSENT_SELECTORS:
            button = frame.locator(selector).first
            try:
                button.wait_for(state="visible", timeout=1_000)
                button.click(timeout=2_000)
                page.wait_for_load_state("domcontentloaded", timeout=5_000)
                return
            except Exception:
                continue


def absolute_url(url: str | None) -> str:
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return f"{YOUTUBE_BASE_URL}{url}"
    return f"{YOUTUBE_BASE_URL}/{url.lstrip('/')}"


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def search_keyword(page: Any, keyword: str, limit: int) -> dict[str, Any]:
    search_url = f"{YOUTUBE_BASE_URL}/results?search_query={quote_plus(keyword)}"
    page.goto(search_url, wait_until="domcontentloaded", timeout=SEARCH_TIMEOUT_MS)
    dismiss_cookie_consent(page)
    if "consent." in page.url:
        page.goto(search_url, wait_until="domcontentloaded", timeout=SEARCH_TIMEOUT_MS)
    page.wait_for_selector("ytd-video-renderer", timeout=SEARCH_TIMEOUT_MS)

    renderers = page.locator("ytd-video-renderer")
    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    count = renderers.count()

    for index in range(count):
        try:
            renderer = renderers.nth(index)
            title_locator = renderer.locator("a#video-title").first
            metadata_spans = renderer.locator("#metadata-line span")

            title = clean_text(title_locator.get_attribute("title")) or clean_text(title_locator.text_content())
            url = absolute_url(title_locator.get_attribute("href"))
            views = clean_text(metadata_spans.nth(0).text_content()) if metadata_spans.count() else ""
        except Exception:
            continue

        if not title or not url or url in seen_urls:
            continue

        seen_urls.add(url)
        results.append({
            "title": title,
            "url": url,
            "views": views,
            "subscribers": "",
            "comments": "",
        })
        if len(results) >= limit:
            break

    return {
        "keyword": keyword,
        "search_url": search_url,
        "results": results,
        "error": None,
    }


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# YouTube Search Results",
        "",
        f"Generated at: {report['generated_at']}",
        f"Per-keyword limit: {report['limit']}",
        "",
    ]

    for item in report["searches"]:
        lines.append(f"## {item['keyword']}")
        lines.append("")
        if item.get("error"):
            lines.append(f"Error: {item['error']}")
            lines.append("")
            continue

        lines.append("| Title | URL | Views | Subscribers | Comments |")
        lines.append("| --- | --- | --- | --- | --- |")
        if item["results"]:
            for result in item["results"]:
                lines.append(
                    "| "
                    f"{markdown_escape(result['title'])} | "
                    f"{markdown_escape(result['url'])} | "
                    f"{markdown_escape(result['views'] or '-')} | "
                    f"{markdown_escape(result.get('subscribers') or '-')} | "
                    f"{markdown_escape(result.get('comments') or '-')} |"
                )
        else:
            lines.append("| No results found | - | - | - | - |")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def write_outputs(output_dir: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "youtube_search_result.md"
    json_path = output_dir / "youtube_search_result.json"

    markdown_path.write_text(build_markdown(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return markdown_path, json_path


def main() -> int:
    args = parse_args()
    try:
        keywords = normalize_keywords(args.keywords)
    except ValueError as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "limit": args.limit,
        "output_dir": str(args.output_dir.resolve()),
        "searches": [],
    }

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(locale="en-US")
            page = context.new_page()

            for keyword in keywords:
                try:
                    report["searches"].append(search_keyword(page, keyword, args.limit))
                except PlaywrightTimeoutError:
                    report["searches"].append({
                        "keyword": keyword,
                        "search_url": f"{YOUTUBE_BASE_URL}/results?search_query={quote_plus(keyword)}",
                        "results": [],
                        "error": "Timed out waiting for YouTube search results",
                    })
                except Exception as exc:
                    report["searches"].append({
                        "keyword": keyword,
                        "search_url": f"{YOUTUBE_BASE_URL}/results?search_query={quote_plus(keyword)}",
                        "results": [],
                        "error": str(exc),
                    })

            context.close()
            browser.close()
    except Exception as exc:
        print(f"ERR: failed to start Playwright Chromium: {exc}", file=sys.stderr)
        return 1

    markdown_path, json_path = write_outputs(args.output_dir, report)
    success_count = sum(1 for item in report["searches"] if not item.get("error"))
    result_count = sum(len(item["results"]) for item in report["searches"])
    failure_count = len(report["searches"]) - success_count

    print(f"Processed {len(report['searches'])} keyword(s): {result_count} result(s), {failure_count} failure(s)")
    print(f"Markdown: {markdown_path}")
    print(f"JSON: {json_path}")
    return 0 if success_count or not report["searches"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
