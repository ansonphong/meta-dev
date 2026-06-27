#!/usr/bin/env python3
"""Dashboard renderer. Reads JSON from stdin, prints a boxed control-plane view.

Display-width aware: emoji render as 2 terminal cells but count as 1 codepoint
in len(), so every pad/truncate uses dwidth() instead of len() — that is what
keeps the rounded box borders aligned (the reason earlier versions fell back to
flat text).
"""
import json
import sys
import unicodedata
from datetime import datetime

BOX_W = 74            # total visible width including both borders
FIELD = BOX_W - 4     # text field inside "│ … │"
BAR_W = 18

# Status markers use geometric dots, NOT emoji. Emoji are spec-width-2 but many
# renderers (incl. inline markdown) draw them at 1 cell, which shifts every box
# border. Dots are width-1-stable, so the rounded boxes stay aligned everywhere.
# Real emoji are confined to the header line, which sits outside every box.
GLYPH = {"done": "●", "inflight": "◐", "pending": "○", "blocked": "◆", "paused": "◌"}


# ── display width ────────────────────────────────────────────────────────────
def _cw(ch):
    o = ord(ch)
    if o == 0x200D or 0xFE00 <= o <= 0xFE0F:      # ZWJ + variation selectors
        return 0
    if unicodedata.combining(ch):
        return 0
    if 0x1F000 <= o <= 0x1FAFF:                   # true emoji / pictographs only
        return 2
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1


def dwidth(s):
    return sum(_cw(c) for c in s)


def fit(s, w):
    """Pad or truncate s to EXACTLY w display cells."""
    if dwidth(s) > w:
        out, cur = "", 0
        for ch in s:
            cw = _cw(ch)
            if cur + cw > w - 1:
                break
            out += ch
            cur += cw
        out += "…"
        cur += 1
        return out + " " * (w - cur)
    return s + " " * (w - dwidth(s))


def col(s, n):
    return fit(s, n)


# ── box primitives ───────────────────────────────────────────────────────────
def _top():
    return "╭" + "─" * (BOX_W - 2) + "╮"


def _bottom():
    return "╰" + "─" * (BOX_W - 2) + "╯"


def _sep():
    return "├" + "─" * (BOX_W - 2) + "┤"


def _row(text=""):
    return "│ " + fit(text, FIELD) + " │"


def _rule():
    return "│ " + "─" * FIELD + " │"


def panel(title, body):
    out = [_top(), _row(title.upper()), _sep()]
    out += [_row(line) for line in body] if body else [_row("(empty)")]
    out.append(_bottom())
    return out


def bar(d, t):
    if t <= 0:
        return "░" * BAR_W
    f = max(0, min(BAR_W, round(BAR_W * d / t)))
    return "█" * f + "░" * (BAR_W - f)


def pct(d, t):
    return f"{int(100 * d / t):>3d}%" if t > 0 else "  —"


# ── sections ─────────────────────────────────────────────────────────────────
def plans_body(plans):
    if not plans:
        return ["(no active plans — run /meta-init)"]
    body = []
    td = tt = 0
    for p in plans:
        d = p.get("tasks_done", 0)
        t = p.get("tasks_total", 0)
        td += d
        tt += t
        st = p.get("status", "pending")
        g = GLYPH.get(st, "⬜")
        stg = p.get("stage")
        if stg:
            sn = p.get("stage_num")
            ss = p.get("stage_status", "")
            mark = "✓" if ss == "completed" else ("!" if ss == "blocked" else "→")
            stage_tag = f"  S{sn if sn else '?'}·{stg}{mark}"
        else:
            stage_tag = ""
        body.append(f"{g} {col(p.get('name', '?'), 22)} {bar(d, t)} {d:>3}/{t:<3} {pct(d, t)}{stage_tag}")
    body.append("─" * FIELD)
    body.append(f"   {col('TOTAL', 22)} {bar(td, tt)} {td:>3}/{tt:<3} {pct(td, tt)}")
    return body


def sessions_body(sess):
    if not sess:
        return ["(none active)"]
    body = [f"{col('SESSION', 16)}  {col('PLAN', 18)}  {col('TASK', 8)}  {col('STAGE', 10)}"]
    for s in sess:
        body.append(
            f"{col(s.get('session', '?'), 16)}  {col(s.get('plan', '—'), 18)}  "
            f"{col(s.get('task', '—'), 8)}  {col(s.get('stage', '—'), 10)}"
        )
    return body


def inbox_body(inbox):
    adv = inbox.get("advisories", 0)
    iss = inbox.get("issues_open", 0)
    auto = inbox.get("auto_clearable", 0)
    body = [f"advisories {adv}   ·   issues {iss}   ·   auto-clearable {auto}"]
    if auto:
        body.append(f"→ /meta-inbox clear all   ({auto} auto-clearable)")
    elif iss:
        body.append("→ /meta-inbox   to triage open issues")
    return body


def commits_body(commits):
    if not commits:
        return ["(no commits)"]
    return [f"{c.get('sha', '?'):<8} {col(c.get('msg', '?'), FIELD - 9)}" for c in commits]


# ── render ───────────────────────────────────────────────────────────────────
def render(data):
    L = []
    L.append(f"🎛  Control Plane — {data.get('project', 'meta-dev')}")
    L.append("")
    L.append("   " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    L.append("")

    L += panel("Plans", plans_body(data.get("plans", [])))
    L.append("")
    L += panel("Active Sessions", sessions_body(data.get("active_sessions", [])))
    L.append("")
    L += panel("Inbox", inbox_body(data.get("inbox", {})))
    L.append("")
    sweep = data.get("sweep_log", [])
    if sweep:
        L += panel("Sweep Log · 24h", [f"✓ {s}" for s in sweep])
        L.append("")
    L += panel("Recent Commits", commits_body(data.get("recent_commits", [])))
    L.append("")

    r = data.get("refresh_rate", "once")
    a = data.get("agent_count", 0)
    di = data.get("dirty_count", 0)
    up = data.get("unpushed_count", 0)
    L.append(f"   refresh {r}  ·  agents {a}  ·  dirty {di}  ·  unpushed {up}")
    L.append("")
    L.append("   [ new idea ]  [ plan ]  [ execute ]  [ review ]  [ ship ]  [ overlord ]")
    return "\n".join(L)


TEST_DATA = {
    "project": "meta-dev",
    "plans": [
        {"name": "auth-refactor", "tasks_done": 24, "tasks_total": 24, "status": "done"},
        {"name": "payments-v2", "tasks_done": 18, "tasks_total": 28, "status": "inflight"},
        {"name": "onboarding-flow", "tasks_done": 7, "tasks_total": 22, "status": "inflight"},
        {"name": "search-v3", "tasks_done": 0, "tasks_total": 14, "status": "pending"},
    ],
    "active_sessions": [
        {"session": "meta-exec-03", "plan": "payments-v2", "task": "P4.3/7", "stage": "review"},
        {"session": "overlord-watch", "plan": "payments-v2", "task": "—", "stage": "reviewing"},
    ],
    "inbox": {"advisories": 2, "issues_open": 7, "auto_clearable": 4},
    "sweep_log": [
        "archived 2 stale plans — search-prototype, api-experiment",
        "wip commit on 3 untracked files",
    ],
    "recent_commits": [
        {"sha": "a7f3d92", "msg": "feat(api): add order webhook handler", "ago": "—"},
        {"sha": "b2e8c41", "msg": "fix(auth): resolve token refresh race", "ago": "—"},
        {"sha": "9c1d5f6", "msg": "chore(plan): mark P4.2 checkboxes DONE", "ago": "—"},
    ],
    "refresh_rate": "fast",
    "agent_count": 2,
    "dirty_count": 3,
    "unpushed_count": 0,
}


if __name__ == "__main__":
    data = TEST_DATA if (len(sys.argv) > 1 and sys.argv[1] == "--test") else json.load(sys.stdin)
    print(render(data))
