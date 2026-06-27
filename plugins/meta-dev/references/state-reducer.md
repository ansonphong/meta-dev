# State Reducer

Event sourcing pattern. `state.events.jsonl` = append-only log. `state.json` = materialized view.

## Event Types (folded into state.json)

| Event | Fields | Effect |
|-------|--------|--------|
| `commit` | sha, message, time | Prepend to recent_commits (cap 50) |
| `overlord_start` | watching, mode, model, auto_fix | Set overlord.active=true |
| `overlord_tick` | tick_n, verdicts, findings | Increment tick_n, update last_review |
| `overlord_done` | reason | Set overlord.active=false |
| `session_start` | session_id, plan | Append to active_sessions |
| `session_end` | session_id | Remove from active_sessions |
| `meta_execute_start` | plan | Append to meta_execute_runs |
| `meta_execute_end` | plan, status | Update run status |
| `sweep_action` | action | Append to sweep_log (cap 100) |

## History-only events (NOT folded)

`stage_transition` rows are appended to `state.events.jsonl` by `stage-emit.sh` as a **timeline/history** record only — the reducer does NOT fold them into `state.json`. Plan stage/status is the plan's YAML frontmatter, read live by the dashboard via `plan-index.py`; it is never derived from the event log. (The old `plan_edit` no-op event and the `plan_stages` fold have been removed for this reason.)

## Idempotency

Reducer folds from events.jsonl each time. Replaying same events → same state. Safe to run repeatedly.
