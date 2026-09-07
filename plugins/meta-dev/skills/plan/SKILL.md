---
name: plan
description: Write and save a self-contained implementation plan for a fresh agent. Use for plan requests, medium changes, or implementation planning before code.
---

# Plan

Use this host-neutral workflow, not a slash-command interface.

1. Read `../../references/codex-writing-plans.md` completely.
2. Read `../../workflow-skills/dod-contract/SKILL.md`.
3. Read `../../references/adaptive-workflow.md` and resolve the intended executor
   with `../../scripts/workflow-policy.py` before selecting the plan target.
   For medium work, create a version `1.1`, `single-file` IR from
   `../../schemas/plan-artifact.schema.json` and target the required dated path.
4. For genuinely large or multi-phase work, follow
   `../../references/workflows/command-adapter.md`,
   `../../commands/meta-planner.md`, and its version `1.0` shared contract.
5. Resolve the plugin root from this file and the project root with
   `<plugin-root>/scripts/lib/repo-topology.py --root`.
6. Validate and render with `../../scripts/plan-artifact-render.py`, replacing
   the relative path with its resolved absolute plugin path. Use `--validate`
   first, then `--project-root <project-root>`.

Do not write plan Markdown directly. A planning-only request stops after saving
and reporting the plan. When the user already explicitly requested scoped
implementation, continue through the execute workflow without asking for the
same go twice.
