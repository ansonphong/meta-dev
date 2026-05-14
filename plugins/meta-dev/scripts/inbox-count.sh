#!/usr/bin/env bash
set -euo pipefail
INBOX_FILE="plans/_dashboard/inbox/inbox.jsonl"
[ -f "$INBOX_FILE" ] || { echo 0; exit 0; }

STATUS_FILTER="${1:-open}"
# Strip --status prefix if passed as --status open
STATUS_FILTER="${STATUS_FILTER#--status }"
export _STATUS_FILTER="$STATUS_FILTER"
export _INBOX_FILE_CNT="$INBOX_FILE"

python3 -c "
import json, os, sys

status_filter = os.environ['_STATUS_FILTER']
with open(os.environ['_INBOX_FILE_CNT']) as f:
    events = [json.loads(line.strip()) for line in f if line.strip()]

# Reduce: last event per id wins
state = {}
for e in events:
    eid = e.get('id', '')
    if e.get('event') == 'resolve':
        state[eid] = e.get('status', 'resolved')
    elif 'status' in e:
        state[eid] = e['status']

count = sum(1 for s in state.values() if s == status_filter or status_filter == 'all')
print(count)
"
