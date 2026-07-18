#!/usr/bin/env python3
"""claims.py — ``claim`` / ``release`` / ``list`` (design §3.5; invariants I5, I6).

The work-claim registry: a SQLite ``claims`` table (off-9p, in ``state.db``)
that coordinates concurrent sessions dispatching plan-editing workers to the
SHARED tree — the no-worktree alternative to filesystem isolation. Two
overlapping live claims cannot both exist (the second refuses, exit 3).

  * ``cmd_claim`` — ``planctl claim <plan> [--pid P] [--session S] [--ttl S]``:
    atomic insert under ``BEGIN IMMEDIATE``. Overlap is a PREFIX scope match
    (not PK-equality — ``plans/meta/`` overlaps ``plans/meta/foo.md``). Stale
    claims (past TTL or dead pid) are swept first. Returns **exit 3** if a LIVE
    conflicting claim exists (G-IMP5); lock-busy/timeout → **exit 1** (W3A-4);
    usage → exit 2.
  * ``cmd_release`` — ``planctl release <plan>``: drop the exact-scope claim.
  * ``cmd_list`` — ``planctl list [--json]``: live claims; ``--json`` field names
    pinned ``.scope``/``.session``/``.pid`` for the ``on-session-start.sh`` jq
    banner (WC-4/W3A-4).

``claims`` carries ``pid`` + ``ttl=1800s`` (W2D-7/R13). The audit trail
(``claim``/``release``/swept-expiry) lives in ``events.jsonl`` (no separate
audit table — I5). The ``_sweep_stale`` helper is also called by ``doctor``/
``sync`` (0e) — exposed here as the single sweep implementation.

Stdlib only.
"""
import json
import os
import socket
import sqlite3
import time

from planctl import db, events, statedir, sync

_TTL_DEFAULT = 1800


def _now():
    return time.time()


def _host():
    try:
        return socket.gethostname()
    except Exception:
        return "?"


def _norm_scope(s):
    """Collapse ``//``, strip trailing ``/`` + leading ``./`` (repo-relative scope)."""
    if not isinstance(s, str):
        return ""
    s = s.replace("\\", "/").strip()
    while "//" in s:
        s = s.replace("//", "/")
    while s.startswith("./"):
        s = s[2:]
    s = s.rstrip("/")
    return s.lstrip("/")


def _resolve_scope(args):
    """Repo-relative scope string for a claim arg (matches index ``plan`` paths).

    Resolves through the project root (cwd-independent) then normalizes, so a
    claim on ``plans/meta/foo.md`` overlaps the index's ``plans/meta/foo.md``
    row (read._claimed_by compares scope ↔ plan path)."""
    root = statedir.project_root()
    rel = sync._normalize_arg_path(args.plan, root)
    return _norm_scope(rel)


def _overlaps(a, b):
    """PREFIX scope match (design — overlap is a prefix relation, not PK-equality).

    Two scopes overlap if equal or one is a path-prefix (ancestor) of the other.
    Trailing-slash-safe: ``plans/meta`` overlaps ``plans/meta/foo.md`` but NOT
    ``plans/meta-other/foo.md`` (the ``/`` boundary prevents false siblings)."""
    if a == b:
        return True
    return a.startswith(b + "/") or b.startswith(a + "/")


def _pid_alive(pid):
    """True if ``pid`` is a running process (``kill -0``). No pid → assume alive."""
    if not pid:
        return True
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def _row_live(row):
    """``(scope,session,host,ts,pid,status,ttl)`` → True if a LIVE claim.

    Live = ``status=='claimed'`` AND within TTL AND pid alive (W2D-7/R13)."""
    _scope, _session, _host, ts, pid, status, ttl = row
    if status != "claimed":
        return False
    try:
        age = _now() - float(ts)
        ttl_s = int(ttl or _TTL_DEFAULT)
    except (TypeError, ValueError):
        return False
    if age > ttl_s:
        return False
    if not _pid_alive(pid):
        return False
    return True


def _sweep_stale(conn):
    """Delete expired/dead/released claims; return ``[(scope, reason)]`` swept.

    Does NOT commit — the caller's transaction (claim) or explicit commit
    (list/release/doctor) owns it. Each swept live-but-stale claim is returned
    so the caller can emit an ``expired`` audit event after its commit lands
    (never before — a rolled-back claim must not log a phantom expiry)."""
    swept = []
    for row in conn.execute(
            "SELECT scope,session,host,ts,pid,status,ttl FROM claims"):
        scope = row[0]
        status = row[5]
        if status != "claimed":
            swept.append((scope, "status_%s" % status))  # leftover released/expired
            continue
        if not _row_live(row):
            ts, pid = row[3], row[4]
            try:
                age = _now() - float(ts)
                ttl_s = int(row[6] or _TTL_DEFAULT)
            except (TypeError, ValueError):
                age, ttl_s = 10 ** 9, 0
            reason = "ttl" if age > ttl_s else "dead_pid"
            swept.append((scope, reason))
    for scope, _reason in swept:
        conn.execute("DELETE FROM claims WHERE scope=?", (scope,))
    return swept


# ── claim ────────────────────────────────────────────────────────────────────
def _is_locked_error(exc):
    return isinstance(exc, sqlite3.OperationalError) and "lock" in str(exc).lower()


def cmd_claim(args):
    """``planctl claim <plan> [--pid P] [--session S] [--ttl S]``.

    Exit 0 granted · 3 blocked (live overlap, G-IMP5) · 1 lock-busy (W3A-4) ·
    2 usage. The critical section (sweep → overlap-scan → insert) runs under
    ``BEGIN IMMEDIATE`` so two concurrent claims for overlapping scopes can't
    both pass the check-then-claim TOCTOU."""
    scope = _resolve_scope(args)
    if not scope:
        sys_err("planctl claim: empty scope")
        return 2
    # Default pid = PPID (the caller/conductor), mirroring worker-claim.sh's
    # ``$PPID`` — planctl itself exits immediately, so getpid() would mark every
    # claim dead on the next sweep. PPID is the long-lived owner (the conductor
    # session that dispatched the worker); --pid overrides for an explicit worker.
    pid = getattr(args, "pid", None)
    pid = pid if pid is not None else os.getppid()
    session = getattr(args, "session", None) or \
        os.environ.get("CLAUDE_SESSION_ID") or ("pid-%d" % os.getppid())
    ttl = getattr(args, "ttl", None)
    ttl = ttl if ttl is not None else _TTL_DEFAULT
    now = _now()

    conn = db.open_db()
    conn.isolation_level = None  # manage BEGIN/COMMIT manually for IMMEDIATE
    try:
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as e:
            if _is_locked_error(e):
                _emit(args, {"scope": scope, "granted": False, "reason": "lock_busy"})
                return 1
            raise
        swept = []
        try:
            swept = _sweep_stale(conn)
            conflict = None
            for row in conn.execute(
                    "SELECT scope,session,host,ts,pid,status,ttl FROM claims"):
                if _row_live(row) and _overlaps(scope, row[0]):
                    conflict = row
                    break
            if conflict:
                conn.execute("ROLLBACK")
                _emit_blocked(args, scope, conflict)
                return 3
            conn.execute(
                "INSERT OR REPLACE INTO claims(scope,session,host,ts,pid,status,ttl) "
                "VALUES(?,?,?,?,?,?,?)",
                (scope, session, _host(), now, pid, "claimed", ttl))
            conn.execute("COMMIT")
        except sqlite3.OperationalError as e:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            if _is_locked_error(e):
                _emit(args, {"scope": scope, "granted": False, "reason": "lock_busy"})
                return 1
            raise

        # audit events AFTER commit (claim durable) — swept expiries first.
        for cscope, creason in swept:
            events.append({"event": "release", "plan": cscope,
                           "data": {"expired": True, "reason": creason}})
        events.append({"event": "claim", "plan": scope,
                       "data": {"session": session, "pid": pid, "ttl": ttl}})
        _emit_granted(args, scope, session, pid, ttl)
        return 0
    finally:
        conn.close()


# ── release ──────────────────────────────────────────────────────────────────
def cmd_release(args):
    """``planctl release <plan>`` — drop the exact-scope claim (exit 0 either way)."""
    scope = _resolve_scope(args)
    conn = db.open_db()
    try:
        row = conn.execute(
            "SELECT scope FROM claims WHERE scope=?", (scope,)).fetchone()
        with conn:
            conn.execute("DELETE FROM claims WHERE scope=?", (scope,))
        released = row is not None
        if released:
            events.append({"event": "release", "plan": scope,
                           "data": {"expired": False}})
        _emit(args, {"scope": scope, "released": released})
        return 0
    finally:
        conn.close()


# ── list ─────────────────────────────────────────────────────────────────────
def cmd_list(args):
    """``planctl list [--json]`` — live claims (``.scope``/``.session``/``.pid`` pinned)."""
    conn = db.open_db()
    try:
        swept = _sweep_stale(conn)
        conn.commit()
        for cscope, creason in swept:
            events.append({"event": "release", "plan": cscope,
                           "data": {"expired": True, "reason": creason}})
        rows = conn.execute(
            "SELECT scope,session,pid,ts,ttl,host FROM claims "
            "WHERE status='claimed' ORDER BY scope").fetchall()
        out = [{"scope": s, "session": se, "pid": p, "ts": t, "ttl": tl, "host": h}
               for (s, se, p, t, tl, h) in rows]
        if getattr(args, "json", False):
            print(json.dumps(out))
        else:
            if not out:
                print("(no active claims)")
            for r in out:
                print("  %-40s  session=%s  pid=%s  ttl=%ss"
                      % (r["scope"], r["session"], r["pid"], r["ttl"]))
        return 0
    finally:
        conn.close()


# ── output helpers ───────────────────────────────────────────────────────────
def sys_err(msg):
    import sys
    sys.stderr.write(msg + "\n")


def _emit(args, payload):
    if getattr(args, "json", False):
        print(json.dumps(payload))


def _emit_granted(args, scope, session, pid, ttl):
    if getattr(args, "json", False):
        print(json.dumps({"scope": scope, "granted": True,
                          "session": session, "pid": pid, "ttl": ttl}))
    else:
        print("[planctl claim] GRANTED '%s' (pid=%s session=%s ttl=%ss)"
              % (scope, pid, session, ttl))


def _emit_blocked(args, scope, conflict):
    cscope, csession, _chost, cts, cpid, _cstatus, cttl = conflict
    try:
        age = int(_now() - float(cts))
    except (TypeError, ValueError):
        age = -1
    msg = ("[planctl claim] BLOCKED '%s' overlaps LIVE claim '%s' "
           "(session=%s pid=%s age=%ds ttl=%ss). Partition by directory, wait, "
           "or it auto-expires." % (scope, cscope, csession, cpid, age, cttl))
    import sys
    sys.stderr.write(msg + "\n")
    if getattr(args, "json", False):
        print(json.dumps({"scope": scope, "granted": False, "reason": "overlap",
                          "conflict": {"scope": cscope, "session": csession,
                                       "pid": cpid}}))
