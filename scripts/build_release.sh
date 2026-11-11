#!/bin/bash
# Builds the release zip from a git tag or commit. Created by Ethan Williams 11/9/26
#
#   scripts/build_release.sh v0.9.0-beta     -> dist/PirateCove-v0.9.0-beta.zip
#
# Uses "git archive", so only committed files go in: never .env, venv/, __pycache__,
# uploads, or anything listed in .gitignore. File permissions are kept, so
# install.command and "Launch Pirate Cove.command" stay double-clickable.

set -euo pipefail
cd "$(dirname "$0")/.."

REF="${1:-HEAD}"
NAME="PirateCove-${2:-$REF}"
mkdir -p dist
OUT="dist/${NAME}.zip"

git rev-parse --verify --quiet "${REF}^{tree}" >/dev/null || { echo "Unknown tag or commit: $REF"; exit 1; }
git archive --format=zip --prefix="${NAME}/" -o "$OUT" "$REF"

# Fail if anything that must never ship slipped in
if unzip -Z1 "$OUT" | grep -E '(^|/)(\.env$|\.env\.bak$|venv/|\.venv/|__pycache__/|smart-home-lab/|media-kit|\.DS_Store|node_modules/)' ; then
    echo "ERROR: the files above should not be in the release."
    rm -f "$OUT"
    exit 1
fi

echo "Built $OUT ($(unzip -Z1 "$OUT" | grep -vc '/$') files, $(du -h "$OUT" | cut -f1))"
