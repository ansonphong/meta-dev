# Migrating to meta-dev 1.5

The six stages remain. Default research/hardening is now proportional to risk;
capable configured executors may retain a bounded coherent slice. This release
does not claim a measured token or quality improvement from live model trials.

## Configuration

The existing JSON cascade remains defaults → `plans/_dashboard/settings.json`
→ `settings.local.json`. Project/local overrides are not rewritten. Check old
overrides before expecting new defaults: existing explicit pools, paused routes,
stage models, and resource settings still apply.

`meta_dev.workflow` holds exact model profiles/aliases, host executor choices,
research/hardening depth, task/slice granularity, reviewer/worker caps, and
optional host capabilities. Shipped profiles cover Sol/Astra, Opus 4.8/5, and
Grok 4.6. Unknown models fall back to standard/task. Generic aliases such as
`opus` need an exact host-resolved/configured ID for frontier classification.
No API capability is enabled merely because a model supports it.

Example project override:

```json
{
  "meta_dev": {
    "workflow": {
      "host_execute_models": {"codex": "gpt-6-astra"},
      "execution_granularity": "auto",
      "hardening_depth": "auto",
      "max_tasks_per_slice": 3,
      "max_parallel_workers": 4,
      "cross_family_review": false
    }
  }
}
```

External pools now default empty, with no personally paused backend. Global
stage model overrides no longer force an Anthropic route on every host; Codex's
existing native route defaults remain. Canary endpoints and design preferences
must be configured by the project rather than contacting example services or
imposing a shipped visual style. Publisher attribution is unchanged.

To use conservative task ownership/full review, set `execution_granularity` to
`task` and `hardening_depth` to `full`. Security, permissions, ownership, focused
verification, and planctl state gates remain in every mode.

## Plans and evidence

Planner validation now reads master-linked phase files regardless of filename,
and validates single-file artifacts. One task has one handle and one ledger
row; independently accepted steps must be real IR tasks, not extra checkboxes.
Lean plans still declare focused verification. The legacy IR `signatures` key
now renders as Codebase Anchors; supply symbols/invariants, not frozen dumps.

New v1.1 single-file output has a canonical checkbox ledger. For older
checkbox-free output, re-render from retained IR before execution, preserving
the artifact path and checking the diff. Do not force-overwrite a plan with
accepted work: reconstruct its accepted state from evidence through planctl.
Input IR versions 1.0 and 1.1 remain supported.

`planctl review ... pass` now requires `--repo-root`, `--base-ref`, `--target-ref`,
and repeated exact `--scope` files (repo-root may default to the project root).
See `commands/meta-execute.md`. Re-review old unbound PASS records; they no
longer auto-complete a plan. The new gate tolerates ledger-only changes but
invalidates changes to reviewed content or plan contracts.
Each bound PASS covers one Git source repository. For multi-repository campaigns,
use repository-owned member plans with their own covering reviews. A single
plan spanning independent Git repositories needs separate review disposition;
do not automatically complete it from one repository's evidence.

Codex worker handoffs add required `task_results`: an empty array for aggregate
single-task compatibility, or one structured result per assigned slice handle.
Existing OUTPUT_FILE wrapping is unchanged. Custom producers must add this
field. The conductor compares assigned and returned handles and accepts each
only with its own evidence; aggregate transport success is not slice success.

Claude headless read-only workers expose read/search tools only, not unrestricted
Bash. Supply a precomputed diff artifact when a review needs Git history, or use
an authorized native reviewer with a verified read-only tool surface. A tool
selection flag must not turn `--readonly` back into a writing worker.

## Context and evaluation

`context-gauge.py` requires exact host/session identity and a known context
window or explicit threshold. Configure `meta_dev.context`, use explicit CLI
flags, or supply host/session-bound generic telemetry. Unsupported or missing
telemetry returns UNKNOWN, never another session's usage. The fixed threshold
and newest-Claude-session fallback are removed.

Use `references/workflow-evaluation.md` and the measurement schema for authorized
comparisons. No paid benchmark, deployment, or external consultant runs merely
because adaptive policy is enabled.
