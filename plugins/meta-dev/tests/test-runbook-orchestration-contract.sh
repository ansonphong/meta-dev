#!/usr/bin/env bash
# Focused regression guard: /runbook execute is a thin campaign conductor
# that farms host-native member conductors in file-disjoint waves (cap 3).
set -uo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0
ok() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

echo "=== Runbook orchestration: host-native member-conductor contract ==="
if DETAIL="$(python3 - "$PLUGIN_ROOT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
required = {
    "commands/runbook.md": [
        "campaign conductor",
        "do **not** implement member tasks",
        "Cap **3**",
        "file-disjoint",
        "spawn_subagent",
        "member conductor",
        "--serial",
        "do not send a slash command",
        "commit --only",
        "runbook-render.py",
        "TaskCreate",
        "CONTEXT_VERDICT",
    ],
    "workflow-skills/runbook-orchestration/SKILL.md": [
        "campaign conductor",
        "do not implement member tasks",
        "Cap **3**",
        "file-disjoint",
        "spawn_subagent",
        "member conductor",
        "--serial",
        "do not send a slash command",
        "commit --only",
        "runbook-render.py",
        "TaskCreate",
        "CONTEXT_VERDICT=OVER",
        "flatten a campaign into a host-specific workflow script",
    ],
    "references/runbook-view.md": [
        "member conductors",
        "Cap **3**",
        "direct task",
    ],
    "references/execute-briefs.md": [
        "Campaign member conductor",
        "Never \"run `/meta-execute`\"",
        "Cap **3** member conductors",
    ],
    "references/workflows/protocol.md": [
        "Campaign runbook",
        "member conductors",
        "Cap **3** in-flight members",
    ],
}
forbidden = {
    "commands/runbook.md": [
        "never write a file that is already dirty on the working tree",
        "Delegation (per CLAUDE.md ladder)",
        "Opus (the main thread)",
    ],
    "workflow-skills/runbook-orchestration/SKILL.md": [
        "never write a file that is already dirty on the working tree",
        "Authoring a runbook's narrative + topo-sort + wave strategy is campaign-design judgment → **Opus**",
        "Does not relax the GLM ~3-request API cap",
    ],
}

issues = []
for rel, needles in required.items():
    text = (root / rel).read_text(encoding="utf-8")
    missing = [n for n in needles if n not in text]
    if missing:
        issues.append(f"{rel}: missing {missing!r}")

for rel, needles in forbidden.items():
    text = (root / rel).read_text(encoding="utf-8")
    present = [n for n in needles if n in text]
    if present:
        issues.append(f"{rel}: forbidden leftover {present!r}")

if issues:
    print("\n".join(issues))
    sys.exit(1)
print("all required markers present; forbidden leftovers absent")
PY
)"; then
  ok "required markers"
else
  bad "required markers"
  echo "$DETAIL"
fi

# Plugin manifests stay in lockstep.
if python3 - "$PLUGIN_ROOT" <<'PY'
from pathlib import Path
import json
import sys
root = Path(sys.argv[1])
a = json.loads((root / ".claude-plugin/plugin.json").read_text())
b = json.loads((root / ".codex-plugin/plugin.json").read_text())
if a["version"] != b["version"]:
    print(f"plugin version drift: claude={a['version']} codex={b['version']}")
    sys.exit(1)
print(a["version"])
PY
then
  ok "plugin.json versions match"
else
  bad "plugin.json versions match"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [ "$FAIL" -eq 0 ]; then
  echo "ALL CHECKS PASSED"
  exit 0
fi
echo "SOME CHECKS FAILED"
exit 1
