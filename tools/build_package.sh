#!/usr/bin/env bash
# Build the distributable skill package and its checksum.
#
#   ./tools/build_package.sh [OUTPUT_DIR]     (default: dist/)
#
# Produces OUTPUT_DIR/wincreator.skill (a zip whose top-level directory is
# `wincreator/`, as Agent Skills runtimes expect) and a sha256 sidecar, so a
# release asset can be verified instead of trusted.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out_dir="${1:-$repo_root/dist}"
package="$out_dir/wincreator.skill"

python3 "$repo_root/skill/wincreator/scripts/package_check.py" \
        "$repo_root/skill/wincreator"

mkdir -p "$out_dir"
rm -f "$package" "$package.sha256"

# -X drops extra attributes so the same tree yields the same archive contents.
( cd "$repo_root/skill" && zip -q -r -X "$package" wincreator \
    -x '*/__pycache__/*' '*.pyc' )

( cd "$out_dir" && sha256sum "$(basename "$package")" > "$(basename "$package").sha256" )

echo "package: $package"
cat "$package.sha256"
