#!/usr/bin/env python3
"""Sync parity test — incremental ≡ full rebuild (design §10 item 2; critical test 2/4).

The silent-staleness guard: after ANY mutation (edit / delete / rename / archive
/ malformed-frontmatter / nested-runbook), the INCREMENTAL sync result must EQUAL
a fresh ``--full`` rebuild on the same tree — on the compared column set (files
sha/kind, membership, edges, plans counts/derived_status, tasks), EXCLUDING
``meta.last_commit`` (the watermark legitimately differs between the two).

Also locks: ancestor-runbook rollup incremental == full (W2-T5), sha1
short-circuit (no-op → ``synced:[]``), uncommitted-porcelain detection, the
``--file`` single-file path, and ~20-round index stability (W2-T3 — event-line
count is 0d's concern; here we assert index + integrity stability).

Each test builds a git-tracked fixture under the conftest-pinned ``META_DEV_ROOT``
tmp dir and sets ``META_DEV_STATE_DIR`` (via conftest) — NEVER the live tree or
live DB.
"""
import json
import os
import subprocess
from types import SimpleNamespace

import pytest  # noqa: E402  (conftest puts scripts/ on sys.path)

from planctl import db, read, sync  # noqa: E402


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


def run_sync(full=False, file=None, json_out=False):
    args = SimpleNamespace(full=full, file=file, json=json_out)
    rc = sync.cmd_sync(args)
    assert rc == 0, "sync returned %s" % rc


def _snapshot(conn):
    """Comparable index snapshot — the parity column set.

    EXCLUDES ``meta`` entirely (``last_commit`` legitimately differs between an
    incremental sync and a fresh ``--full``; ``derive_v`` is stable)."""
    return {
        "files": sorted(conn.execute(
            "SELECT path,kind,sha1,parse_err FROM files")),
        "plans": sorted(conn.execute(
            "SELECT path,repo,stage,override,note,why,title,tasks_done,tasks_total,"
            "human_open,human_total,raw_done,raw_total,drift,context_json,docs_json,"
            "derived_status FROM plans")),
        "tasks": sorted(conn.execute(
            "SELECT plan_path,tid,checked,human_verify,section,text FROM tasks")),
        "membership": sorted(conn.execute(
            "SELECT parent,child,ord,child_kind FROM membership")),
        "edges": sorted(conn.execute("SELECT src,dst,kind FROM edges")),
    }


def _snap():
    conn = db.open_db()
    try:
        return _snapshot(conn)
    finally:
        conn.close()


def _build_base_tree(root):
    """Two plans (alpha depends-on beta), a runbook of both, plus sacrificial
    files — one per mutation class (delete/rename/archive/malform/nest)."""
    _write(root, "plans/meta/2026-01-01-alpha.md",
           "---\nstage: 5\nrepo: meta\nwhy: alpha\n"
           "depends: [plans/meta/2026-01-02-beta.md]\n---\n"
           "# Alpha\n## Build\n- [x] `T1.1` one #a1b2\n- [ ] `T1.2` two #c3d4\n")
    _write(root, "plans/meta/2026-01-02-beta.md",
           "---\nstage: 3\nrepo: meta\n---\n# Beta\n- [ ] first\n")
    _write(root, "plans/meta/2026-01-03-gamma.md",
           "---\nstage: 1\nrepo: meta\n---\n# Gamma\n- [ ] g\n")
    _write(root, "plans/meta/2026-01-04-delta.md",
           "---\nstage: 2\nrepo: meta\n---\n# Delta\n- [ ] d\n")
    _write(root, "plans/meta/2026-01-05-epsilon.md",
           "---\nstage: 2\nrepo: meta\n---\n# Epsilon\n- [ ] e\n")
    _write(root, "plans/meta/_runbook-2026-01-01.md",
           "---\ntype: runbook\nrepo: meta\nmembers:\n"
           "  - plans/meta/2026-01-01-alpha.md\n"
           "  - plans/meta/2026-01-02-beta.md\n---\n# Runbook One\n")


@pytest.fixture
def tree():
    """A committed, full-synced base tree; returns the fixture root path."""
    root = _root()
    _build_base_tree(root)
    _git_init(root)
    _commit(root, "init")
    run_sync(full=True)
    return root


# ── the parity guard: incremental ≡ full after every mutation class ───────────
def test_incremental_equals_full_after_mutations(tree):
    root = tree
    # DELETE gamma
    os.remove(os.path.join(root, "plans/meta/2026-01-03-gamma.md"))
    # RENAME delta -> delta2 (git-detected rename)
    assert _git(root, "mv", "plans/meta/2026-01-04-delta.md",
                "plans/meta/2026-01-04-delta2.md").returncode == 0
    # ARCHIVE epsilon (mv under _archive/ → must vanish from the index)
    os.makedirs(os.path.join(root, "plans/_archive"), exist_ok=True)
    assert _git(root, "mv", "plans/meta/2026-01-05-epsilon.md",
                "plans/_archive/2026-01-05-epsilon.md").returncode == 0
    # MALFORMED frontmatter (unclosed block) — present with parse_err, NOT dropped
    _write(root, "plans/meta/2026-01-06-zeta.md",
           "---\nstage: 3\nrepo: meta\nNO_CLOSING_FENCE\n# Zeta\n- [ ] z\n")
    # NESTED runbook (member is a plan)
    _write(root, "plans/meta/_runbook-2026-01-02.md",
           "---\ntype: runbook\nrepo: meta\nmembers:\n"
           "  - plans/meta/2026-01-01-alpha.md\n---\n# Runbook Two\n")
    _commit(root, "mutations")

    run_sync(full=False)              # incremental over the mutated tree
    inc = _snap()
    run_sync(full=True)               # fresh full rebuild on the SAME mutated tree
    full = _snap()
    assert inc == full, "incremental index drifted from full rebuild"

    files = {r[0]: r for r in full["files"]}
    assert "plans/meta/2026-01-03-gamma.md" not in files          # deleted → gone
    assert "plans/meta/2026-01-04-delta.md" not in files          # renamed-old → gone
    assert "plans/meta/2026-01-04-delta2.md" in files             # renamed-new → present
    assert "plans/meta/2026-01-05-epsilon.md" not in files        # archived → gone
    assert not any("_archive" in p for p in files), files         # _archive excluded
    # malformed → present WITH parse_err (never silently dropped — W2A-5)
    assert "plans/meta/2026-01-06-zeta.md" in files
    zeta_pe = dict(zip(("path", "kind", "sha1", "parse_err"),
                       files["plans/meta/2026-01-06-zeta.md"]))["parse_err"]
    assert zeta_pe, "malformed file must carry a parse_err, not be dropped"
    # nested runbook membership populated
    nested_members = {r[1] for r in full["membership"]
                      if r[0] == "plans/meta/_runbook-2026-01-02.md"}
    assert "plans/meta/2026-01-01-alpha.md" in nested_members


# ── W2-T5: incremental ancestor rollup == --full rollup ────────────────────────
def test_incremental_ancestor_rollup_equals_full(tree):
    root = tree
    _write(root, "plans/meta/2026-01-02-beta.md",
           "---\nstage: 3\nrepo: meta\n---\n# Beta\n- [x] first\n")  # flip 0/1 → 1/1
    _commit(root, "flip beta")

    run_sync(full=False)
    conn = db.open_db()
    try:
        inc_rollup = sync.compute_rollup(conn, "plans/meta/_runbook-2026-01-01.md")
    finally:
        conn.close()
    run_sync(full=True)
    conn = db.open_db()
    try:
        full_rollup = sync.compute_rollup(conn, "plans/meta/_runbook-2026-01-01.md")
    finally:
        conn.close()

    assert inc_rollup == full_rollup
    # the rollup reflects the flip: alpha 1/2 + beta 1/1 → 2/3 tasks done
    assert (inc_rollup["tasks_done"], inc_rollup["tasks_total"]) == (2, 3)


# ── sha1 short-circuit: a no-op re-sync reports synced: [] ─────────────────────
def test_sha_short_circuit_noop_reports_empty(tree, capsys):
    run_sync(full=False)          # warm: advance watermark onto HEAD
    capsys.readouterr()           # discard
    run_sync(json_out=True)       # no changes → must short-circuit every file
    out = json.loads(capsys.readouterr().out)
    assert out["synced"] == [], out
    assert out["full"] is False


# ── porcelain path: an UNCOMMITTED mutation is detected (not just committed) ──
def test_incremental_detects_uncommitted_porcelain(tree):
    root = tree
    _write(root, "plans/meta/2026-01-02-beta.md",
           "---\nstage: 3\nrepo: meta\n---\n# Beta\n- [x] first\n")  # dirty, NOT committed
    run_sync(full=False)
    conn = db.open_db()
    try:
        row = conn.execute(
            "SELECT tasks_done,tasks_total,derived_status FROM plans "
            "WHERE path='plans/meta/2026-01-02-beta.md'").fetchone()
    finally:
        conn.close()
    assert row == (1, 1, "needs-review")  # porcelain caught the dirty edit


# ── --file path: reindex ONE file regardless of git state ──────────────────────
def test_file_flag_reindexes_one_and_matches_full(tree):
    root = tree
    _write(root, "plans/meta/2026-01-02-beta.md",
           "---\nstage: 3\nrepo: meta\n---\n# Beta\n- [x] first\n")  # dirty
    run_sync(file="plans/meta/2026-01-02-beta.md")
    inc = _snap()
    run_sync(full=True)
    full = _snap()
    assert inc == full
    conn = db.open_db()
    try:
        row = conn.execute(
            "SELECT tasks_done,tasks_total,derived_status FROM plans "
            "WHERE path='plans/meta/2026-01-02-beta.md'").fetchone()
    finally:
        conn.close()
    assert row == (1, 1, "needs-review")


# ── W2-T3: ~20 sync rounds leave the index stable + integrity ok ───────────────
def test_index_stable_across_rounds(tree):
    base = _snap()
    for _ in range(20):
        run_sync(full=False)          # no changes between rounds
    assert _snap() == base, "no-op sync rounds mutated the index"
    conn = db.open_db()
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()


# ── --full rebuilds from scratch and is self-consistent ────────────────────────
def test_full_rebuild_is_idempotent(tree):
    a = _snap()
    run_sync(full=True)
    b = _snap()
    assert a == b


# ── first-ever sync (no watermark) behaves as --full ───────────────────────────
def test_first_ever_sync_is_full(tree):
    # wipe state DB; a cold incremental must auto-escalate to a full rebuild
    sdir = os.environ["META_DEV_STATE_DIR"]
    for sidecar in ("state.db", "state.db-wal", "state.db-shm"):
        try:
            os.remove(os.path.join(sdir, sidecar))
        except FileNotFoundError:
            pass
    run_sync(full=False)              # no watermark → _needs_full → full
    conn = db.open_db()
    try:
        # derive_v written (proves it took the --full path)
        assert conn.execute(
            "SELECT value FROM meta WHERE key='derive_v'").fetchone() == (str(sync.derive.DERIVE_V),)
        assert _snapshot(conn)  # index populated
    finally:
        conn.close()


# ── FIX 6a: uncommitted git mv parity ─────────────────────────────────────────
def test_uncommitted_rename_parity(tree):
    """git mv of a plan BEFORE commit — sync detects old path gone, new path
    indexed, incremental ≡ full."""
    root = tree
    # uncommitted rename (porcelain-only — no commit)
    assert _git(root, "mv", "plans/meta/2026-01-04-delta.md",
                "plans/meta/2026-01-04-delta2.md").returncode == 0
    run_sync(full=False)              # incremental BEFORE commit
    inc = _snap()
    run_sync(full=True)               # full on the same dirty tree
    full = _snap()
    assert inc == full, "uncommitted rename: incremental drifted from full"
    files = {r[0]: r for r in full["files"]}
    assert "plans/meta/2026-01-04-delta.md" not in files   # old path gone
    assert "plans/meta/2026-01-04-delta2.md" in files      # new path indexed


# ── FIX 6b: nested runbook (runbook whose members includes another runbook) ───
def test_nested_runbook_parity(tree):
    """A runbook whose members: includes another runbook — incremental ≡ full
    rollup including the child_kind='runbook' membership row."""
    root = tree
    _write(root, "plans/meta/_runbook-2026-01-03.md",
           "---\ntype: runbook\nrepo: meta\nmembers:\n"
           "  - plans/meta/_runbook-2026-01-01.md\n---\n# Nested Runbook\n")
    _commit(root, "nested runbook")
    run_sync(full=False)
    inc = _snap()
    run_sync(full=True)
    full = _snap()
    assert inc == full, "nested runbook: incremental drifted from full"
    memberships = {(r[0], r[1], r[3]) for r in full["membership"]}
    assert ("plans/meta/_runbook-2026-01-03.md",
            "plans/meta/_runbook-2026-01-01.md", "runbook") in memberships


# ── FIX 6c: next-verb blocks: edge gating ────────────────────────────────────
def test_next_blocks_gating(tree):
    """blocks: edge — the BLOCKER is offered and the BLOCKED plan is gated."""
    root = tree
    # Blocker: ready (stage 3, no tasks), blocks Blocked
    _write(root, "plans/meta/2026-01-03-blocks-alpha.md",
           "---\nstage: 3\nrepo: meta\nblocks:\n"
           "  - plans/meta/2026-01-03-blocks-beta.md\n---\n# Blocker\n")
    # Blocked: ready (stage 3, no tasks), blocked by Blocker
    _write(root, "plans/meta/2026-01-03-blocks-beta.md",
           "---\nstage: 3\nrepo: meta\n---\n# Blocked\n")
    _write(root, "plans/meta-runbook.md",
           "## Sequence\n"
           "- plans/meta/2026-01-03-blocks-alpha.md\n"
           "- plans/meta/2026-01-03-blocks-beta.md\n")
    _commit(root, "blocks fixture")
    run_sync(full=True)

    conn = db.open_db()
    try:
        nxt = read._next_list(conn, root)
    finally:
        conn.close()
    paths = [n["path"] for n in nxt]
    # Blocker is ready and unblocked → offered
    assert "plans/meta/2026-01-03-blocks-alpha.md" in paths
    # Blocked is ready but gated by unfinished blocker → NOT offered
    assert "plans/meta/2026-01-03-blocks-beta.md" not in paths

    # Now finish the blocker → blocked plan should become unblocked
    _write(root, "plans/meta/2026-01-03-blocks-alpha.md",
           "---\nstage: 6\nrepo: meta\nblocks:\n"
           "  - plans/meta/2026-01-03-blocks-beta.md\n---\n# Blocker\n")
    _commit(root, "finish blocker")
    run_sync(full=True)

    conn = db.open_db()
    try:
        nxt2 = read._next_list(conn, root)
    finally:
        conn.close()
    paths2 = [n["path"] for n in nxt2]
    # Blocked plan now appears (blocker is done)
    assert "plans/meta/2026-01-03-blocks-beta.md" in paths2
