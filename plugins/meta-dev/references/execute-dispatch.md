# Execution dispatch contract

Read `references/adaptive-workflow.md` and `references/execute-charter.md`.
Use one host-native worker per resolved task or coherent slice, with only the
relevant plan sections inlined. A model route is not a permission grant.
`scripts/jev-decide.sh` is a suggestion only. It does not grant a go-word,
bypass git bans, or spawn the worker. A missing key fails open.

## Worker brief

```text
Objective: <bounded outcome>
Repository: <absolute root>; inspected revision: <sha>
Owner: <worker identity>; handles: <conductor-bound handles>
Declared files: <explicit paths and semantic anchors>
Task sections: <each relevant section, interfaces, acceptance, dependencies>
Integration joins: <producer → transport → consumer; adjacent read-only callers>
Verification: <per-handle command, allowed paths, expected result>
Budget: <resolved turns/time and task/slice limit>

Host timeout (binding): headless workers run 30–180 min. Launch with
background=true and host timeout 0 (Grok) / no short Bash timeout (Claude).
Never pass 5s, 2 min, or 5 min as the tool timeout. Never copy that value
into --timeout. Wait with timeout_ms ≥ 1800000 or until the runner exits.

Before an integration slice, trace its relevant producer → transport → consumer
joins and adjacent read-only callers. Resolve concrete ownership/interface gaps
within declared scope together; report an out-of-scope gap for rescheduling.
Keep the trace bounded to the task. Re-anchor named symbols against live code
before editing. Preserve unrelated changes; do not claim or commit a peer's
overlapping edits. Report an ownership
conflict and continue independent work. Follow the project's branch policy.

Implement only declared work. After edits, create an explicit-path local commit
before returning, including a red/exhausted attempt; never push. Use:
git -C <absolute-root> add -- <explicit-paths>
git -C <absolute-root> commit --only -m "<message>" -- <same-paths>
No tree-wide staging, stash, reset, restore, clean, rebase, or history rewrites.

Run each declared focused verifier. Do not rerun unchanged green evidence.
For changed behavior, verify the intended valid path and relevant refusal path
with focused evidence; state when no refusal path applies.
A task-caused failure is TASK_RED; pre-existing evidence is BASELINE_RED;
tool failure is INFRA_RED. Do not silently substitute a broad suite or a
different verifier. Manual gates stay unaccepted until observed.
Return per handle: SHA, files, command, exit code, output tail, canonical state,
remaining acceptance items, and surprises. Do not mutate the plan ledger.
```

A shared slice commit may support multiple handles, but never share an acceptance
claim without its evidence. Dependency order within the slice remains binding.
If scope or risk changes, return the committed partial result for rescheduling.

## Verification and repair

Classify commands with `scripts/verify-scope.py` using declared source/test paths,
not paths guessed from the command. Only `focused` and `scoped_check` execute.
Security, migration, value-transfer, and critical contract checks are synchronous.
Ordinary checks may overlap independent work when the host supports it.

`test: yes` follows the declared regression/TDD contract; `test: no` does not
require a new test, but still requires focused evidence. Project/user testing
requirements override the default critical-only policy. No build or full suite
is added as a task gate. Syntax/stub searches are evidence to inspect, not
proof that a legitimate empty return or abstract method is a defect.

A fixer owns only the causally affected declared paths. Batch independent,
compatible findings in a coherent repair, preserving per-finding evidence and
the original branch attempt count. Preserve scoped attempts
with local commits. At most two repair attempts before parking that branch;
an external consultant requires separate authorization. Never widen to peer
files or rotate model families simply because infrastructure failed.

## Acceptance and review

The conductor checks returned scope and evidence, then calls
`bash ${PLUGIN_ROOT}/scripts/planctl.sh check <plan> <bound-handle>` for each
accepted outcome. Ledger commits may be coalesced at a bounded slice seam;
state updates are prompt, not an end-of-run batch. Reuse gathered status for
bookkeeping at useful completion seams. Read-only tasks make no
artificial implementation commit.

Review through `workflow-skills/code-review-protocol/SKILL.md` at the selected
cadence. One native review covering the run satisfies Stage 6; cross-family
review is opt-in. The reviewer computes the diff from explicit refs and may
read live files. After repairs, retain clean findings and unchanged green
evidence; re-review repaired scope and impacted assumptions only. If a shared
contract changed, name it and explain why broader review is needed. Record
unresolved
findings honestly; exhausted/manual/infra results are not a PASS.
