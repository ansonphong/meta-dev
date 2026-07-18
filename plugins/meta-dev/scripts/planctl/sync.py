#!/usr/bin/env python3
"""sync.py — the freshness engine (design §3.3; invariants I3, I4).

Markdown stays git truth; this module keeps the disposable SQLite read-model
in sync with it. THREE reindex modes:

  * ``--full``      drop every derived row, reparse every allowlisted
                     ``plans/**/*.md``, recompute derived fields, write
                     ``meta.derive_v = DERIVE_V`` (the mixed-semantics guard).
  * default         INCREMENTAL: ONE ``git status --porcelain -uall -z`` (dirty
                     tree) ∪ ``git diff --name-status -z <watermark>..HEAD``
                     (committed since ``meta.last_commit``) → candidate set;
                     reparse changed files only (sha1 short-circuit, mtime hint-
                     only), upsert, recompute ancestor-runbook rollups
                     transitively to fixpoint (cycle-guarded).
  * ``--file F``    skip git; reindex ONE file (the PostToolUse path).

Trust model: sha1 short-circuit (unchanged content → skip reparse). mtime is a
HINT only (unreliable on 9p); sha decides (W2A-5: sha-based, NOT mtime — a hand
Edit changes sha even with unchanged mtime).

Malformed frontmatter is NEVER silently dropped (W2A-5): an unparseable file
→ a ``files`` row with ``parse_err`` set (sync does NOT skip it, which would
hide the count). ``_archive/`` is excluded ENTIRELY (R7/W2C-3 — archived never
parsed/derived/counted).

``sync_one(path) -> rebuilt_runbooks`` is the shared post-mutation reindex every
0d verb calls after its MD write (so the index is hot post-mutation). The
``rebuilt_runbooks`` return is the sha-based dirty-set source for ``reconcile``
(§3.7) — NOT the event log (events miss hand edits = the disease).

Membership population (S5) happens here: ``parse`` provides ``members:``; sync
inserts ``membership(parent, child, ord, child_kind)`` rows (child path
normalized project-root-relative, G-IMP6). The recursive rollup CTE + the
``runbook`` verbs live in 0e; ``compute_rollup`` below is the 0c read-time
recursive walker (manual descent + cycle guard; DISTINCT diamond-dedup + the
SQL CTE are 0e's — deferred, noted in the phase report).

Stdlib only.
"""
import glob
import hashlib
import json
import os
import re
import subprocess
import time

from planctl import db, derive, parse, statedir

# ── index allowlist (mirrors plan-index.walk_candidates, BUT re-includes
#    _runbook-*.md as a first-class runbook member — plan-index treats those as
#    noise because runbook-render.py handled them separately; planctl unifies).
_EXCLUDE_DIRS = ("_archive", "_future", "_research", "_dashboard")
_EXCLUDE_BY_NAME = (
    "plans/exec-order-2026-06-26.md",
    "plans/STATUS.md",
    "plans/exec-order.md",
)
_SENSITIVE = "plans/exec-order-2026-06-26.md"

_DATED = re.compile(r"^\d{4}-\d{2}-\d{2}-.*\.md$")
_RUNBOOK_FILE = re.compile(r"^_runbook-.*\.md$", re.IGNORECASE)
# plan-index NOISE minus ``_runbook-.*\.md`` (re-included above as a runbook).
_NOISE = re.compile(
    r"^(phase-.*\.md|design\.md|handoff.*|.*-config\.md|\.loop-gap-config\.md"
    r"|_exec-order-.*\.md)$",
    re.IGNORECASE,
)


def is_indexed(rel):
    """True if ``rel`` (repo-relative, forward-slashed) is an index candidate.

    Mirrors ``plan-index.is_allowlisted`` + the dir/name exclusions from
    ``walk_candidates``, then RE-INCLUDES ``_runbook-*.md`` (a runbook, not
    noise — phase spec). ``_archive/`` etc. are excluded entirely (R7/W2C-3).
    """
    if not rel.endswith(".md"):
        return False
    parts = rel.split("/")
    if any(d in _EXCLUDE_DIRS for d in parts):
        return False
    if rel == _SENSITIVE or rel in _EXCLUDE_BY_NAME:
        return False
    base = parts[-1]
    if _NOISE.match(base):
        return False
    if "master-plan" in base:
        return True
    if base.startswith("00-"):
        return True
    if _DATED.match(base):
        return True
    if _RUNBOOK_FILE.match(base):
        return True
    return False


# ── path normalization ────────────────────────────────────────────────────────
def _norm_member(p):
    """Normalize a member/edge path: strip whitespace, leading ``./`` and ``/``.

    project-root-relative (G-IMP6). Non-strings → ''."""
    if not isinstance(p, str):
        return ""
    p = p.strip()
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def _clean_git_path(p):
    """A path from ``git -z`` output is already repo-relative + forward-slashed
    (and unquoted thanks to ``-z``); just normalize stray backslashes/whitespace."""
    return p.replace("\\", "/").strip()


def _normalize_arg_path(arg, root):
    """Resolve a user-supplied ``--file``/``status`` path arg to repo-relative."""
    p = arg.replace("\\", "/")
    ap = os.path.abspath(p) if os.path.isabs(p) else os.path.abspath(os.path.join(root, p))
    rel = os.path.relpath(ap, root).replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


# ── git helpers (cwd-independent: every call is ``git -C <root> …``) ───────────
def _git(root, *git_args):
    return subprocess.run(
        ["git", "-C", root, *git_args], capture_output=True,
    )


def _head_sha(root):
    out = _git(root, "rev-parse", "HEAD")
    if out.returncode != 0:
        return None
    sha = out.stdout.decode("utf-8", "replace").strip()
    return sha or None


def _cat_file_exists(root, sha):
    """Watermark guard (W2C-4): True iff ``sha`` is still a resolvable object
    (not GC'd). Used to decide whether the diff watermark is safe to use."""
    if not sha:
        return False
    return _git(root, "cat-file", "-e", "%s^{commit}" % sha).returncode == 0


def _parse_porcelain_z(data):
    """Yield ``(xy, [paths])`` from ``git status --porcelain -z`` (bytes).

    With ``-z`` each record is NUL-terminated; ``XY <path>\0``, and for renames/
    copies TWO NUL-terminated records: ``XY <new>\0<old>\0`` (destination first,
    then origin; NO tab). Walk by index so renames consume the next record."""
    recs = [r for r in data.split(b"\0") if r]
    out = []
    i = 0
    n = len(recs)
    while i < n:
        rec = recs[i]
        xy = rec[:2].decode("utf-8", "replace")
        path = rec[3:].decode("utf-8", "replace")  # skip "XY " (2 status + 1 space)
        if "R" in xy or "C" in xy:
            origin = recs[i + 1].decode("utf-8", "replace") if i + 1 < n else ""
            out.append((xy, [origin, path]))
            i += 2
        else:
            out.append((xy, [path]))
            i += 1
    return out


def _parse_diff_namestatus_z(data):
    """Yield ``(status, [paths])`` from ``git diff --name-status -z`` (bytes).

    Tokens are NUL-separated: a status token, then 1 path (A/M/D/...) or 2 paths
    (R/C: old, new)."""
    tokens = data.split(b"\0")
    out = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if not tok:
            i += 1
            continue
        status = tok.decode("utf-8", "replace")
        rename = status.startswith("R") or status.startswith("C")
        if rename:
            old = tokens[i + 1].decode("utf-8", "replace") if i + 1 < n else ""
            new = tokens[i + 2].decode("utf-8", "replace") if i + 2 < n else ""
            out.append((status, [old, new]))
            i += 3
        else:
            path = tokens[i + 1].decode("utf-8", "replace") if i + 1 < n else ""
            out.append((status, [path]))
            i += 2
    return out


def _porcelain_paths(root):
    """Uncommitted candidate paths (dirty working tree), allowlist-unfiltered —
    the caller decides upsert-vs-delete per path."""
    out = _git(root, "status", "--porcelain", "-uall", "-z", "--", "plans/")
    paths = set()
    if out.returncode != 0:
        return paths
    for _xy, plist in _parse_porcelain_z(out.stdout):
        for p in plist:
            if p:
                paths.add(_clean_git_path(p))
    return paths


def _diff_paths(root, watermark):
    """Committed-since-watermark candidate paths (renames give old+new)."""
    out = _git(root, "diff", "--name-status", "-z",
               "%s..HEAD" % watermark, "--", "plans/")
    paths = set()
    if out.returncode != 0:
        return paths
    for _status, plist in _parse_diff_namestatus_z(out.stdout):
        for p in plist:
            if p:
                paths.add(_clean_git_path(p))
    return paths


def _incremental_candidates(conn, root):
    """Union of porcelain (uncommitted) ∪ diff-since-watermark (committed)."""
    cands = set()
    cands |= _porcelain_paths(root)
    wm = conn.execute(
        "SELECT value FROM meta WHERE key='last_commit'").fetchone()
    if wm and wm[0] and _cat_file_exists(root, wm[0]):
        cands |= _diff_paths(root, wm[0])
    return cands


# ── Sequence-registered paths (the oracle tracks Sequence paths directly) ──────
_SEQ_HEAD = re.compile(r"^#{1,6}\s+Sequence\b", re.IGNORECASE)
_SEQ_NEXT_HEAD = re.compile(r"^#{1,6}\s+\S")
_SEQ_BULLET = re.compile(r"^(?:[-*]\s+|\d+\.\s+)")
_SEQ_PATH = re.compile(r"(plans/\S*?\.md)")


def _sequence_paths(root):
    """Sequence-registered plan paths from ``plans/meta-runbook.md ## Sequence``.

    The oracle (``plan-index.py``) reads Sequence paths DIRECTLY via
    ``read_plan_file`` regardless of the filename allowlist — so a Sequence-
    registered file is TRACKED even when ``is_indexed`` would skip it (e.g. a
    ``SEED.md``). For parity (R7/BC7), sync unions these into the ``--full``
    ground set. Archived Sequence entries (``/_archive/``) are excluded (parity
    excludes archived from both sides). Local parse (mirrors ``read.sequence_order``;
    not imported from read to avoid a read→sync cycle)."""
    ledger = os.path.join(root, "plans", "meta-runbook.md")
    if not os.path.isfile(ledger):
        return []
    try:
        with open(ledger, encoding="utf-8", errors="ignore") as fh:
            lines = fh.read().split("\n")
    except OSError:
        return []
    start = None
    for i, line in enumerate(lines):
        if _SEQ_HEAD.match(line.strip()):
            start = i + 1
            break
    if start is None:
        return []
    end = len(lines)
    for i in range(start, len(lines)):
        if _SEQ_NEXT_HEAD.match(lines[i]):
            end = i
            break
    order = []
    for raw in lines[start:end]:
        body = _SEQ_BULLET.sub("", raw.strip())
        m = _SEQ_PATH.match(body)
        if m and m.group(1) not in order:
            order.append(m.group(1))
    return [p for p in order if "/_archive/" not in p]


def _walk_indexed(root):
    """Allowlisted ``plans/**/*.md`` (the ``--full`` ground set), UNIONED with
    Sequence-registered paths (tracked regardless of filename allowlist — parity
    with the oracle)."""
    out = []
    base = os.path.join(root, "plans")
    if os.path.isdir(base):
        for p in sorted(glob.glob(os.path.join(base, "**", "*.md"), recursive=True)):
            rel = os.path.relpath(p, root).replace("\\", "/")
            if is_indexed(rel):
                out.append(rel)
    for p in _sequence_paths(root):
        if p not in out:
            out.append(p)
    return out


# ── title helper ───────────────────────────────────────────────────────────────
_H1_RE = re.compile(r"^#\s+(.+?)\s*#*\s*$")


def _derive_title(text):
    """First H1 heading text, else None."""
    for line in text.splitlines():
        m = _H1_RE.match(line)
        if m:
            return m.group(1).strip()
    return None


# ── row writers ────────────────────────────────────────────────────────────────
def _delete_plan_rows(conn, rel):
    """Drop every row keyed by ``rel`` (plans/tasks/edges/membership-as-parent-
    or-child/files). No ghost rows / ghost rollups (W2C-1/W2C-3)."""
    conn.execute("DELETE FROM tasks WHERE plan_path=?", (rel,))
    conn.execute("DELETE FROM edges WHERE src=? OR dst=?", (rel, rel))
    conn.execute("DELETE FROM membership WHERE parent=? OR child=?", (rel, rel))
    conn.execute("DELETE FROM plans WHERE path=?", (rel,))
    conn.execute("DELETE FROM files WHERE path=?", (rel,))


def _upsert_file(conn, root, rel, force_reparse=False):
    """Parse + upsert one file's rows (files/plans/tasks/edges). Membership is
    populated separately (``_populate_membership``) so child_kind resolves after
    all files are indexed.

    Returns True if the file was reparsed (sha changed or ``force_reparse``),
    False if sha-unchanged (short-circuit). Malformed → ``parse_err`` row, NOT
    dropped (W2A-5). Never raises."""
    full_path = os.path.join(root, rel)
    try:
        with open(full_path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return False
    sha = hashlib.sha1(raw).hexdigest()

    if not force_reparse:
        existing = conn.execute(
            "SELECT sha1 FROM files WHERE path=?", (rel,)).fetchone()
        if existing and existing[0] == sha:
            return False  # sha short-circuit (W2A-5)

    text = raw.decode("utf-8", "ignore")
    try:
        st = os.stat(full_path)
        mtime_ns, size = st.st_mtime_ns, st.st_size
    except OSError:
        mtime_ns = size = None

    fm, _raw_status = parse.parse_frontmatter(text)
    tasks, perr = parse.parse_tasks(text)
    td, tt, ho, ht, rd, rt = parse.count_split(tasks)
    kind = parse.kind_of(text, fm, rel)
    parse_err = fm.get("parse_err") or perr

    conn.execute(
        "INSERT OR REPLACE INTO files(path,kind,sha1,mtime_ns,size,parse_err) "
        "VALUES(?,?,?,?,?,?)",
        (rel, kind, sha, mtime_ns, size, parse_err),
    )

    # tasks (replace — boxes may have been added/removed/flipped)
    conn.execute("DELETE FROM tasks WHERE plan_path=?", (rel,))
    for t in tasks:
        conn.execute(
            "INSERT OR REPLACE INTO tasks(plan_path,tid,line_no,checked,"
            "human_verify,section,text) VALUES(?,?,?,?,?,?,?)",
            (rel, t.tid, t.line_no, 1 if t.checked else 0,
             1 if t.human_verify else 0, t.section, t.text),
        )

    # plans row (replace). derived_status stored for PLAN files only; runbook
    # status is computed-on-read (§4) → NULL here.
    ctx = fm.get("context")
    docs = fm.get("docs")
    context_json = json.dumps(ctx) if isinstance(ctx, list) else None
    docs_json = json.dumps(docs) if isinstance(docs, list) else None
    if kind == "plan":
        dstatus, drift = derive.derive_plan(fm, td, tt)
    else:
        dstatus, drift = None, False
    conn.execute(
        "INSERT OR REPLACE INTO plans(path,repo,stage,override,note,why,title,"
        "tasks_done,tasks_total,human_open,human_total,raw_done,raw_total,drift,"
        "context_json,docs_json,derived_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (rel, fm.get("repo"), fm.get("stage"), fm.get("override"), fm.get("note"),
         fm.get("why"), _derive_title(text), td, tt, ho, ht, rd, rt,
         1 if drift else 0, context_json, docs_json, dstatus),
    )

    # edges (depends/blocks — replace)
    conn.execute("DELETE FROM edges WHERE src=?", (rel,))
    for d in (fm.get("depends") or []):
        child = _norm_member(d)
        if child:
            conn.execute("INSERT INTO edges(src,dst,kind) VALUES(?,?,?)",
                         (rel, child, "depends"))
    for b in (fm.get("blocks") or []):
        child = _norm_member(b)
        if child:
            conn.execute("INSERT INTO edges(src,dst,kind) VALUES(?,?,?)",
                         (rel, child, "blocks"))
    return True


def _populate_membership(conn, root, rel):
    """Insert ``membership`` rows for a runbook's declared ``members:`` (S5).

    child_kind resolves from the now-populated ``files`` table (plans indexed
    before this pass); falls back to 'plan' if the member is not (yet) indexed.
    Re-reads the file for ``members:`` (cheap; a handful of runbooks per sync)."""
    frow = conn.execute(
        "SELECT kind FROM files WHERE path=?", (rel,)).fetchone()
    if not frow or frow[0] != "runbook":
        return
    full_path = os.path.join(root, rel)
    try:
        with open(full_path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return
    fm, _ = parse.parse_frontmatter(raw.decode("utf-8", "ignore"))
    members = fm.get("members") or []
    conn.execute("DELETE FROM membership WHERE parent=?", (rel,))
    for ord_i, m in enumerate(members):
        child = _norm_member(m)
        if not child:
            continue
        krow = conn.execute(
            "SELECT kind FROM files WHERE path=?", (child,)).fetchone()
        child_kind = krow[0] if krow else "plan"
        conn.execute(
            "INSERT OR REPLACE INTO membership(parent,child,ord,child_kind) "
            "VALUES(?,?,?,?)",
            (rel, child, ord_i, child_kind),
        )


# ── runbook rollup (delegates to runbook.py/0e — the canonical recursive CTE) ──
def compute_rollup(conn, path, _visited=None):
    """Delegate to ``runbook.compute_rollup`` (0e absorbed the 0c read-time
    walker into the canonical recursive-CTE rollup with DISTINCT diamond-dedup +
    path-guarded cycle termination). Kept here as the call-site every 0c reader
    (``read.cmd_status``/``_active_arcs``/``_build_brief`` + ``_rollup_sig``)
    already targets; the signature + return contract (None for not-a-runbook)
    are unchanged. Lazy import avoids a top-level cycle (runbook imports sync
    inside its verbs only)."""
    from planctl import runbook
    return runbook.compute_rollup(conn, path, _visited)


def _rollup_sig(conn, path):
    """Hashable signature of ``compute_rollup(conn, path)`` (or None). The
    rebuilt-set detector diffs these before/after an upsert (sha-based)."""
    r = compute_rollup(conn, path)
    if r is None:
        return None
    return (r.get("members_done"), r.get("members_total"), r.get("tasks_done"),
            r.get("tasks_total"), r.get("effective_stage"), r.get("now"),
            r.get("status"), bool(r.get("drift")))


def _ancestor_runbooks(conn, path):
    """Set of runbook paths that transitively include ``path`` as a member
    (walks ``membership.child`` upward)."""
    ancestors = set()
    frontier = [path]
    seen = set()
    while frontier:
        cur = frontier.pop()
        if cur in seen:
            continue
        seen.add(cur)
        for r in conn.execute(
                "SELECT parent FROM membership WHERE child=?", (cur,)).fetchall():
            par = r[0]
            if par not in ancestors:
                ancestors.add(par)
                frontier.append(par)
    return ancestors


# ── the core reindex (shared by --full / default / --file / sync_one) ─────────
def _drop_derived_rows(conn):
    """``--full`` reset: drop every markdown-derived row (claims are runtime,
    set by claim/release — kept)."""
    for t in ("tasks", "membership", "edges", "plans", "files"):
        conn.execute("DELETE FROM %s" % t)


def _reindex_paths(conn, root, paths, full=False, head_sha=None, mark_cycles=True):
    """Reindex a set of repo-relative paths. Returns ``(synced, rebuilt)``:
      * ``synced``  — paths actually reparsed (sha changed / ``full``)
      * ``rebuilt`` — set of ancestor-runbook paths whose rollup changed

    For each path: exists+allowlisted → upsert (sha short-circuit unless
    ``full``); missing on disk → delete rows (rename/archive/delete — W2C-1/3).
    Watermark + (on ``full``) derive_v land in the SAME transaction as the
    upserts (W2C-10 — no second rev-parse).

    ``mark_cycles`` (W2E-1/W2-T4): after membership population, scan the FULL
    membership table for cycles and mark both endpoints ``parse_err`` (a
    hand-edited cycle bypasses the ``runbook add`` door, so sync must catch it).
    On for the write paths (``cmd_sync`` + ``sync_one``); OFF for the read path
    (``ensure_fresh``) so reads don't mutate ``parse_err`` — sync owns it."""
    actions = []  # (rel, 'upsert'|'delete')
    # Sequence-registered paths are TRACKED regardless of filename allowlist
    # (parity with the oracle — it reads Sequence paths directly). Compute once;
    # upsert any on-disk path that is allowlisted OR Sequence-registered.
    seq_set = set(_sequence_paths(root))
    for rel in paths:
        full_path = os.path.join(root, rel)
        if os.path.isfile(full_path):
            if is_indexed(rel) or rel in seq_set:
                actions.append((rel, "upsert"))
        else:
            actions.append((rel, "delete"))

    # rebuild detection: snapshot ancestor rollups BEFORE any write.
    # Also track upserted runbooks THEMSELVES (a runbook whose own members:
    # changed must appear in rebuilt, not only its ancestors).
    ancestor_set = set()
    for rel, act in actions:
        ancestor_set |= _ancestor_runbooks(conn, rel)
        if act == "upsert":
            frow = conn.execute(
                "SELECT kind FROM files WHERE path=?", (rel,)).fetchone()
            if frow and frow[0] == "runbook":
                ancestor_set.add(rel)
    before = {rb: _rollup_sig(conn, rb) for rb in ancestor_set}

    synced = []
    with conn:  # one transaction (commit on clean exit, rollback on raise)
        for rel, act in actions:
            if act == "delete":
                _delete_plan_rows(conn, rel)
            else:
                if _upsert_file(conn, root, rel, force_reparse=full):
                    synced.append(rel)
        # membership AFTER files are indexed (child_kind resolvable)
        for rel, act in actions:
            if act == "upsert":
                _populate_membership(conn, root, rel)
        if mark_cycles:
            # W2E-1/W2-T4: a hand-edited membership cycle bypasses the
            # ``runbook add`` door — sync catches it + marks BOTH endpoints
            # parse_err (cheap: membership is a handful of rows).
            from planctl import runbook
            runbook.mark_cycle_parse_errors(conn)
        if head_sha is not None:
            conn.execute(
                "INSERT OR REPLACE INTO meta(key,value) VALUES('last_commit',?)",
                (head_sha,))
        if full:
            conn.execute(
                "INSERT OR REPLACE INTO meta(key,value) VALUES('derive_v',?)",
                (str(derive.DERIVE_V),))

    rebuilt = set()
    for rb in ancestor_set:
        if _rollup_sig(conn, rb) != before.get(rb):
            rebuilt.add(rb)
    return synced, rebuilt


def _needs_full(conn, root):
    """True when a full rebuild is required: DERIVE_V stale (mixed-semantics
    guard), no watermark (first-ever), or watermark GC'd (W2C-4)."""
    if db.is_stale(conn, derive.DERIVE_V):
        return True
    wm = conn.execute(
        "SELECT value FROM meta WHERE key='last_commit'").fetchone()
    if not wm or not wm[0]:
        return True
    if not _cat_file_exists(root, wm[0]):
        return True
    return False


# ── exported single-file reindex (0d post-mutation callable) ──────────────────
def sync_one(path, conn=None):
    """Reindex ONE file post-mutation; return the rebuilt ancestor-runbook set.

    Every 0d mutation verb calls this after its atomic MD write so the index is
    hot. ``conn`` may be passed by a caller already inside its own mutation
    transaction; otherwise a fresh connection is opened (and the watermark is
    advanced inside this call's transaction)."""
    own = conn is None
    if own:
        conn = db.open_db()
    try:
        root = statedir.project_root()
        rel = _normalize_arg_path(path, root)
        head_sha = _head_sha(root) if own else None
        _synced, rebuilt = _reindex_paths(
            conn, root, [rel], full=False, head_sha=head_sha)
        return rebuilt
    finally:
        if own:
            conn.close()


# ── reader freshness (the fast path readers use instead of full `sync`) ────────
def ensure_fresh(conn, root):
    """Cheap freshness gate readers call BEFORE querying (I4 — no reader trusts a
    cold/stale index), WITHOUT the ~10s ``git status`` porcelain scan that the
    ``sync`` verb pays on a 9p ``plans/`` mount.

    Steady state (committed truth unchanged): ``HEAD == meta.last_commit`` → the
    index was synced at ``last_commit`` and PostToolUse ``sync --file`` (M3b)
    has kept it hot for dirty edits since, so we TRUST it and return after one
    cheap ``rev-parse`` (~5ms). When ``HEAD`` advanced, a diff-only incremental
    (``git diff <wm>..HEAD`` — O(changes), ~150ms; skips the porcelain full-tree
    scan) absorbs the committed changes. A cold/stale-``derive_v`` index (incl.
    first-ever) escalates to ``--full``.

    The ``sync`` VERB stays thorough (porcelain ∪ diff) — that is the
    guaranteed-complete explicit refresh + the parity-test path. This reader
    path honors I4 (it verifies freshness via rev-parse; never trusts a
    cold/stale index) and is what makes the G2/G3 read-latency promises
    achievable on 9p. Resolved ambiguity (see phase report)."""
    if db.is_stale(conn, derive.DERIVE_V):
        _drop_derived_rows(conn)
        head_sha = _head_sha(root)
        _reindex_paths(conn, root, _walk_indexed(root), full=True,
                       head_sha=head_sha, mark_cycles=False)
        return

    head = _head_sha(root)
    wm_row = conn.execute(
        "SELECT value FROM meta WHERE key='last_commit'").fetchone()
    wm = wm_row[0] if wm_row else None

    if head is None:
        return  # not a git repo — nothing to detect; trust whatever is indexed
    if head == wm:
        return  # committed truth unchanged → trust (PostToolUse keeps dirty hot)
    if wm and _cat_file_exists(root, wm):
        cands = _diff_paths(root, wm)  # O(changes) — committed-since-watermark
    else:
        # watermark missing or GC'd — drop rows + full reindex + rewrite derive_v
        _drop_derived_rows(conn)
        _reindex_paths(conn, root, _walk_indexed(root), full=True,
                       head_sha=head, mark_cycles=False)
        return
    if cands:
        _reindex_paths(conn, root, cands, full=False, head_sha=head,
                       mark_cycles=False)
    else:
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO meta(key,value) VALUES('last_commit',?)",
                (head,))


# ── the verb ──────────────────────────────────────────────────────────────────
def _print_sync_human(synced, rebuilt, watermark, elapsed_ms, is_full):
    mode = "full" if is_full else "incremental"
    print("planctl sync [%s]: %d file(s) reparsed, %d runbook(s) rebuilt "
          "(%dms)" % (mode, len(synced), len(rebuilt), elapsed_ms))
    if rebuilt:
        print("  rebuilt: " + ", ".join(sorted(rebuilt)))
    print("  watermark: %s" % (watermark or "-"))


def cmd_sync(args):
    """``planctl sync [--file F | --full] [--json]`` — the freshness engine."""
    t0 = time.monotonic()
    root = statedir.project_root()
    conn = db.open_db()
    try:
        full = bool(getattr(args, "full", False))
        file_arg = getattr(args, "file", None)
        head_sha = _head_sha(root)

        if file_arg:
            rel = _normalize_arg_path(file_arg, root)
            paths = [rel] if rel else []
            synced, rebuilt = _reindex_paths(
                conn, root, paths, full=False, head_sha=head_sha)
            is_full = False
        elif full or _needs_full(conn, root):
            _drop_derived_rows(conn)
            paths = _walk_indexed(root)
            synced, rebuilt = _reindex_paths(
                conn, root, paths, full=True, head_sha=head_sha)
            is_full = True
        else:
            cands = _incremental_candidates(conn, root)
            synced, rebuilt = _reindex_paths(
                conn, root, cands, full=False, head_sha=head_sha)
            is_full = False

        elapsed_ms = int((time.monotonic() - t0) * 1000)

        if getattr(args, "json", False):
            print(json.dumps({
                "synced": sorted(synced),
                "rebuilt_runbooks": sorted(rebuilt),
                "watermark": head_sha,
                "elapsed_ms": elapsed_ms,
                "full": is_full,
            }))
        else:
            _print_sync_human(synced, rebuilt, head_sha, elapsed_ms, is_full)
        return 0
    finally:
        conn.close()
