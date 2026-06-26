# Planner Learned Patterns

Copy this file to `${plans_root}/.meta-dev/patterns/planner.md` and populate with project-specific patterns. The meta-planner reads it via `paths.learned_patterns` config.

Patterns are discovered by downstream commands (loop-gap, meta-eval, meta-execute) and appended here. Max 20. Generalized only — no project-specific entries.

## Pattern format

### LP-NNN: Short title
- **Source:** {detecting command} (seen Nx: plan-1, plan-2, ...)
- **Added:** YYYY-MM-DD
- **Rule:** Generalized, actionable instruction
- **Applies to:** When/where in this command's execution

---

### LP-001: Never reference line numbers in plans — they drift
- **Source:** loop-gap (seen 7x across multiple plans)
- **Added:** 2026-03-28
- **Rule:** Never reference specific line numbers in plan tasks. Use function/class names, import locations, or structural markers ("after the last import", "inside the X class") instead. Line numbers shift as code evolves and cause incorrect insertions.
- **Applies to:** During phase file generation (Stage 2) — all `Modify:` and insertion instructions must use semantic anchors, not line numbers.

### LP-002: Verify method/API names against actual codebase before writing tasks
- **Source:** loop-gap (seen 5x across multiple plans)
- **Added:** 2026-03-28
- **Rule:** Every method name, class name, or API endpoint referenced in a task must be verified against the actual codebase (Stage 1.5 verification). Plans frequently use assumed names that differ from the actual implementation. Use the ACTUAL name.
- **Applies to:** During codebase verification (Stage 1.5) and phase file generation (Stage 2).

### LP-003: Cross-layer propagation — trace new fields through all consuming layers
- **Source:** loop-gap (seen 4x across multiple plans)
- **Added:** 2026-03-28
- **Rule:** When a task adds a field/property to any model or type, generate subtasks to propagate that field through ALL consuming layers: backend model → API response schema → frontend types → frontend store → UI component props.
- **Applies to:** During task inventory (Stage 1, step 3).

### LP-004: Framework/idiom version awareness — match the target file's existing conventions before generating code
- **Source:** loop-gap (seen 4x across multiple plans)
- **Added:** 2026-03-28
- **Rule:** Before generating code in an existing file, inspect which framework idioms / API version it uses (e.g. reactivity model, module/import syntax, component pattern, ORM style) and match it. New files follow the project's current standard as documented in the host CLAUDE.md. Never mix an old and a new idiom in the same file.
- **Applies to:** During phase file generation (Stage 2) for any framework-coupled source file.

### LP-005: When a task IS test-worthy, the test should cover edge + error paths — but most tasks are not test-worthy
- **Source:** loop-gap (seen 4x across multiple plans)
- **Added:** 2026-03-28 · **Revised:** 2026-06-26
- **Rule:** This applies ONLY to tasks tagged `test: yes` (critical-breakage — see `test_policy`, default `critical-only`). For those few, the test should list at least one error/failure path and one boundary/edge case, matching the project's existing fixture structure. **Do NOT generate a test subtask for `test: no` tasks** — they verify by their Verify-After (build / grep / run / by-eye). Fewer tests is the intended posture; don't pad ordinary tasks with exhaustive test matrices.
- **Applies to:** During phase file generation (Stage 2) — only the `test: yes` subtasks.
