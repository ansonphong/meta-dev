---
name: meta-execute
description: Subagent-driven plan execution — optimistic momentum (fix regressions async, keep moving), mandatory post-run code review, verify+commit+push between, auto-archive on completion (never deploys)
argument-hint: <plan-path> [--inline] [--strict] [--deploy] [--pause-before=<task-id>]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
model: opus
---

# /meta-execute

## Dashboard stage signal (waterfall — MANDATORY)

This command owns the **EXECUTE** waterfall stage (5/6). Keep `/meta-dashboard` in sync — fire-and-forget, never let a dashboard emit block execution:
- **Before the first task dispatches:** `bash ${CLAUDE_PLUGIN_ROOT}/scripts/stage-emit.sh "<plan-path>" execute in_progress`
- **After the run completes (post code-review, before archive):** `bash ${CLAUDE_PLUGIN_ROOT}/scripts/stage-emit.sh "<plan-path>" execute completed` (use `blocked` if you halt mid-run)

`<plan-path>` is the plan you were invoked on. This lights up the plan at Stage 5 (and the Active Sessions STAGE column) automatically.

## ⛔ Prerequisite — visible main-thread task list (non-negotiable)

**Before starting work on ANY task (whether dispatched to a subagent or run `--inline`), the main thread MUST stand up a visible task list via `TaskCreate` — one entry per `### Task N:` in the plan — and keep it live with `TaskUpdate` for the whole run.** The user runs `/meta-execute` to *watch* progress, so the task list is a primary deliverable, not a side effect. No tracker visible = the run has not started correctly. Updates are mirrored *as each state changes* — never batched at the end.

Parse plan, dispatch one Sonnet subagent per task, commit + push between. **Optimistic by default:** never block forward progress on tests. After each task, run only the instant inline checks, then launch the task's test/verify suite **async in the background** and advance to the next task immediately — tests run in parallel while the run keeps moving. When an async verify comes back red, spawn a background fixer scoped to it, defer dependents, advance independent work, then solidify the foundation before completion. Only critical-risk tasks (`money-path` / `release-stability` / `schema-drift`) verify synchronously. `--strict` = old serial gate (every test runs inline and blocks).

## Charter

Read `references/execute-charter.md` before dispatching. Execution posture (optimistic momentum), anti-paranoia, CLAIMED protocol, failure posture matrix, resume logic, pause gates — all there.

## Flow

### 1. Resolve plan path + parse task inventory

Read the plan. Extract every `### Task N:` heading. Count them. Sub-tasks with `### Task N.M:` are separate. Phase headings are NOT tasks.

### 2. Mirror EVERY task into the visible task list (MANDATORY — see Prerequisite)

Call `TaskCreate` once per task — **descriptive, well-named** content (`<ID> — what it builds/fixes`, not bare IDs) so progress is readable. Set dependencies. The tracker item count MUST equal the step-1 inventory. **Hard gate: do not dispatch before the task list is visible and complete** — if you find yourself dispatching a subagent with no live task list, STOP and create it first. Surface every state through the run via `TaskUpdate`: `in_progress` → `🔧 repairing (async)` / `deferred — waiting on <ID>` / `blocked` → `completed`, plus one entry per background fixer and a final `📋 code review` entry.

### 3. Pre-flight gates

- Read branch policy from host `CLAUDE.md` per `references/host-claude-contract.md`
- Working tree: if dirty files overlap plan file set → commit immediately, keep moving
- Confirm on the host's declared main branch
- `git fetch origin`: rebase silently if behind; only surface on conflict
- If `filesystem.git_corruption_mitigations` config is true → apply host-specific git mitigations
- Read `references/execute-charter.md` for full pre-flight details

### 4. Per task: claim → risk-tag → dispatch → verify → commit

For EACH task-list item:

1. Mark `in_progress` via `TaskUpdate`. CLAIM in plan file (per execute-charter.md). Commit claim.
2. Run `echo "<task body>" | bash scripts/risk-tag.sh` → get risk tags
3. Dispatch Sonnet subagent with prompt from `references/execute-dispatch.md` + risk-tag clauses. Default: dispatch the next dep-satisfied, non-deferred task without waiting on in-flight fixers or in-flight tests (momentum). `--strict`: wait for the prior task to go green first.
4. Subagent returns → **instant inline checks only** (stub grep on the diff + declared-file existence — milliseconds). Commit + push. Then **launch the task's `Verify:`/test suite async in the background** (`Bash run_in_background`, tracked as its own tracker entry `🧪 testing <ID> (async)`) and DO NOT block on it. **Exception — critical gate:** if the task is risk-tagged `money-path`, `release-stability`, or `schema-drift`, run its verify synchronously and require green before advancing. **Never run the full baseline suite per task** — that's the slow part; it runs once at solidify (step 5).
5. **Advance immediately** to the next dep-satisfied task while tests run. Mark the task `✅ code done, tests pending`. When its async verify returns: **green** → mark `completed`, **IMMEDIATELY flip the plan checkbox to `[x] DONE`** (see ⛔ CHECKBOX RULE below). **Recoverable red** → spawn background fixer (execute-dispatch.md), mark task `blocked`, defer dependents, keep dispatching independents. **TRUE BLOCKER** → STOP, surface (see charter momentum gate).

### ⛔ MANDATORY CHECKBOX RULE — NEVER SKIP, NEVER DEFER

**Every time a task completes (green verify), you MUST edit the plan file and flip its checkbox BEFORE dispatching the next task or doing anything else.** This is the user's primary visibility into progress — unchecked boxes read as "nothing happened." Do NOT batch them, do NOT "do it at the end," do NOT assume the user won't notice. The checkbox is the single source of truth.

**The exact Edit operation (do this for EVERY completed task):**

```
Find in plan file:    - [ ] CLAIMED `Task N: <title>`
Replace with:         - [x] DONE `Task N: <title>`
```

If the task was never CLAIMED (resume or --inline):
```
Find in plan file:    - [ ] Task N: <title>
Replace with:         - [x] DONE Task N: <title>
```

**After each flip, commit immediately:** `chore(plan): mark <Task ID> DONE`. Then advance to the next task.

**Self-check before the report card (step 8):** `grep -cE '^[[:space:]]*[-*][[:space:]]+\[[[:space:]]\]' <plan-file>`. If the count is not zero for completed tasks, you missed checkboxes — go back and flip them NOW, before rendering the report card.

### 5. Solidify foundation

### 5. Solidify foundation

**Drain all in-flight async test/verify jobs** (wait for every backgrounded suite to report), all fixers green, no deferred/blocked tasks left → run the **full acceptance suite once** (the clustered test pass deferred from per-task). Gate: all green before proceeding. The run is NOT done while any async test job is still pending or red.

### 6. Mandatory post-run code review

**ALWAYS invoke `superpowers:requesting-code-review`** over the full run diff (`git diff <start-sha>..HEAD`). This is NON-NEGOTIABLE — every `/meta-execute` run ends with an independent code review. Route findings:

- **Trivial/mechanical** (lint, format, missing annotation) → fix inline, commit, push
- **Substantive** (logic, security, contract, scope creep) → surface to user with file:line in the Follow-ups section of the report card, do NOT silently auto-fix

Record verdict in the report card. If the review returns substantive findings, fix them before proceeding to housekeeping.

### 7. Housekeeping

Archive the plan (unless manual gates remain — e.g., GPU acceptance, in-app verification), update STATUS.md + exec-order.md, commit + push both repos.

### 8. Render execution report card

ALWAYS end with this structured dashboard. Use `references/execute-report-card.md` for the exact layout. The report MUST include every section below — no sprawl, no stream-of-consciousness narration.

```
╔══════════════════════════════════════════════════════════════════╗
║         📋 /meta-execute — EXECUTION REPORT CARD               ║
╚══════════════════════════════════════════════════════════════════╝

  Plan:         <plan-title>
  Path:         <plan-path>
  Status:       EXECUTED + REVIEWED (or EXECUTED · awaiting manual gate)
  Duration:     <elapsed>

  ── Tasks ──
  ✅ <done>/<total> completed · <failed> failed · <deferred> deferred

  ── Commits (on <repo> master) ──
  <short-sha>  <description>                    <verify-result>

  ── Code Review ──
  ✅ CLEAN — 0 findings (or)
  ⚠️  <N> findings fixed · 0 remaining (or)
  ❌ <N> findings surfaced — see Follow-ups

  ── Acceptance ──
  <test-suite> <pass>/<total> · <other-gates>

  ── Plan Location ──
  ✅ Archived: plans/<repo>/_archive/<name>/  (or)
  📍 Active:   plans/<repo>/<name>/  (reason: <manual gate pending>)

  ── Follow-ups ──
  • <item> — <action needed> — <who>
  • (empty if none)
```

**Rules for the report card:**
- Every section is mandatory. If a section has no content, write "(none)" — never omit.
- Commit table: one row per commit, short SHA, one-line description, verify result (e.g., "6/6 pass", "check clean", "sync-verified ✓")
- Plan location: state where the plan lives NOW. If archived, show the archive path. If still active, say WHY (e.g., "manual GPU acceptance pending", "awaiting user verification of X")
- Follow-ups: structured list. Each item = what needs doing + what action + who owns it. Include: manual gates, unarchived plans, findings surfaced from code review, deploy prompts
- No narrative. No conversational wrap-up. The report card IS the wrap-up.
- Do NOT repeat the entire plan description. The report card is a summary of execution results, not a re-cap of the design doc.

## Flags

| Flag | Effect |
|------|--------|
| `--inline` | Main-thread execution, no subagents |
| `--strict` | Disable optimistic momentum — every verify/test runs inline and blocks, serial gate, every red is a hard STOP, no background fixers, no async tests |
| `--no-deploy` | Skip deploy prompt after archive |
| `--pause-before=<id>` | Hard stop before that task |
| `--no-pause` | Disable auto-pause on money-path/release-stability |
| `--stop-on-drift` | Halt on new origin/master commits |
| `--dry-run` | Parse + risk-tag + print, don't dispatch |

Config: `bash scripts/config-get.sh` for models/filesystem sections.
