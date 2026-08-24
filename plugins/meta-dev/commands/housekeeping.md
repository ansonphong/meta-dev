---
name: housekeeping
description: Post-completion housekeeping — one fresh agent per plan (saves context), then cross-cutting files, then commit+push. Scoped to current conversation by default; --all for full project sweep.
argument-hint: [--all | --dry-run | --area status|plans|context|git]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /housekeeping

Post-completion cleanup. **One fresh agent per plan** — each agent gets a single plan and a clean context, so the orchestrator never bloats reading every plan file.

**Codex invocation boundary:** run this multi-plan command only when the user
explicitly selects `housekeeping`. The housekeeping section inside
`meta-execute` is an inline completion step, not an invocation of this command.

## Pattern

```
Discover plans → dispatch 1 agent per plan (parallel, fresh context) → cross-cutting files → commit+push
```

## Three Destinations

Every plan lands in ONE of three places:

| Destination | Meaning |
|-------------|---------|
| `_archive/` | **Done.** All tasks complete, all gates passed, code shipped. Lock 1 + Lock 2 both PASS. |
| `_verify/` | **Code-complete, human gate pending.** All implementation tasks are `[x]`, code verified in repo, but one or more manual/human verification gates remain unchecked (GPU smoke test, in-app visual acceptance, manual E2E with real API key, etc.). Zero development work remains — the only blocker is a human running the app. |
| **In-place** | **Active.** Still in development — has unchecked code tasks, active-work markers, or is otherwise unfinished. Left exactly where it is. |

The `_verify/` bucket exists because "code done but waiting for a human to eyeball it" is a distinct state from "in active development." Moving these plans out of the active directory declutters, but keeping them in `_verify/` (not `_archive/`) makes the bottleneck visible — they're all waiting on the same thing (GPU/in-app acceptance).

## Orchestrator (this command)

1. **Discover plans to process** — scoped to current conversation (plans touched this session), or all active plans under `plans/` with `--all`.
2. **Dispatch one agent per plan** (parallel, independent). Each agent receives ONLY its plan path and the three-outcome brief below. Agents must:
   - **Lock 1:** run `scripts/archive-guard.sh` — a deterministic, non-overridable PASS/BLOCK gate.
   - **Lock 2:** verify every deliverable exists in the child repo's actual code; confirm the plan's YAML `status:` is not Active/Blocked and it is not on the active `## Sequence` in `plans/meta-runbook.md`.
   - **If Lock 1 = PASS AND Lock 2 clean** → archive to `_archive/`. Return `{archived: true}`.
   - **If Lock 1 = BLOCK** → classify: is this plan code-complete with ONLY manual/human verification gates remaining? If yes → move to `_verify/`. Return `{verified: true}`.
   - **Otherwise** → leave in place. Return `{archived: false, verified: false}` with `block_reasons`.
   - Return: `{plan, repo, archived: bool, verified: bool, guard: PASS|BLOCK, destination: "_archive"|"_verify"|null, block_reasons: [...], notes}`
3. **Gather results** — collect agent returns. Skip cross-cutting if dry-run.
4. **Cross-cutting ledger** — update `plans/meta-runbook.md` to reflect plans that were archived OR moved to `_verify/`: drop them from the `## Sequence`, add archived plans to the `## Shipped` index, and refresh `## Wave Strategy / Critical Path` if they were on it.
5. **Append changelog entry** — one entry summarizing all housekeeping actions (archived count, verify count, left-in-place count).
6. **Commit + push** — single commit covering all changes.
7. **Report** — structured report card showing all three buckets (archived, verify, left-in-place) with block reasons for every plan left in place.

## Archive Gate — TWO LOCKS, BOTH REQUIRED

**⛔ NEVER archive a plan that is in development, unfinished, or in process.** Archiving is a one-way move of work-in-progress out of sight — getting it wrong is destructive. So archive is **default-DENY**: a plan stays put unless it *proves* it is finished through BOTH locks below. When in doubt, DO NOT ARCHIVE.

Prose "NEVER" rules failed before — an agent rationalized past them. So Lock 1 is **mechanical and non-overridable**, not a judgment call.

### 🔒 Lock 1 — Deterministic guard (mechanical, cannot be overridden)

Run the guard script. It decides paperwork-archivability with **zero discretion** — the agent does NOT get to second-guess it:

```bash
bash scripts/archive-guard.sh <plan-path>
```

- Exit **0** + `PASS` → Lock 1 open. Proceed to Lock 2.
- Exit **non-zero** + `BLOCK: <reasons>` → Archive is blocked. But the plan MAY still qualify for `_verify/` — proceed to the Verify Classification step below. **Do NOT archive. Do NOT rationalize. Do NOT edit the plan to make it pass.**

The guard BLOCKs on ANY of: the plan's YAML `status:` not exactly `Done`; any unchecked `[ ]` checkbox; an active-work marker (`CLAIMED`/`WIP`/🚧/in-progress). These are exactly the signals of "in development / unfinished / in process". The guard fails safe — missing files or unreadable status also BLOCK.

### 🔒 Lock 2 — Implementation verified in code (judgment, can only BLOCK)

Even with Lock 1 open, **paper status is not proof of code.** Verify the implementation is real. Lock 2 can only ever *block* — it can never approve an archive on its own.

1. Read the plan's `Repo:` frontmatter (`app`, `www`, `gallery`).
2. Extract every concrete deliverable — files created/modified, functions, components, endpoints, config, DB migrations.
3. `cd` into the child repo and verify each exists on disk (`ls`/`find` for files, `grep` for symbols/components/routes/config, migration file present).
4. **Any deliverable NOT found → STOP. Return `archived: false`** with a specific missing list `["missing: <path/func>", ...]`.
5. Also confirm the plan's YAML `status:` is not `Active`/`Blocked` and it is **not** on the active `## Sequence` in `plans/meta-runbook.md`. If it is → STOP, `archived: false`.

**Archive ONLY when Lock 1 returned `PASS` AND Lock 2 found every deliverable present AND the plan is not active per its YAML `status:` / the meta-runbook Sequence.** Any failure in either lock → leave the plan exactly where it is.

## Verify Classification — when Lock 1 BLOCKs but code is shipped

When Lock 1 blocks (Status is not "Done" or unchecked checkboxes exist), the plan may still be **code-complete** — all development work is shipped, and the ONLY remaining items are manual/human verification gates. These plans belong in `_verify/`, not cluttering the active directory.

The agent applies judgment to classify. ALL of these must be true to move to `_verify/`:

1. **No active-work markers** — no `CLAIMED`, `WIP`, `🚧`, or `in-progress` in the plan. The plan is not currently being worked on.
2. **Code tasks are complete** — every implementation/development task checkbox is `[x]`. Grep the plan: the only unchecked `[ ]` items are clearly labeled as manual verification gates (GPU smoke test, human acceptance, visual check, in-app verification, manual E2E, hardware gate, operator sign-off, etc.).
3. **Code deliverables exist** — run the Lock 2 code verification: every file/function/component the plan claims to create actually exists in the child repo. If code is missing, the plan is NOT verify-ready (it's unfinished or abandoned).
4. **Not on the active `## Sequence` / Critical Path in `plans/meta-runbook.md`** as an active execution dependency (if it's on the critical path and unfinished, it stays put).
5. **The plan's own text confirms this state** — it explicitly says things like "awaiting manual GPU acceptance," "human gate pending," "Stage 6 manual verification," "operator sign-off required," etc. Not just the agent inferring — the plan itself declares it's waiting on a human.

**If ALL five criteria pass → move to `plans/<repo>/_verify/`. Return `verified: true`.**
**If ANY criterion fails → leave in place. Return `verified: false` with specific block reasons.**

### What "manual verification gate" looks like

The agent looks for unchecked checkboxes with language like:
- "manual GPU smoke test" / "GPU gate" / "hardware acceptance"
- "in-app visual acceptance" / "visual verification" / "eyeball"
- "human sign-off" / "operator gate" / "manual E2E"
- "real API key" test / "live-app verification"
- "MANUAL-ACCEPTANCE.md" / "GPU/Tauri smoke checklist"
- Task descriptions that explicitly say "manual," "human," "operator," "visual," "smoke," "acceptance"

The agent does NOT classify as verify-ready if unchecked items are: code tasks, tests to write, features to build, design decisions, documentation to author, or anything a developer would do.

### Verify guard fails safe

If the agent is uncertain whether the remaining items are truly manual gates → leave in place. False-positive moves to `_verify/` are annoying but harmless (the plan is still visible). False-negative leaves in the active directory are also harmless (clutter, not destruction). When in doubt, leave in place.

## Per-Plan Agent Template

When dispatching each plan agent, give it this exact brief:

> You are a housekeeping agent for a single plan. Your ONLY job is to process this one plan:
>
> **Plan path:** `<plan-path>`
> **Dry run:** `true/false`
>
> **⛔ ARCHIVING IS DEFAULT-DENY. NEVER archive a plan that is in development, unfinished, or in process.** A plan stays exactly where it is unless it passes BOTH locks below. When in doubt, do NOT archive.
>
> **🔒 LOCK 1 — Deterministic guard (run FIRST, non-overridable):**
> Run exactly this, from the project root:
> ```
> bash ${CLAUDE_PLUGIN_ROOT}/scripts/archive-guard.sh "<plan-path>"
> ```
> - Exit code **non-zero** (output begins `BLOCK:`) → Archive is blocked. Do NOT archive. Do NOT rationalize around it. Do NOT edit the plan to make it pass. **BUT** — before giving up, run the **Verify Classification** below (the plan may be code-complete and qualify for `_verify/`).
> - Exit code **0** (output `PASS`) → Lock 1 is open. Continue to Lock 2.
> You may NOT archive on your own judgment. If you did not run the guard, or it did not print `PASS` with exit 0, you may NOT archive — full stop.
>
> **🔒 LOCK 2 — Implementation verified in code (MANDATORY, can only block):**
> Extract every concrete deliverable from the plan (files, functions, components, endpoints, migrations, config). `cd` into the child repo named in the plan's `Repo:` frontmatter and verify each one exists on disk (`ls`, `find`, `grep`). If ANY deliverable is missing → STOP, `archived: false`, `block_reasons: ["missing: <path/func>", ...]`. Then check the plan's YAML `status:` and the `## Sequence` in `plans/meta-runbook.md`: if `status:` is `Active`/`Blocked` or the plan is on the active Sequence → STOP, `archived: false`. Lock 2 can only ever block — it never approves an archive by itself.
>
> **Only if Lock 1 printed `PASS` (exit 0) AND Lock 2 found every deliverable present AND the plan is not active per its YAML `status:` / the meta-runbook Sequence:**
> 1. If not dry-run: move the plan to `plans/<repo>/_archive/` (preserve directory structure for subfolder plans).
> 2. Update any routed context files (`docs/agent-context/`) that reference this plan — remove stale pointers, update status.
> 3. Update any dashboard files (`plans/_dashboard/`) that track this plan.
> 4. Return: `{plan, repo, archived: true, verified: false, guard: "PASS", destination: "_archive", verified_deliverables: [...], context_files_updated, dashboard_files_updated, notes}`.
>
> ---
>
> **🔍 VERIFY CLASSIFICATION — when Lock 1 BLOCKs, check if code-complete:**
>
> If Lock 1 blocked, the plan might still be **code-complete** — all dev work shipped, only manual/human verification gates remain. These go to `_verify/` (NOT `_archive/`). Check ALL five criteria:
>
> 1. **No active-work markers** — grep for `CLAIMED\|WIP\|🚧\|in-progress`. Zero hits required.
> 2. **Code tasks are complete** — read the plan. Every implementation task must be `[x]`. The ONLY unchecked `[ ]` items must be explicitly labeled as manual/human gates (GPU smoke, visual acceptance, human sign-off, manual E2E, operator gate, hardware test, in-app verification). If any unchecked item is a code task (write feature, add test, author docs, make design decision) → NOT verify-ready.
> 3. **Code deliverables exist** — run Lock 2 verification (extract deliverables, verify in child repo). If code claimed by the plan is missing → NOT verify-ready.
> 4. **Not on the active `## Sequence` in `plans/meta-runbook.md`** — if it's an unfinished critical-path item → NOT verify-ready.
> 5. **Plan text confirms** — the plan must explicitly say it's waiting on a human gate. Look for phrases like "awaiting manual GPU acceptance," "human gate pending," "operator sign-off," "Stage 6 manual verification," "MANUAL-ACCEPTANCE," "GPU/Tauri smoke checklist." The plan itself declares the human bottleneck.
>
> **If ALL five pass → move to `plans/<repo>/_verify/`.** Return `{plan, repo, archived: false, verified: true, destination: "_verify", notes: "<what manual gates remain>"}`.
> **If ANY fail → leave in place.** Return `{plan, archived: false, verified: false, destination: null, block_reasons: ["<specific reason for each failed criterion>"]}`.
>
> When uncertain whether remaining items are truly manual gates → leave in place (fail safe).
>
> ---
>
> Do NOT touch `plans/meta-runbook.md` — the orchestrator handles the cross-cutting ledger.
> Do NOT commit — the orchestrator commits everything at the end.

## Flags

- `--all` — full project sweep (every active plan under `plans/`, not just current-conversation scope)
- `--dry-run` — report what would happen, no changes written
- `--area status|plans|context|git` — target single area only

Config: `plans/_dashboard/settings.json` (archive path, changelog path).
