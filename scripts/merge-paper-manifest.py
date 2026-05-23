#!/usr/bin/env python3
"""Merge parse-pdf.py paper entries into harvest_page/manifest.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def log(message: str) -> None:
    print(f"[merge-paper-manifest] {message}", file=sys.stderr)


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        log(f"bad arguments: {message}")
        print_json({"success": False, "error": message})
        raise SystemExit(2)


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def main() -> int:
    parser = JsonArgumentParser(description="Merge manifest_papers.json into manifest.json.")
    parser.add_argument("--harvest-dir", required=True, type=Path, help="harvest_page directory")
    args = parser.parse_args()

    try:
        harvest_dir = args.harvest_dir.expanduser().resolve()
        papers_path = harvest_dir / "manifest_papers.json"
        manifest_path = harvest_dir / "manifest.json"

        if not papers_path.is_file():
            raise FileNotFoundError(f"paper manifest not found: {papers_path}")

        papers = read_json(papers_path)
        paper_entries = papers.get("entries") or []
        if not isinstance(paper_entries, list):
            raise ValueError("manifest_papers.json entries must be a list")

        if manifest_path.is_file():
            manifest = read_json(manifest_path)
            entries = manifest.get("entries") or []
            if not isinstance(entries, list):
                raise ValueError("manifest.json entries must be a list")
            manifest["entries"] = [
                entry for entry in entries if entry.get("source_type") != "paper_pdf"
            ]
        else:
            manifest = {"success": True, "entries": [], "pending_downloads": []}

        manifest["entries"] = paper_entries + manifest["entries"]
        manifest["success"] = bool(manifest["entries"])
        manifest.setdefault("pending_downloads", [])

        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print_json(
            {
                "success": True,
                "output_path": str(manifest_path),
                "paper_entries": len(paper_entries),
                "total_entries": len(manifest["entries"]),
            }
        )
        return 0
    except Exception as exc:
        log(f"error: {exc}")
        print_json({"success": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
