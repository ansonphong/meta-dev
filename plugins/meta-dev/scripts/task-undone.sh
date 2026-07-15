#!/usr/bin/env bash
# task-undone.sh — Reopen stamped plan checkboxes [x] → [ ].
#
# Usage: task-undone.sh [--by <who>] <plan> <handle> [<handle>…]
#
# Same sidecar flock + atomic write + scope-lock as task-done.sh.
# Appends task_undone via state-append.sh AFTER write lands.
# Unknown handle → non-zero + named error, continues remaining handles.
# Already [ ] → no-op exit 0 for that handle.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/anchor-root.sh
source "$SCRIPT_DIR/lib/anchor-root.sh"

BY="${USER:-conductor}"
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --by) BY="${2:-}"; shift 2 ;;
    -*)
      echo "task-undone.sh: unknown flag: $1" >&2
      exit 2
      ;;
    *) ARGS+=("$1"); shift ;;
  esac
done

if [ "${#ARGS[@]}" -lt 2 ]; then
  echo "Usage: task-undone.sh [--by <who>] <plan> <handle> [<handle>…]" >&2
  exit 2
fi

PLAN_ARG="${ARGS[0]}"
HANDLES=("${ARGS[@]:1}")

# Reuse resolve logic from task-done by calling it via a tiny shared path:
# inline a minimal resolve (file / dir / bare).
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
  echo "task-undone.sh: plan not found: $arg" >&2
  return 1
}

PLAN="$(resolve_plan "$PLAN_ARG")" || exit 1
PLAN="$(python3 -c 'import os,sys; print(os.path.normpath(sys.argv[1]))' "$PLAN")"
[ -f "$PLAN" ] || { echo "task-undone.sh: plan file missing: $PLAN" >&2; exit 1; }

LOCK="${PLAN}.task-lock"
: >>"$LOCK"

TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
PLAN_REL="$(python3 -c '
import os, sys
p = os.path.normpath(sys.argv[1]).replace(os.sep, "/")
print(p[p.index("plans/"):] if "plans/" in p else p)
' "$PLAN")"

export TASK_UNDONE_PLAN="$PLAN"
export TASK_UNDONE_BY="$BY"
export TASK_UNDONE_TIME="$TIME"
export TASK_UNDONE_PLAN_REL="$PLAN_REL"
export TASK_UNDONE_HANDLES="$(printf '%s\n' "${HANDLES[@]}")"
export TASK_UNDONE_STATE_APPEND="$SCRIPT_DIR/state-append.sh"

(
  flock -x 200
  python3 - <<'PY'
import json, os, re, sys, tempfile, subprocess

plan = os.environ["TASK_UNDONE_PLAN"]
by = os.environ.get("TASK_UNDONE_BY", "conductor")
time_s = os.environ.get("TASK_UNDONE_TIME", "")
plan_rel = os.environ.get("TASK_UNDONE_PLAN_REL", plan)
handles_raw = os.environ.get("TASK_UNDONE_HANDLES", "").splitlines()
state_append = os.environ.get("TASK_UNDONE_STATE_APPEND", "state-append.sh")

def norm(h: str) -> str:
    h = h.strip()
    if h.startswith("`") and h.endswith("`"):
        h = h[1:-1]
    return h

handles = [norm(h) for h in handles_raw if h.strip()]
box_re = re.compile(r"^(\s*[-*]\s+)\[([ xX])\](\s*)(.*)$")

with open(plan, "r", encoding="utf-8", newline="") as f:
    text = f.read()
ends_nl = text.endswith("\n")
lines = text.split("\n")

def find_handle_line(handle: str):
    target = handle if handle.startswith("T") else f"T{handle}"
    for i, line in enumerate(lines):
        m = box_re.match(line)
        if not m:
            continue
        rest = m.group(4)
        for hm in re.finditer(r"`?(T[A-Za-z0-9]+\.\d+)`?", rest):
            if hm.group(1) == target:
                return i, m.group(2), m
    return None

any_error = False
flipped = []

for h in handles:
    if not re.fullmatch(r"T[A-Za-z0-9]+\.\d+", h):
        print(f"task-undone: invalid handle format: {h!r}", file=sys.stderr)
        any_error = True
        continue
    found = find_handle_line(h)
    if found is None:
        print(f"task-undone: unknown handle {h} in {plan_rel}", file=sys.stderr)
        any_error = True
        continue
    idx, mark, m = found
    prefix, gap, rest = m.group(1), m.group(3), m.group(4)
    if mark == " ":
        print(f"task-undone: {h} already [ ] (no-op)")
        continue
    lines[idx] = f"{prefix}[ ]{gap}{rest}"
    flipped.append(h)
    print(f"task-undone: reopened {h} → [ ]")

new_text = "\n".join(lines)
if ends_nl and not new_text.endswith("\n"):
    new_text += "\n"

if flipped:
    d = os.path.dirname(plan) or "."
    fd, tmp = tempfile.mkstemp(prefix=f".{os.path.basename(plan)}.", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(new_text)
        os.replace(tmp, plan)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    for h in flipped:
        event = {
            "event": "task_undone",
            "plan": plan_rel,
            "handle": h,
            "by": by,
            "time": time_s,
        }
        r = subprocess.run(
            ["bash", state_append, json.dumps(event, separators=(",", ":"))],
            check=False,
        )
        if r.returncode != 0:
            print(f"task-undone: WARN state-append failed for {h}", file=sys.stderr)

sys.exit(1 if any_error else 0)
PY
) 200>"$LOCK"
exit $?
