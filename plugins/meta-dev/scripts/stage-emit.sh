#!/usr/bin/env bash
# stage-emit.sh — Set a plan's waterfall stage in frontmatter + emit event.
# SHIM: delegates to planctl stage (M3a — unified state layer).
#
# Usage: stage-emit.sh <plan> <stage> [status]
#   <stage>   brainstorm|design|plan|harden|execute|review or 1-6
#   [status]  Accepted for compat; conveyed via event only — NEVER written to
#             frontmatter (planctl derives status, never types it).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/anchor-root.sh
source "$SCRIPT_DIR/lib/anchor-root.sh"

PLAN="${1:-}"; STAGE="${2:-}"; STATUS="${3:-in_progress}"

if [ -z "$PLAN" ] || [ -z "$STAGE" ]; then
    echo "Usage: stage-emit.sh <plan> <stage> [in_progress|completed|blocked]" >&2
    exit 1
fi

# Validate stage (name or 1-6) — fail fast on invalid before delegating.
case "$STAGE" in
    brainstorm|design|plan|harden|execute|review|1|2|3|4|5|6) ;;
    *) echo "stage-emit.sh: unknown stage '$STAGE' (expected brainstorm|design|plan|harden|execute|review or 1-6)" >&2; exit 1 ;;
esac

# Delegate to planctl stage — planctl handles the exec-order guard, never writes
# status:/updated:, and emits the event via the new events.jsonl (not state-append.sh).
# Forward $3 as --status for the event payload only (planctl derives status; never types it).
STATUS_VAL="${3:-in_progress}"
exec bash "$SCRIPT_DIR/planctl.sh" stage "$PLAN" "$STAGE" --status "$STATUS_VAL"
