---
name: runbook
description: Coordinate related plans through the six-stage waterfall with dependency-aware ownership and one shared capacity limit.
argument-hint: "[new <dir|plans…> | refresh | execute [--serial] | chain <label> | add <plan> | done <plan> | archive] [prompt]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
---

# /runbook

Read `workflow-skills/runbook-orchestration/SKILL.md` for the canonical
campaign procedure and `references/adaptive-workflow.md` for ownership and
resource policy. This command is an adapter, not a second execution loop.
Single plan → `commands/meta-dev.md`; approved implementation →
`commands/meta-execute.md`.

| Verb | Purpose |
| --- | --- |
| `new <dir|paths…>` | Resolve, topo-sort, scaffold, and register members |
| `refresh` / bare | Recompute campaign status |
| `execute` / `go` | Execute READY members within scoped campaign authority |
| `chain <label>` | Create a successor without declaring unfinished work done |
| `add <plan>` | Insert at a dependency-correct position |
| `done <plan>` | Record completion only with required acceptance/review evidence |
| `archive` | Archive only when all required gates pass |

The campaign conductor coordinates dependency order and cross-plan gates.
Each member conductor follows the canonical single-plan procedure; it does not
receive a new independent worker budget. Count member conductors, nested
task/slice workers, reviewers, and fixers against one host-wide cap, clamped to
observed capacity. `--serial` permits one member at a time. Unknown write sets
serialize; file-disjoint READY members may run concurrently.

Use the actual native host surface (`spawn_subagent`, `Agent`, or Codex native
delegation) when available and permitted. Otherwise use sequential scoped
ownership with the same evidence and safety rules. Do not silently launch
another backend or invent a missing worker primitive. Grok/Codex headless
workers receive direct briefs: do not send a slash command intended for Claude.

Use `TaskCreate`/`TaskUpdate` when available, otherwise a concise status list.
Leave unrelated dirty files alone. Scoped writes use `commit --only`; workers
never push. Runbook state and computed progress go through `planctl`;
`runbook-render.py` is its rendering shim, not an alternate state writer.

At committed member/review seams use the session-bound context watchdog.
`CONTEXT_VERDICT=OVER` requires a drained forward handoff; unavailable telemetry
is nonblocking. Do not use a universal token threshold.

A member `TASK_RED` parks that branch and its dependents; independent work may
continue. Closing reviews must cover member changes and declared cross-plan
interfaces. Cross-family review is opt-in. No unconditional consultant call.

Presentation: `references/runbook-view.md`. Worker briefs:
`references/execute-briefs.md`. Report accepted/parked members, actual
verification/review, scoped SHAs, and remaining manual gates.
