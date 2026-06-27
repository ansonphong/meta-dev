#!/usr/bin/env python3
"""Fold state.events.jsonl into state.json view. Atomic write via tempfile + rename."""
import json
import os
import sys
from datetime import datetime, timezone

PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", ".")
STATE_DIR = os.path.join(PLUGIN_ROOT, "plans/_dashboard")
EVENTS_FILE = os.path.join(STATE_DIR, "state.events.jsonl")
STATE_FILE = os.path.join(STATE_DIR, "state.json")
TEMPLATE = os.path.join(PLUGIN_ROOT, "plugins/meta-dev/templates/state.json")


def load_base() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    if os.path.exists(TEMPLATE):
        with open(TEMPLATE) as f:
            data = json.load(f)
        data["initialized"] = datetime.now(timezone.utc).isoformat()
        return data
    return {"version": "1.0.0", "initialized": datetime.now(timezone.utc).isoformat(),
            "last_updated": "", "active_sessions": [], "sweep_log": [],
            "overlord": {"active": False, "watching": None, "mode": None, "model": None,
                         "auto_fix": None, "tick_n": 0, "last_review": None, "tasks_reviewed": 0},
            "meta_dev_runs": [], "meta_execute_runs": [], "recent_commits": []}


def fold(state: dict, event: dict) -> dict:
    event_type = event.get("event", "")
    now = datetime.now(timezone.utc).isoformat()
    state["last_updated"] = now

    if event_type == "commit":
        commits = state.setdefault("recent_commits", [])
        commits.insert(0, {"sha": event.get("sha", ""), "message": event.get("message", ""),
                           "time": event.get("time", now)})
        state["recent_commits"] = commits[:50]  # cap

    elif event_type == "overlord_start":
        state["overlord"] = {
            "active": True,
            "watching": event.get("watching"),
            "mode": event.get("mode"),
            "model": event.get("model"),
            "auto_fix": event.get("auto_fix"),
            "tick_n": 0,
            "last_review": None,
            "tasks_reviewed": 0,
        }

    elif event_type == "overlord_tick":
        ol = state["overlord"]
        ol["tick_n"] = event.get("tick_n", ol["tick_n"] + 1)
        ol["last_review"] = now

    elif event_type == "overlord_done":
        state["overlord"]["active"] = False

    elif event_type == "session_start":
        sessions = state.setdefault("active_sessions", [])
        sessions.append({"session_id": event.get("session_id", ""),
                         "plan": event.get("plan", ""), "started": now})
        # Keep last 20
        state["active_sessions"] = sessions[-20:]

    elif event_type == "session_end":
        sessions = state.get("active_sessions", [])
        sid = event.get("session_id")
        state["active_sessions"] = [s for s in sessions if s.get("session_id") != sid]

    elif event_type == "meta_execute_start":
        state.setdefault("meta_execute_runs", []).append({
            "plan": event.get("plan"), "started": now, "status": "running"
        })

    elif event_type == "meta_execute_end":
        for run in state.get("meta_execute_runs", []):
            if run.get("plan") == event.get("plan") and run.get("status") == "running":
                run["status"] = event.get("status", "completed")
                run["ended"] = now
                break

    elif event_type == "sweep_action":
        state.setdefault("sweep_log", []).append({
            "action": event.get("action", ""), "time": now
        })
        state["sweep_log"] = state["sweep_log"][-100:]  # cap

    # NOTE: stage_transition events are NOT folded here. Plan stage/status is no
    # longer derived from the event log — it lives in each plan's YAML frontmatter
    # and is read live by the dashboard via plan-index.py. stage_transition rows
    # remain in state.events.jsonl purely as a HISTORY/timeline record.

    return state


def main():
    state = load_base()
    if not os.path.exists(EVENTS_FILE):
        json.dump(state, sys.stdout, indent=2)
        return

    with open(EVENTS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                state = fold(state, event)
            except json.JSONDecodeError:
                continue

    # Atomic write
    tmp = STATE_FILE + ".tmp"
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)

    json.dump(state, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
