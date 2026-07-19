#!/usr/bin/env python3
"""parse.py — markdown truth → rows (the parser the 0c indexer calls).

Pure functions, NO DB. Produces the rows the SQLite read-model is built from:
  * ``parse_frontmatter(text) -> (data, raw_status)`` — flat YAML-subset reader
    (stdlib only — hand-rolled, NEVER imports yaml). Coerces ``stage`` to int
    (non-int → 0, never TypeError), accepts block AND inline sequences, canon-
    validates ``override`` read-side, and tolerates legacy ``status:``/``updated:``
    during the M1 transition (captured / discarded, never re-stored as derived).
  * ``parse_tasks(text) -> (list[Task], parse_err)`` — checkbox parser with the
    DUAL id scheme: canonical beads ``#hex`` (flip-stable content hash) AND legacy
    ``T3.2`` handles as aliases, plus a text-prefix fallback for untagged boxes.
    ``human_verify`` ports ``task-done.sh``'s regexes VERBATIM.
  * ``kind_of(text, fm, path)`` — plan | runbook (``type: runbook``) | ledger
    (basename ``meta-runbook.md``).

Invariants I1 (frontmatter = declared truth; status never re-stored), I7 (schema
gate read-side: non-canon override → parse_err, never KeyError).

Stdlib only.
"""
import hashlib
import re

# ── regexes ──────────────────────────────────────────────────────────────────
# Checkbox line: indent · bullet · mark · rest. Same family as task-stamp.py /
# task-done.sh. ``checked`` ≡ mark in ('x','X') explicitly — a whitespace-only or
# other mark is NOT checked (VC-7).
_CHECKBOX_RE = re.compile(r"^(\s*)([-*])\s+\[([ xX])\]\s*(.*)$")

# Beads canonical tag: ``#a3f8`` (exactly 4 hex), optional ``.N`` (collision
# suffix OR hierarchical subtask — ``.N`` is overloaded per design §3.1; both
# forms accepted). Negative lookahead so a 6-hex color ``#aabbcc`` is NOT
# mis-parsed as ``#aabb``.
_BEAD_RE = re.compile(r"#([0-9a-fA-F]{4})(?![0-9a-fA-F])(\.(\d+))?")

# Legacy handle: ``T3.2`` / `` `T3.2` `` — accepted as an alias. Used for
# STRIPPING handle text out of the normalize_rest() fallback, where matching
# anywhere is correct and harmless.
_HANDLE_RE = re.compile(r"`?T([A-Za-z0-9]+)\.(\d+)`?")

# ...but IDENTIFYING the handle a box OWNS is a different question, and the
# lenient form is wrong for it. task-done.sh used to assign a box's handle with
# a match-anywhere search, so a handle quoted in ANOTHER task's prose could
# claim the box. It misfired three times in one session (T2.0 flipped T2.1,
# T1.4 flipped T2.3, and T4.2 reported a false "already [x]" — exit 0! — after
# anchoring to a "(T4.2)" mention inside T1.4's body). That leniency was ported
# here verbatim; this is where it stops.
#
# A box owns the handle that task-stamp.py anchored at the START of its
# rest-text, preceded only by a DECORATION zone: an optional bead/stamp id
# (which may carry dots, e.g. ``#629a.1``) and/or markdown emphasis/backticks.
# No prose word may precede an owned handle.
#
# Calibrated against the full plans/ corpus (44,319 checkbox lines): 4,940 boxes
# match, and every box that does NOT genuinely owns no handle (``**C.1**``
# items, grep/sed verify lines, commit steps) — several of which merely MENTION
# a handle in prose, which is exactly the hijack this prevents.
_OWNED_HANDLE_RE = re.compile(
    r"^(?:#[0-9A-Za-z][0-9A-Za-z.\-]*\s+)?[*_~`]{0,3}T([A-Za-z0-9]+)\.(\d+)(?![A-Za-z0-9.])"
)

# Human-verify regexes — ported VERBATIM from task-done.sh (W1-C1; do NOT
# reinvent). tag_re matches on the box rest-text; sec_re matches on the NEAREST
# PRECEDING heading (first-heading-decides, G0b-7).
_TAG_RE = re.compile(r"(by\s+eye|by\s+hand|gpu|manual)", re.I)
_SEC_RE = re.compile(r"(acceptance|by\s+eye|by\s+hand|gpu|manual|human[-\s]*verify)", re.I)

# Markdown heading (1-6 #'s) — nearest-preceding section for a box.
_HEADING_RE = re.compile(r"^(?:[ \t]{0,3})(#{1,6})\s+(.+?)\s*#*\s*$")

# Override canon values (design §3.2 closed vocabulary).
_OVERRIDE_CANON = ("blocked", "parked", "superseded")

# List-valued frontmatter keys that accept BOTH inline ``[a,b]`` AND block
# ``- a`` sequences (G-IMP2 — plan-index's inline-only parser silently drops
# block sequences; we union both).
_LIST_KEYS = ("depends", "blocks", "context", "docs", "members")


# ── frontmatter (flat YAML subset) ───────────────────────────────────────────
def _strip_comment(val):
    """Drop a trailing `` # comment`` (not inside quotes/brackets). Mirrors
    plan-index.py so frontmatter parity holds."""
    in_s = in_d = in_b = False
    for i, ch in enumerate(val):
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif ch == "[" and not in_s and not in_d:
            in_b = True
        elif ch == "]" and not in_s and not in_d:
            in_b = False
        elif ch == "#" and not in_s and not in_d and not in_b:
            if i == 0 or val[i - 1] in " \t":
                return val[:i]
    return val


def _parse_scalar(val):
    val = val.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        return val[1:-1]
    return val


def _parse_inline_list(val):
    """Inline flow ``[a, b, c]`` -> ``['a','b','c']``; ``[]`` -> ``[]``; non-list
    -> ``None`` (caller decides scalar/block handling)."""
    val = _strip_comment(val).strip()
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(p) for p in inner.split(",") if p.strip()]
    return None


def _coerce_stage(val):
    """``stage`` -> int; non-int (``?``/blank/None) -> ``0``.

    NEVER raises (G0b-3**: a ``?`` or blank stage is treated as 0/draft, not a
    TypeError). Trailing ``# comment`` stripped first — parity with
    plan-index.py's ``_parse_value`` (a live ``stage: 6  # EXECUTED`` must
    parse as 6, never coerce to 0)."""
    s = _parse_scalar(_strip_comment(val)).strip()
    if s == "":
        return 0
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0


def parse_frontmatter(text):
    """Parse a leading ``---`` frontmatter block (flat YAML subset, stdlib only).

    Returns ``(data, raw_status)``:
      * ``data`` — dict of declared facts: ``stage`` (int, coerced), ``repo``,
        ``override`` (canon-validated), ``note``, ``why``, ``type``, and list
        keys ``depends``/``blocks``/``context``/``docs``/``members`` (inline OR
        block sequences unioned). On a read-side schema violation (non-canon
        ``override``) ``data['parse_err']`` is set (never raised).
      * ``raw_status`` — the legacy ``status:`` value if present, captured so
        M1's migration can read it; NEVER written to ``plans.derived_status``
        (that field is derived-only — I1). ``None`` when absent.

    Malformed frontmatter (unclosed block) -> ``data={'parse_err': ...}``,
    ``raw_status=None``. Never raises.
    """
    lines = text.split("\n")
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i >= len(lines) or lines[i].strip() != "---":
        return {}, None
    start = i + 1
    end = None
    for j in range(start, len(lines)):
        if lines[j].strip() == "---":
            end = j
            break
    if end is None:
        return {"parse_err": "unclosed frontmatter block (no closing ---)"}, None

    data = {}
    raw_status = None
    parse_err = None
    block_key = None  # currently-accumulating block-sequence key (G-IMP2)

    for line in lines[start:end]:
        raw = line.rstrip("\n")
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            block_key = None
            continue

        # Block-sequence continuation: an indented ``- item`` under a list key.
        if block_key is not None and (stripped.startswith("- ") or stripped == "-"):
            item_raw = stripped[2:].strip() if stripped.startswith("- ") else ""
            data.setdefault(block_key, [])
            if isinstance(data[block_key], list) and item_raw:
                data[block_key].append(_parse_scalar(item_raw))
            continue

        # Any other line ends block-sequence accumulation.
        block_key = None

        if ":" not in raw:
            continue
        key, _, val = raw.partition(":")
        key = key.strip()
        if not key:
            continue

        if key == "status":
            # Legacy status — captured for M1, NEVER stored as derived (I1).
            raw_status = _parse_scalar(_strip_comment(val)) or None
            continue
        if key == "updated":
            # Legacy updated — read-then-discard (time truth = git + events).
            continue
        if key == "stage":
            data["stage"] = _coerce_stage(val)
            continue
        if key == "override":
            ov = _parse_scalar(_strip_comment(val)).strip()
            if ov and ov not in _OVERRIDE_CANON:
                # Non-canon override — record parse_err (G0b-6), never raise /
                # never a KeyError downstream (glyph() renders '?').
                parse_err = "override %r not in canon %r" % (ov, list(_OVERRIDE_CANON))
            data["override"] = ov or None
            continue
        if key in _LIST_KEYS:
            raw_val = _strip_comment(val).strip()
            if raw_val == "":
                data[key] = []
                block_key = key  # following ``- item`` lines accumulate here
                continue
            if raw_val.lower() == "none":
                data[key] = None  # explicitly no paths
                continue
            inline = _parse_inline_list(val)
            if inline is not None:
                data[key] = inline
                continue
            # Single scalar item (block seq may extend it on following lines).
            data[key] = [_parse_scalar(raw_val)]
            block_key = key
            continue

        # default scalar key (repo, note, why, type, title, ...) — comment-
        # stripped like every plan-index _parse_value read (parity).
        data[key] = _parse_scalar(_strip_comment(val))

    if parse_err:
        data["parse_err"] = parse_err
    return data, raw_status


# ── stable-id helpers ────────────────────────────────────────────────────────
def normalize_rest(rest):
    """Normalized rest-text for ``#hex`` hashing + text-prefix fallback.

    Strip any ``#hex`` bead + any ``T3.2`` handle, collapse all whitespace,
    casefold. ``rest`` is post-mark (indent+bullet+mark already removed by
    ``_CHECKBOX_RE``). Flip-stable: identical rest → identical hash regardless of
    ``[ ]`` vs ``[x]`` (G-IMP1)."""
    r = _BEAD_RE.sub("", rest)
    r = _HANDLE_RE.sub("", r)
    r = " ".join(r.split())  # collapse runs of whitespace to single spaces
    return r.casefold()


def compute_hex(rest):
    """Beads ``#hex`` = ``sha1(normalize_rest(rest))[:4]``. Flip-stable (G-IMP1).

    Exposed so ``planctl stamp`` (0d) assigns the SAME id a box would hash to;
    identical rest-text → identical ``#hex`` (collision suffix ``.N`` is appended
    in file order at stamp time — stable + monotonic + never reassigned, W2D-8)."""
    return hashlib.sha1(normalize_rest(rest).encode("utf-8")).hexdigest()[:4]


# ── checkbox parser ──────────────────────────────────────────────────────────
class Task:
    """One checkbox row. Mirrors the ``tasks`` table columns (minus plan_path)."""
    __slots__ = ("tid", "alias", "line_no", "checked", "human_verify",
                 "section", "text")

    def __init__(self, tid, alias, line_no, checked, human_verify, section, text):
        self.tid = tid              # canonical: '#hex' / legacy: 'T3.2' / fallback: text-prefix
        self.alias = alias          # legacy 'T3.2' when tid is a '#hex' bead (else None)
        self.line_no = line_no      # 1-indexed
        self.checked = checked      # bool (mark in x/X)
        self.human_verify = human_verify  # bool (tag_re on rest OR sec_re on nearest heading)
        self.section = section      # nearest preceding heading text
        self.text = text            # rest-text (post-mark; tags preserved)

    def __repr__(self):
        return ("Task(tid=%r, alias=%r, line=%d, checked=%s, human=%s, sec=%r)"
                % (self.tid, self.alias, self.line_no, self.checked,
                   self.human_verify, self.section))


def parse_tasks(text):
    """Parse checkbox lines → ``(list[Task], parse_err)``.

    Each ``- [ ]``/``- [x]`` line becomes a ``Task`` with a resolved ``tid``:
      1. canonical ``#hex`` bead if present (with ``.N`` suffix preserved),
      2. else legacy ``T3.2`` handle,
      3. else a text-prefix fallback (``normalize_rest``).

    A box carrying BOTH ``#hex`` and ``T3.2`` → ``tid=#hex`` with ``alias=T3.2``
    (G0b-4 alias map). ``parse_err`` is set (``None`` on success) when:
      * a duplicate ``#hex`` bead appears in the file (G0b-4),
      * two untagged boxes collide on the same text-prefix fallback (ambiguous),
      * a duplicate legacy ``T3.2``-only handle appears (ambiguous alias).
    ``human_verify`` flags boxes whose rest matches ``_TAG_RE`` OR whose nearest
    preceding heading matches ``_SEC_RE`` (both ported verbatim from
    ``task-done.sh``). Never raises.
    """
    lines = text.split("\n")
    tasks = []
    parse_err = None
    seen_beads = {}    # bead_id -> line_no (G0b-4 dup detection)
    seen_prefix = {}   # text-prefix tid -> line_no (ambiguity)
    seen_handle = {}   # legacy handle tid -> line_no (ambiguous alias)

    current_section = ""
    for idx, line in enumerate(lines):
        hm = _HEADING_RE.match(line)
        if hm:
            current_section = hm.group(2).strip()
            continue
        m = _CHECKBOX_RE.match(line)
        if not m:
            continue
        mark = m.group(3)
        rest = m.group(4)
        checked = mark in ("x", "X")

        # Extract bead (#hex[.N]) and legacy handle (T3.2) from rest.
        bead_id = None
        handle_id = None
        bm = _BEAD_RE.search(rest)
        if bm:
            bead_id = "#" + bm.group(1).lower() + (bm.group(2) or "")
        # ANCHORED, not search(): only the handle this box OWNS may identify it.
        # A prose mention of another task's handle must never claim the box.
        hm2 = _OWNED_HANDLE_RE.match(rest)
        if hm2:
            handle_id = "T%s.%s" % (hm2.group(1), hm2.group(2))

        # tid resolution: bead > handle > text-prefix fallback (G-IMP3).
        alias = None
        if bead_id:
            tid = bead_id
            if handle_id:
                alias = handle_id
        elif handle_id:
            tid = handle_id
        else:
            tid = normalize_rest(rest)

        # Duplicate / ambiguity detection (parse_err is sticky once set).
        if bead_id:
            if bead_id in seen_beads:
                parse_err = parse_err or "duplicate #hex bead %s at lines %d and %d" % (
                    bead_id, seen_beads[bead_id], idx + 1)
            else:
                seen_beads[bead_id] = idx + 1
        elif handle_id:
            if handle_id in seen_handle:
                parse_err = parse_err or "duplicate legacy handle %s at lines %d and %d" % (
                    handle_id, seen_handle[handle_id], idx + 1)
            else:
                seen_handle[handle_id] = idx + 1
        else:
            if tid in seen_prefix:
                parse_err = parse_err or ("ambiguous untagged box (identical rest-text) "
                                          "at lines %d and %d — tag with #hex or T3.2" % (
                                              seen_prefix[tid], idx + 1))
            else:
                seen_prefix[tid] = idx + 1

        # human_verify: tag on rest OR nearest heading matches sec_re (G0b-7).
        human = bool(_TAG_RE.search(rest)) or bool(_SEC_RE.search(current_section or ""))

        tasks.append(Task(tid, alias, idx + 1, checked, human, current_section, rest))

    return tasks, parse_err


def count_split(tasks):
    """Split a parsed task list into the two count families (design §3.2/§3.3).

    Returns ``(tasks_done, tasks_total, human_open, human_total, raw_done,
    raw_total)`` where:
      * ``tasks_*`` — EXECUTION-only (non-human-verify) boxes; the derive inputs.
      * ``human_*`` — human-verify boxes, tracked separately (excluded from
        execution math; R2/VC-1).
      * ``raw_*`` — ALL boxes (parity columns; parity compares RAW only).

    Hierarchical ``#hex.N`` child tags are returned by ``parse_tasks`` (they are
    real addressable boxes) but DISTINCT-leaf dedup / container-vs-leaf rollup is
    realized by the 0c indexer that consumes these counts — ``Task`` carries no
    ``is_leaf`` field and counting is the indexer's responsibility (the parser
    only produces rows).
    """
    tasks_done = tasks_total = 0
    human_open = human_total = 0
    raw_done = raw_total = 0
    for t in tasks:
        raw_total += 1
        if t.checked:
            raw_done += 1
        if t.human_verify:
            human_total += 1
            if not t.checked:
                human_open += 1
        else:
            tasks_total += 1
            if t.checked:
                tasks_done += 1
    return tasks_done, tasks_total, human_open, human_total, raw_done, raw_total


# ── file classification ──────────────────────────────────────────────────────
def kind_of(text, fm, path=""):
    """Classify a file → ``'plan'`` | ``'runbook'`` | ``'ledger'`` (design §4).

    * ``ledger`` iff ``path`` basename == ``meta-runbook.md``.
    * ``runbook`` iff ``fm['type'] == 'runbook'`` (frontmatter-based, NOT
      filename — design §4).
    * ``plan`` otherwise.

    ``path`` is needed for ledger detection (basename match); defaults to ``""``
    (then only plan/runbook detection applies). ``text`` is accepted for
    signature stability but unused (runbook-ness is frontmatter-driven)."""
    base = path.rsplit("/", 1)[-1] if path else ""
    if base == "meta-runbook.md":
        return "ledger"
    if isinstance(fm, dict) and fm.get("type") == "runbook":
        return "runbook"
    return "plan"
