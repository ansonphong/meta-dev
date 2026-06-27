# Sweep Rules

Autonomous maintenance actions. Never destructive.

## Archive Finished Plans

- **Trigger: the plan is FINISHED — and nothing else.** Decided solely by `scripts/archive-guard.sh` (YAML `status: Done`, zero unchecked `[ ]`, no CLAIMED/WIP/in-progress marker, not listed active in `plans/meta-runbook.md` `## Sequence`).
- **Age is NEVER a trigger.** An old plan that is unfinished STAYS. We do not archive plans for being old, only for being done.
- Action: move to `plans/<repo>/_archive/` (the plan's real archive, not a stale bucket).
- Never: delete, rm, git rm. Never archive a guard-BLOCKed plan.

## WIP Commit

- Trigger: untracked files in `plans/`
- Action: `git add` + `git commit -m "wip: auto-sweep <date>"`
- Never: add files outside plans/, add .env or credentials

## Config

Controlled by `meta_dev.components.auto_sweep` (default: false).
