---
name: meta-execute
description: Subagent-driven plan execution — one fresh Sonnet per task, verify+commit+push between, auto-archive + deploy on completion
argument-hint: <plan-path> [--inline] [--no-deploy] [--pause-before=<task-id>]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /meta-execute

Parse plan, dispatch one Sonnet subagent per task, verify + commit + push between, escalate on drift.

## Flow

1. Resolve plan path + parse task inventory
2. Mirror into TodoWrite tracker
3. Pre-flight gates (clean tree, master, tests baseline)
4. Per task: claim → dispatch subagent → verify → stub grep → risk gates → mark DONE + commit
5. Completion: archive plan, update changelog + STATUS + exec-order, invoke `/deploy` (unless `--no-deploy`)

Config: `plans/_dashboard/settings.json` (model tier, deploy toggle).

See `superpowers:subagent-driven-development` skill for dispatch template.
