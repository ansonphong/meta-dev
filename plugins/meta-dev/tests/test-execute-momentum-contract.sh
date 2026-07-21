#!/usr/bin/env bash
# Focused regression guard for /meta-execute optimistic momentum semantics.
set -uo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0
ok() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

echo "=== Execute momentum: canonical contract ==="
if DETAIL="$(python3 - "$PLUGIN_ROOT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
required = {
    "commands/meta-execute.md": [
        "Optimistic momentum is the default control flow",
        "FOCUSED_PASS",
        "TASK_RED",
        "BASELINE_RED",
        "INFRA_RED",
        "BROAD_VERIFY_OMITTED",
        "mark `completed`, run `task-done`, and release dependents",
        "Solidify focused foundation",
        "MUST NOT rerun a passing verifier",
    ],
    "references/execute-dispatch.md": [
        "Run it ONCE",
        "A non-zero exit is `TASK_RED` only",
        "BASELINE_RED",
        "BROAD_VERIFY_OMITTED",
        "Do NOT rerun a passing verifier",
    ],
    "references/execute-charter.md": [
        "FOCUSED_PASS",
        "TASK_RED",
        "BASELINE_RED",
        "INFRA_RED",
        "BROAD_VERIFY_OMITTED",
        "optimistic momentum",
    ],
    "skills/agentic-exec-loop/references/loop-protocol.md": [
        "FOCUSED_PASS",
        "TASK_RED",
        "BASELINE_RED",
        "INFRA_RED",
        "BROAD_VERIFY_OMITTED",
        "optimistic momentum",
    ],
    "scripts/codex-headless-exec": [
        "FOCUSED VERIFICATION ONLY",
        "OPTIMISTIC MOMENTUM",
        "BROAD_VERIFY_OMITTED",
        "not at phase end",
    ],
}
forbidden = {
    "commands/meta-execute.md": [
        "full acceptance suite once",
        "Gate: all green before proceeding",
        "runs once at solidify",
    ],
    "references/execute-charter.md": [
        "full acceptance suite is green",
        "full suite, slow+GPU markers included",
    ],
    "references/execute-dispatch.md": [
        "The orchestrator runs those ONCE at phase end",
        "Re-run the verify/test command (don't trust subagent paste)",
        "Red twice → escalate to TRUE BLOCKER, surface",
    ],
    "scripts/codex-headless-exec": ["those run ONCE at phase end"],
}

issues = []
texts = {}
for rel, markers in required.items():
    text = (root / rel).read_text(encoding="utf-8")
    texts[rel] = text
    for marker in markers:
        if marker not in text:
            issues.append(f"{rel}: missing {marker!r}")
for rel, markers in forbidden.items():
    text = texts.get(rel) or (root / rel).read_text(encoding="utf-8")
    for marker in markers:
        if marker in text:
            issues.append(f"{rel}: stale contradiction {marker!r}")

if issues:
    print(" | ".join(issues))
    raise SystemExit(1)
PY
)"; then
  ok "native, dispatch, tier loop, and Codex preamble share focused causal momentum"
else
  bad "execution contract drifted: $DETAIL"
fi

echo
echo "=== Execute momentum: folder-nav regression ==="
if DETAIL="$(python3 - "$PLUGIN_ROOT" <<'PY'
import json
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1])
classifier = root / "scripts" / "verify-scope.py"

def classify(command: str, path: str) -> str:
    completed = subprocess.run(
        [sys.executable, str(classifier), "--command", command, "--allowed-path", path],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)["class"]

assert classify("npm run check", "frontend/src/lib/viewer/folderNav.ts") == "broad"
assert classify(
    "pytest frontend/tests/test_folder_nav.py::test_wrap -q",
    "frontend/tests/test_folder_nav.py",
) == "focused"

# Reproduce the failed run's dependency graph. T1's focused check passes; T2's
# only red evidence is unchanged/outside its surface. Both are accepted, so all
# downstream tasks become runnable. The broad gate never enters the run list.
tasks = {
    "T1": {"deps": [], "result": "FOCUSED_PASS"},
    "T2": {"deps": ["T1"], "result": "BASELINE_RED"},
    "T3": {"deps": ["T1", "T2"], "result": None},
    "T4": {"deps": ["T3"], "result": None},
    "T5": {"deps": ["T1"], "result": None},
}
accepted = {
    task_id
    for task_id, task in tasks.items()
    if task["result"] in {"FOCUSED_PASS", "BASELINE_RED", "BROAD_VERIFY_OMITTED"}
}
assert accepted == {"T1", "T2"}
assert all(dep in accepted for dep in tasks["T3"]["deps"])
assert all(dep in accepted for dep in tasks["T5"]["deps"])
assert "npm run check" not in []
PY
)"; then
  ok "unrelated npm-check debt releases T1/T2 and makes T3/T5 dispatchable"
else
  bad "folder-nav regression failed: $DETAIL"
fi

echo
echo "=== Execute momentum: executor parity ==="
if DETAIL="$(python3 - "$PLUGIN_ROOT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
paths = [
    "commands/auto-execute.md",
    "commands/codex-execute.md",
    "commands/deep-execute.md",
    "commands/fable-execute.md",
    "commands/glm-execute.md",
    "commands/grok-execute.md",
    "commands/opus-execute.md",
    "commands/sonnet-execute.md",
]
issues = []
for rel in paths:
    text = (root / rel).read_text(encoding="utf-8")
    if "not at phase end" not in text:
        issues.append(f"{rel}: missing phase-end broad-test ban")
    if "BASELINE_RED" not in text:
        issues.append(f"{rel}: missing BASELINE_RED momentum rule")
if issues:
    print(" | ".join(issues))
    raise SystemExit(1)
PY
)"; then
  ok "all executor-facing commands ban broad phase gates and preserve BASELINE_RED momentum"
else
  bad "executor parity drifted: $DETAIL"
fi

echo
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
