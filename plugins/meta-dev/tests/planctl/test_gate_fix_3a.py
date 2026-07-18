"""Gate-fix 3a tests — guards against silent state corruption.

Hermetic: ``META_DEV_STATE_DIR`` + ``META_DEV_ROOT`` are auto-pinned to tmp dirs
by conftest. Never touches the real ~/.cache/meta-dev or a real plan file.
"""
import json
import os
import subprocess
import sys
import types


# ── helpers ──────────────────────────────────────────────────────────────────
_SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
_PCTL = os.path.join(_SCRIPTS, "planctl.sh")
_WC_SH = os.path.join(_SCRIPTS, "worker-claim.sh")
_STAMP = os.path.join(_SCRIPTS, "task-stamp.py")


def _write_plan(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _planctl(*args, **kwargs):
    """Run ``planctl.sh <verb> …``, return (rc, stdout, stderr)."""
    r = subprocess.run(
        ["bash", _PCTL] + list(args),
        capture_output=True, text=True, timeout=30, **kwargs,
    )
    return r.returncode, r.stdout, r.stderr


def _stamp(plan_path):
    """Run task-stamp.py to add T<N>.<M> tags to untagged checkboxes."""
    r = subprocess.run(
        ["python3", _STAMP, plan_path],
        capture_output=True, text=True, timeout=30,
    )
    return r.returncode, r.stdout, r.stderr


# ── T1: human-gate bypass — indented heading (F2) ────────────────────────────

def test_indented_acceptance_heading_activates_human_verify(tmp_path):
    """F2: 0–3 leading spaces before # must still trigger human_verify."""
    root = os.environ["META_DEV_ROOT"]
    plan = os.path.join(root, "plans/meta/fixture.md")
    _write_plan(plan, """---
stage: 1
repo: meta
---
# Test

  ### Acceptance
- [ ] First box under indented heading

### Acceptance
- [ ] Second box under non-indented heading
""")
    # Stamp to add T<N>.<M> tags.
    _stamp(plan)

    # Both boxes are under an "Acceptance" heading → human_verify=True.
    # Neither should flip without --human.
    rc1, out1, err1 = _planctl("check", plan, "T0.1", "--json")
    assert rc1 != 0, f"indented-heading box should be gated, got rc={rc1} stderr={err1}"
    payload1 = json.loads(out1)
    skipped1 = {s["tid"]: s["reason"] for s in payload1.get("skipped", [])}
    assert skipped1.get("T0.1") == "human_verify", \
        f"indented Acceptance must trigger human_verify; skipped={skipped1}"

    rc2, out2, err2 = _planctl("check", plan, "T0.2", "--json")
    assert rc2 != 0, f"non-indented Acceptance box should also be gated, got rc={rc2}"
    payload2 = json.loads(out2)
    skipped2 = {s["tid"]: s["reason"] for s in payload2.get("skipped", [])}
    assert skipped2.get("T0.2") == "human_verify", \
        f"both Acceptance boxes must have human_verify=True; skipped={skipped2}"


# ── T2: uncheck reopens a human-verify task (F1) ─────────────────────────────

def test_uncheck_reopens_human_task(tmp_path):
    """F1: uncheck must NOT apply the human-verify gate."""
    root = os.environ["META_DEV_ROOT"]
    plan = os.path.join(root, "plans/meta/uncheck-human.md")
    _write_plan(plan, """---
stage: 1
repo: meta
---
# Test

### Acceptance
- [x] by eye smoke test
""")
    # Stamp to add T<N>.<M> tags.
    _stamp(plan)

    # Uncheck must succeed without --human (gate only applies to check direction).
    rc1, out1, err1 = _planctl("uncheck", plan, "T0.1", "--json")
    assert rc1 == 0, f"uncheck of human task must succeed, got rc={rc1} stderr={err1}"
    payload1 = json.loads(out1)
    assert payload1.get("flipped") == ["T0.1"], \
        f"uncheck must reopen human task; flipped={payload1.get('flipped')}"

    # Verify file: box is now [ ].
    with open(plan, "r") as f:
        assert "- [ ]" in f.read(), "box must be unchecked after task-undone"

    # Run uncheck again → no-op, rc=0.
    rc2, out2, err2 = _planctl("uncheck", plan, "T0.1", "--json")
    assert rc2 == 0, f"second uncheck must be no-op, got rc={rc2}"
    payload2 = json.loads(out2)
    assert payload2.get("flipped") == [], \
        f"already-open box must not flip again; flipped={payload2.get('flipped')}"


# ── T3: claim ownership + liveness (F3) ──────────────────────────────────────

def test_claim_foreign_release_does_not_delete_owners_claim(tmp_path):
    """F3: a foreign-session release does NOT delete the owner's claim."""
    root = os.environ["META_DEV_ROOT"]
    scope = "plans/meta/test-claim.md"
    _write_plan(os.path.join(root, scope), """---
stage: 1
repo: meta
---
# Test
- [ ] Box
""")

    sys.path.insert(0, _SCRIPTS)
    from planctl import claims

    # Claim as pid=1, session=A.
    args_claim = types.SimpleNamespace(
        plan=scope, pid=1, session="test-sess-A", ttl=7200, json=False,
    )
    rc = claims.cmd_claim(args_claim)
    assert rc == 0, f"claim as pid=1 should be granted, got rc={rc}"

    # Release as pid=99999, session=B — must NOT delete pid=1's claim.
    args_release_foreign = types.SimpleNamespace(
        plan=scope, pid=99999, session="test-sess-B", json=False,
    )
    rc_rel = claims.cmd_release(args_release_foreign)
    assert rc_rel == 0, "foreign release must exit 0 (no-op, not an error)"

    # pid=1's claim still exists.
    conn = claims.db.open_db()
    try:
        row = conn.execute(
            "SELECT scope,pid,session FROM claims WHERE scope=?",
            (scope,),
        ).fetchone()
        assert row is not None, "pid=1's claim must survive foreign release"
        assert str(row[1]) == "1", f"claim pid must still be 1, got {row[1]}"
    finally:
        conn.close()

    # Cleanup: release as owner.
    args_release_owner = types.SimpleNamespace(
        plan=scope, pid=1, session="test-sess-A", json=False,
    )
    claims.cmd_release(args_release_owner)


def test_claim_alive_pid_beats_ttl(tmp_path):
    """F3: a claim whose pid is alive is LIVE regardless of TTL."""
    root = os.environ["META_DEV_ROOT"]
    scope = "plans/meta/test-claim-ttl.md"
    _write_plan(os.path.join(root, scope), """---
stage: 1
repo: meta
---
# Test
- [ ] Box
""")

    sys.path.insert(0, _SCRIPTS)
    from planctl import claims

    # Claim with our PPID (which IS alive) and a very short TTL of 1 second.
    import os as _os
    my_pid = _os.getppid()
    args_claim = types.SimpleNamespace(
        plan=scope, pid=my_pid, session="test-sess-alive", ttl=1, json=False,
    )
    rc = claims.cmd_claim(args_claim)
    assert rc == 0, f"claim with alive pid should be granted, got rc={rc}"

    # Wait past TTL.
    import time
    time.sleep(1.1)

    # The claim should STILL be live because our pid is alive.
    conn = claims.db.open_db()
    try:
        row = conn.execute(
            "SELECT scope,pid,status,ttl FROM claims WHERE scope=?",
            (scope,),
        ).fetchone()
        assert row is not None, "claim must still exist"
        assert row[2] == "claimed", "claim status must be 'claimed'"
        # Sweep must NOT reap it.
        with conn:
            swept = claims._sweep_stale(conn)
        assert scope not in [s[0] for s in swept], \
            f"sweep must not reap alive-pid claim; swept={swept}"
    finally:
        conn.close()

    # Cleanup.
    args_release = types.SimpleNamespace(
        plan=scope, pid=my_pid, session="test-sess-alive", json=False,
    )
    claims.cmd_release(args_release)


# ── T4: check never false-succeeds (F4) ──────────────────────────────────────

def test_check_never_false_succeeds(tmp_path):
    """F4: worker-claim.sh check must exit non-zero when planctl fails."""
    root = os.environ["META_DEV_ROOT"]
    _write_plan(os.path.join(root, "plans/meta/test-check.md"), """---
stage: 1
repo: meta
---
# Test
""")

    # Point state dir at a corrupt location: make state.db a directory so SQLite
    # can't open it.
    bad_state = str(tmp_path / "bad-state")
    os.makedirs(os.path.join(bad_state, "state.db"), exist_ok=False)

    env = {**os.environ, "META_DEV_STATE_DIR": bad_state}
    r = subprocess.run(
        ["bash", _WC_SH, "check", "plans/meta/test-check.md"],
        capture_output=True, text=True, timeout=30,
        env=env,
    )
    rc, out, err = r.returncode, r.stdout, r.stderr
    # Must NOT print FREE and must exit non-zero.
    assert rc != 0, \
        f"check must exit non-zero on planctl failure, got rc={rc} stdout={out!r} stderr={err!r}"
    assert "FREE" not in out, \
        f"check must NOT print FREE on failure; stdout={out!r}"
    # Diagnostic must appear somewhere (stderr from planctl or from worker-claim).
    combined = out + err
    assert len(combined) > 0 or rc != 0, \
        "failure must produce diagnostic or non-zero exit"


# ── T5: F11 _row_live precedence ladder ──────────────────────────────────────

def test_row_live_precedence_all_four_rungs(tmp_path):
    """F11: dead pid within TTL → NOT live; alive pid beats TTL; unknown falls to TTL."""
    sys.path.insert(0, _SCRIPTS)
    from planctl import claims

    now = claims._now()

    # rung 1: status != 'claimed' → False
    row_released = ("scope", "s", "h", now, 12345, "released", 7200)
    assert claims._row_live(row_released) is False, "rung 1: released → False"

    # rung 2: known-dead pid, age < ttl → False (the crash-recovery regression)
    row_dead_fresh = ("scope", "s", "h", now - 10, 99999, "claimed", 7200)
    # 99999 is almost certainly dead
    assert claims._row_live(row_dead_fresh) is False, \
        "rung 2: dead pid within TTL → NOT live (crash recovery)"

    # rung 3: known-alive pid → True (regardless of age)
    import os as _os
    my_pid = _os.getppid()
    row_alive_old = ("scope", "s", "h", now - 100000, my_pid, "claimed", 1)
    assert claims._row_live(row_alive_old) is True, \
        "rung 3: alive pid → LIVE regardless of age"

    # rung 4: unknown pid → TTL check
    row_unknown_fresh = ("scope", "s", "h", now - 10, None, "claimed", 7200)
    assert claims._row_live(row_unknown_fresh) is True, \
        "rung 4: unknown pid within TTL → LIVE"

    row_unknown_expired = ("scope", "s", "h", now - 100000, None, "claimed", 1)
    assert claims._row_live(row_unknown_expired) is False, \
        "rung 4: unknown pid past TTL → NOT live"


# ── T6: F12 unknown-pid reaped after TTL ─────────────────────────────────────

def test_unknown_pid_reaped_after_ttl(tmp_path):
    """F12: None/0/''/'-1' are unknown → TTL decides; all reaped past TTL, live before."""
    sys.path.insert(0, _SCRIPTS)
    from planctl import claims

    now = claims._now()

    # All these pids must return None (unknown).
    for bad_pid in (None, 0, '', -1, 'abc'):
        assert claims._pid_alive(bad_pid) is None, \
            f"F12: _pid_alive({bad_pid!r}) must be None (unknown)"

    # Past TTL → all reaped.
    for pid in (None, 0, '', -1, 'abc'):
        row = ("scope", "s", "h", now - 100000, pid, "claimed", 1)
        assert claims._row_live(row) is False, \
            f"F12: pid={pid!r} past TTL must be NOT live"

    # Within TTL → all live.
    for pid in (None, 0, '', -1, 'abc'):
        row = ("scope", "s", "h", now - 10, pid, "claimed", 7200)
        assert claims._row_live(row) is True, \
            f"F12: pid={pid!r} within TTL must be LIVE"


# ── T7: F14 release ownership ────────────────────────────────────────────────

def test_release_same_owner_deletes_foreign_does_not(tmp_path):
    """F14: same-owner release deletes; foreign pid+session does not."""
    root = os.environ["META_DEV_ROOT"]
    scope = "plans/meta/test-f14-release.md"
    _write_plan(os.path.join(root, scope), """---
stage: 1
repo: meta
---
# Test
- [ ] Box
""")

    sys.path.insert(0, _SCRIPTS)
    from planctl import claims

    # Claim with explicit pid=42, session="owner-sess".
    args_claim = types.SimpleNamespace(
        plan=scope, pid=42, session="owner-sess", ttl=7200, json=False,
    )
    rc = claims.cmd_claim(args_claim)
    assert rc == 0, f"claim must be granted, got rc={rc}"

    # Foreign release (pid=99, session="other") — must NOT delete.
    args_rel_foreign = types.SimpleNamespace(
        plan=scope, pid=99, session="other", json=False,
    )
    rc2 = claims.cmd_release(args_rel_foreign)
    assert rc2 == 0, "foreign release must exit 0"

    # Claim must still exist.
    conn = claims.db.open_db()
    try:
        row = conn.execute(
            "SELECT scope,pid,session FROM claims WHERE scope=?",
            (scope,),
        ).fetchone()
        assert row is not None, "claim must survive foreign release"
        assert str(row[1]) == "42", f"pid must still be 42, got {row[1]}"
    finally:
        conn.close()

    # Same-owner release with pid=42, session="owner-sess" — must delete.
    args_rel_owner = types.SimpleNamespace(
        plan=scope, pid=42, session="owner-sess", json=False,
    )
    rc3 = claims.cmd_release(args_rel_owner)
    assert rc3 == 0, "same-owner release must exit 0"

    # Claim must be gone.
    conn2 = claims.db.open_db()
    try:
        row = conn2.execute(
            "SELECT scope FROM claims WHERE scope=?",
            (scope,),
        ).fetchone()
        assert row is None, "same-owner release must delete the claim"
    finally:
        conn2.close()
