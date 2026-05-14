---
name: meta-review-batch
description: Batched review queue — review multiple items in sequence, render results via review-batch-render.py
argument-hint: [<path> | <file-glob> | <plan-dir>]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /meta-review-batch

Batched code review queue. Reviews multiple items and renders aggregated results.

## Flow

1. Resolve review targets (paths, globs, or plan directories)
2. For each target, spawn `review-agent` (`agents/review-agent.md`) in parallel
3. Collect verdicts, confidence scores, blast radii, and issues
4. Render aggregated results via `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review-batch-render.py`
5. Summary: pass count, fail count, critical issues, recommended gate decisions

Config: `plans/_dashboard/settings.json` (max parallel reviews, model tier).
