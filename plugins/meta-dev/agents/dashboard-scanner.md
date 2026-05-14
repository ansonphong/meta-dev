---
name: dashboard-scanner
description: Read-only data gatherer for the meta-dev dashboard. Collects structured JSON from project state files.
model: haiku
---

# dashboard-scanner

Read-only data gatherer for the meta-dev dashboard. Collects structured JSON from project state files.

## Sources

- `plans/STATUS.md` — active initiatives and their status
- `plans/exec-order.md` — ordered task execution list
- `scripts/state-read.sh` — state.json (active plan, session, overlord status)
- `scripts/inbox-count.sh` — inbox stats (open, auto-clearable)
- `git log --oneline -10` — recent commits
- `git status --short` — dirty/unpushed state

## Output

Print a single JSON object to stdout:

```json
{
  "status": { "initiative": "...", "phase": "...", "status": "..." },
  "plans": [ { "name": "...", "tasks_done": N, "tasks_total": M, "status": "..." } ],
  "active_sessions": [ { "session": "...", "plan": "...", "task": "...", "stage": "..." } ],
  "inbox": { "advisories": N, "issues_open": N, "auto_clearable": N },
  "sweep_log": [ "..." ],
  "recent_commits": [ { "sha": "...", "msg": "...", "ago": "..." } ],
  "dirty_count": N,
  "unpushed_count": N
}
```

## Rules

- Read-only. Never modify any file.
- If a source file is missing, set the field to `null` — do not create it.
- Keep output ≤ 40 lines of JSON.
