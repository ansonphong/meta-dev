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

## CLAIMED → DONE — Full Checkbox Lifecycle (MANDATORY)

The plan file's checkboxes are the user's ONLY visibility into execution progress. Every task MUST pass through ALL three states in the plan file. No exceptions, no batching, no "I'll do it at the end."

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
