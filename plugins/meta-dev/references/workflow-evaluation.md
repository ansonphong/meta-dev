# Adaptive workflow evaluation

Do not infer measured savings from smaller prompts or fewer prescribed agents.
No paid comparison runs automatically during implementation or review.

For an authorized comparison, select representative fixed-revision tasks:
one ordinary coherent change, one cross-layer change, and one sensitive contract.
Run task/full and adaptive policies in isolated workspaces with the same
acceptance criteria, dependencies, tool permissions, and model/effort. Alternate
run order; repeat enough to expose variance. Never share implementation output
between candidates or mutate production systems as a benchmark.

Record one JSON result per run using `schemas/workflow-measurement.schema.json`:
policy, model, host, revision, task ID, accepted outcomes, elapsed seconds,
input/output tokens when exposed, actual billed cost when known, rework count,
missed defects from a blind independent acceptance review, and unnecessary user
interruptions. Unknown usage/cost is null, not zero. Keep infrastructure errors
separate from task failures and record the final outcome even on exhaustion.
Report cost per accepted outcome only with nonzero accepted outcomes and known
cost. Compare reliability first, then median/range of latency and cost.

Adopt a local override only when accepted quality is maintained. Revert to
`execution_granularity: task` and `hardening_depth: full` in
`meta_dev.workflow` if slices increase missed defects, unsafe ownership, or
rework. A shorter run with fewer accepted outcomes is not an improvement.
