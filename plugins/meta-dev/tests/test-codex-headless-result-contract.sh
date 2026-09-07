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

python3 - "$valid_output" "$TMP_DIR/argv" "$PLUGIN_ROOT/schemas/codex-worker-result.schema.json" "$RUNNER" <<'PY'
import json
import sys

output, argv, schema, runner = map(__import__('pathlib').Path, sys.argv[1:])
wrapped = json.loads(output.read_text())
assert wrapped["is_error"] is False
assert wrapped["backend"] == "codex"
assert json.loads(wrapped["result"])["verification"] == "FOCUSED_PASS"
assert json.loads(wrapped["result"])["task_results"] == []
args = argv.read_text().splitlines()
assert "--output-schema" in args
assert args[args.index("--output-schema") + 1] == str(schema)
assert args[args.index("-m") + 1] == "gpt-5.6-terra"
assert 'model_reasoning_effort="medium"' in args
assert "exactly one entry for every assigned ledger handle" in runner.read_text()
assert "never a slice wholesale" in runner.read_text()
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

slice_output="$TMP_DIR/slice-output.json"
run_stubbed "$TEST_DIR/fixtures/codex-worker-result-slice.json" "$slice_output" >"$TMP_DIR/slice.stdout" 2>"$TMP_DIR/slice.stderr"
python3 - "$slice_output" <<'PY'
import json
import sys
wrapped = json.load(open(sys.argv[1]))
assert wrapped["is_error"] is False  # Successful transport is not slice acceptance.
result = json.loads(wrapped["result"])
assert result["verification"] == "TASK_RED"
first, second = result["task_results"]
assert first["handle"] == "T1.1" and first["state"] == "FOCUSED_PASS"
assert first["verify_exit_code"] == 0
assert second["handle"] == "T1.2" and second["state"] == "TASK_RED"
assert second["verify_exit_code"] == 1 and second["blockers"]
assert first["commit_sha"] == second["commit_sha"]
PY
echo "PASS: coherent slice preserves per-handle acceptance, shared SHA, and partial failure"

for fixture in duplicate nested-malformed; do
    output="$TMP_DIR/$fixture-output.json"
    if run_stubbed "$TEST_DIR/fixtures/codex-worker-result-$fixture.json" "$output" >"$TMP_DIR/$fixture.stdout" 2>"$TMP_DIR/$fixture.stderr"; then
        echo "FAIL: $fixture worker result unexpectedly succeeded" >&2
        exit 1
    fi
    python3 - "$output" <<'PY'
import json
import sys
assert json.load(open(sys.argv[1]))["is_error"] is True
PY
done
grep -F 'duplicate task handle: T1.1' "$TMP_DIR/duplicate-output.json.stderr" >/dev/null
grep -F 'task_results[0].verify_exit_code: expected integer or null' "$TMP_DIR/nested-malformed-output.json.stderr" >/dev/null
echo "PASS: duplicate handles and malformed nested types fail closed"

# Exercise the same embedded stdlib validator on additional malformed handoffs.
# These checks do not invoke Codex or depend on optional jsonschema packages.
python3 - "$RUNNER" "$PLUGIN_ROOT/schemas/codex-worker-result.schema.json" "$TEST_DIR/fixtures/codex-worker-result-slice.json" "$TMP_DIR" <<'PY'
import copy
import json
from pathlib import Path
import subprocess
import sys

runner, schema_path, fixture, temp = map(Path, sys.argv[1:])
source = runner.read_text().split('validate_worker_result() {', 1)[1].split("<<'PY'\n", 1)[1].split('\nPY\n', 1)[0]
base = json.loads(fixture.read_text())
cases = []
def case(name, change):
    result = copy.deepcopy(base)
    change(result)
    cases.append((name, result))
case('missing nested field', lambda r: r['task_results'][0].pop('blockers'))
case('extra nested field', lambda r: r['task_results'][0].update(accepted=True))
case('invalid handle', lambda r: r['task_results'][0].update(handle='not-a-handle'))
case('invalid SHA', lambda r: r['task_results'][0].update(commit_sha='not-a-sha'))
case('invalid state', lambda r: r['task_results'][0].update(state='PASS'))
case('invalid changed files', lambda r: r['task_results'][0].update(changed_files=[None]))
case('false pass exit', lambda r: r['task_results'][0].update(verify_exit_code=1))
case('false pass no verifier', lambda r: r['task_results'][0].update(verify_command=''))
case('false pass no evidence', lambda r: r['task_results'][0].update(verify_output=''))
case('accepted edits no SHA', lambda r: r['task_results'][0].update(commit_sha=None))
case('accepted handle has blockers', lambda r: r['task_results'][0].update(blockers=['Unresolved dependency']))
case('aggregate hides failure', lambda r: r.update(verification='FOCUSED_PASS'))
case('missing task_results', lambda r: r.pop('task_results'))
for name, result in cases:
    path = temp / 'validator-case.json'
    path.write_text(json.dumps(result))
    run = subprocess.run([sys.executable, '-c', source, str(schema_path), str(path)], capture_output=True, text=True)
    assert run.returncode != 0, name
    assert 'Traceback' not in run.stderr, (name, run.stderr)
print(f'PASS: {len(cases)} additional nested schema and acceptance checks')
PY
