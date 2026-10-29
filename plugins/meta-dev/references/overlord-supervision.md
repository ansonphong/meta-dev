# OVERLORD execution supervision

Watch whether execution delivers the user's requested outcome with truthful
evidence and proportionate effort. Preserve the existing plan checks, task
reviews, authorized repairs, dashboard, and inbox. A checkbox or commit is a
claim to inspect, not proof of success. Activity volume is not progress.

## Start and controls

- `/overlord` or `/overlord start`: bind to this session's current execution.
- `/overlord <plan-path|task|scope> --every 15`: bind to an explicit target.
  Resolve its repository roots, task handles/files, executor session/agent, and
  requested outcome. If several executions match, ask which one; do not choose
  the newest unrelated plan. A scope without a plan is valid; do not invent one.
- `--every N` accepts positive minutes, including 10, 15, and 20. Convert to
  seconds once. `--tick N` is the legacy seconds option (30–3600 seconds).
  Reject conflicting interval flags or values outside 30–3600 seconds.
- Explicit interval wins over `meta_dev.overlord.interval_minutes`. When null
  or absent, choose 10 minutes; choose 15 for a known lengthy focused operation,
  or 20 for a documented external wait. Announce the choice and rationale.
  Keep it fixed until the user changes it; do not slow reviews to hide drift.
- `--event-driven` retains the one-shot mode: review matching unconsumed
  `plan_edit` events, then return. With no delta, do not spawn a reviewer.
  If a watch is live, queue the delta for its owner; do not start a second review.
  Otherwise use a one-shot start/tick/done lifecycle without arming a timer.
  Timed mode reviews even when there are no events or commits: silence may be
  the problem. The legacy `trigger` setting controls hook behavior, not the
  default mode of a direct invocation.
- `status`: report the bound target, interval, live scheduler/monitor identity,
  last review, last correction, and next checkpoint. Do not spawn a reviewer.
- `stop` / `--stop`: invalidate the watch, cancel only its timer/monitor and
  reviewer, then record `overlord_done`. Leave the executor running.

Read the merged settings through `bash ${PLUGIN_ROOT}/scripts/config-get.sh
meta_dev.overlord`. Read runtime state through `state-read.sh overlord`.
Resolve applicable AGENTS.md and routed project rules once at start; refresh
only if they change. User instructions override plugin defaults. Supervision
does not authorize source changes, broaden scope, or waive required reviews.

## Project opt-in for campaign execution

`meta_dev.overlord.auto_start_campaign` defaults to false. When true, the execution
owner invokes this procedure once when starting an explicitly authorized campaign
with multiple deliveries (one master plan or a runbook). This procedural entry
point is not a background hook: installing settings alone starts nothing.
Bind only that campaign and its existing owner, at 15 minutes, retaining the
configured bounded review budget. Explicit user timing/stop instructions prevail.
Inspect live state first: reuse a live watch for the same target; if a different
watch is active, report the conflict and leave it untouched. Never restart a
stopped watch automatically on resume; inspect its recorded stop reason.

Use the scheduler/monitor capability checks below. Reserve monitor and reviewer
capacity without displacing existing work. If unavailable, report the exact missing
scheduler, cancellable native monitor/reviewer capacity or executor messaging
capability; retain `/overlord <target> --every 15` as the manual retry command.
Do not invent scheduling APIs, shell daemons or same-harness headless workers.
No activation occurs for planning, ordinary edits or unapproved campaigns.

## A real timer, one owner

For timed mode, name the actual host and available native capabilities. There is one active
watch per project state. Reinvocation for the same target reuses it; changing
the target or interval cancels the old watch before replacing it. Use a unique
`watch_id`; every callback checks that it is still active and matches.

1. Prefer an available host-native scheduler that can resume this supervisor
   in the same execution context. Register the next review, retain its returned
   identity, and rearm only after the previous review finishes. A tool such as
   `ScheduleWakeup` is usable only if actually exposed by this host.
2. Without that scheduler, use one dedicated **native monitor agent** as the
   supervisor conductor. This invocation authorizes that monitor to spawn one
   native reviewer at each deadline. Give it this procedure, the watch ID,
   absolute roots, scope, executor address, interval, settings, baseline evidence,
   and stop conditions. Choose the cheapest available native model capable of
   coordination; the reviewer uses the table below. Reserve capacity for both
   monitor and reviewer within the host-wide worker limit.
3. The monitor uses cancellable native wait/sleep tools until the next deadline,
   respecting host wait limits. No file scans or model reviews between deadlines.
   It remains active while the executor works; the executor must not wait on
   it. At the deadline it checks ownership, performs the cycle below, then waits
   again. This is session-bound: it cannot survive a closed/killed host.
4. If neither route works, or native review capacity is unavailable, report
   `INFRA_RED` and the missing capability. Do not claim that a timer is armed,
   shell out to another CLI, start a daemon, or substitute an inline self-review.
   An elapsed/unresponsive review is cancelled at its budget; confirm it ended
   before another starts. If cancellation cannot be confirmed, stop monitoring
   and report the failure. Never accumulate overlapping reviews or catch-up ticks.

Confirm timed start only after the scheduler/monitor exists. Report its identity,
scope, interval, reviewer model, and first due time. Persist these through an
`overlord_start` event. The monitor waits for its matching start event before
doing work. Recheck live identity after a resume: stale state is not a live
timer. Stop on requested stop, lost ownership/executor, host cancellation,
`max_loops` (default 100), or proven completion with no unresolved findings.
Do not silently restart a stopped watch. On exit, cancel owned resources and
append `overlord_done` with the matching watch ID and reason.

## Native reviewer

| Host | Default reviewer | Selection |
|------|------------------|-----------|
| Codex | Sol, `gpt-6-sol`, high effort | Native agent with a fresh, scoped context |
| Grok Build | `grok-4.7`, high effort | Native `spawn_subagent` |
| Claude Code | Sonnet | Native Agent/Task; Opus for ambiguous architectural judgment or explicit selection |

`meta_dev.overlord.model = native` selects this table. Existing `sonnet`/`opus`
values apply to Claude only; other hosts use their native default. An explicit
native model ID overrides the default on its own host. Check the host's actual
model allowlist; an unavailable selection is `INFRA_RED`, not permission to
switch families. Other hosts use their configured native review route, or
report it unavailable. Name model and effort before spawning. Do not inherit
the executor's model accidentally. Reviewers cannot spawn workers or edit files.

## Each review cycle

Use one reviewer for the active scope, including newly completed tasks. Review
changed evidence once; reuse already accepted focused checks and task reviews.
The review budget is `review_budget_seconds` (default 120), capped below the
interval. Missing evidence is reported as unknown, never as a pass. Supervision
does not replace a required independent task/final acceptance review.

1. Collect the delta since the last checkpoint: relevant working diff and
   commits, changed plan handles, executor/task status, commands and focused
   results already available, blockers, and the previous correction. Read only
   scoped files and rule references needed to assess these claims. Uncommitted
   work and useful investigation count; commit count, lines changed, elapsed
   time, and checkbox count alone cannot establish progress or a stall.
2. Pass the reviewer the requested outcome, authorized scope, applicable rules,
   baseline/delta refs, prior correction, and this review contract:

   **Return at most 250 words:** `assessment` = `on_track`, `drift`, `stalled`,
   `waiting`, `unknown`, or `complete`; concrete progress and evidence refs;
   any violated rule or unsupported completion claim; one smallest corrective
   action with an owner; the evidence expected at the next checkpoint. For
   drift/stall include a stable `issue_key` describing the same unresolved cause.
   Explain legitimate waiting with its dependency and expected wake condition.

   Check truth (does evidence support completion?), direction (does this work
   advance the ask?), and efficiency (is the route proportionate?). Detect
   repeated unchanged tests, test-harness construction without a critical need,
   repeated planning/research without narrowing uncertainty, scope creep,
   unnecessary abstractions/duplication, and ready work left idle. Apply Grug
   and DRY to the requested change; do not demand unrelated refactors, arbitrary
   line limits, extra test suites, or skipped safety/acceptance gates.
3. Deliver the correction to the bound executor using native agent messaging.
   If the executor is the parent session, return/send the checkpoint there for
   its next message boundary. If that route is unavailable, report undelivered
   direction to the user; never claim it was applied. The executor acknowledges
   the action or supplies a concrete rebuttal, then continues authorized work.
   OVERLORD does not become a second code writer. On-track output is one short
   checkpoint, with no new work manufactured.
4. Retain completed-task review and plan/commit reconciliation. Match actual
   files/evidence to task IDs rather than trusting commit messages alone. Route
   small evidenced drift to the conductor for `planctl` acceptance/reopening or
   to the existing owner for authorized repairs. Respect `auto_fix` and
   `auto_fix_threshold` (default 2 findings); above either limit, flag it.
   Thresholds never authorize edits, checkbox acceptance without proof, or a
   repeated verification loop. Preserve causal `TASK_RED` / `BASELINE_RED` /
   `INFRA_RED` handling and continue independent ready work.
5. Persist one `overlord_tick` with watch ID, timestamp, tick number, and `review`
   containing the assessment, progress, evidence, issue key, correction, and next
   checkpoint. Retain the consumed event-log line offset as `review.event_cursor`
   so the next cycle reads only new events. Set `next_due` on each timed tick;
   one-shot ticks use null. The reducer counts consecutive `drift`/`stalled` reviews with
   the same issue key. At `stall_review_limit` (default 2), escalate to the user
   and inbox with both checkpoints and the unfulfilled correction. Alert once
   per unchanged cause; continue watching, without auto-repair retry storms.
   Urgent rule violations are reported immediately. `waiting` and `unknown`
   do not count as stalls; unknown evidence gets a concrete visibility action.
6. Add actionable findings via `inbox-add.sh --source overlord --tag overlord`
   with stable references; reuse an open finding for the same cause. Honor
   `auto_clear_inbox_per_tick` only for this watch's proven-resolved findings.
   Render the existing `overlord-render.py` input shape (plan phases, scoped
   commits/verdicts, findings, next checkpoint), including the persisted `review`.
   This is one checkpoint, not a full housekeeping or review pipeline.

Use `bash ${PLUGIN_ROOT}/scripts/state-append.sh '<json-event>'` for the existing
overlord event family; never write `state.json` directly. `state-read.sh`
materializes it. Plan checkbox and review-verdict writes remain through
`planctl`, owned by the conductor. This procedure does not create a second ledger.
