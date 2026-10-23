# State Reducer

Event sourcing pattern. `state.events.jsonl` = append-only log. `state.json` = materialized view.

## Event Types (folded into state.json)

| Event | Fields | Effect |
|-------|--------|--------|
| `commit` | sha, message, time | Prepend to recent_commits (cap 50) |
| `overlord_start` | watching, mode, model, auto_fix, watch_id, interval_seconds, scheduler_id, monitor_id, executor, next_due | Start one watch; reset review and stalled_ticks |
| `overlord_tick` | watch_id, time, tick_n, next_due, review | For the active matching watch, retain review and count consecutive drift/stalled reviews for the same issue_key |
| `overlord_done` | watch_id, reason | Stop the matching watch and clear next_due |
| `session_start` | session_id, plan | Append to active_sessions |
| `session_end` | session_id | Remove from active_sessions |
| `meta_execute_start` | plan | Append to meta_execute_runs |
| `meta_execute_end` | plan, status | Update run status |
| `sweep_action` | action | Append to sweep_log (cap 100) |

## History-only events (NOT folded)

`stage_transition` rows are appended to `state.events.jsonl` by `stage-emit.sh` as a **timeline/history** record only — the reducer does NOT fold them into `state.json`. Plan stage/status is the plan's YAML frontmatter, read live by the dashboard via `plan-index.py`; it is never derived from the event log. (The old `plan_edit` no-op event and the `plan_stages` fold have been removed for this reason.)

`task_done` / `task_undone` rows were appended by `task-done.sh` / `task-undone.sh` after a checkbox flip landed. **Post-M3a (planctl unified state layer):** these events stop landing in the legacy `state.events.jsonl` — planctl writes `check`/`uncheck` events to its own off-9p `events.jsonl` instead. This is SAFE: `state-reduce.py` does NOT fold `task_done`/`task_undone` rows (they were history-only), and `on-run-complete.sh` reads checkboxes + `review_verdict` only. Same history-only class as `stage_transition` — never folded into `state.json`. Live checkbox state is read from the plan file.

| Event | Fields | Effect |
|-------|--------|--------|
| `task_done` | plan, handle, by?, time | History only — checkbox already flipped in the plan file |
| `task_undone` | plan, handle, by?, time | History only — checkbox already reopened in the plan file |

## Idempotency

Reducer folds from events.jsonl each time. Replaying same events → same state. Safe to run repeatedly.
