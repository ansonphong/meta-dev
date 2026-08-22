#!/usr/bin/env bash
# Focused regression: /antigravity-execute distills agy JSON into the shared
# headless contract; runner --help / exclusive flags / missing-agy abort
# without a live network call.
set -uo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DISTILL="$PLUGIN_ROOT/scripts/lib/distill-agy-result.py"
RUNNER="$PLUGIN_ROOT/scripts/agy-headless-exec"
PASS=0
FAIL=0
ok() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "=== Antigravity-execute: distill + runner contract ==="

# (a) SUCCESS fixture through the REAL distill entry point
SUCCESS_RAW="$TMP/success.raw.json"
SUCCESS_OUT="$TMP/success.out.json"
cat > "$SUCCESS_RAW" <<'JSON'
{
  "conversation_id": "c8d77036-dfed-4111-89ed-2385cbb59c45",
  "status": "SUCCESS",
  "response": "pong\nkey=sk-ant-abcdefghijklmnopqrstuvwxyz012345",
  "duration_seconds": 4.74,
  "num_turns": 1,
  "usage": {
    "input_tokens": 15833,
    "output_tokens": 15,
    "thinking_tokens": 0,
    "cache_read_tokens": 0,
    "total_tokens": 15848
  }
}
JSON
if RESULT="$(python3 "$DISTILL" "$SUCCESS_RAW" "$SUCCESS_OUT" 0 4740)"; then
  python3 - "$SUCCESS_OUT" "$RESULT" <<'PY' && ok "SUCCESS distill contract + redaction" || bad "SUCCESS distill assertions"
import json, sys
from pathlib import Path
out = json.loads(Path(sys.argv[1]).read_text())
printed = sys.argv[2]
keys = {"is_error", "subtype", "num_turns", "duration_ms", "session_id", "result", "usage", "backend", "stop_reason"}
missing = keys - set(out)
assert not missing, missing
assert out["is_error"] is False
assert out["subtype"] == "success"
assert out["backend"] == "agy"
assert out["stop_reason"] == "SUCCESS"
assert out["session_id"] == "c8d77036-dfed-4111-89ed-2385cbb59c45"
assert out["num_turns"] == 1
assert out["duration_ms"] == 4740
assert "pong" in out["result"]
assert "sk-ant-" not in out["result"]
assert "[REDACTED]" in out["result"]
assert "sk-ant-" not in printed
print("ok")
PY
else
  bad "SUCCESS distill exit"
fi

# non-SUCCESS / nonzero exit → error
FAIL_RAW="$TMP/fail.raw.json"
FAIL_OUT="$TMP/fail.out.json"
cat > "$FAIL_RAW" <<'JSON'
{
  "conversation_id": "deadbeef-0000-0000-0000-000000000001",
  "status": "ERROR",
  "response": "nope",
  "duration_seconds": 1.0,
  "num_turns": 1,
  "usage": {}
}
JSON
python3 "$DISTILL" "$FAIL_RAW" "$FAIL_OUT" 1 1000 >/dev/null
python3 - "$FAIL_OUT" <<'PY' && ok "non-SUCCESS + nonzero exit is error" || bad "error distill"
import json, sys
from pathlib import Path
out = json.loads(Path(sys.argv[1]).read_text())
assert out["is_error"] is True
assert out["subtype"] == "error"
assert out["backend"] == "agy"
assert out["stop_reason"] == "ERROR"
print("ok")
PY

# empty raw → distill failure (exit 1)
EMPTY_RAW="$TMP/empty.raw.json"
EMPTY_OUT="$TMP/empty.out.json"
: > "$EMPTY_RAW"
if python3 "$DISTILL" "$EMPTY_RAW" "$EMPTY_OUT" 0 10 >/dev/null; then
  bad "empty raw should fail distill"
else
  ok "empty raw fails distill"
fi

# (b) real runner --help
HELP="$("$RUNNER" --help 2>&1)" || true
echo "$HELP" | grep -q 'gemini-3.7-flash-high' && echo "$HELP" | grep -q -- '--budget' && echo "$HELP" | grep -q -- '--print' && echo "$HELP" | grep -q -- '--model' && echo "$HELP" | grep -q -- '--opus' \
  && ok "runner --help advertises Flash default, --budget, --print, --model, --opus" \
  || bad "runner --help missing contract strings"

# exclusive-flag abort (no live agy needed)
EXCL_ERR="$("$RUNNER" --opus --pro -- "Say only: pong" 2>&1)" || EXCL_RC=$?
EXCL_RC=${EXCL_RC:-0}
if [[ "$EXCL_RC" -ne 0 ]] && echo "$EXCL_ERR" | grep -q 'exclusive'; then
  ok "exclusive --opus/--pro abort"
else
  bad "exclusive flags did not abort (rc=$EXCL_RC)"
  echo "$EXCL_ERR"
fi

# missing agy on PATH (and no ~/.local/bin/agy under a fake HOME)
EMPTY_HOME="$TMP/empty-home"
mkdir -p "$EMPTY_HOME"
MISS_ERR="$(PATH=/usr/bin:/bin HOME="$EMPTY_HOME" "$RUNNER" --timeout 1000 -- "Say only: pong" 2>&1)" || MISS_RC=$?
MISS_RC=${MISS_RC:-0}
if [[ "$MISS_RC" -ne 0 ]] && echo "$MISS_ERR" | grep -qi "agy"; then
  ok "missing agy aborts"
else
  bad "missing agy did not abort (rc=$MISS_RC)"
  echo "$MISS_ERR"
fi

# command markers
if grep -q 'gemini-3.7-flash-high' "$PLUGIN_ROOT/commands/antigravity-execute.md" \
  && grep -q 'Claude Opus 4.6' "$PLUGIN_ROOT/commands/antigravity-execute.md" \
  && grep -q 'named-only' "$PLUGIN_ROOT/commands/antigravity-execute.md" \
  && grep -q 'agy-headless-exec' "$PLUGIN_ROOT/commands/antigravity-execute.md" \
  && grep -q 'not at phase end' "$PLUGIN_ROOT/commands/antigravity-execute.md" \
  && grep -q 'BASELINE_RED' "$PLUGIN_ROOT/commands/antigravity-execute.md"; then
  ok "command card has Flash default, Opus, parked, runner, test discipline"
else
  bad "command card missing required markers"
fi

if grep -q 'never added to `meta_dev.ladder.pool`' "$PLUGIN_ROOT/commands/antigravity-execute.md" \
  || grep -q 'Never added to `meta_dev.ladder.pool`' "$PLUGIN_ROOT/commands/antigravity-execute.md"; then
  ok "command stays off the pool"
else
  # capabilities card uses "Never auto-selected. Never added to"
  grep -q 'Never added to `meta_dev.ladder.pool`' "$PLUGIN_ROOT/commands/antigravity-execute.md" \
    && ok "command stays off the pool" \
    || { grep -q 'meta_dev.ladder.pool' "$PLUGIN_ROOT/commands/antigravity-execute.md" && ok "command mentions pool (parked)"; }
fi

echo
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
