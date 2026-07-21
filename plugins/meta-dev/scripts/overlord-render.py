#!/usr/bin/env python3
"""Render the Overlord dashboard from plan parse + git log + verdicts JSON.

One card, CARD_W wide, on the shared open-right chassis — see
references/status-cards.md. This renderer used to be box-free at 100 cols with
its own emoji set and its own 10-wide bar; both are gone. Glyphs come from
render_lib.mark()/label() (the ONE vocabulary) and the bar from render_lib.bar()
(width is a parameter, not a second implementation).
"""
import json
import os
import sys
from datetime import datetime

# ── shared render primitives — ONE source (planctl.render_lib) ────────────────
# planctl/ is a sibling package inside scripts/, so scripts/ is what goes on the
# path. There is deliberately NO try/except fallback: a silent inline copy is
# exactly how renderers drift from render_lib while appearing to import it. A
# missing module must fail loudly.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from planctl.render_lib import (
    CARD_FIELD,
    mark, label,
    dwidth, fit, cols, card,
    bar, pct,
)

BAR_CELLS = 10          # overlord's historical bar width, now just a parameter
NAME_W = 18             # phase-name column — narrowed from 20 to fit CARD_W
SHA_W, TASK_W = 10, 24  # commit table columns

# ── local vocabulary → the ONE status vocabulary ──────────────────────────────
# Overlord speaks its own phase/verdict words. These tables translate them into
# canonical statuses; the glyphs themselves live only in render_lib.STATUS.
PHASE_STATUS = {
    "done": "done",
    "in_flight": "executing",
    "pending": "ready",
    "blocked": "blocked",
    "gated": "gated",
}
VERDICT_STATUS = {
    "pass": "done",
    "pending": "needs-review",
    "failed": "blocked",
}


def _clip(s):
    """Keep a composed row inside the open-right field (no right border to
    truncate against). rstrip() drops fit()'s tail padding."""
    return (s if dwidth(s) <= CARD_FIELD else fit(s, CARD_FIELD)).rstrip()


def phase_mark(status):
    """Glyph for a phase status. Unknown → render_lib's UNKNOWN, never a guess."""
    return mark(PHASE_STATUS.get(status, status))


def verdict_mark(verdict):
    """Glyph for a review verdict. ``drift`` is a passing verdict carrying the
    canonical drift suffix — not a status of its own."""
    if verdict == "drift":
        return mark("done", drift=True)
    return mark(VERDICT_STATUS.get(verdict, verdict))


# ── sections ─────────────────────────────────────────────────────────────────
def progress_body(phases):
    rows, td, tt = [], 0, 0
    for ph in phases:
        d = ph.get("done", 0)
        t = ph.get("total", 0)
        td += d
        tt += t
        rows.append(_clip(cols(
            [ph.get("name", "?"), bar(d, t, BAR_CELLS), f"{d}/{t}",
             phase_mark(ph.get("status", "pending"))],
            [NAME_W, BAR_CELLS, 7],
        )))
    rows.append("─" * CARD_FIELD)
    rows.append(_clip(cols(
        ["TOTAL", bar(td, tt, BAR_CELLS), f"{td}/{tt}", pct(td, tt)],
        [NAME_W, BAR_CELLS, 7],
    )))
    return rows


def commits_body(commits):
    rows = [
        cols(["Commit", "Task", "Verdict"], [SHA_W, TASK_W]),
        cols(["─" * SHA_W, "─" * TASK_W, "─" * 28], [SHA_W, TASK_W]),
    ]
    for c in commits[:10]:
        verdict = c.get("verdict", "pending")
        note = c.get("note", "") or label(VERDICT_STATUS.get(verdict, verdict))
        rows.append(_clip(cols(
            [c.get("sha", "")[:8], c.get("task", ""),
             f"{verdict_mark(verdict)} {note}"],
            [SHA_W, TASK_W],
        )))
    return rows


def findings_body(findings):
    rows = []
    for i, f in enumerate(findings[:20], 1):
        rows.append(_clip(f"{mark('blocked')} {i}. [{f.get('severity', '?')}] "
                          f"{f.get('description', '')}"))
        tail = " — ".join(x for x in (f.get("ref", ""), f.get("action", "")) if x)
        if tail:
            rows.append(_clip(f"      {tail}"))
    return rows


def next_body(next_up, next_tick):
    rows = []
    if next_up:
        rows.append(_clip(f"Up next:    {next_up.get('id', '?')} "
                          f"({next_up.get('title', '?')})"))
        rows.append(_clip(f"Checkpoint: {next_up.get('checkpoint', '?')}"))
    if next_tick:
        rows.append(_clip(f"Tick {next_tick.get('n', '?')} in "
                          f"{next_tick.get('in', '?')}. {next_tick.get('plan', '')}"))
    return rows


# ── render ───────────────────────────────────────────────────────────────────
def render(data: dict) -> str:
    plan_slug = data.get("plan_slug", "unknown")
    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    poll = data.get("poll_interval", "event-driven")
    executor = data.get("executor_label", "Sonnet")

    sections = [(None, [_clip(
        f"Tick {data.get('tick_n', 0)} · {date} · poll: {poll} · executor: {executor}"
    )])]
    sections.append(("Progress", progress_body(data.get("phases", []))))

    commits = data.get("commits", [])
    if commits:
        sections.append((f"Commits · last {len(commits)} ({executor} trail)",
                         commits_body(commits)))

    findings = data.get("findings", [])
    if findings:
        sections.append((f"Findings · {len(findings)}", findings_body(findings)))

    nxt = next_body(data.get("next_up", {}), data.get("next_tick", {}))
    if nxt:
        sections.append(("Next", nxt))

    return "\n".join(card(f"Overlord Dashboard — {plan_slug}", sections))


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
