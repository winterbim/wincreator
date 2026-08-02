#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir="${1:-$repo_root/dist}"

python3 "$repo_root/skill/wincreator/scripts/package_check.py" "$repo_root/skill/wincreator"
python3 "$repo_root/tools/build_package.py" --source "$repo_root/skill/wincreator" "$output_dir"
