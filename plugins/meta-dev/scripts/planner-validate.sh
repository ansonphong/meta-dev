#!/usr/bin/env bash
set -euo pipefail
# planner-validate.sh — Deterministic plan consistency checks
# Usage: planner-validate.sh <plan-directory>
# Exit codes: 0 = clean, 1 = warnings, 2 = errors

PLAN_DIR="${1:-.}"
WARNINGS=0
ERRORS=0

yellow() { echo -e "\033[33mWARN: $1\033[0m"; WARNINGS=$((WARNINGS+1)); }
red() { echo -e "\033[31mERR: $1\033[0m"; ERRORS=$((ERRORS+1)); }

# Check 1: Numbering is sequential within each phase file (outside code blocks)
for f in "$PLAN_DIR"/*phase*.md; do
  [ -f "$f" ] || continue
  nums=$(sed '/^```/,/^```/d' "$f" | grep -oP '^## Task \d+\.\d+' | grep -oP '\d+\.\d+' | sort -t. -k1,1n -k2,2n)
  if [ -z "$nums" ]; then continue; fi
  prev_major=""; prev_minor=0
  while IFS=. read -r major minor; do
    if [ "$major" = "$prev_major" ] && [ "$minor" != "$((prev_minor + 1))" ]; then
      yellow "$(basename "$f"): non-sequential task numbering at $major.$minor (prev was $prev_major.$prev_minor)"
    fi
    prev_major=$major; prev_minor=$minor
  done <<< "$nums"
done

# Check 2: Every task has Verify-After (outside code blocks)
for f in "$PLAN_DIR"/*phase*.md; do
  [ -f "$f" ] || continue
  task_count=$(grep -c '^## Task ' "$f" 2>/dev/null || echo 0)
  verify_count=$(sed '/^```/,/^```/d' "$f" | grep -c 'Verify-After:' 2>/dev/null || echo 0)
  if [ "$task_count" != "$verify_count" ]; then
    red "$(basename "$f"): $task_count tasks but $verify_count Verify-After sections"
  fi
done

# Check 3: Every Verify-After has at least one checklist item (non-empty verification)
for f in "$PLAN_DIR"/*phase*.md; do
  [ -f "$f" ] || continue
  # Get line numbers of Verify-After headers
  verify_lines=$(grep -n 'Verify-After:' "$f" | cut -d: -f1)
  if [ -z "$verify_lines" ]; then continue; fi
  while IFS= read -r line_num; do
    # Look ahead from Verify-After line for a checklist item before next ## or end
    awk -v start="$line_num" 'NR > start && /^[-*] \[[ x]\]/ {found=1; exit} NR > start && /^## / {exit} END {exit !found}' "$f" || \      yellow "$(basename "$f"): Verify-After at line $line_num has no checklist items"
  done <<< "$verify_lines"
done

# Check 4: No dangling file references
for f in "$PLAN_DIR"/*phase*.md; do
  [ -f "$f" ] || continue
  while IFS= read -r path; do
    if [ ! -f "$path" ] && [ ! -f "$PLAN_DIR/../$path" ]; then
      yellow "$(basename "$f"): Modify file not found — $path"
    fi
  done < <(grep -oP 'Modify:\s*\`([^\`]+)\`' "$f" | grep -oP '\`[^\`]+\`' | tr -d '\`')
done

# Check 5: No TBD/TODO/placeholders outside code blocks
for f in "$PLAN_DIR"/*phase*.md; do
  [ -f "$f" ] || continue
  # Remove code blocks (``` ... ```), then check remaining text
  clean=$(sed '/^```/,/^```/d' "$f" | grep -qiP '(TBD|TODO|coming soon|placeholder)' && echo "HIT" || echo "CLEAN")
  if [ "$clean" = "HIT" ]; then
    red "$(basename "$f"): contains TBD/TODO/placeholder outside code blocks"
  fi
done

echo "=== planner-validate: $ERRORS errors, $WARNINGS warnings ==="
exit $ERRORS
