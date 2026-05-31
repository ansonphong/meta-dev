---
name: meta-execute
description: Subagent-driven plan execution — optimistic momentum (fix regressions async, keep moving), mandatory post-run code review, verify+commit+push between, auto-archive on completion (never deploys)
argument-hint: <plan-path> [--inline] [--strict] [--deploy] [--pause-before=<task-id>]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /meta-execute

Parse plan, dispatch one Sonnet subagent per task, verify + commit + push between. **Optimistic by default:** keep moving when a task regresses — spawn a background fixer scoped to it, defer dependents, advance independent work, then solidify the foundation before completion. `--strict` = old serial gate.

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
3. Dispatch Sonnet subagent with prompt from `references/execute-dispatch.md` + risk-tag clauses. Default: dispatch the next dep-satisfied, non-deferred task without waiting on in-flight fixers (momentum). `--strict`: wait for the prior task to go green first.
4. Subagent returns → post-task verify gate (re-run verify, stub grep, risk-tag-specific gates per execute-charter.md)
5. **Green** → mark `completed`, flip checkbox to `[x] DONE`, commit + push. **Recoverable red (default)** → spawn background fixer (execute-dispatch.md), mark task `blocked`, defer dependents, keep dispatching independents. **TRUE BLOCKER** → STOP, surface (see charter momentum gate).

### 5. Completion

Solidify foundation (all fixers green, no deferred tasks left) → run acceptance suite → **mandatory post-run code review of the full run diff** (execute-dispatch.md) → archive plan → update STATUS.md + exec-order.md → report.

## Flags

| Flag | Effect |
|------|--------|
| `--inline` | Main-thread execution, no subagents |
| `--strict` | Disable optimistic momentum — serial gate, every red is a hard STOP, no background fixers |
| `--no-deploy` | Skip deploy prompt after archive |
| `--pause-before=<id>` | Hard stop before that task |
| `--no-pause` | Disable auto-pause on money-path/release-stability |
| `--stop-on-drift` | Halt on new origin/master commits |
| `--dry-run` | Parse + risk-tag + print, don't dispatch |

Config: `bash scripts/config-get.sh` for models/filesystem sections.
