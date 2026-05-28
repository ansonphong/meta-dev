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

### 1. Read input + detect project context

Read the input plan. Load host conventions via `references/host-claude-contract.md`. Read the host repo's `CLAUDE.md` for test commands, branch policy, directory layout.

### 2. Inventory tasks, map dependencies, identify phases

Extract every unit of work. Group into phases (3-8 tasks each). Apply task granularity rules from `references/host-claude-contract.md`.

### 3. Codebase verification (ground truth)

Run `references/codebase-verification.md` protocol: collect file refs → read each file → check staleness via `git log` → discover callers → resolve mismatches.

### 4. API contract specification (for full-stack plans)

Define request/response shapes, error codes, endpoints before implementation tasks reference them.

### 5. Generate phase files with TDD + Verify hooks

Each phase file: Codebase Snapshot → tasks with Verify-Before/After hooks → TDD steps (test→fail→impl→pass→commit). Use semantic anchors (function/class names), never line numbers (see `templates/patterns/planner.md`).

### 6. Generate master plan with checklist + execution rules

`00-master-plan.md` with: header, file structure, gap fixes, ALL tasks as `### Task N:` checkboxes, integration test task, execution rules.

### 7. Generate `.loop-gap-config.md`

Per `references/loopgap-config-gen.md`. Signature snapshots from Stage 1.5 reads, affected files from grep, prioritized gap categories.

### 8. Validate output

Run `bash scripts/planner-validate.sh <plan-dir>` for deterministic checks. Invoke `plan-validation` skill for judgment checks. Fix all errors before presenting result.

Config: `bash scripts/config-get.sh` for `paths`/`models` sections. Model tiers from `models.stage_overrides`.
