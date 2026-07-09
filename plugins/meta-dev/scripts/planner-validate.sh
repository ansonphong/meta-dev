#!/usr/bin/env bash
# NOTE: `set -e` is intentionally OMITTED. This script accumulates warnings/errors across
# all checks and prints a summary at the end; `set -e` would abort on the first grep no-match
# (grep returns 1 when the count is 0) or any awk non-zero exit, hiding later checks and
# producing a misleading early exit. We guard each check explicitly instead.
set -uo pipefail
# planner-validate.sh — Deterministic plan consistency checks
# Usage: planner-validate.sh <plan-directory>
# Exit codes: 0 = clean, 1 = warnings, 2 = errors

PLAN_DIR="${1:-.}"
WARNINGS=0
ERRORS=0

yellow() { echo -e "\033[33mWARN: $1\033[0m"; WARNINGS=$((WARNINGS+1)); }
red() { echo -e "\033[31mERR: $1\033[0m"; ERRORS=$((ERRORS+1)); }

# Task-heading matcher. The planner authoring rule (commands/meta-planner.md step 2 + LP-001)
# mandates `### Task N:` (h3). Older plans used `## Task` (h2). Accept both so the validator
# works on every plan regardless of heading level. The task id may carry a letter phase suffix
# (e.g. `2a.1`, `2b.3`), so match `[0-9a-z]+\.[0-9]+`, not bare `\d+\.\d+`.
TASK_HEAD='^#{2,3} Task [0-9a-z]+\.[0-9a-z]+'

# Check 1: Numbering is sequential within each phase file (outside code blocks)
for f in "$PLAN_DIR"/*phase*.md; do
  [ -f "$f" ] || continue
  nums=$(sed '/^```/,/^```/d' "$f" | grep -oP "$TASK_HEAD" | grep -oP '[0-9a-z]+\.[0-9a-z]+' | sort -V)
  [ -z "${nums:-}" ] && continue
  prev=""
  while IFS= read -r id; do
    if [ -n "$prev" ]; then
      pm=${prev%%.*}; pid_major=${id%%.*}
      if [ "$pm" = "$pid_major" ]; then
        prev_minor=${prev#*.}; this_minor=${id#*.}
        # only enforce monotonic minor when both are purely numeric (skip letter-suffix minors)
        if [[ "$prev_minor" =~ ^[0-9]+$ && "$this_minor" =~ ^[0-9]+$ ]] && [ "$this_minor" != "$((prev_minor + 1))" ]; then
          yellow "$(basename "$f"): non-sequential task numbering at $id (prev was $prev)"
        fi
      fi
    fi
    prev=$id
  done <<< "$nums"
done

# Check 2: Every task has Verify-After (outside code blocks)
for f in "$PLAN_DIR"/*phase*.md; do
  [ -f "$f" ] || continue
  task_count=$(grep -cE "$TASK_HEAD" "$f" 2>/dev/null || echo 0)
  verify_count=$(sed '/^```/,/^```/d' "$f" | grep -c 'Verify-After:' 2>/dev/null || echo 0)
  if [ "$task_count" != "$verify_count" ]; then
    red "$(basename "$f"): $task_count tasks but $verify_count Verify-After sections"
  fi
done

# Check 3: Every Verify-After has at least one checklist item (non-empty verification)
# NOTE: a checklist item is ANY cheap check — build passes, grep is clean, run-by-eye.
# It need NOT be an authored test. Under test_policy=critical-only (default) most tasks
# verify this way; only critical-breakage tasks (test: yes) add a real test. Do not tighten
# this check to require a test command — that would re-inflate the suite.
for f in "$PLAN_DIR"/*phase*.md; do
  [ -f "$f" ] || continue
  # Get line numbers of Verify-After headers
  verify_lines=$(grep -n 'Verify-After:' "$f" | cut -d: -f1)
  [ -z "${verify_lines:-}" ] && continue
  while IFS= read -r line_num; do
    [ -z "$line_num" ] && continue
    # Look ahead from Verify-After line for a checklist item before the next heading or end.
    # Uses `if ! awk` (NOT `cmd || \ continuation`, which was a syntax bug) and matches ANY
    # heading (^#) as the boundary, not only h2.
    if ! awk -v start="$line_num" '
      NR > start && /^[*-] \[[ xX]\]/ { found=1; exit }
      NR > start && /^#/ { exit }
      END { exit !found }
    ' "$f"; then
      yellow "$(basename "$f"): Verify-After at line $line_num has no checklist items"
    fi
  done <<< "$verify_lines"
done

# Check 4: No dangling file references
for f in "$PLAN_DIR"/*phase*.md; do
  [ -f "$f" ] || continue
  while IFS= read -r path; do
    [ -z "$path" ] && continue
    if [ ! -f "$path" ] && [ ! -f "$PLAN_DIR/../$path" ]; then
      yellow "$(basename "$f"): Modify file not found — $path"
    fi
  done < <(grep -oP 'Modify:\s*`([^`]+)`' "$f" | grep -oP '`[^`]+`' | tr -d '`')
done

# Check 5: No TBD/TODO/placeholders outside code blocks
for f in "$PLAN_DIR"/*phase*.md; do
  [ -f "$f" ] || continue
  # Remove code blocks (``` ... ```), then check remaining text
  if sed '/^```/,/^```/d' "$f" | grep -qiP '(TBD|TODO|coming soon|placeholder)'; then
    red "$(basename "$f"): contains TBD/TODO/placeholder outside code blocks"
  fi
done

# Check 6: Phase-size cap — phases should stay small (~3 tasks) for fast cycles
for f in "$PLAN_DIR"/*phase*.md; do
  [ -f "$f" ] || continue
  tcount=$(grep -cE "$TASK_HEAD" "$f" 2>/dev/null || echo 0)
  if [ "$tcount" -gt 3 ]; then
    yellow "$(basename "$f"): $tcount tasks (> 3) — oversized phase; split into phase-N-a/phase-N-b for faster cycles (Fast Test Doctrine)"
  fi
done

# Check 7: Verify hooks must be path-scoped — flag the slow `-k`/bare-dir/broad-gate antipatterns
# `pytest -k <expr>` and `pytest <dir>/` collect the WHOLE tree (~18x slower per cycle);
# svelte-check/tsc/build per task belong only in an end-of-phase Acceptance Gate.
for f in "$PLAN_DIR"/*phase*.md; do
  [ -f "$f" ] || continue
  body=$(sed '/^```/,/^```/d' "$f")
  if printf '%s' "$body" | grep -qE 'pytest[^`]*-k '; then
    yellow "$(basename "$f"): a Verify hook uses 'pytest -k' — path-scope instead (name the test file); -k collects all files first (~18x tax)"
  fi
  if printf '%s' "$body" | grep -qE 'pytest +[^ ]*/ +-q|pytest +[A-Za-z_./-]*/ *$'; then
    yellow "$(basename "$f"): a Verify hook runs pytest on a directory — name the test file(s) instead for fast collection"
  fi
  if printf '%s' "$body" | grep -qiE 'svelte-check|tsc --noEmit|npm run build'; then
    yellow "$(basename "$f"): a per-task Verify hook runs svelte-check/tsc/build — move these to a single '## Acceptance Gate (phase end)' section, not per task"
  fi
done

echo "=== planner-validate: $ERRORS errors, $WARNINGS warnings ==="
# Exit 0 = clean, 1 = has warnings OR errors (any finding). Callers grep the output for ERR/WARN.
if [ "$ERRORS" -gt 0 ]; then
  exit 2
elif [ "$WARNINGS" -gt 0 ]; then
  exit 1
fi
exit 0
