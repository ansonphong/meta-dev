# Shared Workflow Protocol

This is the host-neutral contract for meta-dev. Host surfaces may expose commands,
skills, agents, or plain files, but they adapt to this protocol rather than
inventing different workflow semantics.

## Permission boundary

Classify the request before acting:

- `read`: inspect, explain, diagnose, review, audit, design, or plan. Source
  changes are not authorized.
- `write`: an explicit change request or go-word (`go`, `execute`, `ship it`,
  `--fix`). Changes are limited to the declared target.
- `sensitive`: auth, schema/migrations, payments, destructive operations, and
  cross-repo contracts require an explicit confirmation even when nearby work
  is authorized.
- Interactive desktop smoke tests always require their own scheduled approval.

Planning never implies execution. Review and audit are report-only by default.
A finding, `NEEDS_FIX`, `CONDITIONAL_PASS`, or `FAIL` is evidence, not permission
to edit or commit. With explicit fix authorization, remediation is a separate
step followed by focused verification and a new review.

## Six stages

| Stage | Name | Required artifact | Exit |
|---:|---|---|---|
| 1 | Brainstorm | bounded intent and alternatives | direction selected |
| 2 | Design | design/decision record | contracts and tradeoffs explicit |
| 3 | Plan | dependency-ordered plan with focused verifiers | executable plan |
| 4 | Harden | report-only gap record and disposition | no unresolved blocker |
| 5 | Execute | scoped task commits and focused outcomes | usable artifacts landed |
| 6 | Review | structured review verdict | `PASS`, or explicit disposition |

`planctl` is the only write door for plan state. A worker owns scoped edits,
verification, and its exact-path commit. The conductor owns stage transitions,
ledger handles, dashboards, and archival.

## Artifacts

Every workflow consumes only the artifacts it needs and preserves provenance:

- request: subject, declared scope, permission class, constraints;
- design: decisions, contracts, risks, falsifiers;
- plan: ordered tasks, declared files, dependencies, focused `Verify:` hooks;
- execution result: task id, commit SHA, verifier output, one result state;
- review: base/target refs, reviewed files, five dimension results, structured
  verdict, issues, confidence, and blast radius;
- delivery/operations: gate evidence, release target, rollback, final state.

Do not pass raw diffs through an orchestrator when a reviewer can compute the
diff from refs. Scratch artifacts use unique per-run paths and atomic writes.

## Result states

Execution has exactly one causal result:

- `FOCUSED_PASS`: the declared focused verifier passed.
- `TASK_RED`: focused evidence proves the task caused the failure.
- `BASELINE_RED`: the failure is pre-existing or outside declared scope.
- `INFRA_RED`: tooling or worker infrastructure failed.
- `BROAD_VERIFY_OMITTED`: a broad/manual check was intentionally not used as a
  task gate.

Only `TASK_RED` holds its causal branch. Independent branches continue.
Review has exactly one uppercase verdict: `PASS`, `CONDITIONAL_PASS`, or `FAIL`;
see `workflow-skills/code-review-protocol/`.

## Host capability adapters

### Claude Code

- `commands/*.md` remain the command names, flags, and canonical procedures.
- Native Agent/Task and skill discovery implement delegation.
- Claude keeps the reviewer/model configured by command or agent frontmatter
  and project settings. This protocol does not replace it with a universal
  model.

### Codex

- Every canonical command is an exact native skill name. In Codex CLI/IDE,
  invoke `$meta-dev:meta-planner`; on surfaces with the skill picker, select
  `meta-dev:meta-planner` with `@`.
- Pure Claude redirect aliases are not duplicated into Codex's limited initial
  skill index. `skills/command-router/` remains the compatibility fallback for
  those aliases and unknown spellings.
- `routes.json` maps every Claude command name to exactly one workflow
  subcommand, canonical procedure, and first-class native command skill.
- Plan, harden, and review use native `gpt-5.6-sol` with `high` effort by
  default, as configured under `meta_dev.codex.models`. Other workflows use
  their configured native route.
- The review default is native Codex. External/headless reviewers run only when
  the user explicitly selects one; their output never silently replaces the
  native verdict.

### Minimal/headless hosts

Resolve `routes.json`, read the target procedure, and translate capabilities:
filesystem reads, exact-path edits, shell checks, scoped commits, and optional
delegation. Missing delegation is a **bug in the host table**, not permission
to implement on the conductor. Look up `commands/meta-execute.md` Host dispatch
(Grok Build → `spawn_subagent`, Claude Code → `Agent`, Codex → spark/sol).
`--inline` is the only legal serial-on-conductor path. Permission, result-state,
review, and verification semantics never change.

## Routing

`routes.json` is exhaustive over `commands/*.md`. A route target has the form
`<workflow>.<subcommand>`. The target workflow must name a real curated Codex
skill, the subcommand must be declared once, and its procedure must exist.
Aliases deliberately share one target. Unknown names fail closed and must not
be guessed.
