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
  * noncanonical headings containing "smoke" with plain bullets beneath them →
    advisory so exact smoke-heading matching is visible rather than mysterious.
  * 9p placement of ``state.db``/``events.jsonl`` → refuse + instruct (I5).

Calls ``claims._sweep_stale`` before the claims/integrity checks. ``--json`` →
``{ok, integrity, derive_v, cycles, missing, parse_err, stale_override,
  smoke_near_miss, placement}``.

Stdlib only.
"""
import json
import os
import sqlite3

from planctl import claims, db, derive, parse, runbook, statedir, sync


_SMOKE_LABEL_MAX_WORDS = 5


def _is_smoke_label(depth, heading_text):
    """True when a 'smoke'-bearing heading plausibly LABELS a smoke section.

    The near-miss advisory exists to catch an author who wrote ``## Smoke Tests:``
    or ``## Manual smoke`` and silently missed the badge. Matching every heading
    that merely contains the word buries that signal: a document title
    ("Comprehensive Pipeline Render Smoke Suite — Master Plan") or a task heading
    ("Task 3: Smoke test with the offline preview tool (dry-run)") always has
    plain bullets somewhere beneath it, so the has-bullet check alone cannot
    discriminate. Length can: a label is a few words, a sentence describing work
    is not, and every observed false positive was long.

    Depth is deliberately NOT a filter. ``parse_smoke`` honours a canonical
    smoke heading at ANY depth including H1, so excluding H1 here would let an
    H1 near-miss go unwarned about a section the parser would otherwise have
    accepted — the advisory must cover exactly what the parser covers.
    """
    del depth  # intentionally unused; see above
    return len(heading_text.split()) <= _SMOKE_LABEL_MAX_WORDS


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
                "AND override!='' AND stage>=6 "
                "AND (stage_state IS NULL OR stage_state!='active') "
                "ORDER BY path")
        ]

        # Exact smoke headings are intentionally strict. Surface near misses
        # only when they actually contain plain bullets, so ordinary prose/task
        # headings that merely mention smoke do not generate noise. Section
        # extent and fence handling mirror parse.parse_smoke.
        smoke_near_miss = []
        for (path,) in conn.execute("SELECT path FROM files ORDER BY path"):
            full_path = os.path.join(root, path)
            try:
                with open(full_path, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            active = []
            in_fence = False
            for line_no, line in enumerate(text.split("\n"), 1):
                if line.lstrip().startswith(parse._FENCE_PREFIXES):
                    in_fence = not in_fence
                    continue
                if in_fence:
                    continue
                heading = parse._HEADING_RE.match(line)
                if heading:
                    depth = len(heading.group(1))
                    for candidate in active:
                        if depth <= candidate["depth"] and candidate["has_bullet"]:
                            smoke_near_miss.append({
                                "path": path,
                                "line": candidate["line"],
                                "heading": candidate["heading"],
                            })
                    active = [c for c in active if c["depth"] < depth]
                    heading_text = heading.group(2).strip()
                    if (
                        "smoke" in heading_text.casefold()
                        and not parse._SMOKE_HEAD_RE.match(heading_text)
                        and _is_smoke_label(depth, heading_text)
                    ):
                        active.append({
                            "depth": depth,
                            "line": line_no,
                            "heading": heading_text,
                            "has_bullet": False,
                        })
                    continue
                if parse._SMOKE_BULLET_RE.match(line):
                    for candidate in active:
                        candidate["has_bullet"] = True
            for candidate in active:
                if candidate["has_bullet"]:
                    smoke_near_miss.append({
                        "path": path,
                        "line": candidate["line"],
                        "heading": candidate["heading"],
                    })
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
        "smoke_near_miss": smoke_near_miss,
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
    print("  smoke_near_miss: %d%s" % (
        len(p["smoke_near_miss"]),
        "" if not p["smoke_near_miss"] else " — " + ", ".join(
            "%s:%d (%s)" % (item["path"], item["line"], item["heading"])
            for item in p["smoke_near_miss"])))
