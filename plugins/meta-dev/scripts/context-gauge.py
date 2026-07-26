#!/usr/bin/env python3
"""Context gauge — report the orchestrating session's live context-window size.

Reads the current Claude-host session transcript (located via $CLAUDE_CODE_SESSION_ID) and
returns the latest API context occupancy:

    input_tokens + cache_read_input_tokens + cache_creation_input_tokens

taken from the most recent assistant `usage` record. That sum is what the API
actually carries as the live window, so it is the honest number to gauge a
compaction threshold against.

Used by the agentic-exec-loop / auto-execute conductor as a context WATCHDOG: at
a phase/wave seam the conductor runs this and, when the verdict is OVER, pauses
the run and invokes /meta-compact so the user can compact FORWARD before the
harness's blunt hard auto-compact (CLAUDE_AUTOCOMPACT_PCT_OVERRIDE) ever fires.

Deterministic, stdlib-only, and NEVER blocks work: on any failure it prints
CONTEXT_VERDICT=UNKNOWN and exits 0 — a gauge that cannot read must not halt the
loop. Exit code is 10 on OVER, 0 otherwise (a convenience for shell branching;
the verdict line is the real signal).
"""
import argparse
import glob
import json
import os
import sys

DEFAULT_THRESHOLD = 300_000


def find_transcript():
    """Locate the current session's transcript JSONL. Returns a path or None.

    Primary: $CLAUDE_CODE_SESSION_ID names the exact file under any project dir.
    Fallback: the most-recently-modified transcript (the actively-appended one).
    """
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(
        os.environ.get("HOME", ""), ".claude"
    )
    base = os.environ.get("CLAUDE_PROJECTS_DIR") or os.path.join(config_dir, "projects")
    if not os.path.isdir(base):
        return None
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID") or os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        hits = glob.glob(os.path.join(base, "*", sid + ".jsonl"))
        if hits:
            return hits[0]
    allj = glob.glob(os.path.join(base, "*", "*.jsonl"))
    if not allj:
        return None
    try:
        return max(allj, key=os.path.getmtime)
    except Exception:
        return None


def latest_context_tokens(path):
    """Sum the last usage record's context-occupancy fields. None on failure."""
    last = None
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                msg = o.get("message") if isinstance(o.get("message"), dict) else None
                u = (msg or {}).get("usage") or o.get("usage")
                if isinstance(u, dict) and ("input_tokens" in u or "cache_read_input_tokens" in u):
                    last = u
    except Exception:
        return None
    if not last:
        return None
    return (
        int(last.get("input_tokens", 0) or 0)
        + int(last.get("cache_read_input_tokens", 0) or 0)
        + int(last.get("cache_creation_input_tokens", 0) or 0)
    )


def main(argv=None):
    ap = argparse.ArgumentParser(prog="context-gauge.py",
                                 description="Report live context size vs a compaction threshold.")
    ap.add_argument("--threshold", type=int,
                    default=int(os.environ.get("META_DEV_CONTEXT_THRESHOLD", DEFAULT_THRESHOLD)),
                    help="token ceiling for the OVER verdict (default 300000)")
    ap.add_argument("--json", action="store_true",
                    help="emit a JSON object instead of KEY=VALUE lines")
    args = ap.parse_args(argv)

    path = find_transcript()
    tokens = latest_context_tokens(path) if path else None

    if tokens is None:
        if args.json:
            print(json.dumps({"verdict": "UNKNOWN", "tokens": None,
                              "threshold": args.threshold, "transcript": path}))
        else:
            print("CONTEXT_VERDICT=UNKNOWN")
            print(f"CONTEXT_THRESHOLD={args.threshold}")
            print(f"CONTEXT_TRANSCRIPT={path or ''}")
        return 0

    verdict = "OVER" if tokens >= args.threshold else "OK"
    pct = round(100 * tokens / args.threshold) if args.threshold else 0
    if args.json:
        print(json.dumps({"verdict": verdict, "tokens": tokens, "threshold": args.threshold,
                          "pct": pct, "transcript": path}))
    else:
        print(f"CONTEXT_TOKENS={tokens}")
        print(f"CONTEXT_THRESHOLD={args.threshold}")
        print(f"CONTEXT_PCT={pct}")
        print(f"CONTEXT_VERDICT={verdict}")
    return 10 if verdict == "OVER" else 0


if __name__ == "__main__":
    sys.exit(main())
