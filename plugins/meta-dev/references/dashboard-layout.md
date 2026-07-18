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

## Status Glyphs (in-box)

Keyed on the plan-index status enum (`dashboard-render.py` `GLYPH`):

| Glyph | Meaning | status key |
|-------|---------|------------|
| ✓ | Done / shipped | `done` |
| → | Active / in-flight | `active` |
| ! | Blocked | `blocked` |
| ◦ | Draft / queued | `draft` |

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

> **planctl-backed (M2a).** `dashboard-data.sh` now calls `planctl sync` + SQL for
> the plan index; `plan-index.py` delegates to planctl. The dashboard is runbook-aware:
> campaign members render grouped under indented runbook headers with rollup bars, and
> `=== RUNBOOK ===` markers in `plans/meta-runbook.md` are honored.

Plans come from `plan-index.py` (the single source of truth), which the
`dashboard-data.sh` gatherer invokes and reshapes. The tracked set is the
ordered `plans/…md` list under the `## Sequence` of `plans/meta-runbook.md`
(falling back to discovered master/dated plans pre-runbook), excluding
`_archive/_future/_research/_dashboard` and the sensitive ledger. Progress is
derived from anchored task checkboxes (`^\s*[-*]\s*\[[ xX]\]`, so inline prose
mentions of `[ ]` are ignored), counted per tracked file only. Plans render in
runbook Sequence order (extras appended); no fixed cap.

## Arguments

The command forwards `$ARGUMENTS` to `dashboard-data.sh`; the renderer takes no
flags. All are optional — bare `/meta-dashboard` renders the full view.

| Arg | Effect |
|-----|--------|
| `SCOPE` (positional) | a `plans/` **dir** narrows the Plans panel to that area; a single **`.md` file** switches to a focus view (frontmatter, overall bar, per-`##`/`###` checkbox breakdown) |
| `--commits[=N]` | focus on commits — `N` rows (default 25), expanded with relative dates |
| `--only a,b` / `--no a,b` | render only / hide named sections |
| `--repo R` / `--status S` | filter the plan set |
| `--all` | include `_archive`/`_future`/`_research` plans |
| `-h`, `--help` | usage (from `dashboard-data.sh`) |

Sections: `plans focus milestones sessions inbox sweep commits`. `focus` only
renders under single-file scope; `sweep` only when there is recent activity.
The sensitive ledger is hard-refused in focus mode **before any file read**.

## Inline Rendering

The harness collapses tool output (Ctrl+O to expand). The command echoes the
script output verbatim in a fenced code block so the dashboard shows inline.
Borders are pre-aligned — never reformat, re-wrap, or re-indent them.
