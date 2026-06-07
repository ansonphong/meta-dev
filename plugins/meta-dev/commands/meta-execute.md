---
name: meta-execute
description: Subagent-driven plan execution — optimistic momentum (fix regressions async, keep moving), mandatory post-run code review, verify+commit+push between, auto-archive on completion (never deploys)
argument-hint: <plan-path> [--inline] [--strict] [--deploy] [--pause-before=<task-id>]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /meta-execute

Parse plan, dispatch one Sonnet subagent per task, commit + push between. **Optimistic by default:** never block forward progress on tests. After each task, run only the instant inline checks, then launch the task's test/verify suite **async in the background** and advance to the next task immediately — tests run in parallel while the run keeps moving. When an async verify comes back red, spawn a background fixer scoped to it, defer dependents, advance independent work, then solidify the foundation before completion. Only critical-risk tasks (`money-path` / `release-stability` / `schema-drift`) verify synchronously. `--strict` = old serial gate (every test runs inline and blocks).

## Charter

Read `references/execute-charter.md` before dispatching. Execution posture (optimistic momentum), anti-paranoia, CLAIMED protocol, failure posture matrix, resume logic, pause gates — all there.

## Flow

### 1. Resolve plan path + parse task inventory

Read the plan. Extract every `### Task N:` heading. Count them. Sub-tasks with `### Task N.M:` are separate. Phase headings are NOT tasks.

### 2. Mirror EVERY task into the task tracker (MANDATORY)

One tracker item per task via `TaskCreate`. **Descriptive, well-named** content (`<ID> — what it builds/fixes`, not bare IDs) so progress is readable. Set dependencies. Count must match step 1 inventory. **Hard gate: do not dispatch before the tracker is visible and complete.** Surface every state through the run via `TaskUpdate`: `in_progress` → `🔧 repairing (async)` / `deferred — waiting on <ID>` / `blocked` → `completed`, plus one entry per background fixer and a final `📋 code review` entry.

### 3. Pre-flight gates

- Read branch policy from host `CLAUDE.md` per `references/host-claude-contract.md`
- Working tree: if dirty files overlap plan file set → commit immediately, keep moving
- Confirm on the host's declared main branch
- `git fetch origin`: rebase silently if behind; only surface on conflict
- If `filesystem.git_corruption_mitigations` config is true → apply host-specific git mitigations
- Read `references/execute-charter.md` for full pre-flight details

### 4. Per task: claim → risk-tag → dispatch → verify → commit

For EACH TodoWrite item:

1. Mark `in_progress`. CLAIM in plan file (per execute-charter.md). Commit claim.
2. Run `echo "<task body>" | bash scripts/risk-tag.sh` → get risk tags
3. Dispatch Sonnet subagent with prompt from `references/execute-dispatch.md` + risk-tag clauses. Default: dispatch the next dep-satisfied, non-deferred task without waiting on in-flight fixers or in-flight tests (momentum). `--strict`: wait for the prior task to go green first.
4. Subagent returns → **instant inline checks only** (stub grep on the diff + declared-file existence — milliseconds). Commit + push. Then **launch the task's `Verify:`/test suite async in the background** (`Bash run_in_background`, tracked as its own tracker entry `🧪 testing <ID> (async)`) and DO NOT block on it. **Exception — critical gate:** if the task is risk-tagged `money-path`, `release-stability`, or `schema-drift`, run its verify synchronously and require green before advancing. **Never run the full baseline suite per task** — that's the slow part; it runs once at solidify (step 5).
5. **Advance immediately** to the next dep-satisfied task while tests run. Mark the task `✅ code done, tests pending`. When its async verify returns: **green** → mark `completed`, flip checkbox to `[x] DONE`. **Recoverable red** → spawn background fixer (execute-dispatch.md), mark task `blocked`, defer dependents, keep dispatching independents. **TRUE BLOCKER** → STOP, surface (see charter momentum gate).

### 5. Completion

Solidify foundation: **drain all in-flight async test/verify jobs** (wait for every backgrounded suite to report), all fixers green, no deferred tasks left → run the **full acceptance suite once** (the clustered test pass deferred from per-task) → **mandatory post-run code review of the full run diff** (execute-dispatch.md) → archive plan → update STATUS.md + exec-order.md → report. The run is NOT done while any async test job is still pending or red.

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
