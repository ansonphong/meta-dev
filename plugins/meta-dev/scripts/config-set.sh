#!/usr/bin/env bash
set -euo pipefail
# Anchor cwd to the project root: every plans/... path below is root-relative.
# shellcheck source=lib/anchor-root.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/anchor-root.sh"
PLUGIN_ROOT="$(_md_plugin_root)"
export META_DEV_PLUGIN_ROOT="$PLUGIN_ROOT"

PATH_ARG="${1:-}"; VALUE="${2:-}"; LAYER="${3:-project}"

if [ -z "$PATH_ARG" ] || [ -z "$VALUE" ]; then
  echo "Usage: config-set.sh <dot.path> <value> [project|local]"
  exit 1
fi

TARGET="plans/_dashboard/settings.json"
[ "$LAYER" = "local" ] && TARGET="plans/_dashboard/settings.local.json"

# Ensure file exists (bootstrap from template if needed)
if [ ! -f "$TARGET" ]; then
  mkdir -p "$(dirname "$TARGET")"
  if [ "$LAYER" = "local" ]; then
    echo '{}' > "$TARGET"
  else
    cp "$PLUGIN_ROOT/templates/settings.json" "$TARGET"
  fi
fi

# Set value via Python (handles nested dot-notation)
python3 -c '
import json, sys, os

target = sys.argv[1]
path_parts = sys.argv[2].split(".")
path_str = sys.argv[2]
value_raw = sys.argv[3]
layer = sys.argv[4]

# Try to parse as JSON; fall back to raw string
try:
    value = json.loads(value_raw)
except json.JSONDecodeError:
    value = value_raw

with open(target, encoding="utf-8") as f:
    data = json.load(f)

# Walk/create nested path
current = data
for i, key in enumerate(path_parts[:-1]):
    if key not in current:
        current[key] = {}
    current = current[key]
current[path_parts[-1]] = value

# Validate (project layer only; local is partial overlay)
if layer != "local":
    try:
        import jsonschema
    except ImportError:
        print("Warning: jsonschema not available, skipping validation", file=sys.stderr)
    else:
        schema_path = os.environ["META_DEV_PLUGIN_ROOT"] + "/schemas/settings.schema.json"
        with open(schema_path, encoding="utf-8") as sf:
            schema = json.load(sf)
        jsonschema.validate(data, schema)

with open(target, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
print(f"Set {path_str} = {value} in {target}")
' "$TARGET" "$PATH_ARG" "$VALUE" "$LAYER"
