---
name: housekeeping
description: Post-completion housekeeping — one fresh agent per plan (saves context), then cross-cutting files, then commit+push. Scoped to current conversation by default; --all for full project sweep.
argument-hint: [--all | --dry-run | --area status|plans|context|git]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /housekeeping

Post-completion cleanup. **One fresh agent per plan** — each agent gets a single plan and a clean context, so the orchestrator never bloats reading every plan file.

## Pattern

```
Discover plans → dispatch 1 agent per plan (parallel, fresh context) → cross-cutting files → commit+push
```

## Orchestrator (this command)

1. **Discover plans to process** — scoped to current conversation (plans touched this session), or all active plans under `plans/` with `--all`.
2. **Dispatch one agent per plan** (parallel, independent). Each agent receives ONLY its plan path and these instructions:
   - Verify plan completion (all checkboxes [x])
   - If complete: archive plan to `plans/<repo>/_archive/`
   - Update any context files that reference this plan
   - Update any dashboards that track this plan
   - Return: `{plan, repo, archived: bool, context_files_updated: [...], notes}`
3. **Gather results** — collect agent returns. Skip cross-cutting if dry-run.
4. **Cross-cutting files** — update `plans/STATUS.md` and `plans/exec-order.md` to reflect all archived plans.
5. **Append changelog entry** — one entry summarizing all housekeeping actions.
6. **Commit + push** — single commit covering all changes.

## Per-Plan Agent Template

When dispatching each plan agent, give it this exact brief:

> You are a housekeeping agent for a single plan. Your ONLY job is to process this one plan:
>
> **Plan path:** `<plan-path>`
> **Dry run:** `true/false`
>
> 1. Read the plan. Verify every checkbox is `[x]` (completed). If not, note what's unchecked and DO NOT archive — return with `archived: false`.
> 2. If complete and not dry-run: move it to `plans/<repo>/_archive/<plan-filename>.md`.
> 3. If archived, update any context files (`.claude/context/`) that reference this plan — remove stale pointers, update status.
> 4. If archived, update any dashboard files (`plans/_dashboard/`) that track this plan.
> 5. Return: `{plan, repo, archived, context_files_updated, dashboard_files_updated, notes}`.
>
> Do NOT touch STATUS.md or exec-order.md — the orchestrator handles those.
> Do NOT commit — the orchestrator commits everything at the end.

## Flags

- `--all` — full project sweep (every active plan under `plans/`, not just current-conversation scope)
- `--dry-run` — report what would happen, no changes written
- `--area status|plans|context|git` — target single area only

Config: `plans/_dashboard/settings.json` (archive path, changelog path).
