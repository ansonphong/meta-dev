#!/usr/bin/env bash
set -euo pipefail
# archive-guard.sh — DETERMINISTIC archivability gate for a single plan.
#
# This exists because LLM housekeeping agents rationalized past prose "NEVER
# archive unfinished plans" rules and archived in-development plans. This guard
# removes the judgment: it is a mechanical PASS/BLOCK with no discretion.
#
# Contract:
#   PASS  → prints "PASS" and exits 0. The plan's paperwork proves it is finished.
#   BLOCK → prints "BLOCK: <reasons>" and exits 1. The plan is in development /
#           unfinished / in process and MUST NOT be archived.
#
# Fail-safe: ANY error, missing file, or unreadable status => BLOCK (exit 1).
# A caller may archive ONLY when this guard exits 0. It can never be overridden.
#
# Usage: bash archive-guard.sh <plan-path>

fail_block() { echo "BLOCK: $*"; exit 1; }

PLAN="${1:-}"
[ -n "$PLAN" ] || fail_block "no plan path given"
[ -f "$PLAN" ] || fail_block "plan file not found: $PLAN"

reasons=()

# --- Locate the plans/ root (for cross-file checks) ---------------------------
plans_dir="$(dirname "$PLAN")"
while [ "$(basename "$plans_dir")" != "plans" ] && [ "$plans_dir" != "/" ] && [ "$plans_dir" != "." ]; do
  plans_dir="$(dirname "$plans_dir")"
done
STATUS_FILE="$plans_dir/STATUS.md"
EXEC_FILE="$plans_dir/exec-order.md"
base="$(basename "$PLAN")"

# --- Gate 1: frontmatter Status MUST be exactly Done -------------------------
# Handles "**Status:** Done", "Status: Done", any case. Reads first match only.
status_line="$(grep -m1 -iE '^[*[:space:]]*status[*[:space:]]*:' "$PLAN" || true)"
if [ -z "$status_line" ]; then
  reasons+=("no Status: field found (cannot prove Done)")
else
  status_val="$(printf '%s' "$status_line" | sed -E 's/^[^:]*:[[:space:]]*//; s/\*+//g; s/^[[:space:]]+//; s/[[:space:]]+$//' | tr '[:upper:]' '[:lower:]')"
  # A status that lists the options (template not filled in) is NOT Done.
  case "$status_val" in
    done) : ;;  # the only acceptable value
    *) reasons+=("Status is '$status_val', not Done — plan is in development/unfinished") ;;
  esac
fi

# --- Gate 2: zero unchecked checkboxes --------------------------------------
unchecked="$(grep -cE '^[[:space:]]*[-*][[:space:]]+\[[[:space:]]\]' "$PLAN" || true)"
if [ "${unchecked:-0}" -gt 0 ]; then
  reasons+=("$unchecked unchecked checkbox(es) [ ] remain — work is unfinished")
fi

# --- Gate 3: no in-progress / claimed markers --------------------------------
# meta-execute marks in-flight tasks CLAIMED; WIP/🚧/IN PROGRESS = active work.
if grep -qiE '(\bCLAIMED\b|\bWIP\b|🚧|in[ -]progress)' "$PLAN"; then
  reasons+=("plan contains an active-work marker (CLAIMED/WIP/🚧/in-progress)")
fi

# --- Gate 4: not listed unchecked in exec-order.md ---------------------------
if [ -f "$EXEC_FILE" ]; then
  if grep -nE "\[[[:space:]]\].*${base}|${base}.*\[[[:space:]]\]" "$EXEC_FILE" >/dev/null 2>&1; then
    reasons+=("listed UNCHECKED in exec-order.md — still on the critical path")
  fi
fi

# --- Verdict ----------------------------------------------------------------
if [ "${#reasons[@]}" -gt 0 ]; then
  printf 'BLOCK:'
  for r in "${reasons[@]}"; do printf ' %s;' "$r"; done
  printf '\n'
  exit 1
fi

echo "PASS"
exit 0
