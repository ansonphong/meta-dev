#!/usr/bin/env python3
# ============================================================================
# distill-grok-result.py — Normalize a `grok -p --output-format json` run into
# the same clean result contract emitted by distill-headless-result.py (claude)
# and distill-codex-result.py, so /auto-execute can consume grok workers
# identically to deep/glm/codex.
#
# grok's `--output-format json` emits a SINGLE final JSON object on stdout:
#   {"text":        "<final assistant answer>",
#    "stopReason":  "EndTurn" | "MaxTurns" | ...,
#    "sessionId":   "<uuid>",
#    "requestId":   "<uuid>",
#    "thought":     "<reasoning trace>"}
# So — unlike codex's JSONL event stream — there is nothing to reconstruct:
# `text` IS the canonical result. This distiller is intentionally thin.
#
# Note: grok's json mode does not expose a turn count or token usage, so
# num_turns/usage are null. stopReason is surfaced separately for visibility.
#
# Usage:
#   distill-grok-result.py <raw_json> <out_json> <exit_code> <elapsed_ms>
#
# Writes {is_error, subtype, num_turns, duration_ms, session_id, result, usage,
# backend, stop_reason} to <out_json>, and prints `result` to stdout.
# ============================================================================
import json
import sys
import re

# Redact common secret shapes incl. xAI keys (xai-…) so a key that leaked into
# grok's `text`/`thought` never lands in the distilled result.
_SECRET = re.compile(
    r'(sk-ant-[A-Za-z0-9_-]{12,}|sk-[A-Za-z0-9]{16,}|'
    r'xai-[A-Za-z0-9_-]{20,}|[0-9a-f]{16,}\.[A-Za-z0-9]{16,})'
)


def _redact(s):
    return _SECRET.sub('[REDACTED]', s) if isinstance(s, str) else s


def main() -> int:
    if len(sys.argv) < 5:
        print("usage: distill-grok-result.py <raw_json> <out_json> "
              "<exit_code> <elapsed_ms>", file=sys.stderr)
        return 2
    raw_path, out_path, exit_code_s, elapsed_ms_s = sys.argv[1:5]
    exit_code = int(exit_code_s)
    elapsed_ms = int(elapsed_ms_s)

    obj = {}
    try:
        with open(raw_path, encoding="utf-8", errors="replace") as fh:
            obj = json.load(fh)
    except (OSError, json.JSONDecodeError):
        obj = {}

    result = obj.get("text") or ""
    session_id = obj.get("sessionId")
    stop_reason = obj.get("stopReason") or ""
    num_turns = None          # grok json mode exposes no turn count
    usage = None              # grok json mode exposes no token usage

    # is_error reflects RUN failure (non-zero exit), matching the claude + codex
    # distillers' semantics ("not empty content"). A non-EndTurn stopReason is
    # surfaced as an appended note but does not itself mark error — grok still
    # returns its best text on MaxTurns, which is often useful.
    is_error = exit_code != 0
    if stop_reason and stop_reason != "EndTurn":
        note = f"[stopReason={stop_reason} — run ended without a clean EndTurn]"
        result = f"{result}\n\n{note}" if result else note

    result = _redact(result)

    out = {
        "is_error": is_error,
        "subtype": "error" if is_error else "success",
        "num_turns": num_turns,
        "duration_ms": elapsed_ms,
        "session_id": session_id,
        "result": result,
        "usage": usage,
        "backend": "grok",
        "stop_reason": stop_reason,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)

    # Parsed nothing AND have no result → signal distill failure so the runner
    # can fall back to the raw payload (exit 3, matching claude/codex paths).
    if not obj and not result:
        return 1

    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
