#!/usr/bin/env python3
# ============================================================================
# distill-cursor-result.py — Normalize `cursor-agent -p --output-format json`
# into the shared headless contract (same keys as grok/codex/agy).
#
# Cursor json (docs 2026-09): ONE object on success:
#   {"type": "result", "subtype": "success", "is_error": false,
#    "duration_ms": N, "duration_api_ms": N, "result": "<text>",
#    "session_id": "<uuid>", "request_id": "<optional>"}
# Failure: non-zero exit, stderr only — no well-formed JSON.
#
# Usage:
#   distill-cursor-result.py <raw_json> <out_json> <exit_code> <elapsed_ms>
# ============================================================================
import json
import sys
import re

_SECRET = re.compile(
    r'(sk-ant-[A-Za-z0-9_-]{12,}|sk-[A-Za-z0-9]{16,}|'
    r'xai-[A-Za-z0-9_-]{20,}|key_[A-Za-z0-9_-]{16,}|'
    r'AIza[A-Za-z0-9_-]{20,}|[0-9a-f]{16,}\.[A-Za-z0-9]{16,})'
)


def _redact(s):
    return _SECRET.sub('[REDACTED]', s) if isinstance(s, str) else s


def main() -> int:
    if len(sys.argv) < 5:
        print("usage: distill-cursor-result.py <raw_json> <out_json> "
              "<exit_code> <elapsed_ms>", file=sys.stderr)
        return 2
    raw_path, out_path, exit_code_s, elapsed_ms_s = sys.argv[1:5]
    exit_code = int(exit_code_s)
    elapsed_ms = int(elapsed_ms_s)

    obj = {}
    try:
        with open(raw_path, encoding="utf-8", errors="replace") as fh:
            text = fh.read().strip()
        if text:
            obj = json.loads(text)
    except (OSError, json.JSONDecodeError):
        obj = {}

    result = obj.get("result") or obj.get("text") or obj.get("response") or ""
    session_id = obj.get("session_id") or obj.get("sessionId") or obj.get("chatId")
    stop_reason = obj.get("subtype") or obj.get("status") or obj.get("stopReason") or ""
    num_turns = obj.get("num_turns")
    usage = obj.get("usage")
    json_error = bool(obj.get("is_error"))
    status_ok = (not stop_reason) or str(stop_reason).lower() in (
        "success", "ok", "endturn", "completed",
    )
    is_error = exit_code != 0 or json_error or (obj and not status_ok)
    if stop_reason and not status_ok:
        note = f"[subtype={stop_reason} — run ended without success]"
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
        "backend": "cursor",
        "stop_reason": stop_reason,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    try:
        import os
        os.chmod(out_path, 0o600)
    except OSError:
        pass

    if not obj and not result:
        return 1

    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
