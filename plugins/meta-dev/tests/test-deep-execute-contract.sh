#!/usr/bin/env bash
# Focused regression guard: /deep-execute defaults to V4.1 Flash
# (deepseek-v4-flash); --pro upgrades; --vision pins deepseek-v4-flash-vision-exp.
set -uo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0
ok() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

echo "=== Deep-execute: Flash default + --pro/--vision contract ==="
if DETAIL="$(python3 - "$PLUGIN_ROOT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
required = {
    "commands/deep-execute.md": [
        "default deepseek-v4-flash (V4.1 Flash as of 2026-09-10)",
        "**Default model: `deepseek-v4-flash`**",
        "Flash-first",
        "Conductor judgment",
        "--flash",
        "--pro",
        "--vision",
        "deepseek-v4-flash-vision-exp",
        "Unsure and not visual → Flash",
    ],
    "scripts/claude-headless-exec": [
        'BACKEND_SONNET_MODEL[deep]="deepseek-v4-flash"',
        'BACKEND_HAIKU_MODEL[deep]="deepseek-v4-flash"',
        "--flash",
        "--pro",
        "--vision",
        "FLASH_FLAG",
        "VISION_FLAG",
        'MODEL="deepseek-v4-flash"',
        'MODEL="deepseek-v4-pro"',
        'MODEL="deepseek-v4-flash-vision-exp"',
    ],
    "workflow-skills/headless-dispatch/SKILL.md": [
        "`deepseek-v4-flash` (default, V4.1 Flash; `--pro` → `deepseek-v4-pro`; `--vision` → `deepseek-v4-flash-vision-exp`)",
    ],
}
forbidden = {
    "commands/deep-execute.md": [
        "**Default model: `deepseek-v4-pro`**",
        "Pro-first",
        "default: **`pro`**",
        "default model = deepseek-v4-pro",
        "Unsure and not visual → Pro",
    ],
    "scripts/claude-headless-exec": [
        'BACKEND_SONNET_MODEL[deep]="deepseek-v4-pro"',
    ],
}

failed = []
for rel, needles in required.items():
    text = (root / rel).read_text(encoding="utf-8")
    missing = [n for n in needles if n not in text]
    if missing:
        failed.append(f"{rel}: missing {missing!r}")
for rel, needles in forbidden.items():
    text = (root / rel).read_text(encoding="utf-8")
    present = [n for n in needles if n in text]
    if present:
        failed.append(f"{rel}: stale {present!r}")

if failed:
    print("\n".join(failed))
    sys.exit(1)
print("all required markers present; stale Pro-default gone")
PY
)"; then
  ok "required markers"
else
  bad "required markers"
  echo "$DETAIL"
fi

# --help must advertise Flash as the deep default.
if HELP="$("$PLUGIN_ROOT/scripts/claude-headless-exec" --help 2>&1)"; then
  if echo "$HELP" | grep -q 'deep   → deepseek-v4-flash'; then
    ok "help default is deepseek-v4-flash"
  else
    bad "help default is deepseek-v4-flash"
    echo "$HELP" | grep -n 'deep   →' || true
  fi
  if echo "$HELP" | grep -q -- '--flash'; then
    ok "help lists --flash"
  else
    bad "help lists --flash"
  fi
  if echo "$HELP" | grep -q -- '--vision'; then
    ok "help lists --vision"
  else
    bad "help lists --vision"
  fi
  if echo "$HELP" | grep -q 'deepseek-v4-flash-vision-exp'; then
    ok "help names vision model id"
  else
    bad "help names vision model id"
  fi
else
  bad "claude-headless-exec --help"
fi

# Parse-only: exclusive flags abort before a worker spawn.
CONFLICT="$("$PLUGIN_ROOT/scripts/claude-headless-exec" --backend deep --flash --pro -- "nope" 2>&1 || true)"
if echo "$CONFLICT" | grep -q 'cannot be combined'; then
  ok "--flash + --pro conflicts"
else
  bad "--flash + --pro conflicts"
  echo "$CONFLICT" | tail -n 20
fi
VISION_CONFLICT="$("$PLUGIN_ROOT/scripts/claude-headless-exec" --backend deep --vision --flash -- "nope" 2>&1 || true)"
if echo "$VISION_CONFLICT" | grep -q 'cannot be combined'; then
  ok "--vision + --flash conflicts"
else
  bad "--vision + --flash conflicts"
  echo "$VISION_CONFLICT" | tail -n 20
fi

echo
echo "=== $PASS passed, $FAIL failed ==="
exit "$FAIL"
