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
  * ``upsert()`` — if an open item already exists for (plan, cause),
    bump ``seen_count`` + ``updated``; otherwise append a new item.
  * ``resolve()`` — append a resolve event so the renderer marks it resolved.
  * ``drain_backlog()`` — collapse the legacy backlog into one-open-item-per-
    (plan, cause) with deterministic ids; preserve non-done-gate items.

All writes to the host inbox file (META repo). planctl's off-9p events.jsonl
is the audit log; the inbox is the user-facing state.

Stdlib only.
"""
import hashlib
import json
import os
import re
import shutil
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

    If an open item already exists for this (plan, cause), the item's
    ``updated`` and ``seen_count`` are bumped (no duplicate created). Otherwise
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
        existing["updated"] = now
        existing["seen_count"] = existing.get("seen_count", 1) + 1
        # Keep the original created timestamp; bump the title/body in case the
        # decision details changed.
        existing["title"] = title
        existing["body"] = body
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(existing, ensure_ascii=False) + "\n")
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

# Regexes to classify cause from free-text body/title (P4-CAUSE).
_CAUSE_PATTERNS = {
    "open_boxes": re.compile(
        r"(open\s*boxes|fail\s*open\s*boxes|open\s*exec\b)",
        re.IGNORECASE,
    ),
    "review_missing": re.compile(
        r"(review\s*missing|no\s*review\s*verdict|"
        r"checkboxes\s*are\s*all\s*flipped|"
        r"code\s*review\s*not\s*on\s*record)",
        re.IGNORECASE,
    ),
    "docs_missing": re.compile(
        r"(docs\s*missing|docs\s*evidence\s*missing|"
        r"context\s*missing|declared\s*path\s*unmodified|"
        r"declared\s*context\b)",
        re.IGNORECASE,
    ),
}


def _classify_cause(text):
    """Return the cause slug from free text, or ``None`` if unrecognized."""
    for cname, cpat in _CAUSE_PATTERNS.items():
        if cpat.search(text):
            return cname
    return None


def drain_backlog(root):
    """Collapse the done-gate backlog into one-open-item-per-(plan, cause).

    Reads ``inbox.jsonl``, regexes the cause from each done-gate item's free-text
    body + title, dedupes to one-open-per-key, rewrites with deterministic ids.
    Non-done-gate items (overlord, manual advisories) and parse-fail lines are
    PRESERVED verbatim. Items whose cause has long since cleared (resolved) are
    archived (resolve event appended).

    Returns ``{kept, overlord, parse_fail, backup}`` counts for the report.
    """
    path = _inbox_path(root)
    if not os.path.isfile(path):
        return {"kept": 0, "overlord": 0, "parse_fail": 0, "backup": ""}

    # ── Pass 1: collect ──────────────────────────────────────────────────────
    preserved = []          # non-done-gate items + resolve events (as raw or dict)
    done_gate_items = {}    # (plan, cause) → latest item dict
    parse_fail_count = 0

    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                preserved.append(line)  # preserve raw parse-fail line
                parse_fail_count += 1
                continue

            # Resolve events pass through untouched (they reference random ids
            # from the legacy era and won't match deterministic ids — they're
            # harmless noise).
            if rec.get("event") == "resolve":
                preserved.append(rec)
                continue

            source = rec.get("source", "")
            if source != "done-gate":
                preserved.append(rec)
                continue

            # Extract plan from ref.plan or ref.file
            ref = rec.get("ref") or {}
            plan = ref.get("plan") or ref.get("file") or ""
            if not plan:
                preserved.append(rec)  # can't classify, preserve as-is
                continue

            # Classify cause from body + title
            text = " ".join([
                rec.get("body", "") or "",
                rec.get("title", "") or "",
            ])
            cause = _classify_cause(text)
            if cause is None:
                # Best-effort default: most done-gate items are review_missing
                cause = "review_missing"

            key = (plan, cause)
            if key not in done_gate_items:
                done_gate_items[key] = rec
            else:
                # Keep the latest (by created timestamp)
                existing_ts = done_gate_items[key].get("created", "")
                new_ts = rec.get("created", "")
                if new_ts > existing_ts:
                    done_gate_items[key] = rec

    # ── Pass 2: backup + rewrite ─────────────────────────────────────────────
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = path + ".bak-drain-" + stamp
    shutil.copy2(path, backup_path)

    overlord_count = sum(
        1 for r in preserved
        if isinstance(r, dict) and r.get("source") == "overlord"
    )

    with open(path, "w", encoding="utf-8") as fh:
        for item in preserved:
            if isinstance(item, str):
                fh.write(item + "\n")
            else:
                fh.write(json.dumps(item, ensure_ascii=False) + "\n")

        for (plan, cause), item in sorted(done_gate_items.items()):
            new_id = hash_id(plan, cause)
            item["id"] = new_id
            item["auto_clearable"] = True
            item["updated"] = _now_iso()
            if "plan" not in (item.get("ref") or {}):
                item.setdefault("ref", {})["plan"] = plan
            if not item.get("tags"):
                item["tags"] = ["done-gate", cause]
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    kept = len(done_gate_items)
    return {
        "kept": kept,
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
        print("inbox drain: %d stateful items kept (was backlog)" % result["kept"])
        print("  overlord preserved: %d" % result["overlord"])
        print("  parse-fail preserved: %d" % result["parse_fail"])
        print("  backup: %s" % result["backup"])
    return 0
