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


# ══ CARD STANDARD ════════════════════════════════════════════════════════════
# The open-right card chassis. See references/status-cards.md for the doctrine.
#
# Why open-right: emoji are double-width, so ANY right-hand border drifts and can
# never be reliably aligned. Dropping that border is what makes emoji safe in
# every card — it is load-bearing, not decoration. The older rounded box below
# (BOX_W/box_*/panel) had to ban emoji precisely because it kept a right border.

CARD_W = 74               # total visible width of the top/bottom rules
CARD_FIELD = CARD_W - 2   # open-right: only the "│ " prefix is reserved
BAR_FILL, BAR_EMPTY = "█", "░"

# ── the ONE status vocabulary ────────────────────────────────────────────────
# Replaces derive.GLYPHS, derive.EMOJI, render_lib.GLYPH, the dashboard inline
# fallback, and overlord's status_icon/verdict_icon. status -> (glyph, label).
STATUS = {
    "done":         ("✅", "done"),
    "executing":    ("🔄", "running"),
    "draft":        ("⏸",  "queued"),
    "ready":        ("⏸",  "queued"),
    "needs-review": ("⏳", "awaiting verdict"),
    "gated":        ("🔒", "human gate"),
    "blocked":      ("⛔", "blocked"),
    "parked":       ("⏺",  "paused"),
    "superseded":   ("🚫", "superseded"),
    "missing":      ("❓", "missing"),
}
DRIFT = "⚠️"     # suffix, never a status of its own
UNKNOWN = "❔"


def mark(status, drift=False):
    """Glyph for a status. Unknown status → UNKNOWN, never a KeyError."""
    g = STATUS.get(status, (UNKNOWN, "unknown"))[0]
    return g + DRIFT if drift else g


def label(status):
    """Human word for a status. Unknown → ``'unknown'``."""
    return STATUS.get(status, (UNKNOWN, "unknown"))[1]


# ── open-right chassis ───────────────────────────────────────────────────────
def card_top(title="", w=CARD_W):
    """``┌─ TITLE ────…`` — rule length uses dwidth() so an emoji in the title
    still yields exactly *w* cells."""
    if not title:
        return "┌" + "─" * (w - 1)
    head = "┌─ " + title + " "
    return head + "─" * max(0, w - dwidth(head))


def card_sep(label=None, w=CARD_W):
    """``├─ LABEL ───…`` section divider, or a plain rule when *label* is None."""
    if not label:
        return "├" + "─" * (w - 1)
    head = "├─ " + label + " "
    return head + "─" * max(0, w - dwidth(head))


def card_bottom(w=CARD_W):
    return "└" + "─" * (w - 1)


def card_row(text="", indent=0):
    """A card row. Always rstrip()ed — with no right border there is nothing to
    pad to, and trailing whitespace is what markdown renderers and copy/paste
    silently eat."""
    return ("│ " + " " * indent + text).rstrip()


def card_rule():
    """An in-card horizontal rule."""
    return "│ " + "─" * CARD_FIELD


def cols(cells, widths):
    """Join *cells* into an aligned row. Every cell EXCEPT the last is fit() to
    its width; the last is left free, so a wide glyph there costs nothing."""
    if not cells:
        return ""
    out = [fit(str(c), w) for c, w in zip(cells[:-1], widths)]
    out.append(str(cells[-1]))
    return " ".join(out)


def card(title, sections):
    """Build a full card. *sections* = ``[(label|None, [lines]), …]``.

    The first section's label is omitted (the title already heads the card)."""
    out = [card_top(title)]
    for i, (lbl, lines) in enumerate(sections):
        if lbl and i > 0:
            out.append(card_sep(lbl))
        elif i > 0:
            out.append(card_sep())
        out += [card_row(ln) for ln in lines] if lines else [card_row("(empty)")]
    out.append(card_bottom())
    return out


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
def bar(d, t, width=BAR_W):
    """Filled-block progress bar. 0 total → all empty.

    *width* is a parameter so the three historical bars (18-cell dashboard,
    10-cell overlord, 4-cell ``▰▱`` runbook) collapse onto ONE implementation
    and one pair of glyphs."""
    if width <= 0:
        return ""
    if t <= 0:
        return BAR_EMPTY * width
    f = max(0, min(width, round(width * d / t)))
    return BAR_FILL * f + BAR_EMPTY * (width - f)


def bar_frac(frac, width=BAR_W):
    """Bar from an already-computed fraction in [0,1] — for call sites that hold
    a percentage rather than a (done, total) pair."""
    return bar(round(max(0.0, min(1.0, frac)) * 1000), 1000, width)


def pct(d, t):
    """Right-aligned percentage string. 0 total → ``"  —"``."""
    return f"{int(100 * d / t):>3d}%" if t > 0 else "  —"
