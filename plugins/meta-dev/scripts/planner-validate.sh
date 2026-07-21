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
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERIFY_SCOPE="$SCRIPT_DIR/verify-scope.py"

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

# Check 7: automated Verify hooks must be focused. Broad commands are not
# deferred to a phase gate; they are forbidden throughout /meta-execute and
# belong to CI/ship or a separate explicit user request.
for f in "$PLAN_DIR"/*phase*.md; do
  [ -f "$f" ] || continue
  body=$(sed '/^```/,/^```/d' "$f")
  if printf '%s' "$body" | grep -qE 'pytest[^`]*-k '; then
    red "$(basename "$f"): a Verify hook uses 'pytest -k' — name the exact test file/node"
  fi
  if printf '%s' "$body" | grep -qE 'pytest +[^ ]*/ +-q|pytest +[A-Za-z_./-]*/ *$'; then
    red "$(basename "$f"): a Verify hook runs pytest on a directory — name the exact test file/node"
  fi
  if printf '%s' "$body" | grep -qiE 'npm run check|pnpm (run )?check|yarn (run )?check|svelte-check|tsc( --noEmit)?|npm run build|pnpm (run )?build|yarn (run )?build'; then
    red "$(basename "$f"): execution plan contains a broad check/typecheck/build — replace it with a named test file or declared-file check; do not move it to phase end"
  fi

  # Extract backticked commands inside Verify-After blocks. Each command is
  # classified by the same helper /meta-execute calls before dispatch. Path
  # tokens in the command are the validator's allowed-path candidates; the
  # judgment pass separately confirms they are declared task paths.
  verify_body=$(awk '
    /Verify-After:/ { in_verify=1; next }
    in_verify && /^#/ { in_verify=0 }
    in_verify { print }
  ' "$f")
  while IFS= read -r quoted; do
    [ -n "$quoted" ] || continue
    cmd=${quoted#\`}; cmd=${cmd%\`}
    allowed_args=()
    while IFS= read -r candidate; do
      [ -n "$candidate" ] || continue
      allowed_args+=(--allowed-path "$candidate")
    done < <(printf '%s\n' "$cmd" | grep -oE '[A-Za-z0-9_./+-]+\.(py|sh|ts|tsx|js|jsx|svelte|md|json)(::[A-Za-z0-9_./:+-]+)?' | sed 's/::.*//' || true)
    if [ "${#allowed_args[@]}" -eq 0 ]; then
      allowed_args=(--allowed-path "__no_declared_path__")
    fi
    if ! scope_json=$(python3 "$VERIFY_SCOPE" --command "$cmd" "${allowed_args[@]}"); then
      red "$(basename "$f"): verify-scope classifier failed for: $cmd"
      continue
    fi
    scope_class=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["class"])' <<< "$scope_json")
    case "$scope_class" in
      focused|scoped_check|manual) ;;
      broad) red "$(basename "$f"): broad Verify command is forbidden in execution: $cmd" ;;
      unscoped) red "$(basename "$f"): Verify command is not focused on a named test/declared path: $cmd" ;;
      *) red "$(basename "$f"): unknown Verify classification '$scope_class': $cmd" ;;
    esac
  done < <(printf '%s\n' "$verify_body" | grep -oE '`[^`]+`' || true)
done

echo "=== planner-validate: $ERRORS errors, $WARNINGS warnings ==="
# Exit 0 = clean, 1 = has warnings OR errors (any finding). Callers grep the output for ERR/WARN.
if [ "$ERRORS" -gt 0 ]; then
  exit 2
elif [ "$WARNINGS" -gt 0 ]; then
  exit 1
fi
exit 0
