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

> **⛔ PRIME DIRECTIVE: NOTHING IN THIS SECTION IS EVER A REASON TO STOP WORKING.** The tree is SHARED and **4–20 concurrent agents is the normal, expected steady state.** Parallel is FINE. A dirty file is NOT an emergency, NOT a taboo, and NOT a blocker. **You are a battering ram: if you were given a task, you DELIVER it.** Refusing, stalling, polling mtimes, or escalating tree state to the user is a **FAILURE**, not caution.

### 🚫 FORBIDDEN — these are failures, however well-formatted

- ❌ "A file is dirty, so I stopped and I'm asking what to do."
- ❌ "A peer touched this N minutes ago, so I can't write it."
- ❌ "Another session may be active, so I did nothing."
- ❌ Emitting a report of blockers **instead of** the thing you were asked to do.
- ❌ Waiting / polling / re-checking / escalating instead of **just doing the work**.

### ✅ THE RULE: prefer clean, but NEVER stop for dirty

- **Prefer to start on CLEAN files** — it keeps diffs tidy and attribution honest. That is a *preference*, not a gate.
- **Need a file that's already dirty? TAKE IT AND KEEP MOVING.**
  - **Conductor** (owns git): read the diff, **commit the peer's coherent state as its own discrete commit** (`git add <path> && git commit`, message labels it worktree-clean of idle peer state), then make your edit. **Committing is always safe** — additive, recoverable, preserves their work in history forever.
  - **Worker** (commit-free by design): **just write the file and carry on.** Worst case the conductor's manifest-scoped commit also carries a peer's in-flight lines — a cosmetic attribution smudge, **not data loss**. That is strictly better than stopping.
  - Prefer targeted `Edit` over whole-file `Write` on a file you didn't create (replace merges; overwrite clobbers).
- **🚫🚫 `git stash` / `stash pop` / `stash drop` — ABSOLUTELY BANNED, NO EXCEPTIONS.** Stash is worktree-**GLOBAL**: on a tree with 20 live agents it rips out *every peer's* in-flight work at once, and `pop` can conflict and silently lose it. It is an invisible side-channel with no history. **COMMIT INSTEAD. ALWAYS.** There is no situation where stash is the answer. (Workers are mechanically denied it anyway.)
- **Never `discard` / `git checkout <file>` / `git restore <file>`** a peer's uncommitted work. Commit preserves it; these destroy it.
- **Escalate to the user ONLY for genuine ambiguity in WHAT they want — never for tree state.** Tree state is YOUR problem, and the answer is always the same: **commit it and charge on.**
- **Claim is an optional advisory hint, NEVER a gate.** `claude-headless-exec --claim <plan-dir>` records a coarse directory reservation in planctl's `claims` table (via the `worker-claim.sh` shim → `planctl claim`; the old `plans/_dashboard/.worker-locks/` + `worker-claims.jsonl` litter is retired). It must **never abort or block a dispatch** — prefer `--claim-warn` (warn, proceed). An unclaimed tree, or an overlapping claim, is **not** a reason to refuse work. If the registry is going unused, it is dead weight, not a safety mechanism.
- **Stage EXACTLY the worker's files — never a tree-wide add.** Each worker writes a touched-file manifest (`<output>.manifest.jsonl`, surfaced as `MANIFEST_FILE=` in the wrapper trailer). The conductor stages precisely those paths — `git add -- $(jq -r .path <manifest> | sort -u)` — NOT a `git diff`/`git status` scan (which picks up a concurrent session's edits in a shared tree). `git add -A` / `.` / `<dir/>` is **BLOCKED by the host guard hook** (it sweeps foreign edits). Sanctioned single-session dir-adds (plan archival) prefix `META_ALLOW_DIR_ADD=1`.
- **Workers are commit-free, mechanically.** The injected worker git-guard hook DENIES `git add/commit/stash/checkout/reset/rebase/merge/push` in worker context (read-only git stays available). The conductor owns git — always.
- **The exit code is honest.** A worker that reports `is_error:false` exits 0 (the wrapper reconciles the raw process code and no longer lets the EXIT trap force a 1). Trust the exit code together with the `is_error` field.

## CLAIMED → DONE — Full Checkbox Lifecycle (MANDATORY)

The plan file's checkboxes are the user's ONLY visibility into execution progress. Every checkbox — every `### Task N:` AND every `- [ ]` subtask checkbox — MUST pass through the lifecycle below. 1 runtime task ↔ 1 checkbox ↔ 1 handle (`` `T<phase>.<seq>` ``). Completing the task is what checks the box.

**Handles and CLAIMED are orthogonal.** The handle identifies the line (stamped by `task-stamp.py`). `CLAIMED` marks in-flight. The flip itself is **never an `Edit` of `[ ]`→`[x]`** — the conductor runs `task-done` (a shim over `planctl check` — the unified state layer's single write door; the atomic MD edit + index upsert + event append all happen inside planctl).

### State 1: CLAIM (before dispatch)

Before dispatching a subagent for a task:
1. Bind the handle: when the runtime task list is built from stamped master checkboxes, **each TaskCreate entry already stores its `` `T…` `` handle**. That handle is what you will flip later — do **not** parse free-text handle lists from the worker.
2. Optionally mark in-flight: Edit the plan line to insert `CLAIMED` prose (this is **not** the flip). Example: `` - [ ] `T4.2` CLAIMED Add Tile wiring ``.
3. Commit the claim: `chore(plan): claim <handle>` (or Task ID if unstamped legacy).

### State 2: DONE (immediately after green verify) — `planctl check` (via `task-done`), never Edit

**The instant a task's verify returns green** (async or sync), the **conductor** flips the box before anything else:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/task-done.sh <plan-path> <handle-from-runtime-entry>
# ^-- shim over `planctl check` (atomic MD edit + index upsert + event append).
# then commit the flipped plan file:
git add -- <plan-path> && git commit -m "chore(plan): mark <handle> DONE"
```

- **Conductor owns the handle at dispatch** (bound on the runtime entry). Worker may echo the handle for audit; a missing echo must **never** skip the flip. Worker never `Edit`s a checkbox.
- `planctl check` (via the `task-done.sh` shim) matches on the handle and only rewrites the mark `[ ]`→`[x]` — indifferent to CLAIMED/DONE prose on the line. The atomic MD write + index upsert + event append all happen inside planctl (the unified state layer); no `.task-lock` sidecar is written.
- Already `[x]` → no-op exit 0. Unknown handle → non-zero (named error) but remaining handles in a batch still process; treat unknown as a conductor bug, re-bind and retry.
- Human-tagged boxes (`by eye` / `by hand` / `gpu` / `manual`, or under an Acceptance/Human-verify heading) refuse without `--human`.
- **Never** hand-edit `[ ]`→`[x]`. That is the hole this primitive closes.

Only THEN advance to the next task.

### State 3: Verify (before report card)

Before rendering the execution report card (step 8), run:
```bash
grep -cE '^[[:space:]]*[-*][[:space:]]+\[[[:space:]]\]' <plan-file>
```
If the count is non-zero for tasks you believe are done, STOP — run `task-done` for the missing handles NOW. Never render the report card with unchecked completed tasks.

### The deterministic backstop — `on-run-complete.sh`

The checkbox discipline above is **guidance**; the **guarantee** is the `on-run-complete.sh` Stop hook (→ `planctl reconcile`, M3b). On any stop, for a plan at stage 5 it checks that all EXECUTION checkboxes are flipped (human-verify gates — `by eye` / `by hand` / `GPU` / `manual` — are excluded; those are the user's smoke test) AND a `review_verdict(pass)` is on record in planctl's `events.jsonl` (emitted via `planctl review <plan> pass --by <who>`):

- both met → it stamps DONE (stage 6) and re-renders the dashboard itself;
- run claimed `execute completed` with execution boxes still open → it **FAILS LOUD** to the inbox (never silently half-stamps);
- clean execution but no review pass on record → it flags "review missing" and leaves the plan at stage 5.

You still flip via `task-done` per-task and run the review — the gate is the deterministic backstop that makes silent half-completion structurally impossible.

### Stale CLAIMED check

If a task has been CLAIMED for >2 hours with no DONE, prompt the user before re-claiming.

## Resume Logic

If invoked on a plan with mixed DONE/OPEN tasks, resume from the first OPEN task:
- Skip DONE tasks (`[x]` on the stamped line)
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
