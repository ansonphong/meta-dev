#!/usr/bin/env bash
set -euo pipefail
# stage-emit.sh — Patch a plan's YAML frontmatter (the SINGLE source of truth
# for its waterfall stage) AND emit a slim stage_transition event to the
# dashboard state log (history/timeline).
#
# Usage: stage-emit.sh <plan> <stage> [status]
#   <plan>    Plan path you were invoked on, resolved relative to the current
#             working directory / project root
#             (e.g. plans/app/FOO/00-master-plan.md).
#   <stage>   brainstorm | design | plan | harden | execute | review
#             OR a number 1-6 (used as-is when already numeric).
#   [status]  Optional. When given, written to the plan's `status:` key and
#             carried on the event. Defaults to in_progress for the event.
#
# Primary action: patch the FIRST `---...---` frontmatter block of <plan> in
# place — set `stage:` (numeric), `status:` (if given) and `updated:` (today).
# If the file is missing or has no frontmatter block, WARN and skip patching
# (never create frontmatter, never error). Still emits the event.
#
# Reuses state-append.sh (validates + appends). The reducer (state-reduce.py)
# folds stage_transition into the per-plan `plan_stages` map.
#
# Examples:
#   stage-emit.sh plans/app/FOO/00-master-plan.md harden in_progress
#   stage-emit.sh plans/app/FOO/00-master-plan.md 4 blocked

PLAN="${1:-}"
STAGE="${2:-}"
STATUS="${3:-in_progress}"

if [ -z "$PLAN" ] || [ -z "$STAGE" ]; then
    echo "Usage: stage-emit.sh <plan> <stage> [in_progress|completed|blocked]" >&2
    exit 1
fi

# Resolve stage arg → numeric 1-6. Accept name OR already-numeric.
case "$STAGE" in
    brainstorm) N=1 ;;
    design)     N=2 ;;
    plan)       N=3 ;;
    harden)     N=4 ;;
    execute)    N=5 ;;
    review)     N=6 ;;
    1|2|3|4|5|6) N="$STAGE" ;;
    *)          echo "stage-emit.sh: unknown stage '$STAGE' (expected brainstorm|design|plan|harden|execute|review or 1-6)" >&2; exit 1 ;;
esac

TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TODAY="$(date +%F)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Whether a status was explicitly passed (arg 3 present).
STATUS_GIVEN=0
[ "$#" -ge 3 ] && [ -n "${3:-}" ] && STATUS_GIVEN=1

# --- Primary action: patch the plan's YAML frontmatter in place ----------
# Off-limits file: never patch exec-order-2026-06-26.md (event append still ok).
GUARDED="plans/exec-order-2026-06-26.md"
if [ "$PLAN" = "$GUARDED" ] || [ "$(basename "$PLAN")" = "exec-order-2026-06-26.md" ]; then
    echo "[stage-emit] guardrail: skipping frontmatter patch for $PLAN" >&2
elif [ ! -f "$PLAN" ]; then
    echo "[stage-emit] WARNING: plan file not found, skipping frontmatter patch: $PLAN" >&2
else
    python3 - "$PLAN" "$N" "$STATUS" "$STATUS_GIVEN" "$TODAY" <<'PYEOF'
import os, sys, tempfile

path, stage, status, status_given, today = sys.argv[1:6]
status_given = status_given == "1"

with open(path, "r", encoding="utf-8", newline="") as f:
    text = f.read()

lines = text.split("\n")

# A frontmatter block must START on the first line with exactly '---'.
if not lines or lines[0].strip() != "---":
    sys.stderr.write(
        "[stage-emit] WARNING: no YAML frontmatter block, skipping patch: %s\n" % path
    )
    sys.exit(0)

# Find the closing '---' for the first block (search from line 1).
close = None
for i in range(1, len(lines)):
    if lines[i].strip() == "---":
        close = i
        break

if close is None:
    sys.stderr.write(
        "[stage-emit] WARNING: unterminated frontmatter block, skipping patch: %s\n" % path
    )
    sys.exit(0)

# Block body = lines[1:close]; patch ONLY within this range.
updates = {"stage": stage, "updated": today}
if status_given:
    updates["status"] = status

seen = set()
for i in range(1, close):
    line = lines[i]
    stripped = line.lstrip()
    # Skip blanks/comments inside the block.
    if not stripped or stripped.startswith("#"):
        continue
    if ":" not in stripped:
        continue
    key = stripped.split(":", 1)[0].strip()
    if key in updates:
        indent = line[: len(line) - len(stripped)]
        lines[i] = "%s%s: %s" % (indent, key, updates[key])
        seen.add(key)

# Insert any keys that were absent — just before the closing '---'.
missing = [k for k in ("status", "stage", "updated") if k in updates and k not in seen]
if missing:
    insert_at = close
    for k in missing:
        lines.insert(insert_at, "%s: %s" % (k, updates[k]))
        insert_at += 1

new_text = "\n".join(lines)

# Atomic write: temp file in same dir + rename.
d = os.path.dirname(os.path.abspath(path))
fd, tmp = tempfile.mkstemp(dir=d, prefix=".stage-emit.", suffix=".tmp")
try:
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as out:
        out.write(new_text)
    os.replace(tmp, path)
except Exception:
    try:
        os.unlink(tmp)
    except OSError:
        pass
    raise
PYEOF
fi

# --- Existing behavior: append the slim stage_transition event -----------
STAGE_NAME="$STAGE"
case "$N" in
    1) STAGE_NAME=brainstorm ;;
    2) STAGE_NAME=design ;;
    3) STAGE_NAME=plan ;;
    4) STAGE_NAME=harden ;;
    5) STAGE_NAME=execute ;;
    6) STAGE_NAME=review ;;
esac

# Build the event with python so plan paths/status are always JSON-safe.
EVENT="$(python3 -c 'import json,sys; print(json.dumps({"event":"stage_transition","plan":sys.argv[1],"stage":sys.argv[2],"stage_num":int(sys.argv[3]),"status":sys.argv[4],"time":sys.argv[5]}))' "$PLAN" "$STAGE_NAME" "$N" "$STATUS" "$TIME")"

"$SCRIPT_DIR/state-append.sh" "$EVENT"
echo "[stage-emit] $PLAN → stage $N ($STAGE_NAME) $STATUS"
