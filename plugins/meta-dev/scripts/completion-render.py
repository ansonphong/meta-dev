#!/usr/bin/env python3
"""ASCII completion banner. Reads JSON from stdin or --test flag. ≤100 cols."""
import json, sys
from datetime import datetime

BANNER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ✦  meta-dev — COMPLETE  ✦                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

def render(data):
    lines = [BANNER, ""]
    lines.append(f"  Subject:      {data.get('subject','?')}")
    lines.append(f"  Stages:       {data.get('from','?')} → {data.get('to','?')}")
    lines.append(f"  Duration:     {data.get('duration','?')}")
    lines.append(f"  Completed:    {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("  ── Phase Results ──")
    for phase in data.get("phases", []):
        status = phase.get("status","?")
        icon = "✅" if status == "pass" else "❌" if status == "fail" else "⏸"
        lines.append(f"  {icon} {phase.get('name','?'):<20} {status:<6} {phase.get('detail','')}")
    lines.append("")
    stats = data.get("stats", {})
    lines.append(f"  Tasks:    {stats.get('total',0)} total → {stats.get('done',0)} done, {stats.get('failed',0)} failed")
    lines.append(f"  Commits:  {stats.get('commits',0)}")
    lines.append(f"  Files:    {stats.get('files_changed',0)} changed across {stats.get('modules',0)} modules")
    lines.append("")
    if data.get("deploy_status"):
        lines.append(f"  Deploy:   {data['deploy_status']}")
    if data.get("archive_path"):
        lines.append(f"  Archive:  {data['archive_path']}")
    lines.append("")
    lines.append("  ══════════════════════════════════════════════════════════════")
    lines.append("")
    if data.get("follow_ups"):
        lines.append("  Follow-ups:")
        for f in data["follow_ups"]: lines.append(f"    • {f}")
        lines.append("")
    return "\n".join(lines)

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--test":
        data = {
            "subject": "anon-funnel-optimize",
            "from": "brainstorm", "to": "shipped",
            "duration": "2h 14m",
            "phases": [
                {"name":"brainstorm","status":"pass","detail":"→ plans/anon-funnel/brainstorm.md"},
                {"name":"design","status":"pass","detail":"→ plans/anon-funnel/design.md"},
                {"name":"plan","status":"pass","detail":"3 phases, 14 tasks"},
                {"name":"harden","status":"pass","detail":"0 gaps after 2 iterations"},
                {"name":"execute","status":"pass","detail":"14/14 tasks DONE"},
                {"name":"review","status":"pass","detail":"grade B+, shipped"},
            ],
            "stats": {"total":14,"done":14,"failed":0,"commits":18,"files_changed":12,"modules":4},
            "deploy_status": "✅ Deployed to production (build #42)",
            "archive_path": "plans/_archive/anon-funnel-optimize/",
            "follow_ups": ["Monitor analytics for funnel conversion lift", "Consider A/B test on landing page variant"],
        }
    else:
        data = json.load(sys.stdin)
    output = render(data)
    for line in output.splitlines():
        print(line[:100])
