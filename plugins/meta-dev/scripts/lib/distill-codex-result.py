#!/usr/bin/env python3
# ============================================================================
# distill-codex-result.py — Normalize a `codex exec --json` run into the same
# clean result contract emitted by distill-headless-result.py (the claude path),
# so /auto-execute can consume codex workers identically to deep/glm.
#
# Usage:
#   distill-codex-result.py <raw_jsonl> <last_message_file> <out_json> \
#                           <exit_code> <elapsed_ms>
#
# Reads the codex JSONL event stream (--json) plus the -o last-message file,
# writes a single {is_error, subtype, num_turns, duration_ms, session_id,
# result, usage, backend} object to <out_json>, and prints `result` to stdout.
#
# codex JSONL event shapes (codex-cli 0.142.x):
#   {"type":"thread.started","thread_id":"..."}
#   {"type":"turn.started"}
#   {"type":"item.completed","item":{"type":"agent_message","text":"..."}}
#   {"type":"turn.completed","usage":{"input_tokens":N,"output_tokens":N,...}}
#   error events carry "error" in their type.
# ============================================================================
import json
import sys


def main() -> int:
    raw_path, lastmsg_path, out_path, exit_code_s, elapsed_ms_s = sys.argv[1:6]
    exit_code = int(exit_code_s)
    elapsed_ms = int(elapsed_ms_s)

    events = []
    try:
        with open(raw_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass

    session_id = None
    num_turns = 0
    usage = None
    saw_error = False
    result = ""

    for ev in events:
        etype = ev.get("type", "")
        if etype == "thread.started":
            session_id = ev.get("thread_id") or session_id
        elif etype == "turn.started":
            num_turns += 1
        elif etype == "turn.completed":
            usage = ev.get("usage") or usage
        elif "error" in etype.lower():
            saw_error = True
        elif etype == "item.completed":
            item = ev.get("item") or {}
            if item.get("type") == "agent_message":
                text = item.get("text") or ""
                if text:
                    result = text  # keep the latest agent message

    # The -o last-message file is the canonical final answer when present.
    try:
        with open(lastmsg_path, encoding="utf-8", errors="replace") as fh:
            lm = fh.read().strip()
            if lm:
                result = lm
    except OSError:
        pass

    # is_error reflects RUN failure (crash / non-zero exit / error event) — not
    # empty content — matching the claude distiller's semantics.
    is_error = saw_error or exit_code != 0

    obj = {
        "is_error": is_error,
        "subtype": "error" if is_error else "success",
        "num_turns": num_turns,
        "duration_ms": elapsed_ms,
        "session_id": session_id,
        "result": result,
        "usage": usage,
        "backend": "codex",
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2)

    # If we genuinely parsed nothing and have no result, signal distill failure
    # so the runner can fall back to the raw payload (exit 3, like claude path).
    if not events and not result:
        return 1

    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
