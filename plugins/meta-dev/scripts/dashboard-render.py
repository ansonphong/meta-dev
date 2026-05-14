#!/usr/bin/env python3
"""ASCII dashboard renderer. Reads JSON from stdin or file. Prints ≤100-col frame."""
import json, sys, os
from datetime import datetime

GLYPH = {"done":"✅","inflight":"🟡","pending":"⬜","blocked":"🔴","paused":"⏸"}
BAR_W = 10

def bar(done, total):
    if total == 0: return "░" * BAR_W
    filled = round(BAR_W * done / total)
    return "█" * filled + "░" * (BAR_W - filled)

def fmt_pct(done, total):
    if total == 0: return "  0%"
    return f"{100*done//total:3d}%"

def render(data):
    lines = []
    lines.append(f"🎛  Control Plane — {data.get('project','meta-dev')}")
    lines.append("")
    lines.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("")
    lines.append("Plans")
    plans = data.get("plans", [])
    tot_done = tot_total = 0
    for p in plans:
        d = p.get("tasks_done",0); t = p.get("tasks_total",0)
        tot_done += d; tot_total += t
        st = p.get("status","pending")
        g = GLYPH.get(st, GLYPH["pending"])
        over = "  (overlord active)" if p.get("overlord") else ""
        lines.append(f"  {p['name']:<30} {bar(d,t)} {d:>2}/{t:<2}    {g} {st}{over}")
    lines.append("  " + "─" * 60)
    lines.append(f"  {'TOTAL':<30} {bar(tot_done,tot_total)} {tot_done:>2}/{tot_total:<2}    {fmt_pct(tot_done,tot_total)}")
    lines.append("")
    lines.append("Active Sessions")
    sess = data.get("active_sessions", [])
    if sess:
        lines.append(f"  {'Session':<16} {'Plan':<20} {'Task':<8} {'Stage':<10}")
        lines.append(f"  {'─'*16} {'─'*20} {'─'*8} {'─'*10}")
        for s in sess:
            lines.append(f"  {s.get('session','?'):<16} {s.get('plan','?'):<20} {s.get('task','?'):<8} {s.get('stage','?'):<10}")
    else:
        lines.append("  (none)")
    lines.append("")
    inbox = data.get("inbox", {})
    adv = inbox.get("advisories",0); iss = inbox.get("issues_open",0); auto = inbox.get("auto_clearable",0)
    lines.append(f"Inbox — Advisories: {adv}  Issues: {iss}  Auto-clearable: {auto}")
    lines.append("")
    sweep = data.get("sweep_log", [])
    if sweep:
        lines.append("Sweep Log (last 24h)")
        for s in sweep: lines.append(f"  ✓ {s}")
        lines.append("")
    lines.append("Recent Commits")
    for c in data.get("recent_commits", []):
        lines.append(f"  {c.get('sha','?'):7} {c.get('msg','?')}  ({c.get('ago','?')})")
    lines.append("")
    r = data.get("refresh_rate","once")
    a = data.get("agent_count","?")
    di = data.get("dirty_count",0)
    up = data.get("unpushed_count",0)
    lines.append(f"  refresh: {r}  ·  agents: {a} haiku  ·  dirty: {di}  ·  unpushed: {up}")
    lines.append("")
    lines.append("  [new idea] [plan] [execute] [review] [ship] [overlord]")
    return "\n".join(lines)

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--test":
        data = {
            "project": "demo",
            "plans": [
                {"name":"anon-funnel","tasks_done":22,"tasks_total":66,"status":"inflight","overlord":True},
                {"name":"pwa-polish","tasks_done":14,"tasks_total":14,"status":"done"},
                {"name":"dream-filters","tasks_done":0,"tasks_total":8,"status":"pending"},
            ],
            "active_sessions": [{"session":"meta-exec-02","plan":"Anon Funnel Invert","task":"P4/7","stage":"verify"}],
            "inbox": {"advisories":2,"issues_open":2,"auto_clearable":1},
            "sweep_log": ["archived 2 stale plans (2026-05-11 14:00)", "wip commit on 3 untracked files (2026-05-11 13:15)"],
            "recent_commits": [{"sha":"abc1234","msg":"feat: add funnel invert","ago":"2h"}],
            "refresh_rate":"30s","agent_count":3,"dirty_count":0,"unpushed_count":0,
        }
    else:
        data = json.load(sys.stdin)
    output = render(data)
    for line in output.splitlines():
        print(line[:100])
