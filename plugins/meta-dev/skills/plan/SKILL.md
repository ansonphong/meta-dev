---
name: plan
description: Write and save a self-contained implementation plan for a fresh agent. Use for plan requests, medium changes, or implementation planning before code.
---

# Plan

Use this host-neutral workflow, not a slash-command interface.

1. Read `../../references/codex-writing-plans.md` completely.
2. Read `../../workflow-skills/dod-contract/SKILL.md`.
3. For medium work, create a version `1.1`, `single-file` IR from
   `../../schemas/plan-artifact.schema.json` and target the required dated path.
4. For genuinely large or multi-phase work, follow
   `../../commands/meta-planner.md` and its version `1.0` shared contract.
5. Resolve the plugin root from this file and the project root with
   `<plugin-root>/scripts/lib/repo-topology.py --root`.
6. Validate and render with `../../scripts/plan-artifact-render.py`, replacing
   the relative path with its resolved absolute plugin path. Use `--validate`
   first, then `--project-root <project-root>`.

Do not write plan Markdown directly. Do not implement the plan. Finish by
reporting the saved path and waiting for an explicit go.
