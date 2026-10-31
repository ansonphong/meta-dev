---
name: meta-goal
description: Consolidate everything this conversation put in swing into one itemized GOAL string to paste into /goal, so the thread drives itself to completion instead of needing a prompt per step. There is no character budget.
argument-hint: ""
allowed-tools: [Read, Grep, Glob, Bash(bash:*), Bash(git:*)]
model: opus
---

# /meta-goal

Invoke the `meta-goal` skill. Scope is **this conversation only** — not the plan tree, not the inbox, not project-wide git.

## Behavior

1. Harvest every distinct thing this thread put in swing: asked-not-delivered, started-not-finished, found-not-fixed, decided-not-written, open runtime tasks, plan checkboxes this thread promised.
2. Sharpen each to an observable end state; drop anything that won't state as one.
3. Order by dependency — blockers first.
4. Attach a **transcript-visible proof** to each item (commit sha, real stdout, `planctl check` line). The `/goal` evaluator sees only the transcript; an item whose completion never prints can never be judged done.
5. Write every sharpened item in full. There is no character budget. Do not shorten or drop an item to fit a length.
6. Emit one fenced, paste-ready block ending in the fixed `EACH` / `STOP` / `END` directives.

## Rules

Emit only — never type `/goal` yourself. Never pad from project state. Never invent items. Never impose a character budget.

Detail: skill `meta-goal` in `plugins/meta-dev/workflow-skills/meta-goal/`.
