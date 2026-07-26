#!/usr/bin/env bash
set -euo pipefail
# Anchor cwd to the project root: every plans/... path below is root-relative.
# shellcheck source=lib/anchor-root.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/anchor-root.sh"
PLUGIN_ROOT="$(_md_plugin_root)"
# Append a single JSON event line to state.events.jsonl.
# Usage: state-append.sh '{"event":"commit","sha":"abc123",...}'

EVENT_JSON="${1:-}"
[ -z "$EVENT_JSON" ] && { echo "Usage: state-append.sh <json-event>" >&2; exit 1; }

# Validate it's parseable JSON
printf '%s\n' "$EVENT_JSON" | python3 -c "import json,sys; json.loads(sys.stdin.read())" || {
  echo "state-append.sh: invalid JSON" >&2; exit 2
}

# ── M4 gate: done_gate + review_verdict are now planctl's domain (R5) ──────
# The legacy log is frozen for these two types. planctl's events.jsonl is the
# new source of truth for done-gate decisions + review verdicts.
# plan_edit / commit / overlord / session / sweep / meta_execute_* events
# STAY on the legacy log (state-reduce.py still folds them).
_EVENT_TYPE=$(printf '%s\n' "$EVENT_JSON" | python3 -c "
import json,sys
rec = json.loads(sys.stdin.read())
print(rec.get('event',''))
")
for _ft in done_gate review_verdict; do
  if [ "$_EVENT_TYPE" = "$_ft" ]; then
    echo "state-append.sh: event type '${_ft}' is FROZEN (M4 — unified state layer)." >&2
    echo "state-append.sh: done-gate decisions + review verdicts are now sourced from planctl's events.jsonl." >&2
    echo "state-append.sh: use 'planctl review' to record a review verdict; done-gate is emitted by 'planctl reconcile'." >&2
    exit 3
  fi
done

# Hermetic override for tests: META_DEV_STATE_DIR points events at a fixture dir
# so suite runs never touch the live plans/_dashboard/state.events.jsonl.
# CLAUDE_PROJECT_DIR alone is NOT enough — anchor-root re-cds to the real root.
STATE_DIR="${META_DEV_STATE_DIR:-plans/_dashboard}"
mkdir -p "$STATE_DIR"

EVENTS_FILE="$STATE_DIR/state.events.jsonl"
echo "$EVENT_JSON" >> "$EVENTS_FILE"
