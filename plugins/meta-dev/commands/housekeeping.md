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

## Archive Gate — HARD RULE

**⛔ NEVER archive a plan that is still in active development or on the critical path.** Checkboxes alone are not enough — the plan must be **finalized and confirmed implemented**.

A plan is NOT archivable if ANY of these are true:

| Condition | Check |
|-----------|-------|
| Frontmatter `Status:` is NOT `Done` | Read plan frontmatter — `Active`, `Blocked`, `Pending`, `Draft` → **DO NOT ARCHIVE** |
| Plan appears in `exec-order.md` without `[x]` | Grep exec-order for the plan path — if it's listed as an unchecked dependency → **DO NOT ARCHIVE** |
| Plan appears in `STATUS.md` under Active/Blocked | Grep STATUS for the plan — if listed as in-progress → **DO NOT ARCHIVE** |
| Plan `Blocks:` other plans that are not yet Done | Read frontmatter `Blocks:` list — if any blocked plan is still active → **DO NOT ARCHIVE** |

**Only archive when ALL of these hold:**
- Frontmatter `Status: Done`
- All checkboxes `[x]`
- Not in exec-order.md, OR listed there with `[x]`
- Not listed as Active/Blocked in STATUS.md
- No downstream plans blocked by this one that are still active

## Per-Plan Agent Template

When dispatching each plan agent, give it this exact brief:

> You are a housekeeping agent for a single plan. Your ONLY job is to process this one plan:
>
> **Plan path:** `<plan-path>`
> **Dry run:** `true/false`
>
> **⛔ ARCHIVE GATE — check BEFORE archiving:**
> 1. Read the plan frontmatter. `Status:` MUST be `Done`. If `Active`, `Blocked`, `Pending`, or `Draft` → STOP, return `archived: false` with reason "status is <status>, not Done".
> 2. Verify every checkbox is `[x]`. If any unchecked → STOP, `archived: false`.
> 3. Check `plans/exec-order.md` — if this plan appears without `[x]` → STOP, `archived: false` with reason "still on critical path in exec-order".
> 4. Check `plans/STATUS.md` — if this plan is listed under Active or Blocked → STOP, `archived: false`.
> 5. Read the plan's `Blocks:` frontmatter. For each blocked plan, check if its status is `Done`. If any blocked plan is still active → STOP, `archived: false` with reason "blocks <plan> which is still active".
>
> **Only if all 5 gates pass:**
> 6. If not dry-run: move the plan to `plans/<repo>/_archive/<plan-filename>.md`.
> 7. Update any context files (`.claude/context/`) that reference this plan — remove stale pointers, update status.
> 8. Update any dashboard files (`plans/_dashboard/`) that track this plan.
> 9. Return: `{plan, repo, archived: true, context_files_updated, dashboard_files_updated, notes}`.
>
> Do NOT touch STATUS.md or exec-order.md — the orchestrator handles those.
> Do NOT commit — the orchestrator commits everything at the end.

## Flags

- `--all` — full project sweep (every active plan under `plans/`, not just current-conversation scope)
- `--dry-run` — report what would happen, no changes written
- `--area status|plans|context|git` — target single area only

Config: `plans/_dashboard/settings.json` (archive path, changelog path).
