#!/usr/bin/env python3
"""SQLite read-model schema + ``open_db`` + DERIVE_V staleness gate (invariants I2,I3,I5).

The disposable SQLite read-model that ``sync`` (0c) populates from git markdown
truth. ONE interpreter (``derive.py``, 0b) stamps ``DERIVE_V``; readers compare
the on-disk ``meta.derive_v`` against it via ``is_stale`` to decide whether to
re-derive. This module owns the SCHEMA + connection hygiene only — no parsing,
no derivation, no mutation here.

Schema = design §3.3 (``meta``, ``files``, ``plans``, ``tasks``, ``membership``,
``edges``, ``claims``). Both count families live on ``plans`` (R2/VC-2):
``tasks_*``/``human_*`` are derive inputs; ``raw_*`` are the parity columns.

Stdlib only.
"""
import contextlib
import fcntl
import os
import sqlite3

from planctl import statedir

# ── schema (design §3.3) ────────────────────────────────────────────────────
SCHEMA = """\
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS files (
    path      TEXT PRIMARY KEY,
    kind      TEXT,              -- plan | runbook | ledger
    sha1      TEXT,
    mtime_ns  INTEGER,
    size      INTEGER,
    parse_err TEXT
);

CREATE TABLE IF NOT EXISTS plans (
    path            TEXT PRIMARY KEY,
    repo            TEXT,
    stage           INTEGER,
    override        TEXT,
    note            TEXT,
    why             TEXT,
    title           TEXT,
    tasks_done      INTEGER,     -- EXECUTION/human split (derive input)
    tasks_total     INTEGER,
    human_open      INTEGER,     -- human-verify boxes still open (derive input)
    human_total     INTEGER,
    raw_done        INTEGER,     -- ALL boxes (parity column — parity compares RAW only)
    raw_total       INTEGER,
    drift           INTEGER,     -- stage>=6 AND open exec boxes (0/1)
    context_json    TEXT,        -- declared Stage-3 context paths (docs-evidence gate)
    docs_json       TEXT,        -- declared Stage-3 docs paths (docs-evidence gate)
    derived_status  TEXT         -- stored for PLAN files only (runbook status computed-on-read)
);

CREATE TABLE IF NOT EXISTS tasks (
    plan_path    TEXT,
    tid          TEXT,           -- stable id (#hex bead) or legacy T3.2 alias
    line_no      INTEGER,
    checked      INTEGER,        -- 0/1
    human_verify INTEGER,        -- 0/1 (by eye / by hand / gpu / manual)
    section      TEXT,
    text         TEXT,
    PRIMARY KEY (plan_path, tid)
);

CREATE TABLE IF NOT EXISTS membership (
    parent     TEXT,
    child      TEXT,             -- normalized project-root-relative on insert (G-IMP6)
    ord        INTEGER,
    child_kind TEXT,             -- plan | runbook
    PRIMARY KEY (parent, child)
);

CREATE TABLE IF NOT EXISTS edges (
    src  TEXT,
    dst  TEXT,
    kind TEXT                   -- depends | blocks
);

CREATE TABLE IF NOT EXISTS claims (
    scope   TEXT PRIMARY KEY,   -- overlap = PREFIX scope match (not PK-equality)
    session TEXT,
    host    TEXT,
    ts      TEXT,
    pid     INTEGER,
    status  TEXT,
    ttl     INTEGER DEFAULT 1800  -- 1800s
);

CREATE INDEX IF NOT EXISTS idx_tasks_plan      ON tasks (plan_path);
CREATE INDEX IF NOT EXISTS idx_membership_par  ON membership (parent);
CREATE INDEX IF NOT EXISTS idx_membership_chi  ON membership (child);
CREATE INDEX IF NOT EXISTS idx_files_kind      ON files (kind);
"""


class DBCorrupt(Exception):
    """Raised when ``PRAGMA integrity_check`` != 'ok'. Triggers ``heal()``."""


def open_db(path=None):
    """Open (or create) the state DB at ``path``, applying the schema idempotently.

    ``path`` defaults to ``statedir.db_path()`` (off-9p, I5). Calls
    ``statedir.assert_ext4`` (no-op when ``META_DEV_STATE_DIR`` is set). Applies
    WAL + a 5s busy_timeout + foreign_keys, then ``executescript(SCHEMA)``.

    Returns an open ``sqlite3.Connection`` (callers use ``conn.execute``).
    Idempotent: re-running on an existing DB is a no-op (``CREATE … IF NOT
    EXISTS``); disposable: ``rm`` of the file heals (I3).
    """
    if path is None:
        path = statedir.db_path()
    statedir.assert_ext4(path)  # no-op when META_DEV_STATE_DIR set
    conn = sqlite3.connect(path, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


def is_stale(conn, current_v):
    """True if the read-model's ``meta.derive_v`` is missing or != ``current_v``.

    ``current_v`` is the expected DERIVE_V int, passed BY THE CALLER — db.py does
    NOT import ``derive.py`` (avoids an import cycle before derive exists).
    ``meta.derive_v`` is WRITTEN by ``sync --full`` (0c), not by ``open_db``.
    A missing or non-integer stored value counts as stale.
    """
    row = conn.execute("SELECT value FROM meta WHERE key=?", ("derive_v",)).fetchone()
    if row is None:
        return True
    try:
        return int(row[0]) != int(current_v)
    except (ValueError, TypeError):
        return True


def check_integrity(conn):
    """Run ``PRAGMA integrity_check``; raise ``DBCorrupt`` if not 'ok'.

    Called ONLY by ``doctor``/``sync`` (BC4) — never on every ``open_db`` (that
    blows read budgets and raises uncaught ``DBCorrupt`` on read paths). Read
    verbs catch ``DBCorrupt`` and auto-heal.
    """
    row = conn.execute("PRAGMA integrity_check").fetchone()
    result = row[0] if row else ""
    if str(result).lower() != "ok":
        raise DBCorrupt("integrity_check failed: %s" % result)


@contextlib.contextmanager
def _single_flight(lock_path):
    """Exclusive-flock guard for the detect→delete→rebuild heal path (G0a-ADV).

    Prevents two concurrent first-run corruptions from both deleting+rebuilding
    the same sidecars. Blocking acquire (the second healer waits, then re-checks
    integrity under the lock before rebuilding — see ``heal``).
    """
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    fh = open(lock_path, "w")
    acquired = False
    try:
        fcntl.flock(fh, fcntl.LOCK_EX)  # blocking; serializes concurrent healers
        acquired = True
        yield
    finally:
        if acquired:
            fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()


def heal(state_dir):
    """Repair a corrupt DB: delete all sidecars, recreate the schema (BC6/G0a-5).

    A corrupt file cannot be ``DROP``'d in place, so remove all THREE sidecars
    (``state.db``, ``state.db-wal``, ``state.db-shm``) and let ``open_db``
    recreate the schema. Guarded by a single-flight lock so two concurrent
    healers don't both rebuild; the second re-checks integrity under the lock
    and no-ops if the first already fixed it.

    The full DATA repopulation is ``sync --full`` (0c) — this 0a scaffold only
    restores a clean, openable, schema-correct (empty) DB. Disposable (I3).
    """
    lock_path = os.path.join(state_dir, ".heal.lock")
    db = os.path.join(state_dir, "state.db")
    with _single_flight(lock_path):
        # Re-check under lock: another healer may have already fixed it.
        try:
            with contextlib.closing(open_db(db)) as conn:
                check_integrity(conn)
            return  # already healthy
        except (DBCorrupt, sqlite3.DatabaseError):
            pass  # fall through to delete + rebuild

        for name in ("state.db", "state.db-wal", "state.db-shm"):
            try:
                os.remove(os.path.join(state_dir, name))
            except FileNotFoundError:
                pass
        conn = open_db(db)  # recreate schema cleanly
        conn.close()
