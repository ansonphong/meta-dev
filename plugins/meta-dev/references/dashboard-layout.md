# Dashboard Layout Spec

Layout rules for `dashboard-render.py` (the `/meta-dashboard` control plane).

## Why no emoji inside the boxes

Emoji are spec-width-2 but many renderers — including inline markdown and some
terminals — draw them at 1 cell. Box-drawing borders are always 1 cell, so any
emoji inside a bordered row shifts that row's right border out of alignment.
(That misalignment is why earlier versions fell back to flat, box-free text.)

`dashboard-render.py` therefore confines real emoji to the header line (outside
every box) and uses only **width-1-stable** glyphs inside boxes: ASCII,
box-drawing characters, geometric status dots, and the progress-bar blocks.
`dwidth()` in the renderer computes display width (emoji = 2, combining/ZWJ/VS =
0, else 1) so all padding stays exact.

## Status Dots (in-box)

| Glyph | Meaning | status key |
|-------|---------|------------|
| ● | Done / shipped | `done` |
| ◐ | In-flight / active | `inflight` |
| ○ | Pending / queued | `pending` |
| ◆ | Blocked | `blocked` |
| ◌ | Paused | `paused` |

`overlord-render.py` is a separate renderer and keeps its own emoji glyph set
(✅ 🟡 ⬜ 🔴 ⏸); it is not bound by this in-box rule.

## Box & Progress Rules

- Box style: rounded single-line (`╭ ╮ ╰ ╯ │ ─ ├ ┤`), `BOX_W = 74` cells wide.
- Each content row is `│ ` + field(`BOX_W - 4`) + ` │`; `panel()` adds the
  title row + separator.
- Progress bar: `BAR_W = 18`. Filled `█` (U+2588), empty `░` (U+2591);
  filled = round(BAR_W · done / total).
- Ratio `done/total` then percentage right-aligned to 3 digits + `%`.
- PLANS closes with a rule line and a `TOTAL` rollup across all shown plans.

## Plan Source

Plans come from `dashboard-data.sh`, which scans active plan units — directories
containing a master plan, plus loose top-level plan files — under
`plans/{app,www,gallery,meta}/`, excluding `_archive/_future/_research/_dashboard`.
Progress is derived from anchored task checkboxes (`^\s*[-*]\s*\[[ xX]\]`, so
inline prose mentions of `[ ]` are ignored). Sorted in-flight → blocked →
pending → done, then by task count; capped at 12.

## Inline Rendering

The harness collapses tool output (Ctrl+O to expand). The command echoes the
script output verbatim in a fenced code block so the dashboard shows inline.
Borders are pre-aligned — never reformat, re-wrap, or re-indent them.
