#!/usr/bin/env bash
# Focused regression: /cursor-execute distills Cursor JSON into the shared
# headless contract; runner --help / exclusive flags / missing-binary abort
# / --grok 4.6 xhigh resolve without a live billed cursor-agent -p call.
set -uo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DISTILL="$PLUGIN_ROOT/scripts/lib/distill-cursor-result.py"
RESOLVE="$PLUGIN_ROOT/scripts/lib/cursor-model-resolve.py"
RUNNER="$PLUGIN_ROOT/scripts/cursor-headless-exec"
CMD="$PLUGIN_ROOT/commands/cursor-execute.md"
PASS=0
FAIL=0
ok() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "=== Cursor-execute: distill + runner contract ==="

# (a) SUCCESS fixture through the REAL distill entry point
SUCCESS_RAW="$TMP/success.raw.json"
SUCCESS_OUT="$TMP/success.out.json"
cat > "$SUCCESS_RAW" <<'JSON'
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "duration_ms": 1234,
  "duration_api_ms": 1234,
  "result": "pong\nkey=sk-ant-abcdefghijklmnopqrstuvwxyz012345",
  "session_id": "c6b62c6f-7ead-4fd6-9922-e952131177ff",
  "request_id": "10e11780-df2f-45dc-a1ff-4540af32e9c0"
}
JSON
if RESULT="$(python3 "$DISTILL" "$SUCCESS_RAW" "$SUCCESS_OUT" 0 1234)"; then
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
assert out["backend"] == "cursor"
assert out["stop_reason"] == "success"
assert out["session_id"] == "c6b62c6f-7ead-4fd6-9922-e952131177ff"
assert out["duration_ms"] == 1234
assert "pong" in out["result"]
assert "sk-ant-" not in out["result"]
assert "[REDACTED]" in out["result"]
assert "sk-ant-" not in printed
assert out["result"]
print("ok")
PY
else
  bad "SUCCESS distill exit"
fi

# empty raw (Cursor failure: no JSON) → distill failure (exit 1)
EMPTY_RAW="$TMP/empty.raw.json"
EMPTY_OUT="$TMP/empty.out.json"
: > "$EMPTY_RAW"
if python3 "$DISTILL" "$EMPTY_RAW" "$EMPTY_OUT" 1 10 >/dev/null; then
  bad "empty raw should fail distill"
else
  python3 - "$EMPTY_OUT" <<'PY' && ok "empty/fail fixture is error + cursor backend" || bad "empty distill payload"
import json, sys
from pathlib import Path
out = json.loads(Path(sys.argv[1]).read_text())
assert out["is_error"] is True
assert out["subtype"] == "error"
assert out["backend"] == "cursor"
print("ok")
PY
fi

# fake cursor-agent: exercise the real runner without a billed call
EMPTY_HOME="$TMP/empty-home"; mkdir -p "$EMPTY_HOME"
FAKE_BIN="$TMP/fake-bin"; mkdir -p "$FAKE_BIN"
cat > "$FAKE_BIN/cursor-agent" <<'SH'
#!/usr/bin/env bash
if [[ "$1" == status ]]; then echo '{"isAuthenticated":true}'; exit 0; fi
printf '%s\n' "$*" > "${CURSOR_ARGS_LOG:?}"
printf '%s' '{"type":"result","subtype":"success","is_error":false,"result":"fake pong","session_id":"fake-session"}'
SH
chmod 700 "$FAKE_BIN/cursor-agent"
FAKE_OUT="$TMP/fake-result.json"
CURSOR_ARGS_LOG="$TMP/execute.args" PATH="$FAKE_BIN:/usr/bin:/bin" HOME="$EMPTY_HOME" \
  "$RUNNER" --output-file "$FAKE_OUT" --timeout 1000 -- "Say only: pong" >/dev/null
grep -q -- '--force' "$TMP/execute.args" && ! grep -q -- '--mode plan' "$TMP/execute.args" \
  && [[ "$(stat -c %a "$FAKE_OUT" "$FAKE_OUT.raw" "$FAKE_OUT.stderr" "$FAKE_OUT.prompt" | sort -u)" == "600" ]] \
  && grep -q 'fake pong' "$FAKE_OUT" && ok "fake execute argv, contract, and owner-only artifacts" \
  || bad "fake execute contract"
CURSOR_ARGS_LOG="$TMP/readonly.args" PATH="$FAKE_BIN:/usr/bin:/bin" HOME="$EMPTY_HOME" \
  "$RUNNER" --readonly --output-file "$TMP/readonly.json" --timeout 1000 -- "Review only" >/dev/null
grep -q -- '--mode plan' "$TMP/readonly.args" && ! grep -q -- '--force' "$TMP/readonly.args" \
  && ok "fake readonly uses plan mode without force" || bad "fake readonly contract"

# malformed output still leaves a valid distilled error JSON
printf 'not-json\n' > "$TMP/bad.raw"
python3 "$DISTILL" "$TMP/bad.raw" "$TMP/bad.out" 124 9 >/dev/null || true
python3 - "$TMP/bad.out" <<'PY' && ok "malformed output preserves valid error JSON" || bad "malformed output JSON"
import json, sys
out = json.load(open(sys.argv[1]))
assert out["is_error"] is True and out["backend"] == "cursor"
PY

# (b) real runner --help
HELP="$("$RUNNER" --help 2>&1)" || true
echo "$HELP" | grep -q -- '--print' \
  && echo "$HELP" | grep -q -- '--output-format' \
  && echo "$HELP" | grep -q -- '--budget' \
  && echo "$HELP" | grep -q -- '--model' \
  && echo "$HELP" | grep -q -- '--composer' \
  && echo "$HELP" | grep -q -- '--grok' \
  && echo "$HELP" | grep -q -- '--readonly' \
  && echo "$HELP" | grep -q 'composer-2.5' \
  && echo "$HELP" | grep -q 'cursor-grok-4.6' \
  && ok "runner --help advertises --print/--output-format, --budget, --model, --composer/--grok, --readonly, Cursor-pool default" \
  || bad "runner --help missing contract strings"

# exclusive-flag abort (no live cursor-agent needed)
EXCL_ERR="$("$RUNNER" --composer --opus -- "Say only: pong" 2>&1)" || EXCL_RC=$?
EXCL_RC=${EXCL_RC:-0}
if [[ "$EXCL_RC" -ne 0 ]] && echo "$EXCL_ERR" | grep -q 'exclusive'; then
  ok "exclusive --composer/--opus abort"
else
  bad "exclusive flags did not abort (rc=$EXCL_RC)"
  echo "$EXCL_ERR"
fi

# --grok 4.6 xhigh resolves without calling the API
RESOLVED="$("$RUNNER" --grok 4.6 xhigh --resolve-only 2>/dev/null)" || RESOLVE_RC=$?
RESOLVE_RC=${RESOLVE_RC:-0}
if [[ "$RESOLVE_RC" -eq 0 && "$RESOLVED" == "cursor-grok-4.6-xhigh" ]]; then
  ok "--grok 4.6 xhigh → cursor-grok-4.6-xhigh (no API)"
else
  bad "grok alias resolve (rc=$RESOLVE_RC got='$RESOLVED')"
fi

COMP="$("$RUNNER" --composer --resolve-only 2>/dev/null)" || true
[[ "$COMP" == "composer-2.5" ]] && ok "--composer → composer-2.5" || bad "composer resolve got='$COMP'"

SOL="$("$RUNNER" --sol --effort xhigh --resolve-only 2>/dev/null)" || true
[[ "$SOL" == "gpt-5.6-sol-xhigh" ]] && ok "--sol --effort xhigh → gpt-5.6-sol-xhigh" || bad "sol resolve got='$SOL'"

LOW="$("$RUNNER" --budget low --resolve-only 2>/dev/null)" || true
[[ "$LOW" == "composer-2.5" ]] && ok "unspecified + budget low → composer-2.5" || bad "low default got='$LOW'"

ORD="$("$RUNNER" --budget medium --resolve-only 2>/dev/null)" || true
[[ "$ORD" == "cursor-grok-4.6-high" ]] && ok "unspecified + budget medium → cursor-grok-4.6-high" || bad "medium default got='$ORD'"

# resolver unit (same shipped function)
PY_GROK="$(python3 "$RESOLVE" --family grok --grok-version 4.6 --effort xhigh)"
[[ "$PY_GROK" == "cursor-grok-4.6-xhigh" ]] && ok "python resolver grok 4.6 xhigh" || bad "python resolver got='$PY_GROK'"

# missing cursor-agent on PATH (and no ~/.local/bin/cursor-agent under a fake HOME)
EMPTY_HOME="$TMP/empty-home"
mkdir -p "$EMPTY_HOME"
MISS_ERR="$(PATH=/usr/bin:/bin HOME="$EMPTY_HOME" "$RUNNER" --timeout 1000 -- "Say only: pong" 2>&1)" || MISS_RC=$?
MISS_RC=${MISS_RC:-0}
if [[ "$MISS_RC" -ne 0 ]] && echo "$MISS_ERR" | grep -qi "cursor-agent"; then
  ok "missing cursor-agent aborts"
else
  bad "missing cursor-agent did not abort (rc=$MISS_RC)"
  echo "$MISS_ERR"
fi

# command markers
if grep -q 'Cursor Models' "$CMD" \
  && grep -q 'Composer' "$CMD" \
  && grep -q '256k' "$CMD" \
  && grep -q '200k' "$CMD" \
  && grep -q 'named-only' "$CMD" \
  && grep -q 'cursor-headless-exec' "$CMD" \
  && grep -q 'not at phase end' "$CMD" \
  && grep -q 'BASELINE_RED' "$CMD" \
  && grep -q 'Never added to `meta_dev.ladder.pool`' "$CMD"; then
  ok "command documents pools, 256k/200k, parked, runner, test discipline"
else
  bad "command card missing required markers"
fi

if grep -q 'never auto-pick Opus' "$CMD" \
  || grep -q 'Never auto-pick Opus' "$CMD" \
  || grep -q 'never auto-picks Opus' "$CMD" \
  || grep -q 'Never auto-picks Opus/Sol' "$CMD"; then
  ok "command says unspecified runs stay on Composer/Grok"
else
  grep -qi 'never auto-pick' "$CMD" && ok "command says unspecified stays off Opus/Sol" \
    || bad "command missing unspecified-chooser Opus/Sol ban"
fi

if grep -q '"cursor": "commands/cursor-execute.md"' "$PLUGIN_ROOT/references/workflows/routes.json" \
  && grep -q 'cursor-execute' "$PLUGIN_ROOT/references/workflows/routes.json" \
  && grep -q -- '--cursor' "$PLUGIN_ROOT/commands/auto-execute.md"; then
  ok "routes.json + auto-execute --cursor wiring"
else
  bad "routes / --cursor wiring missing"
fi

echo
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
