"""Focused inbox hygiene: upsert must not grow an already-open id; drain
collapses duplicate snapshots and skips corrupt lines.

Fixtures live under pytest ``tmp_path`` / ``META_DEV_ROOT``. Never the live
22MB host inbox.
"""
import json
import os

from planctl import inbox


def _root(tmp_path):
    root = tmp_path / "proj"
    (root / "plans" / "_dashboard" / "inbox").mkdir(parents=True)
    return str(root)


def _jsonl_records(path):
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def test_upsert_existing_open_does_not_append(tmp_path):
    root = _root(tmp_path)
    plan = "plans/app/example/00-master-plan.md"
    item_id = inbox.upsert(root, plan, "review_missing", "needs review", "body")
    path = inbox._inbox_path(root)
    first_n = len(_jsonl_records(path))
    again_id = inbox.upsert(root, plan, "review_missing", "needs review", "body")
    records = _jsonl_records(path)
    open_items = inbox.read_open_items(root)

    assert again_id == item_id
    assert first_n == 1
    assert len(records) == first_n
    assert list(open_items) == [item_id]
    assert open_items[item_id]["status"] == "open"

    other_id = inbox.upsert(root, plan, "open_boxes", "open boxes", "body")
    assert other_id != item_id
    assert len(_jsonl_records(path)) == 2
    assert len(inbox.read_open_items(root)) == 2


def test_drain_dedup_corrupt_line_keeps_open_count(tmp_path):
    root = _root(tmp_path)
    path = inbox._inbox_path(root)
    dup_id = "inb_" + "a" * 24
    other_id = "inb_" + "b" * 24
    snap = {
        "id": dup_id,
        "kind": "issue",
        "source": "done-gate",
        "status": "open",
        "title": "dup",
        "body": "",
        "severity": "medium",
    }
    other = dict(snap, id=other_id, title="other")
    with open(path, "w", encoding="utf-8") as fh:
        for _ in range(8):
            fh.write(json.dumps(snap) + "\n")
        fh.write("{not-json\n")
        fh.write(json.dumps(other) + "\n")
        fh.write(json.dumps(snap) + "\n")

    result = inbox.drain_backlog(root)
    records = _jsonl_records(path)
    ids = [rec["id"] for rec in records]
    open_items = inbox.read_open_items(root)

    assert os.path.isfile(result["backup"])
    assert result["parse_fail"] == 1
    assert result["kept"] == 2
    assert ids.count(dup_id) == 1
    assert ids.count(other_id) == 1
    assert len(records) == 2
    assert set(open_items) == {dup_id, other_id}
    assert len(open_items) == 2
    assert all(rec.get("status") == "open" for rec in records)
