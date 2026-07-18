#!/usr/bin/env bash
# task-done.sh — Flip one or more stamped plan checkboxes [ ] → [x].
# SHIM: delegates to planctl check (M3a — unified state layer).
#
# Usage: task-done.sh [--human] [--force] [--by <who>] <plan> <handle> [<handle>…]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/anchor-root.sh
source "$SCRIPT_DIR/lib/anchor-root.sh"

HUMAN=0; FORCE=0; BY="${USER:-conductor}"; ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --human) HUMAN=1; shift ;;
    --force) FORCE=1; shift ;;
    --by) [ $# -ge 2 ] || { echo "task-done.sh: --by requires a value" >&2; exit 2; }; BY="${2}"; shift 2 ;;
    --) shift; break ;;
    -*) echo "task-done.sh: unknown flag: $1" >&2; exit 2 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done
while [ $# -gt 0 ]; do ARGS+=("$1"); shift; done

[ "${#ARGS[@]}" -ge 2 ] || { echo "Usage: task-done.sh [--human] [--force] [--by <who>] <plan> <handle> [<handle>…]" >&2; exit 2; }

PLAN_ARG="${ARGS[0]}"
HANDLES=("${ARGS[@]:1}")

# ── Resolve plan path (preserved from legacy — planctl doesn't do bare-id lookup) ──
resolve_plan() {
  local arg="$1"
  [ -f "$arg" ] && { printf '%s\n' "$arg"; return 0; }
  if [ -d "$arg" ]; then
    [ -f "$arg/00-master-plan.md" ] && { printf '%s\n' "$arg/00-master-plan.md"; return 0; }
    local hits=()
    while IFS= read -r -d '' f; do hits+=("$f"); done < <(find "$arg" -maxdepth 1 -type f -name '*.md' -print0 2>/dev/null)
    [ "${#hits[@]}" -eq 1 ] && { printf '%s\n' "${hits[0]}"; return 0; }
    echo "task-done.sh: plan dir has no 00-master-plan.md and is ambiguous: $arg" >&2; return 1
  fi
  if [[ "$arg" =~ ^[0-9]+([A-Za-z0-9._-]*)$ ]] || [[ "$arg" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
    local candidates=()
    [ -d plans ] && while IFS= read -r line; do [ -n "$line" ] && candidates+=("$line"); done < <(
      find plans -type f \( -name '00-master-plan.md' -o -name '*.md' \) 2>/dev/null \
        | grep -E "/${arg}(-|/|\$)|/${arg}[^/]*/00-master-plan\.md|/${arg}\.md$" \
        | grep -E '00-master-plan\.md$|/[0-9]{4}-[0-9]{2}-[0-9]{2}-.*\.md$' | sort -u)
    local refined=()
    for c in "${candidates[@]+"${candidates[@]}"}"; do
      case "$c" in */"${arg}"/*|*/"${arg}"-*/00-master-plan.md|*/"${arg}"/00-master-plan.md) refined+=("$c") ;; esac
    done
    [ "${#refined[@]}" -gt 0 ] && candidates=("${refined[@]}")
    local masters=()
    for c in "${candidates[@]+"${candidates[@]}"}"; do
      case "$c" in */00-master-plan.md) masters+=("$c") ;; esac
    done
    [ "${#masters[@]}" -gt 0 ] && candidates=("${masters[@]}")
    [ "${#candidates[@]}" -eq 0 ] && { echo "task-done.sh: no plan matches bare id '$arg'" >&2; return 1; }
    [ "${#candidates[@]}" -gt 1 ] && { echo "task-done.sh: bare id '$arg' matches ${#candidates[@]} plans — list candidates, touch nothing:" >&2; for c in "${candidates[@]}"; do echo "  $c" >&2; done; return 1; }
    printf '%s\n' "${candidates[0]}"; return 0
  fi
  echo "task-done.sh: plan not found: $arg" >&2; return 1
}

PLAN="$(resolve_plan "$PLAN_ARG")" || exit 1
PLAN="$(python3 -c 'import os,sys; print(os.path.normpath(sys.argv[1]))' "$PLAN")"
[ -f "$PLAN" ] || { echo "task-done.sh: plan file missing: $PLAN" >&2; exit 1; }

# ── Delegate to planctl check ──────────────────────────────────────────────────
PCTL=(bash "$SCRIPT_DIR/planctl.sh" check "$PLAN" "${HANDLES[@]}" --by "$BY")
[ "$HUMAN" -eq 1 ] && PCTL+=(--human)
[ "$FORCE" -eq 1 ] && PCTL+=(--force)
exec "${PCTL[@]}"
