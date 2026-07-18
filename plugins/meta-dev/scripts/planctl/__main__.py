#!/usr/bin/env python3
"""planctl CLI entry — argparse dispatch skeleton.

Invoked as ``python3 -m planctl`` (the ``scripts/planctl.sh`` shim sets
PYTHONPATH to the scripts dir and execs this module).

Phase 0a scope: wire the global ``--json`` flag (beads doctrine — EVERY verb
will support it) + the subparser scaffold. Verbs are registered in later
phases (status/brief/next in 0c; check/stamp/stage/claim in 0d–0e). Until
then a bare invocation prints help and exits 0.

The plugin scripts dir is resolved from ``__file__`` (NOT from
``CLAUDE_PLUGIN_ROOT``) so direct ``python3 -m planctl`` invocations from a
checkout work without the plugin runtime — the shim relies on the same
``__file__``-relative resolution.

Stdlib only.
"""
import argparse
import os
import sys


def scripts_dir():
    """Absolute path to the plugin ``scripts/`` dir (parent of this package).

    ``dirname`` twice: ``__file__`` (e.g. ``…/planctl/__main__.py``) → the
    ``planctl/`` package dir → the ``scripts/`` dir that holds siblings like
    ``lib/repo-topology.py``. Resolved from ``__file__`` — no reliance on
    ``CLAUDE_PLUGIN_ROOT`` being set.
    """
    _pkg_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(_pkg_dir)


def build_parser():
    """Construct the top-level parser + (empty) subparser scaffold.

    Every verb WILL support ``--json``; the flag is wired globally now so the
    contract is locked before any verb exists.
    """
    parser = argparse.ArgumentParser(
        prog="planctl",
        description=(
            "Unified state-layer CLI — the single write door for plan/runbook "
            "state. Markdown stays git truth; a disposable SQLite read-model "
            "makes every view fast; this CLI is the only writer."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON (every verb supports this)",
    )
    # Verbs are added as subparsers in phases 0c-0e. The scaffold exists now so
    # the dispatch shape is fixed before verbs land.
    sub = parser.add_subparsers(dest="verb", metavar="<verb>")

    # ── sync (phase 0c.1) — the freshness engine ──────────────────────────────
    sp = sub.add_parser(
        "sync",
        help="incremental reindex of plans/ into the read-model (freshness engine)",
    )
    g = sp.add_mutually_exclusive_group()
    g.add_argument("--file", metavar="F", help="reindex ONE file (PostToolUse path)")
    g.add_argument("--full", action="store_true",
                   help="drop + rebuild every derived row (corruption / DERIVE_V bump)")
    sp.add_argument("--json", action="store_true",
                    help="emit {synced, rebuilt_runbooks, watermark, elapsed_ms, full}")
    sp.set_defaults(func=_dispatch_sync)

    # ── status (phase 0c.2) — one plan's derived state ────────────────────────
    sp = sub.add_parser("status", help="derived status of ONE plan")
    sp.add_argument("plan", help="plan path (repo-relative or absolute)")
    sp.add_argument("--json", action="store_true", help="emit one-plan JSON (~100 tokens)")
    sp.set_defaults(func=_dispatch_read("status"))

    # ── brief (phase 0c.2) — session orientation ──────────────────────────────
    sp = sub.add_parser("brief", help="≤600-token session-orientation summary")
    sp.add_argument("--repo", default=None, help="filter to one repo alias")
    sp.add_argument("--runbook", default=None, help="scope to one runbook's members")
    sp.add_argument("--oneline", action="store_true",
                    help="single line (SessionStart hook)")
    sp.add_argument("--json", action="store_true", help="emit structured JSON")
    sp.set_defaults(func=_dispatch_read("brief"))

    # ── next (phase 0c.3) — ready-work, ledger-ordered ────────────────────────
    sp = sub.add_parser("next", help="ready-work (unclaimed, unblocked, in ledger order)")
    sp.add_argument("--runbook", default=None, help="scope to one runbook's members")
    sp.add_argument("--json", action="store_true", help="emit a JSON list")
    sp.set_defaults(func=_dispatch_read("next"))
    return parser


def _dispatch_sync(args):
    """Shim: import sync lazily so ``python3 -m planctl`` (help) never imports
    the DB/deriver for users who only want ``--help``."""
    from planctl import sync
    return sync.cmd_sync(args)


def _dispatch_read(verb):
    """Return a lazy shim for a read.py verb (status/brief/next)."""
    def _shim(args):
        from planctl import read
        return getattr(read, "cmd_%s" % verb)(args)
    return _shim


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    # No verbs wired yet (phases 0c-0e). The 0c+ pattern: each verb subparser
    # does ``set_defaults(func=<handler>)``; if none is set, show help + exit 0.
    # An unregistered verb is rejected by argparse (exit 2) — correct: it does
    # not exist yet.
    handler = getattr(args, "func", None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
