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

## Durability and ownership

Workers commit their own declared edits before returning, including red or
exhausted attempts. Verification gates acceptance, not preservation. Use
explicit-path staging and `git -C <absolute-root> commit --only -m <message>
-- <same-paths>`. A slice may share a coherent commit across related handles,
with separate acceptance evidence. Read-only work needs no commit.

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

- `FOCUSED_PASS`: accept with evidence and update the bound handle via planctl.
- `TASK_RED`: repair or park only the causally implicated branch.
- `BASELINE_RED`: do not repair unrelated debt; accept only if the task's own
  acceptance criteria are independently established.
- `INFRA_RED`: at most one infrastructure retry, then report unknown acceptance.
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
A final native review covers the run including integration seams. Scoped phase
passes are not a final PASS. Fix within granted authority, then re-review the
changed scope. External consultants/review families remain explicit opt-ins.

`--autonomous` removes routine prompts for authorized work; it never adds
authority for source scope expansion, deployment, spending, destructive
operations, or unobserved human acceptance. See `references/autonomous-mode.md`.
