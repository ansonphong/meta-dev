---
name: plan
description: Create a dependency-aware implementation plan with shared meta-dev contracts and validation.
---

# Plan

Use the planning procedure as host-neutral guidance, not a slash-command interface.
Read `../../skills/dod-contract/SKILL.md`, then follow `../../commands/meta-planner.md` in place.

Before emitting any plan Markdown, create the shared version `1.0` Plan Artifact IR described by `../../schemas/plan-artifact.schema.json`. Run `python3 ../../scripts/plan-artifact-render.py <ir.json> --validate`, then use that same renderer with `--project-root <project-root>` to install the artifact. Do not write Markdown directly: this keeps Codex and Claude output deterministic and preserves the one-ledger rule for multi-phase plans.
