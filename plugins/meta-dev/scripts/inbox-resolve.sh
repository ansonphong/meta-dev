#!/usr/bin/env bash
set -euo pipefail
# Anchor cwd to the project root: every plans/... path below is root-relative.
# shellcheck source=lib/anchor-root.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/anchor-root.sh"
PLUGIN_ROOT="$(_md_plugin_root)"

ID="${1:-}"; NOTE="${2:-}"; BY="${3:-}"
[ -z "$ID" ] && { echo "Usage: inbox-resolve.sh <id> [--note N] [--by who]"; exit 1; }

INBOX_FILE="plans/_dashboard/inbox/inbox.jsonl"
[ -f "$INBOX_FILE" ] || { echo "No inbox file found."; exit 1; }

# ── M4 gate: done-gate items are auto-resolved by planctl reconcile when the
# cause clears (review landed / boxes flipped / docs committed). Manual resolve
# of a done-gate item is refused — it should happen through reconcile.
export _RESOLVE_ID="$ID"
IS_DONE_GATE=$(python3 -c "
import json, os
target = os.environ['_RESOLVE_ID']
try:
    with open('$INBOX_FILE') as f:
        items = {}
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                rec = json.loads(line)
            except: continue
            eid = rec.get('id','')
            if not eid: continue
            if rec.get('event') == 'resolve':
                if eid in items:
                    items[eid]['status'] = 'resolved'
            else:
                items[eid] = rec
    item = items.get(target)
    if item and item.get('source') == 'done-gate' and item.get('status') == 'open':
        print('done-gate')
    else:
        print('ok')
except Exception as e:
    print('error: ' + str(e))
" 2>/dev/null)

if [ "$IS_DONE_GATE" = "done-gate" ]; then
  echo "inbox-resolve: done-gate items are auto-resolved by planctl reconcile." >&2
  echo "inbox-resolve: run 'bash plugins/meta-dev/scripts/planctl.sh reconcile' — it auto-resolves stale causes." >&2
  exit 1
fi

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
