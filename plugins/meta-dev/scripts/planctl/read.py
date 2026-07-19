#!/usr/bin/env python3
"""read.py — the token-cheap read verbs (design §3.6; promises G2, G5).

  * ``status <plan>``  — ONE plan's derived state (~100 tokens --json).
  * ``brief``          — ≤600-token session orientation (active arcs, blocked,
                         needs-review, next actions; top-N per section with
                         ``…and M more`` elision so the cap holds on a 200-plan
                         tree). ``--oneline`` emits a single SessionStart line.
  * ``next``           — ready-work, ledger-ordered (phase 0c.3).

Every reader calls ``sync.ensure_fresh`` first (I4 — no reader trusts a cold or
stale-derive_v index). ``ensure_fresh`` is the cheap freshness gate (rev-parse +
diff-only) that keeps reads fast on the 9p ``plans/`` mount; the ``sync`` VERB
remains the thorough porcelain∪diff path (see sync.py).

Stdlib only.
"""
import os
import re

from planctl import db, derive, statedir, sync

# ── Sequence ordering (the ledger is NOT indexed — read from disk; S8/W2C-9) ───
_SEQ_HEAD_RE = re.compile(r"^#{1,6}\s+Sequence\b", re.IGNORECASE)
_SEQ_NEXT_HEAD_RE = re.compile(r"^#{1,6}\s+\S")
_SEQ_BULLET_RE = re.compile(r"^(?:[-*]\s+|\d+\.\s+)")
_SEQ_PATH_RE = re.compile(r"(plans/\S*?\.md)")


def sequence_order(root):
    """Ordered plan-path list from ``plans/meta-runbook.md ## Sequence``.

    The ledger (basename ``meta-runbook.md``) is EXCLUDED from the index, so it
    is read from disk here. Mirrors ``plan-index.parse_runbook_sequence`` (strip
    the bullet, match the first ``plans/…/foo.md`` token, de-dup in order). ``[]``
    when the ledger or ``## Sequence`` is absent."""
    ledger = os.path.join(root, "plans", "meta-runbook.md")
    if not os.path.isfile(ledger):
        return []
    try:
        with open(ledger, encoding="utf-8", errors="ignore") as fh:
            lines = fh.read().split("\n")
    except OSError:
        return []
    start = None
    for i, line in enumerate(lines):
        if _SEQ_HEAD_RE.match(line.strip()):
            start = i + 1
            break
    if start is None:
        return []
    end = len(lines)
    for i in range(start, len(lines)):
        if _SEQ_NEXT_HEAD_RE.match(lines[i]):
            end = i
            break
    order = []
    for raw in lines[start:end]:
        body = _SEQ_BULLET_RE.sub("", raw.strip())
        m = _SEQ_PATH_RE.match(body)
        if m and m.group(1) not in order:
            order.append(m.group(1))
    return order


# ── claims (live) — dormant plumbing (claims are populated by `claim` in 0d) ───
def _live_claims(conn):
    """``{scope: session}`` for live (non-released, non-expired) claims.

    ``claims`` is empty through 0c (the ``claim`` verb lands in 0d); this is the
    read-side plumbing ``next`` uses to flag already-claimed work."""
    import time
    now = time.time()
    out = {}
    for scope, session, ts, ttl, status in conn.execute(
            "SELECT scope,session,ts,ttl,status FROM claims"):
        if status in ("released", "expired"):
            continue
        try:
            live_ts = float(ts)
            ttl_s = int(ttl or 1800)
        except (TypeError, ValueError):
            continue
        if now - live_ts > ttl_s:
            continue
        out[scope] = session
    return out


def _claimed_by(claims, path):
    """The session holding a live claim overlapping ``path`` (PREFIX scope match
    per design — overlap is a prefix relation, not PK-equality), else None."""
    for scope, session in claims.items():
        if path == scope or path.startswith(scope) or scope.startswith(path):
            return session
    return None


# ── one plan's derived state (design §3.4 `status`) ───────────────────────────
def _plan_row(conn, rel):
    return conn.execute(
        "SELECT path,repo,stage,override,note,why,title,tasks_done,tasks_total,"
        "human_open,human_total,raw_done,raw_total,drift,context_json,docs_json,"
        "derived_status,smoke_total,stage_state FROM plans WHERE path=?",
        (rel,)).fetchone()


def cmd_status(args):
    """``planctl status <plan> [--json]`` — one plan's derived state (~100 tokens).

    For a PLAN: the stored derived_status. For a RUNBOOK: the computed-on-read
    rollup status (§4 — never stored). ~100 tokens --json; a 3-line human summary
    otherwise."""
    root = statedir.project_root()
    conn = db.open_db()
    try:
        sync.ensure_fresh(conn, root)
        rel = sync._normalize_arg_path(args.plan, root)
        row = _plan_row(conn, rel)
        if row is None:
            msg = "planctl: %s is not indexed (missing / excluded / not a plan)." % rel
            if getattr(args, "json", False):
                import json
                print(json.dumps({"path": rel, "error": "not_indexed"}))
            else:
                print(msg)
            return 1

        (path, repo, stage, override, note, why, title, td, tt, ho, ht,
         _rd, _rt, drift, _ctx, _docs, dstatus, _smoke_total,
         _stage_state) = row

        frow = conn.execute(
            "SELECT kind, parse_err FROM files WHERE path=?", (rel,)).fetchone()
        kind = frow[0] if frow else "plan"
        parse_err = frow[1] if frow else None

        if kind == "runbook":
            # computed-on-read rollup (§4)
            rollup = sync.compute_rollup(conn, rel)
            status = (rollup or {}).get("status")
            drift = bool((rollup or {}).get("drift"))
            td = (rollup or {}).get("tasks_done", td)
            tt = (rollup or {}).get("tasks_total", tt)
        else:
            status = dstatus

        glyph = derive.glyph(status, drift) if status else "?"
        pct = derive.pct(td or 0, tt or 0)

        payload = {
            "path": path,
            "kind": kind,
            "repo": repo,
            "stage": stage,
            "derived_status": status,
            "glyph": glyph,
            "drift": bool(drift),
            "override": override,
            "note": note,
            "why": why,
            "tasks_done": td,
            "tasks_total": tt,
            "human_open": ho,
            "progress_pct": pct,
            "parse_err": parse_err,
        }

        if getattr(args, "json", False):
            import json
            print(json.dumps(payload))
        else:
            print("%s  %s %s  [%d/%d] %d%%  stage %s" % (
                path, glyph, status or "?", td or 0, tt or 0, pct, stage))
            if override:
                print("  override: %s%s" % (override, (" — " + note) if note else ""))
            if why:
                print("  why: %s" % why)
            if drift:
                print("  drift: declared done with open execution boxes")
            if parse_err:
                print("  parse_err: %s" % parse_err)
        return 0
    finally:
        conn.close()


# ── session orientation (design §3.6 `brief`) ─────────────────────────────────
_TOPN = 6     # per-section cap before "…and M more" elision (VC-5/W2C-8)
_BUDGET_TOK = 580  # hard ≤600-token target (chars//4); enforced after build
_TRUNC = 50   # max chars of note/why prose carried into a brief item


def _active_arcs(conn, repo_filter=None):
    """Runbooks (campaigns) with ≥1 non-done member — rollup + glyph, top-N."""
    arcs = []
    if repo_filter:
        rows = conn.execute(
            "SELECT f.path FROM files f JOIN plans p ON f.path=p.path "
            "WHERE f.kind='runbook' AND p.repo=? ORDER BY f.path", (repo_filter,))
    else:
        rows = conn.execute(
            "SELECT path FROM files WHERE kind='runbook' ORDER BY path")
    for (rb,) in rows:
        rollup = sync.compute_rollup(conn, rb)
        if not rollup:
            continue
        if rollup.get("members_total", 0) == 0:
            continue  # empty runbook (0 members) is NOT an active arc (§4/W2E-8)
        if rollup.get("status") == "done":
            continue  # active = ≥1 non-done member (design §4)
        arcs.append({
            "path": rb,
            "status": rollup.get("status"),
            "glyph": derive.glyph(rollup.get("status"), rollup.get("drift")),
            "members_done": rollup.get("members_done", 0),
            "members_total": rollup.get("members_total", 0),
            "tasks_done": rollup.get("tasks_done", 0),
            "tasks_total": rollup.get("tasks_total", 0),
            "pct": derive.pct(rollup.get("tasks_done", 0),
                              rollup.get("tasks_total", 0)),
        })
    arcs.sort(key=lambda a: a["path"])
    return arcs


def _queue(conn, where, params=(), repo_filter=None):
    """Helper: SELECT path,stage,why FROM plans WHERE <where> [+ repo filter]."""
    q = ("SELECT path,repo,stage,override,note,why FROM plans WHERE " + where)
    if repo_filter:
        q += " AND repo=?"
        params = params + (repo_filter,)
    q += " ORDER BY path"
    return conn.execute(q, params).fetchall()


def _elide(items, cap=_TOPN):
    """Top-N slice + an elision marker dict (VC-5/W2C-8)."""
    more = len(items) - cap
    return items[:cap], (more if more > 0 else 0)


def _trunc(s, n=_TRUNC):
    """Truncate prose to ~n chars (keeps brief items token-lean)."""
    if not s:
        return None
    s = str(s).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _enforce_budget(payload, max_tokens=_BUDGET_TOK):
    """Hard cap: if the brief JSON exceeds the token target, pop items from the
    largest section until it fits (VC-5/W2C-8 — the ≤600 cap must HOLD on a
    200-plan tree, not just a small one)."""
    import json
    sections = ["active_arcs", "blocked", "needs_review", "next"]
    while len(json.dumps(payload)) // 4 > max_tokens:
        # pick the section with the most items (most elision headroom)
        target = max(sections, key=lambda k: len(payload[k]["items"]))
        sec = payload[target]
        if not sec["items"]:
            return payload  # nothing left to trim; do not loop forever
        sec["items"].pop()
        sec["more"] = sec.get("more", 0) + 1
    return payload


def _build_brief(conn, root, repo_filter=None, runbook=None):
    """Assemble the brief payload (dict). Sections each carry ``items`` + ``more``."""
    if runbook:
        # scoped to ONE runbook: its rollup + direct members
        rb_rel = sync._normalize_arg_path(runbook, root)
        rollup = sync.compute_rollup(conn, rb_rel) or {}
        members = []
        for child, ck, _ord in conn.execute(
                "SELECT child,child_kind,ord FROM membership WHERE parent=? "
                "ORDER BY ord", (rb_rel,)):
            mrow = _plan_row(conn, child)
            ms = mrow[16] if mrow else None  # derived_status
            members.append({
                "path": child, "kind": ck,
                "status": ms, "glyph": derive.glyph(ms, False) if ms else "?",
                "stage": mrow[2] if mrow else None,
            })
        return {
            "runbook": rb_rel,
            "rollup": {
                "status": rollup.get("status"),
                "glyph": derive.glyph(rollup.get("status"), rollup.get("drift")),
                "members_done": rollup.get("members_done", 0),
                "members_total": rollup.get("members_total", 0),
                "pct": derive.pct(rollup.get("tasks_done", 0),
                                  rollup.get("tasks_total", 0)),
            },
            "members": members,
        }

    arcs = _active_arcs(conn, repo_filter)
    arcs_show, arcs_more = _elide(arcs)

    blocked = [{"path": r[0], "override": r[3], "note": _trunc(r[4])}
               for r in _queue(conn, "override IS NOT NULL AND override!=''",
                               repo_filter=repo_filter)]
    blocked_show, blocked_more = _elide(blocked)

    needs_review = [{"path": r[0], "stage": r[2]}
                    for r in _queue(conn, "derived_status='needs-review'",
                                    repo_filter=repo_filter)]
    nr_show, nr_more = _elide(needs_review)

    # next actions: ready plans (Sequence-registered, edge-unblocked, top-N).
    # Lean (path+stage) — the `next` verb carries the full why/detail.
    nxt_show, nxt_more = _elide(
        [{"path": n["path"], "stage": n["stage"]}
         for n in _next_list(conn, root, repo_filter=repo_filter)])

    return {
        "active_arcs": {"items": arcs_show, "more": arcs_more},
        "blocked": {"items": blocked_show, "more": blocked_more},
        "needs_review": {"items": nr_show, "more": nr_more},
        "next": {"items": nxt_show, "more": nxt_more},
    }


def _next_list(conn, root, repo_filter=None, limit=None):
    """Ready-work list (shared by brief's next-actions + the `next` verb).

    ready = derived_status in {ready,executing}, no override, Sequence-registered
    (untracked EXCLUDED per phase pin), not edge-blocked by an unfinished
    depends/blocks edge (W2C-9 — both kinds gate). Claims FLAG (claimed_by), not
    filter. Ordered by Sequence position."""
    order = sequence_order(root)
    order_idx = {p: i for i, p in enumerate(order)}

    ready = {}
    q = ("SELECT path,stage,why,derived_status FROM plans "
         "WHERE derived_status IN ('ready','executing') "
         "AND (override IS NULL OR override='')")
    params = ()
    if repo_filter:
        q += " AND repo=?"
        params = (repo_filter,)
    for path, stage, why, ds in conn.execute(q, params):
        if path in order_idx:  # Sequence-registered only (untracked excluded)
            ready[path] = (stage, why, ds)

    if not ready:
        return []

    unfinished = {r[0] for r in conn.execute(
        "SELECT path FROM plans WHERE derived_status IS NULL "
        "OR derived_status!='done'")}
    edge_blocked = set()
    for src, dst, kind in conn.execute("SELECT src,dst,kind FROM edges"):
        if kind == "depends":
            if src in ready and dst in unfinished:
                edge_blocked.add(src)   # src depends on dst → gate src while dst unfinished
        elif kind == "blocks":
            if src in unfinished and dst in ready:
                edge_blocked.add(dst)   # src blocks dst → gate dst while src unfinished

    claims = _live_claims(conn)
    out = []
    for path, (stage, why, _ds) in ready.items():
        if path in edge_blocked:
            continue
        out.append({"path": path, "stage": stage, "why": why,
                    "blocked_by": None, "claimed_by": _claimed_by(claims, path)})
    out.sort(key=lambda x: (order_idx.get(x["path"], 10 ** 9), x["path"]))
    if limit:
        out = out[:limit]
    return out


def _oneline(payload):
    """One-line SessionStart summary."""
    arcs = payload.get("active_arcs", {}).get("items", []) \
        if "active_arcs" in payload else []
    blocked = payload.get("blocked", {}).get("items", []) \
        if "blocked" in payload else []
    nr = payload.get("needs_review", {}).get("items", []) \
        if "needs_review" in payload else []
    nxt = payload.get("next", {}).get("items", []) \
        if "next" in payload else []
    parts = ["%d active arc(s)" % len(arcs),
             "%d blocked" % len(blocked),
             "%d needs-review" % len(nr)]
    if nxt:
        parts.append("next: " + ", ".join(n["path"].split("/")[-1] for n in nxt[:3]))
    return " · ".join(parts)


def cmd_brief(args):
    """``planctl brief [--repo R] [--runbook RB] [--oneline] [--json]``."""
    root = statedir.project_root()
    conn = db.open_db()
    try:
        sync.ensure_fresh(conn, root)
        repo_filter = getattr(args, "repo", None)
        runbook = getattr(args, "runbook", None)
        payload = _build_brief(conn, root, repo_filter=repo_filter, runbook=runbook)
        if not runbook:
            _enforce_budget(payload)  # hard ≤600-token cap (VC-5/W2C-8)

        if getattr(args, "oneline", False):
            print(_oneline(payload))
            return 0
        if getattr(args, "json", False):
            import json
            print(json.dumps(payload))
            return 0
        _print_brief_human(payload, runbook=bool(runbook))
        return 0
    finally:
        conn.close()


def _print_brief_human(payload, runbook=False):
    if runbook:
        rb = payload["rollup"]
        print("runbook %s  %s %s  [%d/%d members] %d%%" % (
            payload["runbook"], rb["glyph"], rb.get("status") or "?",
            rb["members_done"], rb["members_total"], rb["pct"]))
        for m in payload["members"]:
            print("  %s %s  %s" % (m["glyph"], m["path"], m.get("stage") or ""))
        return

    def _section(title, sec, fmt):
        items, more = sec["items"], sec["more"]
        print("%s (%d):" % (title, len(items) + more))
        if not items:
            print("  —")
        for it in items:
            print("  " + fmt(it))
        if more:
            print("  …and %d more" % more)

    _section("Active arcs", payload["active_arcs"],
             lambda a: "%s %s %s  [%d/%d tasks]" % (
                 a["glyph"], a["path"], a.get("status") or "?",
                 a["tasks_done"], a["tasks_total"]))
    _section("Blocked", payload["blocked"],
             lambda b: "! %s — %s%s" % (
                 b["path"], b["override"],
                 (": " + b["note"]) if b["note"] else ""))
    _section("Needs review", payload["needs_review"],
             lambda n: "⊙ %s (stage %s)" % (n["path"], n.get("stage") or "?"))
    _section("Next", payload["next"],
             lambda nx: "▹ %s%s" % (nx["path"],
                                    " [claimed:%s]" % nx["claimed_by"]
                                    if nx.get("claimed_by") else ""))


# ── ready-work verb (phase 0c.3) ──────────────────────────────────────────────
def cmd_next(args):
    """``planctl next [--runbook RB] [--json]`` — ready-work, ledger-ordered."""
    root = statedir.project_root()
    conn = db.open_db()
    try:
        sync.ensure_fresh(conn, root)
        repo_filter = None
        runbook = getattr(args, "runbook", None)
        # --runbook scopes next to that runbook's member plans
        if runbook:
            rb_rel = sync._normalize_arg_path(runbook, root)
            members = {r[0] for r in conn.execute(
                "SELECT child FROM membership WHERE parent=?", (rb_rel,))}
            nxt = [n for n in _next_list(conn, root) if n["path"] in members]
        else:
            nxt = _next_list(conn, root, repo_filter=repo_filter)

        if getattr(args, "json", False):
            import json
            print(json.dumps(nxt))
            return 0
        if not nxt:
            print("planctl next: no ready work (nothing ready/executing, "
                  "unblocked, and Sequence-registered).")
            return 0
        print("ready work (%d):" % len(nxt))
        for n in nxt:
            claim = (" [claimed:%s]" % n["claimed_by"]) if n.get("claimed_by") else ""
            why = ("  — %s" % n["why"]) if n.get("why") else ""
            print("  ▹ %s (stage %s)%s%s" % (n["path"], n.get("stage") or "?",
                                             claim, why))
        return 0
    finally:
        conn.close()
