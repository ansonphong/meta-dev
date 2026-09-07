# Adaptive workflow policy

The six stages describe progress, not six mandatory agent swarms. This is the
shared policy for planning, execution ownership, and review depth on every host.
User instructions and the discovered project contract take precedence over skill
guidelines. A stage ceiling or model selection never adds write permission.
Upgrade and compatibility notes: `references/migration-1.5.md`.

## Resolve once, carry forward

Run `python3 ${PLUGIN_ROOT}/scripts/workflow-policy.py --host <host>
--project-root <project-root>` before authoring. Pass the intended executor with
`--model <id>`, an existing/explicit `--target`, and each detected `--risk`.
Use `--available-workers` when the host reports a concurrency limit. Save the
resolved policy with the run's evidence; carry `plan_target` into the plan IR.
Re-resolve at dispatch if the executor, risk, or relevant settings changed.
For planctl state calls normalize multi-phase directories to
`00-master-plan.md`; record review against that same canonical path.

Configuration uses `meta_dev.workflow` through the existing defaults → project
→ local JSON cascade. Exact model profiles and aliases are data, not prose
rules. Unknown executors use standard planning and task-sized ownership.
Sensitive work raises planning depth and verification, regardless of model.
The resolver describes policy; it does not launch tools, grant permissions, or
prove that a selected model is available. Validate availability in the host.

`--granularity auto|task|slice`, `--research auto|focused|full`, and
`--harden auto|focused|full` override the corresponding policy. Cross-family
review is opt-in (`--cross-family` or project configuration with authorization
for the external service). A request for a particular external reviewer also
opts into that reviewer, not an unlimited review pool.

## Coherent execution slices

Keep one runtime acceptance record per task/ledger handle. Worker lifetime is
separate: a capable executor may own a bounded group of tightly related tasks
in one phase, such as propagating a field through its API, type, and UI.
The union of declared paths is the worker's write scope. Dependencies must be
ready outside the slice and ordered within it. Never group independent outcomes
just to fill the slice limit. Do not slice across permission gates, critical
risk boundaries, human gates, phase reviews, or `--review each`.

Give the worker the relevant task sections, shared contract, inspected revision,
declared paths, and per-handle acceptance criteria once. Re-anchor live symbols
before editing; do not reread the full plan or unrelated skills for each handle.
For each accepted handle return its commit SHA, verifier command, exit code,
output evidence, and causal state. A shared commit may cover several handles;
it must identify the exact covered scope. Accept no partial slice wholesale.
The conductor updates each accepted handle through `planctl` promptly; one
ledger commit may persist those already-recorded updates at the slice seam.
Never delay state updates until the end of the whole run.

Workers send per-handle progress if the host supports it. Otherwise the bounded
slice reports at return, and the conductor updates each handle then. A failure
parks only its dependents; independent accepted handles retain their evidence.
Persistent ownership ends at completion, scope change, unsafe drift, or a
context boundary. Resume from committed evidence, not an assumed empty context.

Co-dispatch only disjoint write sets; include fixers and nested workers in the
same host-wide concurrency budget. Default caps are ceilings, not occupancy
targets. Use sequential ownership when delegation is absent or forbidden;
report this host limitation without inventing an external worker. `--inline`
explicitly selects this same sequential path.

## Proportional investigation and hardening

Focused research records intent, alternatives, and unresolved questions in one
pass. Add an independent specialist only for a named question whose answer can
change the design. A new behavior does not automatically require a swarm.

Focused hardening starts with deterministic artifact validation, then one
capable independent reviewer covering request coverage, dependencies, contracts,
failure paths, trust boundaries, and verification soundness. The reviewer must
read relevant live code, not only a lossy summary. Add targeted specialists for
unresolved risk; assign each a distinct question and stop condition. Full mode
expands coverage, not one agent per file by default. Preserve security and
permission checks at every depth. No paid external fan-out without the existing
authorization boundary.

Findings need evidence or a concrete falsifier, severity, affected scope, and
disposition. Hardening passes when no unresolved blocker remains and advisories
are recorded. Exhausting a round budget never turns a blocker into a pass.
After a fix, rerun affected checks/review only; do not replay clean unchanged
axes or promote to another wave merely because the last pass was clean.

Stage 6 is one native review of the resulting scope, reusing the final phase
review when it covers that scope. Cross-phase interactions must be covered;
task reviews alone do not establish whole-change coverage. Independent audit,
evaluation, and housekeeping commands run only when requested or required by
the declared delivery contract, not because a stage has the same name.
If independent review is unavailable, label self-review honestly and leave any
required independent gate open. Do not silently opt into a paid reviewer.

## Host capabilities and context

Model support is not host support. Async tools, mid-turn steering, dynamic
effort, and persisted reasoning may be used only when the current host exposes
them. Keep stable prompt prefixes and reuse bounded verified context where
supported; do not simulate these features with polling or assume API controls
exist in a CLI. Effort is task-specific and must be validated by its runner.

At committed phase/slice seams use `scripts/context-gauge.py` with the current
host/session identity and known context window or explicit threshold. Unsupported
or unavailable telemetry returns `UNKNOWN`, never another session's measurement.
On `OVER`, preserve a compact forward handoff before resuming. A worker with
persistent ownership follows the same rule. Never compact solely on an invented
token count. No cache-warming calls or universal token ceiling.

## Evaluate the change

Use `references/workflow-evaluation.md` before asserting a savings or reliability
improvement. Adaptive defaults are configurable hypotheses, not benchmark
results. Keep full/task policy available for rollback and comparison.
