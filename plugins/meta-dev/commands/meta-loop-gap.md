---
name: meta-loop-gap
description: Adaptive evidence-backed hardening of plans or source, with deterministic checks and risk-targeted independent review
argument-hint: <plan-path|code-paths|feature:name|project> [--budget auto|low|medium|high] [--harden auto|focused|full] [--iterations N] [--target lean|standard|explicit] [--scan-model MODEL] [--fix]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /meta-loop-gap

Read `references/workflows/protocol.md` and `references/adaptive-workflow.md`.
This is report-only unless the user explicitly authorized scoped fixes.
Plan hardening may repair the plan artifact under a planning request, using
the IR renderer; it never authorizes source implementation before Stage 5.

## Resolve

1. Resolve the declared plan/source scope and root project contract. Read only
   routed durable context and configured learned patterns. No vendor-specific
   project rules path is assumed.
2. Resolve the intended executor, existing plan target, risks, and hardening
   policy with `scripts/workflow-policy.py`. `--scan-model` selects an
   available permitted detection model separately from the implementation
   executor. Do not infer executor capability from the reviewer's model.
3. `--harden` selects depth. Legacy `--budget low` maps to focused;
   `medium|high` maps to full; `auto` uses resolved policy. These control
   breadth, not permission. Explicit `--harden` wins. `--iterations N`
   is capped by configured maximum rounds; no unlimited loop.
4. Record scope, inspected revision, resolved policy, reviewer count, and
   permission boundary in the scan artifact using
   `references/plan-artifacts.md` naming. A rescan uses the prior scope/revision
   as evidence, never as proof that unchanged source is automatically safe.

## Deterministic floor

For plan mode run `bash ${PLUGIN_ROOT}/scripts/planner-validate.sh <plan-path>`
after the IR renderer's validation. Check linked phases and task-local
verification, not filename conventions. Inventory dependencies and declared
files; re-anchor affected live symbols and callers.

For source mode use applicable declared-file checks selected from the project's
actual toolchain. Do not run a guessed build, full suite, or deployment.
Report tooling failure separately from a code defect. Check security boundaries,
permissions, ownership, and focused verification at every depth.
Mechanical searches produce candidates, not automatic high-severity findings.

## Independent review

Focused mode starts with one capable native reviewer covering:
request coverage, internal consistency, data/contracts and dependencies,
error/edge paths, security, ownership, and verification soundness. Give explicit
scope/revision plus relevant contracts; allow the reviewer to inspect live code.
Full mode additionally inventories the applicable categories in
`references/hardening-categories.md` and assigns independent specialists where
a specific unresolved question warrants them, within the resolved reviewer cap.

One agent may cover related files or multiple review axes. Never require a
per-file, per-endpoint, per-role, or seven-agent semantic floor. A long file
alone does not justify a specialist. Sensitive boundaries still receive their
specific checks, regardless of how many agents perform them.
Missing native delegation means an explicitly labeled in-session review with
independence unverified, not an invented tool or silent external model. If an
independent verdict is a required gate, leave it pending.

Each finding includes category, file/symbol, evidence or a concrete falsifier,
severity, confidence, proposed disposition, and whether it blocks acceptance.
Confidence is not authorization and does not automatically fix a finding.
Deduplicate causes, not just wording. Reject speculative stylistic rewrites.

## Fix and recheck

With explicit source-fix authority, assign each causal fix a disjoint declared
write set and focused verifier. Fix backends (`--fix-backend` or existing
`--deep --glm --opus --sonnet --haiku --fable` shorthands) retain their runner
permission/availability requirements. These flags select a route; only an
explicit fix request authorizes edits. Conflicting backend selectors require
a choice, not silent substitution.

Plan edits go through validated IR rendering; plan state goes through planctl.
Recheck only invalidated checks and changed review scope. After the configured
round limit, report blockers as unresolved. A clean pass does not force another
wave, and a budget limit never forces a PASS.

## Completion

Stage 4 exits with no unresolved blocker and recorded advisory dispositions.
Use `NO GAPS REMAINING` only when none remain; otherwise report
`HARDENED — advisories` or `BLOCKED — unresolved findings` honestly.
Emit stage state through `stage-emit.sh`/planctl. Return scope, evidence,
actual agents/rounds used, fixes/commits if authorized, and outstanding gates.
The optional dashboard format is `references/loopgap-report-card.md`.

Recurring findings may be proposed as generalized patterns after evidence from
multiple runs. Write approved project patterns to the configured
`paths.learned_patterns` destination, not shipped command footers. Do not
automatically edit the installed plugin as a side effect of a project scan.
