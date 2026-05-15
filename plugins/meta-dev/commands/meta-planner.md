---
name: meta-planner
description: Restructure plans into execution-ready format with master checklist, phase files, verification hooks, and loop-gap config
argument-hint: <path-to-plan-file-or-directory>
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /meta-planner

Convert plan docs into execution-ready format with phase files, verification hooks, and loop-gap config.

## Pipeline

### 1. Read input + detect project context

Read the input plan or spec. Load project conventions from `.claude/context/` files. Understand the full scope.

### 2. Inventory tasks, map dependencies, identify phases

**Task granularity rules — HARD:**

- **Every `### Task N:` MUST be a single, coherent unit of work.** One subagent should be able to complete it in one session without getting lost.
- **A task touches at most 5-7 files.** If a task touches more, split it.
- **A task has at most 8 steps.** If more, split into subtasks (`### Task N.M`).
- **Independent work goes in separate tasks.** If two pieces can be done in parallel, they must be separate tasks.
- **Phase headings (`## Phase N: Name`) group related tasks.** Phases are containers, not tasks. They help the executor understand ordering but do NOT get their own TodoWrite items.
- **Every task gets its own `### Task N:` heading in the MASTER-PLAN.** The executor mirrors `### Task N:` headings 1:1 into TodoWrite. If you bury work inside a task step list, it won't get its own tracker item.
- **Sub-tasks use `### Task N.M:` format.** These also get their own TodoWrite items. Use for work that's related but large enough to stand alone.

**Self-check after inventory:** Count your `### Task` headings. Each one becomes a TodoWrite item. If the count feels too low, you're lumping. If a single task has 10+ steps, you're lumping.

### 3. Codebase verification (ground truth pass)

Verify every file path, function signature, and import referenced in the plan exists in the codebase. Flag mismatches. Don't plan against imaginary files.

### 4. API contract specification (for full-stack plans)

Define request/response shapes, error codes, and endpoint paths before implementation tasks reference them. This prevents type drift across tasks.

### 5. Generate phase files with TDD steps + Verify-Before/After hooks

Each phase file contains its tasks in order. Each task has:
- Exact file paths (create/modify)
- Bite-sized steps (2-5 min each) with code blocks
- Verify-before (test fails) and verify-after (test passes) commands
- Commit message

### 6. Generate master plan with checklist + execution rules

Master plan contains:
- Plan header (goal, architecture, tech stack)
- File structure table
- Gap fixes (anything the plan assumes or resolves)
- ALL tasks as `### Task N:` headings with full implementation details
- Integration test / cleanup task at the end

### 7. Generate `.loop-gap-config.md`

Gap-scanning config for post-execution verification.

### 8. Validate output against quality checks

- [ ] Every `### Task N:` has exact file paths
- [ ] No task touches more than 7 files
- [ ] No task has more than 8 steps (or is split into subtasks)
- [ ] No placeholders (TBD, TODO, "add error handling", etc.)
- [ ] Every code block is complete (no `...` or `// etc`)
- [ ] Phase ordering respects dependencies
- [ ] All file paths verified against codebase
- [ ] AP I contracts defined before implementation tasks reference them
- [ ] Master checklist totals match phase file task counts

Config: `plans/_dashboard/settings.json` (model tiers, phase size limits).
