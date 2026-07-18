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
    parser.add_subparsers(dest="verb", metavar="<verb>")
    return parser


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
