#!/usr/bin/env python3
"""inbox.py — stateful per-plan inbox items (design §5, M4).

The inbox at ``plans/_dashboard/inbox/inbox.jsonl`` is an append-only JSONL event
log: item-creation lines carry a full snapshot; resolve lines carry an ``event:
"resolve"`` with the same ``id``. The renderer folds by id — latest event per id
wins.

Before M4, done-gate items were created with random IDs on every Stop → the
11,140-item backlog. M4 replaces that with **stateful per-plan items**::

  * Deterministic id = ``hashlib.sha256(plan + "\0" + cause)[:24]``
    (prefixed ``"inb_"``).
  * ``upsert()`` — if an open item already exists for (plan, cause), return
    that id and do not append. A new id is appended only on first open.
  * ``resolve()`` — append a resolve event so the renderer marks it resolved.
  * ``drain_backlog()`` — rewrite the log to one current snapshot per unique
    id (last-event-wins). Skip corrupt lines. Backup is a gitignored sibling.

All writes to the host inbox file (META repo). planctl's off-9p events.jsonl
is the audit log; the inbox is the user-facing state.

Stdlib only.
"""
import hashlib
import json
import os
import time

from planctl import statedir

INBOX_BASENAME = "inbox.jsonl"
INBOX_SUBDIR = ("plans", "_dashboard", "inbox")

# ── helpers ──────────────────────────────────────────────────────────────────────

def _inbox_path(root):
    return os.path.join(root, *INBOX_SUBDIR, INBOX_BASENAME)


def _inbox_dir(root):
    return os.path.join(root, *INBOX_SUBDIR)


def hash_id(plan, cause):
    """Deterministic id — ``inb_`` + sha256(plan\\0cause)[:24].

    Two keys produce the same id ONLY when they refer to the same plan AND the
    same cause (review_missing / docs_missing / open_boxes). Because the inbox
    renderer folds by id, this makes the upsert stable across runs.
    """
    h = hashlib.sha256(
        ("%s\0%s" % (plan, cause)).encode("utf-8")
    ).hexdigest()[:24]
    return "inb_%s" % h


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ── read (folded view) ───────────────────────────────────────────────────────────

def read_open_items(root):
    """Fold inbox.jsonl → ``{id: item}`` for currently-open items.

    The latest event per id wins — a resolve event sets ``status: "resolved"``
    and the item is excluded from the returned dict.
    """
    path = _inbox_path(root)
    if not os.path.isfile(path):
        return {}

    items = {}
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            eid = rec.get("id", "")
            if not eid:
                continue

            if rec.get("event") == "resolve":
                if eid in items:
                    items[eid]["status"] = "resolved"
                    items[eid]["resolved"] = rec.get("resolved")
                    items[eid]["resolved_by"] = rec.get("resolved_by")
                    items[eid]["resolution_note"] = rec.get("resolution_note")
            else:
                items[eid] = rec

    return {k: v for k, v in items.items() if v.get("status") == "open"}


# ── write (upsert / resolve) ─────────────────────────────────────────────────────

def upsert(root, plan, cause, title, body, severity="medium", tags=None):
    """Upsert a stateful done-gate inbox item keyed by ``hash(plan, cause)``.

    If an open item already exists for this (plan, cause), return that id
    without appending — Stop-hook reconcile must not grow the log. Otherwise
    a new item is appended with ``auto_clearable=True``.

    Returns the item id.
    """
    path = _inbox_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    item_id = hash_id(plan, cause)
    open_items = read_open_items(root)
    existing = open_items.get(item_id)

    now = _now_iso()

    if existing:
        return item_id
    else:
        item = {
            "id": item_id,
            "kind": "issue",
            "source": "done-gate",
            "severity": severity,
            "title": title,
            "body": body,
            "awaits": None,
            "options": [],
            "ref": {
                "file": plan,
                "line": None,
                "commit": None,
                "plan": plan,
            },
            "recommended_action": None,
            "advice": "",
            "auto_clearable": True,
            "status": "open",
            "created": now,
            "updated": now,
            "resolved": None,
            "resolved_by": None,
            "resolution_note": None,
            "related_commits": [],
            "tags": tags or ["done-gate", cause],
            "seen_count": 1,
        }
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    return item_id


def resolve(root, plan, cause, note=None):
    """Resolve the open inbox item for (plan, cause).

    No-op if no open item exists for that key. Appends a resolve event so
    the renderer folds it to ``status: "resolved"``.
    """
    item_id = hash_id(plan, cause)
    open_items = read_open_items(root)

    if item_id not in open_items:
        return  # already resolved or never existed

    path = _inbox_path(root)
    now = _now_iso()

    resolve_event = {
        "id": item_id,
        "event": "resolve",
        "status": "resolved",
        "resolved": now,
        "resolved_by": "planctl-reconcile",
        "resolution_note": note or ("cause '%s' cleared" % cause),
        "updated": now,
    }
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(resolve_event, ensure_ascii=False) + "\n")


# ── backlog drain ────────────────────────────────────────────────────────────────

def drain_backlog(root):
    """Rewrite inbox.jsonl to one current snapshot per unique id.

    Last-event-wins fold: a later snapshot replaces an earlier one; a later
    resolve marks that snapshot resolved; a snapshot after a resolve reopens.
    Corrupt JSON lines are skipped (not rewritten) so a bad line cannot zero
    the open count. The original file is renamed to a gitignored ``.bak-drain-*``
    sibling, then the compact log is written via ``os.replace``.

    Returns ``{kept, overlord, parse_fail, backup}``.
    """
    path = _inbox_path(root)
    if not os.path.isfile(path):
        return {"kept": 0, "overlord": 0, "parse_fail": 0, "backup": ""}

    items = {}
    parse_fail_count = 0

    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                parse_fail_count += 1
                continue

            eid = rec.get("id") or ""
            if not eid:
                continue

            if rec.get("event") == "resolve":
                if eid in items:
                    folded = dict(items[eid])
                    folded["status"] = rec.get("status", "resolved")
                    folded["resolved"] = rec.get("resolved")
                    folded["resolved_by"] = rec.get("resolved_by")
                    folded["resolution_note"] = rec.get("resolution_note")
                    folded["updated"] = rec.get("updated", folded.get("updated"))
                    items[eid] = folded
                else:
                    items[eid] = rec
                continue

            items[eid] = rec

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = path + ".bak-drain-" + stamp
    tmp_path = path + ".tmp-drain-" + stamp

    os.replace(path, backup_path)
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            for eid in sorted(items):
                fh.write(json.dumps(items[eid], ensure_ascii=False) + "\n")
        os.replace(tmp_path, path)
    except Exception:
        if os.path.isfile(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        if not os.path.isfile(path) and os.path.isfile(backup_path):
            os.replace(backup_path, path)
        raise

    overlord_count = sum(
        1 for rec in items.values() if rec.get("source") == "overlord"
    )
    return {
        "kept": len(items),
        "overlord": overlord_count,
        "parse_fail": parse_fail_count,
        "backup": backup_path,
    }


# ── planctl verb entry point ─────────────────────────────────────────────────────

def cmd_inbox_drain(args):
    """``planctl inbox drain`` — drain the done-gate backlog (one-shot)."""
    root = statedir.project_root()
    result = drain_backlog(root)
    if getattr(args, "json", False):
        print(json.dumps(result))
    else:
        print("inbox drain: %d unique ids kept (was backlog)" % result["kept"])
        print("  overlord kept: %d" % result["overlord"])
        print("  parse-fail skipped: %d" % result["parse_fail"])
        print("  backup: %s" % result["backup"])
    return 0
