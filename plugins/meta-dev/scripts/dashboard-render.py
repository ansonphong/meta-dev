#!/usr/bin/env python3
"""Dashboard renderer. Reads JSON from stdin, prints a boxed control-plane view.

Display-width aware: emoji render as 2 terminal cells but count as 1 codepoint
in len(), so every pad/truncate uses dwidth() instead of len() — that is what
keeps the rounded box borders aligned. Shared render primitives imported from
planctl.render_lib (one source for global + boxed views, 2a/2b).

Phase 2a: runbook-aware — campaign members grouped under runbook headers with
rollup bars; derived glyphs (⊙ needs-review, ▹ ready, ✓⚠ drift); override
notes (‖ parked, ⌀ superseded).
"""
import json
import os
import sys
from datetime import datetime

# ── shared render primitives — ONE source (planctl.render_lib) ────────────────
# planctl/ is a sibling package inside scripts/, so scripts/ is what goes on the
# path. There is deliberately NO try/except fallback: a silent inline copy is
# exactly how this renderer drifted from render_lib for months while appearing
# to import it. A missing module must fail loudly.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from planctl.render_lib import (
    BOX_W, FIELD, BAR_W,
    GLYPH, status_glyph,
    dwidth, fit, col,
    box_top, box_bottom, box_sep, box_row, box_rule, panel,
    bar, pct,
)


# ── plan name helper ──────────────────────────────────────────────────────────
def _plan_name(path):
    """Extract a short display name from a plan path."""
    import re, os
    base = os.path.basename(path)
    if "master-plan" in base:
        nm = os.path.basename(os.path.dirname(path))
    else:
        nm = os.path.splitext(base)[0]
    return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", nm)


# ── runbook name helper ───────────────────────────────────────────────────────
def _runbook_label(path):
    """Short label from a runbook path (the parent dir or filename slug)."""
    import re, os
    parts = path.split("/")
    if len(parts) >= 2:
        parent = parts[-2]
        if parent and parent != "plans":
            name = parent.replace("-", " ").replace("_", " ")
            name = re.sub(r"\s+", " ", name).strip()
            if name:
                return name.upper()
    base = parts[-1]
    name = re.sub(r"^_runbook-|\.md$", "", base, flags=re.IGNORECASE)
    name = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", name)
    name = name.replace("-", " ").replace("_", " ")
    name = re.sub(r"\s+", " ", name).strip()
    return name.upper() if name else path


# ── sections ─────────────────────────────────────────────────────────────────
def plans_body(plans, runbooks=None):
    """Build the Plans panel body, runbook-aware.

    Plans are grouped by ``runbook_group``. Ungrouped plans appear first,
    then each runbook group with a header row + rollup bar. Plans show
    derived glyphs + override notes + drift markers.
    """
    if not plans:
        return ["(no active plans — run /meta-init)"]

    # Index runbooks by path for quick lookup
    rb_index = {}
    if runbooks:
        for r in runbooks:
            rb_index[r.get("path", "")] = r

    # Partition plans: grouped vs ungrouped
    groups = {}   # runbook_path → [plan, ...]
    ungrouped = []
    for p in plans:
        rg = p.get("runbook_group")
        if rg:
            groups.setdefault(rg, []).append(p)
        else:
            ungrouped.append(p)

    body = []
    td = tt = 0  # grand totals

    def _stage_tag(p, ds, stg):
        """Canonical stage-state marker plus the informational smoke badge."""
        stage_state = p.get("stage_state")
        if stage_state == "active":
            tag = f"  → {stg}"
            if stg >= 6:
                tag += " (👀)"
        elif stage_state == "done":
            tag = "  ✓ done" if stg >= 6 else f"  ✓ {stg}"
        else:
            # No stage_state is the legacy path: preserve its old rendering.
            tag = f"  S{stg}·{ds}"

        override = p.get("override")
        if override:
            note = p.get("note", "")
            note_str = f" — {note}" if note else ""
            tag = f"  {override}{note_str}"

        smoke = p.get("smoke") or 0
        if smoke > 0:
            tag += f"  · 👁 {smoke} smoke"
        return tag

    # Keep every plan column aligned while reserving enough display cells for
    # the widest marker/badge. dwidth() counts 👁 and 👀 as two cells.
    count_w = max(5, max(dwidth(f"{p.get('tasks_done', 0)}/{p.get('tasks_total', 0)}")
                         for p in plans))
    glyph_w = max(dwidth(status_glyph(
        p.get("derived_status") or p.get("status", "draft"),
        p.get("drift", False),
    )) for p in plans)
    state_rows = [p for p in plans
                  if p.get("stage_state") in ("active", "done")
                  or (p.get("smoke") or 0) > 0]
    tag_w = max((dwidth(_stage_tag(
        p,
        p.get("derived_status") or p.get("status", "draft"),
        p.get("stage", 0),
    )) for p in state_rows), default=0)
    # Spaces and fixed fields outside the name consume 26 cells.
    name_w = max(1, min(22, FIELD - glyph_w - count_w - tag_w - 26))

    def _append_plan_row(p):
        nonlocal td, tt
        d = p.get("tasks_done", 0)
        t = p.get("tasks_total", 0)
        td += d; tt += t

        ds = p.get("derived_status") or p.get("status", "draft")
        drift = p.get("drift", False)
        g = status_glyph(ds, drift)
        stg = p.get("stage", 0)
        stage_tag = _stage_tag(p, ds, stg)
        count = f"{d}/{t}"

        body.append(
            f"{col(g, glyph_w)} {col(p.get('name', '?'), name_w)} {bar(d, t)} "
            f"{col(count, count_w)} {pct(d, t)}{stage_tag}"
        )

    def _append_runbook_header(rb_path, member_plans):
        """Header row + rollup bar for a runbook group."""
        rb = rb_index.get(rb_path, {})
        md = rb.get("members_done", 0)
        mt = rb.get("members_total", len(member_plans))
        rd = rb.get("tasks_done", 0)
        rt = rb.get("tasks_total", 0)
        label = _runbook_label(rb_path)

        body.append(box_rule())
        body.append(
            f"▸ {col(label, name_w)} {bar(md, mt)} {col(f'{md}/{mt}', count_w)} {pct(md, mt)}"
            f"  · {rd}/{rt} tasks"
        )

    # ── Ungrouped plans first ──────────────────────────────────────────────
    for p in ungrouped:
        _append_plan_row(p)

    # ── Runbook groups ─────────────────────────────────────────────────────
    # Sort groups by runbook path for stable output
    for rb_path in sorted(groups.keys()):
        member_plans = groups[rb_path]
        # Sort members within group by Sequence order (preserved from input)
        _append_runbook_header(rb_path, member_plans)
        for p in member_plans:
            _append_plan_row(p)

    # ── Grand total ────────────────────────────────────────────────────────
    body.append("─" * FIELD)
    body.append(
        f"{col('', glyph_w)} {col('TOTAL', name_w)} {bar(td, tt)} "
        f"{td}/{tt} {pct(td, tt)}"
    )
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
    return panel(title, plans_body(data.get("plans", []), data.get("runbooks", [])))


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
            return None
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


# ── TEST_DATA (extended with runbook groups + derived_status) ────────────────
TEST_DATA = {
    "project": "meta-dev",
    "plans": [
        {"name": "auth-refactor", "path": "plans/app/auth-refactor/00-master-plan.md",
         "repo": "app", "tasks_done": 24, "tasks_total": 24,
         "status": "done", "derived_status": "done", "stage": 6, "why": "",
         "runbook_group": None, "malformed": False},
        {"name": "payments-v2", "path": "plans/app/payments-v2/00-master-plan.md",
         "repo": "app", "tasks_done": 18, "tasks_total": 28,
         "status": "active", "derived_status": "executing", "stage": 5, "why": "",
         "runbook_group": "plans/app/_runbook-commerce.md", "malformed": False},
        {"name": "checkout-flow", "path": "plans/app/checkout-flow/00-master-plan.md",
         "repo": "app", "tasks_done": 7, "tasks_total": 22,
         "status": "blocked", "derived_status": "blocked", "stage": 4, "why": "",
         "override": "blocked", "note": "waiting on payments-v2",
         "runbook_group": "plans/app/_runbook-commerce.md", "malformed": False},
        {"name": "onboarding-flow", "path": "plans/app/onboarding/00-master-plan.md",
         "repo": "app", "tasks_done": 12, "tasks_total": 12,
         "status": "active", "derived_status": "needs-review", "stage": 5, "why": "",
         "runbook_group": None, "malformed": False},
        {"name": "search-v3", "path": "plans/app/search-v3/00-master-plan.md",
         "repo": "app", "tasks_done": 0, "tasks_total": 14,
         "status": "draft", "derived_status": "draft", "stage": 2, "why": "",
         "runbook_group": None, "malformed": False},
        {"name": "drift-plan", "path": "plans/app/drift-plan/00-master-plan.md",
         "repo": "app", "tasks_done": 3, "tasks_total": 5,
         "status": "done", "derived_status": "done", "stage": 6, "why": "",
         "drift": True, "runbook_group": None, "malformed": False},
        {"name": "parked-feature", "path": "plans/app/parked/00-design.md",
         "repo": "app", "tasks_done": 2, "tasks_total": 8,
         "status": "blocked", "derived_status": "parked", "stage": 3, "why": "",
         "override": "parked", "note": "indefinitely deferred",
         "runbook_group": None, "malformed": False},
        {"name": "smoke-active", "path": "plans/app/smoke-active/00-master-plan.md",
         "repo": "app", "tasks_done": 9, "tasks_total": 15,
         "status": "active", "derived_status": "needs-review", "stage": 6,
         "stage_state": "active", "smoke": 3, "drift": True, "why": "",
         "runbook_group": None, "malformed": False},
        {"name": "stage-done", "path": "plans/app/stage-done/00-master-plan.md",
         "repo": "app", "tasks_done": 11, "tasks_total": 11,
         "status": "active", "derived_status": "ready", "stage": 4,
         "stage_state": "done", "drift": False, "why": "",
         "runbook_group": None, "malformed": False},
    ],
    "runbooks": [
        {"path": "plans/app/_runbook-commerce.md", "repo": "app",
         "members_done": 0, "members_total": 2, "tasks_done": 25, "tasks_total": 50,
         "effective_stage": 4, "derived_status": "executing",
         "now": "plans/app/payments-v2/00-master-plan.md"},
    ],
    "counts": {"tracked": 9, "malformed": 0, "archived": 0},
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
