#!/usr/bin/env bash
# task-undone.sh — Reopen stamped plan checkboxes [x] → [ ].
# SHIM: delegates to planctl uncheck (M3a — unified state layer).
#
# Usage: task-undone.sh [--by <who>] <plan> <handle> [<handle>…]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/anchor-root.sh
source "$SCRIPT_DIR/lib/anchor-root.sh"

BY="${USER:-conductor}"; ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --by) [ $# -ge 2 ] || { echo "task-undone.sh: --by requires a value" >&2; exit 2; }; BY="${2}"; shift 2 ;;
    -*) echo "task-undone.sh: unknown flag: $1" >&2; exit 2 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done

[ "${#ARGS[@]}" -ge 2 ] || { echo "Usage: task-undone.sh [--by <who>] <plan> <handle> [<handle>…]" >&2; exit 2; }

PLAN_ARG="${ARGS[0]}"
HANDLES=("${ARGS[@]:1}")

# ── Resolve plan (DIFFERS from task-done.sh — W3A-3, preserve per-script) ─────
resolve_plan() {
  local arg="$1"
  if [ -f "$arg" ]; then printf '%s\n' "$arg"; return 0; fi
  if [ -d "$arg" ] && [ -f "$arg/00-master-plan.md" ]; then
    printf '%s\n' "$arg/00-master-plan.md"; return 0
  fi
  if [[ "$arg" =~ ^[0-9A-Za-z] ]]; then
    local candidates=()
    while IFS= read -r line; do
      [ -n "$line" ] && candidates+=("$line")
    done < <(
      find plans -type f -name '00-master-plan.md' 2>/dev/null \
        | grep -E "/${arg}(-|/)" | sort -u
    )
    if [ "${#candidates[@]}" -eq 0 ]; then
      echo "task-undone.sh: no plan matches bare id '$arg'" >&2; return 1
    fi
    if [ "${#candidates[@]}" -gt 1 ]; then
      echo "task-undone.sh: bare id '$arg' matches ${#candidates[@]} plans:" >&2
      for c in "${candidates[@]}"; do echo "  $c" >&2; done
      return 1
    fi
    printf '%s\n' "${candidates[0]}"; return 0
  fi
  echo "task-undone.sh: plan not found: $arg" >&2; return 1
}

PLAN="$(resolve_plan "$PLAN_ARG")" || exit 1
PLAN="$(python3 -c 'import os,sys; print(os.path.normpath(sys.argv[1]))' "$PLAN")"
[ -f "$PLAN" ] || { echo "task-undone.sh: plan file missing: $PLAN" >&2; exit 1; }

# ── Delegate to planctl uncheck ────────────────────────────────────────────────
exec bash "$SCRIPT_DIR/planctl.sh" uncheck "$PLAN" "${HANDLES[@]}" --by "$BY"
