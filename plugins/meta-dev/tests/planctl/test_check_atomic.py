#!/usr/bin/env python3
"""Atomicity test — concurrent ``planctl check`` on ONE file loses no flips
(design §10 item 3; critical test 3/4).

The corruption guard for the 20-agent tree. On a fixture plan with N tagged
boxes, spawn K concurrent ``planctl check`` PROCESSES (real subprocesses — to
exercise the real ``flock`` sidecar + ``O_APPEND`` event writes, not in-process
locks), each flipping a distinct box, and a few flipping the SAME box (to stress
the per-plan flock). Assert:

  * every intended flip lands EXACTLY ONCE (none lost to a lost-update race,
    none duplicated);
  * the file is NEVER left half-written (re-parse always succeeds + the beads
    survive verbatim);
  * the final ``tasks_done`` == the expected count;
  * every event ``check`` line is single-line ≤4KB (W2D-5).

If the ``mutation_lock`` flock were broken, two processes would read the same
pre-flip content and clobber each other → ``tasks_done`` would fall short of the
expected count, and this test would fail loud.

Hermetic: the conftest pins ``META_DEV_STATE_DIR`` + ``META_DEV_ROOT`` to a tmp
dir; subprocesses inherit them (``os.environ``), so NO write touches the real
``~/.cache/meta-dev`` or the live tree.
"""
import json
import os
import pathlib
import subprocess
import sys

import pytest  # noqa: E402  (conftest puts scripts/ on sys.path)

from planctl import events, parse  # noqa: E402

# scripts/ is three parents up from this file (planctl/ -> tests/ -> .../scripts).
_SCRIPTS = str(pathlib.Path(__file__).resolve().parent.parent.parent / "scripts")
_TIDS = ["#aaa%d" % i for i in range(10)]  # 10 distinct, valid 4-hex beads


def _root():
    return os.environ["META_DEV_ROOT"]


def _write_plan(root, rel, boxes_checked=()):
    """A plan with 10 tagged boxes; ``boxes_checked`` is the set already [x]."""
    body = ["---", "stage: 5", "repo: meta", "---", "# Fixture", "", "## Build", ""]
    for i, tid in enumerate(_TIDS):
        mark = "x" if i in boxes_checked else " "
        body.append("- [%s] %s box %d" % (mark, tid, i))
    body.append("")
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(body))
    return rel


def _planctl(*cli_args, timeout=120):
    """Invoke ``python3 -m planctl`` in a SUBPROCESS (inherits the hermetic env)."""
    env = dict(os.environ, PYTHONPATH=_SCRIPTS)
    return subprocess.run(
        [sys.executable, "-m", "planctl", *cli_args],
        env=env, cwd=_root(), capture_output=True, text=True, timeout=timeout)


# ── a single-process flip is correct first (sanity + idempotency) ─────────────
def test_single_check_flips_exactly_one_box(tmp_path):
    root = _root()
    rel = _write_plan(root, "plans/meta/atomic-single.md")
    r = _planctl("check", rel, "#aaa3", "--json")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out == {"flipped": ["#aaa3"], "skipped": [], "verified": True}, out
    # the box is now [x]; re-checking is a no-op (not an error)
    text = open(os.path.join(root, rel), encoding="utf-8").read()
    assert "- [x] #aaa3 box 3" in text
    r2 = _planctl("check", rel, "#aaa3", "--json")
    assert r2.returncode == 0, r2.stderr
    assert json.loads(r2.stdout)["flipped"] == []  # already [x] → no-op


# ── --verify gate: non-zero aborts ALL flips, no event, nonzero exit ──────────
def test_verify_failure_aborts_all_flips(tmp_path):
    root = _root()
    rel = _write_plan(root, "plans/meta/atomic-verify.md")
    before = open(os.path.join(root, rel), encoding="utf-8").read()
    r = _planctl("check", rel, "#aaa0", "#aaa1", "--verify", "false", "--json")
    assert r.returncode == 1, r.stderr
    out = json.loads(r.stdout)
    assert out["flipped"] == [] and out["verified"] is False
    # nothing flipped + no event emitted
    assert open(os.path.join(root, rel), encoding="utf-8").read() == before
    assert events.query(event="check") == []


# ── multi-tid: one bad tid is skipped, good tids STILL land ───────────────────
def test_multi_tid_partial_failure_lands_good_ones(tmp_path):
    root = _root()
    rel = _write_plan(root, "plans/meta/atomic-partial.md")
    r = _planctl("check", rel, "#aaa0", "#zzzz", "#aaa1", "--json")
    assert r.returncode == 1, r.stderr  # nonzero — one tid unresolved
    out = json.loads(r.stdout)
    assert out["flipped"] == ["#aaa0", "#aaa1"]          # good tids landed
    assert out["skipped"] == [{"tid": "#zzzz", "reason": "unresolved"}]
    text = open(os.path.join(root, rel), encoding="utf-8").read()
    assert "- [x] #aaa0 box 0" in text
    assert "- [x] #aaa1 box 1" in text


# ── the corruption guard: K concurrent flippers lose no flips ─────────────────
@pytest.mark.parametrize("concurrency", [8])
def test_concurrent_check_loses_no_flips(concurrency):
    """K processes flip K distinct boxes (a few double up on box 0 for flock
    contention). Every distinct target must land exactly once."""
    root = _root()
    rel = _write_plan(root, "plans/meta/atomic-concurrent.md")
    # 8 distinct targets (boxes 0-7); 2 extra processes also hit box 0.
    targets = ["#aaa%d" % i for i in range(concurrency)] + ["#aaa0", "#aaa0"]

    # Build ALL Popen objects first — they start immediately and overlap.
    # Run several rounds so contention is actually exercised.
    ev_path = events.statedir.events_path()
    rcs = []
    for _round in range(3):
        _write_plan(root, rel)  # reset fixture each round
        open(ev_path, "w").close()  # clear event log between rounds
        pops = []
        for t in targets:
            env = dict(os.environ, PYTHONPATH=_SCRIPTS)
            pops.append(subprocess.Popen(
                [sys.executable, "-m", "planctl", "check", rel, t],
                env=env, cwd=root,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        for p in pops:
            p.wait(timeout=120)
            rcs.append(p.returncode)

    # the file must re-parse cleanly (never half-written) + beads survive.
    text = open(os.path.join(root, rel), encoding="utf-8").read()
    tasks, perr = parse.parse_tasks(text)
    assert perr is None, "re-parse errored (corruption?): %s" % perr
    assert len(tasks) == 10

    checked = {t.tid for t in tasks if t.checked}
    # every distinct target landed exactly once; box 0 is checked (once), not dup.
    expected = {"#aaa%d" % i for i in range(concurrency)}
    assert checked == expected, "lost/duplicated flips: got %s" % sorted(checked)
    # tasks_done == the 8 distinct boxes (the 2 extra no-op'd on box 0).
    assert sum(1 for t in tasks if t.checked) == concurrency

    # every process exited 0 (distinct flips land; double-ups no-op, not errors).
    assert all(rc == 0 for rc in rcs), "a flipper failed: %s" % rcs

    # event log: exactly `concurrency` check events, one per distinct flip, each
    # single-line ≤4KB (W2D-5). (Double-ups on box 0 emitted no event — no flip.)
    evs = events.query(event="check")
    assert len(evs) == concurrency, evs
    ev_path = events.statedir.events_path()
    for line in open(ev_path, encoding="utf-8"):
        line = line.rstrip("\n")
        assert len(line.encode("utf-8")) <= 4000, "event line > 4KB (W2D-5)"
        json.loads(line)  # every line valid single-line JSON
    ev_tids = sorted(e["data"]["tid"] for e in evs if "data" in e)
    assert ev_tids == sorted(expected)


# ── check↔uncheck round-trip is stable under the same lock ────────────────────
def test_check_then_uncheck_roundtrip(tmp_path):
    root = _root()
    rel = _write_plan(root, "plans/meta/atomic-roundtrip.md")
    _planctl("check", rel, "#aaa2", "#aaa5")
    text = open(os.path.join(root, rel), encoding="utf-8").read()
    assert "- [x] #aaa2 box 2" in text and "- [x] #aaa5 box 5" in text
    r = _planctl("uncheck", rel, "#aaa2", "--json")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["flipped"] == ["#aaa2"]
    text = open(os.path.join(root, rel), encoding="utf-8").read()
    assert "- [ ] #aaa2 box 2" in text   # unchecked
    assert "- [x] #aaa5 box 5" in text   # untouched
