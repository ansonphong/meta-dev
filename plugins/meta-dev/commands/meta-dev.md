---
name: meta-dev
description: Adaptive six-stage development lifecycle with capability-aware planning, bounded ownership, and evidence-backed review
argument-hint: <subject|plan-path> [--from <stage>] [--to <stage>] [--gate all|exec|none] [--research auto|focused|full] [--harden auto|focused|full] [--granularity auto|task|slice] [--codex] [--autonomous]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
model: opus
---

# /meta-dev

Read `references/workflows/protocol.md`, `references/adaptive-workflow.md`,
and `references/dev-modes.md`. Resolve the intended executor and risks with
`scripts/workflow-policy.py` before selecting authoring depth. Stage names
describe progress; they do not automatically invoke every associated skill.

## Stage pipeline

Follow `references/dev-swarms.md`:

1. Brainstorm: bounded intent, alternatives, and open questions. Research
   specialists are conditional, not a fixed swarm.
2. Design: sufficient decisions and contracts; design-eval only when applicable.
3. Plan: `/meta-planner` with resolved target and deterministic IR rendering.
4. Harden: `/meta-loop-gap` with resolved depth; no unresolved blockers.
   Optional Stage 4.5 extra-family review is off by default; `--codex` selects
   Codex explicitly. Reviewer findings return to the native owner.
5. Execute: `/meta-execute`, passing resolved granularity and intended model.
   Keep per-handle visibility even when a capable worker owns a coherent slice.
6. Review: one native review covering the run and integration seams. Do not
   infer `meta-eval`, `meta-audit`, or standalone `housekeeping`.

Reuse existing valid artifacts/evidence. Small changes can satisfy early stages
compactly without separate agents or commits. High-risk changes retain explicit
contracts, security checks, and permissions at every depth.

## Progress and permissions

Use `workflow-skills/waterfall-tracking/SKILL.md` for visible progress when the
host exposes a tracker; otherwise report stage transitions concisely.
Emit durable state through:
`bash ${PLUGIN_ROOT}/scripts/stage-emit.sh "<plan-path>" <stage>
<in_progress|completed|blocked>`.
Planctl is the only state write door. Dashboard failures do not fabricate stage
completion or block otherwise valid implementation.

The default ceiling is Stage 4. A direct implementation go, `--to 5|6`, or
explicit scoped autonomous/cruise execution request supplies Stage-5 permission.
An incidental keyword or Accept Edits setting does not. Stages 1–4 do not write
source. Unattended mode never adds deployment, spending, or destructive authority.

## Delivery

Advance only when required evidence exists. Park blockers honestly and continue
independent work. Coalesce related artifact commits at safe seams; no minimum
commit count. Use `references/dev-housekeeping.md` for completion bookkeeping.
Push only under the user/project release contract; do not infer deployment.
Read settings through the JSON cascade, project rules through root `AGENTS.md`
and routed neutral context, never personal vendor paths.
