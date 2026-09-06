#!/usr/bin/env bash
# Focused runner contract test: no network and no live Codex invocation.
set -euo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$TEST_DIR/.." && pwd)"
RUNNER="$PLUGIN_ROOT/scripts/codex-headless-exec"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$TMP_DIR/bin" "$TMP_DIR/codex-home"
cp "$TEST_DIR/fixtures/codex-exec-stub.sh" "$TMP_DIR/bin/codex"
cp "$TEST_DIR/fixtures/codex-auth.json" "$TMP_DIR/codex-home/auth.json"
chmod +x "$TMP_DIR/bin/codex"

run_stubbed() {
    local fixture="$1"
    local output="$2"
    shift 2
    rm -f "$TMP_DIR/argv"
    PATH="$TMP_DIR/bin:$PATH" \
    CODEX_HOME="$TMP_DIR/codex-home" \
    CODEX_STUB_ARGV="$TMP_DIR/argv" \
    CODEX_STUB_RESULT="$fixture" \
    STALL_SECS=0 \
    "$RUNNER" --no-framework --timeout 10000 --output-file "$output" "$@" -- "Return the required JSON handoff."
}

valid_output="$TMP_DIR/valid-output.json"
run_stubbed "$TEST_DIR/fixtures/codex-worker-result-valid.json" "$valid_output" >"$TMP_DIR/valid.stdout" 2>"$TMP_DIR/valid.stderr"

python3 - "$valid_output" "$TMP_DIR/argv" "$PLUGIN_ROOT/schemas/codex-worker-result.schema.json" <<'PY'
import json
import sys

output, argv, schema = map(__import__('pathlib').Path, sys.argv[1:])
wrapped = json.loads(output.read_text())
assert wrapped["is_error"] is False
assert wrapped["backend"] == "codex"
assert json.loads(wrapped["result"])["verification"] == "FOCUSED_PASS"
args = argv.read_text().splitlines()
assert "--output-schema" in args
assert args[args.index("--output-schema") + 1] == str(schema)
assert args[args.index("-m") + 1] == "gpt-5.6-terra"
assert 'model_reasoning_effort="medium"' in args
print("PASS: output schema, Terra default, and legacy wrapper contract")
PY

assert_route() {
    local model="$1" effort="$2"
    shift 2
    run_stubbed "$TEST_DIR/fixtures/codex-worker-result-valid.json" "$TMP_DIR/route.json" "$@" >"$TMP_DIR/route.stdout" 2>"$TMP_DIR/route.stderr"
    python3 - "$TMP_DIR/argv" "$model" "$effort" <<'PY'
from pathlib import Path
import sys
args = Path(sys.argv[1]).read_text().splitlines()
assert args[args.index("-m") + 1] == sys.argv[2], args
assert f'model_reasoning_effort="{sys.argv[3]}"' in args, args
PY
}

assert_route gpt-6-astra high --tier astra
for effort in low medium high xhigh max ultra; do
    assert_route gpt-6-astra "$effort" --tier astra --effort "$effort"
done
echo "PASS: Astra model, high tier default, and all six supported efforts forwarded"

assert_route gpt-5.3-codex-spark low --tier spark
assert_route gpt-5.6-luna low --tier luna
assert_route gpt-5.6-terra medium --tier terra
assert_route gpt-5.6-sol high --tier sol
assert_route gpt-6-astra low --tier astra --budget low
assert_route gpt-6-astra xhigh --tier astra --budget high
assert_route gpt-6-astra ultra --tier astra --effort ultra --budget low
assert_route gpt-6-astra medium --model gpt-6-astra
assert_route custom-model high --tier astra --model custom-model
assert_route custom-model none --tier astra --model custom-model --effort none
echo "PASS: existing tier defaults, budget precedence, and explicit model overrides preserved"

assert_rejected() {
    if run_stubbed "$TEST_DIR/fixtures/codex-worker-result-valid.json" "$TMP_DIR/rejected.json" "$@" >"$TMP_DIR/rejected.stdout" 2>"$TMP_DIR/rejected.stderr"; then
        echo "FAIL: invalid Astra effort unexpectedly succeeded" >&2
        exit 1
    fi
    [[ ! -e "$TMP_DIR/argv" ]] || { echo "FAIL: Codex invoked for invalid Astra effort" >&2; exit 1; }
    grep -F "gpt-6-astra does not support --effort none" "$TMP_DIR/rejected.stderr" >/dev/null
}

assert_rejected --tier astra --effort none
assert_rejected --tier terra --model gpt-6-astra --effort none
echo "PASS: Astra none rejected before Codex invocation for tier and model override"

malformed_output="$TMP_DIR/malformed-output.json"
if run_stubbed "$TEST_DIR/fixtures/codex-worker-result-malformed.json" "$malformed_output" >"$TMP_DIR/malformed.stdout" 2>"$TMP_DIR/malformed.stderr"; then
    echo "FAIL: malformed worker result unexpectedly succeeded" >&2
    exit 1
fi
python3 - "$malformed_output" <<'PY'
import json
import sys
wrapped = json.load(open(sys.argv[1]))
assert wrapped["is_error"] is True
assert wrapped["subtype"] == "error"
PY
grep -F "[ERROR] malformed structured Codex result" "$malformed_output.stderr" >/dev/null
echo "PASS: malformed structured result fails loudly without a live Codex run"
