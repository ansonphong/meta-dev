#!/usr/bin/env python3
"""Parity harness — planctl RAW counts == the frozen plan-index.py oracle
(design §7 M0 gate; R9/V1/S4).

Proves the new ``planctl`` index agrees with the OLD scanner on the LIVE tree.
Run manually + by the phase-0e / M0 / 4.3 Acceptance Gates:

    META_DEV_STATE_DIR=/tmp/parity python3 plugins/meta-dev/tests/planctl/parity_vs_plan_index.py

  * The ORACLE is a FROZEN copy of ``plan-index.py``
    (``tests/planctl/oracle_plan_index.py`` — committed at M0, never edited).
    The harness imports the ORACLE via ``importlib``, NEVER the live
    ``plan-index.py`` (which becomes a shim in M2a — comparing planctl to itself
    would be vacuous). R9/V1/S4.
  * Parity set (R7/BC7 + R2/W2E-2): ``planctl sync --full`` vs the oracle over
    the oracle's TRACKED non-archived set (the ``## Sequence`` set, falling back
    to ``walk_candidates`` pre-migration). RAW checkbox ``done``/``total`` (ALL
    boxes, human INCLUDED) per plan, plus ``stage``/``repo``. Archived plans are
    EXCLUDED from both sides.
  * ``resolve_repo_root`` (G-IMP8): the project root is resolved via
    ``lib/repo-topology.py`` / ``statedir.project_root()`` — NEVER
    ``git rev-parse --show-toplevel`` (BANNED — returns whichever repo the
    ambient cwd sits in).

Prints ``PARITY OK (N plans)`` on agreement, else lists per-plan mismatches and
exits 1. Not a pytest unit test — a runnable script (design §7 M0).
"""
import importlib.util
import json
import os
import pathlib
import sys
import tempfile

_HERE = pathlib.Path(__file__).resolve().parent
_PLUGIN = _HERE.parent.parent                  # plugins/meta-dev/
_SCRIPTS = _PLUGIN / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

# Hermeticity: a throwaway state dir if the caller didn't pin one (never pollute
# the real ~/.cache/meta-dev). META_DEV_ROOT is deliberately LEFT UNSET so the
# topology resolves the real host root.
if not os.environ.get("META_DEV_STATE_DIR"):
    os.environ["META_DEV_STATE_DIR"] = tempfile.mkdtemp(prefix="planctl-parity-")


def _load_oracle():
    """Importlib-load the FROZEN oracle (NOT the live plan-index.py)."""
    p = _HERE / "oracle_plan_index.py"
    spec = importlib.util.spec_from_file_location("oracle_plan_index", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _norm_stage(v):
    if v is None:
        return 0
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return 0


def _norm_repo(v):
    return str(v or "").strip()


def main():
    from planctl import statedir, sync, db
    from types import SimpleNamespace

    # Resolve the project root via topology (cwd-independent — G-IMP8). NEVER
    # `git rev-parse --show-toplevel`.
    root = statedir.project_root()
    os.chdir(root)                              # oracle reads plans/… relatively

    # planctl side: a fresh --full sync into the hermetic state dir.
    rc = sync.cmd_sync(SimpleNamespace(full=True, file=None, json=False))
    if rc != 0:
        print("PARITY FAIL: planctl sync --full returned %s" % rc)
        return 1

    oracle = _load_oracle()
    order, _milestones, _trailing = oracle.parse_runbook_sequence()
    if not order:                               # pre-migration fallback
        order = oracle.walk_candidates()
    # Archived plans are EXCLUDED from both sides (R7/W2E-2).
    parity_set = [p for p in order if "/_archive/" not in p]

    conn = db.open_db()
    try:
        mismatches = []
        compared = 0
        for rel in parity_set:
            info = oracle.read_plan_file(rel)
            if not info.get("ok_read"):
                continue                        # unreadable on either side
            prog = info.get("progress", {})
            o_done, o_total = prog.get("done", 0), prog.get("total", 0)
            fm = info.get("fm", {}) or {}
            o_stage = _norm_stage(fm.get("stage", ""))
            o_repo = _norm_repo(fm.get("repo", ""))

            row = conn.execute(
                "SELECT raw_done, raw_total, stage, repo FROM plans "
                "WHERE path=?", (rel,)).fetchone()
            if row is None:
                mismatches.append({
                    "path": rel, "reason": "not indexed by planctl",
                    "oracle": {"done": o_done, "total": o_total,
                               "stage": o_stage, "repo": o_repo}})
                continue
            p_done, p_total, p_stage, p_repo = row
            diffs = {}
            if int(p_done or 0) != int(o_done):
                diffs["done"] = {"planctl": int(p_done or 0), "oracle": o_done}
            if int(p_total or 0) != int(o_total):
                diffs["total"] = {"planctl": int(p_total or 0), "oracle": o_total}
            if _norm_stage(p_stage) != o_stage:
                diffs["stage"] = {"planctl": _norm_stage(p_stage), "oracle": o_stage}
            if _norm_repo(p_repo) != o_repo:
                diffs["repo"] = {"planctl": _norm_repo(p_repo), "oracle": o_repo}
            if diffs:
                mismatches.append({"path": rel, "diffs": diffs})
            compared += 1
    finally:
        conn.close()

    if mismatches:
        print("PARITY FAIL (%d mismatch(es) of %d compared):" % (
            len(mismatches), compared))
        for m in mismatches:
            print("  %s" % m["path"])
            if "diffs" in m:
                for k, v in m["diffs"].items():
                    print("      %-6s planctl=%s  oracle=%s" % (
                        k, v["planctl"], v["oracle"]))
            else:
                print("      %s" % m.get("reason"))
        return 1
    print("PARITY OK (%d plans)" % compared)
    return 0


if __name__ == "__main__":
    sys.exit(main())
