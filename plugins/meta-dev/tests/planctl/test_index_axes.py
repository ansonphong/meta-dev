#!/usr/bin/env python3
"""Schema/arity guards for the smoke_total + stage_state index axes."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
from types import SimpleNamespace

from planctl import db, read, sync  # noqa: E402


LEGACY_DB = Path(
    "/tmp/claude-1000/-mnt-d-Projects-sample-host/"
    "c1f46252-e549-48fd-9db3-60258c198fd2/scratchpad/legacy-schema.db"
)
LEGACY_PLAN_COLUMNS = [
    "path", "repo", "stage", "override", "note", "why", "title",
    "tasks_done", "tasks_total", "human_open", "human_total", "raw_done",
    "raw_total", "drift", "context_json", "docs_json", "derived_status",
]


def _write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_legacy_db(dst):
    """Copy the preserved warm DB, with a portable equivalent as fallback."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if LEGACY_DB.is_file():
        shutil.copy2(LEGACY_DB, dst)
        return

    # The preserved fixture is local to the hardening run. Keep this regression
    # executable elsewhere by creating the same pre-change 17-column schema.
    legacy_schema = "\n".join(
        line for line in db.SCHEMA.splitlines()
        if "smoke_total" not in line and "stage_state" not in line
    )
    conn = sqlite3.connect(dst)
    try:
        conn.executescript(legacy_schema)
        conn.execute(
            "INSERT INTO meta(key,value) VALUES('derive_v','1')")
        conn.commit()
    finally:
        conn.close()


def test_warm_legacy_schema_upgrades_both_axes_before_sync(capsys):
    """A copied 17-column cache migrates in place before its first upsert."""
    state_db = Path(os.environ["META_DEV_STATE_DIR"]) / "state.db"
    _seed_legacy_db(state_db)

    with sqlite3.connect("file:%s?mode=ro" % state_db, uri=True) as legacy:
        before = [row[1] for row in legacy.execute("PRAGMA table_info(plans)")]
    assert before == LEGACY_PLAN_COLUMNS

    root = Path(os.environ["META_DEV_ROOT"])
    _write(
        root,
        "plans/meta/2026-01-01-warm-upgrade.md",
        "---\nstage: 6\nstage_state: active\nrepo: meta\n---\n"
        "# Warm upgrade\n- [x] indexed\n## Smoke Test\n- inspect it\n",
    )

    assert sync.cmd_sync(
        SimpleNamespace(full=False, file=None, json=True)) == 0
    capsys.readouterr()

    conn = db.open_db()
    try:
        after = [row[1] for row in conn.execute("PRAGMA table_info(plans)")]
        indexed = conn.execute(
            "SELECT derived_status,smoke_total,stage_state FROM plans "
            "WHERE path='plans/meta/2026-01-01-warm-upgrade.md'"
        ).fetchone()
    finally:
        conn.close()

    assert after == LEGACY_PLAN_COLUMNS + ["smoke_total", "stage_state"]
    assert indexed == ("needs-review", 1, "active")


def test_plan_row_keeps_derived_status_at_index_16(capsys):
    """Both tail columns preserve fixed unpacking and mrow[16] semantics."""
    root = Path(os.environ["META_DEV_ROOT"])
    plan = "plans/meta/2026-01-01-index-axes.md"
    runbook = "plans/meta/_runbook-index-axes.md"
    _write(
        root,
        plan,
        "---\nstage: 6\nstage_state: ACTIVE\nrepo: meta\n---\n"
        "# Index axes\n- [x] execution done\n"
        "## Smoke Tests\n- inspect pixels\n- inspect seams\n",
    )
    _write(
        root,
        runbook,
        "---\ntype: runbook\nrepo: meta\nmembers:\n  - %s\n---\n"
        "# Index axes runbook\n" % plan,
    )

    assert sync.cmd_sync(
        SimpleNamespace(full=True, file=None, json=True)) == 0
    capsys.readouterr()

    conn = db.open_db()
    try:
        row = read._plan_row(conn, plan)
        brief = read._build_brief(conn, str(root), runbook=runbook)
    finally:
        conn.close()

    assert len(row) == 19
    assert row[16:] == ("needs-review", 2, "active")
    assert brief["members"][0]["status"] == "needs-review"

    # Exercise cmd_status's fixed-width tuple unpack as well as the direct row.
    assert read.cmd_status(SimpleNamespace(plan=plan, json=True)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["derived_status"] == "needs-review"
