---
name: housekeeping
description: Post-completion housekeeping — archive plan, update context/status/exec-order, commit. Scoped to current conversation by default; --all for full project sweep.
argument-hint: [--all | --dry-run | --area status|plans|context|git]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /housekeeping

Post-completion cleanup scoped to current conversation.

## Steps

1. Verify plan completion (all checkboxes [x])
2. Run parallel audits: checkbox consistency, context updates, dashboard status, git state
3. Apply fixes: archive plan → `plans/_archive/`, update context files, append changelog entry, update STATUS.md + exec-order.md
4. Commit + push

## Flags

- `--all` — full project sweep (all plans, all context, all dashboards)
- `--dry-run` — report without changes
- `--area status|plans|context|git` — target single area

Config: `plans/_dashboard/settings.json` (archive path, changelog path).
