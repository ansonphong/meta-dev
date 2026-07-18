---
name: meta-dashboard
description: Control plane dashboard — gathers plan, session, inbox, git state and renders inline
argument-hint: "[SCOPE] [--commits[=N]] [--only a,b] [--no a,b] [--repo R] [--status S] [--all]"
allowed-tools: [Bash(bash:*), Bash(python3:*)]
model: opus
---

# /meta-dashboard

Control plane for the meta-dev harness — gathers plan, session, inbox, and git state,
renders an inline dashboard. Runbook-aware + planctl-backed. All arguments optional.
See `references/dashboard-layout.md` for layout + glyph spec.

## Behavior

Run from project root, forwarding `$ARGUMENTS` verbatim, then **echo the output
verbatim inside a fenced code block** (no reformatting or commentary):

```
bash ${CLAUDE_PLUGIN_ROOT}/scripts/dashboard-data.sh $ARGUMENTS | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dashboard-render.py
```

## Arguments (all optional)

- **`SCOPE`** (positional) — `plans/` dir narrows Plans panel; **`.md` file** = focus view.
- **`--commits[=N]`** — commit focus: `N` rows (default 25), expanded with dates.
- **`--only a,b`** / **`--no a,b`** — show only / hide named sections.
- **`--repo R`** / **`--status S`** — filter plans. **`--all`** — include archived/future.
  Sections: `plans focus milestones sessions inbox sweep commits`. `-h` for usage.
