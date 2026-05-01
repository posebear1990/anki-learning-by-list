#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
DIST_DIR="$ROOT_DIR/dist"
STAGE_DIR="$(mktemp -d)"
OUTPUT_NAME="$(python3 - <<'PY' "$ROOT_DIR"
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
meta = json.loads((root / "addon.json").read_text(encoding="utf-8"))
print(f"{meta['repo_name']}.ankiaddon")
PY
)"

cleanup() {
  rm -rf "$STAGE_DIR"
}
trap cleanup EXIT

python3 -m py_compile "$ROOT_DIR"/*.py

python3 - <<'PY' "$ROOT_DIR" "$STAGE_DIR"
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1])
stage = Path(sys.argv[2])

release_paths = [
    "__init__.py",
    "addon.py",
    "config.json",
    "config.md",
    "config_store.py",
    "data.py",
    "manifest.json",
    "window.py",
    "user_files",
]

for rel_path in release_paths:
    source = root / rel_path
    target = stage / rel_path
    if not source.exists():
        continue
    if source.is_dir():
        shutil.copytree(source, target)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
PY

rm -f "$DIST_DIR/$OUTPUT_NAME"
(
  cd "$STAGE_DIR"
  zip -qr "$DIST_DIR/$OUTPUT_NAME" .
)

python3 - <<'PY' "$DIST_DIR/$OUTPUT_NAME"
import sys
import zipfile

archive = sys.argv[1]
blocked_fragments = [
    "__pycache__/",
    ".git/",
    "meta.json",
    "backups/",
    "dist/",
]

with zipfile.ZipFile(archive) as zf:
    names = zf.namelist()
    for fragment in blocked_fragments:
        if any(fragment in name for name in names):
            raise SystemExit(f"Blocked path found in release archive: {fragment}")
    if "__init__.py" not in names:
        raise SystemExit("Release archive is missing __init__.py")
    if "manifest.json" not in names:
        raise SystemExit("Release archive is missing manifest.json")
PY

printf 'Built %s\n' "$DIST_DIR/$OUTPUT_NAME"
printf 'Validated %s\n' "$DIST_DIR/$OUTPUT_NAME"
