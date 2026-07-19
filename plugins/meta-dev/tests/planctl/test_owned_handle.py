#!/usr/bin/env python3
"""Handle OWNERSHIP test — a prose mention must never claim another box.

The silent-corruption guard for the ledger. ``task-done.sh`` assigned a box's
handle with a **match-anywhere** search, so a handle merely QUOTED inside some
other task's prose could claim that box. It misfired three times in one session:

  * ``T2.0`` flipped ``T2.1``
  * ``T1.4`` flipped ``T2.3``
  * ``T4.2`` reported a false "already ``[x]``" — **and exited 0** — after
    anchoring to a ``(T4.2)`` mention inside ``T1.4``'s body.

That leniency was ported into ``parse.py`` verbatim. ``_OWNED_HANDLE_RE``
anchors the match instead: a box owns only the handle ``task-stamp.py`` put at
the START of its rest-text, preceded at most by a DECORATION zone (an optional
``#hex[.N]`` bead and/or markdown emphasis/backticks). No prose word may precede
an owned handle.

Why this test matters more than most: the failure is SILENT. The wrong box gets
flipped, the command exits 0, and the plan reports progress it has not made. A
human-verify box hijacked this way would report a by-eye gate as passed that
nobody ever looked at.

Every case below is asserted to FAIL against the old match-anywhere behaviour —
see ``test_lenient_regex_would_have_hijacked``, which pins that the fixtures
genuinely exercise the bug rather than passing vacuously.
"""
import pathlib
import re

import pytest  # noqa: E402  (conftest puts scripts/ on sys.path)

from planctl import parse  # noqa: E402


def _plan(*box_lines):
    """A minimal stage-5 plan wrapping the given checkbox lines."""
    head = ["---", "stage: 5", "repo: meta", "---", "# Fixture", "", "## Build", ""]
    return "\n".join(head + list(box_lines)) + "\n"


def _by_line(text):
    """{line_no: Task} for the parsed fixture."""
    tasks, err = parse.parse_tasks(text)
    assert err is None, "fixture should parse cleanly, got: %r" % (err,)
    return {t.line_no: t for t in tasks}


# ── the hijack corpus ────────────────────────────────────────────────────────
# Each case: (id, owning box line, mentioning box line, the contested handle).
#
# The mentioning box is deliberately UNTAGGED — it carries no handle of its own
# and would otherwise fall to the text-prefix fallback. That is the real shape
# of the bug: the boxes that hijacked handles were exactly these — ``**C.1**``
# items, grep/sed verify lines, and commit steps that merely QUOTE a handle
# belonging to a sibling task. (A box with its own leading handle was never at
# risk; ``search()`` finds its own handle first.)
HIJACK_CASES = [
    (
        "bare-parenthetical",           # the real T4.2-inside-another-body misfire
        "- [ ] `T4.2` render the mask preview",
        "- [ ] wire the picker, superseding the old path (T4.2)",
        "T4.2",
    ),
    (
        "backticked-mid-prose",
        "- [ ] `T2.1` add the bulk verb",
        "- [ ] scaffold the session; depends on `T2.1` landing first",
        "T2.1",
    ),
    (
        "handle-at-end-of-prose",
        "- [ ] `T2.3` flip the ledger",
        "- [ ] document the flip protocol used by T2.3",
        "T2.3",
    ),
    (
        "verify-command-quoting-a-handle",
        "- [ ] `T3.1` add the parity corpus",
        "- [ ] verify: `grep -n 'T3.1' plans/foo.md` returns the stamped line",
        "T3.1",
    ),
    (
        "commit-step-quoting-a-handle",
        "- [ ] `T5.1` close the gate",
        "- [ ] commit: `chore(plan): flip T5.1 [arc execution]`",
        "T5.1",
    ),
    (
        "bold-subitem-quoting-a-handle",
        "- [ ] `T7.2` add the decal cache bound",
        "- [ ] **C.1** re-run the bound check described in T7.2",
        "T7.2",
    ),
]


@pytest.mark.parametrize(
    "case_id,owner_line,mention_line,handle",
    HIJACK_CASES,
    ids=[c[0] for c in HIJACK_CASES],
)
def test_prose_mention_does_not_claim_the_box(case_id, owner_line, mention_line, handle):
    """The OWNING box gets the handle; the box that merely mentions it does not."""
    text = _plan(owner_line, mention_line)
    tasks = _by_line(text)

    owner_no = 9        # first box line (1-indexed, after the 8-line header)
    mention_no = 10

    assert tasks[owner_no].tid == handle, (
        "the box that OWNS %s must resolve to it, got tid=%r"
        % (handle, tasks[owner_no].tid)
    )
    assert tasks[mention_no].tid != handle, (
        "box merely MENTIONING %s hijacked it (tid=%r) — a flip aimed at the "
        "owner would land on the wrong box and exit 0"
        % (handle, tasks[mention_no].tid)
    )


def test_owner_is_unique_so_a_flip_is_unambiguous():
    """Across the whole corpus at once, each contested handle has ONE owner.

    Exercises the real shape: many boxes in one plan, several quoting handles
    that belong to others. If any mention claimed a handle, the tid would
    collide and ``parse_tasks`` would report an ambiguity — or worse, resolve
    silently to the wrong row.
    """
    lines = []
    for _, owner, mention, _ in HIJACK_CASES:
        lines.extend([owner, mention])
    text = _plan(*lines)

    tasks, err = parse.parse_tasks(text)
    assert err is None, "corpus must parse without ambiguity, got: %r" % (err,)

    for _, _, _, handle in HIJACK_CASES:
        owners = [t for t in tasks if t.tid == handle]
        assert len(owners) == 1, (
            "handle %s resolved to %d boxes (%r) — a flip would be ambiguous"
            % (handle, len(owners), [t.text for t in owners])
        )


# ── the DECORATION zone still counts as ownership ────────────────────────────
# These must KEEP working: task-stamp.py emits beads and markdown emphasis
# before the handle, and those boxes genuinely own it.
OWNED_FORMS = [
    ("plain", "- [ ] T6.1 by-eye gate", "T6.1"),
    ("backticks", "- [ ] `T6.1` by-eye gate", "T6.1"),
    ("bead-then-handle", "- [ ] #a1b2 `T6.1` by-eye gate", "T6.1"),
    ("dotted-bead-then-handle", "- [ ] #629a.1 `T6.1` by-eye gate", "T6.1"),
    ("bold", "- [ ] **T6.1** by-eye gate", "T6.1"),
    ("alnum-phase", "- [ ] `T6a.1` by-eye gate", "T6a.1"),
]


@pytest.mark.parametrize(
    "form_id,line,handle", OWNED_FORMS, ids=[f[0] for f in OWNED_FORMS]
)
def test_decoration_prefix_still_owns_the_handle(form_id, line, handle):
    """A bead and/or markdown emphasis before the handle does not break ownership."""
    tasks = _by_line(_plan(line))
    tid_or_alias = {tasks[9].tid, tasks[9].alias}
    assert handle in tid_or_alias, (
        "%s form lost its handle: tid=%r alias=%r"
        % (form_id, tasks[9].tid, tasks[9].alias)
    )


def test_human_verify_gate_cannot_be_hijacked():
    """The worst case, stated explicitly: a by-eye gate flipped by a prose mention.

    A human-verify box reports a gate only a person can close. If a prose
    mention could claim it, an automated flip aimed elsewhere would mark the
    gate passed with nobody having looked — and exit 0.
    """
    text = _plan(
        "- [ ] `T6.1` verify by eye: TilePreview overlay modes",
        "- [ ] archive the plan once T6.1 passes",
    )
    tasks = _by_line(text)

    assert tasks[9].tid == "T6.1"
    assert tasks[10].tid != "T6.1", (
        "the archive box hijacked the by-eye gate's handle — flipping T6.1 "
        "would silently close a gate no human ever ran"
    )
    assert tasks[9].human_verify, "fixture should register as a human-verify box"


# ── proof the fixtures are not vacuous ───────────────────────────────────────

def test_lenient_regex_would_have_hijacked():
    """Every hijack fixture genuinely exercises the bug.

    Re-runs the OLD match-anywhere pattern over each mentioning box and asserts
    it DOES claim the contested handle. Without this, a future edit could
    weaken the fixtures into prose that never contained a handle at all, and
    the tests above would pass while testing nothing.
    """
    lenient = re.compile(r"`?T([A-Za-z0-9]+)\.(\d+)`?")   # the pre-fix behaviour

    for case_id, _, mention_line, handle in HIJACK_CASES:
        rest = parse._CHECKBOX_RE.match(mention_line).group(4)
        m = lenient.search(rest)
        assert m is not None, (
            "%s: fixture no longer contains a handle mention — it cannot "
            "exercise the hijack" % case_id
        )
        claimed = "T%s.%s" % (m.group(1), m.group(2))
        assert claimed == handle, (
            "%s: the old lenient regex would have claimed %s, not the "
            "contested %s — fixture does not reproduce the bug"
            % (case_id, claimed, handle)
        )


def test_patch_is_present_in_this_parse_module():
    """Guard against the fix being silently reverted by a plugin update.

    The fix lived only in the install cache for three sessions and was wiped
    twice. If ``_OWNED_HANDLE_RE`` is gone, every test above may still pass
    against a stale import — so assert the anchored pattern exists here.
    """
    assert hasattr(parse, "_OWNED_HANDLE_RE"), (
        "_OWNED_HANDLE_RE is missing from planctl.parse — the owned-handle fix "
        "has been reverted; a prose mention can hijack a box again"
    )
    assert parse._OWNED_HANDLE_RE.pattern.startswith("^"), (
        "_OWNED_HANDLE_RE must be ANCHORED; an unanchored pattern reintroduces "
        "the match-anywhere hijack"
    )


def test_real_corpus_parses_without_handle_ambiguity():
    """Smoke the fix against this repo's own plans, if any are present.

    Not a strict gate — the plugin repo may ship no plans. When plans exist,
    every one must parse without a duplicate-handle ambiguity error, which is
    what a hijack looks like at scale.
    """
    root = pathlib.Path(__file__).resolve().parents[3]
    plans = sorted(root.glob("plans/**/*.md"))[:40]
    if not plans:
        pytest.skip("no plans/ corpus in this repo")

    for p in plans:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        _tasks, err = parse.parse_tasks(text)
        if err and "duplicate legacy" in err:
            pytest.fail("handle ambiguity in %s: %s" % (p, err))
