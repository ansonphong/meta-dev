#!/usr/bin/env python3
"""runbook.py — membership rollup + ``runbook add``/``render`` (design §4; I7).

A runbook's derived status is COMPUTED-ON-READ (G-IMP7) via a recursive walk of
the ``membership`` table — never stored in ``plans.derived_status``. This module
owns the canonical recursive rollup + the runbook verbs:

  * ``compute_rollup(conn, path)`` — a SQLite recursive CTE (path-guarded cycle
    termination — SQLite ``CYCLE`` needs ≥3.34; the ``instr`` path guard is
    version-independent and equally terminating) collects the DISTINCT reachable
    LEAF plans (diamond-deduped, W2E-5); a Python descent calls
    ``derive.rollup`` per level for ``members_done``/``total`` +
    ``effective_stage`` + ``now`` (W2E-6/7/8). ``sync.compute_rollup`` delegates
    here (0e absorbs the 0c read-time walker).
  * ``detect_cycles(conn)`` / ``mark_cycle_parse_errors(conn)`` — list cyclic
    membership edges; sync marks both endpoints ``parse_err`` so the disease is
    loud, not silent (W2E-1/W2-T4). Every walk is path-guarded so a hand-edited
    cycle can't hang sync/render/rollup (the doctor surfaces it).
  * ``cmd_runbook_add`` — ``planctl runbook add <rb> <plan-or-rb>``: cycle-
    refused at the door (I7) via a recursive-CTE reachability check BEFORE the
    insert; non-zero + no write on a would-be cycle.
  * ``cmd_runbook_render`` — ``planctl runbook render <rb>``: write the
    ``<!-- RUNBOOK:PROGRESS:START -->``…``END -->`` sentinel block computed from
    the index (sync-first, I4); idempotent (skip if unchanged — R6); a MISSING
    member renders loud (§4). ``--json`` returns the rollup without writing.

Rollup semantics (design §3.2/§4 — pinned R4/VC-4):
  * ``members_done``/``total`` — DIRECT members (a nested runbook = 1 unit, done
    ≡ its derived done).
  * ``tasks_done``/``total`` — recursive sum over LEAF plans with DISTINCT
    diamond-dedup (W2E-5).
  * ``effective_stage`` — ``min`` over non-done AND non-overridden members,
    recursing on each nested member's EFFECTIVE stage (W2E-6).
  * ``now`` — DESCENDS into a nested runbook to its leaf ``now`` (W2E-7).
  * empty runbook (0 members) → ``0/0`` (renders ``"—"``, never 100%) (W2E-8).

Stdlib only.
"""
import json
import os
import re

from planctl import db, derive, events, mutate, parse, statedir

# ── the path-guarded recursive descent CTE ────────────────────────────────────
# Walks membership DOWNWARD from a root, accumulating the path of nodes so a
# cycle (A->B->A) is detected when the next child already appears in the path.
# A diamond (P1 reached two ways) is NOT a cycle — each branch's path is
# distinct, and DISTINCT collapses the duplicated leaf. Version-independent
# (no CYCLE clause needed); bounds every walk (W2E-1) so a hand-edited cycle
# terminates pre-doctor.
_DESCEND_CTE = """\
WITH RECURSIVE walk(child, path) AS (
    SELECT child, '|' || parent || '|' || child || '|'
    FROM membership WHERE parent = ?
    UNION ALL
    SELECT m.child, w.path || m.child || '|'
    FROM membership m
    JOIN walk w ON m.parent = w.child
    WHERE instr(w.path, '|' || m.child || '|') = 0
)
"""


def _distinct_leaf_tasks(conn, root):
    """``(tasks_done, tasks_total)`` over DISTINCT leaf PLAN members reachable
    from ``root`` (diamond-dedup — W2E-5). Cycle-safe (path-guarded CTE).

    A nested runbook contributes ONLY its own leaf plans (reached by the walk
    descending into it), never its rollup counts twice — the DISTINCT collapse
    is over the reachable leaf SET, not a sum of subtree sums."""
    row = conn.execute(
        _DESCEND_CTE +
        "SELECT COALESCE(SUM(p.tasks_done),0), COALESCE(SUM(p.tasks_total),0) "
        "FROM (SELECT DISTINCT w.child FROM walk w "
        "      JOIN files f ON f.path = w.child WHERE f.kind='plan') leaf "
        "JOIN plans p ON p.path = leaf.child",
        (root,)).fetchone()
    return int(row[0] or 0), int(row[1] or 0)


def reaches(conn, src, dst):
    """True iff ``dst`` is reachable downward from ``src`` via membership.

    Cycle-safe (path-guarded). Used by ``runbook add``'s door check: adding
    ``member`` under ``rb`` (edge rb->member) cycles iff ``member`` already
    reaches ``rb`` (closes the loop) or member == rb."""
    row = conn.execute(
        _DESCEND_CTE + "SELECT 1 FROM walk WHERE child=? LIMIT 1",
        (src, dst)).fetchone()
    return row is not None


def detect_cycles(conn):
    """List cyclic membership edges ``[(parent, child), …]``.

    A membership row ``(P -> C)`` is cyclic iff ``C`` reaches ``P`` (closes a
    loop) or ``P == C`` (self-loop). Every ``reaches`` call is path-guarded, so
    this is bounded regardless of graph shape (W2E-1). De-duped: a 2-cycle
    surfaces as both ``(A,B)`` and ``(B,A)``; the endpoint SET is what matters."""
    out = set()
    for parent, child in conn.execute("SELECT parent, child FROM membership"):
        if parent == child or reaches(conn, child, parent):
            out.add((parent, child))
    return sorted(out)


def mark_cycle_parse_errors(conn):
    """Mark every file in a membership cycle as ``parse_err`` (W2E-1/W2-T4).

    Called by ``sync`` AFTER membership population so a hand-edited cycle lands
    BOTH endpoints as ``parse_err`` (refusal-only at the door is insufficient —
    a file Edit bypasses the verb). ``COALESCE`` keeps a more-specific content
    ``parse_err`` if one is already set. Returns the set of paths marked.

    Clearing is automatic: the next sync re-upserts each file with
    ``parse_err`` from its content (NULL when clean), then this pass re-marks
    only files still in a cycle — so removing the cycle clears the flag."""
    cyclic_paths = set()
    for parent, child in detect_cycles(conn):
        cyclic_paths.add(parent)
        cyclic_paths.add(child)
    for p in cyclic_paths:
        conn.execute(
            "UPDATE files SET parse_err=COALESCE(parse_err, 'membership cycle') "
            "WHERE path=?", (p,))
    return cyclic_paths


def _offindex_kind(path):
    """Classify a member that has NO index row.

    Returns ``(kind, status, tasks_done, tasks_total)`` where kind is
    ``missing`` | ``archived`` | ``plan`` | ``doc``, and ``status`` for a
    ``plan`` comes from ``derive.derive_plan`` — the ONE interpreter (I2).
    Deciding completion here with a hand-rolled ``done >= total`` would be a
    SECOND interpreter and would get it wrong: an execution-complete plan below
    stage 6 is ``needs-review``, not ``done``.

    ``path`` is project-root-relative. The disk is the authority here — sync's
    allowlist decides what gets COUNTED, never what EXISTS.

    The PATH cannot tell you whether an unindexed file is a finished document or
    a live plan: ``sync.is_indexed`` also excludes undated names, ``phase-*``,
    ``01-plan.md`` and friends, and plenty of those carry open checkboxes. An
    earlier cut classified purely by path, so every such plan came back ``doc``
    ⇒ done — trading false-MISSING for false-DONE, which is the worse error
    (it inflates ``members_done`` and can flip a runbook to ``done`` with real
    work still open). So ASK THE FILE: anything checkbox-bearing is a plan and
    is done only when its boxes are.
    """
    full = os.path.join(statedir.project_root(), path)
    if not os.path.isfile(full):
        return "missing", None, 0, 0
    if "/_archive/" in "/" + path:
        # Archived is done by doctrine (CLAUDE.md archives only at 100%).
        return "archived", "done", 0, 0
    try:
        with open(full, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return "doc", "done", 0, 0
    tasks, _err = parse.parse_tasks(text)
    td, tt = parse.count_split(tasks)[:2]
    if not tt:
        return "doc", "done", 0, 0
    fm, _fm_err = parse.parse_frontmatter(text)
    status, _drift = derive.derive_plan(fm or {}, td, tt)
    return "plan", status, td, tt


# ── child-result builders (derive.rollup's input shape) ──────────────────────


# ── child-result builders (derive.rollup's input shape) ──────────────────────
def _child_result_from_plan(conn, path):
    """Build a ``derive.rollup`` child-result dict for a PLAN member.

    No index row is NOT the same as "gone" — sync deliberately excludes
    ``_archive/`` (R7/W2C-3: archived is never parsed/derived/counted) and
    ``_NOISE`` names like ``design.md``. Treating either as MISSING made the
    runbook scream ``✗ MISSING`` at files sitting right there on disk. So when
    there is no row, ASK THE DISK:

      * absent            → ``missing``  — genuinely gone, render loud (debt)
      * present, archived → ``archived`` — shipped + filed away; done by
        doctrine (CLAUDE.md: archive only at 100% complete). ``ledger check``
        separately nags to re-register it, which is the right place for that.
      * present, boxes    → ``plan``     — a REAL plan sync just doesn't index;
        done only when its own checkboxes are.
      * present, no boxes → ``doc``      — a document member (design.md etc.):
        nothing to roll up, so existing IS delivered.

    Only ``missing`` is debt; only ``plan`` can be legitimately not-done."""
    r = conn.execute(
        "SELECT stage,override,tasks_done,tasks_total,derived_status "
        "FROM plans WHERE path=?", (path,)).fetchone()
    if r is None:
        kind, ostatus, td, tt = _offindex_kind(path)
        if kind == "missing":
            return {"path": path, "kind": "plan", "done": False, "overridden": False,
                    "effective_stage": None, "tasks_done": 0, "tasks_total": 0,
                    "now": None, "missing": True}
        done = ostatus == "done"
        return {"path": path, "kind": "plan", "done": done, "overridden": False,
                "effective_stage": None, "tasks_done": td, "tasks_total": tt,
                "now": None if done else path,
                "missing": False, "offindex": kind}
    stage, override, td, tt, dstatus = r
    done = dstatus == "done"
    overridden = bool(override)
    eff_stage = None if overridden else stage
    now = None if (done or overridden) else path
    return {"path": path, "kind": "plan", "done": done, "overridden": overridden,
            "effective_stage": eff_stage, "tasks_done": td or 0,
            "tasks_total": tt or 0, "now": now, "missing": False}


def _child_result_from_rollup(sub, path):
    """Build a ``derive.rollup`` child-result dict for a nested RUNBOOK member
    from its already-computed rollup (``sub``). ``sub`` may be None (cyclic /
    not-a-runbook) → a not-done placeholder (doctor surfaces the cycle)."""
    if not sub:
        return {"path": path, "kind": "runbook", "done": False, "overridden": False,
                "effective_stage": None, "tasks_done": 0, "tasks_total": 0,
                "now": None}
    done = sub.get("status") == "done"
    return {"path": path, "kind": "runbook", "done": done, "overridden": False,
            "effective_stage": sub.get("effective_stage"),
            "tasks_done": sub.get("tasks_done", 0),
            "tasks_total": sub.get("tasks_total", 0),
            "now": sub.get("now")}


# ── the canonical recursive rollup ───────────────────────────────────────────
def compute_rollup(conn, path, _visited=None):
    """Recursive rollup for a runbook path → ``derive.rollup`` dict.

    Returns ``None`` when ``path`` is not a runbook (no ``files`` row or
    ``kind != 'runbook'``). An EMPTY runbook (``kind == 'runbook'`` but 0
    members) → the ``0/0`` rollup (renders ``"—"`` — W2E-8).

    Cycle-safe two ways: the Python descent carries a ``_visited`` set (a cyclic
    node bails to a not-done placeholder), AND ``_distinct_leaf_tasks`` is
    path-guarded. So a hand-edited cycle TERMINATES (doctor surfaces it); the
    rollup is never stored (computed-on-read, G-IMP7)."""
    if _visited is None:
        _visited = set()
    if path in _visited:
        return None  # cycle — bounded; doctor detects + marks parse_err
    _visited.add(path)

    # ``_visited`` must be the CURRENT PATH, not everything ever seen. It is
    # passed by reference into every child, so without unwinding it becomes a
    # global-visited set and a legal DIAMOND (two runbooks sharing one child)
    # is misread as a cycle: the second parent gets None -> a not-done
    # placeholder, and the root under-reports members_done / status / now.
    # (tasks_* survive — _distinct_leaf_tasks dedups correctly on its own.)
    # discard-on-exit restores the path-guard the docstring promises and
    # matches _DESCEND_CTE.
    try:
        frow = conn.execute(
            "SELECT kind FROM files WHERE path=?", (path,)).fetchone()
        is_runbook = bool(frow and frow[0] == "runbook")

        rows = conn.execute(
            "SELECT child, child_kind FROM membership WHERE parent=? ORDER BY ord",
            (path,)).fetchall()

        if not rows:
            if is_runbook:
                return derive.rollup([])  # empty runbook → 0/0 (W2E-8)
            return None  # not a runbook

        child_results = []
        for child, kind in rows:
            if kind == "runbook":
                sub = compute_rollup(conn, child, _visited)
                child_results.append(_child_result_from_rollup(sub, child))
            else:
                child_results.append(_child_result_from_plan(conn, child))

        rolled = derive.rollup(child_results)
        # Override task counts with the DISTINCT leaf-plan union (diamond-dedup,
        # W2E-5) — derive.rollup's per-level sum would double-count a diamond;
        # the root's tasks are its OWN reachable-leaf SET, not a sum of subtree sums.
        leaf_done, leaf_total = _distinct_leaf_tasks(conn, path)
        rolled["tasks_done"] = leaf_done
        rolled["tasks_total"] = leaf_total
        rolled["status"], rolled["drift"] = derive._derive_runbook_status(
            rolled["members_done"], rolled["members_total"],
            leaf_done, leaf_total, rolled["effective_stage"])
        return rolled
    finally:
        _visited.discard(path)


def direct_members(conn, rb):
    """Ordered ``[(child, child_kind, ord)]`` for a runbook's DIRECT members."""
    return [(c, k, o) for c, k, o in conn.execute(
        "SELECT child, child_kind, ord FROM membership WHERE parent=? "
        "ORDER BY ord", (rb,))]


# ── runbook add: frontmatter members-list mutation ───────────────────────────
_FM_FENCE = re.compile(r"^\s*-{3}\s*$")
_MEMBERS_KEY = re.compile(r"^members:\s*(.*)$")
_MEMBER_ITEM = re.compile(r"^(\s+)-\s+(.*)$")


def _parse_inline_member_list(val):
    """``"[a, b]"`` -> ``['a','b']``; ``"[]"`` -> ``[]`` (bare scalar strip)."""
    inner = val.strip()
    if inner.endswith("]"):
        inner = inner[:-1]
    inner = inner.strip()
    if not inner:
        return []
    out = []
    for part in inner.split(","):
        p = part.strip().strip("'\"")
        if p:
            out.append(p)
    return out


def insert_member(lines, member):
    """Append ``member`` to the frontmatter ``members:`` list in ``lines``.

    Returns ``(new_lines, inserted_bool)``. Handles: no frontmatter (creates
    one), no ``members:`` key (inserts it), inline ``[a, b]``, and block
    ``- a`` sequences. Idempotent: if ``member`` is already present, returns
    ``(lines, False)`` (no write, no event).

    Targeted edit (find the block extent + insert one line) so the rest of the
    frontmatter + body are preserved verbatim — never a full-frontmatter
    rewrite (which would drop comments + reformat)."""
    if not lines or _FM_FENCE.match(lines[0]) is None:
        # No frontmatter — prepend a minimal runbook frontmatter with the member.
        fm = ["---", "type: runbook", "members:", "  - " + member, "---", ""]
        return fm + lines, True

    close = None
    for i in range(1, len(lines)):
        if _FM_FENCE.match(lines[i]):
            close = i
            break
    if close is None:
        return lines, False  # unclosed frontmatter — parse_err territory; don't touch

    m_idx = None
    for i in range(1, close):
        if _MEMBERS_KEY.match(lines[i]):
            m_idx = i
            break

    if m_idx is None:
        # Insert a members: block right before the closing fence.
        new = lines[:close] + ["members:", "  - " + member] + lines[close:]
        return new, True

    rest = _MEMBERS_KEY.match(lines[m_idx]).group(1).strip()
    if rest.startswith("["):
        # Inline list — append (idempotent).
        items = _parse_inline_member_list(rest)
        if member in items:
            return lines, False
        if rest == "[]":
            new_val = "[ " + member + " ]"
        else:
            inner = rest[:-1].rstrip()
            sep = "" if inner.endswith(",") else ", "
            new_val = inner + sep + member + "]"
        new = lines[:m_idx] + ["members: " + new_val] + lines[m_idx + 1:]
        return new, True

    # Block (or empty) sequence — find the extent of contiguous ``  - item`` lines.
    last_item_idx = None
    existing = []
    j = m_idx + 1
    while j < close:
        mit = _MEMBER_ITEM.match(lines[j])
        if mit:
            last_item_idx = j
            existing.append(mit.group(2).strip())
            j += 1
        elif lines[j].strip() == "":
            break  # a blank line ends the block
        else:
            break
    if member in existing:
        return lines, False  # idempotent
    insert_at = (last_item_idx + 1) if last_item_idx is not None else (m_idx + 1)
    new = lines[:insert_at] + ["  - " + member] + lines[insert_at:]
    return new, True


# ── runbook render: sentinel block ───────────────────────────────────────────
SENTINEL_START = "<!-- RUNBOOK:PROGRESS:START -->"
SENTINEL_END = "<!-- RUNBOOK:PROGRESS:END -->"
_START_SUB = "<!-- RUNBOOK:PROGRESS:START"   # substring match (tolerates suffixes)
_END_SUB = "<!-- RUNBOOK:PROGRESS:END -->"

_STAGE_NAME = {
    0: "not started", 1: "BRAINSTORM", 2: "DESIGN", 3: "PLAN",
    4: "HARDEN", 5: "EXECUTE", 6: "REVIEW",
}


def _bar(frac, width=4):
    """Block-fill bar mirroring ``frac`` (0..1)."""
    width = max(4, width)
    filled = min(width, round(frac * width))
    return "▰" * filled + "▱" * (width - filled)


# Repo-root buckets under plans/ — never the identity of a plan, just its repo.
_REPO_DIRS = ("app", "www", "gallery", "meta", "cam")


def _member_label(path, kind, missing=False, offindex=None):
    """Human-tellable label for a member row.

    A campaign plan lives in its OWN folder as ``00-master-plan.md``, so the
    basename is identical for every such member — useless in a table. The
    FOLDER is the identity; the filename is the footnote. Standalone plans
    (a dated ``.md`` sitting directly in ``plans/<repo>/``) have no folder to
    borrow, so their own stem is the identity.

    ``offindex`` members (archived / plain docs) are real files, so they get a
    real name with a quiet suffix — never the MISSING treatment."""
    if missing:
        return "%s MISSING `%s`" % (derive.EMOJI_MISSING, path)
    base = path.rsplit("/", 1)[-1]
    stem = base[:-3] if base.endswith(".md") else base
    parent = os.path.basename(os.path.dirname(path))
    folder = parent if parent and parent not in _REPO_DIRS else None

    if kind == "runbook":
        return "▸ **%s** _(nested runbook)_" % (folder or stem)
    if folder:
        # Folder is the identity; say what the file is only when it is NOT the
        # conventional master plan (those are interchangeable by definition).
        detail = "master plan" if base.startswith("00-master") else stem
        return "**%s** · _%s_" % (folder, detail)
    return "**%s**" % stem


def _member_rows(conn, root, rb_rel):
    """Direct-member rows for the render table, index-driven (NOT re-read)."""
    rows = []
    for child, kind, _ord in direct_members(conn, rb_rel):
        if kind == "runbook":
            sub = compute_rollup(conn, child) or {}
            rows.append({
                "path": child, "kind": "runbook", "missing": False,
                "stage": sub.get("effective_stage"),
                "status": sub.get("status"),
                "drift": bool(sub.get("drift")),
                "glyph": derive.glyph(sub.get("status"), sub.get("drift")),
                "tasks_done": sub.get("tasks_done", 0),
                "tasks_total": sub.get("tasks_total", 0),
                "pct": derive.pct(sub.get("tasks_done", 0),
                                  sub.get("tasks_total", 0)),
                "override": None,
            })
            continue
        on_disk = os.path.isfile(os.path.join(root, child))
        # ``drift`` is selected so the declared-done-with-open-work warning
        # reaches the rendered table. compose_block reads row["drift"]; without
        # it every member renders as clean ✅ and the warning is silently lost.
        prow = conn.execute(
            "SELECT stage,override,derived_status,tasks_done,tasks_total,drift "
            "FROM plans WHERE path=?", (child,)).fetchone()
        if prow is None or not on_disk:
            # No index row is not "gone". sync excludes _archive/ and _NOISE
            # names (design.md …) BY DESIGN, so only the disk can say MISSING —
            # and only the FILE can say whether an unindexed member is a
            # finished doc or a plan with open boxes (see _offindex_kind).
            okind, ostatus, otd, ott = _offindex_kind(child)
            is_missing = okind == "missing"
            rows.append({"path": child, "kind": "plan",
                         "missing": is_missing,
                         "offindex": None if is_missing else okind,
                         "stage": None,
                         "status": ostatus,
                         "glyph": "✗" if is_missing else derive.glyph(ostatus, False),
                         "drift": False,
                         "tasks_done": otd, "tasks_total": ott,
                         "pct": derive.pct(otd, ott),
                         "override": None})
            continue
        stage, override, dstatus, td, tt, pdrift = prow
        pdrift = bool(pdrift)
        rows.append({
            "path": child, "kind": "plan", "missing": False, "stage": stage,
            "status": dstatus, "drift": pdrift,
            "glyph": derive.glyph(dstatus, pdrift),
            "tasks_done": td or 0, "tasks_total": tt or 0,
            "pct": derive.pct(td or 0, tt or 0), "override": override,
        })
    return rows


def compose_block(rb_rel, rollup, member_rows):
    """Build the ``RUNBOOK:PROGRESS`` block (WITHOUT the sentinel lines).

    Execution-order glyph chain + summary + member table + Now/blocked/needs-
    review queues. MISSING members render loud (§4). Index-driven (computed from
    the read-model, never re-reads the member files)."""
    r = rollup or {}
    members_total = r.get("members_total", 0)
    members_done = r.get("members_done", 0)
    tasks_done = r.get("tasks_done", 0)
    tasks_total = r.get("tasks_total", 0)
    now = r.get("now")
    status = r.get("status")
    empty = members_total == 0

    def _glyph_for(row):
        if row.get("missing"):
            return "✗"
        if row.get("override"):
            return "!"
        g = row.get("glyph") or "?"
        return g

    chain = " → ".join(
        "**%s** %s" % (os.path.basename(os.path.dirname(row["path"])) or row["path"],
                       _glyph_for(row))
        for row in member_rows) or "—"

    lines = []
    lines.append("")
    lines.append("### Execution order & package progress")
    lines.append("")
    lines.append("> %s → **Stage 6** ⬜" % chain)
    lines.append("")

    if empty:
        lines.append("**Members:** 0/0  ·  **Progress:** —  (empty runbook)")
    else:
        pct = derive.pct(tasks_done, tasks_total)
        lines.append("**Members done:** %d / %d  ·  **Tasks:** %d/%d (%d%%)  "
                     "·  **%s %s**" % (
                         members_done, members_total, tasks_done, tasks_total, pct,
                         derive.emoji(status, r.get("drift")), status or "?"))
    lines.append("")

    lines.append("| # | Plan | Stage | Progress | Status | → |")
    lines.append("|---|------|-------|----------|--------|---|")
    for i, row in enumerate(member_rows):
        name = _member_label(row["path"], row["kind"], row.get("missing"),
                             row.get("offindex"))
        stage = row.get("stage")
        if stage is None:
            stage_cell = "—"
        else:
            stage_cell = "stage %s" % stage
        if row.get("override"):
            stage_cell += " ⛔ %s" % row["override"]
        if row.get("tasks_total") and not row.get("missing"):
            prog = "`%s` %d%%" % (_bar(row["pct"] / 100.0 if row["pct"] else 0),
                                  row["pct"])
        else:
            prog = "—"
        if row.get("missing"):
            status_cell = "%s MISSING" % derive.EMOJI_MISSING
        elif row.get("offindex") == "archived":
            status_cell = "📦 archived"
        elif row.get("offindex") == "doc":
            status_cell = "📄 doc"
        else:
            status_cell = "%s %s" % (
                derive.emoji(row.get("status"), row.get("drift")),
                row.get("status") or "?")
        lines.append("| %d | %s | %s | %s | %s | [plan](%s) |" % (
            i + 1, name, stage_cell, prog, status_cell, row["path"]))
    lines.append("")

    # Now / blocked / needs-review queues.
    lines.append("**Now:** %s" % (now or ("—" if empty else "none — all done")))
    blocked = [r for r in member_rows if r.get("override")]
    nr = [r for r in member_rows if r.get("status") == "needs-review"]
    lines.append("**Blocked:** %s" % (
        ", ".join("%s (%s)" % (r["path"], r["override"]) for r in blocked) or "—"))
    lines.append("**Needs review:** %s" % (
        ", ".join(r["path"] for r in nr) or "—"))
    lines.append("")
    return "\n".join(lines)


def replace_progress_block(text, block):
    """Insert ``block`` between the sentinel lines (keeping the sentinels).

    Returns the new full-file text. If both sentinels are present, replaces the
    span between them; if START exists without END, appends END; if neither,
    appends a fresh sentinel-wrapped block at EOF (so a first render on a
    sentinel-less runbook still writes + is idempotent thereafter)."""
    lines = text.split("\n")
    si = ei = None
    for i, ln in enumerate(lines):
        if si is None and _START_SUB in ln:
            si = i
        if si is not None and _END_SUB in ln:
            ei = i
            break
    if si is not None and ei is not None:
        new_lines = lines[:si + 1] + [block] + lines[ei:]
        return "\n".join(new_lines)
    if si is not None and ei is None:
        new_lines = lines[:si + 1] + [block, SENTINEL_END] + lines[si + 1:]
        return "\n".join(new_lines)
    # No sentinels — append a fresh wrapped block at EOF.
    sep = "" if text.endswith("\n") or not text else "\n"
    if text.strip():
        return text + sep + "\n" + SENTINEL_START + "\n" + block + "\n" + \
            SENTINEL_END + "\n"
    return SENTINEL_START + "\n" + block + "\n" + SENTINEL_END + "\n"


# ── output helper ────────────────────────────────────────────────────────────
def _emit(args, payload, err=None):
    """JSON when ``--json``, else a human summary. ``err`` → stderr (human only)."""
    if getattr(args, "json", False):
        print(json.dumps({k: v for k, v in payload.items() if k != "_err"}))
        return
    msg = payload.get("_msg") or payload.get("reason") or ""
    if err:
        import sys
        sys.stderr.write(err + "\n")
    elif msg:
        print(msg)


# ── the verbs ────────────────────────────────────────────────────────────────
def cmd_runbook_add(args):
    """``planctl runbook add <rb> <plan-or-rb> [--json]`` — insert a member,
    cycle-refused at the door (I7)."""
    from planctl import sync  # lazy (sync imports nothing from runbook at top-level)
    root = statedir.project_root()
    rb_rel = sync._normalize_arg_path(args.rb, root)
    member_rel = sync._normalize_arg_path(args.member, root)
    rb_abs = os.path.join(root, rb_rel)
    if not os.path.isfile(rb_abs):
        _emit(args, {"rb": rb_rel, "member": member_rel, "added": False,
                     "reason": "rb_not_found"},
              err="[planctl runbook add] %s is not a file" % rb_rel)
        return 1

    # Cycle guard at the door (I7): edge rb->member cycles iff member reaches rb
    # (or member == rb). Refuse loudly, non-zero, NO write.
    conn = db.open_db()
    try:
        sync.ensure_fresh(conn, root)
        if member_rel == rb_rel or reaches(conn, member_rel, rb_rel):
            msg = ("[planctl runbook add] REFUSED: adding %s under %s would "
                   "create a membership cycle (I7)." % (member_rel, rb_rel))
            _emit(args, {"rb": rb_rel, "member": member_rel, "added": False,
                         "reason": "cycle"}, err=msg)
            return 1
    finally:
        conn.close()

    # Atomic MD edit: append member to frontmatter members: list (under the lock).
    with mutate.mutation_lock(rb_abs):
        def mutator(lines):
            return insert_member(lines, member_rel)
        _new_text, inserted = mutate.atomic_write_md(rb_abs, mutator)

    if inserted:
        # Re-trigger membership population (S5) + event.
        sync.sync_one(rb_rel)
        events.append({"event": "runbook_change", "plan": rb_rel,
                       "data": {"verb": "add", "member": member_rel}})
        _emit(args, {"rb": rb_rel, "member": member_rel, "added": True,
                     "_msg": "runbook add: %s += %s" % (rb_rel, member_rel)})
    else:
        _emit(args, {"rb": rb_rel, "member": member_rel, "added": False,
                     "reason": "already_member",
                     "_msg": "runbook add: %s already a member of %s (no-op)"
                             % (member_rel, rb_rel)})
    return 0


def cmd_runbook_render(args):
    """``planctl runbook render <rb> [--json]`` — write the RUNBOOK:PROGRESS
    sentinel block computed from the index (sync-first, I4); idempotent (R6)."""
    from planctl import sync  # lazy
    root = statedir.project_root()
    rb_rel = sync._normalize_arg_path(args.rb, root)
    rb_abs = os.path.join(root, rb_rel)
    if not os.path.isfile(rb_abs):
        _emit(args, {"runbook": rb_rel, "written": False, "reason": "not_found"},
              err="[planctl runbook render] %s is not a file" % rb_rel)
        return 1

    conn = db.open_db()
    try:
        sync.ensure_fresh(conn, root)  # sync-first (I4 — render trusts a fresh index)
        rollup = compute_rollup(conn, rb_rel)
        frow = conn.execute(
            "SELECT kind FROM files WHERE path=?", (rb_rel,)).fetchone()
        is_runbook = bool(frow and frow[0] == "runbook")
        if is_runbook and rollup is None:
            rollup = derive.rollup([])  # empty runbook → 0/0
        member_rows = _member_rows(conn, root, rb_rel) if is_runbook else []
    finally:
        conn.close()

    if getattr(args, "json", False):
        print(json.dumps({"runbook": rb_rel, "rollup": rollup,
                          "members": member_rows}))
        return 0

    if not is_runbook:
        _emit(args, {"runbook": rb_rel, "written": False, "reason": "not_runbook"},
              err="[planctl runbook render] %s is not a runbook (no type:runbook)"
                  % rb_rel)
        return 1

    block = compose_block(rb_rel, rollup, member_rows)

    # Atomic write; skip if the computed block is unchanged (idempotent, R6).
    with mutate.mutation_lock(rb_abs):
        def mutator(lines):
            text = "\n".join(lines)
            new_text = replace_progress_block(text, block)
            return new_text.split("\n"), (new_text != text)
        _nt, changed = mutate.atomic_write_md(rb_abs, mutator)

    if changed:
        events.append({"event": "runbook_change", "plan": rb_rel,
                       "data": {"verb": "render"}})
        _emit(args, {"runbook": rb_rel, "written": True,
                     "_msg": "runbook render: wrote progress block → %s" % rb_rel})
    else:
        _emit(args, {"runbook": rb_rel, "written": False, "reason": "unchanged",
                     "_msg": "runbook render: unchanged (no rewrite) → %s" % rb_rel})
    return 0
