# State Reducer

Event sourcing pattern. `state.events.jsonl` = append-only log. `state.json` = materialized view.

## Event Types

| Event | Fields | Effect |
|-------|--------|--------|
| `commit` | sha, message, time | Prepend to recent_commits (cap 50) |
| `plan_edit` | file, time | Update last_plan_edit per file |
| `overlord_start` | watching, mode, model, auto_fix | Set overlord.active=true |
| `overlord_tick` | tick_n, verdicts, findings | Increment tick_n, update last_review |
| `overlord_done` | reason | Set overlord.active=false |
| `session_start` | session_id, plan | Append to active_sessions |
| `session_end` | session_id | Remove from active_sessions |
| `meta_execute_start` | plan | Append to meta_execute_runs |
| `meta_execute_end` | plan, status | Update run status |
| `sweep_action` | action | Append to sweep_log (cap 100) |

## Idempotency

Reducer folds from events.jsonl each time. Replaying same events → same state. Safe to run repeatedly.
