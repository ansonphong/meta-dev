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
- **Rule:** Before generating code in an existing file, inspect which framework idioms / API version it uses (e.g. reactivity model, module/import syntax, component pattern, ORM style) and match it. New files follow the project's current standard as documented in the host `AGENTS.md`. Never mix an old and a new idiom in the same file.
- **Applies to:** During phase file generation (Stage 2) for any framework-coupled source file.

### LP-005: When a task IS test-worthy, the test should cover edge + error paths — but most tasks are not test-worthy
- **Source:** loop-gap (seen 4x across multiple plans)
- **Added:** 2026-03-28 · **Revised:** 2026-06-26
- **Rule:** This applies ONLY to tasks tagged `test: yes` (critical-breakage — see `test_policy`, default `critical-only`). For those few, the test should list at least one error/failure path and one boundary/edge case, matching the project's existing fixture structure. **Do NOT generate a test subtask for `test: no` tasks** — they verify by their Verify-After (build / grep / run / by-eye). Fewer tests is the intended posture; don't pad ordinary tasks with exhaustive test matrices.
- **Applies to:** During phase file generation (Stage 2) — only the `test: yes` subtasks.

### LP-006: Zero-behavior move/refactor plans lift code bodies VERBATIM from the source symbol — never invent them
- **Source:** 39-TOOL-COLOCATION plan-authoring + Grok/DeepSeek/Codex hardening (seen 1x, 5 phase files: fabricated `register.ts` descriptor bodies — invented icon lazy-imports, placeholder `activate()` bodies, guessed slot maps)
- **Added:** 2026-07-09
- **Rule:** For zero-behavior move/refactor tasks (git-mv + import-rewrite, no behavior change — the `renders-routes-split` / colocation doctrine), any code block representing MOVED code (a descriptor, handler, function body, config object) must reference the **source symbol** to lift VERBATIM — e.g. "lift the entire returned object body of `makeXDescriptor(target)` from `toolbarTools.ts`, adjusting import paths only" — **never** an invented/placeholder body. The plan cannot know the exact content at authoring time (the tree drifts between authoring and execution; Phase 0 re-anchors onto the live HEAD). Inventing a body plants fabricated APIs (icon imports, activate logic, slot maps, default-vs-named exports) that look authoritative but are wrong, and that a later lens must catch. The instruction "lift VERBATIM from `<symbol>`" is the correct unit; the body is filled at execution against the re-anchored code.
- **Applies to:** During phase file generation (Stage 2) for any task that moves/extracts existing code (register.ts authoring, handler extraction, facade re-export, git-mv of a module whose internal shape is reused).

### LP-007: Record anchors, never frozen content — and re-anchor before executing
- **Source:** Stage 4 hardening of the adaptive-plan-calibration plan (generalizes LP-006 from code bodies to ALL captured content)
- **Added:** 2026-07-26
- **Rule:** A plan records the **symbol name plus the invariant that matters** — signatures, guards, callers, data flow, the constraint a reader would otherwise miss. It NEVER pastes file contents, signature dumps, or a captured snapshot of a file's body as ground truth. Frozen content is stale the moment the tree moves, and staleness is not neutral: the model still relates to the stale block and gets pulled off-course by it. Any task consuming captured ground truth **re-anchors onto live HEAD before editing** — the plan names *where* to look, HEAD says *what is there*. This is NOT gated on the plan's `target`: a frontier model is no more immune to a stale anchor than a mechanical one. Note this is the generalization of the already-established rule that line numbers are banned — the same drift argument applies to every frozen thing, not just line numbers.
- **Applies to:** During Codebase Anchors authoring (Stage 3) and any `Codebase Ground Truth` section — all target tiers, all plan layouts.
