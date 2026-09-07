#!/usr/bin/env python3
"""Session-bound context watchdog. UNKNOWN never blocks; OVER exits 10.

Claude usage adds input + cache read + cache creation; Codex token_count uses
last_token_usage input + output (cached tokens are already included). Generic
JSON telemetry is {host, session_id, context_tokens, context_window?}. It must
be published by the active host, not inferred from cumulative billing usage.
No latest-session fallback or hardcoded model window is safe here.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def positive(value):
    if isinstance(value, bool):
        raise ValueError("expected a positive integer")
    number = int(value)
    if number <= 0 or str(number) != str(value):
        raise ValueError("expected a positive integer")
    return number


def tokens(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("invalid token count")
    return value


def context_settings(project_root=None):
    """Use the shared validated cascade; invalid config gives UNKNOWN."""
    script = Path(__file__).with_name("config-merge.py")
    env = None
    if project_root is not None:
        root = Path(project_root).resolve()
        if not root.is_dir():
            raise ValueError("project root must be an existing directory")
        env = dict(os.environ, META_DEV_PROJECT_ROOT=str(root))
        # An explicit CLI project boundary wins over an inherited topology file.
        env.pop("META_DEV_REPOS_FILE", None)
    result = subprocess.run([sys.executable, str(script)], capture_output=True,
                            text=True, timeout=10, check=True, env=env)
    return json.loads(result.stdout).get("meta_dev", {}).get("context", {})


def identity(host=None, session_id=None):
    host = host or os.environ.get("META_DEV_CONTEXT_HOST")
    session_id = session_id or os.environ.get("META_DEV_CONTEXT_SESSION_ID")
    native = {
        "claude": os.environ.get("CLAUDE_CODE_SESSION_ID") or os.environ.get("CLAUDE_SESSION_ID"),
        "codex": os.environ.get("CODEX_THREAD_ID"),
    }
    if not host:
        available = [name for name, sid in native.items() if sid]
        if len(available) != 1:
            raise ValueError("explicit host required when identity is missing or ambiguous")
        host = available[0]
    session_id = session_id or native.get(host)
    if not session_id or not re.fullmatch(r"[A-Za-z0-9_-]+", session_id):
        raise ValueError("missing or unsafe session identity")
    return host, session_id


def find_transcript(host, session_id, explicit=None):
    if explicit:
        return Path(explicit)
    if host == "claude":
        config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
        base = Path(os.environ.get("CLAUDE_PROJECTS_DIR") or config / "projects")
        hits = list(base.glob(f"*/{session_id}.jsonl"))
    elif host == "codex":
        base = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "sessions"
        hits = list(base.glob(f"*/*/*/rollout-*-{session_id}.jsonl"))
    else:
        return None
    return hits[0] if len(hits) == 1 else None


def read_transcript(path, host, session_id):
    """Validate identity before accepting occupancy; reject malformed records."""
    if host not in {"claude", "codex"}:
        raise ValueError("unsupported native transcript host; supply generic telemetry")
    if host == "claude" and path.name != session_id + ".jsonl":
        raise ValueError("Claude transcript filename does not match session")
    bound = host == "claude"
    latest, window = None, None
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError("invalid transcript record")
            if host == "claude":
                if record.get("sessionId", session_id) != session_id:
                    raise ValueError("Claude transcript session mismatch")
                message = record.get("message", {})
                usage = message.get("usage") if isinstance(message, dict) else None
                usage = usage if usage is not None else record.get("usage")
                if usage is not None:
                    if not isinstance(usage, dict) or "input_tokens" not in usage:
                        raise ValueError("invalid Claude usage")
                    latest = sum(tokens(usage.get(key, 0)) for key in (
                        "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
            else:
                payload = record.get("payload", {})
                if record.get("type") == "session_meta":
                    if payload.get("id") != session_id:
                        raise ValueError("Codex transcript session mismatch")
                    bound = True
                elif not bound:
                    raise ValueError("Codex session metadata must precede usage")
                elif record.get("type") == "event_msg" and payload.get("type") == "token_count":
                    info = payload.get("info")
                    if info is None:
                        continue  # Rate-limit-only event, not a new usage sample.
                    usage = info["last_token_usage"]
                    latest = tokens(usage["input_tokens"]) + tokens(usage.get("output_tokens", 0))
                    if info.get("model_context_window") is not None:
                        window = positive(info["model_context_window"])
    if not bound or latest is None:
        raise ValueError("no session-bound usage")
    return latest, window


def read_telemetry(path, host, session_id):
    with path.open(encoding="utf-8") as stream:
        data = json.load(stream)
    if data.get("host") != host or data.get("session_id") != session_id:
        raise ValueError("telemetry identity mismatch")
    count = tokens(data["context_tokens"])
    window = positive(data["context_window"]) if data.get("context_window") is not None else None
    return count, window


def evaluate(args, settings):
    result = {"verdict": "UNKNOWN", "tokens": None, "threshold": None,
              "context_window": None, "host": None, "session_id": None, "transcript": None}
    try:
        host, sid = identity(args.host, args.session_id)
        result.update(host=host, session_id=sid)
        telemetry = args.telemetry or os.environ.get("META_DEV_CONTEXT_TELEMETRY")
        explicit = args.transcript or os.environ.get("META_DEV_CONTEXT_TRANSCRIPT")
        if telemetry and explicit:
            raise ValueError("choose telemetry or transcript, not both")
        path = Path(telemetry) if telemetry else find_transcript(host, sid, explicit)
        if path is None:
            raise ValueError("no uniquely identified transcript; supply session-bound telemetry")
        result["transcript"] = str(path)
        count, measured_window = (read_telemetry(path, host, sid) if telemetry
                                  else read_transcript(path, host, sid))
        model = args.model or os.environ.get("META_DEV_CONTEXT_MODEL")
        window = (args.context_window or os.environ.get("META_DEV_CONTEXT_WINDOW")
                  or settings.get("context_window") or measured_window
                  or settings.get("model_windows", {}).get(model))
        window = positive(window) if window is not None else None
        threshold = (args.threshold if args.threshold is not None else
                     os.environ.get("META_DEV_CONTEXT_THRESHOLD", settings.get("threshold")))
        ratio = (args.threshold_ratio if args.threshold_ratio is not None else
                 os.environ.get("META_DEV_CONTEXT_THRESHOLD_RATIO", settings.get("threshold_ratio", 0.8)))
        if isinstance(ratio, bool) or not 0 < float(ratio) <= 1:
            raise ValueError("threshold ratio must be in (0, 1]")
        if threshold is None:
            if window is None:
                raise ValueError("context window or explicit threshold required")
            threshold = max(1, int(window * float(ratio)))
        threshold = positive(threshold)
        if window is not None and threshold > window:
            raise ValueError("threshold exceeds context window")
        result.update(tokens=count, threshold=threshold, context_window=window,
                      pct=round(100 * count / threshold),
                      verdict="OVER" if count >= threshold else "OK")
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        result["reason"] = str(exc)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("host", "session-id", "transcript", "telemetry", "model", "project-root", "context-window",
                 "threshold", "threshold-ratio"):
        parser.add_argument("--" + flag)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = evaluate(args, context_settings(args.project_root))
    except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError) as exc:
        result = {"verdict": "UNKNOWN", "tokens": None, "threshold": None,
                  "transcript": None, "reason": "configuration unavailable: " + str(exc)}
    if args.json:
        print(json.dumps(result))
    else:
        for key, value in result.items():
            print(f"CONTEXT_{key.upper()}={'' if value is None else value}")
    return 10 if result["verdict"] == "OVER" else 0


if __name__ == "__main__":
    sys.exit(main())
