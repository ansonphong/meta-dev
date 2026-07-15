#!/usr/bin/env bash
set -euo pipefail
# PostToolUse hook: fires after Edit/Write tool calls.
# Matcher: Edit|Write in plugin.json.
# Input: JSON payload on stdin — { tool_name, tool_input:{file_path,...}, ... }
#
# Validates a plan file's YAML frontmatter on edit. WARNS only — this hook
# must NEVER block an edit, so it ALWAYS exits 0. Non-plan paths, the sensitive
# exec-order file, and plain docs (no frontmatter) are passed through silently.

PAYLOAD=$(cat)
PATH_EDITED=$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.file_path // ""' 2>/dev/null || echo "")
[ -z "$PATH_EDITED" ] && exit 0

# Normalize backslashes and reduce to a plans/-relative tail for matching.
NORM=$(printf '%s' "$PATH_EDITED" | tr '\\' '/')

# Only validate *.md under plans/.
case "$NORM" in
  */plans/*.md|plans/*.md) : ;;
  *) exit 0 ;;
esac

# Never validate the sensitive file.
case "$NORM" in
  *plans/exec-order-2026-06-26.md) exit 0 ;;
esac

[ -f "$PATH_EDITED" ] || exit 0

# Inspect the leading frontmatter block + validate required keys.
WARN=$(python3 - "$PATH_EDITED" <<'PY' 2>/dev/null || true
import re, sys

path = sys.argv[1]
try:
    with open(path, encoding="utf-8", errors="ignore") as fh:
        text = fh.read()
except Exception:
    sys.exit(0)

lines = text.split("\n")
i = 0
while i < len(lines) and lines[i].strip() == "":
    i += 1
if i >= len(lines) or lines[i].strip() != "---":
    sys.exit(0)  # no frontmatter — plain doc, silent

start = i + 1
end = None
for j in range(start, len(lines)):
    if lines[j].strip() == "---":
        end = j
        break
if end is None:
    print("unterminated frontmatter block (no closing '---')")
    sys.exit(0)

data = {}
for line in lines[start:end]:
    s = line.strip()
    if not s or s.startswith("#") or ":" not in s:
        continue
    k, _, v = s.partition(":")
    k = k.strip()
    v = v.split(" #")[0].strip()
    if (len(v) >= 2 and v[0] == v[-1] and v[0] in "'\""):
        v = v[1:-1]
    if k:
        data[k] = v

problems = []
for key in ("status", "stage", "repo"):
    if key not in data:
        problems.append(f"missing required key '{key}'")

if "status" in data and data["status"] not in ("draft", "active", "blocked", "done"):
    problems.append(f"status='{data['status']}' (must be draft|active|blocked|done)")

stage_n = None
if "stage" in data:
    try:
        stage_n = int(str(data["stage"]).strip())
        if not (1 <= stage_n <= 6):
            problems.append(f"stage={data['stage']} (must be 1-6)")
    except (ValueError, TypeError):
        problems.append(f"stage='{data['stage']}' (must be an int 1-6)")

# Stage ≥ 3: warn if context:/docs: missing (value must be a path list or literal none).
# Warn-only — never blocks (this hook always exits 0).
if stage_n is not None and stage_n >= 3:
    for key in ("context", "docs"):
        if key not in data:
            problems.append(
                f"missing '{key}:' (stage>={stage_n}: declare path list or literal 'none')"
            )

if problems:
    print("; ".join(problems))
PY
)

if [ -n "$WARN" ]; then
  echo "meta-dev WARNING: plan frontmatter invalid in $PATH_EDITED — $WARN" >&2
fi

exit 0
