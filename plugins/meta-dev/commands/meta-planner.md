---
name: meta-planner
description: Restructure plans into execution-ready format with master checklist, phase files, verification hooks, and loop-gap config
argument-hint: <path-to-plan-file-or-directory>
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /meta-planner

Convert plan docs into execution-ready format with phase files, verification hooks, and loop-gap config.

## Dashboard stage signal (waterfall — MANDATORY)

This command owns the **PLAN** waterfall stage (3/6). Keep `/meta-dashboard` in sync — fire-and-forget, never let it block real work:
- **First action:** `bash ${CLAUDE_PLUGIN_ROOT}/scripts/stage-emit.sh "<plan-path>" plan in_progress`
- **On successful finish:** `bash ${CLAUDE_PLUGIN_ROOT}/scripts/stage-emit.sh "<plan-path>" plan completed` (use `blocked` if you halt)

`<plan-path>` = the plan file/dir invoked on (the `$ARGUMENTS` target); this shows the plan at Stage 3 automatically.

## Pipeline

### 1. Read input + detect project context

Read the input plan. Load host conventions via `references/host-claude-contract.md`. Read the host repo's `CLAUDE.md` for test commands, branch policy, directory layout.

### 2. Inventory tasks, map dependencies, identify phases

Extract every unit of work. Group into phases (3-8 tasks each).

**Granularity — author for the progress bar (MANDATORY).** Every task carries a `### Task N:` unit; **any task with more than one distinct, independently-verifiable step gets `- [ ]` subtask checkboxes for those steps** (e.g. `- [ ] backend field`, `- [ ] API schema`, `- [ ] frontend type`, `- [ ] UI wiring`). **One-ledger rule (D3):** all `- [ ]`/`- [x]` checkboxes live **only** in `00-master-plan.md` — the sole checkbox ledger. Phase files keep Codebase Snapshot + task prose + focused Verify-Before/After hooks but **no** checkbox marks (use bold task headings / plain bullets). `/meta-execute` mirrors master subtask checkboxes into the live task list (1 checkbox ↔ 1 runtime task ↔ 1 handle) and flips each via `task-done` the instant its focused work is accepted. Author each checkbox as a single coherent unit that completes and verifies on its own. This does NOT inflate the phase-size cap below: granularity lives in **subtask checkboxes within a task**, not in more top-level `### Task` headings (LP-003 cross-layer propagation is the canonical source of these subtasks).

### 3. Codebase verification (ground truth)

Run `references/codebase-verification.md` protocol: collect file refs → read each file → check staleness via `git log` → discover callers → resolve mismatches.

### 4. API contract specification (for full-stack plans)

Define request/response shapes, error codes, endpoints before implementation tasks reference them.

### 5. Generate phase files with Verify hooks (tests only where they earn their keep)

Each phase file: Codebase Snapshot → task prose (bold headings / plain bullets — **no `- [ ]`/`- [x]` marks**) with Verify-Before/After hooks. Use semantic anchors (function/class names), never line numbers (see `templates/patterns/planner.md`). **For zero-behavior move/refactor tasks** (git-mv + import-rewrite, no behavior change — the `renders-routes-split` / colocation doctrine), any code block representing MOVED code must reference the **source symbol** to lift VERBATIM (e.g. "lift the returned body of `makeXDescriptor(target)` from `toolbarTools.ts`, adjust import paths only") — **never invent the body**. The plan can't know exact content at authoring time (the tree drifts; Phase 0 re-anchors onto live HEAD), and an invented body plants fabricated APIs (icon imports, activate logic, slot maps, default-vs-named exports) that look authoritative but are wrong. "Lift VERBATIM from `<symbol>`" is the unit; the body is filled at execution (LP-006).

**Phase-size cap — keep phases SMALL (kills slow runs at the source).** No phase file exceeds **~3 tasks or ~8 touched files**. A fat phase (e.g. 6 tasks / 24 readers) makes every test cycle and review heavier and serializes the run — split it into `phase-N-a-<slug>.md` / `phase-N-b-<slug>.md` with a dependency note. Small phases move ~linearly faster and let the conductor fan mechanical leaves to DeepSeek. This is a hard authoring rule, audited at HARDEN.

**Verify hooks MUST be focused — broad gates do not belong in execution plans.** Every automated Verify-After names one test file/node or a check explicitly scoped to declared files: `pytest backend/tests/test_<thisfeature>.py -q`, never bare/directory pytest or `-k` without a file. Add `-m "not slow and not gpu and not integration"` where marked. NEVER author `npm run check`, package-wide npm/Vitest/Jest, `svelte-check`, project-wide `tsc`, a build, or a full-suite command—not per task and not in an end-of-phase acceptance section. Those belong to CI, `/ship`, or a separate explicit user request. A phase may name one path-scoped cross-task integration test. Manual/by-eye/GPU gates remain explicit human acceptance items and are never automated by `/meta-execute`. Validate every command with `scripts/verify-scope.py`; only `focused` and `scoped_check` are executable. See `references/execute-charter.md` → Focused Verification Doctrine.

**Tag every task `test: yes` or `test: no` (default `no`).** Read `meta_dev.execute.test_policy` (`bash scripts/config-get.sh meta_dev.execute.test_policy`, default `critical-only`) and the host `CLAUDE.md` testing policy first:

- **`critical-only` (default)** — tag `test: yes` ONLY for critical-breakage tasks: data-corruption paths, auth/crypto verification, payment/value transfer, DB migration, serialization round-trip, cross-service API contract (refined by any critical surfaces the host CLAUDE.md names). Every other task is `test: no`.
- **`tdd-all`** — every task `test: yes` (legacy behavior).
- **`none`** — every task `test: no`.

Only `test: yes` tasks get a TDD subtask (test→fail→impl→pass→commit). **`test: no` tasks get NO test subtask** — they verify via a declared-file scoped check, focused run, or by-eye gate, never a project build/typecheck/full suite. Don't pad ordinary tasks with tests; fewer tests is the intended posture (see `references/execute-charter.md` → Test Policy). `/meta-execute` reads the `test:` tag to pick its dispatch directive.

### 6. Generate master plan with checklist + execution rules

`00-master-plan.md` with: header, file structure, gap fixes, ALL tasks as `### Task N:` units **plus the per-task `- [ ]` subtask checkboxes from step 2** (so the master is the **sole** granular ledger execution will flip — see step 2 granularity + one-ledger rule), integration test task, execution rules.

**After the master checklist is written:** run (or instruct) `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/task-stamp.py <path-to-00-master-plan.md>` so every box carries a `` `T…` `` handle before Stage 5. Generated execution rules must say: conductor runs `task-done <master-plan> <handle>` on the master only — **never** "flip HERE and in the phase file", never dual-write.

### 7. Generate `.loop-gap-config.md`

Per `references/loopgap-config-gen.md`. Signature snapshots from Stage 1.5 reads, affected files from grep, prioritized gap categories.

### 8. Validate output

Run `bash scripts/planner-validate.sh <plan-dir>` for deterministic checks. Invoke `plan-validation` skill for judgment checks. Fix all errors before presenting result.

Config: `bash scripts/config-get.sh` for `paths`/`models` sections. Model tiers from `models.stage_overrides`.
