#!/usr/bin/env bash
# Download deterministic local WOFF2 fonts for topic-to-video styles.
#
# Usage: bash fonts-download.sh [target_dir] [style] [--dry-run]
#   target_dir defaults to ./fonts
#   style defaults to dawn
#   style values: dawn, moon, all
#
# Downloads Google Fonts WOFF2 subsets and writes a local CSS file for each style.
set -Eeuo pipefail

log() {
  echo "[fonts] $*" >&2
}

emit_json_error() {
  python3 - "$1" <<'PY'
import json
import sys

print(json.dumps({"success": False, "error": sys.argv[1]}, ensure_ascii=False))
PY
}

emit_json_success() {
  python3 - "$TARGET" "$@" <<'PY'
import json
import sys

print(
    json.dumps(
        {
            "success": True,
            "output_dir": sys.argv[1],
            "files": sys.argv[2:],
        },
        ensure_ascii=False,
    )
)
PY
}

bad_args() {
  local message="$1"
  log "$message"
  emit_json_error "$message"
  exit 2
}

runtime_error() {
  local message="$1"
  log "$message"
  emit_json_error "$message"
  exit 1
}

on_error() {
  local command="$BASH_COMMAND"
  trap - ERR
  runtime_error "command failed: $command"
}
trap on_error ERR

TARGET="${1:-fonts}"
STYLE="${2:-dawn}"
DRY_RUN="${3:-}"

if [[ "$#" -gt 3 ]]; then
  bad_args "Usage: bash fonts-download.sh [target_dir] [style] [--dry-run]"
fi

if [[ "$DRY_RUN" != "" && "$DRY_RUN" != "--dry-run" ]]; then
  bad_args "Usage: bash fonts-download.sh [target_dir] [style] [--dry-run]"
fi

mkdir -p "$TARGET"

download_google_fonts() {
  local style_name="$1"
  local css_url="$2"
  local css_file="$TARGET/rose-pine-${style_name}-fonts.css"

  if [[ "$DRY_RUN" == "--dry-run" ]]; then
    log "dry-run ${style_name} css: $css_url"
    log "dry-run ${style_name} css output: $css_file"
    return
  fi

  python3 - "$style_name" "$css_url" "$css_file" <<'PY'
import hashlib
import re
import sys
import urllib.request
from pathlib import Path

style_name = sys.argv[1]
css_url = sys.argv[2]
css_file = Path(sys.argv[3])
target_dir = css_file.parent
headers = {"User-Agent": "Mozilla/5.0"}


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


css = fetch(css_url).decode("utf-8")
urls = list(dict.fromkeys(re.findall(r"url\((https://fonts\.gstatic\.com/[^)]+)\)", css)))
if not urls:
    raise SystemExit("No Google Font WOFF2 URLs found in CSS response")

for index, url in enumerate(urls):
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    filename = f"{style_name}-{index:02d}-{digest}.woff2"
    destination = target_dir / filename
    if destination.exists():
        print(f"[fonts] {filename} (cached)", file=sys.stderr)
    else:
        print(f"[fonts] downloading {filename}", file=sys.stderr)
        destination.write_bytes(fetch(url))
    css = css.replace(url, filename)

css = css.replace("'Noto Serif SC'", "'NotoSerifSC'")
css = css.replace("'Noto Sans SC'", "'NotoSansSC'")
css = css.replace("'IBM Plex Mono'", "'IBMPlexMono'")
css = css.replace("'Ma Shan Zheng'", "'MaShanZheng'")
css = css.replace("'Long Cang'", "'LongCang'")
css = css.replace("'Zhi Mang Xing'", "'ZhiMangXing'")
css = css.replace("'Patrick Hand'", "'PatrickHand'")
css_file.write_text(css, encoding="utf-8")
print(f"[fonts] wrote {css_file}", file=sys.stderr)
PY
}

download_dawn() {
  download_google_fonts \
    "dawn" \
    "https://fonts.googleapis.com/css2?family=Ma+Shan+Zheng&family=Long+Cang&family=Zhi+Mang+Xing&family=Caveat:wght@700&family=Patrick+Hand&display=swap"
}

download_moon() {
  download_google_fonts \
    "moon" \
    "https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&family=Noto+Sans+SC:wght@400;500;700&family=IBM+Plex+Mono:wght@400;600&display=swap"
}

case "$STYLE" in
  dawn)
    download_dawn
    ;;
  moon)
    download_moon
    ;;
  all)
    download_dawn
    download_moon
    ;;
  *)
    bad_args "Unknown style '$STYLE'. Expected: dawn, moon, all"
    ;;
esac

set --
while IFS= read -r file; do
  set -- "$@" "$file"
done < <(find "$TARGET" -type f \( -name '*.woff2' -o -name '*.css' \) | sort)
emit_json_success "$@"
