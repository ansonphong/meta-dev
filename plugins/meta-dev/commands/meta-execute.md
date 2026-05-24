---
name: meta-execute
description: Subagent-driven plan execution — one fresh Sonnet per task, verify+commit+push between, auto-archive on completion (never deploys)
argument-hint: <plan-path> [--inline] [--deploy] [--pause-before=<task-id>]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /meta-execute

Parse plan, dispatch one Sonnet subagent per task, verify + commit + push between, escalate on drift.

## NON-NEGOTIABLE: task tracker first

**Before dispatching ANY subagent, before pre-flight gates, before anything else — the TodoWrite tracker must exist with one granular item per task.** The user relies on this list to watch progress; a run with no visible task list is a failed run regardless of whether the code lands.

This is a hard gate, not a suggestion:
- Step 1 (parse) and Step 2 (mirror to TodoWrite) happen FIRST, in order, every run. No exceptions for "small" plans.
- Do not begin Step 3 until TodoWrite item count == task count from Step 1. If they differ, STOP and fix before proceeding.
- Keep the tracker live: flip each item to `in_progress` when its subagent starts and `completed` the moment it verifies+commits. Never leave a task running while its item still reads `pending`, and never batch-complete.

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

**STOP gate — do not pass until both are true:**
1. Every `### Task N:` (and every split subtask) in the plan has a corresponding TodoWrite item.
2. The TodoWrite list is visible to the user (you have actually called the tool, not just planned to).

If either is false, fix it now. Dispatching a subagent before this gate passes is a defect.

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
- **Do NOT deploy.** Deployment is always a separate, manual `/deploy` run by the user. Completing a plan is NOT permission to deploy. Only invoke `/deploy` if the user passed the explicit `--deploy` flag on THIS run.

Config: `plans/_dashboard/settings.json` (model tier).

See `superpowers:subagent-driven-development` skill for dispatch template.
