#!/usr/bin/env python3
"""Off-9p state directory + project slug for planctl (invariant I5).

State DB + event log live OFF the 9p mount::

    ~/.cache/meta-dev/<project-slug>/{state.db, events.jsonl}

``<project-slug>`` = ``slugify(abs_path(host_project_root))`` — the SAME scheme
Claude Code uses for its own project dirs (e.g. ``-mnt-d-Projects-360-Hextile``),
so the planctl state tree sits next to Claude Code's per-project data.

Injection seam (R8/DR-4) — two env overrides, NEVER set in production:

``META_DEV_STATE_DIR``
    If set, ``state_dir()`` returns it VERBATIM and BYPASSES ``slugify`` +
    ``assert_ext4`` (the ``tmp_path`` a test passes is on whatever fs pytest
    chose — usually ext4 under ``/tmp``, never 9p, and the slug is irrelevant).
    This is THE hermeticity knob (W2-T1): every test + the parity harness sets
    it via ``conftest tmp_path``.

``META_DEV_ROOT``
    If set, ``project_root()`` returns it (bypasses the ``repo-topology.py
    --root`` subprocess + ``CLAUDE_PROJECT_DIR`` fallback) so a fixture
    ``plans/`` tree is the project root, not the live host root.

``project_root()`` resolves the HOST project root through
``lib/repo-topology.py --root`` (cwd-independent — never guesses cwd, mirroring
``resolve-workdir.sh``'s refuse-to-guess law).

Stdlib only.
"""
import os
import re
import subprocess
import sys

# Scripts dir = the PARENT of this package dir (dirname applied twice:
# __file__ → planctl/ → scripts/). repo-topology.py lives in scripts/lib/.
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.dirname(_PKG_DIR)
_TOPOLOGY = os.path.join(_SCRIPTS_DIR, "lib", "repo-topology.py")

# fstypes / option markers that mark the unwritable 9p mount.
_9P_FSTYPES = ("9p", "drvfs")
_DRVFS_OPT = "drvfs"


def slugify(abs_path):
    """Sanitize an absolute path into a stable slug.

    ``re.sub(r'[/.]', '-', abs_path)`` — casefold-stable. Golden:
    ``slugify('/home/u/Projects/My-App')`` == ``-home-u-Projects-My-App``
    (G0a-3/G-IMP4 — matches Claude Code's scheme).
    """
    return re.sub(r"[/.]", "-", abs_path)


# Memo for project_root(). Resolution spawns `repo-topology.py` as a SUBPROCESS,
# and reconcile calls this ~25x per run (directly and via state_dir/events_path).
# On a 9p mount each spawn costs ~160ms → ~4s of pure fork overhead, which alone
# blew the <1s Stop-hook budget (G3). The result is a pure function of the two
# env vars below, so the cache is keyed on them: hermetic tests that repoint
# META_DEV_ROOT per fixture get their own entry instead of a stale hit.
_ROOT_MEMO = {}


def project_root():
    """Absolute path of the HOST project root.

    Order (first hit wins; never guesses cwd):
      1. ``$META_DEV_ROOT``            — fixture/test override (DR-4)
      2. ``repo-topology.py --root``   — cwd-independent topology (preferred)
      3. ``$CLAUDE_PROJECT_DIR``       — plugin-runtime fallback
      4. error loudly                  — refuse-to-guess (resolve-workdir law)

    Memoized per (META_DEV_ROOT, CLAUDE_PROJECT_DIR) — see ``_ROOT_MEMO``.

    Raises SystemExit (exit 1) if none resolve.
    """
    _key = (os.environ.get("META_DEV_ROOT"), os.environ.get("CLAUDE_PROJECT_DIR"))
    if _key in _ROOT_MEMO:
        return _ROOT_MEMO[_key]
    _resolved = _project_root_uncached()
    _ROOT_MEMO[_key] = _resolved
    return _resolved


def _project_root_uncached():
    """The real resolution — see ``project_root`` for the order."""
    env_root = os.environ.get("META_DEV_ROOT")
    if env_root:
        return os.path.abspath(env_root)

    if os.path.isfile(_TOPOLOGY):
        try:
            result = subprocess.run(
                [sys.executable, _TOPOLOGY, "--root"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return os.path.abspath(result.stdout.strip())
        except (OSError, subprocess.TimeoutExpired):
            pass  # fall through to CLAUDE_PROJECT_DIR

    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    if proj:
        return os.path.abspath(proj)

    sys.exit(
        "planctl: cannot resolve project root (set META_DEV_ROOT or "
        "CLAUDE_PROJECT_DIR, or run where .claude/meta-dev-repos.json is "
        "discoverable). Refusing to guess cwd."
    )


# ── filesystem detection (works on not-yet-created paths) ───────────────────

def _nearest_existing(path):
    """Walk up from ``path`` to the first existing ancestor (or ``/``)."""
    cur = os.path.abspath(path)
    while True:
        if os.path.exists(cur):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return cur  # reached /
        cur = parent


def _unescape_proc_mount(s):
    """Decode ``\\ooo`` octal escapes used in /proc/mounts (space=\\040, \\=\\134)."""
    out = []
    i = 0
    n = len(s)
    while i < n:
        if s[i] == "\\" and i + 3 < n and s[i + 1:i + 4].isdigit():
            try:
                out.append(chr(int(s[i + 1:i + 4], 8)))
                i += 4
                continue
            except ValueError:
                pass
        out.append(s[i])
        i += 1
    return "".join(out)


def _fs_from_proc(path):
    """``(fstype, options)`` for the longest-matching mount of ``path`` in /proc/mounts.

    Works on path strings directly (path need not exist). Returns ``("", "")``
    if nothing matches (e.g. /proc/mounts unreadable).
    """
    ap = os.path.abspath(path)
    best = ("", "")
    best_prefix = ""
    try:
        with open("/proc/mounts", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 3:
                    continue
                mount = _unescape_proc_mount(parts[1])
                if ap == mount or ap.startswith(mount.rstrip("/") + "/"):
                    if len(mount) > len(best_prefix):
                        best_prefix = mount
                        best = (parts[2], parts[3] if len(parts) > 3 else "")
    except OSError:
        pass
    return best


def _fs_of(path):
    """``(fstype, options)`` for the filesystem holding ``path``.

    Resolves to the nearest EXISTING ancestor first (``findmnt -T`` returns
    nothing for non-existent paths), then falls back to a /proc/mounts
    longest-prefix match on the path string. Best-effort; returns ``("", "")``
    if neither resolves.
    """
    anchor = _nearest_existing(path)
    try:
        out = subprocess.run(
            ["findmnt", "-no", "FSTYPE,OPTIONS", "-T", anchor],
            capture_output=True, text=True, timeout=3,
        )
        if out.returncode == 0 and out.stdout.strip():
            line = out.stdout.splitlines()[0]
            cols = line.split(None, 1)
            fstype = cols[0].strip()
            opts = cols[1].strip() if len(cols) > 1 else ""
            if fstype:
                return fstype, opts
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return _fs_from_proc(path)


def is_9p(path):
    """True if ``path`` lives on the 9p/drvfs mount."""
    fstype, opts = _fs_of(path)
    if fstype in _9P_FSTYPES:
        return True
    return _DRVFS_OPT in (opts or "")


def assert_ext4(path):
    """Refuse to place state on the 9p/drvfs mount (I5).

    NO-OP when ``META_DEV_STATE_DIR`` is set (the hermeticity knob bypasses this
    so tests can target tmp dirs on any fs). Otherwise, if the resolved path is
    on 9p/drvfs, exit loudly naming the offending mount, the target, and the
    ``META_DEV_STATE_DIR`` escape hatch (G0a-ADV).
    """
    if os.environ.get("META_DEV_STATE_DIR"):
        return
    fstype, opts = _fs_of(path)
    on_9p = fstype in _9P_FSTYPES or _DRVFS_OPT in (opts or "")
    if not on_9p:
        return
    sys.exit(
        "planctl: refusing to write state onto a 9p/drvfs mount (I5).\n"
        "  target : %s\n"
        "  mount  : fstype=%s options=%s\n"
        "The state DB must live on ext4 (off the 9p mount) for correctness and\n"
        "speed. Set META_DEV_STATE_DIR=/path/on/ext4 to override\n"
        "(tests/hermetic harness only — never in production)."
        % (path, fstype or "?", opts or "?")
    )


def state_dir():
    """Absolute state dir, creating it (mode 0o700) if absent.

    ``$META_DEV_STATE_DIR`` (if set) is returned VERBATIM (no slugify, no 9p
    assert) — the hermeticity knob. Otherwise:
    ``$HOME/.cache/meta-dev/<slug>/`` where ``slug = slugify(project_root())``,
    asserted off-9p before anything is written there.

    ``db_path()`` and ``events_path()`` route through here so the first write
    can never hit a missing dir (DR-5).
    """
    env = os.environ.get("META_DEV_STATE_DIR")
    if env:
        os.makedirs(env, exist_ok=True)
        try:
            os.chmod(env, 0o700)
        except OSError:
            pass
        return env

    slug = slugify(project_root())
    d = os.path.join(os.path.expanduser("~"), ".cache", "meta-dev", slug)
    assert_ext4(d)  # refuse 9p BEFORE creating anything on it
    os.makedirs(d, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


def db_path():
    """``<state_dir>/state.db``."""
    return os.path.join(state_dir(), "state.db")


def events_path():
    """``<state_dir>/events.jsonl``."""
    return os.path.join(state_dir(), "events.jsonl")
