#!/usr/bin/env python3
"""view.py — per-campaign boxed view for ``planctl runbook <path>`` (design §3.6).

Consumes the shared ``render_lib.py`` (landed in 2a) — ONE render library, two
entry points (global dashboard + this boxed runbook view). Each boxed view is
scoped to ONE runbook path:

  * Rollup header — campaign name, members bar, recursive task bar, effective
    stage, derived glyph.
  * Member table — one row per DIRECT member; nested runbooks as INDENTED
    sub-groups with their own rollup rows; ``❓ MISSING`` loud for dead paths.
  * ``Now:`` pointer — leaf plan from ``compute_rollup``\'s ``now``.
  * Queues — blocked (override + note) and needs-review members.
  * Claims — live claims overlapping any member scope.
  * ``--json`` — same data structured (rollup + member rows + queues + claims).

Sync-first (I4). Renders on the open-right CARD chassis — one standard, shared
with every other meta-dev surface (see references/status-cards.md). Stdlib only.
"""
import json
import os
import time

from planctl import db, derive, runbook, statedir, sync
from planctl.render_lib import (
    CARD_FIELD,
    card_top, card_bottom, card_sep, card_row,
    bar, pct, mark, dwidth, fit, clip,
)

# ── stage display names ────────────────────────────────────────────────────────
_STAGE_NAME = {
    0: "not started", 1: "BRAINSTORM", 2: "DESIGN", 3: "PLAN",
    4: "HARDEN", 5: "EXECUTE", 6: "REVIEW",
}


# ── DB query helpers ───────────────────────────────────────────────────────────
def _plan_info(conn, path):
    """One plan's indexed row as a dict, or None."""
    row = conn.execute(
        "SELECT stage, override, note, derived_status, tasks_done, tasks_total "
        "FROM plans WHERE path=?", (path,)).fetchone()
    if row is None:
        return None
    stage, override, note, dstatus, td, tt = row
    return {"stage": stage, "override": override, "note": note,
            "status": dstatus, "tasks_done": td or 0, "tasks_total": tt or 0}


def _file_kind(conn, path):
    row = conn.execute("SELECT kind FROM files WHERE path=?", (path,)).fetchone()
    return row[0] if row else None


def _live_claims_detailed(conn):
    """Live claims as ``[{scope, session, ts, ttl, pid}, …]``."""
    now = time.time()
    out = []
    for scope, session, ts, ttl, status, pid in conn.execute(
            "SELECT scope, session, ts, ttl, status, pid FROM claims"):
        if status in ("released", "expired"):
            continue
        try:
            live_ts = float(ts)
            ttl_s = int(ttl or 1800)
        except (TypeError, ValueError):
            continue
        if now - live_ts > ttl_s:
            continue
        out.append({"scope": scope, "session": session, "ts": live_ts,
                    "ttl": ttl_s, "pid": pid})
    return out


# ── member row builders ────────────────────────────────────────────────────────
def _build_member_rows(conn, root, rb_rel, depth=0, _seen=None):
    """Flat list of member-row dicts for *rb_rel*, recursing into nested runbooks.

    Each dict carries ``indent`` = current nesting depth (0 = top-level member).
    Nested runbooks produce a header row at depth + their own member rows at
    depth+1, so the renderer just iterates the flat list.

    ``_seen`` mirrors ``compute_rollup``'s ``_visited`` — a hand-edited
    membership cycle renders a loud ❓ CYCLE row instead of recursing forever."""
    if _seen is None:
        _seen = set()
    _seen.add(rb_rel)
    rows = []
    members = runbook.direct_members(conn, rb_rel)
    for child, kind, _ord in members:
        if kind == "runbook":
            if child in _seen:
                rows.append({"type": "plan", "path": child, "missing": True,
                             "indent": depth, "glyph": mark("missing"),
                             "status": "cycle", "stage": None,
                             "tasks_done": 0, "tasks_total": 0, "pct_val": 0})
                continue
            sub_rollup = runbook.compute_rollup(conn, child)
            on_disk = os.path.isfile(os.path.join(root, child))
            rows.append({
                "type": "nested_runbook_header",
                "path": child,
                "indent": depth,
                "rollup": sub_rollup or {},
                "members_done": (sub_rollup or {}).get("members_done", 0),
                "members_total": (sub_rollup or {}).get("members_total", 0),
                "tasks_done": (sub_rollup or {}).get("tasks_done", 0),
                "tasks_total": (sub_rollup or {}).get("tasks_total", 0),
                "effective_stage": (sub_rollup or {}).get("effective_stage"),
                "status": (sub_rollup or {}).get("status"),
                "drift": (sub_rollup or {}).get("drift"),
                "missing": not on_disk or sub_rollup is None,
            })
            rows.extend(_build_member_rows(conn, root, child, depth + 1, _seen))
        else:
            info = _plan_info(conn, child)
            on_disk = os.path.isfile(os.path.join(root, child))
            if info is None or not on_disk:
                rows.append({"type": "plan", "path": child, "missing": True,
                             "indent": depth,
                             "glyph": mark("missing"), "status": None,
                             "stage": None,
                             "tasks_done": 0, "tasks_total": 0, "pct_val": 0,
                             "override": None, "note": None})
            else:
                g = mark(info["status"], False)
                rows.append({"type": "plan", "path": child, "missing": False,
                             "indent": depth,
                             "glyph": g, "status": info["status"],
                             "stage": info["stage"],
                             "tasks_done": info["tasks_done"],
                             "tasks_total": info["tasks_total"],
                             "pct_val": derive.pct(info["tasks_done"],
                                                    info["tasks_total"]),
                             "override": info["override"],
                             "note": info["note"]})
    return rows


# ── the boxed-view entry point ─────────────────────────────────────────────────
def cmd_runbook_boxed(args):
    """``planctl runbook <path> [--json]`` — per-campaign boxed view."""
    root = statedir.project_root()
    rb_path = getattr(args, "rb_path", None)
    if not rb_path:
        import sys
        print("planctl runbook: expected a runbook path for the boxed view, "
              "or a subcommand (add/render).", file=sys.stderr)
        print("  planctl runbook <path>            boxed campaign view",
              file=sys.stderr)
        print("  planctl runbook add <rb> <m>      add a member",
              file=sys.stderr)
        print("  planctl runbook render <rb>        write progress block",
              file=sys.stderr)
        return 1

    rb_rel = sync._normalize_arg_path(rb_path, root)
    rb_abs = os.path.join(root, rb_rel)

    conn = db.open_db()
    try:
        sync.ensure_fresh(conn, root)  # sync-first (I4)

        rollup = runbook.compute_rollup(conn, rb_rel) or {}
        is_runbook = _file_kind(conn, rb_rel) == "runbook"

        # Member rows (only for runbooks)
        member_rows = _build_member_rows(conn, root, rb_rel) if is_runbook else []

        # ── Now pointer ──
        now_path = rollup.get("now")
        now_info = None
        if now_path:
            pi = _plan_info(conn, now_path)
            if pi:
                now_info = {"path": now_path,
                            "glyph": mark(pi["status"], False),
                            "stage": pi["stage"]}

        # ── Queues ──
        blocked = [mr for mr in member_rows
                   if mr["type"] == "plan" and mr.get("override")
                   and not mr.get("missing")]
        needs_review = [mr for mr in member_rows
                        if mr["type"] == "plan"
                        and mr.get("status") == "needs-review"
                        and not mr.get("missing")]

        # ── Claims overlapping any member scope ──
        all_claims = _live_claims_detailed(conn)
        member_paths = {mr["path"] for mr in member_rows if mr["type"] == "plan"}
        overlapping = []
        for c in all_claims:
            for mp in member_paths:
                if (mp == c["scope"] or mp.startswith(c["scope"])
                        or c["scope"].startswith(mp)):
                    overlapping.append(c)
                    break

        # ── Payload for --json ──
        payload = {
            "path": rb_rel,
            "is_runbook": is_runbook,
            "rollup": rollup,
            "members": [_jsonable_member(mr) for mr in member_rows],
            "now": now_info,
            "queues": {
                "blocked": [{"path": b["path"], "override": b["override"],
                             "note": b.get("note")} for b in blocked],
                "needs_review": [{"path": n["path"], "stage": n.get("stage")}
                                 for n in needs_review],
            },
            "claims": overlapping,
        }

        if getattr(args, "json", False):
            print(json.dumps(payload, default=str))
            return 0

        if not is_runbook:
            _print_minimal_box(rb_rel, rollup)
            return 0

        _print_boxed_view(rb_rel, rollup, member_rows, now_info,
                          blocked, needs_review, overlapping)
        return 0
    finally:
        conn.close()


def _jsonable_member(mr):
    """Shallow copy of a member row for --json output."""
    return dict(mr)


# ── render: one-level member rows → box lines ──────────────────────────────────
def _render_member_table(member_rows):
    """Render a flat member-row list into card-safe lines (each ≤CARD_FIELD cells).

    Handles plan rows and nested_runbook_header rows. Each row carries its own
    ``indent`` level. The caller collects lines and passes them to ``card_row()``."""
    lines = []
    for mr in member_rows:
        indent = mr.get("indent", 0)
        if mr["type"] == "nested_runbook_header":
            lines.append(_render_nested_header(mr, indent))
        elif mr["type"] == "plan":
            lines.append(_render_plan_row(mr, indent))
    return lines


def _short_path(path):
    """Compact member name: parent-dir/basename for plans in subdirectories,
    or the full path for top-level entries. Avoids 10 identical basenames."""
    parts = path.rsplit("/", 1)
    if len(parts) == 2 and parts[0] != "plans":
        # Show the last meaningful directory + basename
        parent = parts[0].rsplit("/", 1)[-1] if "/" in parts[0] else parts[0]
        return parent + "/" + parts[1]
    return path


def _render_nested_header(mr, indent):
    """One indented line for a nested runbook header with its rollup.

    Same column arithmetic as ``_render_plan_row`` (glyph first, name flexes,
    bar/pct/tail fixed) so a nested header lines up with the plan rows beneath
    it and, like them, always fits inside CARD_FIELD."""
    prefix = "  " * indent
    md = mr.get("members_done", 0)
    mt = mr.get("members_total", 0)
    td = mr.get("tasks_done", 0)
    tt = mr.get("tasks_total", 0)
    es = mr.get("effective_stage")
    glyph = mark(mr.get("status"), mr.get("drift"))

    if mr.get("missing"):
        return "%s%s MISSING nested runbook: %s" % (
            prefix, mark("missing"), mr["path"])

    name = "▸ " + _short_path(mr["path"])
    if mt <= 0:
        return "%s%s  %s  (empty runbook)" % (prefix, glyph, name)

    bar_str = bar(td, tt)
    pct_str = pct(td, tt)
    tail = "  members %d/%d  stage %s" % (
        md, mt, es if es is not None else "?")
    fixed = (len(prefix) + dwidth(glyph) + 4
             + dwidth(bar_str) + dwidth(pct_str) + dwidth(tail))
    name_w = max(4, CARD_FIELD - fixed)
    return "%s%s  %s%s %s%s" % (
        prefix, glyph, fit(name, name_w), bar_str, pct_str, tail)


def _render_plan_row(mr, indent):
    """One indented line for a plan member.

    Uses a column-aware layout: fixed-width parts (glyph, bar, pct, stage) get
    priority; the name column gets the remaining space and is fit()'d if needed,
    so the stage + bar always survive even on very long paths."""
    prefix = "  " * indent
    if mr.get("missing"):
        name = _short_path(mr["path"])
        return "%s%s  MISSING: %s" % (prefix, mark("missing"), name)

    glyph = mr["glyph"]
    name = _short_path(mr["path"])
    td = mr.get("tasks_done", 0)
    tt = mr.get("tasks_total", 0)
    stage = mr.get("stage")
    override = mr.get("override")
    note = mr.get("note")

    bar_str = bar(td, tt)         # exactly BAR_W=18 cells
    pct_str = pct(td, tt)         # e.g. " 60%" (4 cells) or "  —" (3 cells)
    stage_str = "stage %s" % (stage if stage is not None else "?")

    override_str = ""
    if override:
        note_tail = (" — " + note) if note else ""
        override_str = "  %s %s%s" % (mark(override), override, note_tail)

    # Fixed-width parts: prefix N*2, glyph (dwidth — an emoji is 2 cells),
    # separators 4 ("  " + " " + " "), bar 18, pct ≤4, stage 7-9, override
    # variable. The budget is CARD_FIELD (= CARD_W - 2), NOT the retired
    # FIELD (= BOX_W - 4): the open-right chassis reserves only the "│ "
    # prefix, so the text field is 2 cells WIDER than the old boxed one.
    fixed = (len(prefix) + dwidth(glyph) + 4
             + dwidth(bar_str) + dwidth(pct_str) + dwidth(stage_str)
             + dwidth(override_str))
    name_w = max(4, CARD_FIELD - fixed)
    name_fitted = fit(name, name_w)

    return "%s%s  %s%s %s %s%s" % (
        prefix, glyph, name_fitted, bar_str, pct_str, stage_str, override_str)


def _print_boxed_view(rb_rel, rollup, member_rows, now_info, blocked,
                      needs_review, claims):
    """Render the complete per-campaign card to stdout.

    Open-right chassis: ``card_top`` heads the card with the campaign name,
    ``card_sep`` labels each section (so the old title-row + ``box_rule()`` pair
    collapses into one divider), and no row is padded to a right border."""
    name = (rb_rel.rstrip("/").rsplit("/", 1)[-1]
            if "/" in rb_rel else rb_rel)

    members_done = rollup.get("members_done", 0)
    members_total = rollup.get("members_total", 0)
    tasks_done = rollup.get("tasks_done", 0)
    tasks_total = rollup.get("tasks_total", 0)
    eff_stage = rollup.get("effective_stage")
    status = rollup.get("status")
    drift = rollup.get("drift")
    glyph = mark(status, drift) if status else mark("draft")

    out = [card_top(name.upper())]

    # ── Rollup summary ──
    if members_total == 0:
        out.append(card_row(clip("%s  Members: 0/0  ·  (empty runbook)" % glyph)))
    else:
        mpct = pct(members_done, members_total)
        tpct_val = derive.pct(tasks_done, tasks_total)
        out.append(card_row(clip(
            "%s  Members: %d/%d  %s %s  ·  Tasks: %d/%d (%d%%)" % (
                glyph, members_done, members_total,
                bar(members_done, members_total), mpct,
                tasks_done, tasks_total, tpct_val))))
        sn = _STAGE_NAME.get(eff_stage or 0, "?")
        out.append(card_row(clip("Effective stage: %s (%s)  ·  %s" % (
            eff_stage if eff_stage is not None else "—", sn, status or "?")))

    # ── Members ──
    out.append(card_sep("Members (%d)" % members_total))
    if not member_rows:
        out.append(card_row(clip("(no members)")))
    else:
        for ml in _render_member_table(member_rows):
            out.append(card_row(clip(ml)))

    # ── Now ──
    out.append(card_sep("Now"))
    if now_info:
        out.append(card_row(clip("%s  %s  stage %s" % (
            now_info["glyph"], now_info["path"],
            now_info.get("stage") or "?"))))
    elif members_total == 0:
        out.append(card_row(clip("— (empty runbook)")))
    else:
        out.append(card_row(clip("— all done")))

    # ── Blocked ──
    out.append(card_sep("Blocked (%d)" % len(blocked)))
    if not blocked:
        out.append(card_row(clip("—")))
    else:
        for b in blocked:
            note_str = (" — " + b["note"]) if b.get("note") else ""
            override = b.get("override") or "blocked"
            out.append(card_row(clip("%s  %s  %s%s" % (
                mark(override), b["path"], override, note_str))))

    # ── Needs review ──
    out.append(card_sep("Needs review (%d)" % len(needs_review)))
    if not needs_review:
        out.append(card_row(clip("—")))
    else:
        for nr in needs_review:
            out.append(card_row(clip("%s  %s  stage %s" % (
                mark("needs-review"), nr["path"], nr.get("stage") or "?")))

    # ── Claims ──
    out.append(card_sep("Live claims (%d)" % len(claims)))
    if not claims:
        out.append(card_row(clip("—")))
    else:
        for c in claims:
            out.append(card_row(clip("%s  session=%s  pid=%s" % (
                c["scope"], c["session"], c.get("pid", "?"))))
    out.append(card_bottom())

    print("\n".join(out))


def _print_minimal_box(rb_rel, rollup):
    """Minimal card for a non-runbook path."""
    name = os.path.basename(rb_rel) or rb_rel
    r = rollup or {}
    out = [card_top(name.upper()),
           card_row(clip("Not a runbook — no members to display."))]
    td = r.get("tasks_done") or 0
    tt = r.get("tasks_total") or 0
    if tt:
        out.append(card_row(clip("Plan tasks: %d/%d  %s  %s" % (
            td, tt, bar(td, tt), pct(td, tt))))
    out.append(card_row(clip("Use 'planctl status %s' for plan-level details." % rb_rel)))
    out.append(card_bottom())
    print("\n".join(out))
