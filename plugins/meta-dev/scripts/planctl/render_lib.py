#!/usr/bin/env python3
"""Shared render components for the global dashboard + boxed runbook view.

Display-width aware (emoji render as 2 terminal cells but count as 1 codepoint
in len()), box primitives, progress bars, and the canonical glyph map — ONE
source so the two views never diverge. Imported by dashboard-render.py (global
view, 2a) and the 2b boxed-view renderer.

Stdlib only.
"""
import unicodedata

# ── layout constants ──────────────────────────────────────────────────────────
BOX_W = 74            # total visible width including both borders
FIELD = BOX_W - 4     # text field inside "│ … │"
BAR_W = 18

# ── canonical glyph map (design §3.2, §3.6) ───────────────────────────────────
# Status markers use geometric/symbol glyphs, NOT emoji. Emoji are spec-width-2
# but many renderers (incl. inline markdown) draw them at 1 cell, which shifts
# every box border. These glyphs are width-1-stable, so the rounded boxes stay
# aligned everywhere.
GLYPH = {
    "draft":         "◦",
    "ready":         "▹",
    "executing":     "→",
    "needs-review":  "⊙",
    "done":          "✓",
    "blocked":       "!",
    "parked":        "‖",
    "superseded":    "⌀",
}

# Drift suffix — appended to any drift-bearing status glyph so newly introduced
# canonical statuses cannot silently hide open execution boxes.
DRIFT_SUFFIX = "⚠"

# Legacy status mapping (for backward-compatible glyph render of old status: values
# that may still appear during the M1 transition).
LEGACY_GLYPH = {"done": "✓", "blocked": "!", "active": "→", "draft": "◦"}


def status_glyph(status, drift=False):
    """Render the glyph for a derived status.

    Any drift-bearing status gets the warning suffix. A non-canon status (e.g.
    legacy ``active``) → falls back to LEGACY_GLYPH, then ``'?'``."""
    marker = GLYPH.get(status) or LEGACY_GLYPH.get(status, "?")
    return marker + DRIFT_SUFFIX if drift else marker


# ── display width ────────────────────────────────────────────────────────────
def _cw(ch):
    """Terminal cell width of one codepoint (0 for combining/ZWJ/variation
    selectors, 2 for true emoji / CJK wide, 1 otherwise)."""
    o = ord(ch)
    if o == 0x200D or 0xFE00 <= o <= 0xFE0F:      # ZWJ + variation selectors
        return 0
    if unicodedata.combining(ch):
        return 0
    if 0x1F000 <= o <= 0x1FAFF:                   # true emoji / pictographs only
        return 2
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1


def dwidth(s):
    """Display width of a string (sum of terminal cell widths)."""
    return sum(_cw(c) for c in s)


def fit(s, w):
    """Pad or truncate *s* to EXACTLY *w* display cells.

    Truncation appends ``"…"`` (1 cell) so the field stays exactly *w* cells wide."""
    if dwidth(s) > w:
        out, cur = "", 0
        for ch in s:
            cw = _cw(ch)
            if cur + cw > w - 1:
                break
            out += ch
            cur += cw
        out += "…"
        cur += 1
        return out + " " * (w - cur)
    return s + " " * (w - dwidth(s))


def col(s, n):
    """Convenience: ``fit(s, n)``."""
    return fit(s, n)


# ── box primitives ───────────────────────────────────────────────────────────
def box_top():
    return "╭" + "─" * (BOX_W - 2) + "╮"


def box_bottom():
    return "╰" + "─" * (BOX_W - 2) + "╯"


def box_sep():
    return "├" + "─" * (BOX_W - 2) + "┤"


def box_row(text=""):
    return "│ " + fit(text, FIELD) + " │"


def box_rule():
    return "│ " + "─" * FIELD + " │"


def panel(title, body):
    """Build a rounded box panel: top border, title, separator, body lines, bottom."""
    out = [box_top(), box_row(title.upper()), box_sep()]
    out += [box_row(line) for line in body] if body else [box_row("(empty)")]
    out.append(box_bottom())
    return out


# ── progress bar ─────────────────────────────────────────────────────────────
def bar(d, t):
    """Filled-block progress bar of width ``BAR_W``. 0 total → all empty."""
    if t <= 0:
        return "░" * BAR_W
    f = max(0, min(BAR_W, round(BAR_W * d / t)))
    return "█" * f + "░" * (BAR_W - f)


def pct(d, t):
    """Right-aligned percentage string. 0 total → ``"  —"``."""
    return f"{int(100 * d / t):>3d}%" if t > 0 else "  —"
