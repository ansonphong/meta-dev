#!/usr/bin/env python3
"""doctor.py — the integrity sweep (design §3.3; invariants I2, I3, I5).

``cmd_doctor`` — ``planctl doctor [--json]`` — a one-shot health check + auto-
heal over the disposable read-model:

  * ``PRAGMA integrity_check`` (ONLY here + sync — BC4); on failure, ``heal()`` =
    ``rm`` all three sidecars + ``--full`` rebuild (I3 — corruption is a non-
    event: detect → delete → rebuild, never repaired; BC6).
  * ``meta.derive_v != DERIVE_V`` → auto ``--full`` (rule change, I2).
  * membership cycles (hand-edited, bypassing the ``runbook add`` door) → marked
    ``parse_err`` by sync; listed loud here.
  * missing members (``membership.child`` not on disk) → listed.
  * malformed frontmatter (``files.parse_err`` non-null) → listed.
  * stale-override advisory (VC-8): ``override`` present AND ``stage >= 6`` →
    flagged as stale-override drift (the mirror of ``✓⚠``).
  * 9p placement of ``state.db``/``events.jsonl`` → refuse + instruct (I5).

Calls ``claims._sweep_stale`` before the claims/integrity checks. ``--json`` →
``{ok, integrity, derive_v, cycles, missing, parse_err, stale_override,
placement}``.

Stdlib only.
"""
import json
import os
import sqlite3

from planctl import claims, db, derive, runbook, statedir, sync


def cmd_doctor(args):
    """``planctl doctor [--json]`` — integrity sweep + auto-heal."""
    root = statedir.project_root()
    sdir = statedir.state_dir()

    # Placement (I5): state must live off the 9p/drvfs mount. open_db already
    # refuses 9p, so this is belt-and-suspenders + the reportable signal.
    on_9p = statedir.is_9p(os.path.join(sdir, "state.db"))
    placement = {"state_dir": sdir, "on_9p": bool(on_9p)}

    healed = False
    integrity = "ok"

    # Open-or-heal: a corrupt DB may fail ``open_db`` itself (garbage header) OR
    # ``integrity_check`` (page damage). Both trigger heal() (I3: detect→delete→
    # rebuild). NB: SQLite tolerates trailing-byte appends (``echo x >>`` does
    # NOT break ``integrity_check``) — a real heal is triggered by header/page
    # damage, which ``open_db``/``check_integrity`` surface.
    conn = None
    try:
        # Open-or-heal: a corrupt DB may fail ``open_db`` itself (garbage header)
        # OR ``integrity_check`` (page damage). Both trigger heal() (I3: detect→
        # delete→rebuild). NB: SQLite tolerates trailing-byte appends
        # (``echo x >>`` does NOT break ``integrity_check``) — a real heal is
        # triggered by header/page damage, which these surface.
        try:
            conn = db.open_db()
            db.check_integrity(conn)
        except (db.DBCorrupt, sqlite3.DatabaseError) as exc:
            integrity = "corrupt: %s" % exc
            if conn is not None:
                try:
                    conn.close()
                except sqlite3.DatabaseError:
                    pass
                conn = None
            db.heal(sdir)              # rm all three sidecars + recreate schema
            conn = db.open_db()
            db.check_integrity(conn)   # confirm the heal worked
            integrity = "ok (healed)"
            healed = True

        stale = db.is_stale(conn, derive.DERIVE_V)  # decide rebuild from pre-state

        if healed or stale:
            # Auto --full (I2/I3): drop + rebuild every derived row.
            sync._drop_derived_rows(conn)
            sync._reindex_paths(conn, root, sync._walk_indexed(root),
                                full=True, head_sha=sync._head_sha(root),
                                mark_cycles=True)
        else:
            sync.ensure_fresh(conn, root)
        # Re-read derive_v AFTER any rebuild so the payload reflects post-heal
        # state (a healed DB was empty → derive_v was None until the rebuild).
        derive_v_row = conn.execute(
            "SELECT value FROM meta WHERE key='derive_v'").fetchone()
        derive_v = derive_v_row[0] if derive_v_row else None
        # Ensure parse_err reflects any current cycle (idempotent; sync owns it
        # on the write paths, but doctor is an explicit integrity verb).
        runbook.mark_cycle_parse_errors(conn)

        # Sweep stale claims before the claims/integrity reads.
        claims._sweep_stale(conn)
        conn.commit()

        cycles = runbook.detect_cycles(conn)

        missing = []
        for (child,) in conn.execute("SELECT DISTINCT child FROM membership"):
            if not os.path.isfile(os.path.join(root, child)):
                missing.append(child)

        parse_err_files = [
            {"path": p, "parse_err": e}
            for p, e in conn.execute(
                "SELECT path, parse_err FROM files WHERE parse_err IS NOT NULL "
                "ORDER BY path")
        ]

        stale_override = [
            p for (p,) in conn.execute(
                "SELECT path FROM plans WHERE override IS NOT NULL "
                "AND override!='' AND stage>=6 ORDER BY path")
        ]
    finally:
        if conn is not None:
            conn.close()

    ok = (
        not on_9p
        and integrity.startswith("ok")
        and not cycles
        and not missing
        and not parse_err_files
    )

    payload = {
        "ok": bool(ok),
        "integrity": integrity,
        "derive_v": derive_v,
        "cycles": cycles,
        "missing": missing,
        "parse_err": parse_err_files,
        "stale_override": stale_override,
        "placement": placement,
    }
    if getattr(args, "json", False):
        print(json.dumps(payload))
        return 0
    _print_doctor_human(payload)
    return 0 if ok else 1


def _print_doctor_human(p):
    status = "OK" if p["ok"] else "ISSUES"
    print("planctl doctor: %s" % status)
    print("  integrity    : %s" % p["integrity"])
    print("  derive_v     : %s (expected %s)" % (
        p["derive_v"], derive.DERIVE_V))
    print("  placement    : %s%s" % (
        p["placement"]["state_dir"],
        "  ⚠ ON 9p (I5 violation)" if p["placement"]["on_9p"] else ""))
    cyc = p["cycles"]
    print("  cycles       : %d%s" % (
        len(cyc), "" if not cyc else " — " + ", ".join("%s<->%s" % tuple(c) for c in cyc)))
    print("  missing      : %d%s" % (
        len(p["missing"]), "" if not p["missing"] else " — " + ", ".join(p["missing"])))
    print("  parse_err    : %d%s" % (
        len(p["parse_err"]),
        "" if not p["parse_err"] else " — " + ", ".join(
            e["path"] for e in p["parse_err"])))
    print("  stale_override: %d%s" % (
        len(p["stale_override"]),
        "" if not p["stale_override"] else " — " + ", ".join(p["stale_override"])))
