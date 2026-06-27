#!/usr/bin/env bash
set -euo pipefail
# stage-emit.sh — Emit a waterfall stage_transition event to the dashboard
# state log, so the dashboard always knows which of the 6 stages a plan is at.
#
# Usage: stage-emit.sh <plan> <stage> [status]
#   <plan>    Plan identity — the plan path or dir you were invoked on
#             (e.g. plans/app/FOO/00-master-plan.md or plans/app/FOO/).
#   <stage>   brainstorm | design | plan | harden | execute | review
#   [status]  in_progress (default) | completed | blocked
#
# Reuses state-append.sh (validates + appends). The reducer (state-reduce.py)
# folds stage_transition into the per-plan `plan_stages` map.
#
# Examples:
#   stage-emit.sh plans/app/FOO/00-master-plan.md harden in_progress
#   stage-emit.sh plans/app/FOO/00-master-plan.md harden completed

PLAN="${1:-}"
STAGE="${2:-}"
STATUS="${3:-in_progress}"

if [ -z "$PLAN" ] || [ -z "$STAGE" ]; then
    echo "Usage: stage-emit.sh <plan> <stage> [in_progress|completed|blocked]" >&2
    exit 1
fi

case "$STAGE" in
    brainstorm) N=1 ;;
    design)     N=2 ;;
    plan)       N=3 ;;
    harden)     N=4 ;;
    execute)    N=5 ;;
    review)     N=6 ;;
    *)          echo "stage-emit.sh: unknown stage '$STAGE' (expected brainstorm|design|plan|harden|execute|review)" >&2; exit 1 ;;
esac

TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Build the event with python so plan paths/status are always JSON-safe.
EVENT="$(python3 -c 'import json,sys; print(json.dumps({"event":"stage_transition","plan":sys.argv[1],"stage":sys.argv[2],"stage_num":int(sys.argv[3]),"status":sys.argv[4],"time":sys.argv[5]}))' "$PLAN" "$STAGE" "$N" "$STATUS" "$TIME")"

"$SCRIPT_DIR/state-append.sh" "$EVENT"
echo "[stage-emit] $PLAN → stage $N ($STAGE) $STATUS"
