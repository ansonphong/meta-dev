#!/usr/bin/env bash
# Focused regression guard for /meta-task-agent session-mode dispatch.
set -uo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0
ok() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

echo "=== Task-agent: session + async spawn contract ==="
if DETAIL="$(python3 - "$PLUGIN_ROOT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
required = {
    "commands/meta-task-agent.md": [
        "task-agent session",
        "Every later user message is a **task**",
        "spawn a fresh host-native subagent",
        "Do not wait for the worker",
        "typed prompt **is the go**",
        "Cap **8** in-flight",
        "Unknown file set → **still dispatch**",
        "spawn_subagent",
        "/meta-task-agent --end",
        "This is **not** `/meta-execute`",
    ],
    "commands/task-agent.md": [
        "Execute /meta-task-agent $ARGUMENTS",
    ],
    "references/workflows/routes.json": [
        "commands/meta-task-agent.md",
        '"meta-task-agent": "execute.task-agent"',
        '"task-agent": "execute.task-agent"',
    ],
}

failed = []
for rel, needles in required.items():
    text = (root / rel).read_text(encoding="utf-8")
    missing = [n for n in needles if n not in text]
    if missing:
        failed.append(f"{rel}: missing {missing!r}")

if failed:
    print("\n".join(failed))
    sys.exit(1)
print("all required markers present")
PY
)"; then
  ok "required markers"
else
  bad "required markers"
  echo "$DETAIL"
fi

# Alias must be a pure redirect so Codex treats it as non-canonical.
if python3 - "$PLUGIN_ROOT" <<'PY'
from pathlib import Path
import re
import sys
root = Path(sys.argv[1])
text = (root / "commands/task-agent.md").read_text(encoding="utf-8")
body = text.split("---", 2)[2].strip()
if not re.fullmatch(r"Execute /[a-z0-9-]+ \$ARGUMENTS", body):
    print(f"alias body is not a pure redirect: {body!r}")
    sys.exit(1)
PY
then
  ok "task-agent alias is a pure redirect"
else
  bad "task-agent alias is a pure redirect"
fi

echo
echo "=== $PASS passed, $FAIL failed ==="
exit "$FAIL"
