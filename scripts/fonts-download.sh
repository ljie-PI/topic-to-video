#!/usr/bin/env bash
# Download deterministic local WOFF2 fonts for topic-to-video themes.
#
# Usage: bash fonts-download.sh [target_dir] [--theme <theme_dir|theme_name> | style] [--dry-run]
#   target_dir defaults to ./fonts
#   --theme reads a theme's fonts.json manifest (e.g. modules/designs/dawn or dawn)
#   style (legacy) values: default, dawn, moon, github, producthunt, all
#
# Theme manifests live in modules/designs/<theme>/fonts.json; a manifest lists
# the Google Fonts css2 families, the local CSS filename and the rename flag.
# The legacy named styles are aliases for the matching theme manifests.
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULES_DESIGNS="$SCRIPT_DIR/../modules/designs"
LEGACY_STYLES="default dawn moon github producthunt"

TARGET=""
THEME=""
STYLE=""
DRY_RUN=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN="--dry-run"
      shift
      ;;
    --theme)
      [[ $# -ge 2 ]] || bad_args "--theme requires a theme dir or theme name"
      THEME="$2"
      shift 2
      ;;
    default|dawn|moon|github|producthunt|all)
      STYLE="$1"
      shift
      ;;
    *)
      if [[ -z "$TARGET" ]]; then
        TARGET="$1"
      else
        bad_args "Usage: bash fonts-download.sh [target_dir] [--theme <theme_dir|theme_name> | style] [--dry-run]"
      fi
      shift
      ;;
  esac
done

TARGET="${TARGET:-fonts}"

if [[ -n "$THEME" && -n "$STYLE" ]]; then
  bad_args "pass either --theme or a named style, not both"
fi
if [[ -z "$THEME" && -z "$STYLE" ]]; then
  STYLE="default"
fi

mkdir -p "$TARGET"

# Resolve a theme dir / theme name / fonts.json path to a manifest file.
resolve_manifest() {
  local spec="$1"
  local dir=""
  if [[ -f "$spec" ]]; then
    echo "$spec"
    return
  fi
  if [[ -d "$spec" ]]; then
    dir="$spec"
  elif [[ -d "$MODULES_DESIGNS/$spec" ]]; then
    dir="$MODULES_DESIGNS/$spec"
  else
    runtime_error "unknown theme '$spec' (no fonts.json; not a dir under $MODULES_DESIGNS)"
  fi
  if [[ ! -f "$dir/fonts.json" ]]; then
    runtime_error "theme dir '$dir' has no fonts.json"
  fi
  echo "$dir/fonts.json"
}

# Read a manifest and download its families. Manifest fields:
#   css_filename   local CSS file written into the target dir
#   rename         true -> short family aliases (NotoSansSC, ...); false -> keep
#   css2_families  list of Google Fonts css2 family specs
download_manifest() {
  local manifest="$1"
  python3 - "$manifest" "$TARGET" "$DRY_RUN" <<'PY'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
css_url = "https://fonts.googleapis.com/css2?family=" + "&family=".join(
    manifest["css2_families"]
) + "&display=swap"
print(manifest["css_filename"])
print(css_url)
print("rename" if manifest.get("rename") else "keep")
PY
}

download_theme() {
  local manifest="$1"
  local style_name
  style_name="$(basename "$(dirname "$manifest")")"
  local fields
  fields="$(download_manifest "$manifest")"
  local css_file css_url rename_families
  css_file="$(sed -n '1p' <<<"$fields")"
  css_url="$(sed -n '2p' <<<"$fields")"
  rename_families="$(sed -n '3p' <<<"$fields")"
  download_google_fonts "$style_name" "$css_url" "$rename_families" "$css_file"
}

download_google_fonts() {
  local style_name="$1"
  local css_url="$2"
  local rename_families="${3:-rename}"
  local css_file="$TARGET/${4:-rose-pine-${style_name}-fonts.css}"

  if [[ "$DRY_RUN" == "--dry-run" ]]; then
    log "dry-run ${style_name} css: $css_url"
    log "dry-run ${style_name} css output: $css_file"
    return
  fi

  python3 - "$style_name" "$css_url" "$css_file" "$rename_families" <<'PY'
import hashlib
import re
import sys
import time
import urllib.request
from pathlib import Path

style_name = sys.argv[1]
css_url = sys.argv[2]
css_file = Path(sys.argv[3])
rename_families = sys.argv[4] == "rename"
target_dir = css_file.parent
# A modern browser UA makes Google Fonts serve real WOFF2 (unicode-range
# subsets, variable axes kept); a bare UA gets static TrueType per instance.
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def fetch(url: str, attempts: int = 3) -> bytes:
    request = urllib.request.Request(url, headers=headers)
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except OSError as exc:
            if attempt == attempts:
                raise
            print(f"[fonts] retry {attempt}/{attempts - 1} after {exc}", file=sys.stderr)
            time.sleep(2 * attempt)


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

if rename_families:
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

if [[ -n "$THEME" ]]; then
  manifest="$(resolve_manifest "$THEME")"
  download_theme "$manifest"
else
  case "$STYLE" in
    all)
      for name in $LEGACY_STYLES; do
        download_theme "$MODULES_DESIGNS/$name/fonts.json"
      done
      ;;
    *)
      download_theme "$MODULES_DESIGNS/$STYLE/fonts.json"
      ;;
  esac
fi

set --
while IFS= read -r file; do
  set -- "$@" "$file"
done < <(find "$TARGET" -type f \( -name '*.woff2' -o -name '*.css' \) | sort)
emit_json_success "$@"
