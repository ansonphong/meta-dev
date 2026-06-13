---
name: meta-loop-gap
description: Four-Wave Gap Scanner — scans plans OR source code, finds bugs, fixes them directly
argument-hint: <plan-dir | feature:name | code-path | project> [--budget low|medium|high] [--iterations N]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
model: sonnet
---

# /meta-loop-gap — Four-Wave Gap Scanner

Scan plans, source code, features, or entire projects for gaps, bugs, and issues. Four waves: Tools → Haiku → Sonnet/Opus → Opus. **In code/feature mode, agents find AND fix bugs directly in source files.**

**Agent philosophy:** Be extremely liberal spawning agents. Every independent analysis axis gets its own agent. Haiku agents are cheap — spawn dozens. Sonnet agents are worth it for deep analysis — one per file plus semantic specialists. Agent count should scale dynamically with plan complexity: small plans get ~30 total agents across all waves, large plans get 70+. Only spawn agents that do genuinely independent work — never spawn an agent that duplicates another's exact scope. Spin up fast, collect results, spin up the next wave. Conditional agents (per-endpoint, per-consumer, cross-file verification) spawn only when applicable — 0 endpoints = 0 endpoint agents.

## Usage

```
/meta-loop-gap plans/app/my-feature/          # Plan directory
/meta-loop-gap feature:licensing                       # Feature scan
/meta-loop-gap backend/routes/ backend/models/         # Code paths
/meta-loop-gap project                                 # Whole project
/meta-loop-gap plans/app/foo/ --budget high --iterations 3
```

## Step 0 — Parse Arguments

**Mode:** Path inside `plans/` → `plan` | `feature:{name}` → `feature` | `project` → `project` | other paths → `code`

**Budget** (default `medium`):

| Budget | Wave 0 | Wave 1 | Wave 2 | Wave 3 |
|--------|--------|--------|--------|--------|
| low | Always | Always | Single consolidated Sonnet | Never |
| medium | Always | Always | Full (one agent/file + semantic agents) | Final iteration only |
| high | Always | Always | Full (one agent/file + semantic agents) | Every iteration |

**Iterations** (default `1`): Multi-iteration uses progressive depth — early iterations run Wave 0+1 only, promoting to deeper waves as gap count drops below 10 → below 3 → zero.

## Step 0.5 — Read Learned Patterns

Before scanning, read this command's `## Learned Patterns` section (at the bottom of this file). For each pattern:
- If the pattern adds a new gap category, extend the gap category list for this scan
- If the pattern identifies a recurring gap type, increase its severity weight
- Document which patterns were active in the scan's metadata

## Step 1 — Discover Files

**Plan mode:**
1. Glob `{TARGET_DIR}/**/*.md` — collect plan files
2. Extract file paths from `- Files:`, `- Create:`, `- Modify:`, `- Test:` lines → **codebase verification set**
3. Read CLAUDE.md for repo structure/conventions
4. `git log --since={plan_date} --name-only` for staleness detection

**Feature mode (deep discovery):**
1. **Seed files:** Glob `**/*{feature_name}*` across source dirs + common locations (routes, models, tests, components, stores, services, utils)
2. **Import graph walk (2 levels):** For each seed file, extract all imports. For each imported module, extract ITS imports. This gives you the feature's dependency cone — files it depends on and files that depend on it.
3. **Consumer discovery:** For each exported function/class/store in seed files, `grep -rn` the entire codebase for all call sites. Add consumer files to the scan set.
4. **Test file matching:** For each source file found, look for corresponding test files (`test_*.py`, `*.test.ts`, `*.spec.ts`, `__tests__/`). Add them.
5. **Related config/types:** Check for shared type files, config files, constants files that seed files import.
6. **Related plan files:** Glob `plans/**/*{feature_name}*` — include if they exist (hybrid plan+code scan).
7. **Result:** The full file set = seed files + 2-level import cone + consumers + tests + types/config. This is the **feature boundary**.

**Code mode (targeted scan):**
1. Glob all source files (`.py`, `.ts`, `.svelte`, `.rs`, `.js`, `.tsx`, `.jsx`) in specified paths
2. **Consumer discovery:** For each exported function/class in the target files, `grep -rn` the codebase for call sites. Add external consumer files as **read-only context** (scanned but not fixed).
3. **Test file matching:** Find test files corresponding to each source file. Add them to the scan set.
4. **Shared dependencies:** If multiple target files import the same module, add that module as context.

**Project mode:** Read CLAUDE.md, identify major source directories, group into ~5-15 agent groups.

**Always exclude:** `loop-gap.md`, `.loop-gap-config.md`, `__pycache__/`, `node_modules/`, `.venv/`, `dist/`, `build/`.

## Step 2 — Classify Files

**Plan mode buckets:**

| Bucket | Rule |
|--------|------|
| Master | Filename contains `master-plan`, `foundation`, `overview` |
| Editable | Plan files not master, not research/reference, not scanner metadata |
| Read-only | `research/` subdirs, `REVIEW-LOG`, `iteration-*-gap`, `original-reference` |

**Model per file:** `00-master-plan.md` → **opus**. Phase files with 5+ tasks or cross-repo → **opus**. Everything else → **sonnet**.

**Code/feature/project buckets:**

| Bucket | Rule |
|--------|------|
| Primary | Source files in the target paths or feature seed set — **editable, agents CAN fix these** |
| Consumer | External files that call/import primary files — **read-only context**, report gaps but don't fix |
| Test | Test files matching primary files — **editable**, agents can fix broken tests |
| Types/Config | Shared type definitions, constants, config — **editable if directly related** |

**Model per file:** Files 200+ lines, cross-module, or containing complex logic (loops, state machines, error handling chains) → **opus**. Everything else → **sonnet**. Test files → **sonnet**.

**Agent spawning rule: ONE AGENT PER FILE. Never batch.** For large plans with 10+ files, this means 10+ Wave 2 agents running in parallel. This is intentional — parallel agents are cheap and thorough.

## Step 3 — Check for Existing loop-gap.md

Output locations: Plan → `{TARGET_DIR}/loop-gap.md` | Feature → `plans/loop-gap-{feature}.md` | Code → `plans/loop-gap-{dirname}.md` | Project → `plans/loop-gap-project.md`

If exists: read, compare file lists, update. Use `git diff --name-only {LAST_SHA}..HEAD` for incremental mode — unchanged files get a one-line stub instead of full analysis.

## Step 4 — Generate loop-gap.md

Write the scanner prompt file using this unified template:

````markdown
# {SCOPE_NAME} Gap Scanner

> `/loop-gap {TARGET} [--budget {BUDGET}] [--iterations {N}]`

Progressive-depth four-wave scanner (Tools → Haiku → Sonnet/Opus → Opus). Aggressively parallel — one agent per file plus specialized semantic agents.

## Last Scan
```
timestamp: {ISO_TIMESTAMP}
git_sha: {CURRENT_SHA}
iteration: {N}
files_scanned: {N}
gaps_found: {N}
budget: {BUDGET}
```

## Files

| # | File | Model | Agent Focus |
|---|------|-------|-------------|
{FOR_EACH_FILE}
| {N} | `{FILENAME}` | {MODEL} | {FOCUS} |
{END_FOR}

## Codebase Verification Set (plan mode)
```
{FILEPATH} (referenced by: {PLAN_FILE})
```

## Stale File Alerts (plan mode)
Files modified after plan date ({PLAN_DATE}):
```
{FILEPATH} — {DATE} by {AUTHOR}: "{MSG}"
```

## Read-Only Reference Files
```
{FILEPATH}
```

## Gap Report Format

ALL agents report gaps as:
```
GAP | file:{FILE} | line:{LINE} | cat:{CAT} | sev:{high|med|low} | conf:{0.0-1.0}
DESC | {one-line}
FIX  | {one-line}
---
```

**Categories:** `cross_ref`, `internal`, `completeness`, `naming`, `dependency`, `structural`, `contract_fields`, `contract_schema`, `contract_implicit`, `contract_feasibility`, `contract_dataflow`, `codebase_mismatch`, `stale_assumption`, `missing_edge_case`, `import_chain`, `test_validity`, `type_error`, `lint_error`, `build_error`, `test_failure`, `lint_warning`, `security`, `ai_antipattern`, `state_lifecycle`, `ui_state_combinatorics`, `side_channel_leak`, `behavioral_claim`, `verification_soundness`, `execution_context`, `architecture_mapping`, `migration`, `performance`, `value_correctness`, `verification_reachability`, `dead_code`, `error_handling`, `resource_leak`, `race_condition`, `type_safety`, `api_drift`, `logic_error`, `test_coverage`, `stub_placeholder`, `plan_claim`

**Auto-fix:** conf ≥ 0.8 → fix. conf 0.5-0.79 → fix + flag. conf < 0.5 → report only.

## Gap Categories

### Document-Level (plan mode, checked by Wave 2 per-file agents)

**1. Cross-Reference Integrity** — Task IDs, test names, test paths, file lists, checkpoint commands all match between master and phase docs.

**2. Internal Consistency** — Sequential task numbering, no gaps/dupes. Checklist items match tasks. Test commands use valid syntax. No dangling references. **Prose self-contradiction:** Scan for places where the plan asserts X in one section and contradicts X in another (e.g., overview says "any mode" but scope says "generate only"; one paragraph says "not imported", another says "already imported"). These are often 200+ lines apart.

**3. Completeness** — Every phase task ↔ master plan (bidirectional). Checkpoints include tests AND review scope. Import paths resolve after prior tasks. **UI action ↔ backend contract:** For EVERY interactive element in the UI design (buttons, toggles, links), verify the plan defines a store method, API endpoint (if persistent), and wiring between them.

**4. Terminology & Naming** — Consistent terminology. PascalCase classes. `Test` prefix on test classes. Project file naming conventions.

**5. Dependency & Ordering** — No forward refs without notes. Logical phase/task ordering. Cross-plan dependencies exist and are in correct state.

**6. Structural Quality** — No orphan/phantom tasks. Consistent markdown. No duplication.

**7. Contract & API Gaps** (5 subcategories — trace mechanically):

- **7a. Field Completeness** (`contract_fields`) — For every endpoint: list fields handler reads, compare against request model. Gap = field read but not in model. Repeat for response → consumer.
- **7b. Schema Alignment** (`contract_schema`) — Line up fields across layers (TS interface ↔ Pydantic ↔ service params). Gap = field missing at one layer or type mismatch. Check camelCase↔snake_case.
- **7c. Implicit Derivation** (`contract_implicit`) — Flag values derived from naming/structure/convention instead of explicit params. Not all are bugs — flag at sev:med, conf:0.7.
- **7d. Runtime Feasibility** (`contract_feasibility`) — Every external call has ALL info needed. **Conditional no-op:** For every call to an existing codebase function, check for runtime guards (`if (!enabled) return`). A function that compiles but is a no-op due to unmet guards is a gap.
- **7e. Data Flow E2E** (`contract_dataflow`) — Trace: UI input → request body → handler → service → response → consumer. Gap = break in chain.

**8. State Lifecycle** (`state_lifecycle`) — For every store/state the plan touches:
- Enumerate ALL mutation paths (mount, config load, user action, effect, external event, parent prop)
- Trace invariant claims ("locked", "always", "forced") across all paths
- **Cross-store boundary:** Plan writes to Store A but consumer reads Store B for same value? Gap.
- **Temporal drift (TOCTOU):** Plan's "save/favorite/snapshot" reads live mutable state but user can change controls between trigger and capture? Gap. Must use frozen snapshot.
- **Initialization timing:** New state field must specify when populated, what prevents duplicate fetches, and empty-state UX.
- **Persistence boundary:** Store persists wholesale to localStorage but plan adds backend-only fields? They'll leak unless explicitly excluded.

**9. UI State Combinatorics** (`ui_state_combinatorics`) — List all boolean flags controlling render branches. Enumerate reachable combinations. Gap = state that renders nothing or has no exit action.

**10. Side-Channel Leakage** (`side_channel_leak`) — When plan adds a scope limiter (globalOnly, readOnly, etc.), trace ALL data paths. Gap = data bypasses the limiter through shared stores, parent props, or backend request bodies.

**11. Behavioral Claim Verification** (`behavioral_claim`) — Extract every "always/never/locked/forced/only/must" claim. List all code paths that could violate it. Gap = claim not enforced on all paths.

**12. Verification Soundness** (`verification_soundness`) — For every test/verification command: Would a false positive pass? Would a true negative be missed? Is the exit code correct? (`cmd | grep` returns grep's exit code, not cmd's.) Does the command test what it claims? **Sequential state simulation (CRITICAL):** For manual smoke tests and multi-step verification procedures, model the system/UI state as a state machine. After each step, compute the new state. Then check: is the NEXT step still physically executable given the current state? Example: step 4 changes state → step 7 tries to act on prior state → IMPOSSIBLE. This class of gap is invisible to static analysis — you must simulate the state transitions step by step. See also category 24.

**13. Execution Context** (`execution_context`) — All file paths and shell commands correct for the ACTUAL working directory (monorepo root vs child repo). Check `cd` commands, `git add` paths, verification command paths.

**14. Architecture Mapping** (`architecture_mapping`) — When plan maps concept to implementation, check codebase dispatch maps/registries/factories. Gap = plan uses generic fallback when dedicated implementation exists.

### Codebase-Level (plan + code modes)

**15. Ground Truth** — File paths exist. Functions/classes have expected signatures. **Exhaustive consumer grep:** For every modified class/function, `grep -rn "ClassName\|module_name" --include="*.py" --include="*.ts" --include="*.svelte"` the ENTIRE codebase. Gap = plan doesn't account for a consumer found by grep.

**16. Import Chain** — Every import resolves. Modules imported only after creation task. No circular chains.

**17. Test Validity** — Test files/classes/functions exist. Commands use project's actual runner/syntax.

**18. Stale Assumptions** — Files modified after plan date. Plan's "current state" descriptions match reality.

**19. Edge Cases & Integration** — Error handling at boundaries. Concurrent access. Input validation. Rollback scenarios.

**20. AI Anti-Patterns** — Middleware defined not mounted. Auth on HTTP not WS. Client-side validation accepted server-side. Catch-and-swallow. TS `any` escapes. Hallucinated APIs. Missing `await`. Hardcoded secret fallbacks.

**21. Migration & Backwards Compatibility** (`migration`) — When the plan changes a data model (store shape, API response, config schema, file format, database schema):
- Will existing localStorage/saved configs from the OLD format cause a crash or silent data loss on load? Plan must define a migration path or version check.
- Will existing API clients that send the OLD request format get a 422/500? Plan must handle backwards-compatible parsing or version the endpoint.
- Will existing saved files (JSON manifests, user presets) be unreadable? Plan must handle graceful fallback or migration.
- Does the plan add a required field to a Pydantic model? Old callers that don't send it will break.

**22. Performance & Resource Impact** (`performance`) — For each change the plan makes:
- Adds a synchronous fetch/file-read on component mount or in a hot path? Gap if it blocks rendering or causes jank.
- Adds a loop over a collection that could grow large? Check algorithmic complexity — O(n²) in a list that could have 100+ items is a gap.
- Loads an entire file/image/model into memory? Check if streaming or pagination is needed.
- Adds a reactive effect/subscription that fires on every keystroke or frame? Could cause excessive re-renders.
- Adds a new API call on a path that already has API calls? Could cause waterfall loading.

**23. Algorithmic Value Correctness** (`value_correctness`) — **CRITICAL: This category exists because a multi-pass loop returned the last pass's value instead of the cumulative target, which would have corrupted downstream state.** For every variable assigned inside a loop, conditional chain, multi-pass pipeline, or accumulator pattern:
- **Loop output values:** After a for/while loop completes, what value does each variable hold? Is that the value consumers expect, or is it the value from the LAST ITERATION only? Trace the variable from loop exit to return/response/store-write.
- **Accumulator vs. last-write:** Distinguish between variables that ACCUMULATE across iterations (running total, concatenation, product) and variables that get OVERWRITTEN each iteration. If a consumer expects the accumulated value but the code only stores the last write, that's a high-severity gap.
- **Conditional assignment completeness:** If a variable is set in branch A of an if/else/match and used after the conditional, verify it's also set in ALL other branches. Unset-on-some-paths = gap.
- **Reduction correctness:** For reduce/fold/aggregate operations, verify the initial value is correct, the combiner function is associative/commutative when assumed, and the final result matches what downstream code expects (e.g., count vs. sum vs. max).
- **Pipeline intermediate vs. final:** In multi-stage pipelines (transform → validate → format → return), verify the FINAL stage output is what gets returned/stored, not an intermediate stage's output. Watch for variables that shadow the final result.
- **Return value in nested scopes:** When a return statement is inside a loop or try/catch, verify it returns the correct scope's variable.
- Always severity HIGH. A wrong return value silently corrupts all downstream consumers.

**24. Sequential Verification Reachability** (`verification_reachability`) — **CRITICAL: This category exists because a smoke test kept steps on the same entity, not realizing that a prior step made a later step physically impossible because the UI disables elements based on state.** For ANY multi-step verification procedure (manual smoke tests, QA checklists, integration test sequences, migration runbooks):
- **State machine simulation:** Model the system state (UI state, database state, file system state) as a state machine. BEFORE each step, record the current state. AFTER each step, compute the new state based on the step's side effects. Then verify: is the NEXT step still reachable from this new state?
- **UI state gating:** When a step triggers a UI action (click button, toggle, navigate), check if the target element is ENABLED/VISIBLE/CLICKABLE given the current UI state. Buttons can be disabled by: threshold rules, feature flags, permission gates, loading states, validation errors. A step that targets a disabled element is an IMPOSSIBLE step.
- **Entity identity across steps:** When sequential steps operate on "the same" entity, verify that prior steps haven't CHANGED that entity's state in a way that blocks subsequent steps. The fix is usually: use a DIFFERENT entity for the later step.
- **Ordering dependencies:** Would reordering steps produce different results? If so, the procedure has implicit ordering constraints that must be documented.
- **Cleanup/reset steps:** Does the procedure need explicit cleanup between test scenarios? If step group A leaves state that poisons step group B, a reset step is missing.
- **Side-effect accumulation:** Steps can accumulate side effects (created files, database rows, consumed resources, rate limits). Later steps may fail not because of a logic error but because prior steps exhausted a resource.
- Always severity HIGH when a step is physically unreachable. Severity MED for implicit ordering dependencies.

### Source Code-Level (code + feature modes — checked by Wave 2 per-file agents)

These categories apply when scanning actual source code (code mode, feature mode, project mode). They also apply to codebase files in plan mode's verification set. **In code/feature mode, agents fix source code directly** — same confidence thresholds as plan fixes.

**25. Dead Code & Unreachable Paths** (`dead_code`) — Functions/methods never called from anywhere in the codebase. Variables assigned but never read. Import statements that import unused names. Conditional branches that can never execute (constant condition, type-impossible guard). Entire else branches after exhaustive returns. Parameters accepted but never used. **Technique:** For each function/class, grep the entire codebase for call sites. Zero callers = dead code (unless it's a public API endpoint, CLI entry point, or framework callback — check before flagging).

**26. Error Handling Gaps** (`error_handling`) — Bare `except:` or `except Exception:` that swallows errors silently (no logging, no re-raise). `try/catch` that catches too broadly (catches `Exception` when only `ValueError` is expected). Missing error handling on I/O operations (file reads, network calls, database queries). Promises/async functions with no `.catch()` or surrounding `try/catch`. Error paths that return `None` when callers expect a value. Missing `finally` blocks for cleanup (file handles, locks, temp files). HTTP handlers that catch exceptions but return 200 instead of an error status.

**27. Resource Leaks** (`resource_leak`) — File handles opened but not closed (missing `with` statement or `finally`). Database connections/cursors not returned to pool. Event listeners/subscriptions added but never removed (component mount without unmount cleanup). Timers (`setInterval`, `setTimeout`) created but never cleared. Temp files created but not cleaned up on error paths. WebSocket connections opened but not closed on error. **Technique:** For each resource-acquiring call, trace ALL exit paths from the function — does every path (including exceptions) release the resource?

**28. Concurrency & Race Conditions** (`race_condition`) — Shared mutable state accessed from multiple async contexts without synchronization. TOCTOU (time-of-check-to-time-of-use) patterns in file operations (`if exists → open` without locking). `async def` functions that modify shared state between `await` points. Missing `await` on coroutines (fire-and-forget without error handling). Lock ordering violations (A→B in one place, B→A in another = deadlock risk). Non-atomic read-modify-write sequences on shared data.

**29. Type Safety Holes** (`type_safety`) — `any` type annotations in TypeScript (explicit escape from type checking). Unchecked type assertions (`as Type` without validation). `Optional`/nullable values accessed without null checks. Union types not narrowed before use. Pydantic models with `model_config = {"strict": False}` accepting wrong types silently. Type: ignore comments that mask real errors. `isinstance` checks missing union members.

**30. API Contract Drift** (`api_drift`) — Frontend fetch/axios calls expecting fields the backend doesn't send. Request body fields the backend handler doesn't read. Response fields the frontend destructures but the backend doesn't include. camelCase↔snake_case mismatches between frontend and backend. Deprecated API endpoints still called by active frontend code. WebSocket event shapes that differ between sender and listener. **Technique:** Grep all fetch/axios/API calls in frontend, extract expected request/response shapes. Grep all route handlers in backend, extract actual request/response shapes. Diff them.

**31. Logic Errors** (`logic_error`) — Off-by-one errors in loop bounds or array indexing. Wrong comparison operator (`<` vs `<=`, `==` vs `===`). Inverted boolean conditions (`if (!ready)` when `if (ready)` was intended). Wrong variable used in expression (copy-paste using `a` when `b` was intended — especially in similar-looking parallel code). Short-circuit evaluation hiding side effects. Operator precedence errors (missing parentheses). Integer division truncation when float was intended. **Technique (conceptual mutation):** For each conditional, mentally negate it — does the function still make sense? For each loop bound, add/subtract 1 — does it break? For each variable in an expression, swap it with a similar nearby variable — is the original clearly correct?

**32. Test Coverage Gaps** (`test_coverage`) — Public functions with no corresponding test. Error/exception paths not tested (only happy path). Edge cases not covered (empty input, null, max values, boundary conditions). Mocked dependencies that hide real integration failures. Tests that assert nothing meaningful (just `assert True` or `expect(result).toBeDefined()`). Tests with no negative cases (only test that valid input works, never that invalid input fails). Flaky tests that pass intermittently.

**33. Stub & Placeholder Detection** (`stub_placeholder`) — **CRITICAL CATEGORY.** During the initial Dreamfields build, agents marked tasks complete while leaving stubs throughout. A CODEX audit found: placeholder text on shipped pages, route handlers returning hardcoded `[]`, services implemented but bypassed by stub route handlers, "coming soon" text in production UI, and `return []` in federation code claimed as "verified."

Patterns to detect:
- **Backend:** `return []`, `return {}`, `return None` (in route handlers — not in helper functions where these may be valid), `pass` as function body (non-abstract), `raise NotImplementedError` in concrete classes, `# TODO`, `# FIXME`, `hardcoded`, `stub`, `placeholder`, `not yet implemented`
- **Frontend:** `coming soon`, `Coming soon`, `Phase [0-9]`, `placeholder`, `Placeholder`, `Lorem ipsum`, `TBD`, `will be implemented`, `will arrive`, `will be added`, `// TODO`, `// FIXME`, `not yet`, `not implemented`
- **Structural stubs:** Pydantic response models with no matching route handler, service functions never called by any route (route uses inline stub instead), schema fields that no endpoint reads or writes
- **Severity:** ALL stub patterns in production code are HIGH. Placeholder text visible to users is CRITICAL. A function that returns hardcoded data instead of querying the database is CRITICAL.
- **Confidence:** 0.95 for exact pattern matches (grep), 0.8 for structural stubs (semantic analysis)

**34. Plan Claim Verification** (`plan_claim`) — When scanning in plan mode or project mode, verify that plan claims match codebase reality.
- For each `[x]` or `DONE` item in a plan: grep the referenced code for stub patterns (category 33). If the code has stubs, the plan claim is false.
- For each "complete" or "verified" assertion in plan prose: check that referenced files exist and don't contain TODO/placeholder/stub patterns.
- For each review artifact referenced by a plan (e.g., `design-review-1.md`, `wave-3-review.md`): verify the file exists on disk.
- For contradictory plan claims (one plan says "deferred", another says "done"): report as HIGH severity.
- **Severity:** FALSE DONE claims are HIGH. Missing review artifacts are MEDIUM. Plan contradictions are HIGH.

## Procedure

### Wave 0 — Tool Verification (always runs, zero LLM tokens)

Run developer tools via Bash. Parse output into gap reports at confidence 1.0.

**Detect toolchain** from CLAUDE.md + config files:
- Python: mypy/pyright, ruff/flake8, pytest, bandit/semgrep
- TS/JS: tsc --noEmit, eslint, npm run build/check, vitest/jest, npm audit
- Svelte: npx svelte-check --threshold warning
- Rust: cargo check, cargo clippy, cargo test

Only run tools that are installed (`command -v`). Skip gracefully if missing.

**Plan mode (Step 0b):**
1. Extract ALL fenced code blocks from plan .md files, classify by type
2. Write to temp dir mirroring `- Files:` structure
3. Syntax-check each block (`python -m py_compile`, `tsc --noEmit --allowJs --strict`, `python -m json.tool`)
4. Validate library API signatures for third-party calls:
   ```python
   python -c "import inspect; from {module} import {Class}; print(inspect.signature({Class}.{method}))"
   ```
   Check: does the plan pass all required params? Is this the current API or deprecated?
5. Validate Pydantic models — instantiate with example data, check `model_json_schema()`, verify Literal/Enum values match what callers pass
6. **Cross-block interface stitch:** Collect all function defs + call sites across ALL code blocks. Cross-reference signatures — missing args, type mismatches, camelCase↔snake_case mismatches are all gaps.
7. Verify file paths exist, read `- Modify:` files to check plan assumptions match reality

**Code/feature mode (Step 0c):**
1. Run full toolchain (type checker → linter → build → tests → security scanner → import verification)
2. Run security-focused scans if available: `bandit -r {paths}` (Python), `npm audit` (JS/TS), `semgrep --config auto {paths}` (if installed)
3. For Python: `python -c "import ast; [ast.parse(open(f).read()) for f in {files}]"` — syntax validation
4. For TypeScript: `tsc --noEmit` on target files — type checking
5. Collect test results: which tests cover target files? Any failures?

**Parse output (Step 0d):** Convert every error/warning to structured gap report. Confidence always 1.0.

| Tool Output | Severity | Category |
|-------------|----------|----------|
| Type error (mypy E:, tsc error) | high | `type_error` |
| Lint error (ruff E, eslint error) | high | `lint_error` |
| Build failure | high | `build_error` |
| Test failure | high | `test_failure` |
| Security finding (HIGH/MED) | high/med | `security` |
| Import not found | high | `import_chain` |
| Lint/type warning | med | `lint_warning`/`type_error` |

**If > 20 tool errors:** Report to user, suggest fixing before LLM waves.

### Wave 1 — Mechanical Checks + Indexing (Haiku, massively parallel)

**Be extremely liberal spawning Haiku agents. They're cheap. One per file, one per concern.** Spawn ALL agents in a single parallel message.

**Scaling rule:** Agent count scales with plan complexity. Small plan (3 phases, 5 codebase files) → ~15 agents. Large plan (10 phases, 25 codebase files) → ~40 agents. Massive plan (15+ phases, 40+ codebase files) → 50+ agents. This is intentional — Haiku agents are fast and cheap, and parallel execution means wall-clock time barely increases.

#### Fixed agents (always spawn these 7):

**Test Command Validator** (haiku) — Every `- Test:` line: file exists? class/function exists? Run `--collect-only` if supported.

**Import Chain Checker** (haiku) — Every import resolves? Modules imported before creation task? Circular chains?

**Execution Context Validator** (haiku) — Determine plan's assumed cwd. Verify ALL paths and shell commands resolve from actual execution context.

**Verification Soundness Checker** (haiku) — Every verification command: exit code correct? False positives? False negatives? Tests what it claims?

**Architecture Registry Scanner** (haiku) — Read dispatch maps, registries, factories. Build Architecture Registry. Cross-reference plan's implementation mappings.

**Virtual Codebase Builder** (haiku, plan mode) — Build definitions + call sites + mismatches from all code blocks. Merge with library API findings from Wave 0.

**Contract Extractor** (haiku) — Build Contract Registry: endpoints table, WebSocket events, data models, implicit derivations. Report field count mismatches immediately.

#### Code/feature mode fixed agents (replace plan-specific agents above when in code/feature mode):

**Import Graph Builder** (haiku) — Build a dependency graph for all target files. For each file: extract imports, map to resolved file paths, classify as internal vs. external. Output: adjacency list of file→file dependencies. This feeds all other agents.

**Consumer Discovery Agent** (haiku) — For each exported function/class/constant in primary files, `grep -rn` the entire codebase for all call sites. Build a consumer map: `{function} → [{file:line, file:line, ...}]`. Flag functions with zero consumers as potential dead code (confirm against entry points before reporting).

**Error Handler Auditor** (haiku) — Find ALL try/catch/except blocks in target files. Classify each as: (a) proper (logs + re-raises or returns error), (b) swallowed (catches but does nothing), (c) too broad (catches Exception when specific type expected), (d) missing cleanup (no finally for resources). Report swallowed and too-broad as gaps immediately.

**Type Coverage Scanner** (haiku) — Find all `any` types (TS), bare `dict`/`list` without type params (Python), unchecked assertions (`as Type`), `# type: ignore` comments, `Optional` values used without null checks. Report each as a gap with line number.

**API Surface Mapper** (haiku) — **MANDATORY in code/feature/project mode.** Find ALL API endpoints and ALL API callers. Build a comprehensive contract map.

**Why this is mandatory:** During the initial Dreamfields build, frontend and backend were built in separate phases. Each side was built against the *plan's* API contract, not against each other. Result: 5+ endpoints returning 404 at runtime despite all tests passing. This agent prevents that class of failure.

Steps:
1. Find ALL API call sites in frontend: grep for `api.get`, `api.post`, `api.put`, `api.delete`, `fetch(`, `$fetch(`. Extract: HTTP method, URL path, TypeScript type parameter (expected response shape), file:line.
2. Find ALL route handlers in backend: grep for `@router.get`, `@router.post`, `@router.put`, `@router.delete`. Read the router mounting file (e.g., `router.py`) to get prefix→file mapping. Compute full mounted paths: `{prefix}{route_path}`.
3. Find ALL response model definitions: Read Pydantic response model classes. Extract field names and types.
4. Find ALL frontend type definitions used in API calls: Read TypeScript interfaces/types used as generic params in api calls. Extract field names and types.
5. Build CONTRACT MAP: `{frontend_call: {method, url, expected_type}} → {backend_route: {method, mounted_path, response_model}} → {match: bool, shape_match: bool}`
6. Report EVERY entry where:
   - Frontend URL has no matching backend route → `api_drift` sev:HIGH conf:1.0 (404 at runtime)
   - Response type fields don't match response model fields → `contract_schema` sev:HIGH conf:0.9
   - Request body fields don't match request model fields → `contract_fields` sev:HIGH conf:0.9
   - Multiple inconsistent pagination patterns without explicit frontend handling → `contract_schema` sev:HIGH conf:0.85
   - Hardcoded API base URL in frontend calls (double-prefix risk) → `api_drift` sev:MED conf:0.9
   - camelCase↔snake_case field naming mismatches → `contract_schema` sev:MED conf:0.8

**Project Rules Checker** (haiku, conditional) — If `.claude/loop-gap-rules.md` exists in the repo, read it and mechanically apply every rule against the target files. Rules are project-specific patterns like "every Pydantic model with a Literal field must have a migration handler" or "every API endpoint must have a corresponding test." Report violations.

**Stub & Placeholder Scanner** (haiku) — **MANDATORY in code/feature/project mode.** Grep ALL target files for stub patterns from category 33. This is a fast mechanical check — no semantic analysis needed, just pattern matching.

```bash
# Backend stubs (in target files)
grep -rn "# TODO\|# FIXME\|pass$\|return \[\]\s*$\|return {}\s*$\|raise NotImplementedError\|not.yet.implemented\|hardcoded\|stub\|placeholder" {BACKEND_FILES}

# Frontend stubs (in target files)
grep -rn "// TODO\|// FIXME\|coming soon\|Coming soon\|Phase [0-9]\|placeholder\|Placeholder\|Lorem ipsum\|TBD\|will be implemented\|will arrive\|will be added" {FRONTEND_FILES}
```

Every match is a gap report at sev:HIGH conf:0.95. No filtering — every stub in production code is a finding. For context-dependent matches (e.g., `return []` in a helper that legitimately returns empty), the Wave 2 per-file agent will downgrade if appropriate.

**Plan Claim Verifier** (haiku, conditional — only in plan/project mode) — For each `[x]` DONE item in plan files, extract the feature name and referenced files. Grep those files for stub patterns (category 33). If stubs are found in code claimed as done, report as:
```
GAP | file:{plan_file} | line:{N} | cat:plan_claim | sev:high | conf:0.95
DESC | Plan marks "{feature}" as DONE but {code_file}:{line} contains "{stub_pattern}"
FIX | Either complete the implementation or revert the DONE status to OPEN
```

#### Per-codebase-file agents (one per file in the codebase verification set / target set):

For EACH file in the codebase verification set, spawn a dedicated Haiku agent:

**File Verifier + Indexer: {filename}** (haiku) — Read this ONE codebase file. Verify AND index:
- File exists at the path the plan references
- Functions/classes/signatures match what the plan assumes
- `grep -rn "ClassName\|function_name"` the entire codebase for ALL consumers — report any the plan doesn't mention
- Compare plan's "current state" description against actual file contents
- Check if file was modified after plan date (staleness)
- **Produce this file's Context Index entry:** signatures with GUARDS (early return conditions), STORE READS (which stores/fields this file reads from), rendering branches (if UI component), mutation paths (if store). This distributes indexing across all per-file agents — no single point of failure.

5 codebase files = 5 agents. 25 = 25. Each agent produces both verification results AND its portion of the Context Index.

#### Context Index Merger (haiku, 1 agent):

Does NOT read all files itself. Instead, **merges** the partial indexes from all per-codebase-file agents + plan file summaries into the unified Context Index. Also builds:
```
### Plan Files Summary
{FILE}: {N} tasks → {summary per task}
### Codebase Signatures
{FILE}: def {name}({params}) -> {ret} [line N] GUARDS: {early returns}
  STORE READS: {which stores/fields read}
### Reactive State Map
{COMPONENT}: flags: {list}, mutations: {list}, render branches: {list}, claims: {list}
### Cross-Reference Map
master:TaskN ↔ phase:TaskN — title:✓ test:✓ files:✓
### Architecture Registry
{type}: {id} → {file}:{func}
```

#### Wave 1 agent count examples:
- Small plan (3 phases, 5 codebase files): 7 fixed + 5 per-file + 1 indexer = **13 agents**
- Medium plan (6 phases, 15 codebase files): 7 fixed + 15 per-file + 1 indexer = **23 agents**
- Large plan (10 phases, 25 codebase files): 7 fixed + 25 per-file + 1 indexer = **33 agents**

**Merge:** After all agents complete, merge outputs into a single **Context Index**.

**Early termination:** If > 10 high-severity structural gaps → skip Wave 2, fix first.

### Wave 2 — Deep Analysis (Sonnet/Opus, massively parallel)

**Spawn ALL agents in a single parallel message.** Be aggressive — every independent analysis axis gets its own agent. Wall-clock time is bounded by the slowest agent, not the count.

**Per-file agents (one per file, NEVER batch):**
Each agent's prompt MUST include:
1. Its primary file — read in full
2. The merged Context Index (NOT raw files) — including Reactive State Map, Architecture Registry, Contract Registry
3. Wave 0 tool results (skip checks tools already covered)
4. All gap categories applicable to the current mode — plan mode: cats 1-24 + 34, code/feature mode: cats 15-34 + applicable plan cats if hybrid scan
5. **Semantic verification mandate:** For every behavioral claim ("always/locked/forced/only") → check Reactive State Map mutation paths. For every UI component change → check for dead-end state combos. For every scope limiter → trace all data paths in Context Index. For every implementation mapping → check Architecture Registry. For every function call → check GUARDS in Codebase Signatures. **For every code block with a loop/pipeline** → trace variable values through iterations and verify return/response uses the correct (cumulative vs. last-iteration) value (cat 23). **For every multi-step verification procedure** → simulate state after each step and verify next step is reachable (cat 24).
6. Instructions: **Plan mode:** fix own file only, report cross-file gaps, preserve checkboxes, no new tasks, no deletions. **Code/feature mode:** fix source code in own file directly (conf ≥ 0.8), report cross-file gaps, never delete public functions without consumer verification, produce at least 1 adversarial scenario. **Stub detection (ALL modes):** Check for category 33 patterns in every file. A route handler that returns hardcoded data when a service function exists for real data is ALWAYS a bug. A component showing "coming soon" or "Phase N" text in production is ALWAYS a bug. Report these at sev:HIGH conf:0.95 regardless of mode.

**Role agents (parallel with per-file agents):**

| Agent | Model | Prompt |
|-------|-------|--------|
| Implementer | sonnet | Review tasks for implementability. Flag ambiguous instructions, missing context, places you'd get stuck. |
| Tester | sonnet | Evaluate test coverage. What cases are missing? Error paths? Edge cases? |
| Consumer | sonnet | Review from caller's perspective. Do interfaces make sense? Error cases? Edge inputs? |

**Semantic agents (parallel with per-file + role agents):**

**Source-read rule:** Semantic agents primarily work from the Context Index for efficiency. But if the Context Index entry for a file seems incomplete (missing GUARDS, missing mutation paths, missing store reads), the agent MUST read the actual source file directly rather than guessing. An incomplete index is worse than no index — it creates false confidence. When in doubt, read the source.

**Data Flow Tracer** (sonnet) — Input: Contract Registry
- For each endpoint: compare Request Fields ↔ Handler Reads ↔ Service Params ↔ Response Fields ↔ Consumer Uses
- Flag: field handler reads not in request (HIGH), service param handler doesn't pass (HIGH), response field consumer reads not in response (HIGH), implicit derivation (MED), naming/type mismatch across layers (MED)
- For external calls: verify plan specifies EXACT value/source of every required arg

**Mental Dry Run** (sonnet) — Input: Virtual Codebase Index + Contract Registry
- Simulate execution in task order. BEFORE each task: what state must exist? Does a prior task create it?
- AS code runs: does each function call match a definition with compatible params? Each attribute access — was it assigned in prior step/constructor?
- AFTER: does the next task expect exactly this output (return types, side effects, files)?
- Watch for: `self.X` used but never assigned in `__init__`, constructor params not stored (`__init__(self, config)` but no `self.config = config`), async/sync boundary mismatches, resource lifecycle (who creates, who destroys, what if creation skipped)
- **Runtime value simulation (cat 23 — MANDATORY):** For EVERY code block containing a loop, conditional chain, or multi-pass pipeline: mentally execute the loop with concrete example values. Track what EACH variable holds after EACH iteration. Then check: does the value at loop exit match what the return statement / response constructor / store write expects? If you cannot build a variable trace table from the plan's code blocks, the plan is AMBIGUOUS about the return value — report as gap.

**Behavioral Claim Verifier** (sonnet) — Input: Reactive State Map + Codebase Signatures
1. EXTRACT: Scan for "always/never/locked/forced/only/must/default" → testable assertions
2. MUTATION PATHS: For each claim, enumerate: mount, config load, user action, effect/subscription, external event, parent prop, store reset
3. ENFORCE: Does plan's implementation respect claim on ALL paths? Plan only modifies mount but config load overrides? Gap.
4. TRANSITIONS: Feature toggled on with divergent state on both sides — source-of-truth rule defined? If not → gap.
5. SELF-CONTRADICTION: Compare claims across ALL sections — overview says X, implementation says NOT-X?
6. CROSS-STORE: Plan writes Store A, consumer reads Store B for same value? Gap.
7. TOCTOU: "Save/favorite/snapshot" reads live mutable state but user can change controls between trigger and capture? Gap.
8. INITIALIZATION: New state field — when populated? Duplicate fetch guard? Empty-state UX?
9. PERSISTENCE: Store persists wholesale but plan adds backend-only fields? They'll leak.
10. CONDITIONAL NO-OP: Function call on existing code — check GUARDS in Codebase Signatures. No-op if guards unmet? Gap.

**UI State Exhaustiveness** (sonnet) — Input: Reactive State Map
- For each component plan modifies: list ALL boolean/enum flags controlling render branches
- Build state table: `| flag1 | flag2 | Renders | Has exit action? |`
- Focus on "all-false" states — most commonly missed dead ends
- Example: `| hasApiKey=F | onboardingOpen=F | ??? NOTHING | ✗ DEAD END |`

**Side-Channel Detector** (sonnet) — Input: Context Index
- For each scope limiter plan introduces: identify restricted data, then trace ALL paths: direct component→API, shared stores, parent props, event dispatchers, WebSocket, backend aggregation
- Does the limiter filter on EVERY path? Or does data bypass through an unmodified channel?

**User Journey Trace** (sonnet, first iteration only, plan mode) — Trace primary user journey through plan tasks. Verify each step has implementation, error handling, and tests. Cross-ref Contract Registry at each API call.

#### Code/feature mode semantic agents (replace plan-specific semantic agents above):

**Logic Flow Auditor** (sonnet) — Input: Import Graph + Context Index
- For each function with conditional logic: trace all execution paths. Check for unreachable branches (constant guards), inverted conditions, off-by-one in loop bounds, wrong variable in expression (copy-paste errors).
- **Conceptual mutation (from mutation testing):** For each boolean condition, mentally negate it — does the function behavior still make sense? For each loop bound, mentally add/subtract 1 — does it break? For each variable in a comparison, mentally swap with a nearby similar variable — is the original clearly correct? If any mutation produces plausible-looking code, the original may have a bug.
- Check short-circuit evaluation hiding side effects, operator precedence ambiguity.

**Resource Lifecycle Tracker** (sonnet) — Input: Context Index
- For each resource-acquiring call (file open, DB connect, lock acquire, temp file create, WebSocket open, event listener add):
  - Trace ALL exit paths from the enclosing scope (normal return, early return, exception, async rejection)
  - Does EVERY exit path release the resource?
  - Is cleanup in `finally`/`__exit__`/`useEffect` cleanup/`onDestroy`?
- Flag any path that leaks. Propose fix (add `with` statement, `finally` block, cleanup function).

**Concurrency Auditor** (sonnet) — Input: Context Index
- Find shared mutable state (module-level variables, class attributes mutated from multiple methods, store state).
- For each shared mutable: is access synchronized? (lock, mutex, atomic, queue, `asyncio.Lock`)
- Find all `async def` functions: between each pair of `await` points, is shared state accessed?
- Find fire-and-forget patterns: `asyncio.create_task` or `.then()` without error handling.
- Check for TOCTOU in file operations: `if os.path.exists(f): open(f)` without locking.

**API Contract Verifier** (sonnet) — Input: API Surface Map from Wave 1
- For each endpoint: compare frontend's expected request/response shape against backend's actual handler.
- **Consumer-driven verification (from Pact):** For each consumer of a function/API, extract what the consumer DEPENDS ON (which fields it reads, which return values it checks, which side effects it expects). Verify the provider still delivers ALL of those. This catches the case where a refactor preserves the function signature but changes behavior a consumer relied on.
- Check: deprecated endpoints still called, versioned endpoints with mixed callers, WebSocket event shapes.
- **Pagination consistency audit:** Collect ALL distinct pagination response patterns from the backend (e.g., `{data, meta: {total, page, pages}}` vs `{items, total, has_next}` vs `{items, cursor, has_more}`). If more than one pattern exists, verify the frontend handles each variant explicitly — not via a single generic `PaginatedResponse<T>` that only matches one pattern. Report unhandled variants as `contract_schema` sev:HIGH.
- **URL construction audit:** Check all frontend API calls for: (a) hardcoded base URL prefixes like `/api/v1/` that would double-prefix when combined with the API client's base URL, (b) URL paths that don't match any backend mounted route, (c) URL paths that are close but not exact matches (e.g., `/notifications/mark-all-read` vs `/notifications/read-all`) — report near-misses at sev:HIGH as they indicate plan↔implementation drift.
- **Response field naming audit:** For each endpoint where frontend destructures the response, verify every field name the frontend reads exists in the backend response model. Check camelCase↔snake_case conversion — if the API doesn't auto-convert, field names must match exactly.

**Conceptual Mutation Tester** (sonnet) — Input: ALL target files
- **Philosophy (from Alloy/CrossHair): Instead of asking "are there bugs?", ask "find a concrete scenario where this code fails."**
- For each public function, construct ONE adversarial scenario — a specific input that could cause unexpected behavior. Consider: empty collections, None/null, zero, negative numbers, max integer, empty strings, unicode edge cases, concurrent calls, resource exhaustion.
- For each error handler, construct a scenario where the caught exception masks a real bug.
- For each conditional, construct an input that hits the boundary between branches.
- Each agent MUST produce at least 3 concrete adversarial scenarios, even if it concludes the code handles them correctly. Document each: `SCENARIO | {input} | EXPECTED: {X} | ACTUAL: {Y or "correctly handles"}`

**Response Shape Consistency Auditor** (sonnet) — **MANDATORY in project mode and feature mode when feature spans frontend+backend.**
- Collect ALL paginated response patterns from backend response models. Group by shape signature.
- Collect ALL pagination-related TypeScript interfaces/types from frontend.
- For each frontend type, find which backend endpoints it's used with. Verify the type matches the actual response shape.
- If a single generic type (e.g., `PaginatedResponse<T>`) is used across endpoints that return DIFFERENT shapes, report each mismatch as:
  ```
  GAP | file:{frontend_file} | line:{N} | cat:contract_schema | sev:high | conf:0.95
  DESC | Frontend uses PaginatedResponse<T> (expects {items, has_next}) but endpoint /posts returns {data, meta: {pages}}
  FIX | Either standardize backend pagination or create endpoint-specific response types in frontend
  ```
- Check that ALL API response type definitions in frontend match their corresponding Pydantic response models in backend — field names, field types, nesting structure.
- Report any "orphan types" — frontend TypeScript interfaces for API responses that don't match any backend response model.

**Sequential Verification Simulator** (sonnet) — Input: ALL verification/smoke-test sections from ALL plan files + Reactive State Map + Codebase Signatures
- **MANDATORY agent — always spawned when plan contains manual test steps, smoke tests, QA procedures, or multi-step verification sequences.**
- Extract EVERY multi-step verification procedure from the plan (smoke tests, manual QA steps, ordered verification lists).
- For each procedure, build an explicit state table:
  ```
  | Step | Action | State BEFORE | State AFTER | Next step reachable? |
  |------|--------|-------------|-------------|---------------------|
  ```
- Check UI gating rules from codebase: disabled-when conditions, visibility conditions, validation gates, loading states. Read the actual component code if the Reactive State Map doesn't capture gating rules.
- Check entity identity: do sequential steps use the SAME entity? If prior steps changed that entity's state, can subsequent steps still operate on it?
- Check resource exhaustion: do steps consume one-time resources (upload slots, API quotas, unique IDs)?
- Report UNREACHABLE steps at severity HIGH, confidence 0.95. Propose fix: use a different entity, reorder steps, or add reset steps.

**Value Correctness Auditor** (sonnet) — Input: ALL code blocks from ALL plan files
- **MANDATORY agent — always spawned when plan contains code blocks with loops, conditionals, pipelines, or multi-pass operations.**
- Extract EVERY code block from plan files. For each block containing a loop, conditional chain, accumulator, pipeline, or multi-step transformation:
  1. Identify ALL variables that are assigned inside the loop/conditional
  2. Trace each variable to its point of USE (return, response construction, store write, function argument)
  3. Determine: does the USE site expect the FINAL/CUMULATIVE value or the LAST-ITERATION value?
  4. If ambiguous (plan doesn't explicitly state which), report as gap — ambiguity in return values is always HIGH severity
- Build explicit value trace tables for every loop
- Cross-reference with Contract Registry: does the response field's consumer expect cumulative or per-iteration?
- Special attention to: `total_*`, `count`, `size`, `progress`, `accumulated_*` — any field whose NAME implies accumulation but whose code shows simple assignment
- Report at severity HIGH, confidence 0.9. Fix = add explicit comment/instruction to plan specifying which value to use.

#### Per-endpoint agents (one per API endpoint, plan mode):

If the Contract Registry lists N endpoints, spawn N Haiku agents — one per endpoint:

**Endpoint Verifier: {endpoint}** (haiku) — For this ONE endpoint, trace the full data flow: request model fields → handler reads → service params → response fields → consumer reads. Flag any break in the chain. Check camelCase↔snake_case. Check that external calls have all required args. This is fast, focused, and catches the exact class of gap ("handler reads field X but request model doesn't include it") that per-file agents miss because they see the endpoint from only one side.

#### Conditional agents (spawn only when applicable):

**Per-modified-function Consumer Audit** (sonnet, one per function) — If Wave 1 found consumers the plan doesn't mention, spawn one agent per unaccounted consumer. The agent reads the consumer file AND the plan's changes to the function/class, then answers: (a) will this consumer break? (b) does the consumer depend on behavior the plan is changing? (c) does the consumer pass arguments the plan is removing or renaming? This is **regression detection** — catching breaks in existing functionality the plan doesn't mention. 3 unaccounted consumers = 3 agents.

**Cross-phase Dependency Checker** (sonnet, one per phase boundary) — For each pair of adjacent phases (phase 1→2, 2→3, etc.), spawn an agent that verifies: does phase N's output satisfy phase N+1's preconditions? Are there ordering assumptions that could break? This catches integration seams between phases that per-file agents miss because each only sees one phase.

#### Wave 2 agent count examples:
- Small plan (3 phases, 3 endpoints, 0 unaccounted consumers): 3 file + 3 role + 7 semantic + 1 journey + 3 endpoint + 2 cross-phase = **19 agents**
- Medium plan (6 phases, 5 endpoints, 2 unaccounted consumers): 6 file + 3 role + 7 semantic + 1 journey + 5 endpoint + 5 cross-phase + 2 consumer = **29 agents**
- Large plan (10 phases, 8 endpoints, 4 unaccounted consumers): 10 file + 3 role + 7 semantic + 1 journey + 8 endpoint + 9 cross-phase + 4 consumer = **42 agents**

#### Wave 2.5 — Follow-up Verification (spawn after Wave 2 completes, if needed)

After collecting Wave 2 results, if any agent reported HIGH-severity cross-file gaps (gaps that span multiple files), spawn **verification agents** to confirm them:

**Cross-file Gap Verifier** (sonnet, one per cross-file gap cluster) — Read BOTH files involved in the reported gap. Verify the gap is real (not a Context Index artifact). If confirmed, propose a specific fix spanning both files. If false positive, report as retracted.

Only spawn these if Wave 2 found cross-file gaps. 0 cross-file gaps = skip this round entirely. 5 cross-file gaps = 5 verification agents.

### Wave 3 — Holistic Review (Opus, conditional)

Runs when: high budget (every iteration) | medium budget (final pass when prior gaps < 3) | low budget (never).

**3a: Review Agent** (opus, `subagent_type: "superpowers:code-reviewer"`) — Verify all Wave 1-2 fixes. Correctness, no scope creep, consistency, checkboxes preserved.

**3b: Devil's Advocate** (opus) — Find what all other agents missed:
1. Unstated assumptions
2. Integration boundary failures
3. Runtime failures the plan doesn't handle
4. Concurrency/timing issues
5. Hostile code reviewer perspective
6. Unaccounted callers of modified functions
7. Security (OWASP top 10)
8. Pick one endpoint, trace it fully — every field at every layer
9. Implicit derivations that could break
10. External calls with vague argument sources
11. State lifecycle — mutation paths that violate invariants
12. UI dead ends — boolean flag combos with no exit
13. Scope limiter bypass — data through unmodified parallel paths
14. Architecture mapping — wrong implementation when dedicated one exists
15. Verification soundness — commands that pass when broken
16. Execution context — paths wrong for actual cwd
17. Prose contradictions between sections
18. Temporal drift — live state read for capture actions
19. Persistence boundary — backend-only fields leaking to localStorage
20. Migration — does changing a data model break existing saved data, configs, or API clients?
21. Performance — sync fetches on mount, O(n²) loops, full-file memory loads, reactive effects on every keystroke
22. Regression — do the plan's changes to existing functions break callers that depend on current behavior?
23. **Algorithmic value correctness** — Pick EVERY loop/pipeline in the plan's code blocks. Execute it mentally with concrete values. Does the return/response use the cumulative result or the last-iteration's local value? Build a variable trace table. If the plan is ambiguous about which value to use, that IS the gap.
24. **Sequential verification reachability** — Take EVERY manual smoke test / QA procedure. Simulate state step by step. After step N mutates state, is step N+1 still physically executable? Pay special attention to: UI elements disabled by threshold rules, entities reused across steps whose state changed, resources consumed by earlier steps.

Minimum 5 findings.

### Collect + Apply

- Compile all gap reports from all waves
- Deduplicate (same file + line + category = one)
- Sort by severity (high first), then confidence
- Fix conf ≥ 0.8, flag 0.5-0.79, report-only < 0.5

### Loop Decision

**Single iteration (default):** Apply fixes, update `## Last Scan`, report to user. Done.

**Multi-iteration:**
- Gaps fixed → update `## Last Scan`, `/compact`, next iteration
- Zero gaps + Wave 3 ran → done
- Zero gaps + Wave 3 didn't run → promote to full four-wave, continue
- Only low-conf gaps → report, done
- Max iterations reached → report remaining gaps

## Rules

### Plan mode rules
- Do NOT invent/delete tasks. Do NOT edit read-only files. Preserve checkbox states.
- Prefer phase doc's version when fixing mismatches.

### Code/feature mode rules
- **Agents CAN and SHOULD fix source code directly** for gaps at conf ≥ 0.8. This is the whole point of code mode — find bugs and fix them.
- **Safety rails for code fixes:**
  - NEVER delete a function/class/export without first verifying zero consumers via grep. Dead code removal requires exhaustive consumer search.
  - NEVER change a public API signature (function params, return type, endpoint shape) without checking all callers. Prefer adding overloads or optional params over breaking changes.
  - NEVER modify test assertions to make tests pass — fix the source code instead, or flag the test as incorrect.
  - After all fixes, re-run Wave 0 tools to verify no regressions (type errors, lint failures, test failures introduced by fixes).
  - For fixes that touch multiple files, verify import chains still resolve after changes.
- **Fix scope:** Primary files → full fixes. Consumer files → report only (read-only context). Test files → fix broken tests if the fix is clear, otherwise report.
- **Counterexample mandate (from Alloy):** Every Wave 2 agent in code/feature mode must produce at least ONE concrete adversarial scenario for the code it reviews, even if the code is correct. This catches bugs that "looking for problems" misses.

### Universal rules
- Fix ALL gaps per pass. Be specific (file:line, exact strings).
- Structured gap format mandatory. Confidence filtering mandatory.
- Respect budget. Use Context Index (not raw files) for Wave 2/3.
- Never use ralph-loop. All iteration via per-plan loop-gap.md.
- **Project-specific rules:** If `.claude/loop-gap-rules.md` exists in the target repo, load and enforce its rules in addition to the built-in categories. Rules are project-specific patterns (e.g., "every endpoint must validate auth", "every store must have a reset method").
````

## Step 5 — Execute

After generating/updating loop-gap.md:

**Single iteration (default):**
1. Run Wave 0 (tools)
2. If > 20 tool errors → report, stop unless user says continue
3. Spawn ALL Wave 1 agents (parallel Haiku — could be 13-50+ agents) with Wave 0 results
4. After Wave 1: merge Context Index
5. If budget ≥ medium: spawn ALL Wave 2 agents (parallel — could be 17-42+ agents) with Context Index
6. After Wave 2: if cross-file gaps found, spawn Wave 2.5 verification agents (parallel)
7. If budget = high: spawn Wave 3 agents
8. Compile, dedup, apply fixes, commit, update metadata → **render report card (Step 7)**

**Multi-iteration:**
```
iteration = 1
while iteration <= N:
    Run Wave 0 (re-verify prior fixes)
    Progressive depth: iter 1 or gaps>10 → W0+W1 | gaps≥3 → W0+W1+W2 | gaps<3 → W0+W1+W2+W3
    Apply fixes, update ## Last Scan, /compact
    Zero gaps + W3 ran → DONE | Zero gaps + no W3 → promote, continue
    Low-conf only → DONE | Max iter → DONE (carry remaining gaps into card)
    iteration += 1
```

When the loop terminates (converged, low-conf only, or max-iter), proceed to Step 6 then render the report card (Step 7). Track these counters across all iterations so the card is accurate: files scanned, agents spawned, gaps found/fixed/flagged/remaining (by severity + category), and every fix commit SHA.

---

## Step 6 — Self-Improving Detection (Post-Scan)

After completing the scan, check for recurring gap patterns:

1. Compare current gap categories against last 3-5 scan reports via `git log --grep="loop-gap" --oneline -10`
2. Search for past loop-gap metadata: `find plans -name "loop-gap.md" -not -path "*/_archive/*" | head -10`
3. If the SAME gap category appears in 3+ separate plans (not 3x in the same plan):
   - Generalize the finding into a Learned Pattern rule
   - Patch `meta-planner.md`'s `## Learned Patterns` section (upstream): "Plans must include {X} subtask to prevent {gap category}"
   - Add LP entry to THIS file as well (extends gap category list)
   - Commit: `improve: LP-NNN added to loop-gap + meta-planner from gap scan`

---

## Step 7 — Render Gap Scan Report Card (MANDATORY)

ALWAYS end the run with this structured dashboard — the loop-gap analogue of the `/meta-execute` report card. It makes the hardening outcome obvious at a glance: which files were hardened, what was committed, whether the plan reached **NO GAPS REMAINING** (the Stage 4 exit criteria), and what (if anything) is left. Use `references/loopgap-report-card.md` for the exact layout. Render it ONCE, at the very end — not per wave, not per iteration.

```
╔══════════════════════════════════════════════════════════════════════╗
║           /meta-loop-gap — GAP SCAN REPORT CARD                    ║
╚══════════════════════════════════════════════════════════════════════╝

  Scope:        <scope-name>
  Path:         <plan-dir | target path>
  Mode:         plan | project | code | feature
  Status:       HARDENED — NO GAPS REMAINING  (or "GAPS REMAIN — <N> unresolved")
  Duration:     <iterations · agents · tokens>

  ── Scan ──
  <N> files · <budget> budget · waves W0+W1+W2+W3 · <I> iteration(s)

  ── Gaps ──
  ✅ <fixed>/<found> fixed   <flagged> flagged   <remaining> remaining
     severity:  <H> high · <M> med · <L> low
     category:  <top categories by count>

  ── Files Hardened ──
  <file>                                        <K> fixed

  ── Commits (on <repo> master, all pushed) ──
  <short-sha>  <one-line description>                    <K gaps>

  ── Review Gate ──
  ✅ Wave 3 review CLEAN — fixes verified, no scope creep

  ── Remaining Gaps ──
  • <file:line> — <category> — sev:<H> conf:<X.XX> — <why unresolved>
  • (none)

  ── Follow-ups ──
  • <item> — <action> — <owner>
  • (none)
```

**Rules for the report card:**
- Every section is mandatory. If a section has no content, write "(none)" — never omit.
- **Status must match reality:** never render `NO GAPS REMAINING` while the Remaining Gaps list is non-empty. Use `GAPS REMAIN — <N> unresolved` when high/med gaps are left, `HARDENED — <N> advisories` when only report-only items remain.
- **Files Hardened** lists only files that received ≥1 fix (not read-only consumer/reference files).
- **Commits** is one row per fix commit, with the count of gaps it closed. If nothing was committed, say so honestly (`(uncommitted — N files modified)` or `(none — scan clean)`).
- **Follow-ups** carries the next action — for a HARDENED plan that is `Ready for /meta-execute <plan>` (owner: you). Include any LP patches from Step 6.
- No narrative, no per-wave recap, no conversational sign-off. The report card IS the wrap-up. See `references/loopgap-report-card.md` for full section rules and anti-sprawl constraints.

---

## Learned Patterns

<!-- Auto-maintained by the improvement loop. Generalized only — no project-specific entries. -->
<!-- Max 20 patterns per command. meta-audit enforces cap via consolidation. -->
<!-- Append-only for this command — only meta-audit removes patterns. -->

(No patterns yet. Patterns are added automatically when recurring gap categories are detected across 3+ separate plans.)
