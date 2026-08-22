#!/usr/bin/env python3
# ============================================================================
# distill-agy-result.py — Normalize an `agy --print --output-format json` run
# into the same clean result contract as distill-grok-result.py /
# distill-codex-result.py / distill-headless-result.py.
#
# agy json (verified 2026-08-22, CLI 1.1.18) is ONE object on stdout:
#   {"conversation_id": "<uuid>",
#    "status":          "SUCCESS" | ...,
#    "response":        "<final assistant answer>",
#    "duration_seconds": <float>,
#    "num_turns":        <int>,
#    "usage":            {"input_tokens", "output_tokens", "thinking_tokens",
#                         "cache_read_tokens", "total_tokens"}}
#
# Usage:
#   distill-agy-result.py <raw_json> <out_json> <exit_code> <elapsed_ms>
#
# Writes {is_error, subtype, num_turns, duration_ms, session_id, result, usage,
# backend, stop_reason} to <out_json>, and prints `result` to stdout.
# ============================================================================
import json
import sys
import re

_SECRET = re.compile(
    r'(sk-ant-[A-Za-z0-9_-]{12,}|sk-[A-Za-z0-9]{16,}|'
    r'xai-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{20,}|'
    r'[0-9a-f]{16,}\.[A-Za-z0-9]{16,})'
)


def _redact(s):
    return _SECRET.sub('[REDACTED]', s) if isinstance(s, str) else s


def main() -> int:
    if len(sys.argv) < 5:
        print("usage: distill-agy-result.py <raw_json> <out_json> "
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

    result = obj.get("response") or obj.get("text") or ""
    session_id = obj.get("conversation_id") or obj.get("sessionId")
    stop_reason = obj.get("status") or obj.get("stopReason") or ""
    num_turns = obj.get("num_turns")
    usage = obj.get("usage")

    status_ok = (not stop_reason) or stop_reason.upper() in (
        "SUCCESS", "OK", "ENDTURN", "COMPLETED",
    )
    is_error = exit_code != 0 or not status_ok
    if stop_reason and not status_ok:
        note = f"[status={stop_reason} — run ended without SUCCESS]"
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
        "backend": "agy",
        "stop_reason": stop_reason,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)

    if not obj and not result:
        return 1

    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
