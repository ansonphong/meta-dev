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

This command owns the **PLAN** waterfall stage (3/6). Keep `/meta-dashboard` in sync by emitting a stage transition — fire-and-forget, never let it block the real work:
- **First action:** `bash ${CLAUDE_PLUGIN_ROOT}/scripts/stage-emit.sh "<plan-path>" plan in_progress`
- **On successful finish:** `bash ${CLAUDE_PLUGIN_ROOT}/scripts/stage-emit.sh "<plan-path>" plan completed` (use `blocked` instead if you halt)

`<plan-path>` is the plan file/dir you were invoked on (the `$ARGUMENTS` target). This is what makes the dashboard show this plan at Stage 3 automatically.

## Pipeline

### 1. Read input + detect project context

Read the input plan. Load host conventions via `references/host-claude-contract.md`. Read the host repo's `CLAUDE.md` for test commands, branch policy, directory layout.

### 2. Inventory tasks, map dependencies, identify phases

Extract every unit of work. Group into phases (3-8 tasks each).

**Granularity — author for the progress bar (MANDATORY).** Every task carries a `### Task N:` checkbox, and **any task with more than one distinct, independently-verifiable step gets `- [ ]` subtask checkboxes for those steps** (e.g. `- [ ] backend field`, `- [ ] API schema`, `- [ ] frontend type`, `- [ ] UI wiring`). These subtask checkboxes are what `/meta-execute` mirrors into the live task list (1 checkbox ↔ 1 runtime task) and flips one-by-one — so finer checkboxes = a finer progress bar the developer can actually track. Author each checkbox as a single coherent unit of work that completes and verifies on its own. This does NOT inflate the phase-size cap below: granularity lives in **subtask checkboxes within a task**, not in more top-level `### Task` headings (LP-003 cross-layer propagation is the canonical source of these subtasks).

### 3. Codebase verification (ground truth)

Run `references/codebase-verification.md` protocol: collect file refs → read each file → check staleness via `git log` → discover callers → resolve mismatches.

### 4. API contract specification (for full-stack plans)

Define request/response shapes, error codes, endpoints before implementation tasks reference them.

### 5. Generate phase files with Verify hooks (tests only where they earn their keep)

Each phase file: Codebase Snapshot → tasks with Verify-Before/After hooks. Use semantic anchors (function/class names), never line numbers (see `templates/patterns/planner.md`).

**Phase-size cap — keep phases SMALL (kills slow runs at the source).** No phase file exceeds **~3 tasks or ~8 touched files**. A fat phase (e.g. 6 tasks / 24 readers) makes every test cycle and review heavier and serializes the run — split it into `phase-N-a-<slug>.md` / `phase-N-b-<slug>.md` with a dependency note. Small phases move ~linearly faster and let the conductor fan mechanical leaves to DeepSeek. This is a hard authoring rule, audited at HARDEN.

**Verify hooks MUST be path-scoped — `-k` is BANNED (~18× tax).** Measured: `pytest backend/tests/ -k "headline or refresh"` = 30s (collects all 233 files, then deselects); `pytest backend/tests/test_headline.py` = 1.7s. So every per-task `Verify-After` test command names the **file** (or `…::test_name`), never a bare dir or `-k` expression: write `pytest backend/tests/test_<thisfeature>.py -q`, NOT `pytest backend/tests/ -k "<expr>"`. Add `-m "not slow and not gpu and not integration"` for backends that mark them. **Never put `svelte-check`, `tsc --noEmit`, `npm run build`, or a full-suite run in a per-task Verify-After** — collect ALL of those into one **`## Acceptance Gate (phase end)`** section at the bottom of the phase file (the single place the whole suite + type/build/slow/GPU checks run once). See `references/execute-charter.md` → Fast Test Doctrine.

**Tag every task `test: yes` or `test: no` (default `no`).** Read `meta_dev.execute.test_policy` (`bash scripts/config-get.sh meta_dev.execute.test_policy`, default `critical-only`) and the host `CLAUDE.md` testing policy first:

- **`critical-only` (default)** — tag `test: yes` ONLY for critical-breakage tasks: data-corruption paths, auth/crypto verification, payment/value transfer, DB migration, serialization round-trip, cross-service API contract (refined by any critical surfaces the host CLAUDE.md names). Every other task is `test: no`.
- **`tdd-all`** — every task `test: yes` (legacy behavior).
- **`none`** — every task `test: no`.

Only `test: yes` tasks get a TDD subtask (test→fail→impl→pass→commit). **`test: no` tasks get NO test subtask** — they verify via the Verify-After hook (build / grep / run / by-eye), which is cheaper and is what the validator checks. Do not pad ordinary tasks with tests; fewer tests is the intended posture (see `references/execute-charter.md` → Test Policy). The task's `test:` tag is what `/meta-execute` reads to pick its dispatch directive.

### 6. Generate master plan with checklist + execution rules

`00-master-plan.md` with: header, file structure, gap fixes, ALL tasks as `### Task N:` checkboxes **plus the per-task `- [ ]` subtask checkboxes from step 2** (so the master checklist is the complete, granular set of boxes execution will flip), integration test task, execution rules. Every checkbox here is one runtime task at execution time and gets flipped `- [x]` the instant its work is green — author them at that granularity.

### 7. Generate `.loop-gap-config.md`

Per `references/loopgap-config-gen.md`. Signature snapshots from Stage 1.5 reads, affected files from grep, prioritized gap categories.

### 8. Validate output

Run `bash scripts/planner-validate.sh <plan-dir>` for deterministic checks. Invoke `plan-validation` skill for judgment checks. Fix all errors before presenting result.

Config: `bash scripts/config-get.sh` for `paths`/`models` sections. Model tiers from `models.stage_overrides`.
