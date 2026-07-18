#!/usr/bin/env python3
"""tasks.py — ``stamp`` + ``task add`` (design §3.4; invariant I7).

The checkbox lifecycle verbs. Both route through ``mutate.atomic_write_md`` +
``sync.sync_one`` + ``events.append`` (under ``mutate.mutation_lock``).

  * ``cmd_stamp`` — ``planctl stamp <plan>``: add ``#hex`` beads to UNTAGGED
    checkbox lines. The bead = ``parse.compute_hex(rest)`` (4-hex content hash,
    flip-stable). Collision-checked per file: on a hash collision (a second box
    hashing to the same 4-hex) a disambiguating ``.N`` suffix is appended in
    file order. **The collision suffix is STABLE across re-stamps (W2D-8):**
    existing beads are NEVER reassigned — re-running stamp is idempotent (no
    double-tags, no renumber). A box with only a legacy ``T3.2`` handle gets a
    ``#hex`` ADDED alongside (the handle is preserved as an alias). A box
    already carrying ``#hex`` is skipped.
  * ``cmd_task_add`` — ``planctl task add <plan> "<text>" [--section S]``:
    append a BORN-TAGGED box (a fresh ``#hex`` immediately, collision-aware) at
    the section end (or EOF); return the new ``tid`` in ``--json``.

This is the planctl successor to ``task-stamp.py``; the legacy script stays
until M3 (planctl tolerates both id forms — see ``parse._BEAD_RE``/``_HANDLE_RE``).

Stdlib only.
"""
import json
import os

from planctl import events, mutate, parse, statedir, sync
from planctl.parse import _BEAD_RE, _CHECKBOX_RE


def _existing_beads(lines):
    """Set of every ``#hex[.N]`` bead already present in the file (lowercased).

    Pre-scanned so stamp/task-add assign collision-stable suffixes without
    reusing an existing bead (W2D-8)."""
    text = "\n".join(lines)
    out = set()
    for m in _BEAD_RE.finditer(text):
        out.add("#" + m.group(1).lower() + (m.group(2) or ""))
    return out


def _assign_bead(hex4, existing):
    """The next free bead for ``hex4``: base ``#hex`` if free, else ``#hex.N``.

    Monotonic ``.N`` in file order; existing beads are never reassigned (W2D-8).
    Mutates ``existing`` (adds the assigned bead) so successive collisions in the
    same pass keep climbing."""
    base = "#" + hex4
    if base not in existing:
        existing.add(base)
        return base
    n = 1
    while "%s.%d" % (base, n) in existing:
        n += 1
    bead = "%s.%d" % (base, n)
    existing.add(bead)
    return bead


# ── stamp ────────────────────────────────────────────────────────────────────
def cmd_stamp(args):
    """``planctl stamp <plan>`` — add stable ``#hex`` beads to untagged boxes."""
    rel, abs_path = mutate._resolve_plan(args)
    if abs_path is None:
        if getattr(args, "json", False):
            print(json.dumps({"error": "plan_not_found", "plan": args.plan}))
        else:
            print("planctl stamp: plan not found: %s" % args.plan)
        return 1

    with mutate.mutation_lock(abs_path):
        stamped = []
        collisions = []

        def mutator(lines):
            existing = _existing_beads(lines)
            for idx, line in enumerate(lines):
                m = _CHECKBOX_RE.match(line)
                if not m:
                    continue
                rest = m.group(4)
                if _BEAD_RE.search(rest):
                    continue  # already tagged — skip (idempotent, W2D-8)
                hex4 = parse.compute_hex(rest)  # normalize_rest strips handles
                bead = _assign_bead(hex4, existing)
                if "." in bead[1:]:
                    collisions.append(bead)
                # place the bead at the START of the rest (after the mark).
                new_rest = bead + (" " + rest if rest else "")
                lines[idx] = line[:m.start(4)] + new_rest + line[m.end(4):]
                stamped.append(bead)
            return lines, stamped

        mutate.atomic_write_md(abs_path, mutator)

        if stamped:
            sync.sync_one(rel)
            events.append({"event": "stamp", "plan": rel,
                           "data": {"count": len(stamped), "beads": stamped}})

    if getattr(args, "json", False):
        print(json.dumps({"stamped": stamped, "collisions": collisions}))
    else:
        if stamped:
            print("planctl stamp: tagged %d box(es)" % len(stamped))
            for b in stamped:
                print("  %s%s" % (b, "  (collision suffix)" if "." in b[1:] else ""))
        else:
            print("planctl stamp: no untagged boxes (idempotent)")
    return 0


# ── task add ─────────────────────────────────────────────────────────────────
def _section_insert_at(lines, section):
    """Line index to insert a new box at: end of ``section``, else EOF.

    If ``section`` is given, find its heading (1-6 #'s, case-insensitive
    substring) then the NEXT same-or-higher heading (or EOF); back up over
    trailing blank lines so the box lands as the section's last item. If the
    heading is absent or ``section`` is None, append at EOF."""
    if not section:
        return len(lines)
    head_re = None
    start = None
    for i, line in enumerate(lines):
        s = line.lstrip()
        if s.startswith("#"):
            HM = _heading_match(s, section)
            if HM:
                level = len(s) - len(s.lstrip("#"))
                head_re = (level, i)
                start = i
                break
    if start is None:
        return len(lines)
    level, _ = head_re
    # next heading at same-or-higher level (<= level) after the section heading.
    end = len(lines)
    for j in range(start + 1, len(lines)):
        s = lines[j].lstrip()
        if s.startswith("#"):
            lv = len(s) - len(s.lstrip("#"))
            if lv <= level:
                end = j
                break
    # back up over trailing blank lines.
    at = end
    while at > start + 1 and lines[at - 1].strip() == "":
        at -= 1
    return at


def _heading_match(heading_line, section):
    """True if a ``# heading`` line's title matches ``section`` (case-insensitive
    substring on the title text)."""
    s = heading_line.lstrip("#").strip().rstrip("#").strip()
    return section.lower() in s.lower()


def cmd_task_add(args):
    """``planctl task add <plan> "<text>" [--section S]`` — append a born-tagged box."""
    rel, abs_path = mutate._resolve_plan(args)
    if abs_path is None:
        if getattr(args, "json", False):
            print(json.dumps({"error": "plan_not_found", "plan": args.plan}))
        else:
            print("planctl task add: plan not found: %s" % args.plan)
        return 1

    text = args.text.strip()
    with mutate.mutation_lock(abs_path):
        bead = None

        def mutator(lines):
            nonlocal bead
            existing = _existing_beads(lines)
            hex4 = parse.compute_hex(text)
            bead = _assign_bead(hex4, existing)
            at = _section_insert_at(lines, getattr(args, "section", None))
            new_line = "- [ ] %s %s" % (bead, text)
            lines.insert(at, new_line)
            return lines, bead

        mutate.atomic_write_md(abs_path, mutator)
        sync.sync_one(rel)
        events.append({"event": "task_add", "plan": rel,
                       "data": {"tid": bead, "text": text}})

    if getattr(args, "json", False):
        print(json.dumps({"tid": bead}))
    else:
        print("planctl task add: %s → %s" % (text, bead))
    return 0
