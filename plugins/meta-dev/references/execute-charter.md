# Execute charter

The shared authority is `references/workflows/protocol.md`; adaptive depth and
ownership are defined in `references/adaptive-workflow.md`. User/project
instructions take precedence over skill guidelines. Explain a genuine conflict
rather than turning a personal workaround into a universal rule.

## Focused Verification Doctrine

Use the smallest declared check that proves acceptance. Classify through
`scripts/verify-scope.py` with actual declared source/test paths. Broad suites,
builds, and whole-project typechecks belong to explicitly authorized release/CI
work, not automatic task or phase gates. A named test file may use a narrowing
selector; a selector without a file is not focused.

Run a green verifier once for unchanged code. Relevant code/contract changes
invalidate that evidence and require a rerun. Critical security, migration,
value-transfer, and contract checks remain synchronous. Async verification is
allowed only when the host supports it and dependent work waits for evidence.

## Test Policy

Read `meta_dev.execute.test_policy` and the project testing contract.
`critical-only` is the fallback; `tdd-all` requests regression tests per task;
`none` adds none unless a higher-priority requirement demands them.
`test: no` does not waive verification. Ordinary UI work does not require
one test per component; choose evidence proportional to the failure risk.
Explicit user requests for regression coverage override the default.

## Ownership through completion

One implementation owner keeps the authorized task or coherent slice through
implementation, necessary caller/fixture migrations, ordinary repairs, focused
verification, self-check and exact-path commits. A scoped go covers reversible
technical decisions and ordinary in-scope repairs; neither a failing test nor a
changed implementation assumption needs another go. Keep coupled producer,
transport, consumer and lifecycle changes together. The conductor may implement
directly; delegate only when the benefit outweighs startup and handoff costs.

Before claiming completion, compare the actual diff and retained evidence with
the whole task: production changes, callers/fixtures, integration joins, intended
behavior, relevant refusal/stale-state/integrity behavior and explicit artifacts.
Record this compact check in the existing result record. A narrow green verifier
proves only what it covers. Do not weaken assertions, fake native success or
redefine acceptance to hide unfinished requirements. Self-check does not replace
required independent review.

Commit scoped edits before stopping or handing off, including red/exhausted
attempts: explicit-path staging and `git -C <absolute-root> commit --only
-m <message> -- <same-paths>`. Commit-on-red is durability, not acceptance,
an instruction to return or an ownership transfer. Continue viable in-scope work
within the agreed budget. Read-only work needs no commit.

Ordinary edit/test iterations stay with the owner. After two unsuccessful
corrective attempts against the same underlying failure, reassess the diagnosis;
continue only with a changed, evidence-backed approach or use one justified
escalation to a pre-authorized stronger completion owner. Use existing routing
and budgets, not model roulette. Track the failure and failed corrections in
the existing result record across task names and owner changes. A newly found
required fixture migration is unfinished scope, not another failed correction.

Reuse the current session when the host supports it. If transfer is necessary,
hand over the complete remaining task, exact commits, exclusive file ownership,
valid passing evidence, concrete defects and failed hypotheses. Release the old
owner before the new one edits. Do not repeat planning, hardening or general
discovery. Context compaction alone does not end accountability.

Stop affected work for a genuine external blocker, unavailable prerequisite,
scope/authority conflict, protected action, exhausted agreed budget or failed
bounded escalation. Preserve work and report the exact blocker and missing
evidence; keep independent ready work moving. No unlimited corrective loop or
retry of unchanged authentication, quota or availability failures. Existing
permission, human-action and infrastructure limits still apply.

## Shared worktree

Preserve unrelated edits. If a declared file overlaps another worker's active
changes, establish ownership or serialize; continue disjoint work. Never take,
overwrite, or commit a peer's unapproved dirty state. Existing dirt does not
prove a peer is idle. Claims are advisory metadata, not permission to collide.
Only planctl changes plan state; do not hand-insert CLAIMED or checkbox marks.

No tree-wide staging, stash, reset, restore, clean, rebase, non-fast-forward
merge, or destructive recovery. Follow the repository's branch policy, not a
hardcoded branch name. Workers never push; the conductor performs only remote
operations authorized by the user/project release contract.

If an executor cannot commit within its permitted environment, report the
limitation and preserve the evidence. Do not expand filesystem permissions
automatically. Choose an already-authorized capable route or ask when required.

## Causal failure posture

- `FOCUSED_PASS`: verification evidence; accept only after whole-task self-check
  and conductor inspection establish the declared outcome.
- `TASK_RED`: the same owner repairs the causally implicated work under the
  completion policy above; only its dependents wait.
- `BASELINE_RED`: do not repair unrelated debt; accept only if the task's own
  acceptance criteria are independently established.
- `INFRA_RED`: at most one transient infrastructure retry, accounting for runner
  retries; do not repeat unchanged auth/quota/unavailable-service failures.
- `BROAD_VERIFY_OMITTED`: do not run a broader substitute or claim it passed.
  Human acceptance remains open until observed.

Budget exhaustion does not complete a task. Keep independent work moving while
parking unsafe branches. Global safety denial, unusable critical contracts, or
a global plan/code contradiction stop affected work. An unchanged green test
needs no replay; a security gate is never removed for token savings.

## Scheduling, resume, and review

Resolve task/slice ownership with the workflow policy. Prefer bounded coherent
ownership and independent disjoint workers where available. Count nested
workers and fixers against actual host capacity. `--review each`, unknown
write sets, ownership overlap, and critical/human gates prevent unsafe slicing.
Minimal hosts execute sequentially with the same acceptance contract.

Resume from committed per-handle evidence and planctl state, re-anchoring relevant
live symbols. A stale claim alone does not transfer ownership.
The conductor inspects the actual scoped diff and evidence, accepts only completed
requirements through planctl, and immediately advances dependency-ready disjoint
work within capacity. Carry unresolved requirements explicitly. Use one conductor
per task ledger; do routine inspection, bookkeeping and commits directly.
A final native review covers the run including integration seams. Scoped phase
passes are not a final PASS. Fix within granted authority, then re-review the
changed scope. External consultants/review families remain explicit opt-ins.

`--autonomous` removes routine prompts for authorized work; it never adds
authority for source scope expansion, deployment, spending, destructive
operations, or unobserved human acceptance. See `references/autonomous-mode.md`.

Report accepted deliverables, unresolved requirements/blockers, current action
and any next owner briefly. A silent live runner is not failed because an
observation timed out. Follow host monitoring and communication requirements.
After a substantial interval without a deliverable, new acceptance evidence or
closure of a prerequisite, identify the bottleneck and simplify the next action;
do not add orchestration or paperwork.
