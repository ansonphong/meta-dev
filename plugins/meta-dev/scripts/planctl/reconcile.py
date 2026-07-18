#!/usr/bin/env python3
"""reconcile.py — ``planctl reconcile``: the Stop-hook composition (design §3.7).

Composes the per-Stop work into ONE cheap pass:
  1. Fast-path freshness (ensure_fresh-style — no porcelain scan; trusts
     PostToolUse ``sync --file`` to keep dirty files hot).
  2. DONE-gate decision matrix AS SQL over the index — the same 5-outcome
     matrix as the legacy ``on-run-complete.sh`` inline python, preserved
     verbatim:
       (A) clean+reviewed        → stamp stage 6 + render runbook + done_gate
       (B) docs evidence missing  → docs_missing + MED inbox (no stamp)
       (C) clean+no-review       → review_missing + MED inbox
       (D) open boxes + drift    → FAIL LOUD (HIGH inbox + event)
       (E) open + executing      → no-op (run alive)
     Stage-6 done plans are EXACTLY excluded (W1-D2).
  3. Render only DIRTY runbooks — ``sync``'s sha-based ``rebuilt_runbooks``
     UNION self-heal (rollup-vs-rendered-block compare), NOT the
     unconditional ``find … _runbook-*.md`` loop. Budget <1s typical.

Performance: review-verdicts from BOTH logs are read ONCE into a cached dict
(not once per plan — the legacy log is 2.5MB). Same for stage-5 timestamps.
``--json`` returns ``{synced, decisions, rendered, elapsed_ms}``.

Stdlib only.
"""
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import time

from planctl import db, derive, events, parse, runbook, statedir, sync



def _like_prefix(prefix):
    """Escape LIKE metacharacters in a path prefix.

    ``_`` is a single-char wildcard in SQL LIKE, so a scope like
    ``plans/app/_AUDIT/`` also matches a sibling ``plans/app/XAUDIT/``. Real
    directories in this tree start with ``_`` (``_AUDIT``, ``_archive``), so the
    escape is load-bearing, not theoretical. Pair with ``ESCAPE '\\'``."""
    return prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

def _parse_ts(raw):
    """Coerce a legacy event timestamp to an epoch float.

    The legacy log writes ISO-8601 (``2026-07-17T18:00:00Z``); the new log
    writes epoch floats. An isdigit() guard collapses EVERY ISO string to 0,
    which makes "latest wins" degenerate into "first wins" — inverting recency
    for both review verdicts and stage-5 transitions. Handle both shapes."""
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    if not s:
        return 0.0
    try:
        return float(s)  # bare epoch
    except ValueError:
        pass
    iso = s.replace("Z", "+00:00")
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            import datetime as _dt
            return _dt.datetime.strptime(iso, fmt).timestamp()
        except (ValueError, OverflowError):
            continue
    return 0.0


def _quiet_stdout(enabled):
    """Swallow stdout when emitting a JSON payload.

    ``--json`` promises ONE parseable object on stdout; the stage stamp and the
    runbook render both print human lines. Without this the payload is preceded
    by prose exactly when a stamp fires — the case a consumer most needs to
    parse."""
    if enabled:
        return contextlib.redirect_stdout(io.StringIO())
    return contextlib.nullcontext()


# ── Cached dual-log readers (read ONCE, not per-plan) ──────────────────────────

def _build_review_cache():
    """Read BOTH event logs ONCE; return ``{plan_rel: ('pass'|'fail', ts)}``.

    Until M4 flips to new-log-only, BOTH logs are authoritative. Later ``ts``
    in either log wins per plan."""
    cache = {}  # plan_rel → (verdict, ts_float)

    # ── New log (planctl events.jsonl) ─────────────────────────────────────
    for rec in events.query(event="review_verdict"):
        plan = str(rec.get("plan", "")).replace(os.sep, "/")
        if plan.startswith("./"):
            plan = plan[2:]
        data = rec.get("data", {}) if isinstance(rec.get("data"), dict) else {}
        v = str(data.get("verdict", "")).lower()
        try:
            ts = float(rec.get("ts", 0))
        except (TypeError, ValueError):
            ts = 0
        if plan not in cache or ts > cache[plan][1]:
            cache[plan] = (v, ts)

    # ── Legacy log (state.events.jsonl) ────────────────────────────────────
    root = statedir.project_root()
    legacy = os.path.join(root, "plans", "_dashboard", "state.events.jsonl")
    if os.path.isfile(legacy):
        try:
            with open(legacy, encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or '"review_verdict"' not in line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("event") != "review_verdict":
                        continue
                    plan = str(rec.get("plan", "")).replace(os.sep, "/")
                    if plan.startswith("./"):
                        plan = plan[2:]
                    v = str(rec.get("verdict", "")).lower()
                    ts_f = _parse_ts(rec.get("time") or rec.get("ts"))
                    # ``>=`` (not ``>``): the log is append-ordered, so on a tie
                    # the LATER line wins — matching the legacy hook, which
                    # overwrote ``latest`` on every match (last wins).
                    if plan not in cache or ts_f >= cache[plan][1]:
                        cache[plan] = (v, ts_f)
        except OSError:
            pass
    return cache


def _build_stage5_ts_cache():
    """Read BOTH event logs ONCE; return ``{plan_rel: ts_iso_string}`` for the
    latest stage-5 transition per plan."""
    cache = {}  # plan_rel → (ts_iso, ts_float)

    # ── New log ─────────────────────────────────────────────────────────────
    for rec in events.query(event="stage"):
        plan = str(rec.get("plan", "")).replace(os.sep, "/")
        if plan.startswith("./"):
            plan = plan[2:]
        data = rec.get("data", {}) if isinstance(rec.get("data"), dict) else {}
        sn = data.get("stage") or data.get("stage_num")
        try:
            if int(sn) != 5:
                continue
        except (TypeError, ValueError):
            continue
        try:
            ts = float(rec.get("ts", 0))
        except (TypeError, ValueError):
            ts = 0
        iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
        if plan not in cache or ts > cache[plan][1]:
            cache[plan] = (iso, ts)

    # ── Legacy log ──────────────────────────────────────────────────────────
    root = statedir.project_root()
    legacy = os.path.join(root, "plans", "_dashboard", "state.events.jsonl")
    if os.path.isfile(legacy):
        try:
            with open(legacy, encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or "stage_transition" not in line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("event") != "stage_transition":
                        continue
                    plan = str(rec.get("plan", "")).replace(os.sep, "/")
                    if plan.startswith("./"):
                        plan = plan[2:]
                    sn = rec.get("stage_num") or rec.get("stage")
                    try:
                        sn_i = int(sn)
                    except (TypeError, ValueError):
                        sn_i = 5 if str(sn).lower() in ("5", "execute") else -1
                    if sn_i != 5:
                        continue
                    t = rec.get("time") or rec.get("ts")
                    if not t:
                        continue
                    ts_f = _parse_ts(t)
                    # ``>=`` — append-ordered log, latest stage-5 transition
                    # wins (a stale earlier ts widens the docs-evidence window).
                    if plan not in cache or ts_f >= cache[plan][1]:
                        cache[plan] = (str(t), ts_f)
        except OSError:
            pass
    return cache


def _lookup_review_verdict(cache, plan_rel):
    """Look up in pre-built cache. Returns ``'pass'``, ``'fail'``, or ``None``."""
    plan_rel = plan_rel.replace(os.sep, "/")
    entry = cache.get(plan_rel)
    if entry is None:
        return None
    return entry[0]


def _lookup_stage5_ts(cache, plan_rel):
    """Look up in pre-built cache. Returns ISO string or None."""
    plan_rel = plan_rel.replace(os.sep, "/")

    # Direct match first
    entry = cache.get(plan_rel)
    if entry:
        return entry[0]

    # Plan-dir match (a stage-5 transition on a sibling file counts for the
    # master plan scope — mirrors the legacy hook's dir-based matching).
    plan_dir = plan_rel.rsplit("/", 1)[0] if "/" in plan_rel else plan_rel
    for cached_plan, (iso, _ts) in cache.items():
        cached_dir = cached_plan.rsplit("/", 1)[0] if "/" in cached_plan else cached_plan
        if plan_dir == cached_dir or cached_plan.startswith(plan_dir + "/") or plan_rel.startswith(cached_dir + "/"):
            return iso
    return None


# ── scope resolution (master-vs-dir rule, W1-D5) ───────────────────────────────

def _build_scope_set(conn, root):
    """Find all stage-5 plans, resolve scopes with the master-vs-dir rule.

    Returns ``[(scope_path, plan_rel), …]`` deduped by scope.

    W1-D5: A dir with ``00-master-plan.md`` AND zero phase-file checkboxes →
    scope = master only; else scope = whole dir. Stage-5 means EXACTLY stage=5
    (W1-D2 — stage-6 done plans are NOT reprocessed)."""
    rows = conn.execute(
        "SELECT path FROM plans WHERE stage=5 "
        "AND (override IS NULL OR override='')").fetchall()

    plan_rel_set = {r[0] for r in rows}
    if not plan_rel_set:
        return []

    # Group by directory
    dirs = {}
    for plan_rel in plan_rel_set:
        d = os.path.dirname(plan_rel) if "/" in plan_rel else "."
        dirs.setdefault(d, []).append(plan_rel)

    seen_scope = set()
    scopes = []
    for d, plans_in_dir in sorted(dirs.items()):
        master_rel = os.path.join(d, "00-master-plan.md") if d != "." else "00-master-plan.md"
        has_master = master_rel in plan_rel_set or os.path.isfile(
            os.path.join(root, master_rel))

        if has_master:
            # Check if any non-master .md file in this dir has tasks (total>0)
            phase_has_boxes = False
            for p in plans_in_dir:
                if p == master_rel:
                    continue
                row = conn.execute(
                    "SELECT tasks_total FROM plans WHERE path=?", (p,)).fetchone()
                if row and (row[0] or 0) > 0:
                    phase_has_boxes = True
                    break
            # Also check non-stage-5 files in same dir with tasks
            if not phase_has_boxes:
                other = conn.execute(
                    "SELECT p.path FROM plans p WHERE p.path LIKE ? ESCAPE '\\' "
                    "AND p.path != ? AND p.tasks_total > 0 LIMIT 1",
                    (_like_prefix(d + "/") + "%", master_rel)).fetchone()
                if other:
                    phase_has_boxes = True

            scope = master_rel if not phase_has_boxes else d
            plan = master_rel
        else:
            scope = plans_in_dir[0]
            plan = plans_in_dir[0]

        if scope in seen_scope:
            continue
        seen_scope.add(scope)
        scopes.append((scope, plan))

    return scopes


# ── docs/context evidence gate ──────────────────────────────────────────────────

def _owning_repo(abs_path):
    """Walk up from ``abs_path`` to the nearest ``.git`` dir."""
    cur = os.path.abspath(abs_path)
    if os.path.isfile(cur):
        cur = os.path.dirname(cur)
    for _ in range(40):
        if os.path.isdir(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def _docs_evidence_gate(conn, root, plan_rel, stage5_ts):
    """Validate declared ``context:``/``docs:`` paths have git commits since
    ``stage5_ts``. Returns ``([]blocks, []warnings)`` — empty blocks = ok.

    Soft-warns (never hard-blocks) when ts or owning repo is unresolvable."""
    row = conn.execute(
        "SELECT context_json, docs_json FROM plans WHERE path=?",
        (plan_rel,)).fetchone()
    if not row:
        return [], []

    ctx = json.loads(row[0]) if row[0] else []
    docs = json.loads(row[1]) if row[1] else []
    declared = (ctx or []) + (docs or [])

    if not declared:
        return [], []

    if not stage5_ts:
        return [], ["docs-gate: no stage_5 transition ts for %s — soft-pass" % plan_rel]

    blocks = []
    warnings = []

    for rel in declared:
        abs_p = os.path.join(root, rel) if not os.path.isabs(rel) else rel
        repo = _owning_repo(abs_p)
        if repo is None:
            warnings.append(
                "docs-gate: unresolvable repo for %r — advisory" % rel)
            continue
        try:
            rel_in_repo = os.path.relpath(os.path.abspath(abs_p), repo)
        except ValueError:
            warnings.append(
                "docs-gate: path not under repo for %r — advisory" % rel)
            continue
        try:
            r = subprocess.run(
                ["git", "-C", str(repo), "log", "--since", stage5_ts,
                 "--oneline", "--", rel_in_repo],
                capture_output=True, text=True, timeout=20,
            )
            if r.returncode != 0 or not r.stdout.strip():
                blocks.append(
                    "declared path unmodified since stage 5 (%s): %s" % (
                        stage5_ts, rel))
        except (OSError, subprocess.TimeoutExpired) as e:
            warnings.append(
                "docs-gate: git log failed for %r: %s" % (rel, e))
    return blocks, warnings


# ── self-heal: rollup-vs-rendered-block compare ────────────────────────────────

def _read_sentinel_block(file_path):
    """Extract the text between ``RUNBOOK:PROGRESS:START`` and ``END -->`` markers.

    Returns ``(block_text, found_both)`` — ``block_text`` is the extracted text
    (or ``""`` if markers not found), ``found_both`` is True when both markers
    are present (so the block exists and is replaceable)."""
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        return "", False

    start_marker = "<!-- RUNBOOK:PROGRESS:START"
    end_marker = "<!-- RUNBOOK:PROGRESS:END -->"

    si = text.find(start_marker)
    if si < 0:
        return "", False
    si_nl = text.find("\n", si)
    if si_nl < 0:
        return "", False

    ei = text.find(end_marker, si_nl)
    if ei < 0:
        return text[si_nl + 1:], False

    return text[si_nl + 1:ei], True


def _self_heal_runbooks(conn, root, already_rebuilt):
    """Find runbooks whose rendered block differs from the current rollup.

    For each runbook NOT in ``already_rebuilt``: compute the rollup + block,
    compare against the on-disk sentinel block. Returns the additional
    runbook paths that need re-rendering."""
    extra = set()
    all_rbs = conn.execute(
        "SELECT path FROM files WHERE kind='runbook'").fetchall()
    for (rb_rel,) in all_rbs:
        if rb_rel in already_rebuilt:
            continue
        rb_abs = os.path.join(root, rb_rel)
        if not os.path.isfile(rb_abs):
            continue

        rollup_data = runbook.compute_rollup(conn, rb_rel)
        if rollup_data is None:
            rollup_data = derive.rollup([])
        member_rows = runbook._member_rows(conn, root, rb_rel)
        block_new = runbook.compose_block(rb_rel, rollup_data, member_rows)

        block_old, has_both = _read_sentinel_block(rb_abs)
        if not has_both or block_new.rstrip() != block_old.rstrip():
            extra.add(rb_rel)
    return extra


# ── the verb ───────────────────────────────────────────────────────────────────

def cmd_reconcile(args):
    """``planctl reconcile [--json]`` — the Stop-hook composition."""
    t0 = time.monotonic()
    root = statedir.project_root()
    conn = db.open_db()
    json_out = getattr(args, "json", False)

    try:
        # ── 1. Fast-path freshness (ensure_fresh-style, NO porcelain scan) ─
        head_sha = sync._head_sha(root)
        if db.is_stale(conn, derive.DERIVE_V) or sync._needs_full(conn, root):
            sync._drop_derived_rows(conn)
            paths = sync._walk_indexed(root)
            synced_paths, rebuilt_runbooks = sync._reindex_paths(
                conn, root, paths, full=True, head_sha=head_sha)
        else:
            wm_row = conn.execute(
                "SELECT value FROM meta WHERE key='last_commit'").fetchone()
            wm = wm_row[0] if wm_row else None
            if head_sha is None:
                synced_paths, rebuilt_runbooks = [], set()
            elif head_sha == wm:
                synced_paths, rebuilt_runbooks = [], set()
            elif wm and sync._cat_file_exists(root, wm):
                cands = sync._diff_paths(root, wm)
                synced_paths, rebuilt_runbooks = sync._reindex_paths(
                    conn, root, cands, full=False, head_sha=head_sha)
            else:
                sync._drop_derived_rows(conn)
                synced_paths, rebuilt_runbooks = sync._reindex_paths(
                    conn, root, sync._walk_indexed(root), full=True,
                    head_sha=head_sha)

        # ── 2. Pre-build caches (read logs ONCE, not per-plan) ──────────────
        review_cache = _build_review_cache()
        stage5_ts_cache = _build_stage5_ts_cache()

        # ── 3. DONE-gate decision matrix ────────────────────────────────────
        decisions = []
        scopes = _build_scope_set(conn, root)

        for scope_path, plan_rel in scopes:
            # Count open execution checkboxes across the scope
            if os.path.isdir(os.path.join(root, scope_path)):
                scope_prefix = scope_path + "/" if scope_path != "." else ""
                rows = conn.execute(
                    "SELECT COUNT(*) FROM tasks t "
                    "JOIN plans p ON t.plan_path = p.path "
                    "WHERE p.path LIKE ? ESCAPE '\\' AND t.checked=0 AND t.human_verify=0",
                    (_like_prefix(scope_prefix) + "%",)).fetchone()
                open_exec = rows[0] if rows else 0
                total_rows = conn.execute(
                    "SELECT COUNT(*) FROM tasks t "
                    "JOIN plans p ON t.plan_path = p.path "
                    "WHERE p.path LIKE ? ESCAPE '\\' AND t.human_verify=0",
                    (_like_prefix(scope_prefix) + "%",)).fetchone()
                total_tasks = total_rows[0] if total_rows else 0
            else:
                rows = conn.execute(
                    "SELECT COUNT(*) FROM tasks "
                    "WHERE plan_path=? AND checked=0 AND human_verify=0",
                    (scope_path,)).fetchone()
                open_exec = rows[0] if rows else 0
                total_rows = conn.execute(
                    "SELECT COUNT(*) FROM tasks "
                    "WHERE plan_path=? AND human_verify=0",
                    (scope_path,)).fetchone()
                total_tasks = total_rows[0] if total_rows else 0

            if total_tasks == 0:
                continue  # not a real execution plan

            review_pass = _lookup_review_verdict(
                review_cache, plan_rel) == "pass"

            # ── Decision matrix (5 outcomes) ────────────────────────────
            if open_exec == 0 and review_pass:
                # (A) clean + reviewed → stamp stage 6
                stage5_ts = _lookup_stage5_ts(stage5_ts_cache, plan_rel)
                blocks, warns = _docs_evidence_gate(
                    conn, root, plan_rel, stage5_ts)

                if blocks:
                    # (B) docs declared but evidence missing
                    events.append({
                        "event": "done_gate",
                        "plan": plan_rel,
                        "data": {"result": "docs_missing",
                                 "blocks": blocks},
                    })
                    decisions.append({
                        "plan": plan_rel,
                        "decision": "docs_missing",
                    })
                    for w in warns:
                        print(w, file=sys.stderr)
                    continue

                if warns:
                    for w in warns:
                        print(w, file=sys.stderr)

                # Stamp stage 6 (stdout silenced in --json mode so the payload
                # stays parseable — cmd_stage prints a human line).
                from types import SimpleNamespace as _SN2
                from planctl import stage as _stage
                try:
                    with _quiet_stdout(json_out):
                        _stage.cmd_stage(_SN2(
                            plan=plan_rel, stage="6", status="completed",
                            json=False))
                except SystemExit:
                    pass

                # Find owning runbook
                owner_rb = None
                rb_rows = conn.execute(
                    "SELECT parent FROM membership WHERE child=? LIMIT 1",
                    (plan_rel,)).fetchone()
                if rb_rows:
                    owner_rb = rb_rows[0]

                events.append({
                    "event": "done_gate",
                    "plan": plan_rel,
                    "data": {"result": "done"},
                })
                decisions.append({
                    "plan": plan_rel,
                    "decision": "done",
                    "runbook": owner_rb,
                })

            elif open_exec == 0 and not review_pass:
                # (C) clean + no review → review_missing
                events.append({
                    "event": "done_gate",
                    "plan": plan_rel,
                    "data": {"result": "review_missing"},
                })
                decisions.append({
                    "plan": plan_rel,
                    "decision": "review_missing",
                })

            elif open_exec > 0:
                prow = conn.execute(
                    "SELECT derived_status, drift FROM plans WHERE path=?",
                    (plan_rel,)).fetchone()
                dstatus = prow[0] if prow else None
                drift = bool(prow[1]) if prow else False

                # The claimed-done-but-lied case (the bug this gate exists to
                # catch) is frontmatter ``status: completed`` WITH open exec
                # boxes at stage 5. It CANNOT be expressed via derived_status/
                # drift: derive.derive_plan only yields 'done'/drift at
                # stage>=6, and the scope set selects stage==5 EXACTLY (W1-D2)
                # — so both predicates above are unreachable here and (D) would
                # silently degrade to (E) no-op. The legacy status is not
                # indexed (I1: never stored as derived), so read it from the
                # frontmatter, as parse.parse_frontmatter explicitly exposes it.
                claimed_done = False
                try:
                    with open(os.path.join(root, plan_rel),
                              encoding="utf-8", errors="ignore") as fh:
                        _fm, raw_status = parse.parse_frontmatter(fh.read())
                    claimed_done = str(raw_status or "").strip().lower() in (
                        "completed", "complete", "done")
                except OSError:
                    claimed_done = False

                if dstatus == "done" or drift or claimed_done:
                    # (D) open boxes + derived-done → FAIL LOUD
                    events.append({
                        "event": "done_gate",
                        "plan": plan_rel,
                        "data": {"result": "fail_open_boxes",
                                 "open_exec": open_exec},
                    })
                    decisions.append({
                        "plan": plan_rel,
                        "decision": "fail_open_boxes",
                        "open_exec": open_exec,
                    })
                else:
                    # (E) open boxes + executing/blocked → no-op
                    decisions.append({
                        "plan": plan_rel,
                        "decision": "noop",
                        "open_exec": open_exec,
                    })

        # ── 4. Render only DIRTY runbooks ───────────────────────────────────
        dirty = set(rebuilt_runbooks)
        extra = _self_heal_runbooks(conn, root, dirty)
        dirty |= extra

        rendered = []
        from types import SimpleNamespace as _SN
        for rb_rel in sorted(dirty):
            rb_abs = os.path.join(root, rb_rel)
            if os.path.isfile(rb_abs):
                try:
                    # Silence render output in JSON mode (stdout is for the
                    # reconcile payload only). The context manager restores
                    # stdout even if the render raises — the hand-rolled
                    # save/restore leaked a swapped stdout on some paths.
                    with _quiet_stdout(json_out):
                        rc = runbook.cmd_runbook_render(_SN(
                            rb=rb_rel, json=False))
                    if rc == 0:
                        rendered.append(rb_rel)
                except Exception as e:
                    print("reconcile: render failed for %s: %s" % (rb_rel, e),
                          file=sys.stderr)

        elapsed_ms = int((time.monotonic() - t0) * 1000)

        if json_out:
            print(json.dumps({
                "synced": sorted(synced_paths),
                "decisions": decisions,
                "rendered": rendered,
                "elapsed_ms": elapsed_ms,
            }))
        else:
            print("planctl reconcile: %d synced, %d decision(s), "
                  "%d runbook(s) rendered (%dms)" % (
                      len(synced_paths), len(decisions), len(rendered),
                      elapsed_ms))
            if decisions:
                for d in decisions:
                    extra_info = ""
                    if d["decision"] == "done" and d.get("runbook"):
                        extra_info = " (runbook: %s)" % d["runbook"]
                    elif d["decision"] == "noop":
                        extra_info = " (%d open)" % d.get("open_exec", 0)
                    elif d["decision"] == "fail_open_boxes":
                        extra_info = " (%d open)" % d.get("open_exec", 0)
                    print("  %s → %s%s" % (d["plan"], d["decision"], extra_info))
            if rendered:
                print("  rendered: " + ", ".join(rendered))

        return 0
    except Exception as e:
        # Non-zero so the Stop hook surfaces its one-line warning (Codex #12),
        # but --json must STILL be parseable on the failure path.
        if json_out:
            print(json.dumps({
                "synced": [], "decisions": [], "rendered": [],
                "elapsed_ms": int((time.monotonic() - t0) * 1000),
                "error": "%s: %s" % (type(e).__name__, e),
            }))
        print("planctl reconcile: %s: %s" % (type(e).__name__, e),
              file=sys.stderr)
        return 1
    finally:
        conn.close()
