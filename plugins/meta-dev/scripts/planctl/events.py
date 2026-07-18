#!/usr/bin/env python3
"""events.py — the append-only event log (design §3.5; invariants I5, I6).

A single ``events.jsonl`` under ``statedir.events_path()`` (off-9p, ext4) is the
audit + read trail for the unified state layer. Every mutation verb appends ONE
line here as its final step (atomic MD edit → index upsert → event append).

Layout::

    {ts, session, event, plan, data}

``ts`` is a float epoch (microsecond precision on Linux) — the stable sort key
(W2D-8 tie-break: same-second events stay ordered by write order, and the float
carries sub-second precision so collisions are effectively impossible). It is
parity-consistent with ``claims.ts`` (``read._live_claims`` parses it as float).
``session`` is injected from ``$CLAUDE_SESSION_ID`` (fallback ``pid-<pid>``).

Two correctness properties:

  * **Atomic single-line ≤4KB (W2D-5):** each appended line is serialized as
    single-line JSON and shrunk to fit under ``PIPE_BUF`` (4096) so an
    ``O_APPEND`` write never tears. When the line would exceed the budget the
    ``data`` payload is truncated to a string prefix and ``"truncated": true`` is
    set — structure is lost but the line stays valid + atomic.
  * **10MB rotation (W2D-6):** on append, if the file is ≥10MB, an exclusive
    events lock guards a size-check → ``os.replace`` rename to
    ``events-<timestamp>.jsonl`` (timestamp suffix, NOT date-only, so multiple
    rotations in one second stay distinct + sort chronologically). Appends
    themselves are lock-free (O_APPEND + ≤4KB is atomic on ext4); only rotation
    serializes.

Event types (design §3.5 canon — NOT enforced here, to stay forward-compatible;
new types land without a code change):
  check | uncheck | stage | override | claim | release | runbook_change |
  done_gate | review_verdict | archive | task_add | stamp

Stdlib only.
"""
import contextlib
import fcntl
import glob
import json
import os
import time

from planctl import statedir

# PIPE_BUF is 4096 on Linux; leave headroom for the newline + fs block safety.
# A write of ≤ this many BYTES is atomic under O_APPEND on a local fs.
_MAX_LINE_BYTES = 4000
_ROTATE_THRESHOLD = 10 * 1024 * 1024  # 10MB


def _session():
    """Stable-per-process session id (``$CLAUDE_SESSION_ID`` else ``pid-<pid>``)."""
    return os.environ.get("CLAUDE_SESSION_ID") or ("pid-%d" % os.getpid())


def _encode_line(rec, max_bytes=_MAX_LINE_BYTES):
    """Serialize ``rec`` to single-line JSON ≤ ``max_bytes`` (incl newline).

    If the full record fits, return it verbatim. Otherwise set
    ``"truncated": true`` and replace ``data`` with the longest prefix of its
    JSON serialization that still fits (structure lost, line stays valid +
    atomic — W2D-5). The non-``data`` fields are tiny and always fit.
    """
    def enc(r):
        # separators: tightest JSON (no spaces); ensure_ascii=False keeps unicode
        # (control chars like \n are still escaped → output stays single-line).
        return json.dumps(r, separators=(",", ":"), ensure_ascii=False)

    base = enc(rec)
    if len((base + "\n").encode("utf-8")) <= max_bytes:
        return base

    data = rec.get("data")
    skel = {k: v for k, v in rec.items() if k != "data"}
    skel["truncated"] = True
    data_str = json.dumps(data, ensure_ascii=False) if data is not None else ""

    # Binary search the longest data_str prefix that fits.
    lo, hi, best = 0, len(data_str), ""
    while lo <= hi:
        mid = (lo + hi) // 2
        cand = dict(skel)
        cand["data"] = data_str[:mid]
        if len((enc(cand) + "\n").encode("utf-8")) <= max_bytes:
            best = data_str[:mid]
            lo = mid + 1
        else:
            hi = mid - 1
    cand = dict(skel)
    cand["data"] = best
    return enc(cand)


@contextlib.contextmanager
def _events_lock():
    """Exclusive flock on ``<state_dir>/events.lock`` — guards rotation only.

    Appends are lock-free (O_APPEND + ≤4KB atomic); only the size-check→rename
    rotation critical section takes this lock so two concurrent rotators don't
    double-rename. The lock file persists (stable inode across calls)."""
    sd = statedir.state_dir()
    os.makedirs(sd, exist_ok=True)
    fh = open(os.path.join(sd, "events.lock"), "a+")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()


def _rotated_suffix(ts):
    """``events-<timestamp>`` suffix — sortable ISO + ms (NOT date-only, W2D-6)."""
    gm = time.gmtime(ts)
    return time.strftime("%Y%m%dT%H%M%S", gm) + (".%03d" % int((ts % 1) * 1000))


def _maybe_rotate(path, threshold=_ROTATE_THRESHOLD):
    """If ``path`` ≥ threshold bytes, rename it to ``events-<ts>.jsonl`` (W2D-6).

    Under the events lock: re-check the size (another rotator may have just
    rotated), then ``os.replace`` the current file aside so the next append
    starts a fresh ``events.jsonl``. Concurrent lock-free appends are safe: one
    in flight writes to the rotated inode (persisted), one after the rename
    writes the new file — no line lost or torn (each ≤4KB atomic)."""
    try:
        if os.path.getsize(path) < threshold:
            return
    except OSError:
        return
    with _events_lock():
        try:
            size = os.path.getsize(path)
        except OSError:
            return
        if size < threshold:
            return
        rotated = os.path.join(
            os.path.dirname(path), "events-%s.jsonl" % _rotated_suffix(time.time()))
        # If the exact suffix exists (two rotations in the same ms — virtually
        # impossible), fall back to a uniquified name rather than clobbering.
        if os.path.exists(rotated):
            i = 1
            while os.path.exists("%s.%d" % (rotated, i)):
                i += 1
            rotated = "%s.%d" % (rotated, i)
        os.replace(path, rotated)


def append(record):
    """Append one event line to ``events.jsonl``.

    ``record`` is a dict carrying at least ``event`` (the type) and ``plan``
    (repo-relative plan path or scope); optional ``data`` holds the verb-specific
    payload. ``ts`` (float epoch) + ``session`` are INJECTED here — callers never
    set them. The line is shrunk to ≤4KB (``_encode_line``) and written with a
    single ``O_APPEND`` so concurrent writers never tear (W2D-5). Rotation at
    10MB (W2D-6). Never raises on payload size; may raise on disk failure.
    """
    rec = {"ts": time.time(), "session": _session()}
    rec.update(record or {})
    path = statedir.events_path()
    statedir.assert_ext4(path)  # no-op under META_DEV_STATE_DIR (I5 guard)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _maybe_rotate(path)
    line = _encode_line(rec)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def query(plan=None, event=None, since=None, limit=None):
    """Scan current + rotated events in chronological order; filter + return list.

    Rotated files (``events-*.jsonl``) sort before + lexically-chronological;
    the current ``events.jsonl`` is read last (newest). Within each file, lines
    are append-order (chronological). Optional filters: ``plan`` (exact match on
    the ``plan`` field), ``event`` (type), ``since`` (float-epoch ``ts`` floor).
    ``limit`` keeps the last N (most recent) matching events. Malformed lines are
    skipped (never raise) — a truncated line is still valid JSON (data is a
    string prefix), so it parses; only a genuinely corrupt line is dropped."""
    path = statedir.events_path()
    directory = os.path.dirname(path)
    files = sorted(glob.glob(os.path.join(directory, "events-*.jsonl")))
    if os.path.isfile(path):
        files.append(path)
    out = []
    for f in files:
        try:
            fh = open(f, encoding="utf-8")
        except OSError:
            continue
        try:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if plan is not None and rec.get("plan") != plan:
                    continue
                if event is not None and rec.get("event") != event:
                    continue
                if since is not None:
                    try:
                        if float(rec.get("ts", 0)) < since:
                            continue
                    except (TypeError, ValueError):
                        continue
                out.append(rec)
        finally:
            fh.close()
    if limit:
        out = out[-limit:]
    return out
