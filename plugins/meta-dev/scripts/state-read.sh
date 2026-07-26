#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=lib/anchor-root.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/anchor-root.sh"
PLUGIN_ROOT="$(_md_plugin_root)"
PATH_ARG="${1:-}"

# Ensure reduced state is current, then output
export META_DEV_PLUGIN_ROOT="$PLUGIN_ROOT"
OUTPUT=$(python3 "$PLUGIN_ROOT/scripts/state-reduce.py")

if [ -z "$PATH_ARG" ]; then
  echo "$OUTPUT"
else
  export _PATH_ARG="$PATH_ARG"
  echo "$OUTPUT" | python3 -c "
import json, os, sys
data = json.load(sys.stdin)
parts = os.environ['_PATH_ARG'].split('.')
val = data
for p in parts:
    val = val.get(p, val[p] if p in val else None)
    if val is None:
        break
if val is None:
    print('null')
elif isinstance(val, (dict, list)):
    print(json.dumps(val, indent=2))
else:
    print(val)
"
fi
