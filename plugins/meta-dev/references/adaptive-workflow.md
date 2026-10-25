# Adaptive workflow

Stage outcomes and authority are defined once in
`references/workflows/protocol.md`; implementation ownership and bounded repairs
are defined in `references/execute-charter.md`. Follow user/project constraints.
This file covers only depth, coherent slices and actual host capacity.

## Resolve existing policy

When selecting authoring depth or dispatching work, use
`scripts/workflow-policy.py --host <host> --project-root <root>` with the intended
`--model`, explicit `--target`, relevant `--risk` and observed `--available-workers`.
Carry the result forward; resolve again only when relevant inputs change.
Existing defaults → project → local settings remain authoritative. Unknown
models use standard/task policy. Risk raises contract/verification precision;
it never grants authority or proves a model is available.

Existing `--research`, `--harden` and `--granularity` overrides remain available.
Focused depth uses the current owner to resolve bounded questions; specialist
workers need a specific unanswered question whose answer can change the result.
Full depth broadens relevant coverage, not a fixed swarm. Small work may share
intent/design/plan/hardening notes in one record. No automatic skill chain.

## Ownership and capacity

A capable owner may implement a coherent slice of coupled tasks. Keep one
acceptance record per handle, exact union of write paths, ready external
dependencies and ordered internal dependencies. Do not group independent work
just to fill a slice or split a coupled lifecycle to create workers.

Do not cross permission, critical-risk, human or required phase-review gates.
`--review each` requires task-sized sequential acceptance. Unknown/overlapping
write sets serialize. Count all implementation owners, fixers and nested workers
against actual host-wide capacity; caps are ceilings, not occupancy goals.
Keep dependency-ready disjoint work moving. `--inline` or missing/prohibited
delegation uses direct sequential ownership with the same acceptance rules.

Give each owner relevant scope, interfaces, acceptance, inspected revision,
authority and budget once. Native host tools choose the method. Reuse sessions
when supported; do not invent resume support, reread full plans per handle or
repeat valid discovery at every stage. Ordinary repairs retain the owner.

The conductor checks actual diff/evidence, records completed handles promptly
through planctl and batches ledger commits at coherent seams. Never accept a
partial slice wholesale. Context compaction preserves ownership and evidence;
use available host session management rather than mandatory telemetry calls.
For explicit watchdog/loop tooling use the existing loop protocol; UNKNOWN
telemetry never proves a runner is stuck or requires a restart.

## Review and evidence

Harden against relevant live code and explicit contracts. Add an independent
plan specialist only for unresolved risk or a required/user-selected gate.
Keep security, permission and contract checks. Final independent review follows
the shared protocol: one covering native review, extra families only by opt-in.
Batch repairs, rerun affected checks and retain unaffected evidence. Exhausted
budgets do not pass blockers; no repeated review merely because a pass is clean.

Async tools, effort controls and context telemetry must exist in the actual
host. Preserve configured model/effort/budget validation. No cache warming,
invented token limits, paid fan-out or model roulette. Use
`references/workflow-evaluation.md` before asserting measured improvements.
