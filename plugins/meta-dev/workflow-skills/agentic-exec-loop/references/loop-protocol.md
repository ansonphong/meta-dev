# Loop protocol — execute, review, fix

The scheduling and acceptance contract is `commands/meta-execute.md`;
`references/adaptive-workflow.md` defines coherent slices and resource limits.
Read those rather than duplicating the worker loop here.

## Review seams and provenance

Record the starting revision, declared scope, and per-handle committed outcomes.
The reviewer computes its diff from explicit base/target refs and inspects live
contracts where needed. A phase verdict applies only to that phase. Persist the
final planctl PASS only when the closing review covers the whole completed run
and its integration seams. Changed reviewed code requires affected re-review.
Manual gates or unresolved blockers cannot be converted into PASS.
Record PASS with the exact source repository, base/target refs, and repeated
`--scope` file arguments documented in `commands/meta-execute.md`. Planctl
rejects unbound PASS; legacy events need a fresh review. Content/contract drift
invalidates evidence without penalizing checkbox-only commits.

Runbook members reconcile through planctl at seams; render only a dirty owning
runbook and commit only an actual scoped diff. Do not rewrite every campaign or
directly stamp YAML state. No independent audit/eval/housekeeping fan-out.

## Context watchdog

At committed task/slice or review seams, measure the current session only:

```bash
python3 ${PLUGIN_ROOT}/scripts/context-gauge.py --host <host> --session-id <id> --project-root <root> --json
```

Pass `--transcript <path>` for an exact supported Claude/Codex transcript, or
`--telemetry <path>` for a host-neutral JSON object containing `host`,
`session_id`, `context_tokens`, and optionally `context_window`.
Use `--context-window N`, `--threshold N`, or `--threshold-ratio 0.8` when
the host/configuration supplies trustworthy limits. Settings use
`meta_dev.context`; `META_DEV_CONTEXT_*` environment equivalents are supported.
Never select the most recently modified transcript.

`OK` or `UNKNOWN` (exit 0): continue. `OVER` (exit 10): finish the current
safe commit/evidence boundary, then use meta-compact to write a forward handoff
naming the next handle, outstanding jobs, and review scope. Use the host's
available compaction procedure; do not invent a universal /compact command.
Persistent workers use the same boundary discipline. No artificial keepalive
calls, repeated plan reads, or periodic sleeps to preserve a speculative cache.

## Infrastructure and repair

Preserve structured worker output and local commits. Runner stalls are
`INFRA_RED`, not code regressions. Retry infrastructure at most once at the
conductor layer, respecting the runner's own retry budget. Park unsupported
branches without abandoning running work or claiming acceptance.

Repair only causal scope, with at most two attempts before disposition. Route
through configured permitted backends; do not automatically escalate to a paid
consultant. Reuse unchanged green evidence; rerun only checks invalidated by the
repair. Budget exhaustion leaves an honest unresolved result.
