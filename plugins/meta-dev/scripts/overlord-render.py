#!/usr/bin/env python3
"""Render Overlord Dashboard from plan parse + git log + verdicts JSON."""
import json
import sys
from datetime import datetime


def render_bar(done: int, total: int, width: int = 10) -> str:
    if total == 0:
        return "░" * width
    filled = round(done / total * width)
    return "█" * filled + "░" * (width - filled)


def status_icon(status: str) -> str:
    return {"done": "✅", "in_flight": "\U0001f7e1", "pending": "⬜", "blocked": "\U0001f534", "gated": "⏸"}.get(status, "⬜")


def verdict_icon(verdict: str) -> str:
    return {"pass": "✅", "drift": "\U0001f7e1", "pending": "⏳", "failed": "\U0001f534"}.get(verdict, "❓")


def render(data: dict) -> str:
    lines = []
    plan_slug = data.get("plan_slug", "unknown")
    tick_n = data.get("tick_n", 0)
    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    poll = data.get("poll_interval", "event-driven")
    executor = data.get("executor_label", "Sonnet")

    lines.append(f"\U0001f6df️ Overlord Dashboard — {plan_slug}")
    lines.append(f"Tick {tick_n} · {date} · poll: {poll} · executor: {executor}")
    lines.append("")

    # Progress bars
    lines.append("Progress")
    lines.append("")
    total_done = 0
    total_tasks = 0
    for phase in data.get("phases", []):
        name = phase.get("name", "?")
        done = phase.get("done", 0)
        total = phase.get("total", 0)
        status = phase.get("status", "pending")
        bar = render_bar(done, total)
        icon = status_icon(status)
        lines.append(f"  {name:<20} {bar} {done}/{total}  {icon}")
        total_done += done
        total_tasks += total

    pct = round(total_done / total_tasks * 100) if total_tasks > 0 else 0
    lines.append(f"  {'─' * 45}")
    lines.append(f"  {'TOTAL':<20} {render_bar(total_done, total_tasks)} {total_done}/{total_tasks}  {pct}%")
    lines.append("")

    # Commit verdict table
    commits = data.get("commits", [])
    if commits:
        lines.append(f"Last {len(commits)} commits ({executor} trail)")
        lines.append("")
        lines.append(f"  {'Commit':<10} {'Task':<24} {'Verdict':<32}")
        lines.append(f"  {'─' * 10} {'─' * 24} {'─' * 32}")
        for c in commits[:10]:
            sha = c.get("sha", "")[:8]
            task = c.get("task", "")[:22]
            verdict = c.get("verdict", "pending")
            note = c.get("note", "")[:28]
            icon = verdict_icon(verdict)
            lines.append(f"  {sha:<10} {task:<24} {icon} {note}")
        lines.append("")

    # Findings
    findings = data.get("findings", [])
    if findings:
        lines.append(f"\U0001f534 Findings ({len(findings)})")
        lines.append("")
        for i, f in enumerate(findings[:20], 1):
            sev = f.get("severity", "?")
            desc = f.get("description", "")
            ref = f.get("ref", "")
            action = f.get("action", "")
            lines.append(f"  {i}. [{sev}] {desc} — {ref} — {action}")
        lines.append("")

    # Next checkpoint
    next_up = data.get("next_up", {})
    if next_up:
        lines.append(f"Next checkpoint")
        lines.append("")
        lines.append(f"  Up next: {next_up.get('id', '?')} ({next_up.get('title', '?')})")
        lines.append(f"  Checkpoint: {next_up.get('checkpoint', '?')}")
        lines.append("")

    # Next tick
    next_tick = data.get("next_tick", {})
    if next_tick:
        lines.append(f"Tick {next_tick.get('n', '?')} in {next_tick.get('in', '?')}. {next_tick.get('plan', '')}")

    return "\n".join(lines)


if __name__ == "__main__":
    if "--test" in sys.argv:
        sample = {
            "plan_slug": "meta-dev-plugin",
            "tick_n": 3,
            "date": "2026-05-11",
            "poll_interval": "20m",
            "executor_label": "Sonnet",
            "phases": [
                {"name": "Phase 0: Scaffold", "done": 1, "total": 1, "status": "done"},
                {"name": "Phase 1: Config", "done": 5, "total": 5, "status": "done"},
                {"name": "Phase 2: Scripts", "done": 4, "total": 6, "status": "in_flight"},
                {"name": "Phase 3: Hooks", "done": 0, "total": 2, "status": "gated"},
            ],
            "commits": [
                {"sha": "3a4fcf9d", "task": "T2.4 inbox scripts", "verdict": "drift", "note": "missing test for dedup"},
                {"sha": "6dc0e1a3", "task": "T2.3 version scripts", "verdict": "pass", "note": ""},
                {"sha": "a1b2c3d4", "task": "T2.2 changelog scripts", "verdict": "pending", "note": ""},
            ],
            "findings": [
                {"severity": "moderate", "description": "Checkbox drift on T2.4", "ref": "master-plan.md:164", "action": "auto-fix on next tick"},
            ],
            "next_up": {"id": "T2.5", "title": "sweep scripts", "checkpoint": "CHECKPOINT Phase 2"},
            "next_tick": {"n": 4, "in": "20 min", "plan": "check git log delta, review T2.4-T2.5"},
        }
        print(render(sample))
    else:
        data = json.load(sys.stdin) if not sys.stdin.isatty() else {}
        print(render(data))
