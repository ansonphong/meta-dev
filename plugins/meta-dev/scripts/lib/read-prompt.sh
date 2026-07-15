#!/usr/bin/env bash
# ============================================================================
# lib/read-prompt.sh — shared prompt resolution + fail-loud validation for the
# headless-exec runners (codex / grok / claude). SOURCED, not executed.
#
#   resolve_prompt <input_file> <runner_name>
#     Populates the global $PROMPT and HARD-FAILS (exit 1) on a prompt that is
#     missing / empty / whitespace-only, with a diagnostic naming the empty
#     source. Turns a mis-staged conductor scratchpad file into a LOUD error
#     instead of the silent "No prompt provided" degradation that skips a lens.
#
#   Precedence: when <input_file> is non-empty it is AUTHORITATIVE — its
#   contents replace any positional $PROMPT the caller already parsed.
#
# Conductor-side staging rules (unique per-run paths, atomic writes, verify
# before dispatch) live in:
#   skills/agentic-exec-loop/references/loop-protocol.md → "Scratchpad staging".
# ============================================================================

resolve_prompt() {
    local infile="$1" runner="${2:-headless-exec}"
    PROMPT="${PROMPT-}"   # safe under `set -u` even if caller left it unset

    if [[ -n "$infile" ]]; then
        if [[ ! -s "$infile" ]]; then
            echo "[ERROR] $runner: --prompt-file '$infile' is missing or empty." >&2
            echo "        The conductor staged a prompt to a path that was overwritten or" >&2
            echo "        never written. Stage to a UNIQUE per-run path and verify '[ -s FILE ]'" >&2
            echo "        before dispatch (loop-protocol.md -> Scratchpad staging)." >&2
            exit 1
        fi
        PROMPT="$(cat "$infile")"
    fi

    # Reject whitespace-only: $(...) strips trailing newlines but not embedded
    # spaces/tabs, and a blank prompt is never a real task.
    if [[ -z "${PROMPT//[[:space:]]/}" ]]; then
        echo "[ERROR] $runner: empty or whitespace-only prompt — nothing to execute." >&2
        echo "        Pass a real task after '--', or --prompt-file <non-empty path>." >&2
        exit 1
    fi
}
