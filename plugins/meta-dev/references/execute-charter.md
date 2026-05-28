# Execute Charter — Anti-Paranoia, Failure Posture, Protocols

## Anti-Paranoia Charter

`/meta-execute` is a **commit to ship the plan**, not a request for a planning session. The user typed the command to walk away and come back to a finished plan.

- **Do not ask "should I commit dirty files first?"** If dirty files overlap the plan's file inventory, commit them and keep moving. If they don't overlap, just start.
- **Do not ask "proceed?" / "ready?" / "shall I dispatch?"** after a clean pre-flight. The invocation IS the GO.
- **Do not enumerate options** when one path is obviously correct. Pick it and act.
- **Do not pause between tasks for confirmation** unless a hard pause-gate trips.
- **Stay in lane.** Out-of-scope dirty files are not your problem — leave them exactly as they are.

## CLAIMED Protocol

Before dispatching a subagent for a task:
1. Edit the plan file: insert `` `CLAIMED` `` tag next to the task checkbox.
2. Commit + push the claim immediately: `chore(plan): claim <Task ID>`
3. This prevents parallel sessions from picking up the same task.

Stale CLAIMED check: if a task has been CLAIMED for >2 hours with no DONE, prompt the user before re-claiming.

## Resume Logic

If invoked on a plan with mixed DONE/OPEN tasks, resume from the first OPEN task:
- Skip DONE tasks
- Skip CLAIMED tasks (assume another session owns them, unless stale >2h)
- Pick up first OPEN task
- State tracked in plan checkbox state (committed) — no sidecar file needed

## Dry-Run Mode (`--dry-run`)

Parse the plan, run risk-tagging, print the full task inventory with risk labels, verify all file paths exist. Do not dispatch any subagents. Exit with a report.

## Failure Posture Matrix

| Situation | Action |
|-----------|--------|
| Red verify (1st time) | Re-dispatch same task with failure output appended |
| Red verify (2nd time) | STOP. Surface failure + diff. User decides: skip, re-plan, abort |
| Stub grep hit | STOP. Same protocol as red verify |
| Plan <-> code contradiction | STOP. Surface. Never improvise |
| Schema drift unexpected | STOP. Show `alembic check` output |
| Test baseline regresses outside touched files | STOP — task may have side-effected |
| Parallel session pushed to origin/master | If `--stop-on-drift`, halt. Else rebase, re-baseline, continue |

## Pause Gates

Default = no pause between green tasks. Only pause when:
- `--pause-before=<task-id>` matched
- Risk tag is `money-path` or `release-stability` (auto-pause unless `--no-pause`)
- Same task failed twice
- Plan contradiction surfaced
- `git fetch` shows new origin/master commits AND `--stop-on-drift` set
