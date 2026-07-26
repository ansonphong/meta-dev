#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' "$@" > "$CODEX_STUB_ARGV"
last_message=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -o|--output-last-message)
            last_message="$2"
            shift 2
            ;;
        *) shift ;;
    esac
done

[[ -n "$last_message" ]] || { echo "stub: missing -o" >&2; exit 64; }
cp "$CODEX_STUB_RESULT" "$last_message"
printf '%s\n' '{"type":"thread.started","thread_id":"stub-thread"}'
printf '%s\n' '{"type":"turn.started"}'
printf '%s\n' '{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}'
