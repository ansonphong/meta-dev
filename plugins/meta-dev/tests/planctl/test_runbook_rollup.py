#!/usr/bin/env python3
"""Nested-rollup + cycle test — design §10 item 4 (critical test 4/4).

Locks the recursive runbook rollup semantics (design §3.2/§4) + the cycle guard
(W2E-1..W2E-8) that the 0c read-time walker could not express:

  * nested runbook rollup — exact members_done/total + tasks_done/total +
    effective_stage + now, with ``now`` DESCENDING into a nested runbook to its
    leaf when the earlier member is done (W2E-7);
  * depth-2 nesting (R3 -> R1 -> [P1, R2 -> [P2, P3]]);
  * DISTINCT diamond-dedup — a leaf reached two ways counts ONCE in
    tasks_done/total (W2E-5);
  * blocked member EXCLUDED from effective_stage min (doesn't drag it, W2E-6);
  * empty runbook -> 0/0 -> renders ``"-"`` (never 100%, W2E-8);
  * render writes the RUNBOOK:PROGRESS sentinel block, idempotent (R6), and
    renders a MISSING member loud (§4);
  * ``runbook add`` cycle-refused at the door (I7), happy path populates
    membership;
  * a FILE-EDITED cycle (bypassing the door) — sync TERMINATES (timeout assert,
    no hang), BOTH endpoints land ``parse_err``, and ``doctor`` lists them
    (W2E-3/W2-T4 — refusal-only is insufficient).

Hermetic: conftest pins ``META_DEV_STATE_DIR`` + ``META_DEV_ROOT`` to a tmp dir;
subprocesses inherit them so NO write touches the real ``~/.cache/meta-dev`` or
the live tree.
"""
import json
import os
import pathlib
import subprocess
import sys
from types import SimpleNamespace

import pytest  # noqa: E402  (conftest puts scripts/ on sys.path)

from planctl import db, derive, runbook, sync  # noqa: E402

# scripts/ is three parents up from this file (planctl/ -> tests/ -> .../scripts).
_SCRIPTS = str(pathlib.Path(__file__).resolve().parent.parent.parent / "scripts")

# ── fixture plan/runbook paths (under the conftest tmp META_DEV_ROOT) ─────────
P1 = "plans/meta/2026-01-01-p1.md"     # done (stage 6, 2/2)
P2 = "plans/meta/2026-01-02-p2.md"     # executing (stage 5, 1/2)
P3 = "plans/meta/2026-01-03-p3.md"     # ready (stage 5, 0/1)
P4 = "plans/meta/2026-01-04-p4.md"     # blocked (stage 3, override blocked)
PNEW = "plans/meta/2026-01-09-pnew.md"
R1 = "plans/meta/_runbook-r1.md"       # [P1, R2]
R2 = "plans/meta/_runbook-r2.md"       # [P2, P3]
R3 = "plans/meta/_runbook-r3.md"       # [R1]            (depth-2)
RD = "plans/meta/_runbook-rd.md"       # [P1, RD2]       (diamond)
RD2 = "plans/meta/_runbook-rd2.md"     # [P1, P2]
REMPTY = "plans/meta/_runbook-rempty.md"   # [] (empty)
RBLOCK = "plans/meta/_runbook-rblock.md"   # [P4, P2]      (blocked member)
RMISS = "plans/meta/_runbook-rmiss.md"     # [missing-plan]


# ── helpers ───────────────────────────────────────────────────────────────────
def _root():
    return os.environ["META_DEV_ROOT"]


def _git(root, *args):
    return subprocess.run(["git", "-C", root, *args],
                          capture_output=True, text=True)


def _commit(root, msg):
    _git(root, "add", "-A")
    r = _git(root, "commit", "-qm", msg)
    assert r.returncode == 0, "git commit failed: %s" % r.stderr


def _git_init(root):
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "commit.gpgsign", "false")


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _runbook(rel, members):
    """A runbook frontmatter + body with the given ordered members (or [] empty)."""
    if members:
        block = "members:\n" + "".join("  - %s\n" % m for m in members)
    else:
        block = "members: []\n"
    return "---\ntype: runbook\nrepo: meta\n%s---\n# Runbook %s\n" % (
        block, rel.rsplit("/", 1)[-1])


def run_sync(full=False):
    args = SimpleNamespace(full=full, file=None, json=False)
    rc = sync.cmd_sync(args)
    assert rc == 0, "sync returned %s" % rc


def _planctl(*cli_args, timeout=30):
    """Invoke ``python3 -m planctl`` in a SUBPROCESS (inherits hermetic env)."""
    env = dict(os.environ, PYTHONPATH=_SCRIPTS)
    return subprocess.run(
        [sys.executable, "-m", "planctl", *cli_args],
        env=env, cwd=_root(), capture_output=True, text=True, timeout=timeout)


def _build_tree(root):
    _write(root, P1, "---\nstage: 6\nrepo: meta\n---\n# P1\n"
                    "- [x] a #0001\n- [x] b #0002\n")          # done, 2/2
    _write(root, P2, "---\nstage: 5\nrepo: meta\n---\n# P2\n"
                    "- [x] a #0003\n- [ ] b #0004\n")           # executing, 1/2
    _write(root, P3, "---\nstage: 5\nrepo: meta\n---\n# P3\n"
                    "- [ ] a #0005\n")                          # ready, 0/1
    _write(root, P4, "---\nstage: 3\nrepo: meta\noverride: blocked\n---\n# P4\n"
                    "- [ ] a #0006\n")                          # blocked, 0/1
    _write(root, R1, _runbook(R1, [P1, R2]))
    _write(root, R2, _runbook(R2, [P2, P3]))
    _write(root, R3, _runbook(R3, [R1]))
    _write(root, RD, _runbook(RD, [P1, RD2]))
    _write(root, RD2, _runbook(RD2, [P1, P2]))
    _write(root, REMPTY, _runbook(REMPTY, []))
    _write(root, RBLOCK, _runbook(RBLOCK, [P4, P2]))
    _write(root, RMISS, _runbook(RMISS, ["plans/meta/does-not-exist.md"]))


@pytest.fixture
def tree():
    """A committed, full-synced base tree; returns the fixture root path."""
    root = _root()
    _build_tree(root)
    _git_init(root)
    _commit(root, "init")
    run_sync(full=True)
    return root


# ── nested rollup: exact counts + descending now (W2E-7) ───────────────────────
def test_nested_rollup_exact(tree):
    conn = db.open_db()
    try:
        r2 = runbook.compute_rollup(conn, R2)
        assert r2 is not None
        assert (r2["members_done"], r2["members_total"]) == (0, 2)
        assert (r2["tasks_done"], r2["tasks_total"]) == (1, 3)   # P2 1/2 + P3 0/1
        assert r2["effective_stage"] == 5                        # min(5,5)
        assert r2["now"] == P2                                   # first open member

        r1 = runbook.compute_rollup(conn, R1)
        # P1 done + R2 not done -> 1/2 members; P1 2/2 + P2 1/2 + P3 0/1 = 3/5
        assert (r1["members_done"], r1["members_total"]) == (1, 2)
        assert (r1["tasks_done"], r1["tasks_total"]) == (3, 5)
        assert r1["effective_stage"] == 5                        # P1 done excluded
        # now DESCENDS into R2 (P1 done) to its leaf P2 (W2E-7)
        assert r1["now"] == P2
    finally:
        conn.close()


# ── depth-2 nesting: R3 -> R1 -> [P1, R2 -> [P2, P3]] ──────────────────────────
def test_depth2_rollup_descends_to_leaf(tree):
    conn = db.open_db()
    try:
        r3 = runbook.compute_rollup(conn, R3)
        assert (r3["members_done"], r3["members_total"]) == (0, 1)
        assert (r3["tasks_done"], r3["tasks_total"]) == (3, 5)   # same leaf set
        assert r3["effective_stage"] == 5
        # now descends R3 -> R1 -> R2 -> P2 (the deepest open leaf)
        assert r3["now"] == P2
    finally:
        conn.close()


# ── diamond dedup: P1 reached two ways counts ONCE (W2E-5) ─────────────────────
def test_diamond_dedup_counts_leaf_once(tree):
    conn = db.open_db()
    try:
        rd = runbook.compute_rollup(conn, RD)       # [P1, RD2=[P1, P2]]
        # distinct leaves {P1, P2} -> 2/2 + 1/2 = 3/4 (P1 counted ONCE)
        assert (rd["tasks_done"], rd["tasks_total"]) == (3, 4)
    finally:
        conn.close()


# ── blocked member EXCLUDED from effective_stage min (W2E-6) ───────────────────
def test_blocked_member_excluded_from_effective_stage(tree):
    conn = db.open_db()
    try:
        rb = runbook.compute_rollup(conn, RBLOCK)   # [P4 blocked stage3, P2 stage5]
        # P4 overridden -> excluded; effective_stage = P2's 5 (NOT dragged to 3)
        assert rb["effective_stage"] == 5
        assert rb["now"] == P2                       # P4 overridden -> skipped
    finally:
        conn.close()


# ── empty runbook: 0/0 -> renders "—" (never 100%, W2E-8) ──────────────────────
def test_empty_runbook_renders_dash(tree, capsys):
    conn = db.open_db()
    try:
        re_ = runbook.compute_rollup(conn, REMPTY)
        assert re_ is not None
        assert re_["members_total"] == 0
        assert (re_["tasks_done"], re_["tasks_total"]) == (0, 0)
        assert re_["status"] is None                  # not 100% done
    finally:
        conn.close()
    # render emits the "—" progress marker for an empty runbook
    capsys.readouterr()
    assert runbook.cmd_runbook_render(SimpleNamespace(rb=REMPTY, json=False)) == 0
    text = open(os.path.join(_root(), REMPTY), encoding="utf-8").read()
    assert "<!-- RUNBOOK:PROGRESS:START" in text
    assert "0/0" in text and "—" in text


# ── render writes the sentinel block; idempotent (R6); MISSING loud (§4) ───────
def test_render_writes_block_and_is_idempotent(tree, capsys):
    assert runbook.cmd_runbook_render(SimpleNamespace(rb=R1, json=False)) == 0
    text = open(os.path.join(_root(), R1), encoding="utf-8").read()
    assert "<!-- RUNBOOK:PROGRESS:START -->" in text
    assert "<!-- RUNBOOK:PROGRESS:END -->" in text
    assert "Members done:" in text and "| # | Plan |" in text
    # re-render is a true no-op on disk (idempotent content-compare, R6)
    capsys.readouterr()
    assert runbook.cmd_runbook_render(SimpleNamespace(rb=R1, json=False)) == 0
    assert "unchanged" in capsys.readouterr().out


def test_render_missing_member_is_loud(tree):
    assert runbook.cmd_runbook_render(SimpleNamespace(rb=RMISS, json=False)) == 0
    text = open(os.path.join(_root(), RMISS), encoding="utf-8").read()
    # Rendered-markdown surfaces use the emoji vocabulary (derive.EMOJI_MISSING);
    # the ✗ glyph remains the terminal/box spelling. "Loud" is the contract —
    # assert the marker AND the offending path, in both the name and status cells.
    assert "%s MISSING" % derive.EMOJI_MISSING in text
    assert "does-not-exist.md" in text


# ── runbook add: happy path populates membership; cycle refused at door (I7) ───
def test_runbook_add_happy_path_populates_membership(tree, capsys):
    root = _root()
    _write(root, PNEW, "---\nstage: 3\nrepo: meta\n---\n# Pnew\n- [ ] x #0007\n")
    capsys.readouterr()
    rc = runbook.cmd_runbook_add(SimpleNamespace(rb=R1, member=PNEW, json=True))
    assert rc == 0, capsys.readouterr()
    out = json.loads(capsys.readouterr().out)
    assert out["added"] is True
    # the member was appended to the runbook's frontmatter members: list
    assert PNEW in open(os.path.join(root, R1), encoding="utf-8").read()
    # membership now includes PNEW under R1 (sync_one repopulated it)
    conn = db.open_db()
    try:
        children = {r[0] for r in conn.execute(
            "SELECT child FROM membership WHERE parent=?", (R1,))}
    finally:
        conn.close()
    assert PNEW in children


def test_runbook_add_refuses_cycle_at_door(tree, capsys):
    root = _root()
    # R1 -> R2 already; adding R1 UNDER R2 would close R2 -> R1 -> R2 (cycle)
    capsys.readouterr()
    rc = runbook.cmd_runbook_add(SimpleNamespace(rb=R2, member=R1, json=False))
    assert rc != 0                                      # refused, non-zero
    err = capsys.readouterr().err
    assert "REFUSED" in err and "cycle" in err
    # NO write: R2 still has only [P2, P3] (no R1)
    assert R1 not in open(os.path.join(root, R2), encoding="utf-8").read()


# ── file-edited cycle: sync terminates + parse_err + doctor lists (W2E-3/W2-T4) ─
def test_file_edited_cycle_terminates_and_marks_parse_err(tree):
    root = _root()
    r2_path = os.path.join(root, R2)
    # hand-Edit R2.members += [R1]  (bypasses the door)  -> R1 <-> R2 cycle
    text = open(r2_path, encoding="utf-8").read()
    text = text.replace("  - %s\n" % P3, "  - %s\n  - %s\n" % (P3, R1))
    assert R1 in text
    open(r2_path, "w", encoding="utf-8").write(text)
    _commit(root, "hand-edited cycle R2 += R1")

    # sync via SUBPROCESS with a hard timeout — a cyclic graph must TERMINATE
    # (no hang). If the path-guarded CTE / visited-set walker regressed, this
    # raises subprocess.TimeoutExpired and fails the test loud.
    r = _planctl("sync", "--full", timeout=30)
    assert r.returncode == 0, r.stderr

    # BOTH endpoints land parse_err (refusal-only at the door is insufficient)
    conn = db.open_db()
    try:
        rows = dict(conn.execute(
            "SELECT path, parse_err FROM files WHERE path IN (?,?)", (R1, R2)))
    finally:
        conn.close()
    assert "membership cycle" in (rows.get(R1) or ""), rows
    assert "membership cycle" in (rows.get(R2) or ""), rows

    # doctor lists both cyclic files
    d = _planctl("doctor", "--json", timeout=30)
    assert d.returncode == 0, d.stderr
    dj = json.loads(d.stdout)
    cyc = {n for pair in dj["cycles"] for n in pair}
    assert R1 in cyc and R2 in cyc, dj["cycles"]
