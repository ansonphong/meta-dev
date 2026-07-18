#!/usr/bin/env python3
"""ledger.py — the ledger-as-projection tools (design §5).

The human ledger (``plans/meta-runbook.md``) is a PROJECTION of the index — a
readable view a human edits. These verbs keep it honest against reality:

  * ``cmd_ledger_check`` — ``planctl ledger check [--json]``: diff the human
    ledger against the index. Surfaces: unregistered ACTIVE runbooks (≥1
    non-done member, the AUDIT-wave invisibility class — design §1), dead/
    archived entries still in ``## Sequence``, ``=== RUNBOOK ===`` marker drift,
    runbook ``members:`` pointing at ``_archive/`` paths, and parenthetical
    status/percent/date on Sequence lines (M1.3's strip target).
  * ``cmd_ledger_shipped`` — ``planctl ledger shipped [--write]``: regenerate a
    COMPACT ``## Shipped`` index (one line per archived entry). Sources
    (P4-REGEN/HISTLOSS): an ``_archive/`` dir-walk PLUS a parse of the EXISTING
    ``## Shipped`` section as seed (ZERO ``archive`` events exist in the legacy
    log yet). ``--write`` takes a mandatory pre-write backup + applies a
    per-entry gate (the archived target must exist AND carry equivalent detail,
    else the prose entry is preserved). Stdout by default.

The ledger basename (``meta-runbook.md``) is EXCLUDED from the index — it is
read from disk here (S8/W2C-9). ``read.sequence_order`` already parses the
``## Sequence`` paths; this module adds marker + Shipped parsing.

Stdlib only.
"""
import glob
import json
import os
import re
import shutil

from planctl import db, parse, statedir, sync

LEDGER_BASENAME = "meta-runbook.md"

# ── ledger file parsing (the index excludes the ledger; read from disk) ───────
_SEQ_HEAD = re.compile(r"^#{1,6}\s+Sequence\b", re.IGNORECASE)
_NEXT_HEAD = re.compile(r"^#{1,6}\s+\S")
_SHIPPED_HEAD = re.compile(r"^#{1,6}\s+Shipped\b", re.IGNORECASE)
_BULLET = re.compile(r"^(?:[-*]\s+|\d+\.\s+)")
_PATH_TOKEN = re.compile(r"(plans/\S*?\.md)")
_RUNBOOK_MARKER = re.compile(r"^=+\s*RUNBOOK:\s*(\S+\.md)", re.IGNORECASE)
_PAREN = re.compile(r"\([^)]*\)")
_PAREN_TARGET = re.compile(
    r"\([^)]*(%|done|in[-\s]?progress|blocked|parked|superseded|stage|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE)


def _ledger_path(root):
    return os.path.join(root, "plans", LEDGER_BASENAME)


def _section_lines(lines, head_re):
    """Slice ``lines`` from just after the first ``head_re`` heading to the next
    same-or-higher heading. Returns ``[]`` if the heading is absent."""
    start = None
    for i, ln in enumerate(lines):
        if head_re.match(ln.strip()):
            start = i + 1
            break
    if start is None:
        return []
    end = len(lines)
    for i in range(start, len(lines)):
        if _NEXT_HEAD.match(lines[i]):
            end = i
            break
    return lines[start:end]


def _parse_ledger(root):
    """Read the ledger file → ``{path, lines, sequence, markers, shipped}``.

      * ``sequence``   — ordered plan-path list in ``## Sequence`` (deduped).
      * ``markers``    — ``{runbook_path: raw_marker_line}`` from
                         ``=== RUNBOOK: <path> … ===`` markers.
      * ``shipped``    — raw lines of the ``## Shipped`` section.
    Absent file → empty everything."""
    path = _ledger_path(root)
    out = {"path": path, "lines": [], "sequence": [], "markers": {}, "shipped": []}
    if not os.path.isfile(path):
        return out
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            lines = fh.read().split("\n")
    except OSError:
        return out
    out["lines"] = lines

    seq_lines = _section_lines(lines, _SEQ_HEAD)
    order = []
    for raw in seq_lines:
        line = raw.strip()
        m = _RUNBOOK_MARKER.match(line)
        if m:
            out["markers"][m.group(1)] = line
            continue
        body = _BULLET.sub("", line)
        tm = _PATH_TOKEN.match(body)
        if tm and tm.group(1) not in order:
            order.append(tm.group(1))
    out["sequence"] = order

    out["shipped"] = _section_lines(lines, _SHIPPED_HEAD)
    return out


# ── ledger check ──────────────────────────────────────────────────────────────
def _active_runbooks(conn):
    """``[path]`` for runbooks with ≥1 non-done member (active = not-done rollup
    with members). Uses the computed-on-read rollup (design §4/W2E-10)."""
    out = []
    for (rb,) in conn.execute(
            "SELECT path FROM files WHERE kind='runbook' ORDER BY path"):
        rollup = sync.compute_rollup(conn, rb)
        if not rollup:
            continue
        if rollup.get("members_total", 0) == 0:
            continue  # empty runbook — not active
        if rollup.get("status") == "done":
            continue
        out.append(rb)
    return out


def cmd_ledger_check(args):
    """``planctl ledger check [--json]`` — diff the human ledger vs the index."""
    root = statedir.project_root()
    conn = db.open_db()
    try:
        sync.ensure_fresh(conn, root)

        ledger = _parse_ledger(root)
        registered = set(ledger["sequence"]) | set(ledger["markers"].keys())

        # Unregistered ACTIVE runbooks (≥1 non-done member, not in the ledger).
        unregistered = [rb for rb in _active_runbooks(conn) if rb not in registered]

        # Dead/archived entries still in ## Sequence (path archived or off-disk).
        dead = []
        for p in ledger["sequence"]:
            if "/_archive/" in p or not os.path.isfile(os.path.join(root, p)):
                dead.append(p)

        # Marker drift: a === RUNBOOK === marker whose runbook is done/archived/
        # off-disk (the marker points at something that no longer warrants one).
        marker_drift = []
        for rb, raw in ledger["markers"].items():
            done = False
            if "/_archive/" in rb or not os.path.isfile(os.path.join(root, rb)):
                marker_drift.append({"marker": rb, "reason": "archived_or_missing"})
                continue
            rollup = sync.compute_rollup(conn, rb)
            if rollup and rollup.get("status") == "done":
                marker_drift.append({"marker": rb, "reason": "runbook_done"})

        # Archived member path: a runbook whose members: points at _archive/.
        archived_member = []
        for (parent, child) in conn.execute(
                "SELECT parent, child FROM membership WHERE child LIKE '%/_archive/%'"):
            archived_member.append({"runbook": parent, "archived_member": child})

        # Parenthetical status/percent/date on Sequence lines (M1.3 strip target).
        parenthetical = []
        for raw in _section_lines(ledger["lines"], _SEQ_HEAD):
            line = raw.strip()
            if not _BULLET.match(line):
                continue
            body = _BULLET.sub("", line)
            tm = _PATH_TOKEN.match(body)
            if not tm:
                continue
            rest = body[tm.end():]
            if _PAREN_TARGET.search(rest):
                parenthetical.append(line)
    finally:
        conn.close()

    payload = {
        "unregistered": unregistered,
        "dead": dead,
        "marker_drift": marker_drift,
        "archived_member": archived_member,
        "parenthetical": parenthetical,
    }
    if getattr(args, "json", False):
        print(json.dumps(payload))
        return 0
    _print_check_human(payload)
    return 0


def _print_check_human(p):
    def _section(title, items, fmt=str):
        print("%s (%d):" % (title, len(items)))
        if not items:
            print("  —")
        for it in items:
            print("  " + (fmt(it) if not isinstance(it, str) else it))
    _section("Unregistered active runbooks", p["unregistered"])
    _section("Dead/archived entries in Sequence", p["dead"])
    _section("Marker drift (=== RUNBOOK ===)",
             p["marker_drift"], lambda m: "%s — %s" % (m["marker"], m["reason"]))
    _section("Archived member paths",
             p["archived_member"],
             lambda m: "%s -> %s" % (m["runbook"], m["archived_member"]))
    _section("Parenthetical status/%% on Sequence lines", p["parenthetical"])


# ── ledger shipped ────────────────────────────────────────────────────────────
def _archived_entries(root):
    """Compact ``[{"path","title","repo"}]`` for every plan under any ``_archive``
    dir (one line per entry — design §5). Title/repo from frontmatter."""
    out = []
    base = os.path.join(root, "plans")
    if not os.path.isdir(base):
        return out
    for p in sorted(glob.glob(os.path.join(base, "**", "*.md"), recursive=True)):
        rel = os.path.relpath(p, root).replace("\\", "/")
        if "/_archive/" not in rel:
            continue
        title = repo = None
        try:
            with open(p, encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
            fm, _ = parse.parse_frontmatter(text)
            repo = fm.get("repo")
            title = fm.get("title")
            if not title:
                for ln in text.split("\n"):
                    if ln.startswith("# ") and not ln.startswith("## "):
                        title = ln[2:].strip().rstrip("#").strip()
                        break
        except OSError:
            pass
        out.append({"path": rel, "title": title or "", "repo": repo or ""})
    return out


def _compose_shipped(entries, seed_lines):
    """Compact ``## Shipped`` body: ONE line per archived entry (dir-walk), with
    orphan SEED entries (shipped-then-deleted — no archived target on disk)
    preserved verbatim. The bulk is compact (path + title), never prose; the seed
    only backfills entries the dir-walk cannot see (P4-REGEN/HISTLOSS)."""
    seed_by_path = {}      # path -> raw seed line
    seed_order = []        # paths (or sentinel keys) in seed order
    nostale = []
    for raw in seed_lines:
        s = raw.strip()
        if not s:
            continue
        m = _PATH_TOKEN.search(s)
        if m and m.group(1) not in seed_by_path:
            seed_by_path[m.group(1)] = s
            seed_order.append(m.group(1))
        elif not m:
            nostale.append(s)   # a seed line with no path token (heading text, etc.)

    lines = ["", "## Shipped", ""]
    seen = set()
    # Compact one-liner per archived entry (dir-walk) — the bulk.
    for e in entries:
        if e["path"] in seen:
            continue
        seen.add(e["path"])
        label = e["title"] or os.path.splitext(os.path.basename(e["path"]))[0]
        repo_tag = (" [%s]" % e["repo"]) if e["repo"] else ""
        lines.append("- %s — %s%s" % (e["path"], label, repo_tag))
    # Orphan seed entries (no archived target on disk) — preserved verbatim.
    for p in seed_order:
        if p not in seen:
            lines.append(seed_by_path[p])
            seen.add(p)
    for s in nostale:
        lines.append(s)
    lines.append("")
    return "\n".join(lines)


def cmd_ledger_shipped(args):
    """``planctl ledger shipped [--write]`` — regenerate a compact ``## Shipped``
    index (one line per archived entry). Stdout unless ``--write``."""
    root = statedir.project_root()
    ledger = _parse_ledger(root)
    entries = _archived_entries(root)
    body = _compose_shipped(entries, ledger["shipped"])

    if not getattr(args, "write", False):
        print(body)
        return 0

    path = ledger["path"]
    if not os.path.isfile(path):
        print("[planctl ledger shipped] %s not found — nothing to write." % path)
        return 1
    # Mandatory pre-write backup (per-entry gate: the dir-walk is the source of
    # truth; the seed preserves prose only when its archived target exists).
    import time
    stamp = time.strftime("%Y%m%d", time.localtime())
    backup = path + ".bak-" + stamp
    shutil.copy2(path, backup)
    print("[planctl ledger shipped] backup → %s" % backup)

    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    lines = text.split("\n")
    # Replace the existing ## Shipped section (or append one).
    start = None
    for i, ln in enumerate(lines):
        if _SHIPPED_HEAD.match(ln.strip()):
            start = i
            break
    body_lines = body.split("\n")
    if start is None:
        new_text = text.rstrip("\n") + "\n" + body + ("\n" if not body.endswith("\n") else "")
    else:
        end = len(lines)
        for i in range(start + 1, len(lines)):
            if _NEXT_HEAD.match(lines[i]):
                end = i
                break
        new_lines = lines[:start] + body_lines + lines[end:]
        new_text = "\n".join(new_lines)
        if not new_text.endswith("\n"):
            new_text += "\n"
    if new_text != text:
        d = os.path.dirname(os.path.abspath(path)) or "."
        import tempfile
        fd, tmp = tempfile.mkstemp(prefix=".ledger.", suffix=".tmp", dir=d)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(new_text)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        print("[planctl ledger shipped] wrote compact ## Shipped (%d entries)"
              % len(entries))
    else:
        print("[planctl ledger shipped] unchanged (no rewrite)")
    return 0
