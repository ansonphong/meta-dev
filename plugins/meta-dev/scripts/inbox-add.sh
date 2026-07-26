#!/usr/bin/env bash
set -euo pipefail
# Anchor cwd to the project root: every plans/... path below is root-relative.
# shellcheck source=lib/anchor-root.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/anchor-root.sh"
PLUGIN_ROOT="$(_md_plugin_root)"

# Parse args
SOURCE=""; SEVERITY="low"; TITLE=""; BODY=""; REF_FILE=""; REF_LINE=""; REF_COMMIT=""
ACTION=""; AUTO_CLEARABLE="false"; KIND="issue"; OPTIONS_JSON="[]"; TAGS_STR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --source) SOURCE="$2"; shift 2 ;;
    --severity) SEVERITY="$2"; shift 2 ;;
    --title) TITLE="$2"; shift 2 ;;
    --body) BODY="$2"; shift 2 ;;
    --ref-file) REF_FILE="$2"; shift 2 ;;
    --ref-line) REF_LINE="$2"; shift 2 ;;
    --ref-commit) REF_COMMIT="$2"; shift 2 ;;
    --action) ACTION="$2"; shift 2 ;;
    --auto-clearable) AUTO_CLEARABLE="true"; shift ;;
    --kind) KIND="$2"; shift 2 ;;
    --options) OPTIONS_JSON="$2"; shift 2 ;;
    --tag) TAGS_STR="${TAGS_STR} $2"; shift 2 ;;
    *) shift ;;
  esac
done

[ -z "$SOURCE" ] && { echo "Usage: inbox-add.sh --source <source> --title <title> [flags]"; exit 1; }
[ -z "$TITLE" ] && { echo "Missing --title"; exit 1; }

# ── M4 gate: done-gate items are stateful per-(plan,cause), managed by
# planctl reconcile via inbox.upsert(). Blind append-per-stop is the old
# world — refuse it here. Non-done-gate items (manual advisories, overlord)
# keep working unchanged.
if [ "$SOURCE" = "done-gate" ]; then
  echo "inbox-add: done-gate items are now managed by planctl reconcile (stateful per-(plan,cause))." >&2
  echo "inbox-add: run 'bash plugins/meta-dev/scripts/planctl.sh reconcile' to update inbox state." >&2
  exit 1
fi

INBOX_DIR="plans/_dashboard/inbox"
mkdir -p "$INBOX_DIR"
INBOX_FILE="$INBOX_DIR/inbox.jsonl"

# Generate ULID
ULID=$(python3 -c "
try:
    from ulid import new
    print(new())
except ImportError:
    import hashlib, time
    print(hashlib.sha256(str(time.time_ns()).encode()).hexdigest()[:26])
" 2>/dev/null)
ID="inb_${ULID}"

# Build dedup key
DEDUP_KEY="${SOURCE}:${REF_FILE:-}:${REF_LINE:-}:${REF_COMMIT:-}"
if [ "$DEDUP_KEY" = "${SOURCE}:::" ]; then
  export _TITLE_HASH="$TITLE"
  TITLE_HASH=$(python3 -c "
import hashlib, os
print(hashlib.sha256(os.environ['_TITLE_HASH'].encode()).hexdigest()[:16])
")
  DEDUP_KEY="${SOURCE}:${TITLE_HASH}"
fi

# Check dedup window (default 72h)
DEDUP_HOURS=72
CONFIG_DEDUP=$(bash "$PLUGIN_ROOT/scripts/config-get.sh" meta_dev.inbox.dedup_window_hours 2>/dev/null || echo "72")
[ -n "$CONFIG_DEDUP" ] && DEDUP_HOURS="$CONFIG_DEDUP"

if [ -f "$INBOX_FILE" ]; then
  export _INBOX_FILE_DEDUP="$INBOX_FILE" _DEDUP_HOURS="$DEDUP_HOURS" _SOURCE_DEDUP="$SOURCE" _DEDUP_KEY="$DEDUP_KEY"
  EXISTING=$(python3 -c "
import json, os, datetime
cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=int(os.environ['_DEDUP_HOURS']))
with open(os.environ['_INBOX_FILE_DEDUP']) as f:
    for line in f:
        try:
            item = json.loads(line.strip())
            if item.get('status') == 'open' and item.get('source') == os.environ['_SOURCE_DEDUP']:
                ref = item.get('ref', {})
                key = f\"{item['source']}:{ref.get('file','')}:{ref.get('line','')}:{ref.get('commit','')}\"
                if key == os.environ['_DEDUP_KEY']:
                    print(item['id'])
                    break
        except: pass
" 2>/dev/null)
  if [ -n "$EXISTING" ]; then
    echo "inbox-add: dedup — item $EXISTING already open (same source+ref within ${DEDUP_HOURS}h)"
    # Bump seen_count via resolve+re-add pattern handled by render.py's latest-event logic
    exit 0
  fi
fi

# Overflow check
MAX_OPEN=50
CONFIG_MAX=$(bash "$PLUGIN_ROOT/scripts/config-get.sh" meta_dev.inbox.max_open_items 2>/dev/null || echo "50")
[ -n "$CONFIG_MAX" ] && MAX_OPEN="$CONFIG_MAX"

OPEN_COUNT=$(bash "$PLUGIN_ROOT/scripts/inbox-count.sh" --status open 2>/dev/null || echo 0)
if [ "$OPEN_COUNT" -ge "$MAX_OPEN" ]; then
  OVERFLOW_ACTION="archive_oldest_resolved"
  CONFIG_OVERFLOW=$(bash "$PLUGIN_ROOT/scripts/config-get.sh" meta_dev.inbox.max_overflow_action 2>/dev/null || echo "archive_oldest_resolved")
  [ -n "$CONFIG_OVERFLOW" ] && OVERFLOW_ACTION="$CONFIG_OVERFLOW"
  case "$OVERFLOW_ACTION" in
    archive_oldest_resolved)
      bash "$PLUGIN_ROOT/scripts/inbox-archive.sh" 2>/dev/null || true
      ;;
    block)
      echo "inbox-add: overflow — $OPEN_COUNT open items (max $MAX_OPEN), action=block"; exit 2
      ;;
    force) ;; # proceed
  esac
fi

NOW=$(date -u +%FT%TZ)
export _ID="$ID" _KIND="$KIND" _SOURCE="$SOURCE" _SEVERITY="$SEVERITY"
export _TITLE="$TITLE" _BODY="$BODY"
export _REF_FILE="${REF_FILE:-}" _REF_LINE="${REF_LINE:-}" _REF_COMMIT="${REF_COMMIT:-}"
export _ACTION="$ACTION" _AUTO_CLEARABLE="$AUTO_CLEARABLE"
export _TAGS_STR="$TAGS_STR" _OPTIONS_JSON="$OPTIONS_JSON" _NOW="$NOW"

ITEM=$(python3 -c "
import json, os

item = {
    'id': os.environ['_ID'],
    'kind': os.environ['_KIND'],
    'source': os.environ['_SOURCE'],
    'severity': os.environ['_SEVERITY'],
    'title': os.environ['_TITLE'],
    'body': os.environ['_BODY'],
    'awaits': None,
    'options': json.loads(os.environ['_OPTIONS_JSON']),
    'ref': {
        'file': os.environ.get('_REF_FILE') or None,
        'line': int(os.environ['_REF_LINE']) if os.environ.get('_REF_LINE') else None,
        'commit': os.environ.get('_REF_COMMIT') or None,
        'plan': None,
    },
    'recommended_action': os.environ.get('_ACTION') or None,
    'advice': '',
    'auto_clearable': os.environ.get('_AUTO_CLEARABLE') == 'true',
    'status': 'open',
    'created': os.environ['_NOW'],
    'updated': os.environ['_NOW'],
    'resolved': None,
    'resolved_by': None,
    'resolution_note': None,
    'related_commits': [],
    'tags': [t for t in os.environ.get('_TAGS_STR', '').split() if t],
    'seen_count': 1,
}
print(json.dumps(item))
")
echo "$ITEM" >> "$INBOX_FILE"

# Render
python3 "$PLUGIN_ROOT/scripts/inbox-render.py" 2>/dev/null || true

echo "inbox-add: $ID ($SOURCE/$SEVERITY) — $TITLE"
