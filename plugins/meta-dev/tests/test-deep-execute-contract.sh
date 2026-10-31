#!/usr/bin/env bash
# Focused contract: Flash 1017 + Max defaults; explicit overrides survive.
# Worker is a local stub: no live model, API call, or credentials required.
set -uo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0
ok() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

PROOF_PARENT="${META_DEV_PROOF_DIR:-${TMPDIR:-/tmp}}"
mkdir -p "$PROOF_PARENT"
PROOF_DIR="$(mktemp -d "$PROOF_PARENT/deep-max.XXXXXXXX")"
mkdir -p "$PROOF_DIR/bin"
cat > "$PROOF_DIR/bin/claude" <<'STUB'
#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
if "--model" in args:
    settings = json.loads(Path(args[args.index("--settings") + 1]).read_text())
    capture = {
        "model": args[args.index("--model") + 1],
        "effort": os.environ.get("CLAUDE_CODE_EFFORT_LEVEL"),
        "thinking": settings.get("alwaysThinkingEnabled"),
        "thinking_tokens": os.environ.get("MAX_THINKING_TOKENS"),
        "nested": [os.environ.get(key) for key in (
            "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL")],
    }
    Path(os.environ["DEEP_STUB_CAPTURE"]).write_text(json.dumps(capture))
print(json.dumps({"type": "result", "is_error": False, "subtype": "success",
                  "result": "stub ok", "num_turns": 1, "session_id": "stub"}))
STUB
chmod +x "$PROOF_DIR/bin/claude"
export PATH="$PROOF_DIR/bin:$PATH"

echo "=== Deep-execute: Flash 1017 + Max reasoning contract ==="
if DETAIL="$(python3 - "$PLUGIN_ROOT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
required = {
    "commands/deep-execute.md": [
        "default deepseek-flash (V4.1 Flash 1017)",
        "**Default model: `deepseek-flash`; default reasoning: `max`.**",
        "Flash-first",
        "Conductor judgment",
        "--flash",
        "--pro",
        "--vision",
        "deepseek-v4-flash-vision-exp",
        "CLAUDE_CODE_EFFORT_LEVEL=max",
        "output_config",
        "--effort",
    ],
    "scripts/claude-headless-exec": [
        'BACKEND_SONNET_MODEL[deep]="deepseek-flash"',
        'BACKEND_HAIKU_MODEL[deep]="deepseek-flash"',
        "--flash",
        "--pro",
        "--vision",
        "FLASH_FLAG",
        "VISION_FLAG",
        'MODEL="deepseek-flash"',
        'BACKEND_EFFORT[deep]="max"',
        'MODEL="deepseek-v4-pro"',
        'settings["alwaysThinkingEnabled"] = True',
    ],
    "workflow-skills/headless-dispatch/SKILL.md": [
        "`deepseek-flash` (V4.1 Flash 1017, Max reasoning by default; `--pro` → `deepseek-v4-pro`; `--vision` → same multimodal Flash)",
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
  if echo "$HELP" | grep -q 'deep   → deepseek-flash'; then
    ok "help default is deepseek-flash"
  else
    bad "help default is deepseek-flash"
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
  if echo "$HELP" | grep -q 'effort max'; then
    ok "help names max effort default"
  else
    bad "help names max effort default"
  fi
else
  bad "claude-headless-exec --help"
fi

# Parse-only: exclusive flags abort before a worker spawn.
CONFLICT="$(DEEPSEEK_API_KEY=test-only "$PLUGIN_ROOT/scripts/claude-headless-exec" --backend deep --flash --pro -- "nope" 2>&1 || true)"
if echo "$CONFLICT" | grep -q 'cannot be combined'; then
  ok "--flash + --pro conflicts"
else
  bad "--flash + --pro conflicts"
  echo "$CONFLICT" | tail -n 20
fi
VISION_CONFLICT="$(DEEPSEEK_API_KEY=test-only "$PLUGIN_ROOT/scripts/claude-headless-exec" --backend deep --vision --flash -- "nope" 2>&1 || true)"
if echo "$VISION_CONFLICT" | grep -q 'cannot be combined'; then
  ok "--vision + --flash conflicts"
else
  bad "--vision + --flash conflicts"
  echo "$VISION_CONFLICT" | tail -n 20
fi

# Exercise the real launch boundary with a stub, including hostile ambient
# settings, budget lowering, explicit efforts, tiers and exact model overrides.
run_case() {
  local name="$1" expected_model="$2" expected_effort="$3"
  shift 3
  if DEEPSEEK_API_KEY=test-only CLAUDE_CODE_EFFORT_LEVEL=low MAX_THINKING_TOKENS=0 \
      DEEP_STUB_CAPTURE="$PROOF_DIR/$name.capture.json" STALL_SECS=0 \
      "$PLUGIN_ROOT/scripts/claude-headless-exec" --backend deep --readonly \
      --output-file "$PROOF_DIR/$name.json" "$@" -- "Return ok" \
      >"$PROOF_DIR/$name.stdout" 2>"$PROOF_DIR/$name.stderr" \
    && python3 - "$PROOF_DIR/$name.capture.json" "$expected_model" "$expected_effort" <<'PY'
import json, sys
from pathlib import Path
c = json.loads(Path(sys.argv[1]).read_text())
assert c["model"] == sys.argv[2], c
assert c["effort"] == sys.argv[3], c
assert c["thinking"] is True, c
assert c["thinking_tokens"] is None, c
assert c["nested"] == ["deepseek-flash"] * 4, c
PY
  then ok "$name launch environment/settings"
  else bad "$name launch environment/settings (see $PROOF_DIR)"
  fi
}
run_case default deepseek-flash max
run_case low-budget deepseek-flash max --budget low
run_case explicit-max deepseek-flash max --effort max
run_case explicit-high deepseek-flash high --effort high
run_case explicit-low deepseek-flash low --effort low --budget high
run_case pro deepseek-v4-pro max --pro
run_case vision deepseek-flash max --vision
run_case exact-model deepseek-v4-flash max --vision --model deepseek-v4-flash

echo "Proof artifacts retained: $PROOF_DIR"

echo
echo "=== $PASS passed, $FAIL failed ==="
exit "$FAIL"
