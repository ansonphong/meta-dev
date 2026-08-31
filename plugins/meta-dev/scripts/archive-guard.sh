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
# Fail-safe: ANY error, missing file, or unreadable derived state => BLOCK (exit 1).
# A caller may archive ONLY when this guard exits 0. It can never be overridden.
#
# Usage: bash archive-guard.sh <plan-path>

fail_block() { echo "BLOCK: $*"; exit 1; }

PLAN="${1:-}"
[ -n "$PLAN" ] || fail_block "no plan path given"
[ -f "$PLAN" ] || fail_block "plan file not found: $PLAN"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

reasons=()

# --- Locate the plans/ root (for cross-file checks) ---------------------------
plans_dir="$(dirname "$PLAN")"
while [ "$(basename "$plans_dir")" != "plans" ] && [ "$plans_dir" != "/" ] && [ "$plans_dir" != "." ]; do
  plans_dir="$(dirname "$plans_dir")"
done
[ "$(basename "$plans_dir")" = "plans" ] || fail_block "plan is not inside a plans directory"
RUNBOOK_FILE="$plans_dir/meta-runbook.md"
# Normalize the plan path to its repo-relative form (plans/...) so it can be
# matched against the runbook Sequence entries regardless of how it was passed.
plan_rel="plans/${PLAN#*plans/}"

# --- Gate 1: planctl's derived state MUST be exactly done --------------------
# Typed status is legacy input and is never truth. Parse the Markdown directly,
# then call planctl's one status interpreter so this guard cannot drift from the
# dashboard/index semantics or trust a stale SQLite row.
derived_result="$(
  PYTHONPATH="$SCRIPT_DIR" python3 - "$PLAN" <<'PY'
import pathlib
import sys

from planctl import derive, parse

try:
    text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
except (OSError, UnicodeError) as exc:
    print("ERROR\tunable to read plan: %s" % exc)
    raise SystemExit(0)

frontmatter, _legacy_status = parse.parse_frontmatter(text)
tasks, task_error = parse.parse_tasks(text)
parse_error = frontmatter.get("parse_err") or task_error
if parse_error:
    print("ERROR\t%s" % parse_error)
    raise SystemExit(0)

execution = [task for task in tasks if not task.human_verify]
done = sum(1 for task in execution if task.checked)
status, drift = derive.derive_plan(frontmatter, done, len(execution))
print("OK\t%s\t%s" % (status, "true" if drift else "false"))
PY
)" || fail_block "cannot derive plan status"

IFS=$'\t' read -r derived_kind derived_status derived_drift <<< "$derived_result"
if [ "$derived_kind" != "OK" ]; then
  reasons+=("cannot derive plan status${derived_status:+: $derived_status}")
elif [ "$derived_status" != "done" ]; then
  reasons+=("derived status is '$derived_status', not done — plan is unfinished")
elif [ "$derived_drift" = "true" ]; then
  reasons+=("derived done state has open execution tasks")
fi

# --- Gate 2: zero unchecked checkboxes --------------------------------------
unchecked="$(grep -cE '^[[:space:]]*[-*][[:space:]]+\[[[:space:]]\]' "$PLAN" || true)"
if [ "${unchecked:-0}" -gt 0 ]; then
  reasons+=("$unchecked unchecked checkbox(es) [ ] remain — work is unfinished")
fi

# --- Gate 3: no explicit task-state markers ---------------------------------
# Match machine-shaped markers only. Ordinary design prose such as "claimed
# symbol" or a UI title such as "Render in progress" is not execution state.
marker_result="$(
  PYTHONPATH="$SCRIPT_DIR" python3 - "$PLAN" <<'PY'
import pathlib
import re
import sys

text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
task_marker = re.compile(
    r"^\s*[-*]\s*\[[ xX]\]\s+"
    r"(?:(?:#[0-9a-f]{4}(?:\.\d+)?|`?T[A-Za-z0-9]+\.\d+`?|DONE)\s+)*"
    r"`?(?:CLAIMED|WIP|🚧)`?(?:\s|$)",
    re.IGNORECASE,
)
state_marker = re.compile(
    r"^\s*(?:status|state)\s*:\s*(?:CLAIMED|WIP|🚧|in[- ]progress)\s*$",
    re.IGNORECASE,
)
heading_task_marker = re.compile(
    r"^\s*#{1,6}\s+Task(?:\s+[^:]+)?\s*:\s*\[[ xX]\]\s+"
    r"(?:(?:#[0-9a-f]{4}(?:\.\d+)?|`?T[A-Za-z0-9]+\.\d+`?|DONE)\s+)*"
    r"`?(?:CLAIMED|WIP|🚧)`?(?:\s|$)",
    re.IGNORECASE,
)
standalone_marker = re.compile(r"^\s*🚧(?:\s|$)")
print(
    "MARKER" if any(
        task_marker.search(line)
        or state_marker.search(line.replace("*", ""))
        or heading_task_marker.search(line)
        or standalone_marker.search(line)
        for line in text.splitlines()
    ) else "CLEAR"
)
PY
)" || fail_block "cannot inspect active-work markers"
case "$marker_result" in
  MARKER) reasons+=("plan contains an explicit active-work marker") ;;
  CLEAR) : ;;
  *) reasons+=("cannot inspect active-work markers") ;;
esac

# --- Gate 4: not listed active in meta-runbook.md `## Sequence` ---------------
# Use planctl's own Sequence grammar, including bullets and numeric list items.
# Unlike the general reader, the archive gate fails closed when the ledger or
# Sequence section cannot be read: absence is not proof that a plan is inactive.
sequence_result="$(
  PYTHONPATH="$SCRIPT_DIR" python3 - "$RUNBOOK_FILE" "$plan_rel" <<'PY'
import pathlib
import sys

from planctl import read

lines = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
start = None
for index, line in enumerate(lines):
    if read._SEQ_HEAD_RE.match(line.strip()):
        start = index + 1
        break
if start is None:
    print("NO_SEQUENCE")
    raise SystemExit(0)

end = len(lines)
for index in range(start, len(lines)):
    if read._SEQ_NEXT_HEAD_RE.match(lines[index]):
        end = index
        break

target = sys.argv[2]
for raw in lines[start:end]:
    body = read._SEQ_BULLET_RE.sub("", raw.strip())
    match = read._SEQ_PATH_RE.match(body)
    if match and match.group(1) == target:
        print("LISTED")
        raise SystemExit(0)
print("CLEAR")
PY
)" || fail_block "cannot inspect meta-runbook.md Sequence"
case "$sequence_result" in
  LISTED) reasons+=("listed active in meta-runbook.md \`## Sequence\` — still on the critical path") ;;
  CLEAR) : ;;
  NO_SEQUENCE) reasons+=("meta-runbook.md has no readable \`## Sequence\` section") ;;
  *) reasons+=("cannot inspect meta-runbook.md Sequence") ;;
esac

# --- Verdict ----------------------------------------------------------------
if [ "${#reasons[@]}" -gt 0 ]; then
  printf 'BLOCK:'
  for r in "${reasons[@]}"; do printf ' %s;' "$r"; done
  printf '\n'
  exit 1
fi

echo "PASS"
exit 0
