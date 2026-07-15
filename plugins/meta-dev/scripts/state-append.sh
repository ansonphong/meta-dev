#!/usr/bin/env bash
set -euo pipefail
# Anchor cwd to the project root: every plans/... path below is root-relative.
# shellcheck source=lib/anchor-root.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/anchor-root.sh"
# Append a single JSON event line to state.events.jsonl.
# Usage: state-append.sh '{"event":"commit","sha":"abc123",...}'

EVENT_JSON="${1:-}"
[ -z "$EVENT_JSON" ] && { echo "Usage: state-append.sh <json-event>" >&2; exit 1; }

# Validate it's parseable JSON
printf '%s\n' "$EVENT_JSON" | python3 -c "import json,sys; json.loads(sys.stdin.read())" || {
  echo "state-append.sh: invalid JSON" >&2; exit 2
}

# Hermetic override for tests: META_DEV_STATE_DIR points events at a fixture dir
# so suite runs never touch the live plans/_dashboard/state.events.jsonl.
# CLAUDE_PROJECT_DIR alone is NOT enough — anchor-root re-cds to the real root.
STATE_DIR="${META_DEV_STATE_DIR:-plans/_dashboard}"
mkdir -p "$STATE_DIR"

EVENTS_FILE="$STATE_DIR/state.events.jsonl"
echo "$EVENT_JSON" >> "$EVENTS_FILE"
