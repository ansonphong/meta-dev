---
name: meta-dashboard
description: Control plane dashboard — gathers plan, session, inbox, git state and renders inline
argument-hint: "[SCOPE] [--commits[=N]] [--only a,b] [--no a,b] [--repo R] [--status S] [--all]"
allowed-tools: [Bash(bash:*), Bash(python3:*)]
model: opus
---

# /meta-dashboard

Control plane for meta-dev harness. Gathers project state and renders an inline dashboard.
All arguments are optional — bare `/meta-dashboard` renders the full project view.

## Behavior

1. Run the pipeline from the project root, forwarding the user's arguments verbatim
   to the data gatherer (the renderer takes no flags — all config flows through `$ARGUMENTS`):

   ```
   bash ${CLAUDE_PLUGIN_ROOT}/scripts/dashboard-data.sh $ARGUMENTS | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dashboard-render.py
   ```

2. **Reproduce the script's output verbatim in your reply, inside a fenced code block.**
   Harness tool output is collapsed (the user must press Ctrl+O to expand it), so the
   dashboard only appears *inline* if you echo it back. Copy it exactly — the rounded
   box borders are pre-aligned; do not reformat, re-wrap, re-indent, or "improve" them,
   and add no commentary above or below unless the user asked a question. The code block
   is the whole response.

## Arguments (all optional)

- **`SCOPE`** (positional) — a `plans/` **directory** narrows the Plans panel to that
  area; a single **`.md` plan file** switches to a focus view (frontmatter, overall
  progress, per-section checkbox breakdown).
- **`--commits[=N]`** — focus on commits: `N` rows (default 25), expanded with dates.
- **`--only a,b`** / **`--no a,b`** — show only / hide named sections.
- **`--repo R`** / **`--status S`** — filter the plan set. **`--all`** — include archived/future.
- Sections: `plans focus milestones sessions inbox sweep commits`. Pass `-h`/`--help` for usage.

If the user names a path, pass it through as `$ARGUMENTS` — never expand or resolve it
yourself. Pure scripts, no agents — completes in under 2 seconds.

Detail: `references/dashboard-layout.md`.
