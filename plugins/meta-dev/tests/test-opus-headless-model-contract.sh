#!/usr/bin/env bash
# Focused runner contract: stub `claude` on PATH. No live Claude session.
set -euo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$TEST_DIR/.." && pwd)"
RUNNER="$PLUGIN_ROOT/scripts/claude-headless-exec"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$TMP_DIR/bin"
cat > "$TMP_DIR/bin/claude" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
model=""
prev=""
for arg in "$@"; do
    if [[ "$prev" == "--model" ]]; then
        model="$arg"
    fi
    prev="$arg"
done
printf '%s\n' "$model" > "${CLAUDE_STUB_MODEL:?}"
printf '%s\n' "${ANTHROPIC_DEFAULT_OPUS_MODEL-}" > "${CLAUDE_STUB_OPUS_ENV:?}"
printf '%s\n' "${CLAUDE_CODE_SUBAGENT_MODEL-}" > "${CLAUDE_STUB_SUB_ENV:?}"
printf '%s\n' '{"type":"result","is_error":false,"subtype":"success","result":"ok","num_turns":1,"session_id":"stub"}'
EOF
chmod +x "$TMP_DIR/bin/claude"

run_stubbed() {
    rm -f "$TMP_DIR/model" "$TMP_DIR/opus-env" "$TMP_DIR/sub-env"
    PATH="$TMP_DIR/bin:$PATH" \
    CLAUDE_STUB_MODEL="$TMP_DIR/model" \
    CLAUDE_STUB_OPUS_ENV="$TMP_DIR/opus-env" \
    CLAUDE_STUB_SUB_ENV="$TMP_DIR/sub-env" \
    STALL_SECS=0 \
    "$RUNNER" --backend opus --timeout 30m --output-file "$TMP_DIR/out.json" "$@" -- "Return ok."
}

assert_model() {
    local expected="$1"
    shift
    run_stubbed "$@" >"$TMP_DIR/stdout" 2>"$TMP_DIR/stderr"
    python3 - "$TMP_DIR/model" "$TMP_DIR/opus-env" "$TMP_DIR/sub-env" "$expected" <<'PY'
from pathlib import Path
import sys
model = Path(sys.argv[1]).read_text().strip()
opus_env = Path(sys.argv[2]).read_text().strip()
sub_env = Path(sys.argv[3]).read_text().strip()
expected = sys.argv[4]
assert model == expected, model
assert opus_env == expected, opus_env
assert sub_env == expected, sub_env
PY
}

assert_model claude-opus-5-5
assert_model claude-opus-5 --model claude-opus-5
assert_model claude-opus-4-8 --model claude-opus-4-8
assert_model claude-opus-future --model claude-opus-future
echo "PASS: omitted opus model is claude-opus-5-5; explicit --model is forwarded"
