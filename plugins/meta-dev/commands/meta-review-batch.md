---
name: meta-review-batch
description: Batched review queue — review multiple items in sequence, render results via review-batch-render.py
argument-hint: [<path> | <file-glob> | <plan-dir>]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /meta-review-batch

Batched code review queue. Reviews multiple items and renders aggregated results.

## Flow

1. Resolve review targets (paths, globs, or plan directories)
2. For each target, spawn `review-agent` (`agents/review-agent.md`) within the
   configured worker limit. Prompt urgent blockers immediately; let each reviewer
   finish safe inspection of its declared scope and return all findings together.
3. Collect verdicts, confidence scores, blast radii, and issues in the existing
   `{"reviews": [...]}` envelope; include the target in each review.
4. Pipe that JSON to `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review-batch-render.py
   --validate-only`. If validation fails, keep the affected gate pending and
   correct the review evidence before rendering or accepting it.
5. Pipe the same JSON to `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review-batch-render.py`.
   Report every finding, the exact critical/high count, and gate decisions.

Config: `plans/_dashboard/settings.json` (max parallel reviews, model tier).
