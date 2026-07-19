#!/usr/bin/env python3
"""Golden-table test for derive.py — the ONE status interpreter (design §10 item 1).

Regression-locks the ``completed != done`` class: a stage-5 plan with all
EXECUTION boxes done derives ``needs-review``, NOT ``done`` (the bug that read
0% on the control plane while its code was already in the tree).

Axes: ``(stage, exec_done, exec_total, human_open, override) -> (status, drift)``.
``human_open`` is a table axis specifically to PROVE human-verify boxes never
enter ``derive_plan`` (G0b-2): they are excluded by the caller before these
counts are passed in, so the same exec counts derive the same status whether or
not human boxes are open.
"""
import os

import pytest  # noqa: E402  (conftest puts scripts/ on sys.path)

from planctl import derive, parse  # noqa: E402


def _derive(stage, exec_done, exec_total, override=None):
    fm = {"stage": stage}
    if override:
        fm["override"] = override
    return derive.derive_plan(fm, exec_done, exec_total)


# ── the golden table ─────────────────────────────────────────────────────────
# (id, stage, exec_done, exec_total, human_open, override, exp_status, exp_drift)
GOLDEN = [
    # rule 6 — stage <= 2, no exec boxes -> draft
    ("draft-stage1",            1, 0, 0, 0, None,         "draft",        False),
    ("draft-stage2",            2, 0, 0, 0, None,         "draft",        False),
    # rule 5 — stage 3-5, exec_total==0 -> ready (VC-ACK: human-only/review-only)
    ("ready-stage3-empty",      3, 0, 0, 0, None,         "ready",        False),
    ("ready-stage4-empty",      4, 0, 0, 0, None,         "ready",        False),
    ("ready-stage5-empty",      5, 0, 0, 0, None,         "ready",        False),
    # G0b-2 axis: human boxes open do NOT change the exec-derived status.
    ("ready-stage5-human-open", 5, 0, 0, 3, None,         "ready",        False),
    # rule 3 — all exec done at stage<6 -> needs-review (beats rule 5)
    ("needs-review-stage3-all-done", 3, 5, 5, 0, None,    "needs-review", False),
    ("needs-review-stage4-all-done", 4, 5, 5, 0, None,    "needs-review", False),
    # *** REGRESSION: completed != done. stage5 + all-exec-done -> needs-review,
    #     NOT done (old status:completed read as done -> 0% bug). ***
    ("REGRESSION-completed-not-done", 5, 5, 5, 0, None,   "needs-review", False),
    # G0b-2 mandatory row: human-only-open (all exec done) at stage5 -> needs-review
    ("needs-review-stage5-human-open", 5, 5, 5, 2, None,  "needs-review", False),
    # rule 4 — some exec done, some open -> executing
    ("executing-stage4",        4, 2, 5, 0, None,         "executing",    False),
    ("executing-stage5",        5, 2, 5, 0, None,         "executing",    False),
    # rule 2 — stage>=6 -> done. drift iff open EXEC boxes remain.
    ("done-stage6-empty",       6, 0, 0, 0, None,         "done",         False),
    ("done-stage6-all-done",    6, 5, 5, 0, None,         "done",         False),
    # G0b-2 mandatory row: stage6 + human-only-open -> done, NO drift
    ("done-stage6-human-open",  6, 5, 5, 3, None,         "done",         False),
    # *** DRIFT row: stage6 + open EXEC boxes -> done + drift=True ***
    ("DRIFT-stage6-open-exec",  6, 3, 5, 0, None,         "done",         True),
    ("drift-stage6-open-exec-human", 6, 3, 5, 2, None,    "done",         True),
    # rule 1 — override wins, drift suppressed (even at stage6 with open boxes)
    ("override-blocked-stage5-done",  5, 5, 5, 0, "blocked",    "blocked",    False),
    ("override-blocked-stage6-open",  6, 3, 5, 0, "blocked",    "blocked",    False),
    ("override-parked",                6, 0, 0, 0, "parked",     "parked",     False),
    ("override-superseded",            3, 0, 0, 0, "superseded", "superseded", False),
]


# ── stage_state axis (Phase 2) ──────────────────────────────────────────────
# (id, stage, exec_done, exec_total, override, stage_state, exp_status, exp_drift)
GOLDEN_STAGE_STATE = [
    # THE FIX: stage6 + active review is NOT done.
    ("stage6-active-review",       6, 5, 5, None, "active", "needs-review", False),
    ("stage6-done-explicit",       6, 5, 5, None, "done",   "done",         False),
    # BACKWARD COMPAT: absent must derive exactly today's behavior.
    ("stage6-absent-is-legacy",    6, 5, 5, None, None,     "done",         False),
    # drift still reported while actively reviewing with open exec boxes.
    ("stage6-active-open-exec",    6, 3, 5, None, "active", "needs-review", True),
    ("stage6-done-open-exec",      6, 3, 5, None, "done",   "done",         True),
    # override still wins over everything (rule 1 precedence unchanged).
    ("override-beats-stage-state", 6, 5, 5, "parked", "active", "parked",  False),
    # stages 1-5 are UNAFFECTED by stage_state (render-only signal there).
    ("stage4-done-still-ready",    4, 0, 0, None, "done",   "ready",        False),
    ("stage4-active-still-ready",  4, 0, 0, None, "active", "ready",        False),
    ("stage5-done-needs-review",   5, 5, 5, None, "done",   "needs-review", False),
    # unknown/garbage stage_state is ignored, not fatal.
    ("stage6-garbage-ignored",     6, 5, 5, None, "wat",    "done",         False),
]


@pytest.mark.parametrize(
    "tid,stage,ed,et,override,stage_state,exp_status,exp_drift",
    GOLDEN_STAGE_STATE,
    ids=[r[0] for r in GOLDEN_STAGE_STATE],
)
def test_derive_stage_state(tid, stage, ed, et, override, stage_state,
                            exp_status, exp_drift):
    fm = {"stage": stage}
    if override:
        fm["override"] = override
    if stage_state is not None:
        fm["stage_state"] = stage_state
    assert derive.derive_plan(fm, ed, et) == (exp_status, exp_drift)


@pytest.mark.parametrize(
    "stage,exec_done,exec_total,human_open,override,exp_status,exp_drift",
    [(r[1], r[2], r[3], r[4], r[5], r[6], r[7]) for r in GOLDEN],
    ids=[r[0] for r in GOLDEN],
)
def test_golden_derive_plan(stage, exec_done, exec_total, human_open, override,
                            exp_status, exp_drift):
    status, drift = _derive(stage, exec_done, exec_total, override)
    assert status == exp_status, (
        "stage=%s exec=%s/%s human_open=%s override=%s -> status %r, want %r"
        % (stage, exec_done, exec_total, human_open, override, status, exp_status))
    assert drift == exp_drift, (
        "stage=%s exec=%s/%s -> drift %r, want %r"
        % (stage, exec_done, exec_total, drift, exp_drift))


# ── mandatory single-row assertions (named so a failure names the class) ──────
def test_regression_completed_not_done():
    """The completed!=done bug: stage5 + all exec done -> needs-review, never done."""
    status, drift = _derive(5, 5, 5)
    assert status == "needs-review"
    assert drift is False


def test_rule3_beats_rule5():
    """stage3 + all-exec-done -> needs-review (rule 3 beats rule 5's ready)."""
    assert _derive(3, 5, 5)[0] == "needs-review"


def test_drift_row():
    """stage6 with open EXEC boxes -> done + drift (rendered '✓⚠')."""
    status, drift = _derive(6, 3, 5)
    assert status == "done"
    assert drift is True
    assert derive.glyph("done", drift=True) == "✓⚠"


def test_override_suppresses_drift():
    """override + stage6 + open exec boxes -> override wins, drift suppressed."""
    status, drift = _derive(6, 3, 5, override="blocked")
    assert status == "blocked"
    assert drift is False


def test_human_open_is_invisible_to_derive_plan():
    """G0b-2: derive_plan takes exec-only counts; human_open is not even a param.
    All-exec-done derives needs-review (stage5) / done-no-drift (stage6) regardless
    of how many human boxes are open (they're excluded by the caller)."""
    assert _derive(5, 5, 5) == ("needs-review", False)
    assert _derive(6, 5, 5) == ("done", False)


def test_exec_total_zero_derives_ready_indefinitely():
    """VC-ACK: a human-only/review-only plan (exec_total==0) derives ready (stage
    3-5) / draft (stage<=2) forever — nothing to execute."""
    assert _derive(4, 0, 0) == ("ready", False)
    assert _derive(2, 0, 0) == ("draft", False)


# ── glyph + pct helpers ───────────────────────────────────────────────────────
def test_glyph_map_closed_vocabulary():
    assert derive.glyph("draft") == "◦"
    assert derive.glyph("ready") == "▹"
    assert derive.glyph("executing") == "→"
    assert derive.glyph("needs-review") == "⊙"
    assert derive.glyph("done") == "✓"
    assert derive.glyph("blocked") == "!"
    assert derive.glyph("parked") == "‖"
    assert derive.glyph("superseded") == "⌀"
    assert derive.glyph("done", drift=True) == "✓⚠"
    # non-canon (bogus override that slipped past parse) -> '?', never KeyError
    assert derive.glyph("bogus") == "?"
    with pytest.raises(KeyError):
        derive.GLYPHS["bogus"]  # the raw map still KeyErrors; glyph() is the safe door


def test_pct_bankers_round_matches_plan_index():
    """pct = round(100*done/total) (banker's) — parity-bound to plan-index.py:154.

    NOT int truncation: done=2,total=3 -> 67 (not 66); done=3,total=8 -> 38 (not 37).
    Banker's (the parity-binding choice): round(12.5)==12 for done=1,total=8 — the
    spec's prose example '-> 13' is round-HALF-UP and would BREAK plan-index parity,
    so banker's wins (locked here)."""
    assert derive.pct(0, 0) == 0
    assert derive.pct(5, 5) == 100
    assert derive.pct(2, 3) == 67          # round(66.67)=67 ; int()=66
    assert derive.pct(3, 8) == 38          # round(37.5)=38 (banker's->even) ; int()=37
    assert derive.pct(1, 8) == 12          # banker's: round(12.5)=12 (== plan-index.py)
    assert derive.pct(1, 8) == round(100 * 1 / 8)


def test_derive_v_is_two():
    assert derive.DERIVE_V == 2


# ── parse -> derive integration (the fixture mini-plan) ───────────────────────
def test_parse_then_derive_completed_not_done_regression():
    """End-to-end: parse the fixture mini-plan (stage5, status:completed, all exec
    boxes done, one human box open under an Acceptance heading) -> count exec-only
    -> derive -> needs-review. This is the completed!=done class proven through
    the real parser, not just numeric inputs."""
    fixture = os.path.join(os.path.dirname(__file__), "fixtures",
                           "completed-not-done.md")
    with open(fixture, encoding="utf-8") as fh:
        text = fh.read()

    fm, raw_status = parse.parse_frontmatter(text)
    assert raw_status == "completed"          # legacy status captured (NOT derived)
    assert "parse_err" not in fm
    assert fm["stage"] == 5

    tasks, perr = parse.parse_tasks(text)
    assert perr is None
    td, tt, ho, ht, rd, rt = parse.count_split(tasks)
    assert (td, tt) == (3, 3)                 # 3 EXEC boxes, all done
    assert (ho, ht) == (1, 1)                 # 1 human-verify box, open
    assert (rd, rt) == (3, 4)                 # 3 of 4 raw boxes checked

    status, drift = derive.derive_plan(fm, td, tt)
    assert (status, drift) == ("needs-review", False)
    assert derive.glyph(status, drift) == "⊙"


def test_trailing_comment_stripped_on_scalar_keys():
    """Parity with plan-index _parse_value: a trailing ``# comment`` on scalar
    keys never corrupts the value (review finding, phase-0b gate — a live
    ``stage: 6  # EXECUTED ...`` must derive done, not draft)."""
    text = (
        "---\n"
        "stage: 6            # EXECUTED 2026-07-09\n"
        "repo: app           # the desktop repo\n"
        "override: blocked  # waiting on GPU box\n"
        "status: completed  # legacy note\n"
        "---\n"
    )
    fm, raw_status = parse.parse_frontmatter(text)
    assert fm["stage"] == 6
    assert fm["repo"] == "app"
    assert fm["override"] == "blocked"
    assert "parse_err" not in fm
    assert raw_status == "completed"
    status, drift = derive.derive_plan(fm, 0, 0)
    assert status == "blocked"  # override wins; no bogus 'blocked  # note' value
