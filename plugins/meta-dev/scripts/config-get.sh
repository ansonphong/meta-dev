#!/usr/bin/env bash
set -euo pipefail
# Anchor cwd to the project root: every plans/... path below is root-relative.
# shellcheck source=lib/anchor-root.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/anchor-root.sh"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-.}"

PATH_ARG="${1:-}"
if [ -z "$PATH_ARG" ]; then
  exec python3 "$PLUGIN_ROOT/scripts/config-merge.py"
fi

# Dot-notation lookup: "meta_dev.overlord.model" -> walk JSON
python3 -c '
import json, subprocess, sys
plugin_root = sys.argv[1]
result = subprocess.run(
    ["python3", plugin_root + "/scripts/config-merge.py"],
    capture_output=True, text=True
)
merged = json.loads(result.stdout)
parts = sys.argv[2].split(".")
val = merged
for p in parts:
    val = val[p]
if isinstance(val, (dict, list)):
    print(json.dumps(val, indent=2))
else:
    print(val)
' "$PLUGIN_ROOT" "$PATH_ARG"
