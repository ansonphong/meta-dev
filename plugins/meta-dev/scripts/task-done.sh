#!/usr/bin/env bash
# task-done.sh — Flip one or more stamped plan checkboxes [ ] → [x].
#
# Usage: task-done.sh [--human] [--force] [--by <who>] <plan> <handle> [<handle>…]
#
# <plan>    Path to a plan file, a plan dir, or a bare number (e.g. 50).
#           Bare number with 0 or >1 matches → fail loud, list candidates, touch nothing.
# <handle>  T<phase>.<seq>  (with or without surrounding backticks)
#
# Properties:
#   - flock on sidecar <plan>.task-lock (NOT the plan inode — rename would drop it)
#   - atomic temp+rename of plan body
#   - appends task_done via state-append.sh AFTER flip lands
#   - unknown handle → non-zero + named error, continues remaining handles
#   - already [x] → no-op exit 0 for that handle
#   - refuses human-tagged boxes unless --human (same tag_re + sec_re as on-run-complete)
#   - scope-locked: no git, no other files
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/anchor-root.sh
source "$SCRIPT_DIR/lib/anchor-root.sh"

HUMAN=0
FORCE=0
BY="${USER:-conductor}"
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --human) HUMAN=1; shift ;;
    --force) FORCE=1; shift ;;
    --by) BY="${2:-}"; shift 2 ;;
    --) shift; break ;;
    -*)
      echo "task-done.sh: unknown flag: $1" >&2
      exit 2
      ;;
    *) ARGS+=("$1"); shift ;;
  esac
done
# trailing after --
while [ $# -gt 0 ]; do ARGS+=("$1"); shift; done

if [ "${#ARGS[@]}" -lt 2 ]; then
  echo "Usage: task-done.sh [--human] [--force] [--by <who>] <plan> <handle> [<handle>…]" >&2
  exit 2
fi

PLAN_ARG="${ARGS[0]}"
HANDLES=("${ARGS[@]:1}")

# ── Resolve plan path ────────────────────────────────────────────────────────
resolve_plan() {
  local arg="$1"
  if [ -f "$arg" ]; then
    printf '%s\n' "$arg"
    return 0
  fi
  if [ -d "$arg" ]; then
    if [ -f "$arg/00-master-plan.md" ]; then
      printf '%s\n' "$arg/00-master-plan.md"
      return 0
    fi
    # single .md in dir?
    local hits=()
    while IFS= read -r -d '' f; do hits+=("$f"); done < <(find "$arg" -maxdepth 1 -type f -name '*.md' -print0 2>/dev/null)
    if [ "${#hits[@]}" -eq 1 ]; then
      printf '%s\n' "${hits[0]}"
      return 0
    fi
    echo "task-done.sh: plan dir has no 00-master-plan.md and is ambiguous: $arg" >&2
    return 1
  fi
  # Bare number (or short token): search plans/** for matching path components
  if [[ "$arg" =~ ^[0-9]+([A-Za-z0-9._-]*)$ ]] || [[ "$arg" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
    local candidates=()
    if [ -d plans ]; then
      while IFS= read -r line; do
        [ -n "$line" ] && candidates+=("$line")
      done < <(
        find plans -type f \( -name '00-master-plan.md' -o -name '*.md' \) 2>/dev/null \
          | grep -E "/${arg}(-|/|\$)|/${arg}[^/]*/00-master-plan\.md|/${arg}\.md$" \
          | grep -E '00-master-plan\.md$|/[0-9]{4}-[0-9]{2}-[0-9]{2}-.*\.md$' \
          | sort -u
      )
      # Prefer exact dir name matches like plans/**/50-*/00-master-plan.md
      local refined=()
      for c in "${candidates[@]+"${candidates[@]}"}"; do
        case "$c" in
          */"${arg}"/*|*/"${arg}"-*/00-master-plan.md|*/"${arg}"/00-master-plan.md) refined+=("$c") ;;
        esac
      done
      if [ "${#refined[@]}" -gt 0 ]; then
        candidates=("${refined[@]}")
      fi
      # Further prefer 00-master-plan.md only
      local masters=()
      for c in "${candidates[@]+"${candidates[@]}"}"; do
        case "$c" in
          */00-master-plan.md) masters+=("$c") ;;
        esac
      done
      if [ "${#masters[@]}" -gt 0 ]; then
        candidates=("${masters[@]}")
      fi
    fi
    if [ "${#candidates[@]}" -eq 0 ]; then
      echo "task-done.sh: no plan matches bare id '$arg'" >&2
      return 1
    fi
    if [ "${#candidates[@]}" -gt 1 ]; then
      echo "task-done.sh: bare id '$arg' matches ${#candidates[@]} plans — list candidates, touch nothing:" >&2
      for c in "${candidates[@]}"; do echo "  $c" >&2; done
      return 1
    fi
    printf '%s\n' "${candidates[0]}"
    return 0
  fi
  echo "task-done.sh: plan not found: $arg" >&2
  return 1
}

PLAN="$(resolve_plan "$PLAN_ARG")" || exit 1
PLAN="$(python3 -c 'import os,sys; print(os.path.normpath(sys.argv[1]))' "$PLAN")"
[ -f "$PLAN" ] || { echo "task-done.sh: plan file missing: $PLAN" >&2; exit 1; }

LOCK="${PLAN}.task-lock"
# Ensure sidecar exists so flock has a stable path/inode across renames of the plan.
: >>"$LOCK"

# Normalize handle: strip optional backticks, require T…
norm_handle() {
  local h="$1"
  h="${h#\`}"
  h="${h%\`}"
  printf '%s\n' "$h"
}

TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
# Repo-relative plan form for the event
PLAN_REL="$(python3 -c '
import os, sys
p = os.path.normpath(sys.argv[1]).replace(os.sep, "/")
if "plans/" in p:
    print(p[p.index("plans/"):])
else:
    print(p)
' "$PLAN")"

# Python RMW under flock — one invocation for all handles so the lock is held once.
# Exit codes from python: 0 = all ok (incl. no-op done), 1 = at least one unknown/refused
export TASK_DONE_PLAN="$PLAN"
export TASK_DONE_HUMAN="$HUMAN"
export TASK_DONE_FORCE="$FORCE"
export TASK_DONE_BY="$BY"
export TASK_DONE_TIME="$TIME"
export TASK_DONE_PLAN_REL="$PLAN_REL"
export TASK_DONE_HANDLES="$(printf '%s\n' "${HANDLES[@]}")"
export TASK_DONE_STATE_APPEND="$SCRIPT_DIR/state-append.sh"

# flock the SIDECAR for the entire RMW
(
  flock -x 200
  python3 - <<'PY'
import json, os, re, sys, tempfile

plan = os.environ["TASK_DONE_PLAN"]
human = os.environ.get("TASK_DONE_HUMAN", "0") == "1"
force = os.environ.get("TASK_DONE_FORCE", "0") == "1"
by = os.environ.get("TASK_DONE_BY", "conductor")
time_s = os.environ.get("TASK_DONE_TIME", "")
plan_rel = os.environ.get("TASK_DONE_PLAN_REL", plan)
handles_raw = os.environ.get("TASK_DONE_HANDLES", "").splitlines()
state_append = os.environ.get("TASK_DONE_STATE_APPEND", "state-append.sh")

def norm(h: str) -> str:
    h = h.strip()
    if h.startswith("`") and h.endswith("`"):
        h = h[1:-1]
    return h

handles = [norm(h) for h in handles_raw if h.strip()]
HANDLE_PAT = re.compile(r"`?(T[A-Za-z0-9]+\.\d+)`?")

# Mirror on-run-complete.sh human-gate forms
tag_re = re.compile(r"(by\s+eye|by\s+hand|gpu|manual)", re.I)
sec_re = re.compile(r"(acceptance|by\s+eye|by\s+hand|gpu|manual|human[-\s]*verify)", re.I)
# Checkbox line with optional handle after mark
box_re = re.compile(r"^(\s*[-*]\s+)\[([ xX])\](\s*)(.*)$")

with open(plan, "r", encoding="utf-8", newline="") as f:
    text = f.read()
# Preserve whether original ended with newline
ends_nl = text.endswith("\n")
lines = text.split("\n")

# Precompute section-heading human regions: track current heading
def is_human_box(line_idx: int, rest: str, lines=lines) -> bool:
    if tag_re.search(rest):
        return True
    # walk up for nearest markdown heading
    for j in range(line_idx, -1, -1):
        s = lines[j].lstrip()
        if s.startswith("#"):
            # strip leading # and spaces
            title = s.lstrip("#").strip()
            return bool(sec_re.search(title))
    return False

def find_handle_line(handle: str):
    """Return (idx, mark, groups) or None. groups = (prefix, mark, gap, rest)."""
    target = handle if handle.startswith("T") else f"T{handle}"
    # Accept T… with or without backtick form in the line
    for i, line in enumerate(lines):
        m = box_re.match(line)
        if not m:
            continue
        rest = m.group(4)
        # look for `T…` or bare T… as a token at start / anywhere after mark
        for hm in re.finditer(r"`?(T[A-Za-z0-9]+\.\d+)`?", rest):
            if hm.group(1) == target or hm.group(0).strip("`") == target:
                return i, m.group(2), m
    return None

any_error = False
flipped = []  # handles that actually changed [ ]→[x]

for h in handles:
    if not re.fullmatch(r"T[A-Za-z0-9]+\.\d+", h):
        print(f"task-done: invalid handle format: {h!r} (expected T<phase>.<seq>)", file=sys.stderr)
        any_error = True
        continue
    found = find_handle_line(h)
    if found is None:
        print(f"task-done: unknown handle {h} in {plan_rel}", file=sys.stderr)
        any_error = True
        continue
    idx, mark, m = found
    prefix, gap, rest = m.group(1), m.group(3), m.group(4)

    if is_human_box(idx, rest) and not human and not force:
        print(
            f"task-done: refuse human-tagged box {h} (pass --human to flip): {lines[idx].strip()[:100]}",
            file=sys.stderr,
        )
        any_error = True
        continue

    if mark.lower() == "x":
        # already done — no-op
        print(f"task-done: {h} already [x] (no-op)")
        continue

    # Flip [ ] → [x]; preserve everything else (CLAIMED prose, handle, rest)
    lines[idx] = f"{prefix}[x]{gap}{rest}"
    flipped.append(h)
    print(f"task-done: flipped {h} → [x]")

new_text = "\n".join(lines)
if ends_nl and not new_text.endswith("\n"):
    new_text += "\n"

if flipped:
    # atomic write
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

    # Append events AFTER flip lands
    import subprocess
    for h in flipped:
        event = {
            "event": "task_done",
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
            print(f"task-done: WARN state-append failed for {h} (flip already landed)", file=sys.stderr)

sys.exit(1 if any_error else 0)
PY
) 200>"$LOCK"
exit $?
