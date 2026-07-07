# Execute Charter — Anti-Paranoia, Momentum, Failure Posture, Protocols

## Execution Posture — Optimistic Momentum (default)

`/meta-execute` is **optimistic by default**: assume each task passes and keep dispatching forward. Do NOT stall the whole run waiting for every verify to go green. When something breaks, repair it *asynchronously* and keep advancing on independent work — then circle back to solidify the foundation before completion. `--strict` restores the serial gate (one green before the next, every red is a hard STOP).

## Verify Posture — Async Tests (default)

**The per-task verify gate must never block the run.** Tests are the slow part; waiting on them inline serializes the whole plan behind the test suite. Instead:

1. **Inline = instant only.** After a subagent returns, run ONLY checks that finish in milliseconds: stub-grep on the diff, declared-file existence. These gate the commit.
2. **Commit + push the code**, then **launch the task's `Verify:`/test command async in the background** (`Bash run_in_background`). Track each as its own tracker entry (`🧪 testing <ID> (async)`). **Advance to the next task immediately** — do not await the test result.
3. **Tests run in parallel with forward progress.** As each async verify reports: green → mark the task `completed`; red → it's a regression, apply the momentum gate below (background fixer, defer dependents, keep moving).
4. **No full baseline suite per task.** The expensive whole-suite run is *clustered* to the solidify step at completion — run once, not once-per-task.
5. **Critical gate (the only synchronous verify).** If a task is risk-tagged `money-path`, `release-stability`, or `schema-drift`, run its verify **synchronously and require green before advancing** — these are too costly to discover late. Everything else verifies async.
6. **Solidify drains the queue.** Completion blocks until every async test job has reported and the full acceptance suite is green. Optimism defers the wait; it never skips it.

`--strict` disables all of this: every verify runs inline and blocks, every red is a hard STOP, no background fixers, no async tests.

## Test Policy — Critical-Only (default)

**Do not write a test for every task.** Most tasks verify by their cheap `Verify-After` check (build passes, grep is clean, run-by-eye) — not by an authored test. Governed by `meta_dev.execute.test_policy` (default `critical-only`):

- **`critical-only` (default)** — a written test is generated/run ONLY for **critical-breakage** tasks: data-corruption paths, auth/crypto verification, payment/value transfer, DB migration, serialization round-trip, cross-service API contract (refined by the host `CLAUDE.md` testing policy if it names specific critical surfaces). Every other task is verified by its Verify command alone.
- **`tdd-all`** — legacy: every task runs the full failing-test-first TDD cycle.
- **`none`** — no authored tests; verify by cheap checks only.

`/meta-planner` encodes the decision per task as a `test: yes` / `test: no` tag; `/meta-execute` reads that tag to pick the dispatch directive (`references/execute-dispatch.md` → Test directive), falling back to this config when a task is untagged. **`test: no` tasks must NOT have a test written for them** — adding one is scope creep. Verify ≠ test: a Verify-After is satisfied by a build/grep/run, and only critical tasks escalate to an actual test. Fewer tests is the intended posture; the verify gates above (async, non-blocking) still apply to whatever verification a task does declare.

## Fast Test Doctrine — make every test cycle CHEAP (non-negotiable)

The single biggest execution cost is slow test cycles. Measured on a real run: `pytest backend/tests/ -k "headline or refresh"` = **30s** (it collects all 233 files, THEN deselects — `-k` filters *after* collection), versus `pytest backend/tests/test_base_node.py` = **1.7s**. That's an **~18× tax paid on every red→green cycle.** These rules make every cycle cheap; they apply to ALL backends (the main thread, and every GLM/DeepSeek/Codex worker).

1. **PATH-SCOPE ALWAYS — `-k` is BANNED as the primary selector.** Name the file(s) or node: `pytest path/to/test_thisfeature.py -q` (or `…::test_name`). NEVER run bare `pytest`, `pytest <dir>/`, or `pytest … -k <expr>` in a per-task cycle — they all collect the whole tree and pay the full collection tax every time. Path-scope first; you may add `-k`/`-x` *on top of* a named file to narrow further, never as the only selector.
2. **FAST-ONLY in the inner loop — defer slow/GPU/integration.** The loop runs only fast, pure-logic unit tests. Default selector `-m "not slow and not gpu and not integration"`. GPU/model-loading/integration tests (the ones that actually take minutes-to-hours in a diffusion app) are deferred to the **one** end-of-phase acceptance gate or a deliberate manual/CI run — NEVER per task, NEVER on "one line changed".
3. **NO broad commands per task.** `svelte-check`, `tsc --noEmit`, `npm run build`, and any full-suite run are FORBIDDEN in a per-task cycle. They run **exactly once**, at the end-of-phase acceptance gate. Per task you run only that task's single path-scoped test.
4. **Optimistic + async (per Verify Posture above).** Launch the one path-scoped test in the background, advance immediately, circle back only if it actually goes red. Never wait on a green test. Never re-run a passing test "to be sure" — one green is green.
5. **SECURE — speed never skips the security gate.** Critical-breakage and security-critical tasks (`money-path`, `release-stability`, `schema-drift`, auth/crypto verification, payment/value transfer, DB migration) STILL verify **synchronously and block** before advancing (per Verify Posture #5). Fast ≠ unverified: the optimization removes redundant whole-suite collection, not the gates that protect correctness and security. The final acceptance gate (full suite, slow+GPU markers included) still runs once before completion — optimism defers the heavy verification to one place, it never deletes it.

**Momentum gate.** When a task `T` returns red / regressed, classify:

- **TRUE BLOCKER → halt the whole run, surface.** Only these:
  1. **Plan ↔ code contradiction** — the plan no longer matches reality; nothing downstream can be trusted.
  2. **money-path / release-stability regression** — too costly to defer.
  3. **Schema drift** — DB-state divergence compounds across later tasks.
  4. **A background fixer that failed twice** on the same regression.
- **RECOVERABLE → momentum.** Everything else (ordinary red verify, stub-grep hit, subsystem test failure).

**On a recoverable regression:**
1. Spawn a **background fixer** scoped strictly to `T`'s declared files + failure output (see `references/execute-dispatch.md` → Background fixer prompt). It commits the fix to master when green. Track it as its own task-tracker entry.
2. Mark `T` `blocked` (NOT completed) with activeForm `Repairing <T> (async)`.
3. **Dependency-aware advance.** Remaining tasks that depend on `T` (declared dep, shared file, or same subsystem foundation) → `deferred`, hold. Tasks independent of `T` (disjoint files + different subsystem) → keep dispatching.
4. Fixer reports green → flip `T` `completed`, re-open tasks deferred solely on `T`.

**Solidify before completion.** Run is NOT done until every fixer resolved green, every `deferred`/`blocked` task executed, and the full acceptance suite is green.

**Conflict safety.** Fixers touch only the failed task's files; dependents (overlapping files) are `deferred`, so the main loop advances only disjoint-file work — no parallel-commit collision. Push-on-behind rebases; genuine conflict → surface.

## Anti-Paranoia Charter

`/meta-execute` is a **commit to ship the plan**, not a request for a planning session. The user typed the command to walk away and come back to a finished plan.

- **Do not ask "should I commit dirty files first?"** If dirty files overlap the plan's file inventory, commit them and keep moving. If they don't overlap, just start.
- **Do not ask "proceed?" / "ready?" / "shall I dispatch?"** after a clean pre-flight. The invocation IS the GO.
- **Do not enumerate options** when one path is obviously correct. Pick it and act.
- **Do not pause between tasks for confirmation** unless a hard pause-gate trips.
- **Stay in lane.** Out-of-scope dirty files are not your problem — leave them exactly as they are.
- **Another session may be live in this tree.** A background `/meta-execute`, `/glm-execute`, `/deep-execute`, or manual edit can be mid-flight on a *different* part of the codebase at the same moment. Dirty files outside your plan's file inventory are its in-flight work — leave them alone (never `git add -A`/`.`; scope `git add` to your task's declared paths). Only hold up if they overlap your next task's files; otherwise proceed — no need to wait on unrelated work.

## Concurrency Safety (Shared Tree) — MANDATORY

The meta working tree is SHARED across concurrent sessions, and that is FINE — **multiple sessions/workers may run in parallel.** The unit of exclusion is the **file**, not the session or the repo; coordination is **mechanically enforced** (not just advisory) so two sessions can't tangle each other's edits or sweep them into the wrong commit (incident 2026-07-05). Exactly one rule matters, and everything below just enforces it:

- **Never write a file that is already dirty on the working tree.** A dirty file outside your own task is a peer's in-flight edit — touching it double-writes and tangles the diff. Before picking up a unit, confirm its target files are CLEAN (`git status`); write only clean files, then commit them. If every worker starts only on clean files, two can never collide on the same file — so any number run concurrently, safely. (Dependency order still applies where one unit consumes another's output; the GLM ~3-request cap is a separate API rate limit — neither is this file rule.)
- **Claim is an optional coarse guard, not the law.** For a worker that will churn many files across one directory, `claude-headless-exec --claim <plan-dir>` reserves that dir in the cross-session registry (`plans/_dashboard/worker-claims.jsonl`, mkdir-atomic); by default it **ABORTS** the dispatch on an overlapping claim, is stamped with the wrapper's pid, auto-releases on exit, and auto-expires a crashed session's claim (dead pid / 30-min TTL). Directory-claim is coarser than the file rule above — for file-disjoint members sharing a directory, prefer `--claim-warn` (warn, don't abort) and lean on clean-before-write so a legitimate parallel wave isn't needlessly blocked.
- **Stage EXACTLY the worker's files — never a tree-wide add.** Each worker writes a touched-file manifest (`<output>.manifest.jsonl`, surfaced as `MANIFEST_FILE=` in the wrapper trailer). The conductor stages precisely those paths — `git add -- $(jq -r .path <manifest> | sort -u)` — NOT a `git diff`/`git status` scan (which picks up a concurrent session's edits in a shared tree). `git add -A` / `.` / `<dir/>` is **BLOCKED by the host guard hook** (it sweeps foreign edits). Sanctioned single-session dir-adds (plan archival) prefix `META_ALLOW_DIR_ADD=1`.
- **Workers are commit-free, mechanically.** The injected worker git-guard hook DENIES `git add/commit/stash/checkout/reset/rebase/merge/push` in worker context (read-only git stays available). The conductor owns git — always.
- **The exit code is honest.** A worker that reports `is_error:false` exits 0 (the wrapper reconciles the raw process code and no longer lets the EXIT trap force a 1). Trust the exit code together with the `is_error` field.

## CLAIMED → DONE — Full Checkbox Lifecycle (MANDATORY)

The plan file's checkboxes are the user's ONLY visibility into execution progress. Every checkbox — every `### Task N:` AND every `- [ ]` subtask checkbox — MUST pass through ALL three states in the plan file (a subtask checkbox flips DONE the instant its own step is green, exactly like a top-level task). No exceptions, no batching, no "I'll do it at the end." 1 runtime task ↔ 1 checkbox; completing the task is what checks the box.

### State 1: CLAIM (before dispatch)

Before dispatching a subagent for a task:
1. Edit the plan file: change `- [ ] Task N: <title>` to `` - [ ] CLAIMED `Task N: <title>` ``
2. Commit + push the claim immediately: `chore(plan): claim <Task ID>`
3. This prevents parallel sessions from picking up the same task.

### State 2: DONE (immediately after green verify)

**The instant a task's verify returns green** (async or sync), you MUST flip its checkbox before doing anything else:
1. Edit the plan file: change `` - [ ] CLAIMED `Task N: <title>` `` to `` - [x] DONE `Task N: <title>` ``
2. Commit + push immediately: `chore(plan): mark <Task ID> DONE`
3. Only THEN advance to the next task or do any other work.

**This is the step that keeps getting missed.** The checkbox flip + commit takes 5 seconds. Do it after EVERY single task — never batch, never defer. Unchecked boxes read as "nothing happened" to the user watching the plan file.

**If the task was never CLAIMED** (resume, --inline, or direct execution):
- Find: `- [ ] Task N: <title>`
- Replace with: `- [x] DONE Task N: <title>`

### State 3: Verify (before report card)

Before rendering the execution report card (step 8), run:
```bash
grep -cE '^[[:space:]]*[-*][[:space:]]+\[[[:space:]]\]' <plan-file>
```
If the count is non-zero for tasks you believe are done, STOP — go back and flip those checkboxes NOW. Never render the report card with unchecked completed tasks.

### The deterministic backstop — `on-run-complete.sh`

The checkbox discipline above is **guidance**; the **guarantee** is the `on-run-complete.sh` Stop hook. On any stop, for a plan at stage 5 it checks that all EXECUTION checkboxes are flipped (human-verify gates — `by eye` / `by hand` / `GPU` / `manual` — are excluded; those are the user's smoke test) AND a `review_verdict(pass)` is on record:

- both met → it stamps DONE (stage 6) and re-renders the dashboard itself;
- run claimed `execute completed` with execution boxes still open → it **FAILS LOUD** to the inbox (never silently half-stamps);
- clean execution but no review pass on record → it flags "review missing" and leaves the plan at stage 5.

You still flip checkboxes per-task and run the review — the gate is the deterministic backstop that makes silent half-completion structurally impossible.

### Stale CLAIMED check

If a task has been CLAIMED for >2 hours with no DONE, prompt the user before re-claiming.

## Resume Logic

If invoked on a plan with mixed DONE/OPEN tasks, resume from the first OPEN task:
- Skip DONE tasks
- Skip CLAIMED tasks (assume another session owns them, unless stale >2h)
- Pick up first OPEN task
- State tracked in plan checkbox state (committed) — no sidecar file needed

## Dry-Run Mode (`--dry-run`)

Parse the plan, run risk-tagging, print the full task inventory with risk labels, verify all file paths exist. Do not dispatch any subagents. Exit with a report.

## Failure Posture Matrix

Default = optimistic momentum. `--strict` column = the serial-gate fallback.

| Situation | Default (momentum) | `--strict` |
|-----------|--------------------|-----------|
| Red verify (recoverable) | Background fixer + defer dependents, keep moving | Re-dispatch once; STOP on 2nd red |
| Stub grep hit | Background fixer (recoverable) | STOP |
| Background fixer fails twice | Escalate to TRUE BLOCKER — STOP, surface | n/a |
| Plan <-> code contradiction | TRUE BLOCKER — STOP. Never improvise | STOP |
| Schema drift unexpected | TRUE BLOCKER — STOP. Show `alembic check` | STOP |
| money-path / release-stability regression | TRUE BLOCKER — STOP. Surface diff | STOP |
| Test baseline regresses outside touched files | Background fixer scoped to side-effected files; escalate if root cause ambiguous/cross-subsystem | STOP |
| Parallel session pushed to origin/master | If `--stop-on-drift`, halt. Else rebase, re-baseline, continue | same |

## Pause Gates

Default = no pause between green tasks. Only pause when:
- `--pause-before=<task-id>` matched
- Risk tag is `money-path` or `release-stability` (auto-pause unless `--no-pause`)
- Same task failed twice
- Plan contradiction surfaced
- `git fetch` shows new origin/master commits AND `--stop-on-drift` set
