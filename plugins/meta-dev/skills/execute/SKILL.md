---
name: execute
description: Execute an approved plan task-by-task with focused verification and durable per-task commits. Requires an explicit go.
---

# Execute

Use this host-neutral workflow, not a slash-command interface.

**Gate first: a plan is not permission.** Execute only on an explicit go from
the user for this plan. Absent one, report what would run and stop.

1. Read `../../references/workflows/protocol.md` completely.
2. Read `../../workflow-skills/agentic-exec-loop/SKILL.md` for the
   execute→review→fix loop and the phase-seam context watchdog.
3. Read `../../references/execute-dispatch.md` for the worker brief, and obey
   its durability law: every worker commits its own edits with explicit paths,
   including on red. Never write a git constraint into a brief — fix the
   executor or route the task elsewhere.
4. Resolve the plugin root from this file and the project root with
   `<plugin-root>/scripts/lib/repo-topology.py --root`.
5. Build one runtime task per plan checkbox, in dependency order. Dispatch one
   fresh scoped worker per task and **inline that task's own plan section
   verbatim** into the brief — never tell a worker to reconstruct the task by
   reading the plan file.
6. Verify each task with a focused check scoped to its declared files. A
   task-caused failure is `TASK_RED`: repair it and defer only its direct
   dependents. Pre-existing or out-of-scope failures are `BASELINE_RED` and
   defer nothing. Never run a repo-wide suite, build, or typecheck as a task
   gate.
7. Flip the plan checkbox only through the write door, immediately after that
   task's commit and before starting the next:
   `bash <plugin-root>/scripts/planctl.sh check <plan> <handle>`.
   Never hand-edit a checkbox. Never batch flips.
8. Close each phase with one native review per
   `../../workflow-skills/code-review-protocol/SKILL.md`.

Keep the conductor thin: worker output, diffs, and review prose stay inside
dispatched agents. Report what changed, what was verified, and residual risk.
