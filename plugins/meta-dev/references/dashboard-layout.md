# Dashboard Layout Spec

Layout rules for `dashboard-render.py` (the `/meta-dashboard` control plane).

> **Card format:** open-right chassis, 9-glyph vocabulary, `CARD_W = 74` —
> see [`status-cards.md`](status-cards.md). This file defines only the
> *content* of the dashboard: where its data comes from, its arguments, and
> how it is rendered inline.

Dashboard-specific content notes:

- Progress bar width is `BAR_W = 18` (passed to `render_lib.bar()`).
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
