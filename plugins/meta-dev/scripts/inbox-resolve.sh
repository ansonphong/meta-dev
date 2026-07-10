#!/usr/bin/env bash
set -euo pipefail
# Anchor cwd to the project root: every plans/... path below is root-relative.
# shellcheck source=lib/anchor-root.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/anchor-root.sh"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-.}"

ID="${1:-}"; NOTE="${2:-}"; BY="${3:-}"
[ -z "$ID" ] && { echo "Usage: inbox-resolve.sh <id> [--note N] [--by who]"; exit 1; }

INBOX_FILE="plans/_dashboard/inbox/inbox.jsonl"
[ -f "$INBOX_FILE" ] || { echo "No inbox file found."; exit 1; }

NOW=$(date -u +%FT%TZ)
export _ID="$ID" _NOW="$NOW" _BY="${BY:-system}" _NOTE="${NOTE:-}" _INBOX_FILE_RES="$INBOX_FILE"

RESOLVE_EVENT=$(python3 -c "
import json, os
event = {
    'id': os.environ['_ID'], 'event': 'resolve', 'status': 'resolved',
    'resolved': os.environ['_NOW'],
    'resolved_by': os.environ['_BY'],
    'resolution_note': os.environ.get('_NOTE') or None,
    'updated': os.environ['_NOW']
}
print(json.dumps(event))
")
echo "$RESOLVE_EVENT" >> "$INBOX_FILE"

python3 "$PLUGIN_ROOT/scripts/inbox-render.py" 2>/dev/null || true
echo "Resolved: $ID"
