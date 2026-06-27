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

# Status markers use geometric/symbol glyphs, NOT emoji. Emoji are spec-width-2
# but many renderers (incl. inline markdown) draw them at 1 cell, which shifts
# every box border. These glyphs are width-1-stable, so the rounded boxes stay
# aligned everywhere. Real emoji are confined to the header line (outside boxes).
# Keyed on the plan-index status enum: done / blocked / active / draft.
GLYPH = {"done": "✓", "blocked": "!", "active": "→", "draft": "◦"}


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
        st = p.get("status", "draft")
        g = GLYPH.get(st, "◦")
        stg = p.get("stage", 0)
        stage_tag = f"  S{stg}·{st}"
        body.append(f"{g} {col(p.get('name', '?'), 22)} {bar(d, t)} {d:>3}/{t:<3} {pct(d, t)}{stage_tag}")
    body.append("─" * FIELD)
    body.append(f"   {col('TOTAL', 22)} {bar(td, tt)} {td:>3}/{tt:<3} {pct(td, tt)}")
    return body


def milestones_body(ms):
    if not ms:
        return ["(none)"]
    body = []
    for i, m in enumerate(ms):
        if i:
            body.append("─" * FIELD)
        typ = m.get("type", "MILESTONE")
        lbl = m.get("label", "")
        ver = m.get("version", "")
        tgt = m.get("target", "")
        d = m.get("plans_done", 0)
        t = m.get("plans_total", 0)
        body.append(col(f"{typ} · {lbl}", FIELD))
        meta = f"{bar(d, t)} {d}/{t} done"
        if ver:
            meta += f"   v{ver}"
        if tgt:
            meta += f"   target {tgt}"
        body.append(meta)
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


def commits_body(commits, expanded=False):
    if not commits:
        return ["(no commits)"]
    body = []
    for c in commits:
        sha = (c.get("sha", "?") or "?")[:8]
        msg = c.get("msg", "?")
        body.append(f"{sha:<8} {col(msg, FIELD - 9)}")
        if expanded:
            ago = c.get("ago", "")
            if ago and ago != "—":
                body.append(f"{'':<8} {col(ago, FIELD - 9)}")
    return body


def focus_body(f):
    """Single-plan deep-dive panel for --scope FILE."""
    if f.get("restricted"):
        return ["(scope restricted — this path is not available)"]
    if f.get("missing"):
        return [f"(no such plan file: {f.get('path', '?')})"]
    if f.get("malformed"):
        return [f"(could not read: {f.get('path', '?')})"]
    d = f.get("progress", {}) or {}
    done, total = d.get("done", 0), d.get("total", 0)
    body = [
        col(f.get("name", "?"), FIELD),
        f"status {f.get('status', '?')}   ·   stage {f.get('stage', '?')}"
        f"   ·   repo {f.get('repo', '—') or '—'}",
        f"{bar(done, total)} {done:>3}/{total:<3} {pct(done, total)}",
    ]
    why = f.get("why", "")
    if why:
        body.append(col("why: " + why, FIELD))
    secs = f.get("sections", [])
    if secs:
        body.append("─" * FIELD)
        for s in secs:
            sd, st = s.get("done", 0), s.get("total", 0)
            body.append(f"{col(s.get('title', '?'), 30)} {bar(sd, st)} {sd:>3}/{st:<3} {pct(sd, st)}")
    return body


# ── render ───────────────────────────────────────────────────────────────────
def _plans_panel(data):
    counts = data.get("counts", {}) or {}
    tracked = counts.get("tracked", len(data.get("plans", [])))
    title = f"Plans · {tracked} tracked"
    extra = []
    if counts.get("malformed"):
        extra.append(f"{counts['malformed']} malformed")
    untr = data.get("untracked", [])
    if untr:
        extra.append(f"{len(untr)} untracked")
    if extra:
        title += " · " + " · ".join(extra)
    return panel(title, plans_body(data.get("plans", [])))


def render_section(sec, data):
    """Render one named section to a list of lines, or None to skip it."""
    if sec == "plans":
        return _plans_panel(data)
    if sec == "focus":
        f = data.get("focus")
        if not f:
            return None
        return panel("Plan Focus", focus_body(f))
    if sec == "milestones":
        return panel("Milestones", milestones_body(data.get("milestones", [])))
    if sec == "sessions":
        return panel("Active Sessions", sessions_body(data.get("active_sessions", [])))
    if sec == "inbox":
        return panel("Inbox", inbox_body(data.get("inbox", {})))
    if sec == "sweep":
        sweep = data.get("sweep_log", [])
        if not sweep:
            return None  # conditional — only renders when there is activity
        return panel("Sweep Log · 24h", [f"✓ {s}" for s in sweep])
    if sec == "commits":
        commits = data.get("recent_commits", [])
        title = "Recent Commits"
        if data.get("commits_expanded"):
            title += f" · {len(commits)}"
        return panel(title, commits_body(commits, data.get("commits_expanded", False)))
    return None


# Default panel order when the data carries no explicit `sections` (e.g. --test).
DEFAULT_SECTIONS = ["plans", "milestones", "sessions", "inbox", "sweep", "commits"]


def render(data):
    L = []
    L.append(f"🎛  Control Plane — {data.get('project', 'meta-dev')}")
    L.append("")
    scope = data.get("scope")
    if scope:
        kind = data.get("scope_kind") or "scope"
        L.append(f"   scope: {scope}  ({kind})")
    L.append("   " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    L.append("")

    for sec in (data.get("sections") or DEFAULT_SECTIONS):
        block = render_section(sec, data)
        if block is None:
            continue
        L += block
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
        {"name": "auth-refactor", "tasks_done": 24, "tasks_total": 24, "status": "done", "stage": 6},
        {"name": "payments-v2", "tasks_done": 18, "tasks_total": 28, "status": "active", "stage": 5},
        {"name": "onboarding-flow", "tasks_done": 7, "tasks_total": 22, "status": "blocked", "stage": 4},
        {"name": "search-v3", "tasks_done": 0, "tasks_total": 14, "status": "draft", "stage": 2},
    ],
    "counts": {"tracked": 4, "malformed": 0, "archived": 0},
    "untracked": [],
    "milestones": [
        {"type": "PRODUCT LAUNCH", "label": "Public Beta", "version": "1.1.0-beta.1",
         "target": "2026-06-30", "plans_done": 1, "plans_total": 4},
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
