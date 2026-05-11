#!/usr/bin/env python3
"""Search Bing Images with Playwright and export markdown + JSON results.

Usage:
  python3 search-images.py --keywords "AI chip,GPU architecture" --limit 8 --output-dir materials

Requires:
  pip install playwright
  playwright install chromium

This script opens Bing Images for each comma-separated keyword, waits for image
results to load, extracts image metadata from Bing's `a.iusc` result anchors,
and falls back to `img.mimg` images when needed.

Outputs:
  - image_search_result.md
  - image_search_result.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
except ImportError:  # pragma: no cover - runtime dependency check
    PlaywrightTimeoutError = TimeoutError
    sync_playwright = None


DEFAULT_LIMIT = 8
RESULT_WAIT_TIMEOUT_MS = 15_000
PAGE_TIMEOUT_MS = 30_000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search Bing Images and export markdown and JSON results.")
    parser.add_argument(
        "--keywords",
        required=True,
        help="Comma-separated search keywords, e.g. 'AI chip,GPU architecture'",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Per-keyword result limit (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for image_search_result.md and image_search_result.json (default: current dir)",
    )
    return parser.parse_args()


def parse_keywords(raw_keywords: str) -> list[str]:
    return [keyword.strip() for keyword in raw_keywords.split(",") if keyword.strip()]


def build_search_url(keyword: str) -> str:
    return f"https://www.bing.com/images/search?q={quote_plus(keyword)}&form=HDRSC2"


def dedupe_results(results: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in results:
        image_url = (item.get("image_url") or "").strip()
        thumbnail_url = (item.get("thumbnail_url") or "").strip()
        key = image_url or thumbnail_url
        if not key or key in seen:
            continue

        seen.add(key)
        deduped.append(
            {
                "description": (item.get("description") or "").strip(),
                "thumbnail_url": thumbnail_url,
                "image_url": image_url,
                "size": (item.get("size") or "").strip(),
            }
        )
        if len(deduped) >= limit:
            break

    return deduped


def extract_anchor_results(page: Any) -> list[dict[str, Any]]:
    return page.evaluate(
        """
        () => Array.from(document.querySelectorAll('a.iusc')).map((anchor) => {
            let meta = {};
            const rawMeta = anchor.getAttribute('m') || '';
            if (rawMeta) {
                try {
                    meta = JSON.parse(rawMeta);
                } catch (_error) {
                    meta = {};
                }
            }

            const card = anchor.closest('.iuscp') || anchor.closest('.imgpt') || anchor.parentElement;
            const size = (
                card?.querySelector('.fileInfo')?.textContent ||
                card?.querySelector('.imgpt .des')?.textContent ||
                card?.querySelector('.des')?.textContent ||
                ''
            ).trim();

            const img = anchor.querySelector('img');
            const description = (
                meta.t ||
                meta.desc ||
                anchor.getAttribute('aria-label') ||
                anchor.getAttribute('title') ||
                img?.getAttribute('alt') ||
                ''
            ).trim();

            return {
                description,
                thumbnail_url: (meta.turl || img?.getAttribute('src') || img?.currentSrc || '').trim(),
                image_url: (meta.murl || '').trim(),
                size,
            };
        })
        """
    )


def extract_fallback_results(page: Any) -> list[dict[str, Any]]:
    return page.evaluate(
        """
        () => Array.from(document.querySelectorAll('img.mimg')).map((img) => {
            const card = img.closest('.iuscp') || img.closest('.imgpt') || img.parentElement;
            const src = (img.currentSrc || img.getAttribute('src') || '').trim();
            const size = (
                card?.querySelector('.fileInfo')?.textContent ||
                card?.querySelector('.imgpt .des')?.textContent ||
                card?.querySelector('.des')?.textContent ||
                ''
            ).trim();

            return {
                description: (img.getAttribute('alt') || img.getAttribute('aria-label') || '').trim(),
                thumbnail_url: src,
                image_url: src,
                size,
            };
        })
        """
    )


def search_keyword(page: Any, keyword: str, limit: int) -> dict[str, Any]:
    search_url = build_search_url(keyword)
    group: dict[str, Any] = {
        "keyword": keyword,
        "search_url": search_url,
        "results": [],
        "error": None,
    }

    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
        try:
            page.wait_for_load_state("networkidle", timeout=5_000)
        except PlaywrightTimeoutError:
            pass

        page.wait_for_function(
            "() => !!document.querySelector('a.iusc, img.mimg')",
            timeout=RESULT_WAIT_TIMEOUT_MS,
        )
        page.wait_for_timeout(1_000)

        anchor_results = dedupe_results(extract_anchor_results(page), limit)
        if anchor_results:
            group["results"] = anchor_results
            return group

        fallback_results = dedupe_results(extract_fallback_results(page), limit)
        if fallback_results:
            group["results"] = fallback_results
        else:
            group["error"] = "No image results found"
    except PlaywrightTimeoutError:
        group["error"] = "Timed out while waiting for Bing image results"
    except Exception as exc:  # pragma: no cover - defensive runtime handling
        group["error"] = str(exc)

    return group


def escape_markdown(text: str) -> str:
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").strip()


def format_thumbnail_cell(url: str) -> str:
    return f"![]({url})" if url else ""


def format_image_url_cell(url: str) -> str:
    return f"<{url}>" if url else ""


def render_markdown(groups: list[dict[str, Any]]) -> str:
    lines = ["# Bing Image Search Results", ""]

    for group in groups:
        keyword = escape_markdown(group["keyword"])
        lines.append(f"## {keyword}")
        lines.append("")

        error = group.get("error")
        results = group.get("results") or []
        if error and not results:
            lines.append(f"> Error: {escape_markdown(error)}")
            lines.append("")
            continue
        if not results:
            lines.append("_No results found._")
            lines.append("")
            continue

        lines.extend(
            [
                "| Description | Thumbnail | Full Image URL | Size |",
                "| --- | --- | --- | --- |",
            ]
        )
        for item in results:
            description = escape_markdown(item.get("description") or "") or "N/A"
            thumbnail = format_thumbnail_cell(item.get("thumbnail_url") or "")
            image_url = format_image_url_cell(item.get("image_url") or "")
            size = escape_markdown(item.get("size") or "")
            lines.append(f"| {description} | {thumbnail} | {image_url} | {size} |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_outputs(groups: list[dict[str, Any]], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "image_search_result.md"
    json_path = output_dir / "image_search_result.json"

    markdown_path.write_text(render_markdown(groups), encoding="utf-8")
    json_path.write_text(json.dumps(groups, ensure_ascii=False, indent=2), encoding="utf-8")
    return markdown_path, json_path


def print_summary(groups: list[dict[str, Any]], markdown_path: Path, json_path: Path) -> None:
    print("Bing image search complete:")
    for group in groups:
        keyword = group["keyword"]
        count = len(group.get("results") or [])
        error = group.get("error")
        if error and count == 0:
            print(f"- {keyword}: 0 results ({error})")
        else:
            print(f"- {keyword}: {count} results")
    print(f"- Markdown: {markdown_path}")
    print(f"- JSON: {json_path}")


def main() -> int:
    args = parse_args()
    keywords = parse_keywords(args.keywords)
    if not keywords:
        print("ERR: --keywords must contain at least one non-empty keyword", file=sys.stderr)
        return 2
    if args.limit <= 0:
        print("ERR: --limit must be greater than 0", file=sys.stderr)
        return 2
    if sync_playwright is None:
        print(
            "ERR: Playwright is not installed. Install it with 'pip install playwright' and 'playwright install chromium'.",
            file=sys.stderr,
        )
        return 1

    groups: list[dict[str, Any]] = []
    output_dir = Path(args.output_dir).expanduser()

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context()
            try:
                for keyword in keywords:
                    page = context.new_page()
                    try:
                        groups.append(search_keyword(page, keyword, args.limit))
                    finally:
                        page.close()
            finally:
                context.close()
                browser.close()
    except Exception as exc:  # pragma: no cover - defensive runtime handling
        print(
            "ERR: failed to run Playwright search: "
            f"{exc}. If Chromium is missing, run 'playwright install chromium'.",
            file=sys.stderr,
        )
        return 1

    markdown_path, json_path = write_outputs(groups, output_dir)
    print_summary(groups, markdown_path, json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
