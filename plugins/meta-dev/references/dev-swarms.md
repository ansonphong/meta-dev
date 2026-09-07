# Development stages — adaptive depth

Read `references/adaptive-workflow.md` and resolve the workflow policy first.
Model routes come from the settings cascade; no stage prescribes a vendor pool.

## Stage 1: Brainstorm

Focused mode: one bounded investigation covering intent, alternatives, unknowns,
and trust boundaries. Add specialists only for questions that can change the
direction. Full mode: independent perspectives selected for the problem, within
the resolved reviewer/concurrency cap, then one synthesis. Exit: direction and
scope selected. No fixed four-to-six-agent minimum.

## Stage 2: Design

Record architecture, interfaces, failure handling, and meaningful tradeoffs.
For a small well-understood change this may share the plan's decision section.
Invoke design-eval only for applicable design risk or an explicit request.
Exit: requirements and contracts are explicit; unresolved decisions are owned.

## Stage 3: Plan

Use `/meta-planner` and the deterministic IR renderer. Resolve the intended
executor before choosing authoring depth; apply risk overrides afterward.
Exit: valid single-file or multi-phase artifact and focused acceptance evidence.

## Stage 4: Harden

Use `/meta-loop-gap` with the resolved hardening depth. Deterministic validation
then one independent review is the focused path; unresolved risks justify
specialists. Exit: no unresolved blocker, with advisory dispositions recorded.
An exhausted budget is not a passing verdict.

## Stage 4.5: Optional extra-family review

Off by default, consistently across hosts. `--codex` explicitly selects a
read-only Codex second opinion; `--cross-family` uses the configured permitted
reviewer. Announce the external worker count before dispatch and preserve the
shared protocol's confirmation gate. One pass, with at most one confirming
pass after material changes within the configured round cap. Use artifact names
from `references/plan-artifacts.md`. The native owner triages findings; no
automatic vendor-specific integrate-back hop. Plan edits use the renderer,
state uses planctl, and source implementation remains gated at Stage 5.

## Stage 5: Execute

Use `/meta-execute`. Coherent slices may share a worker while retaining
individual handle evidence and state. Exit: each requested outcome is accepted
or explicitly parked; no in-flight verifier is abandoned. Unrelated dirty files
are preserved, not a reason to claim whole-tree cleanliness.

## Stage 6: Review

One native structured review covering the run and its integration seams.
Reuse a final phase review if its scope suffices. Do not implicitly invoke
meta-eval, meta-audit, or standalone housekeeping. Sync only relevant durable
context and planctl state. Archive only when completion/manual gates permit;
push only under the user's/project's release authorization.
