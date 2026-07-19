#!/usr/bin/env bash
# stage-emit.sh — Set a plan's waterfall stage in frontmatter + emit event.
# SHIM: delegates to planctl stage (M3a — unified state layer).
#
# Usage: stage-emit.sh <plan> <stage> [status]
#   <stage>   brainstorm|design|plan|harden|execute|review or 1-6
#   [status]  Forwarded to the event log and written to stage_state in the plan's
#             frontmatter, making this a git-visible write.
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
# Forward $3 as --status; planctl also writes completed -> stage_state: done and
# every other accepted status -> stage_state: active in the plan frontmatter.
STATUS_VAL="${3:-in_progress}"
exec bash "$SCRIPT_DIR/planctl.sh" stage "$PLAN" "$STAGE" --status "$STATUS_VAL"
