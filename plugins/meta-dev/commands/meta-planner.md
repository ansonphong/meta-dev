---
name: meta-planner
description: Restructure plans into execution-ready format with master checklist, phase files, verification hooks, and loop-gap config
argument-hint: <path-to-plan-file-or-directory>
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /meta-planner

Convert plan docs into execution-ready format with phase files, verification hooks, and loop-gap config.

## Pipeline

1. Read input + detect project context
2. Inventory tasks, map dependencies, identify phases
3. Codebase verification (ground truth pass — verify file paths + signatures exist)
4. API contract specification (for full-stack plans)
5. Generate phase files with TDD steps + Verify-Before/After hooks
6. Generate master plan with checklist + execution rules
7. Generate `.loop-gap-config.md`
8. Validate output against 37+ quality checks

Config: `plans/_dashboard/settings.json` (model tiers, phase size limits).
