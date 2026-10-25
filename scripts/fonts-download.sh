#!/usr/bin/env bash
# Download deterministic local WOFF2 fonts for topic-to-video themes.
#
# Usage: bash fonts-download.sh [target_dir] [--theme <theme_dir|theme_name> | style] [--dry-run]
#   target_dir defaults to ./fonts
#   --theme reads a theme's fonts.json manifest (e.g. modules/designs/dawn or dawn)
#   style (legacy) values: any theme name under modules/designs, or all
#
# Theme manifests live in modules/designs/<theme>/fonts.json and are the only
# source of truth for the theme roster: adding a theme = dropping a new
# manifest dir. A manifest lists the Google Fonts css2 families, the local
# CSS filename and the rename flag. The legacy named styles are aliases for
# the matching theme dirs.
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

if [[ ! -d "$MODULES_DESIGNS" ]]; then
  runtime_error "theme dir $MODULES_DESIGNS does not exist"
fi

# All theme manifests (the roster source of truth).
theme_manifests() {
  local manifest
  for manifest in "$MODULES_DESIGNS"/*/fonts.json; do
    [[ -f "$manifest" ]] && echo "$manifest"
  done
}

THEME=""
STYLE=""
DRY_RUN=""
POSITIONALS=()

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
    *)
      POSITIONALS+=("$1")
      shift
      ;;
  esac
done

if [[ ${#POSITIONALS[@]} -gt 2 ]]; then
  bad_args "Usage: bash fonts-download.sh [target_dir] [--theme <theme_dir|theme_name> | style] [--dry-run]"
fi
TARGET="${POSITIONALS[0]:-fonts}"
if [[ ${#POSITIONALS[@]} -eq 2 ]]; then
  STYLE="${POSITIONALS[1]}"
fi

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
  elif [[ -f "$MODULES_DESIGNS/$spec/fonts.json" ]]; then
    dir="$MODULES_DESIGNS/$spec"
  else
    runtime_error "unknown theme '$spec' (no fonts.json under $MODULES_DESIGNS)"
  fi
  echo "$dir/fonts.json"
}

# Download one theme manifest: validate it, build the css2 URL, fetch the
# WOFF2 subsets and write the local CSS in a single pass.
download_manifest() {
  local manifest="$1"
  python3 - "$manifest" "$TARGET" "$DRY_RUN" <<'PY'
import hashlib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

manifest_path = Path(sys.argv[1])
target_dir = Path(sys.argv[2])
dry_run = sys.argv[3] == "--dry-run"

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
try:
    families = manifest["css2_families"]
    css_filename = manifest["css_filename"]
    rename_families = bool(manifest.get("rename"))
except KeyError as exc:
    raise SystemExit(f"manifest {manifest_path} missing field: {exc}")
if not isinstance(families, list) or not families:
    raise SystemExit(f"manifest {manifest_path}: css2_families must be a non-empty list")

style_name = manifest_path.parent.name
css_url = "https://fonts.googleapis.com/css2?family=" + "&family=".join(families) + "&display=swap"
css_file = target_dir / css_filename


def log(message: str) -> None:
    print(f"[fonts] {message}", file=sys.stderr)


if dry_run:
    log(f"dry-run {style_name} css: {css_url}")
    log(f"dry-run {style_name} css output: {css_file}")
    raise SystemExit(0)

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
            log(f"retry {attempt}/{attempts - 1} after {exc}")
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
        log(f"{filename} (cached)")
    else:
        log(f"downloading {filename}")
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
log(f"wrote {css_file}")
PY
}

if [[ -n "$THEME" ]]; then
  download_manifest "$(resolve_manifest "$THEME")"
else
  case "$STYLE" in
    all)
      while IFS= read -r manifest; do
        download_manifest "$manifest"
      done < <(theme_manifests)
      ;;
    *)
      manifest="$MODULES_DESIGNS/$STYLE/fonts.json"
      if [[ ! -f "$manifest" ]]; then
        known="$(theme_manifests | while IFS= read -r m; do basename "$(dirname "$m")"; done | tr '\n' ' ')"
        bad_args "Unknown style '$STYLE'. Expected one of: $known all"
      fi
      download_manifest "$manifest"
      ;;
  esac
fi

set --
while IFS= read -r file; do
  set -- "$@" "$file"
done < <(find "$TARGET" -type f \( -name '*.woff2' -o -name '*.css' \) | sort)
emit_json_success "$@"
