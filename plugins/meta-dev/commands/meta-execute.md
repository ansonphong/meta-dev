---
name: meta-execute
description: Subagent-driven plan execution — one fresh Sonnet per task, verify+commit+push between, auto-archive on completion (never deploys)
argument-hint: <plan-path> [--inline] [--deploy] [--pause-before=<task-id>]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /meta-execute

Parse plan, dispatch one Sonnet subagent per task, verify + commit + push between, escalate on drift.

## Charter

Read `references/execute-charter.md` before dispatching. Anti-paranoia, CLAIMED protocol, failure posture, resume logic, pause gates — all there.

## Flow

### 1. Resolve plan path + parse task inventory

Read the plan. Extract every `### Task N:` heading. Count them. Sub-tasks with `### Task N.M:` are separate. Phase headings are NOT tasks.

### 2. Mirror EVERY task into TodoWrite tracker

One TodoWrite item per task. Set dependencies. Count must match step 1 inventory. **Hard gate: do not dispatch before TodoWrite is visible and complete.**

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
3. Dispatch Sonnet subagent with prompt from `references/execute-dispatch.md` + risk-tag clauses
4. Subagent returns → post-task verify gate (re-run verify, stub grep, risk-tag-specific gates per execute-charter.md)
5. Mark `completed`. Flip checkbox to `[x] DONE`. Commit + push.

### 5. Completion

All tasks DONE → run acceptance suite → archive plan → update STATUS.md + exec-order.md → report.

## Flags

| Flag | Effect |
|------|--------|
| `--inline` | Main-thread execution, no subagents |
| `--no-deploy` | Skip deploy prompt after archive |
| `--pause-before=<id>` | Hard stop before that task |
| `--no-pause` | Disable auto-pause on money-path/release-stability |
| `--stop-on-drift` | Halt on new origin/master commits |
| `--dry-run` | Parse + risk-tag + print, don't dispatch |

Config: `bash scripts/config-get.sh` for models/filesystem sections.
