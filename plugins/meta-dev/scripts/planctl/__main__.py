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

    # ── check / uncheck (phase 0d.1) — flip checkboxes ────────────────────────
    sp = sub.add_parser("check", help="flip [ ] → [x] for one or more task ids")
    sp.add_argument("plan", help="plan path (repo-relative or absolute)")
    sp.add_argument("tids", nargs="+", metavar="tid", help="task id (#hex / T3.2 / text)")
    sp.add_argument("--human", action="store_true",
                    help="allow flipping a by-eye/gpu/manual box")
    sp.add_argument("--force", action="store_true", help="alias of --human")
    sp.add_argument("--verify", metavar="CMD", default=None,
                    help='run CMD (explicit cwd, 300s) first; abort all flips unless it exits 0')
    sp.add_argument("--by", default=None, help="who flipped (default $USER)")
    sp.add_argument("--json", action="store_true",
                    help="emit {flipped, skipped, verified}")
    sp.set_defaults(func=_dispatch_module("mutate", "cmd_check"))

    sp = sub.add_parser("uncheck", help="flip [x] → [ ] for one or more task ids")
    sp.add_argument("plan", help="plan path (repo-relative or absolute)")
    sp.add_argument("tids", nargs="+", metavar="tid", help="task id (#hex / T3.2 / text)")
    sp.add_argument("--human", action="store_true", help="allow flipping a human-verify box")
    sp.add_argument("--force", action="store_true", help="alias of --human")
    sp.add_argument("--by", default=None, help="who flipped (default $USER)")
    sp.add_argument("--json", action="store_true", help="emit {flipped, skipped, verified}")
    sp.set_defaults(func=_dispatch_module("mutate", "cmd_uncheck"))

    # ── stamp / task add (phase 0d.2) — checkbox lifecycle ─────────────────────
    sp = sub.add_parser("stamp", help="add stable #hex beads to untagged checkboxes")
    sp.add_argument("plan", help="plan path (repo-relative or absolute)")
    sp.add_argument("--json", action="store_true", help="emit {stamped, collisions}")
    sp.set_defaults(func=_dispatch_module("tasks", "cmd_stamp"))

    sp = sub.add_parser("task", help="task lifecycle (add …)")
    sub_task = sp.add_subparsers(dest="task_verb", metavar="<sub>")
    sp_add = sub_task.add_parser("add", help="append a born-tagged checkbox")
    sp_add.add_argument("plan", help="plan path (repo-relative or absolute)")
    sp_add.add_argument("text", help="the checkbox text (gets a fresh #hex)")
    sp_add.add_argument("--section", default=None, help="heading to append under (default: EOF)")
    sp_add.add_argument("--json", action="store_true", help="emit {tid}")
    sp_add.set_defaults(func=_dispatch_module("tasks", "cmd_task_add"))

    # ── stage / override / review (phase 0d.2) — frontmatter writers ──────────
    sp = sub.add_parser("stage", help="set declared stage (name or 1-6) in frontmatter")
    sp.add_argument("plan", help="plan path (repo-relative or absolute)")
    sp.add_argument("stage", help="brainstorm|design|plan|harden|execute|review or 1-6")
    sp.add_argument("--json", action="store_true", help="emit {stage, stage_num}")
    sp.set_defaults(func=_dispatch_module("stage", "cmd_stage"))

    sp = sub.add_parser(
        "override",
        help="set/clear override (blocked|parked|superseded) in frontmatter")
    # Both forms share one subparser: ``override <plan> <value> [--note]`` and
    # ``override clear <plan>`` (detected by plan == "clear" in cmd_override).
    sp.add_argument("plan", help="plan path, OR the literal 'clear'")
    sp.add_argument("value", help="blocked|parked|superseded, OR the plan (clear form)")
    sp.add_argument("--note", default=None, help="override note (set form only)")
    sp.add_argument("--json", action="store_true", help="emit {override, note}")
    sp.set_defaults(func=_dispatch_module("stage", "cmd_override"))

    sp = sub.add_parser("review", help="record a review verdict (pass|fail) in the event log")
    sp.add_argument("plan", help="plan path (repo-relative or absolute)")
    sp.add_argument("verdict", choices=("pass", "fail"), help="review outcome")
    sp.add_argument("--by", default=None, help="reviewer (default $USER)")
    sp.add_argument("--json", action="store_true", help="emit {verdict, by}")
    sp.set_defaults(func=_dispatch_module("stage", "cmd_review"))

    # ── runbook (phase 0e.1 + 2b) — membership, render, boxed view ────────────
    # Flat parser with REMAINDER — argparse subparsers ALWAYS validate choices
    # when a positional is present (even required=False), so we can't use nested
    # subparsers for a bare ``runbook <path>`` form. REMAINDER captures everything
    # after ``--json``; the router (_dispatch_runbook_router) detects "add"/
    # "render" subcommands vs a bare runbook path (R22 — ONE spelling).
    sp = sub.add_parser("runbook", help="runbook membership + boxed view + render")
    sp.add_argument("--json", action="store_true",
                    help="emit structured JSON (boxed view)")
    sp.add_argument("runbook_args", nargs=argparse.REMAINDER, default=None,
                    help=argparse.SUPPRESS)
    sp.set_defaults(func=_dispatch_runbook_router)

    # ── claim / release / list (phase 0d.3) — work-claim registry ─────────────
    sp = sub.add_parser("claim", help="claim a plan/dir scope (blocks overlapping claims)")
    sp.add_argument("plan", help="scope to claim (plan path or dir)")
    sp.add_argument("--pid", type=int, default=None, help="process id (default $PID)")
    sp.add_argument("--session", default=None, help="session id (default $CLAUDE_SESSION_ID)")
    sp.add_argument("--ttl", type=int, default=None, help="claim TTL seconds (default 1800)")
    sp.add_argument("--json", action="store_true", help="emit {scope, session, pid}")
    sp.set_defaults(func=_dispatch_module("claims", "cmd_claim"))

    sp = sub.add_parser("release", help="release a claimed scope")
    sp.add_argument("plan", help="scope to release")
    sp.add_argument("--json", action="store_true", help="emit {scope, released}")
    sp.set_defaults(func=_dispatch_module("claims", "cmd_release"))

    sp = sub.add_parser("list", help="list live work-claims (field names pinned for jq)")
    sp.add_argument("--json", action="store_true", help="emit [{scope, session, pid, …}]")
    sp.set_defaults(func=_dispatch_module("claims", "cmd_list"))

    # ── ledger check/shipped (phase 0e.2) — ledger ⇄ reality ───────────────────
    sp = sub.add_parser("ledger", help="ledger-as-projection tools (check + shipped)")
    sub_ledger = sp.add_subparsers(dest="ledger_verb", metavar="<sub>")
    sp_chk = sub_ledger.add_parser(
        "check", help="diff the human ledger vs the index")
    sp_chk.add_argument("--json", action="store_true",
                        help="emit {unregistered, dead, marker_drift, …}")
    sp_chk.set_defaults(func=_dispatch_module("ledger", "cmd_ledger_check"))

    sp_shp = sub_ledger.add_parser(
        "shipped", help="regenerate a compact ## Shipped index (stdout unless --write)")
    sp_shp.add_argument("--write", action="store_true",
                        help="write the section (backup + per-entry gate)")
    sp_shp.set_defaults(func=_dispatch_module("ledger", "cmd_ledger_shipped"))

    # ── doctor (phase 0e.3) — integrity sweep + auto-heal ──────────────────────
    sp = sub.add_parser("doctor", help="integrity sweep + auto-heal (cycles/9p/derive_v)")
    sp.add_argument("--json", action="store_true",
                    help="emit {ok, integrity, derive_v, cycles, missing, …}")
    sp.set_defaults(func=_dispatch_module("doctor", "cmd_doctor"))
    return parser


def _dispatch_runbook_router(args):
    """Route ``planctl runbook`` — subcommand or bare boxed view.

    argparse subparsers always validate choices when a positional is present,
    so we use REMAINDER + manual routing. ``args.runbook_args`` is the list
    of tokens after ``runbook`` (minus ``--json`` which the parent parser
    consumes). ``args.json`` is True when ``--json`` appeared before the
    positional args.

    Subcommands:
      ``planctl runbook add <rb> <member> [--json]``
      ``planctl runbook render <rb> [--json]``

    Bare form (boxed view, phase 2b):
      ``planctl runbook <path> [--json]``
    """
    ra = args.runbook_args or []
    is_json = getattr(args, "json", False)

    # ``--json`` may land in REMAINDER when it appears after the first positional
    if "--json" in ra:
        is_json = True
        ra = [a for a in ra if a != "--json"]

    if not ra:
        print("planctl runbook: expected 'add', 'render', or a runbook path.",
              file=sys.stderr)
        print("  planctl runbook <path>            boxed campaign view",
              file=sys.stderr)
        print("  planctl runbook add <rb> <m>      add a member",
              file=sys.stderr)
        print("  planctl runbook render <rb>        write progress block",
              file=sys.stderr)
        return 1

    verb = ra[0]

    if verb == "add":
        if len(ra) < 3:
            print("planctl runbook add: expected <rb> and <member> args.",
                  file=sys.stderr)
            return 1
        from types import SimpleNamespace as _SN
        from planctl import runbook as _runbook
        return _runbook.cmd_runbook_add(_SN(rb=ra[1], member=ra[2], json=is_json))

    elif verb == "render":
        if len(ra) < 2:
            print("planctl runbook render: expected <rb> arg.", file=sys.stderr)
            return 1
        from types import SimpleNamespace as _SN
        from planctl import runbook as _runbook
        return _runbook.cmd_runbook_render(_SN(rb=ra[1], json=is_json))

    else:
        # verb is the runbook path → boxed view
        from types import SimpleNamespace as _SN
        from planctl import view as _view
        return _view.cmd_runbook_boxed(_SN(rb_path=verb, json=is_json))


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


def _dispatch_module(module, func):
    """Return a lazy shim for a verb in ``mutate``/``tasks``/``stage``/``claims``.

    Lazy so ``python3 -m planctl --help`` never imports the DB/deriver/events
    stack; the verb's module is imported only when the verb actually runs."""
    def _shim(args):
        mod = __import__("planctl." + module, fromlist=[module])
        return getattr(mod, func)(args)
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
