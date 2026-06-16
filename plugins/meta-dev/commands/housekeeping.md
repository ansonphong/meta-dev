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
2. **Dispatch one agent per plan** (parallel, independent). Each agent receives ONLY its plan path and the 6-gate brief below. Agents must:
   - Run all 6 gates (paperwork 1-5 + implementation verification 6)
   - Gate 6 is mandatory — verify deliverables exist in the child repo's actual code
   - If all gates pass: archive plan, update context/dashboard files
   - Return: `{plan, repo, archived: bool, verified_deliverables: [...], context_files_updated: [...], notes}`
3. **Gather results** — collect agent returns. Skip cross-cutting if dry-run.
4. **Cross-cutting files** — update `plans/STATUS.md` and `plans/exec-order.md` to reflect all archived plans.
5. **Append changelog entry** — one entry summarizing all housekeeping actions.
6. **Commit + push** — single commit covering all changes.

## Archive Gate — HARD RULE

**⛔ NEVER archive a plan unless it is VERIFIABLY 100% implemented.** Paper status means nothing — the code must exist. Self-declared `Status: Done` and checked boxes are necessary but NOT sufficient. The agent MUST confirm the implementation is real.

A plan is NOT archivable if ANY of these are true:

| # | Condition | Check |
|---|-----------|-------|
| 1 | Frontmatter `Status:` is NOT `Done` | Read plan frontmatter — `Active`, `Blocked`, `Pending`, `Draft` → **DO NOT ARCHIVE** |
| 2 | Plan appears in `exec-order.md` without `[x]` | Grep exec-order for the plan path — if listed as unchecked → **DO NOT ARCHIVE** |
| 3 | Plan appears in `STATUS.md` under Active/Blocked | Grep STATUS — if listed as in-progress → **DO NOT ARCHIVE** |
| 4 | Plan `Blocks:` other plans that are not yet Done | Read frontmatter `Blocks:` list — if any blocked plan still active → **DO NOT ARCHIVE** |
| 5 | **Implementation NOT verifiable in code** | **Go to the child repo and verify the claimed changes exist on disk — see below** |

### Gate 5: Implementation Verification (MANDATORY)

**This gate cannot be skipped. Do not trust the plan's own claims — verify against the codebase.**

1. Read the plan's `Repo:` frontmatter to know which child repo to check (`app`, `www`, `gallery`).
2. Extract every concrete deliverable from the plan — files created, files modified, functions added, components built, API endpoints, config changes, DB migrations.
3. `cd` into the child repo and verify each deliverable exists:
   - **Files:** `ls <path>` or `find` — does the file exist?
   - **Functions/classes:** `grep` for the symbol — is it defined?
   - **Components:** does the Svelte/Vue/React component file exist and contain the expected code?
   - **API endpoints:** does the route/blueprint exist?
   - **DB migrations:** is the migration file present?
   - **Config:** is the config key/value present?
4. **Any deliverable NOT found → STOP.** Return `archived: false` with a specific list of what's missing.
5. **All deliverables confirmed present → gate 5 passes.**

**Only archive when ALL 6 conditions hold:**
- Frontmatter `Status: Done`
- All checkboxes `[x]`
- Not in exec-order.md, OR listed there with `[x]`
- Not listed as Active/Blocked in STATUS.md
- No downstream plans blocked by this one that are still active
- **Every concrete deliverable from the plan is verified present in the child repo's code**

## Per-Plan Agent Template

When dispatching each plan agent, give it this exact brief:

> You are a housekeeping agent for a single plan. Your ONLY job is to process this one plan:
>
> **Plan path:** `<plan-path>`
> **Dry run:** `true/false`
>
> **⛔ ARCHIVE GATE — 6 mandatory checks BEFORE archiving:**
>
> **PAPERWORK GATES (gates 1-4):**
> 1. Read the plan frontmatter. `Status:` MUST be `Done`. If `Active`, `Blocked`, `Pending`, or `Draft` → STOP, return `archived: false` with reason "status is <status>, not Done".
> 2. Verify every checkbox is `[x]`. If any unchecked → STOP, `archived: false`.
> 3. Check `plans/exec-order.md` — if this plan appears without `[x]` → STOP, `archived: false` with reason "still on critical path in exec-order".
> 4. Check `plans/STATUS.md` — if this plan is listed under Active or Blocked → STOP, `archived: false`.
> 5. Read the plan's `Blocks:` frontmatter. For each blocked plan, check if its status is `Done`. If any blocked plan is still active → STOP, `archived: false` with reason "blocks <plan> which is still active".
>
> **IMPLEMENTATION VERIFICATION (gate 6 — MANDATORY, cannot skip):**
> 6. Extract every concrete deliverable from the plan (files, functions, components, endpoints, migrations, config). `cd` into the child repo named in the plan's `Repo:` frontmatter and verify each one exists on disk. Use `ls`, `find`, `grep` to confirm. If ANY deliverable is missing → STOP, `archived: false` with a specific list: `["missing: <path/func>", ...]`. If all confirmed present → gate 6 passes.
>
> **Only if all 6 gates pass:**
> 7. If not dry-run: move the plan to `plans/<repo>/_archive/<plan-filename>.md`.
> 8. Update any context files (`.claude/context/`) that reference this plan — remove stale pointers, update status.
> 9. Update any dashboard files (`plans/_dashboard/`) that track this plan.
> 10. Return: `{plan, repo, archived: true, verified_deliverables: [...], context_files_updated, dashboard_files_updated, notes}`.
>
> Do NOT touch STATUS.md or exec-order.md — the orchestrator handles those.
> Do NOT commit — the orchestrator commits everything at the end.

## Flags

- `--all` — full project sweep (every active plan under `plans/`, not just current-conversation scope)
- `--dry-run` — report what would happen, no changes written
- `--area status|plans|context|git` — target single area only

Config: `plans/_dashboard/settings.json` (archive path, changelog path).
