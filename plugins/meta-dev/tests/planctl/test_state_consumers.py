"""Regression tests for stage-state consumers that can hide wrong signals."""
import json
import os
from types import SimpleNamespace

from planctl import db, derive, events, reconcile, stage


def test_derive_glyph_shows_needs_review_drift():
    assert derive.glyph("needs-review", drift=True) == "⏳⚠️"
    assert derive.glyph("needs-review", drift=False) == "⏳"
    assert derive.glyph("done", drift=True) == "✅⚠️"


def test_derive_emoji_is_an_alias_of_glyph():
    """glyph and emoji were two vocabularies; the open-right chassis collapsed
    them into one, so emoji() is now an alias kept for call-site compatibility."""
    assert derive.emoji("needs-review", drift=True) == "⏳⚠️"
    assert derive.emoji("needs-review", drift=False) == "⏳"
    assert derive.emoji("done", drift=True) == "✅⚠️"
    for status in derive.PLAN_STATUSES + derive.OVERRIDES:
        assert derive.emoji(status) == derive.glyph(status)


def _write_plan(root, rel, checked):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mark = "x" if checked else " "
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(
            "---\nstage: 6\nstage_state: active\nrepo: meta\n"
            "context: none\ndocs: none\n---\n\n# Fixture\n\n"
            "- [%s] `T1.1` execution task\n" % mark
        )


def _seed_plan(rel, checked):
    conn = db.open_db()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO meta(key,value) VALUES('derive_v',?)",
            (str(derive.DERIVE_V),),
        )
        conn.execute(
            "INSERT INTO plans(path,repo,stage,stage_state,tasks_done,"
            "tasks_total,drift,derived_status) VALUES(?,?,?,?,?,?,?,?)",
            (rel, "meta", 6, "active", int(checked), 1,
             int(not checked), "needs-review"),
        )
        conn.execute(
            "INSERT INTO tasks(plan_path,tid,line_no,checked,human_verify,"
            "section,text) VALUES(?,?,?,?,?,?,?)",
            (rel, "T1.1", 10, int(checked), 0, "Fixture", "execution task"),
        )
        conn.commit()
    finally:
        conn.close()


def _run_reconcile(monkeypatch, capsys, rel, checked):
    root = os.environ["META_DEV_ROOT"]
    _write_plan(root, rel, checked)
    _seed_plan(rel, checked)

    monkeypatch.setattr(reconcile.sync, "_head_sha", lambda _root: None)
    monkeypatch.setattr(reconcile.sync, "_needs_full", lambda _conn, _root: False)
    monkeypatch.setattr(
        reconcile, "_build_review_cache", lambda: {rel: ("pass", 1.0)})
    monkeypatch.setattr(reconcile, "_build_stage5_ts_cache", lambda: {})
    monkeypatch.setattr(
        reconcile, "_docs_evidence_gate",
        lambda _conn, _root, _plan, _ts: ([], []),
    )
    monkeypatch.setattr(reconcile, "_manage_inbox_items", lambda *_args: None)
    monkeypatch.setattr(reconcile, "_self_heal_runbooks", lambda *_args: set())
    monkeypatch.setattr(events, "append", lambda _event: None)

    stage_calls = []
    monkeypatch.setattr(stage, "cmd_stage", lambda args: stage_calls.append(args))

    assert reconcile.cmd_reconcile(SimpleNamespace(json=True)) == 0
    payload = json.loads(capsys.readouterr().out)
    return payload, stage_calls


def test_done_gate_stage6_active_complete_stamps_done(monkeypatch, capsys):
    rel = "plans/meta/live-review-complete.md"
    payload, stage_calls = _run_reconcile(
        monkeypatch, capsys, rel, checked=True)

    assert payload["decisions"] == [
        {"plan": rel, "decision": "done", "runbook": None}
    ]
    assert len(stage_calls) == 1
    assert stage_calls[0].stage == "6"
    assert stage_calls[0].status == "completed"


def test_done_gate_stage6_active_open_boxes_reports_failure(monkeypatch, capsys):
    rel = "plans/meta/live-review-open.md"
    payload, stage_calls = _run_reconcile(
        monkeypatch, capsys, rel, checked=False)

    assert payload["decisions"] == [
        {"plan": rel, "decision": "fail_open_boxes", "open_exec": 1}
    ]
    assert stage_calls == []


def test_done_gate_scope_preserves_stage5_and_legacy_stage6(tmp_path):
    conn = db.open_db()
    try:
        rows = [
            ("plans/meta/stage5.md", 5, None),
            ("plans/www/stage6-active.md", 6, "active"),
            ("plans/gallery/stage6-legacy.md", 6, None),
        ]
        conn.executemany(
            "INSERT INTO plans(path,stage,stage_state,tasks_total) "
            "VALUES(?,?,?,1)",
            rows,
        )
        scopes = reconcile._build_scope_set(conn, str(tmp_path))
    finally:
        conn.close()

    assert set(scopes) == {
        ("plans/meta/stage5.md", "plans/meta/stage5.md"),
        ("plans/www/stage6-active.md", "plans/www/stage6-active.md"),
    }
