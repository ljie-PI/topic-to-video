#!/usr/bin/env python3
"""Apply a video-download.py JSON result back into harvest manifest metadata."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv"}
SUBTITLE_EXTS = {".srt", ".vtt", ".ass", ".json"}


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def log(message: str) -> None:
    print(f"[apply-video-download] {message}", file=sys.stderr)


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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def choose_files(files: list[str]) -> tuple[str, str | None]:
    video_files = [path for path in files if Path(path).suffix.lower() in VIDEO_EXTS]
    subtitle_files = [path for path in files if Path(path).suffix.lower() in SUBTITLE_EXTS]
    if not video_files:
        raise ValueError("download result did not include a video file")
    return video_files[0], subtitle_files[0] if subtitle_files else None


def update_entry(entry: dict[str, Any], url: str, local_path: str, subtitle_path: str | None) -> bool:
    changed = False
    for video in entry.get("videos", []) or []:
        if video.get("url") != url:
            continue
        video["download_required"] = False
        video["downloaded"] = True
        video["local_path"] = local_path
        video["id"] = Path(local_path).stem
        if subtitle_path:
            video["subtitle_path"] = subtitle_path
        changed = True
    return changed


def update_metadata(harvest_dir: Path, slug: str, url: str, local_path: str, subtitle_path: str | None) -> bool:
    metadata_path = harvest_dir / slug / "metadata.json"
    if not metadata_path.is_file():
        return False
    metadata = read_json(metadata_path)
    changed = update_entry(metadata, url, local_path, subtitle_path)
    if changed:
        write_json(metadata_path, metadata)
    return changed


def main() -> int:
    parser = JsonArgumentParser(description="Update harvest manifests after video-download.py succeeds.")
    parser.add_argument("--harvest-dir", required=True, type=Path, help="harvest_page directory")
    parser.add_argument("--source-slug", required=True, help="Slug that owns the pending download")
    parser.add_argument("--url", required=True, help="Video URL from manifest.pending_downloads[]")
    parser.add_argument("--result-json", required=True, type=Path, help="JSON stdout captured from video-download.py")
    args = parser.parse_args()

    try:
        harvest_dir = args.harvest_dir.expanduser().resolve()
        manifest_path = harvest_dir / "manifest.json"
        result = read_json(args.result_json)

        if not result.get("success"):
            print_json({"success": True, "updated": False, "reason": "download failed"})
            return 0

        local_path, subtitle_path = choose_files(result.get("files") or [])
        manifest = read_json(manifest_path)

        updated_slugs = []
        for entry in manifest.get("entries", []) or []:
            if entry.get("slug") == args.source_slug and update_entry(entry, args.url, local_path, subtitle_path):
                updated_slugs.append(args.source_slug)

        for pending in manifest.get("pending_downloads", []) or []:
            if pending.get("url") != args.url:
                continue
            for slug in pending.get("also_referenced_by", []) or []:
                for entry in manifest.get("entries", []) or []:
                    if entry.get("slug") == slug and update_entry(entry, args.url, local_path, subtitle_path):
                        updated_slugs.append(slug)

        manifest["pending_downloads"] = [
            pending
            for pending in manifest.get("pending_downloads", []) or []
            if pending.get("url") != args.url
        ]

        write_json(manifest_path, manifest)

        metadata_updated = []
        for slug in sorted(set(updated_slugs)):
            if update_metadata(harvest_dir, slug, args.url, local_path, subtitle_path):
                metadata_updated.append(slug)

        print_json(
            {
                "success": True,
                "updated": bool(updated_slugs),
                "updated_slugs": sorted(set(updated_slugs)),
                "metadata_updated": metadata_updated,
                "local_path": local_path,
                "subtitle_path": subtitle_path,
            }
        )
        return 0
    except Exception as exc:
        log(f"error: {exc}")
        print_json({"success": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
