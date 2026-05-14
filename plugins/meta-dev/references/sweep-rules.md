# Sweep Rules

Autonomous maintenance actions. Never destructive.

## Archive Stale Plans

- Trigger: plan file mtime > 30 days, no git commits touching it
- Action: move to `plans/_archive/stale/YYYY-MM/`
- Never: delete, rm, git rm

## WIP Commit

- Trigger: untracked files in `plans/`
- Action: `git add` + `git commit -m "wip: auto-sweep <date>"`
- Never: add files outside plans/, add .env or credentials

## Config

Controlled by `meta_dev.components.auto_sweep` (default: false).
