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
2. **Dispatch one agent per plan** (parallel, independent). Each agent receives ONLY its plan path and the two-lock brief below. Agents must:
   - **Lock 1:** run `scripts/archive-guard.sh` — a deterministic, non-overridable PASS/BLOCK gate. BLOCK = leave the plan in place, no exceptions.
   - **Lock 2:** verify every deliverable exists in the child repo's actual code; confirm not Active/Blocked in STATUS.md.
   - Archive ONLY if Lock 1 = PASS AND Lock 2 clean. Otherwise return `archived: false` with `block_reasons`.
   - Return: `{plan, repo, archived: bool, guard: PASS|BLOCK, verified_deliverables: [...], block_reasons: [...], context_files_updated: [...], notes}`
3. **Gather results** — collect agent returns. Skip cross-cutting if dry-run.
4. **Cross-cutting files** — update `plans/STATUS.md` and `plans/exec-order.md` to reflect ONLY the plans that were actually archived (`archived: true`).
5. **Append changelog entry** — one entry summarizing all housekeeping actions.
6. **Commit + push** — single commit covering all changes.
7. **Report** — list archived plans AND every plan left in place with its `block_reasons`, so it is always visible WHY a plan was not archived (and that no in-development plan was touched).

## Archive Gate — TWO LOCKS, BOTH REQUIRED

**⛔ NEVER archive a plan that is in development, unfinished, or in process.** Archiving is a one-way move of work-in-progress out of sight — getting it wrong is destructive. So archive is **default-DENY**: a plan stays put unless it *proves* it is finished through BOTH locks below. When in doubt, DO NOT ARCHIVE.

Prose "NEVER" rules failed before — an agent rationalized past them. So Lock 1 is **mechanical and non-overridable**, not a judgment call.

### 🔒 Lock 1 — Deterministic guard (mechanical, cannot be overridden)

Run the guard script. It decides paperwork-archivability with **zero discretion** — the agent does NOT get to second-guess it:

```bash
bash scripts/archive-guard.sh <plan-path>
```

- Exit **0** + `PASS` → Lock 1 open. Proceed to Lock 2.
- Exit **non-zero** + `BLOCK: <reasons>` → **STOP. Return `archived: false`** with the guard's reasons verbatim. **Do NOT archive. Do NOT rationalize. Do NOT edit the plan to make it pass.** A BLOCK is final.

The guard BLOCKs on ANY of: `Status:` not exactly `Done`; any unchecked `[ ]` checkbox; an active-work marker (`CLAIMED`/`WIP`/🚧/in-progress); or the plan listed unchecked in `exec-order.md`. These are exactly the signals of "in development / unfinished / in process". The guard fails safe — missing files or unreadable status also BLOCK.

### 🔒 Lock 2 — Implementation verified in code (judgment, can only BLOCK)

Even with Lock 1 open, **paper status is not proof of code.** Verify the implementation is real. Lock 2 can only ever *block* — it can never approve an archive on its own.

1. Read the plan's `Repo:` frontmatter (`app`, `www`, `gallery`).
2. Extract every concrete deliverable — files created/modified, functions, components, endpoints, config, DB migrations.
3. `cd` into the child repo and verify each exists on disk (`ls`/`find` for files, `grep` for symbols/components/routes/config, migration file present).
4. **Any deliverable NOT found → STOP. Return `archived: false`** with a specific missing list `["missing: <path/func>", ...]`.
5. Also confirm the plan is **not** listed under Active/Blocked in `STATUS.md` (grep). If it is → STOP, `archived: false`.

**Archive ONLY when Lock 1 returned `PASS` AND Lock 2 found every deliverable present AND STATUS.md does not list it active.** Any failure in either lock → leave the plan exactly where it is.

## Per-Plan Agent Template

When dispatching each plan agent, give it this exact brief:

> You are a housekeeping agent for a single plan. Your ONLY job is to process this one plan:
>
> **Plan path:** `<plan-path>`
> **Dry run:** `true/false`
>
> **⛔ ARCHIVING IS DEFAULT-DENY. NEVER archive a plan that is in development, unfinished, or in process.** A plan stays exactly where it is unless it passes BOTH locks below. When in doubt, do NOT archive — leaving an active plan in place is harmless; archiving an unfinished one is destructive.
>
> **🔒 LOCK 1 — Deterministic guard (run FIRST, non-overridable):**
> Run exactly this, from the project root:
> ```
> bash ${CLAUDE_PLUGIN_ROOT}/scripts/archive-guard.sh "<plan-path>"
> ```
> - Exit code **non-zero** (output begins `BLOCK:`) → **STOP NOW. Return `archived: false`** with `block_reasons` set to the guard's output verbatim. Do NOT archive. Do NOT rationalize around it. Do NOT edit the plan to make it pass. Do NOT continue to Lock 2. A BLOCK is final and absolute.
> - Exit code **0** (output `PASS`) → Lock 1 is open. Continue to Lock 2.
> You may NOT archive on your own judgment. If you did not run the guard, or it did not print `PASS` with exit 0, you may NOT archive — full stop.
>
> **🔒 LOCK 2 — Implementation verified in code (MANDATORY, can only block):**
> Extract every concrete deliverable from the plan (files, functions, components, endpoints, migrations, config). `cd` into the child repo named in the plan's `Repo:` frontmatter and verify each one exists on disk (`ls`, `find`, `grep`). If ANY deliverable is missing → STOP, `archived: false`, `block_reasons: ["missing: <path/func>", ...]`. Then grep `plans/STATUS.md`: if this plan is listed under Active or Blocked → STOP, `archived: false`. Lock 2 can only ever block — it never approves an archive by itself.
>
> **Only if Lock 1 printed `PASS` (exit 0) AND Lock 2 found every deliverable present AND STATUS.md does not list it active:**
> 1. If not dry-run: move the plan to `plans/<repo>/_archive/<plan-filename>.md`.
> 2. Update any context files (`.claude/context/`) that reference this plan — remove stale pointers, update status.
> 3. Update any dashboard files (`plans/_dashboard/`) that track this plan.
> 4. Return: `{plan, repo, archived: true, guard: "PASS", verified_deliverables: [...], context_files_updated, dashboard_files_updated, notes}`.
>
> If NOT archiving, always return `{plan, archived: false, guard: "<PASS|BLOCK>", block_reasons: [...]}` so the orchestrator can report exactly why.
>
> Do NOT touch STATUS.md or exec-order.md — the orchestrator handles those.
> Do NOT commit — the orchestrator commits everything at the end.

## Flags

- `--all` — full project sweep (every active plan under `plans/`, not just current-conversation scope)
- `--dry-run` — report what would happen, no changes written
- `--area status|plans|context|git` — target single area only

Config: `plans/_dashboard/settings.json` (archive path, changelog path).
