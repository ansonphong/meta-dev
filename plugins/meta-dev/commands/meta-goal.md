---
name: meta-goal
description: Consolidate everything this conversation put in swing into one itemized ≤1000-char GOAL string to paste into /goal, so the thread drives itself to completion instead of needing a prompt per step.
argument-hint: "[--limit N]"
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
5. Compress to the budget by cutting whole items from the bottom — never by making items vaguer.
6. Emit one fenced, paste-ready block ending in the fixed `EACH` / `STOP` / `END` directives, then the char count and anything cut.

## Flags

- `--limit N` — character budget (default `1000`).

## Rules

Emit only — never type `/goal` yourself. Never pad from project state. Never invent items. Always report what was cut for budget.

Detail: skill `meta-goal` in `plugins/meta-dev/workflow-skills/meta-goal/`.
