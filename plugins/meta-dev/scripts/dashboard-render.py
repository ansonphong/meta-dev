#!/usr/bin/env python3
"""Dashboard renderer. Reads JSON from stdin. Prints clean inline output."""
import json, sys
from datetime import datetime

GLYPH = {"done": "✅", "inflight": "🟡", "pending": "⬜", "blocked": "🔴", "paused": "⏸"}
BAR_W = 10


def bar(done, total):
    if total == 0:
        return "░" * BAR_W
    filled = round(BAR_W * done / total)
    return "█" * filled + "░" * (BAR_W - filled)


def trunc(s, n):
    return s if len(s) <= n else s[:n - 1] + "…"


def render(data):
    lines = []
    project = data.get("project", "meta-dev")
    lines.append(f"🎛  Control Plane — {project}")
    lines.append("")
    lines.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("")

    # Plans
    plans = data.get("plans", [])
    tot_done = 0
    tot_total = 0
    if plans:
        lines.append("Plans")
        for p in plans:
            d = p.get("tasks_done", 0)
            t = p.get("tasks_total", 0)
            tot_done += d
            tot_total += t
            st = p.get("status", "pending")
            g = GLYPH.get(st, "⬜")
            name = trunc(p["name"], 28)
            pct = f"{int(100 * d / t):3d}%" if t > 0 else "  —"
            lines.append(f"  {name:<28}  {bar(d, t)}  {d:>2}/{t:<2}  {pct}  {g} {st}")
        lines.append("  " + "─" * 72)
        total_pct = f"{int(100 * tot_done / tot_total):3d}%" if tot_total > 0 else "  —"
        lines.append(f"  {'TOTAL':<28}  {bar(tot_done, tot_total)}  {tot_done:>2}/{tot_total:<2}  {total_pct}")
    else:
        lines.append("Plans")
        lines.append("  (no active plans found — run /meta-init)")
    lines.append("")

    # Active Sessions
    lines.append("Active Sessions")
    sess = data.get("active_sessions", [])
    if sess:
        lines.append(f"  {'Session':<16}  {'Plan':<20}  {'Task':<8}  {'Stage':<10}")
        lines.append(f"  {'─' * 16}  {'─' * 20}  {'─' * 8}  {'─' * 10}")
        for s in sess:
            lines.append(
                f"  {trunc(s.get('session', '?'), 16):<16}  "
                f"{trunc(s.get('plan', '?'), 20):<20}  "
                f"{trunc(s.get('task', '?'), 8):<8}  "
                f"{trunc(s.get('stage', '?'), 10):<10}"
            )
    else:
        lines.append("  (none)")
    lines.append("")

    # Inbox
    inbox = data.get("inbox", {})
    adv = inbox.get("advisories", 0)
    iss = inbox.get("issues_open", 0)
    auto = inbox.get("auto_clearable", 0)
    lines.append(f"Inbox — Advisories: {adv}  |  Issues: {iss}  |  Auto-clearable: {auto}")
    lines.append("")

    # Sweep log
    sweep = data.get("sweep_log", [])
    if sweep:
        lines.append("Sweep Log (24h)")
        for s in sweep:
            lines.append(f"  ✓ {trunc(str(s), 90)}")
        lines.append("")

    # Recent commits
    lines.append("Recent Commits")
    for c in data.get("recent_commits", []):
        sha = c.get("sha", "?")
        msg = trunc(c.get("msg", "?"), 72)
        ago = c.get("ago", "—")
        lines.append(f"  {sha}  {msg}  ({ago})")
    lines.append("")

    # Footer
    r = data.get("refresh_rate", "once")
    a = data.get("agent_count", 0)
    di = data.get("dirty_count", 0)
    up = data.get("unpushed_count", 0)
    lines.append(f"  refresh: {r}  ·  agents: {a}  ·  dirty: {di}  ·  unpushed: {up}")
    lines.append("")
    lines.append("  [new idea]  [plan]  [execute]  [review]  [ship]  [overlord]")
    return "\n".join(lines)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--test":
        data = {
            "project": "acme-platform",
            "plans": [
                {"name": "auth-refactor", "tasks_done": 24, "tasks_total": 24, "status": "done"},
                {"name": "payments-v2", "tasks_done": 18, "tasks_total": 28, "status": "inflight"},
                {"name": "onboarding-flow", "tasks_done": 7, "tasks_total": 22, "status": "inflight"},
                {"name": "search-v3", "tasks_done": 0, "tasks_total": 14, "status": "pending"},
            ],
            "active_sessions": [
                {"session": "meta-exec-03", "plan": "payments-v2", "task": "P4.3/7", "stage": "review"},
                {"session": "meta-exec-04", "plan": "onboarding-flow", "task": "P2.1/5", "stage": "implement"},
                {"session": "overlord-watch", "plan": "payments-v2", "task": "—", "stage": "reviewing"},
            ],
            "inbox": {"advisories": 2, "issues_open": 7, "auto_clearable": 4},
            "sweep_log": [
                "archived 2 stale plans — search-prototype, api-experiment (14:00 UTC)",
                "wip commit on 3 untracked files (13:15 UTC)",
            ],
            "recent_commits": [
                {"sha": "a7f3d92", "msg": "feat(payments): add Stripe webhook handler", "ago": "2 min"},
                {"sha": "b2e8c41", "msg": "fix(auth): resolve token refresh race", "ago": "14 min"},
                {"sha": "9c1d5f6", "msg": "chore(plan): mark P4.2 checkboxes DONE", "ago": "31 min"},
                {"sha": "e4f7a83", "msg": "feat(payments): implement checkout session create", "ago": "1 hr"},
                {"sha": "d3a2b71", "msg": "test(payments): add webhook signature verification", "ago": "2 hr"},
            ],
            "refresh_rate": "fast",
            "agent_count": 2,
            "dirty_count": 3,
            "unpushed_count": 0,
        }
    else:
        data = json.load(sys.stdin)
    output = render(data)
    for line in output.splitlines():
        print(line[:100])
