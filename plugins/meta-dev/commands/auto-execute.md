---
name: auto-execute
argument-hint: <task or plan> [--deep|--grok|--codex|--sonnet|--opus|--glm|--agy|--fable] [--flash] [--vision] [--budget auto|low|medium|high] [--effort <level>] [--repo <name>] [--readonly] [--max-turns <n>] [--autonomous]
description: Route a bounded task or approved plan through the configured adaptive workflow, preserving intent, scope, permissions, and host capacity.
---

# /auto-execute

A routing adapter, not a second execution engine. Read
`references/workflows/protocol.md`, `references/work-ladder.md`, and
`references/adaptive-workflow.md`. The current host coordinates; no named
provider, account quota, or mandatory external pool is assumed.

## Classify the request before routing

- Explanation, research, review, audit, and diagnosis remain read-only unless
  the user requested an artifact or implementation. A plan path alone does not
  authorize its execution. `--readonly` forbids source, ledger, and dashboard
  writes; return evidence in the final message.
- Approved plan implementation routes once to `commands/meta-execute.md`.
  Pass the plan, explicit go, selected backend/model, granularity, review mode,
  budget, and other supported flags. That procedure owns task/slice scheduling,
  focused verification, state updates, closing review, and completion.
- A multi-plan campaign routes to `commands/runbook.md`. Do not create an
  additional phase-worker loop around its member conductors.
- Named planning, hardening, or review operations use their corresponding
  command/shared protocol, with the original scope and stage ceiling.
- A standalone task follows the bounded dispatch procedure below. Do not
  decompose a coherent small job simply to create more workers.

## Resolve policy and dispatch a standalone task

1. Resolve project rules from root `AGENTS.md`, routed durable context, and
   canonical skills. Repository aliases come from `.meta-dev/repos.json`;
   legacy vendor topology files are compatibility inputs.
2. Resolve actual executor, risk, and ownership with
   `scripts/workflow-policy.py`. Explicit selections and configured pauses
   remain binding. External backends require their existing authorization and
   availability checks. Unknown models use conservative standard/task policy.
3. Keep tightly related acceptance outcomes in a bounded coherent slice.
   Independent work may run concurrently only with disjoint declared write
   sets. Unknown write sets serialize. Use one host-wide worker cap, including
   nested conductors, workers, reviewers, and fixers; never multiply per-layer
   caps. Use sequential ownership when native delegation is absent or forbidden.
4. Brief the available host-native worker or explicitly selected headless
   runner using `references/execute-dispatch.md`. Include relevant task
   excerpts, live anchors, scoped paths, acceptance criteria, and read-only
   intent. Codex/Grok headless workers receive direct tasks or supported skill
   files, not Claude slash commands. Do not require nested delegation.
5. For authorized code edits, use focused verification only: not a broad suite
   per task and not at phase end. Preserve per-outcome evidence.
   `BASELINE_RED` does not block independent work, but is not evidence that
   acceptance passed. `TASK_RED` repairs or parks only its causal branch.
   Reuse verifier evidence only while relevant code and contracts are unchanged.
6. Inspect the result contract, actual evidence, scoped commits, and residual
   risk. An independent native review covers the resulting implementation;
   Cross-family review is opt-in, not a side effect of backend selection.
   Repairs require existing write authority and re-review of affected scope.
   At most two scoped repair attempts before reporting a parked branch.
7. At committed seams, use the session-bound context watchdog described in
   `workflow-skills/agentic-exec-loop/references/loop-protocol.md`.
   `UNKNOWN` telemetry is nonblocking; `OVER` requires a forward handoff
   after draining active work. No fixed universal token threshold.
8. Report completed/parked outcomes, actual verification, review, scoped SHAs,
   and remaining gates. Workers commit their own authorized edits and never
   push. Read-only tasks create no commits. Remote operations require the
   user's or project release contract's authority.

For an authorized workflow-state update, use `stage-emit.sh`/`planctl`;
never append raw events or worker output to dashboard logs. The canonical
stage procedure normally owns this update, so do not duplicate it here.

No mandatory Fable consultation or other paid escalation precedes a user
question. Use safe in-scope defaults for routine ambiguity; surface material
scope, authority, or safety decisions to the user.

## Flags

- `--deep --grok --codex --sonnet --opus --glm --agy --fable`: explicit backend
  selection, subject to its authentication, permission gates, and configured
  pauses. Otherwise use the host-native configured route.
- `--flash`/`--vision`: forward only to the selected supporting runner.
  Preserve its mutual-exclusion and model-override rules.
- `--budget auto|low|medium|high`: classify each task; a slice uses the highest
  member's classification, clamped by the campaign ceiling. See
  `references/execute-budget.md`.
- `--effort <level>`: preserve explicit effort, validated by the actual runner.
  Do not infer support or account limits from another host.
- `--repo <name>`: configured repository alias; ambiguous roots require resolution.
- `--readonly`: keep the entire routed task read-only, including state.
- `--max-turns <n>`: forward only when supported; otherwise report the limitation.
- `--autonomous`: does not waive permissions, human gates, or verification.

If no task is supplied, ask what to route. Before dispatch, state intent,
deliverable, chosen route, ownership bounds, and any authorization gate.
