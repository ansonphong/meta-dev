#!/usr/bin/env python3
"""Distill a headless `claude -p --output-format json` payload into a clean result.

claude's JSON output is inconsistent across versions/backends: it may be a single
`{type:"result",...}` object, a JSON array of every stream event, or — under
`--output-format stream-json --verbose` — NEWLINE-DELIMITED JSON events (JSONL, one
object per line). The file can also carry a leading non-JSON warning line (e.g. the
claude.ai-connectors notice on stderr-less captures). This script normalizes all of that:

  argv[1] = raw payload file (claude stdout)
  argv[2] = output file to write the clean result object to

Writes a compact object {is_error, subtype, num_turns, duration_ms,
session_id, result} to argv[2], and echoes the result text to stdout (which the
shell captures for its summary). Exit non-zero if unparseable.
(total_cost_usd is intentionally omitted — the CLI prices non-Anthropic tokens at
Anthropic rates, so it's meaningless.)
"""
import sys
import json
import re

_SECRET = re.compile(r'(sk-ant-[A-Za-z0-9_-]{12,}|sk-[A-Za-z0-9]{16,}|[0-9a-f]{16,}\.[A-Za-z0-9]{16,})')
def _redact(s):
    return _SECRET.sub('[REDACTED]', s) if isinstance(s, str) else s


def try_parse(s):
    s = s.strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def main():
    if len(sys.argv) != 3:
        sys.stderr.write("usage: distill-headless-result.py <raw> <out>\n")
        return 2
    raw_path, out_path = sys.argv[1], sys.argv[2]
    try:
        data = open(raw_path, encoding="utf-8", errors="replace").read()
    except OSError as e:
        sys.stderr.write(f"distill: cannot read {raw_path}: {e}\n")
        return 2

    # Try whole-file first, then skip any leading non-JSON (warning) prefix.
    payload = try_parse(data)
    if payload is None:
        idx = next((i for i, ch in enumerate(data) if ch in "[{"), None)
        if idx is not None:
            payload = try_parse(data[idx:])
    # stream-json (`-p --output-format stream-json --verbose`) emits NEWLINE-DELIMITED
    # JSON events (JSONL), not one array/object — a whole-file parse fails on it.
    # Fall back to line-by-line and collect every valid event.
    if payload is None:
        evts = []
        for line in data.splitlines():
            obj = try_parse(line)
            if obj is not None:
                evts.append(obj)
        if evts:
            payload = evts
    if payload is None:
        sys.stderr.write("distill: no parseable JSON payload found\n")
        return 1

    events = payload if isinstance(payload, list) else [payload]
    results = [e for e in events if isinstance(e, dict) and e.get("type") == "result"]
    if results:
        r = results[-1]
    elif isinstance(payload, dict):
        r = payload
    else:
        # No result event — synthesize from the last assistant text block.
        text = ""
        for e in events:
            if isinstance(e, dict) and e.get("type") == "assistant":
                for b in e.get("message", {}).get("content", []):
                    if isinstance(b, dict) and b.get("type") == "text":
                        text = b.get("text", "")
        r = {"subtype": "no_result_event", "result": text, "is_error": False}

    result_text = r.get("result", "")
    if not isinstance(result_text, str):
        result_text = json.dumps(result_text, ensure_ascii=False)
    result_text = _redact(result_text)

    clean = {
        "is_error": r.get("is_error", False),
        "subtype": r.get("subtype"),
        "num_turns": r.get("num_turns"),
        "duration_ms": r.get("duration_ms"),
        "session_id": r.get("session_id"),
        "result": result_text,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)

    sys.stdout.write(result_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
