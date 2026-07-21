#!/usr/bin/env python3
"""Invariant tests for the open-right card chassis (references/status-cards.md).

These lock the two properties that make the chassis safe, both of which are easy
to break by accident:

1. **Rules are exactly CARD_W cells** — computed with dwidth(), not len(), so an
   emoji in a title or section label cannot shorten the rule.
2. **No row ever ends in whitespace** — with no right border there is nothing to
   pad to, and trailing whitespace is silently eaten by markdown renderers and
   copy/paste, which would make cards look ragged in exactly the places they are
   most read.

Plus a closed-vocabulary guard: every status derive.py can produce must have a
glyph, so a newly added status can never render blank.
"""
from planctl import derive
from planctl import render_lib as R


# ── rules are exactly CARD_W cells ───────────────────────────────────────────
def test_card_top_is_exactly_card_w():
    assert R.dwidth(R.card_top("EXECUTION REPORT")) == R.CARD_W


def test_card_top_untitled_is_exactly_card_w():
    assert R.dwidth(R.card_top()) == R.CARD_W


def test_card_bottom_is_exactly_card_w():
    assert R.dwidth(R.card_bottom()) == R.CARD_W


def test_card_sep_is_exactly_card_w_labelled_and_plain():
    assert R.dwidth(R.card_sep("Tasks")) == R.CARD_W
    assert R.dwidth(R.card_sep()) == R.CARD_W


def test_emoji_in_title_does_not_shorten_the_rule():
    """The whole point of measuring with dwidth(): a double-width glyph in the
    title must consume two cells of the rule, not one."""
    assert R.dwidth(R.card_top("✅ DONE")) == R.CARD_W
    assert R.dwidth(R.card_sep("🔄 Running")) == R.CARD_W


# ── no trailing whitespace, ever ─────────────────────────────────────────────
def test_card_row_never_has_trailing_whitespace():
    for text in ["", "short", "  padded  ", "trailing tabs\t\t"]:
        row = R.card_row(text)
        assert row == row.rstrip(), f"trailing whitespace in {row!r}"


def test_full_card_has_no_trailing_whitespace_on_any_line():
    lines = R.card("ORCHESTRATION", [
        (None, ["✅ T1  done", "🔄 T2  running"]),
        ("Gates", ["🔒 T5  held for your opt-in"]),
        ("Empty", []),
    ])
    for ln in lines:
        assert ln == ln.rstrip(), f"trailing whitespace in {ln!r}"


def test_card_row_starts_with_the_prefix_even_with_emoji_tail():
    assert R.card_row("✅ T1  facetPick→tilePick").startswith("│ ")


def test_card_row_indent():
    # "│ " prefix (2 cells) + 4 indent spaces, then the text
    assert R.card_row("x", indent=4) == "│     x"


def test_card_rule_is_not_double_wrapped_as_a_body_line():
    """card() wraps body lines with card_row(); an already-prefixed line like
    card_rule() must pass through, or it emits '│ │ ────'. Two independent
    renderer migrations hit this, so the guard lives in card(), not in callers."""
    lines = R.card("X", [(None, ["row", R.card_rule(), "row2"])])
    assert not any(ln.startswith("│ │") for ln in lines), lines


# ── clip: the open-right chassis has no border to truncate against ───────────
def test_clip_truncates_to_field_width():
    long = "x" * 200
    assert R.dwidth(R.clip(long)) <= R.CARD_FIELD


def test_clip_leaves_short_strings_alone_and_rstrips():
    assert R.clip("short") == "short"
    assert R.clip("short   ") == "short"


def test_clip_is_emoji_safe():
    """Truncation must count display cells, not codepoints."""
    assert R.dwidth(R.clip("✅" * 100, 20)) <= 20


def test_clipped_row_never_exceeds_the_card():
    row = R.card_row(R.clip("parked — indefinitely deferred " * 10))
    assert R.dwidth(row) <= R.CARD_W


# ── columns: last cell is free ───────────────────────────────────────────────
def test_cols_fits_all_but_the_last_cell():
    """The last cell is deliberately unpadded so a wide glyph there costs
    nothing — that is what makes the open-right chassis emoji-safe."""
    row = R.cols(["T1", "rename", "✅"], [4, 10])
    assert row.startswith("T1   ")          # fit to 4
    assert row.endswith("✅")               # last cell untouched, unpadded
    assert row == row.rstrip()


def test_cols_empty():
    assert R.cols([], []) == ""


# ── closed vocabulary ────────────────────────────────────────────────────────
def test_status_covers_every_derivable_status():
    """Every status derive.py can emit must have a glyph, or it renders blank."""
    required = set(derive.PLAN_STATUSES) | set(derive.OVERRIDES)
    missing = required - set(R.STATUS)
    assert not missing, f"statuses with no glyph: {sorted(missing)}"


def test_mark_never_raises_on_unknown_status():
    assert R.mark("no-such-status") == R.UNKNOWN
    assert R.label("no-such-status") == "unknown"


def test_drift_is_a_suffix_not_a_status():
    assert R.mark("done") == "✅"
    assert R.mark("done", drift=True) == "✅" + R.DRIFT
    assert "drift" not in R.STATUS


def test_queued_states_share_a_glyph():
    """draft and ready both read as 'queued' — a deliberate collapse."""
    assert R.mark("draft") == R.mark("ready") == "⏸"
    assert R.label("draft") == "queued"


# ── progress bar ─────────────────────────────────────────────────────────────
def test_bar_uses_only_the_two_canonical_glyphs_at_exact_width():
    for width in (4, 10, 18):
        b = R.bar(2, 3, width)
        assert len(b) == width
        assert set(b) <= {R.BAR_FILL, R.BAR_EMPTY}


def test_bar_zero_total_is_all_empty():
    assert R.bar(0, 0, 10) == R.BAR_EMPTY * 10


def test_bar_full_and_clamped():
    assert R.bar(3, 3, 10) == R.BAR_FILL * 10
    assert R.bar(99, 3, 10) == R.BAR_FILL * 10   # clamped, never overflows


def test_bar_frac_matches_bar():
    assert R.bar_frac(0.5, 10) == R.bar(1, 2, 10)
    assert R.bar_frac(0.0, 10) == R.BAR_EMPTY * 10
    assert R.bar_frac(1.0, 10) == R.BAR_FILL * 10
