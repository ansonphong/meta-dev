#!/usr/bin/env python3
"""stage.py — ``stage`` + ``override`` + ``review`` (design §3.2, §3.4; invariant I7).

The frontmatter-writer verbs + the review-verdict producer. The first two patch
the declared-truth frontmatter (then route through ``mutate.atomic_write_md`` +
``sync.sync_one`` + ``events.append`` under ``mutate.mutation_lock``); ``review``
only appends an event (no markdown change).

  * ``cmd_stage`` — ``planctl stage <plan> <1-6|name>``: set the declared
    ``stage`` in frontmatter. Accepts BOTH names (``brainstorm|design|plan|
    harden|execute|review``) and numbers 1–6 (the name→number map ported from
    ``stage-emit.sh``, W3A-1). **NEVER writes ``status:`` or ``updated:``**
    (W3A-2 — status is DERIVED, never typed). Carries the ``exec-order-2026-06-26.md``
    skip guard (event yes, frontmatter patch no — mirrors stage-emit.sh).
  * ``cmd_override`` — ``planctl override <plan> blocked|parked|superseded
    --note "…"`` / ``override clear <plan>``: set/clear ``override:``+``note:``.
    **Schema gate (I7):** a value outside the canon is rejected with a loud
    non-zero exit.
  * ``cmd_review`` — ``planctl review <plan> pass|fail --by <who>`` (R5/W3B-1/
    DR-2): append a ``review_verdict`` event to the NEW ``events.jsonl``. The
    ONLY writer of ``review_verdict`` to the new log — the DONE-gate reads it.

Stdlib only.
"""
import json
import os
import sys

from planctl import events, mutate, statedir, sync

# Name → number (ported from stage-emit.sh's case block — W3A-1).
STAGE_NAMES = {
    "brainstorm": 1,
    "design": 2,
    "plan": 3,
    "harden": 4,
    "execute": 5,
    "review": 6,
}
STAGE_NUM_TO_NAME = {v: k for k, v in STAGE_NAMES.items()}

# Override canon (design §3.2 closed vocabulary — the schema gate enforces it).
OVERRIDE_CANON = ("blocked", "parked", "superseded")

# Status values accepted by --status. Drives the stage_state frontmatter bit:
# completed -> done, anything else (in_progress, blocked) -> active. The write is
# unconditional whenever --status is given, so a status can never inherit a stale
# stage_state from the stage it just left. For a durable halt use `override`,
# which outranks stage_state in derive precedence.
STATUS_CANON = ("in_progress", "completed", "blocked")

# Off-limits: never patch this file's frontmatter (event append still ok) —
# mirrors stage-emit.sh's GUARDED.
_GUARDED_BASENAME = "exec-order-2026-06-26.md"


# ── frontmatter patch helper ─────────────────────────────────────────────────
def _frontmatter_bounds(lines):
    """``(start, close)`` line indices of the first ``---…---`` block, or None.

    ``start`` is the opening ``---`` line; ``close`` is the closing ``---``.
    None if there is no well-formed leading block."""
    start = 0
    while start < len(lines) and lines[start].strip() == "":
        start += 1
    if start >= len(lines) or lines[start].strip() != "---":
        return None
    for i in range(start + 1, len(lines)):
        if lines[i].strip() == "---":
            return (start, i)
    return None  # unterminated


def _patch_frontmatter_keys(lines, set_map=None, remove_set=None):
    """Patch keys in the first frontmatter block; returns ``(lines, changed)``.

    ``set_map``: ``{key: value}`` to set (replace existing, or insert before the
    closing ``---``). ``remove_set``: keys to delete. ONLY the named keys are
    touched — every other line (``status:``/``updated:`` included) is preserved
    byte-for-byte (W3A-2). If no frontmatter block exists, one is created at the
    top holding the ``set_map`` keys (so stage/override are always settable)."""
    set_map = set_map or {}
    remove_set = remove_set or set()
    bounds = _frontmatter_bounds(lines)
    if bounds is None:
        # No block — create a minimal one at the top with the set keys.
        block = ["---"]
        for k, v in set_map.items():
            block.append("%s: %s" % (k, v))
        block.append("---")
        block.append("")
        return block + lines, bool(set_map)

    _start, close = bounds
    seen = set()
    out = []
    for i, line in enumerate(lines):
        if 0 < i <= close:
            stripped = line.lstrip()
            if (not stripped or stripped.startswith("#") or ":" not in stripped):
                out.append(line)
                continue
            key = stripped.split(":", 1)[0].strip()
            if key in remove_set:
                continue  # drop the line
            if key in set_map:
                indent = line[: len(line) - len(stripped)]
                out.append("%s%s: %s" % (indent, key, set_map[key]))
                seen.add(key)
                continue
        out.append(line)

    # Insert set keys that were absent, just before the closing ``---``.
    missing = [k for k in set_map if k not in seen]
    if missing:
        # ``close`` index in the original list; out has the same length so far
        # (removes == inserts-of-replacements cancel; pure removes shorten it).
        # Recompute the close line position in ``out``.
        new_close = None
        for i in range(1, len(out)):
            if out[i].strip() == "---":
                new_close = i
                break
        if new_close is not None:
            for off, k in enumerate(missing):
                out.insert(new_close + off, "%s: %s" % (k, set_map[k]))
    changed = bool(set_map) or bool(remove_set)
    return out, changed


# ── stage ────────────────────────────────────────────────────────────────────
def _resolve_stage(arg):
    """``stage_num`` for a name or 1-6, else None (schema gate rejects)."""
    s = (arg or "").strip().lower()
    if s in STAGE_NAMES:
        return STAGE_NAMES[s]
    if s in ("1", "2", "3", "4", "5", "6"):
        return int(s)
    return None


def _is_guarded(rel):
    base = rel.rsplit("/", 1)[-1] if rel else ""
    return base == _GUARDED_BASENAME


def cmd_stage(args):
    """``planctl stage <plan> <1-6|name>`` — set the declared stage (name or number)."""
    n = _resolve_stage(args.stage)
    if n is None:
        sys.stderr.write(
            "planctl stage: unknown stage %r (expected %s or 1-6)\n"
            % (args.stage, "|".join(STAGE_NAMES)))
        return 2  # usage / schema-gate style non-zero

    rel, abs_path = mutate._resolve_plan(args)
    if abs_path is None:
        if getattr(args, "json", False):
            print(json.dumps({"error": "plan_not_found", "plan": args.plan}))
        else:
            print("planctl stage: plan not found: %s" % args.plan)
        return 1

    name = STAGE_NUM_TO_NAME.get(n, "?")

    # --status <s> validation — drives stage_state in frontmatter (see mutator).
    status_val = getattr(args, "status", None)
    if status_val is not None:
        status_val = status_val.strip().lower()
        if status_val not in STATUS_CANON:
            sys.stderr.write(
                "planctl stage: invalid --status %r (expected %s)\n"
                % (status_val, "|".join(STATUS_CANON)))
            return 2

    guarded = _is_guarded(rel)
    patched = False
    if guarded:
        # exec-order skip guard: event YES, frontmatter patch NO (mirrors
        # stage-emit.sh). Still emit the event below.
        sys.stderr.write("[planctl stage] guardrail: skipping frontmatter patch "
                         "for %s\n" % rel)
    else:
        with mutate.mutation_lock(abs_path):
            # Re-read and check bounds UNDER the lock (F16 — close the TOCTOU window).
            with open(abs_path, "r", encoding="utf-8") as _f:
                _raw = _f.read()
            if _frontmatter_bounds(_raw.split("\n")) is None:
                sys.stderr.write(
                    "planctl stage: no valid frontmatter in %s — "
                    "refusing to synthesize one (add a --- … --- block first).\n" % rel)
                return 1
            def mutator(lines):
                set_map = {"stage": str(n)}
                remove_set = set()
                # The stage_state write is UNCONDITIONAL when --status is given:
                # only "completed" means the stage's work is finished; every other
                # status (in_progress, blocked) means it is still open. Omitting
                # the write would let a new stage inherit the previous stage's
                # bit -- e.g. a FAILED review (`stage-emit.sh ... review blocked`)
                # landing at stage 6 with a stale `done` and deriving "done".
                if status_val is not None:
                    set_map["stage_state"] = (
                        "done" if status_val == "completed" else "active")
                else:
                    # No status declared -> drop the key rather than carry a stale
                    # one; absent == legacy semantics (stage reached).
                    remove_set.add("stage_state")
                return _patch_frontmatter_keys(
                    lines, set_map=set_map, remove_set=remove_set)
            mutate.atomic_write_md(abs_path, mutator)
            sync.sync_one(rel)
            patched = True
            # Event append MUST be inside the lock — two concurrent stage writes
            # can otherwise interleave so markdown says stage 6 while the event
            # chronology ends at 5 (mirrors cmd_check's shape in mutate.py).
            events.append({"event": "stage", "plan": rel,
                           "data": {"stage": n, "name": name, "patched": patched,
                                    "status": status_val}})

    if guarded:
        events.append({"event": "stage", "plan": rel,
                       "data": {"stage": n, "name": name, "patched": False,
                                "status": status_val}})

    if getattr(args, "json", False):
        print(json.dumps({"stage": n, "stage_num": n, "name": name,
                          "patched": patched, "guarded": guarded}))
    else:
        print("planctl stage: %s → stage %d (%s)%s" % (
            rel, n, name, "  [frontmatter patch skipped: guarded file]"
            if guarded else ""))
    return 0


# ── override ─────────────────────────────────────────────────────────────────
def cmd_override(args):
    """``planctl override <plan> <blocked|parked|superseded> [--note "…"]``
    / ``planctl override clear <plan>`` — set/clear ``override:``+``note:``."""
    # Two invocation shapes share one subparser (plan/value positionals):
    #   override <plan> <value> [--note X]   and   override clear <plan>
    note = getattr(args, "note", None)
    if args.plan == "clear":
        plan_arg, mode = args.value, "clear"
    elif str(args.value).strip().lower() == "clear":
        plan_arg, mode = args.plan, "clear"
    else:
        plan_arg = args.plan
        value = str(args.value).strip().lower()
        if value not in OVERRIDE_CANON:
            sys.stderr.write(
                "planctl override: %r is not a canon override value (expected "
                "%s or 'clear'). Refusing — invariant I7.\n"
                % (args.value, "|".join(OVERRIDE_CANON)))
            return 2  # schema gate — loud non-zero
        mode = "set"
        canon_value = value

    rel, abs_path = mutate._resolve_plan_arg(plan_arg)
    if abs_path is None:
        if getattr(args, "json", False):
            print(json.dumps({"error": "plan_not_found", "plan": plan_arg}))
        else:
            print("planctl override: plan not found: %s" % plan_arg)
        return 1

    with mutate.mutation_lock(abs_path):
        # Re-read and check bounds UNDER the lock (F16 — close the TOCTOU window).
        with open(abs_path, "r", encoding="utf-8") as _f:
            _raw = _f.read()
        if _frontmatter_bounds(_raw.split("\n")) is None:
            sys.stderr.write(
                "planctl override: no valid frontmatter in %s — "
                "refusing to synthesize one (add a --- … --- block first).\n" % rel)
            return 1
        def mutator(lines):
            if mode == "clear":
                return _patch_frontmatter_keys(
                    lines, remove_set={"override", "note"})
            set_map = {"override": canon_value}
            if note is not None:
                set_map["note"] = note
            return _patch_frontmatter_keys(lines, set_map=set_map)
        mutate.atomic_write_md(abs_path, mutator)
        sync.sync_one(rel)

    if mode == "clear":
        events.append({"event": "override", "plan": rel,
                       "data": {"override": None, "cleared": True}})
        payload = {"override": None, "cleared": True}
    else:
        events.append({"event": "override", "plan": rel,
                       "data": {"override": canon_value, "note": note}})
        payload = {"override": canon_value, "note": note}

    if getattr(args, "json", False):
        print(json.dumps(payload))
    else:
        if mode == "clear":
            print("planctl override: cleared %s" % rel)
        else:
            print("planctl override: %s → %s%s" % (
                rel, canon_value, ("  — " + note) if note else ""))
    return 0


# ── review ───────────────────────────────────────────────────────────────────
def cmd_review(args):
    """``planctl review <plan> pass|fail --by <who>`` — append a review_verdict.

    The ONLY writer of ``review_verdict`` to the new ``events.jsonl`` (R5/W3B-1/
    DR-2). No markdown change — review is an event-only record the DONE-gate
    reads (``events.query(event='review_verdict', plan=…)``)."""
    root = statedir.project_root()
    rel = sync._normalize_arg_path(args.plan, root)
    by = getattr(args, "by", None) or os.environ.get("USER") or "unknown"
    verdict = args.verdict  # argparse choices=("pass","fail") enforces the canon
    events.append({"event": "review_verdict", "plan": rel,
                   "data": {"verdict": verdict, "by": by}})
    if getattr(args, "json", False):
        print(json.dumps({"verdict": verdict, "by": by, "plan": rel}))
    else:
        print("planctl review: %s → %s (by %s)" % (rel, verdict, by))
    return 0
