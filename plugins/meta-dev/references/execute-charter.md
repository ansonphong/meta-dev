# Execute Charter — Anti-Paranoia, Momentum, Failure Posture, Protocols

## Execution Posture — Optimistic Momentum (default)

`/meta-execute` is **optimistic by default**: prove the changed behavior with the
smallest focused check, accept that evidence once, and keep dispatching forward.
Failures park only the causally implicated branch while independent work keeps
moving. There is no phase-end or end-of-run whole-suite acceptance gate.
`--strict` serializes focused verification only; it never authorizes broad
checks and it does not turn an ordinary branch-local red into a whole-run STOP.

## Verify Posture — Focused Causal Evidence (default)

**The task's declared focused verify is the complete acceptance surface.** Run
only the named file, node, contract, grep, or equally narrow command that can
causally prove the task. Ordinary focused verifies may run asynchronously;
critical focused verifies run synchronously. In either case, the result affects
only the smallest implicated branch.

**COMMIT-ON-RED INVARIANT.** Persistence and acceptance are separate. Any
implementation worker or fixer that changed declared files stages only those
exact paths and creates a local commit before every return, including red,
BLOCKED, strict-mode return, failed review, or exhausted repair. `TASK_RED`
blocks acceptance only for its implicated branch; `BASELINE_RED` and
`INFRA_RED` never block the local commit. A later review does not rewrite task
commits already accepted by focused evidence. Read-only work and contradictions
found before editing create no commit.

**The invariant is universal — no backend is exempt.** A worker that edits and
returns without committing leaves *unowned* state, which on a 4-20 agent tree is
adoptable: the next peer's broad `git add` absorbs it and the author, message,
and revert boundary are gone. So when a backend appears unable to commit, the
only legitimate responses are **fix the executor** (the inability is nearly
always our own configuration) or **route the task to a backend that can**, and
say why. Writing the exemption into a task brief is never one of them — a
constraint that belongs to a tool must live in that tool's dispatch path, where
it applies automatically and cannot outlive its cause. Retyped into per-task
prose it carries no scope marker, and a conductor will paste it onto a backend
it never applied to. Precedent: "run NO git command, the conductor commits" was
authored for Codex's read-only `.git` on 2026-07-20, canonized in a handoff as a
reusable preamble, and was reaching fully-capable Claude workers hours later
while peer sessions twice swept up the uncommitted results. The real fix was one
`writable_roots` entry in `codex-headless-exec`.

1. **Inline = instant only.** After a worker returns, run only focused checks
   declared by the task or instant integrity checks on its committed diff. A
   broad command is not an additional confidence gate.
2. **Commit, then verify.** Launch the task's focused `Verify:` command async
   and advance immediately to ready work. Track it as `testing <ID>`. The
   critical focused checks named below remain synchronous.
3. **Classify before acting.** Every result enters exactly one canonical state:
   - **`FOCUSED_PASS`** — the declared focused check is green. Complete and
     release the task; one green is green and is never rerun.
   - **`TASK_RED`** — causal evidence ties the failure to the task's touched
     paths or named focused test paths. Repair only the smallest implicated
     branch and its direct dependents.
   - **`BASELINE_RED`** — the failure is unchanged from the task's pre-state or
     wholly outside its declared task/test paths. Complete and release the
     task; never fix, defer, or block on this result.
   - **`INFRA_RED`** — the runner, tool, service, or environment failed rather
     than the code. Retry the infrastructure once, then report it without
     blaming or repairing code; continue all work supported by a committed
     usable artifact.
   - **`BROAD_VERIFY_OMITTED`** — a suite, build, typecheck, slow/GPU/integration
     sweep, or other check broader than the task contract. It is never run,
     fixed, deferred, or treated as blocked by `/meta-execute`.
4. **Readiness comes from artifacts.** A dependency becomes ready when the
   producer has committed a usable artifact with the evidence its contract
   requires. Checkbox ceremony records that fact; it does not create readiness.
5. **Critical focused gate.** `money-path`, `release-stability`, `schema-drift`,
   auth/crypto, payment/value-transfer, migration, and critical contract work
   still run their declared focused verification synchronously. Critical means
   focused and blocking for its causal branch, never broad.
6. **Drain focused jobs only.** Completion waits only for launched focused jobs
   and branch-local repair dispositions. `BROAD_VERIFY_OMITTED` is not a debt to
   run later.

`--strict` changes scheduling, not scope: it serializes the same focused checks.
It never runs a broad check, retries a green, repairs `BASELINE_RED`, or turns
ordinary fixer exhaustion into a whole-run STOP.

## Test Policy — Critical-Only (default)

**Do not write a test for every task.** Most tasks verify by their cheap `Verify-After` check (build passes, grep is clean, run-by-eye) — not by an authored test. Governed by `meta_dev.execute.test_policy` (default `critical-only`):

- **`critical-only` (default)** — a written test is generated/run ONLY for **critical-breakage** tasks: data-corruption paths, auth/crypto verification, payment/value transfer, DB migration, serialization round-trip, cross-service API contract (refined by the host `CLAUDE.md` testing policy if it names specific critical surfaces). Every other task is verified by its Verify command alone.
- **`tdd-all`** — legacy: every task runs the full failing-test-first TDD cycle.
- **`none`** — no authored tests; verify by cheap checks only.

`/meta-planner` encodes the decision per task as a `test: yes` / `test: no` tag; `/meta-execute` reads that tag to pick the dispatch directive (`references/execute-dispatch.md` → Test directive), falling back to this config when a task is untagged. **`test: no` tasks must NOT have a test written for them** — adding one is scope creep. Verify ≠ test: a Verify-After is satisfied by a build/grep/run, and only critical tasks escalate to an actual test. Fewer tests is the intended posture; the verify gates above (async, non-blocking) still apply to whatever verification a task does declare.

## Fast Test Doctrine — make every test cycle CHEAP (non-negotiable)

The single biggest execution cost is slow test cycles. Measured on a real run: `pytest backend/tests/ -k "headline or refresh"` = **30s** (it collects all 233 files, THEN deselects — `-k` filters *after* collection), versus `pytest backend/tests/test_base_node.py` = **1.7s**. That's an **~18× tax paid on every red→green cycle.** These rules make every cycle cheap; they apply to ALL backends (the main thread, and every GLM/DeepSeek/Codex worker).

1. **PATH-SCOPE ALWAYS — `-k` is BANNED as the primary selector.** Name the file(s) or node: `pytest path/to/test_thisfeature.py -q` (or `…::test_name`). NEVER run bare `pytest`, `pytest <dir>/`, or `pytest … -k <expr>` in a per-task cycle — they all collect the whole tree and pay the full collection tax every time. Path-scope first; you may add `-k`/`-x` *on top of* a named file to narrow further, never as the only selector.
2. **FAST-ONLY in the execution loop.** Run only fast, pure-logic focused
   tests. Slow/GPU/integration sweeps are `BROAD_VERIFY_OMITTED`; a separately
   authorized manual or CI workflow may own them, but `/meta-execute` does not
   defer them as execution debt.
3. **NO broad commands.** `svelte-check`, `tsc --noEmit`, broad builds, and
   suite/directory runs are never added as phase or completion gates. Per task,
   run only its single focused contract.
4. **Optimistic + async (per Verify Posture above).** Launch the one path-scoped test in the background, advance immediately, circle back only if it actually goes red. Never wait on a green test. Never re-run a passing test "to be sure" — one green is green.
5. **SECURE — keep the critical focused gate.** Critical-breakage and
   security-critical tasks still verify their named contract synchronously.
   Speed removes unrelated collection, never the focused evidence that protects
   correctness and security.

**Momentum gate.** Classification is causal, not exit-code-shaped. A red line is
not a regression until evidence connects it to the changed task/test paths.

**On `TASK_RED`:**
1. Spawn a background fixer scoped strictly to the causal failure, `T`'s
   declared files, and only the direct dependents needed to reproduce it. The
   fixer commits every edited attempt before returning.
2. Park only `T`'s smallest causal branch. Independent tasks — including later
   phases with usable committed inputs — keep dispatching.
3. A focused pass releases the branch. Ordinary fixer exhaustion writes the
   dossier and leaves that branch parked; it never stops unrelated work.

**Whole-run STOP is exceptional.** Stop only for an execution guard or safety
gate, a global plan↔code contradiction, genuine schema divergence, or a critical
contract whose unusable artifact makes the run globally unsafe. Ordinary red,
stub hits, infrastructure failure, and fixer exhaustion are branch-local.

**Focused completion.** The run is accounted for when every branch is released
or explicitly parked with evidence and every launched focused job is drained.
There is no broad acceptance sweep to make the focused results "more green."

**Conflict safety.** Fixers touch only the failed task's files; dependents (overlapping files) are `deferred`, so the main loop advances only disjoint-file work — no parallel-commit collision. The conductor owns remote synchronization and uses only the repository's permitted fast-forward flow; genuine conflict → surface.

## Conductor law — this thread does not implement

The `/meta-execute` conductor does **not** implement plan tasks. Each verifiable checkbox is a fresh host-native subagent (Grok Build → `spawn_subagent`; Claude Code → `Agent`, or pooled Grok if host `CLAUDE.md` says so; Codex → spark mechanical / sol hard). The worker commits its own edits. The conductor reads a one-line result and flips `task-done`. `--inline` is the only exception, and only when the user passed it. Missing a worker primitive is a bug in the host table, not permission to type the plan on this thread. When unsure, spawn. Stay native only for the slash harness, vision, a true one-liner, permission/stage gates, and integrating that one-line return.

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
  - **Worker**: **just write the file and carry on**, then commit your own task's files by explicit path before every return, whether verification is green or red. Worst case a commit also carries a peer's in-flight lines in a file you both touched — a cosmetic attribution smudge, **not data loss**. That is strictly better than stopping.
  - Prefer targeted `Edit` over whole-file `Write` on a file you didn't create (replace merges; overwrite clobbers).
- **🚫🚫 `git stash` / `stash pop` / `stash drop` — ABSOLUTELY BANNED, NO EXCEPTIONS.** Stash is worktree-**GLOBAL**: on a tree with 20 live agents it rips out *every peer's* in-flight work at once, and `pop` can conflict and silently lose it. It is an invisible side-channel with no history. **COMMIT INSTEAD. ALWAYS.** There is no situation where stash is the answer. (Workers are mechanically denied it anyway.)
- **Never `discard` / `git checkout <file>` / `git restore <file>`** a peer's uncommitted work. Commit preserves it; these destroy it.
- **Escalate to the user ONLY for genuine ambiguity in WHAT they want — never for tree state.** Tree state is YOUR problem, and the answer is always the same: **commit it and charge on.**
- **Claim is an optional advisory hint, NEVER a gate.** `claude-headless-exec --claim <plan-dir>` records a coarse directory reservation in planctl's `claims` table (via the `worker-claim.sh` shim → `planctl claim`; the old `plans/_dashboard/.worker-locks/` + `worker-claims.jsonl` litter is retired). It must **never abort or block a dispatch** — prefer `--claim-warn` (warn, proceed). An unclaimed tree, or an overlapping claim, is **not** a reason to refuse work. If the registry is going unused, it is dead weight, not a safety mechanism.
- **The touched-file manifest is audit + recovery, not normal commit ownership.** Each worker writes `<output>.manifest.jsonl`; the conductor checks that manifest against the worker's commit. If a broken/legacy worker returns dirty, the conductor recovers by staging precisely those manifest paths and making the local commit before any other action — never by scanning `git status`/`git diff`. `git add -A` / `.` / `<dir/>` remains blocked. Sanctioned single-session directory adds (plan archival) prefix `META_ALLOW_DIR_ADD=1`.
- **Workers COMMIT THEIR OWN WORK — one coherent commit per task attempt** (policy change 2026-07-19; supersedes the old commit-free rule). Before every return after editing, stage the exact files you touched by full path and commit them, even when verification is red. Modular commits beat one end-of-run conductor sweep: history reads as coherent units, and attempted work is durable the moment the worker stops. Flip the ledger handle only after a releasable focused outcome (`FOCUSED_PASS` or `BASELINE_RED`), so the ledger never runs ahead of acceptance.
- **What the worker git-guard hook still DENIES** (it was never really about `commit`): tree-wide staging — `git add -A|.|-u|<dir>/` and `git commit -a` — which sweeps a concurrent session's in-flight lines into your commit (incident 2026-07-05); every destroyer of uncommitted peer work — `stash/checkout/switch/restore/reset/clean`; every shared-history rewrite — `rebase/merge/cherry-pick/revert/am/commit --amend`; and the remote — `push/pull/fetch` (the conductor owns the remote). `git add <explicit paths>`, `git commit`, and all read-only git are ALLOWED.
- **Stage by name, never by scan.** Use the worker's own touched-file list — `git -C <abs-repo-root> add path/a.ts path/b.svelte` — never a `git status`/`git diff` sweep, which picks up peer edits in a shared tree.
- **The exit code is honest.** A worker that reports `is_error:false` exits 0 (the wrapper reconciles the raw process code and no longer lets the EXIT trap force a 1). Trust the exit code together with the `is_error` field.

## CLAIMED → DONE — Full Checkbox Lifecycle (MANDATORY)

The plan file's checkboxes are the user's ONLY visibility into execution progress. Every checkbox — every `### Task N:` AND every `- [ ]` subtask checkbox — MUST pass through the lifecycle below. 1 runtime task ↔ 1 checkbox ↔ 1 handle (`` `T<phase>.<seq>` ``). Completing the task is what checks the box.

**Handles and CLAIMED are orthogonal.** The handle identifies the line (stamped by `task-stamp.py`). `CLAIMED` marks in-flight. The flip itself is **never an `Edit` of `[ ]`→`[x]`** — the conductor runs `task-done` (a shim over `planctl check` — the unified state layer's single write door; the atomic MD edit + index upsert + event append all happen inside planctl).

### State 1: CLAIM (before dispatch)

Before dispatching a subagent for a task:
1. Bind the handle: when the runtime task list is built from stamped master checkboxes, **each TaskCreate entry already stores its `` `T…` `` handle**. That handle is what you will flip later — do **not** parse free-text handle lists from the worker.
2. Optionally mark in-flight: Edit the plan line to insert `CLAIMED` prose (this is **not** the flip). Example: `` - [ ] `T4.2` CLAIMED Add Tile wiring ``.
3. Commit the claim: `chore(plan): claim <handle>` (or Task ID if unstamped legacy).

### State 2: DONE (after a releasable focused outcome) — `planctl check` (via `task-done`), never Edit

**The instant a task reaches `FOCUSED_PASS` or `BASELINE_RED`**, the
**conductor** releases it and flips the box before anything else. `INFRA_RED` is
reported after its one retry and does not trigger code repair; artifact
usability, not checkbox state, decides whether its dependents are ready.

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

The flip records acceptance; it is not a prerequisite for dispatching a
dependent whose committed usable artifact is already ready.

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

Default = optimistic momentum. `--strict` serializes focused verification only.

| Situation | Default (momentum) | `--strict` |
|-----------|--------------------|-----------|
| `FOCUSED_PASS` | Complete/release; never rerun | Same, before next focused verify |
| `TASK_RED` | Repair smallest causal branch; independent work continues | Same repair, scheduled serially |
| `BASELINE_RED` | Complete/release; never fix or block | Same |
| `INFRA_RED` | Retry infra once, report, continue usable branches | Same |
| `BROAD_VERIFY_OMITTED` | Never run/fix/defer/block | Same |
| Ordinary fixer exhaustion | Park that branch; independent work continues | Same |
| Global plan <-> code contradiction | Whole-run STOP; never improvise | Same |
| Genuine schema divergence / unusable critical contract | Whole-run STOP with causal evidence | Same |
| Parallel session pushed to origin/master | If local HEAD can fast-forward, review then merge `--ff-only`; otherwise halt and surface divergence. Never rebase | same |

## Pause Gates

Default = no pause between releasable focused outcomes. Only pause when:
- `--pause-before=<task-id>` matched
- Risk tag is `money-path` or `release-stability` (auto-pause unless `--no-pause`)
- Global plan contradiction surfaced
- Genuine schema divergence or a globally unusable critical contract
- `git fetch` shows new origin/master commits AND `--stop-on-drift` set

**Under `--autonomous`, every pause gate above is OFF** (the flag implies
`--no-pause`) — the user is asleep and a pause is just a stall until morning.
Risk-tagged work still *verifies* synchronously per Verify Posture #5; it simply
does not wait for a person. The Failure Posture matrix and whole-run STOP list
are unchanged: a branch-local blocker parks THAT subject and the run continues elsewhere,
landing in the Autonomous Run Report rather than in a prompt. Full contract and
the hard floor: `references/autonomous-mode.md`.

## Escalation — consult Fable before you wake the human

When the run is about to stop and ask the user a **judgment call** — an
architecture choice, an under-specified plan, a design trade-off, implementation
taste, a bug whose next move is unclear — route it through the `fable-consult`
skill FIRST:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/fable-consult.sh \
  --question "<the decision>" --plan <plan-path> [--autonomous]
# 0 ADOPT · 10 escalate (low confidence) · 11 escalate (veto class)
# 12 DEFER (REVIEW-ME) · 2 error → escalate. FAIL CLOSED.
```

Fable's verdict is adopted only at ≥0.90 **and** only when it carries `file:line`
evidence plus a concrete falsifier — a bare confidence number is not a
measurement and the script caps one that lacks its backing. Below the bar, you
still escalate, but the escalation now leads with Fable's recommendation so the
user can approve in one word. Report the confidence **exactly as returned**.

This never applies to safety-class decisions — destructive, deploy, security,
money-path, schema, cross-repo contract, spend-or-send, scope expansion. Those
are on the veto list and always reach a person. Nor to tree state, which is never
a judgment call at all: commit and charge on. Contract, calibration rationale and
the full veto list: `workflow-skills/fable-consult/SKILL.md`.
