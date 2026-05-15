---
name: meta-execute
description: Subagent-driven plan execution — one fresh Sonnet per task, verify+commit+push between, auto-archive + deploy on completion
argument-hint: <plan-path> [--inline] [--no-deploy] [--pause-before=<task-id>]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /meta-execute

Parse plan, dispatch one Sonnet subagent per task, verify + commit + push between, escalate on drift.

## Flow

### 1. Resolve plan path + parse task inventory

Read the plan file (or MASTER-PLAN.md if given a directory). Extract the full task inventory:

- **Every `### Task N:` heading is a task.** Count them. Do not skip any.
- **Sub-tasks with their own `### Task N.M:` or `#### Subtask:` headings** are separate tasks too — each gets its own TodoWrite item.
- **Phase groupings** (e.g., `## Phase 1: Backend`) are organizational containers — they are NOT tasks. Phase headings do NOT get TodoWrite items. The tasks inside them do.
- **Complex steps within a task** (8+ substantial steps, or steps that touch entirely different subsystems): split into separate TodoWrite items. A step that says "run tests" or "commit" stays part of its parent task. A step that says "rewrite charging flow for both interpret() and reply() across 6 files" is a task in its own right.
- **Independent steps** that could be dispatched in parallel: each gets its own TodoWrite item.

### 2. Mirror EVERY task into TodoWrite tracker — NOT just phases

**Hard rule: one TodoWrite item per task. Never one per phase.**

For each task extracted in step 1:
- Create a TodoWrite item with the task's full title (e.g., "Task 1: Add is_premium flag to ModelEntry")
- If a task has been split into subtasks, each subtask gets its own TodoWrite item
- Set dependencies via `addBlockedBy` where the plan specifies ordering

After mirroring, count TodoWrite items. Compare against task count from step 1. They must match. If they don't, fix the gap before proceeding.

**Self-check question before continuing:** "Does every `### Task N:` in the plan have a corresponding TodoWrite item?" If no, stop and fix.

### 3. Pre-flight gates

- Working tree clean? (If dirty files exist but don't overlap plan inventory, note and proceed.)
- On master branch?
- Backend + frontend test baselines pass? (Quick smoke: `cd backend && python -m pytest tests/ -q --tb=line 2>&1 | tail -5`, `cd frontend && bun run check 2>&1 | tail -5`)

### 4. Per task: claim → dispatch → verify → commit

For EACH TodoWrite item (not each phase):

1. Mark task `in_progress`
2. Dispatch implementer subagent (Sonnet, fresh context) with:
   - Full text of THIS specific task (not the whole plan)
   - Context: where this task fits, what it depends on, architectural notes from plan header
   - File inventory from the task's `**Files:**` block
   - Explicit instruction: implement ONLY this task, don't touch files from other tasks
3. Subagent reports back. Read its output.
4. Verify: stub-grep for key symbols the task should produce, run relevant tests
5. Risk gates: if anything looks wrong, escalate to spec-reviewer subagent
6. Mark task `completed`
7. Commit + push with task-specific message

**Between tasks:** Don't batch-mark multiple tasks complete at once. Each task gets its own verify → mark-done → commit cycle. This keeps the tracker accurate and commits granular.

### 5. Completion

After ALL TodoWrite items are `completed`:
- Archive plan to `plans/_archive/`
- Update changelog via `meta-dev:meta-changelog`
- Update `plans/STATUS.md` + `plans/exec-order.md`
- Invoke `/deploy` (unless `--no-deploy`)

Config: `plans/_dashboard/settings.json` (model tier, deploy toggle).

See `superpowers:subagent-driven-development` skill for dispatch template.
