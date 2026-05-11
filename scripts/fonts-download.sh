#!/usr/bin/env bash
# Download deterministic local WOFF2 fonts for topic-to-video styles.
#
# Usage: bash fonts-download.sh [target_dir] [style] [--dry-run]
#   target_dir defaults to ./fonts
#   style defaults to dawn
#   style values: dawn, moon, all
#
# Dawn requires: curl, python3 with fonttools+brotli installed
#   pip3 install --break-system-packages fonttools brotli
#
# Moon downloads Google Fonts WOFF2 subsets and writes rose-pine-moon-fonts.css.
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

download_dawn() {
  pushd "$TARGET" >/dev/null

  declare -A FONTS=(
    ["ma-shan-zheng"]="https://fonts.gstatic.com/s/mashanzheng/v17/NaPecZTRCLxvwo41b4gvzkXaRMQ.ttf"
    ["long-cang"]="https://fonts.gstatic.com/s/longcang/v21/LYjAdGP8kkgoTec8zkRgrQ.ttf"
    ["zhi-mang-xing"]="https://fonts.gstatic.com/s/zhimangxing/v19/f0Xw0ey79sErYFtWQ9a2rq-g0ac.ttf"
    ["caveat-700"]="https://fonts.gstatic.com/s/caveat/v23/WnznHAc5bAfYB2QRah7pcpNvOx-pjRV6SII.ttf"
    ["patrick-hand"]="https://fonts.gstatic.com/s/patrickhand/v25/LDI1apSQOAYtSuYWp8ZhfYeMWQ.ttf"
  )

  if [[ "$DRY_RUN" == "--dry-run" ]]; then
    log "dry-run dawn fonts: ${!FONTS[*]}"
    popd >/dev/null
    return
  fi

  for name in "${!FONTS[@]}"; do
    url="${FONTS[$name]}"
    if [[ -f "${name}.woff2" ]]; then
      log "${name}.woff2 (cached)"
      continue
    fi
    log "downloading ${name}.ttf"
    curl -sSL -o "${name}.ttf" "$url"
  done

  python3 - <<'PY'
import glob
import os
import sys

from fontTools.ttLib import TTFont

for ttf in glob.glob('*.ttf'):
    woff2 = ttf.replace('.ttf', '.woff2')
    if os.path.exists(woff2):
        continue
    font = TTFont(ttf)
    font.flavor = 'woff2'
    font.save(woff2)
    print(f'[fonts] converted {ttf} -> {woff2}', file=sys.stderr)
PY

  rm -f ./*.ttf
  popd >/dev/null
}

download_moon() {
  local css_url='https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&family=Noto+Sans+SC:wght@400;500;700&family=IBM+Plex+Mono:wght@400;600&display=swap'
  local css_file="$TARGET/rose-pine-moon-fonts.css"

  if [[ "$DRY_RUN" == "--dry-run" ]]; then
    log "dry-run moon css: $css_url"
    log "dry-run moon css output: $css_file"
    return
  fi

  python3 - "$css_url" "$css_file" <<'PY'
import hashlib
import re
import sys
import urllib.request
from pathlib import Path

css_url = sys.argv[1]
css_file = Path(sys.argv[2])
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
    filename = f"moon-{index:02d}-{digest}.woff2"
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
css_file.write_text(css, encoding="utf-8")
print(f"[fonts] wrote {css_file}", file=sys.stderr)
PY
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

mapfile -t files < <(find "$TARGET" -type f \( -name '*.woff2' -o -name '*.css' \) | sort)
emit_json_success "${files[@]}"
