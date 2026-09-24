#!/usr/bin/env bash
# Focused runner contract: stub `grok` on PATH. No live Grok session.
set -euo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$TEST_DIR/.." && pwd)"
RUNNER="$PLUGIN_ROOT/scripts/grok-headless-exec"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$TMP_DIR/bin" "$TMP_DIR/home/.grok"
printf '%s\n' '{}' > "$TMP_DIR/home/.grok/auth.json"
cat > "$TMP_DIR/bin/grok" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
model=""
effort=""
prev=""
for arg in "$@"; do
    if [[ "$prev" == "-m" ]]; then
        model="$arg"
    elif [[ "$prev" == "--effort" ]]; then
        effort="$arg"
    fi
    prev="$arg"
done
printf '%s\n' "$model" > "${GROK_STUB_MODEL:?}"
printf '%s\n' "$effort" > "${GROK_STUB_EFFORT:?}"
printf '%s\n' '{"text":"ok","stopReason":"EndTurn","sessionId":"stub"}'
EOF
chmod +x "$TMP_DIR/bin/grok"

run_stubbed() {
    rm -f "$TMP_DIR/model" "$TMP_DIR/effort"
    HOME="$TMP_DIR/home" \
    PATH="$TMP_DIR/bin:$PATH" \
    GROK_STUB_MODEL="$TMP_DIR/model" \
    GROK_STUB_EFFORT="$TMP_DIR/effort" \
    "$RUNNER" --timeout 30m --output-file "$TMP_DIR/out.json" "$@" -- "Return ok."
}

assert_route() {
    local model="$1" effort="$2"
    shift 2
    run_stubbed "$@" >"$TMP_DIR/stdout" 2>"$TMP_DIR/stderr"
    python3 - "$TMP_DIR/model" "$TMP_DIR/effort" "$model" "$effort" <<'PY'
from pathlib import Path
import sys
got_model = Path(sys.argv[1]).read_text().strip()
got_effort = Path(sys.argv[2]).read_text().strip()
assert got_model == sys.argv[3], got_model
assert got_effort == sys.argv[4], got_effort
PY
}

assert_route grok-4.7 high
assert_route grok-4.7 xhigh --model grok-4.7 --effort xhigh
assert_route grok-4.6 high --model grok-4.6
assert_route grok-4.5 high --model grok-4.5
assert_route grok-4.5 high --model grok-4.5 --effort xhigh
echo "PASS: grok-4.7 default, 4.6/4.5 accepted, 4.7 xhigh forwarded, 4.5 xhigh clamped"
