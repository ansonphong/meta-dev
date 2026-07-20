#!/usr/bin/env python3
"""Smoke-bullet counter — the structural replacement for prose-sniffed by-eye boxes.

The critical property under test is NEGATIVE: a heading that merely *contains*
the word "smoke" must NOT reclassify its execution boxes. Across the indexed
corpus — the population this parser actually sees — 47 such headings span 29
plan files, and they look like "### Task C — Smoke + parent plan (no code)".
A substring match would silently drop real work out of the progress math: the
same failure mode _TAG_RE already exhibits.
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace

from planctl import doctor, parse, sync  # noqa: E402  (conftest puts scripts/ on sys.path)


def test_smoke_bullets_counted_and_excluded_from_exec():
    text = "\n".join([
        "## Smoke Test",
        "- render a tile and eyeball the fog",
        "- check depth VALUES not just checker alignment",
        "",
        "## Task 1",
        "- [ ] `T1.1` write the thing",
    ])
    assert parse.parse_smoke(text) == 2
    tasks, _err = parse.parse_tasks(text)
    td, tt, _ho, _ht, _rd, _rt = parse.count_split(tasks)
    assert (td, tt) == (0, 1), "smoke bullets must never enter execution counts"


def test_smoke_heading_is_exact_not_substring():
    """REGRESSION GUARD: the whole point of the exact match.

    NOTE the PLAIN BULLETS below. They are the load-bearing part of this test.
    `_SMOKE_BULLET_RE` rejects checkboxes unconditionally, so a corpus of only
    `- [ ]` lines makes `parse_smoke(text) == 0` trivially true — the assertion
    would hold even if a noncanonical heading DID wrongly enter smoke mode, and
    the test could never fail for the reason it exists. The plain bullets are
    what actually distinguish "the heading was rejected" from "the bullets were
    rejected".
    """
    text = "\n".join([
        "### Task C — Smoke + parent plan (no code)",
        "- this plain bullet must NOT be counted",
        "- neither must this one",
        "- [ ] `T2.1` real execution work",
        "",
        "## Residual risk / smoke only",
        "- another uncounted plain bullet",
        "- [ ] `T2.2` more real execution work",
    ])
    assert parse.parse_smoke(text) == 0, (
        "plain bullets under a NONCANONICAL heading must not enter the smoke count"
    )
    tasks, _err = parse.parse_tasks(text)
    _td, tt, _ho, _ht, _rd, _rt = parse.count_split(tasks)
    assert tt == 2, "ordinary headings containing 'smoke' must not reclassify work"


def test_smoke_variants_and_checkbox_immunity():
    """A stray checkbox under a smoke heading is not a smoke bullet — but it must
    NOT fall through to the execution math either, or the heading re-opens the
    exact 98% trap this phase exists to close. It is classified HUMAN.

    Also pins all three valid Markdown unordered-list markers (`-`, `*`, `+`)
    and the 0-3 space top-level indent window."""
    text = "\n".join([
        "## Smoke",
        "- one",
        " * two (one leading space is still top-level)",
        "   + three (three spaces is the last valid top-level indent)",
        "### Smoke Tests",
        "- four",
        "    - NOT counted: four spaces is a code line / nested sub-bullet",
        "- [ ] `T3.1` a checkbox under a smoke heading is NOT a smoke bullet",
    ])
    assert parse.parse_smoke(text) == 4
    tasks, _err = parse.parse_tasks(text)
    _td, tt, _ho, ht, _rd, _rt = parse.count_split(tasks)
    assert tt == 0, "a box under a smoke heading must never enter execution counts"
    assert ht == 1, "it is human-verify work, not execution work"


def test_smoke_section_ends_at_equal_or_shallower_heading():
    """Depth-aware section end: a DEEPER heading is a subsection of the smoke
    section and does NOT end it; an EQUAL-or-SHALLOWER heading does.

    T1.4 tells authors to add a `## Smoke Test` section, and people naturally
    structure a long one with `###` subsections. Terminating on *any* heading
    would silently undercount exactly the plans that documented themselves best.
    """
    text = "\n".join([
        "## Smoke Test",
        "- counted",
        "### Depth pass",          # deeper -> still inside the smoke section
        "- counted too",
        "#### Fog check",          # deeper still
        "- also counted",
        "## Notes",                # equal depth -> section ends
        "- not counted",
        "### Sub of Notes",
        "- not counted either",
    ])
    assert parse.parse_smoke(text) == 3


def test_smoke_heading_inside_fence_is_not_a_section():
    """REGRESSION GUARD: plans routinely show `## Smoke Test` as a fenced example
    (this phase file does it in T1.3). Without a fence toggle the plan indexes its
    own illustration as live smoke bullets."""
    text = "\n".join([
        "Example of the shape:",
        "```markdown",
        "## Smoke Test",
        "- illustrative only",
        "- also illustrative",
        "- [ ] `T9.9` illustrative checkbox only",
        "```",
    ])
    assert parse.parse_smoke(text) == 0
    tasks, _err = parse.parse_tasks(text)
    assert tasks == [], "fenced checkbox examples must not become execution tasks"


def test_no_smoke_section():
    assert parse.parse_smoke("## Task 1\n- [ ] `T1.1` x") == 0


def test_doctor_warns_only_on_near_miss_headings_with_plain_bullets(capsys):
    root = Path(os.environ["META_DEV_ROOT"])
    plan = root / "plans/meta/2026-01-01-smoke-near-misses.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("\n".join([
        "---",
        "stage: 3",
        "repo: meta",
        "---",
        "# Plan",
        "## Manual smoke",
        "- warn about this near miss",
        "## Smoke Test",
        "- canonical, so no warning",
        "## Task C — Smoke + parent plan",
        "- warn about this near miss too",
        "## Smoke notes with boxes only",
        "- [ ] `T1.1` a checkbox is not a smoke bullet",
        "```markdown",
        "## Fenced smoke example",
        "- illustrative only",
        "```",
    ]), encoding="utf-8")

    assert sync.cmd_sync(SimpleNamespace(full=True, file=None, json=True)) == 0
    capsys.readouterr()
    assert doctor.cmd_doctor(SimpleNamespace(json=True)) == 0
    payload = json.loads(capsys.readouterr().out)

    warnings = payload["smoke_near_miss"]
    # "Task C — Smoke + parent plan" is deliberately NOT flagged: it is a task
    # heading that merely contains the word, and that family (e.g. the real
    # "Task 3: Smoke test with the offline preview tool (dry-run)") is what
    # drowned this advisory in false positives — 19 warnings of which 16 were
    # titles or sentences. See doctor._is_smoke_label.
    assert [(w["line"], w["heading"]) for w in warnings] == [
        (6, "Manual smoke"),
    ]


# ── doctor near-miss discrimination (advisory precision) ─────────────────────
from planctl import doctor  # noqa: E402


def test_near_miss_label_accepts_short_headings_at_any_depth():
    """Short headings are plausible smoke-section labels."""
    assert doctor._is_smoke_label(2, "Manual smoke")
    assert doctor._is_smoke_label(3, "7.6 Frontend manual smoke")
    assert doctor._is_smoke_label(2, "Smoke Tests:")
    assert doctor._is_smoke_label(4, "Residual risk / smoke only")


def test_near_miss_label_covers_h1_because_parse_smoke_does():
    """Depth must NOT filter: parse_smoke honours a canonical heading at any
    depth, so an H1 near-miss names a section the parser would have accepted.
    Excluding H1 would leave exactly that case unwarned."""
    assert parse._SMOKE_HEAD_RE.match("Smoke Test")     # parser accepts it...
    assert parse.parse_smoke("# Smoke Test\n- a\n- b") == 2   # ...even as H1
    assert doctor._is_smoke_label(1, "Smoke Tests")     # ...so the advisory must too


def test_near_miss_label_rejects_titles_and_sentences():
    """The two false-positive families that made the advisory unreadable.

    Both always carry plain bullets somewhere beneath them, so the has-bullet
    check cannot filter them — length is what discriminates. Every observed
    false positive was long; every genuine label was short.
    """
    assert not doctor._is_smoke_label(
        1, "Comprehensive Pipeline Render Smoke Suite — Master Plan")
    assert not doctor._is_smoke_label(
        1, "Phase 4: Verification — Full Suite, Manual Smoke, Context Sync")
    assert not doctor._is_smoke_label(
        3, "Task 3: Smoke test with the offline preview tool (dry-run)")
    assert not doctor._is_smoke_label(
        2, "Phase A — P0 Backend Criticals (block smoke test)")
