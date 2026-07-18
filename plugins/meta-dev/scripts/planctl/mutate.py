#!/usr/bin/env python3
"""mutate.py — the atomic MD-write helper + ``check``/``uncheck`` (invariants I5,I6,I7).

The single mutation door's file-level primitives (I7 — schema gate lives in the
verbs that call these):

  * ``mutation_lock(plan_abs)`` — an exclusive ``flock`` on an ext4 sidecar at
    ``state_dir()/locks/<sha1(plan)>.lock``. ALWAYS under ``state_dir()`` — the
    plans dir is on 9p, where a same-dir sidecar would be dead code (W2D-1). The
    lock spans the WHOLE mutation: MD write → index upsert → event append
    (W2D-2) — callers acquire it once and run all three inside.
  * ``atomic_write_md(path, mutator)`` — read → ``mutator(lines)`` → temp +
    ``os.replace`` (the runbook-render/task-done idiom, I6). No lock inside: the
    caller holds ``mutation_lock`` so the write is serialized against concurrent
    mutators of the same plan.
  * ``cmd_check`` / ``cmd_uncheck`` — ``planctl check/uncheck <plan> <tid…>``:
    ONE atomic read-modify-write for ALL tids (W2D-3); dual-id match (``#hex``
    canonical, ``T3.2`` alias, text-prefix fallback); the human-gate (refuse a
    ``by eye``/``gpu``/``manual`` box unless ``--human``/``--force``, mirroring
    ``task-done.sh``); the ``--verify "<cmd>"`` gate (design §3.4, W2D-4 — run
    ONCE with an explicit cwd + 300s timeout, held under the lock so it can't
    deadlock, abort ALL flips on non-zero). After the write: ``sync.sync_one``
    (upsert) + ``events.append`` (per flipped tid).

A crash mid-mutation self-heals: the next ``sync`` detects the sha mismatch and
reparses (the index is disposable — I3).

Stdlib only.
"""
import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

from planctl import events, parse, statedir, sync
from planctl.parse import _CHECKBOX_RE  # parity with the parser's checkbox regex

# tids that are NOT a bead (#hex) or a legacy handle (T3.2) → text-prefix fallback.
_BEAD_TID_RE = re.compile(r"^#[0-9a-fA-F]{4}(\.\d+)?$")
_HANDLE_TID_RE = re.compile(r"^T[A-Za-z0-9]+\.\d+$")

_VERIFY_TIMEOUT = 300  # seconds (W2D-4 — bounded so the lock can't deadlock)


# ── lock + atomic write ──────────────────────────────────────────────────────
@contextlib.contextmanager
def mutation_lock(plan_abs_path):
    """Exclusive flock on ``state_dir()/locks/<sha1(plan)>.lock`` (W2D-1).

    The sidecar lives UNDER ``state_dir()`` (ext4, off-9p) — NEVER next to the
    plan (the plans dir is on 9p, so a same-dir sidecar is dead code). The lock
    file persists (stable path/inode across plan renames + reuse). Blocking
    acquire — serializes concurrent mutators of the SAME plan; different plans
    use different sha1 keys → no cross-plan contention."""
    import fcntl
    sd = statedir.state_dir()
    locks_dir = os.path.join(sd, "locks")
    os.makedirs(locks_dir, exist_ok=True)
    key = hashlib.sha1(plan_abs_path.encode("utf-8")).hexdigest()
    lock_path = os.path.join(locks_dir, key + ".lock")
    fh = open(lock_path, "a+")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()


def atomic_write_md(path, mutator):
    """Read ``path`` → ``mutator(lines) → (new_lines, changes)`` → temp+replace.

    ``mutator`` receives the current line list (``split("\\n")``) and returns
    ``(new_lines, changes)``; ``changes`` is opaque to this function (the caller
    uses it — e.g. the flipped-tid list). Newline style is preserved (a trailing
    newline in the source is kept). A no-op (``new_text == text``) writes
    nothing. The temp lands in the SAME dir as the target (the established idiom;
    ``os.replace`` is atomic on 9p too) — I6.

    Returns ``(new_text, changes)``. Raises on disk failure (caller's lock is
    released by the context manager; a half-written temp is unlinked)."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    ends_nl = text.endswith("\n")
    lines = text.split("\n")
    new_lines, changes = mutator(lines)
    new_text = "\n".join(new_lines)
    if ends_nl and not new_text.endswith("\n"):
        new_text += "\n"
    if new_text == text:
        return new_text, changes  # no-op: no write, no event
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".planctl.", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(new_text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return new_text, changes


# ── checkbox flip + tid resolution ───────────────────────────────────────────
def _flip_line(line, to_checked):
    """Flip ONE checkbox line's mark. Returns ``(new_line, changed)``.

    ``to_checked`` True → ``[ ]``→``[x]``; False → ``[x]``→``[ ]``. A line
    already in the target state → ``(line, False)`` (no-op, not an error).
    Preserves indent/bullet/gap/rest exactly (only the mark char is swapped)."""
    m = _CHECKBOX_RE.match(line)
    if not m:
        return line, False
    s, e = m.start(3), m.end(3)  # group(3) = the mark char
    is_checked = line[s:e].lower() == "x"
    if is_checked == to_checked:
        return line, False  # already in the target state
    new_mark = "x" if to_checked else " "
    return line[:s] + new_mark + line[e:], True


def _match_task(tasks, query):
    """Resolve a user tid query → a ``parse.Task`` (or None).

    Dual-id match (the parser's): ``#hex`` canonical, ``T3.2`` alias, then a
    text-prefix fallback for untagged boxes. A bare 4-hex token (no ``#``) is
    accepted as ``#``+token; ``T3.2`` accepts optional surrounding backticks."""
    q = (query or "").strip().strip("`")
    if not q:
        return None
    ql = q.lower()
    if len(ql) == 4 and all(c in "0123456789abcdef" for c in ql):
        ql = "#" + ql  # bare 4-hex → bead form
    for t in tasks:
        if t.tid and t.tid.lower() == ql:
            return t
        if t.alias and t.alias.lower() == ql:
            return t
    # text-prefix fallback: an untagged box's tid IS normalize_rest(rest).
    nq = parse.normalize_rest(q)
    if nq:
        for t in tasks:
            if t.tid and not (_BEAD_TID_RE.match(t.tid) or _HANDLE_TID_RE.match(t.tid)) \
                    and t.tid == nq:
                return t
    return None


# ── --verify gate (design §3.4, W2D-4) ────────────────────────────────────────
def _run_verify(cmd, cwd):
    """Run ``cmd`` ONCE with ``shell=True``, explicit ``cwd`` + 300s timeout.

    Returns ``(rc, output)``. ``cwd`` is the explicit host project root (never
    ambient). Held under the file lock by the caller — the timeout bounds it so
    a hung verify can't wedge the lock forever. Timeout → rc 124."""
    try:
        r = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True,
            timeout=_VERIFY_TIMEOUT)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired as e:
        out = ((e.stdout or "") if isinstance(e.stdout, str) else "") + \
              ((e.stderr or "") if isinstance(e.stderr, str) else "")
        return 124, out + "\n[planctl: verify timed out after %ds]" % _VERIFY_TIMEOUT
    except OSError as e:
        return 127, "[planctl: verify failed to start: %s]" % e


# ── the verbs ────────────────────────────────────────────────────────────────
def _emit(args, payload):
    """Print the verb result — JSON when ``--json``, else a human summary.

    Successful summaries go to stdout; skipped/refused/error diagnostics go to
    stderr so callers doing ``>/dev/null`` still see the diagnostic."""
    if getattr(args, "json", False):
        # Drop the internal ``_ev`` hint from the JSON payload.
        out = {k: v for k, v in payload.items() if k != "_ev"}
        print(json.dumps(out))
        return
    ev = payload.get("_ev", "check")
    flipped = payload["flipped"]
    skipped = payload.get("skipped", [])
    verified = payload.get("verified")
    if flipped:
        print("planctl %s: flipped %d → %s" % (ev, len(flipped), ", ".join(flipped)))
    else:
        print("planctl %s: no boxes flipped" % ev)
    for s in skipped:
        sys.stderr.write("  skipped %s (%s)\n" % (s.get("tid"), s.get("reason")))
    if verified is False:
        sys.stderr.write("  --verify failed: aborted all flips\n")


def _resolve_plan_arg(plan_arg):
    """``(rel, abs_path)`` for a plan-path STRING resolved against the project root.

    Returns ``(None, None)`` if the file does not exist (caller emits a
    plan_not_found skip). Shared by every verb that resolves a plan —
    ``cmd_override`` passes a string (its clear-form arg shuffling yields the
    real plan path late); most verbs pass ``args.plan`` via ``_resolve_plan``."""
    root = statedir.project_root()
    rel = sync._normalize_arg_path(plan_arg, root)
    abs_path = os.path.join(root, rel)
    if not os.path.isfile(abs_path):
        return None, None
    return rel, abs_path


def _resolve_plan(args):
    """``_resolve_plan_arg(args.plan)`` — convenience for the common case."""
    return _resolve_plan_arg(args.plan)


def cmd_check(args, to_checked=True):
    """``planctl check <plan> <tid…> [--human] [--force] [--verify "<cmd>"]``.

    ONE atomic read-modify-write flips every resolvable tid (W2D-3): a partial
    failure (one tid unresolvable / human-gated) → ``skipped:[{tid,reason}]`` +
    nonzero exit, but the resolvable tids STILL land. Human-gate refuses a
    ``by eye``/``gpu``/``manual`` box unless ``--human``/``--force``.
    ``--verify`` runs once (explicit cwd, 300s, under the lock); non-zero ABORTS
    ALL flips + emits NO event + exits nonzero. After the write: ``sync.sync_one``
    + one ``check``/``uncheck`` event per flipped tid.

    ``--json`` → ``{flipped:[tid…], skipped:[{tid,reason}], verified: bool}``.
    """
    rel, abs_path = _resolve_plan(args)
    if abs_path is None:
        _emit(args, {"_ev": "check" if to_checked else "uncheck",
                     "flipped": [], "verified": True,
                     "skipped": [{"tid": args.plan, "reason": "plan_not_found"}]})
        return 1

    by = getattr(args, "by", None) or os.environ.get("USER") or "conductor"
    verify_cmd = getattr(args, "verify", None)
    root = statedir.project_root()
    ev_name = "check" if to_checked else "uncheck"

    with mutation_lock(abs_path):
        # --verify gate: run ONCE, under the lock, bounded (W2D-4).
        verify_rc = None
        if verify_cmd:
            verify_rc, _vout = _run_verify(verify_cmd, root)
            if verify_rc != 0:
                # ABORT ALL flips + NO event + nonzero exit.
                _emit(args, {"_ev": ev_name, "flipped": [], "skipped": [],
                             "verified": False})
                return 1

        flipped, skipped = [], []

        def mutator(lines):
            tasks, _perr = parse.parse_tasks("\n".join(lines))
            for q in args.tids:
                t = _match_task(tasks, q)
                if t is None:
                    skipped.append({"tid": q, "reason": "unresolved"})
                    continue
                if to_checked and t.human_verify \
                        and not getattr(args, "human", False) \
                        and not getattr(args, "force", False):
                    skipped.append({"tid": q, "reason": "human_verify"})
                    continue
                idx = t.line_no - 1
                new_ln, changed = _flip_line(lines[idx], to_checked)
                if changed:
                    lines[idx] = new_ln
                    flipped.append(t.tid)
            return lines, flipped

        atomic_write_md(abs_path, mutator)

        # upsert index + event append (still under the lock — W2D-2).
        if flipped:
            sync.sync_one(rel)
            for tid in flipped:
                data = {"tid": tid, "by": by}
                if verify_rc is not None:
                    data["verify_rc"] = verify_rc
                    data["verify_out"] = _vout[:1500]
                events.append({"event": ev_name, "plan": rel, "data": data})

    verified = True if verify_rc is None else (verify_rc == 0)
    _emit(args, {"_ev": ev_name, "flipped": flipped,
                 "skipped": skipped, "verified": verified})
    return 1 if skipped else 0


def cmd_uncheck(args):
    """``planctl uncheck <plan> <tid…>`` — ``cmd_check`` with ``to_checked=False``."""
    return cmd_check(args, to_checked=False)
