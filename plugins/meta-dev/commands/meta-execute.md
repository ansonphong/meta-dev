---
name: meta-execute
description: Execute an approved plan with adaptive task or slice ownership, focused verification, durable commits, and native review
argument-hint: <plan-path> [--granularity auto|task|slice] [--inline] [--strict] [--review each|phase|end|auto] [--budget auto|low|medium|high] [--codex|--grok|--sonnet|--deep|--glm|--agy|--cursor] [--effort <level>]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
model: opus
---

# /meta-execute

Execute only with an explicit go for the scoped plan. Read
`references/workflows/protocol.md`, `references/adaptive-workflow.md`, and
`references/execute-charter.md` before dispatch. Source implementation is
Stage 5; planning and review alone never authorize it.

## Resolve and schedule

1. Resolve the plan, project contract, intended executor, risk, and policy with
   `scripts/workflow-policy.py`. Honor explicit model/backend, target, and
   granularity. Preserve runner-specific effort validation. Unknown models use
   standard/task policy. Backend flags select the corresponding existing runner;
   no flag means the host-native configured route, not a foreign pool.
   Normalize a multi-phase directory to its `00-master-plan.md` before every
   planctl/stage/review call. The validator may still consume the directory.
2. Parse task handles from the canonical ledger; v1.1 single-file plans use
   their task units. Use one visible runtime entry per acceptance handle, with
   dependencies and actual backend. Do not double-count a heading and its ledger
   row. If no native tracker exists, report concise progress and use planctl.
   Legacy checkbox-free v1.1 artifacts need re-rendering from their retained IR
   to add the canonical ledger before execution. Do not treat an unresolved
   planctl handle as success or silently hand-add state marks.
3. Preflight exact paths and branch policy. Leave unrelated dirty files alone.
   For overlapping changes, establish ownership before editing/committing;
   continue independent work. Never auto-commit another session's state.
4. Resolve bounded coherent slices using the adaptive policy. Do not cross a
   permission, critical-risk, human, or phase-review gate. Independent slices
   may run concurrently only with disjoint declared write sets, counting fixers
   and nested workers against the host capacity. Unknown write sets serialize.
5. Dispatch using `references/execute-dispatch.md`. The worker owns local
   implementation, verification, and exact-path commits; the conductor owns
   plan state and authorized remote operations. Native delegation is preferred
   when useful and permitted. `--inline`, absent delegation, or a host
   prohibition uses sequential ownership with the same safety/acceptance rules.
   Never invent a missing worker primitive or silently launch a paid backend.

## Host dispatch

| Host | Native surface |
| --- | --- |
| Claude Code | available Agent/Task interface and configured model |
| Codex | available native delegation, or explicitly configured headless runner |
| Grok Build | available spawn_subagent surface and configured model |
| Minimal/headless | sequential scoped ownership when delegation is unavailable |

Tool presence, permissions, and capacity must be observed, not inferred from
the model name. Backend loading details live in the runner/adapters.

## Execute and accept

Emit `bash ${PLUGIN_ROOT}/scripts/stage-emit.sh "<plan-path>" execute in_progress`
before implementation. For each task/slice:

- Inline relevant task sections and per-handle acceptance, not the entire plan.
  Re-anchor live code once at ownership start and after relevant drift.
- Classify each Verify command with `scripts/verify-scope.py`, passing the
  declared source/test paths. Run only focused/scoped checks. Never add a full
  suite, build, or whole-project typecheck as a task or phase gate.
- Preserve edits with explicit-path local commits even on red. Require actual
  command, exit code, output evidence, and causal result for each handle.
- `FOCUSED_PASS`: accept the proven outcome.
  `BASELINE_RED`: accept only when the task's own acceptance is established.
  `TASK_RED`: repair/park that causal branch; independent work continues.
  `INFRA_RED`: retry infrastructure once; never claim unverified acceptance.
  `BROAD_VERIFY_OMITTED`: report omitted broad evidence; it is not a pass.
  Human gates remain open until observed, even if implementation is complete.
- Promptly update each accepted handle through
  `bash ${PLUGIN_ROOT}/scripts/planctl.sh check <plan> <bound-handle>`.
  Workers never edit checkboxes. A ledger commit may persist multiple updates
  at a bounded slice seam, not at the end of the whole run.
- Use at most two scoped repair attempts before reporting a parked branch.
  Never treat budget exhaustion as success.
- At committed slice/phase seams, use the session-bound context watchdog from
  `workflow-skills/agentic-exec-loop/references/loop-protocol.md`. Unknown
  telemetry is nonblocking. Drain running workers/verifiers before handoff.

`--strict` waits for focused verification before advancing dependencies; it
does not broaden checks. No green verifier is repeated unless relevant source
or its acceptance contract changed.

## Review and completion

`--review auto` uses phase reviews for multi-phase work, otherwise end review;
critical tasks use an each-task gate. `each` serializes dispatch and disables
slicing. `phase` reviews each phase. `end` reviews the run once. Every closing
review must cover cross-task/cross-phase integration, not only the last task.

Use `workflow-skills/code-review-protocol/SKILL.md` and the configured native
reviewer. One native closing review suffices. External/cross-family review is
opt-in; selecting a headless executor does not also select a foreign reviewer.
Stage 6 does not invoke `/meta-eval`, `/meta-audit`, or `/housekeeping`.
If native independent delegation is unavailable, label in-session review as
self-review with independence unverified. When an independent verdict is required,
obtain a permitted reviewer or leave that gate pending; sequential implementation
fallback does not authorize recording self-review as an independent PASS.

Fixes require the existing scoped implementation authority. Re-review repaired
scope. Persist a covering PASS with exact reviewed refs and source scope:

```bash
bash ${PLUGIN_ROOT}/scripts/planctl.sh review <plan-file> pass --by <reviewer> \
  --repo-root <absolute-source-repo> --base-ref <start-sha> --target-ref <reviewed-sha> \
  --scope <repo-relative-file> --scope <another-file>
```

Include every file needed to cover the completed run; omit neither changed
implementation nor its acceptance surface. Scoped working contents must match
the reviewed commit. Review evidence binds file content and the plan contract;
source/contract changes invalidate it, while ledger-only commits do not.
Old unbound PASS events require a fresh covering review. Cross-repository work
must retain a separate covering verdict per source repository; do not use a
single-repository event to claim review of another repo. Prefer repository-owned
member plans; leave aggregate completion pending when the current single-repo
evidence contract cannot cover the whole plan.
There must be no unresolved blocking acceptance. Do not use a partial phase PASS as
the final run verdict. The completion hook reconciles plan state and dirty
runbook dashboards; it is a backstop, not evidence that a review happened.

Archive only after required acceptance/manual gates pass, using the state door.
Push only when the user/project release contract authorizes it; never deploy
implicitly. Report accepted/parked handles, scoped commits, actual verification,
review verdict, remaining manual gates, and the plan's current location.
Use `references/execute-report-card.md` when the host supports that presentation.

## Additional flags

Backend flags `--deep --glm --grok --sonnet --codex --agy --cursor` retain their runner
contracts, availability checks, and configured pauses. `--budget` is a ceiling
from `references/execute-budget.md`; `--effort` must be supported by the chosen
runner. `--pause-before=<id>` stops before that handle and splits a slice.
`--dry-run` resolves/prints inventory and policy without dispatch or source edits.
`--no-deploy` never changes acceptance. `--no-pause` and `--autonomous` may
defer human gates but never waive security, permissions, or required verification.
`--stop-on-drift` reports remote divergence; it does not authorize polling,
pulling, or rewriting history. See `references/autonomous-mode.md`.
