#!/usr/bin/env bash
# Hermetic unit tests for lib/read-prompt.sh — the guard runs before any
# codex/grok/claude CLI invocation, so no external tool or auth is needed.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="$HERE/read-prompt.sh"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
pass=0; fail=0
check() { if [[ "$1" == "$2" ]]; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $3 (got '$1' want '$2')"; fi; }

# 1) non-empty positional prompt → exit 0, PROMPT preserved
( source "$LIB"; PROMPT="do the thing"; resolve_prompt "" test; [[ "$PROMPT" == "do the thing" ]] )
check "$?" 0 "positional non-empty passes"

# 2) whitespace-only positional → exit 1
( source "$LIB"; PROMPT="   "; resolve_prompt "" test ) 2>/dev/null
check "$?" 1 "whitespace positional rejected"

# 3) empty --prompt-file → exit 1
: > "$tmp/empty.prompt"
( source "$LIB"; PROMPT=""; resolve_prompt "$tmp/empty.prompt" test ) 2>/dev/null
check "$?" 1 "empty prompt-file rejected"

# 4) missing --prompt-file → exit 1
( source "$LIB"; PROMPT=""; resolve_prompt "$tmp/nope.prompt" test ) 2>/dev/null
check "$?" 1 "missing prompt-file rejected"

# 5) non-empty --prompt-file → exit 0 AND PROMPT loaded from file (overrides positional)
printf 'from file' > "$tmp/ok.prompt"
out="$( source "$LIB"; PROMPT="positional"; resolve_prompt "$tmp/ok.prompt" test; printf '%s' "$PROMPT" )"
check "$?" 0 "prompt-file happy path exits 0"
check "$out" "from file" "prompt-file overrides positional"

echo "read-prompt.sh: $pass passed, $fail failed"
[[ "$fail" -eq 0 ]]
