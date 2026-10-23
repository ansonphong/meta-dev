---
name: meta-overlord
description: Supervise truthful, efficient execution with periodic native reviews, plan checks, corrective direction, and a progress dashboard
argument-hint: "[start|stop|status] [target] [--every <minutes>|--tick <seconds>|--event-driven]"
allowed-tools: [Read, Bash(bash:*), Bash(python3:*), Agent]
---

# /meta-overlord

Read `../references/overlord-supervision.md` completely and follow it with
`$ARGUMENTS`. `/overlord` is the same command.

With no arguments, supervise the current execution every 10 minutes. An explicit
plan, task, or scope overrides the current execution. `--every 15` and
`--every 20` select minutes; `--tick 900` remains the seconds alias.

Preserve plan/commit reconciliation, completed-task review, bounded authorized
auto-repair, the dashboard, and the issue inbox. The primary question is whether
the actual work is truthfully and efficiently delivering the user's request.
