---
name: meta-eval
description: Dedicated evaluator agent — tests implementations against design criteria, catches what self-review misses
argument-hint: <plan-path | feature-name> [--criteria design|functional|full] [--rounds N] [--fix]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /meta-eval

Post-execution evaluation. Dispatch 8 specialized agents and score design
quality. Evaluation is report-only by default. `--fix` or an explicit user
go-word authorizes a separate remediation round; findings alone never authorize
edits or commits.

## Dashboard stage signal (waterfall — MANDATORY)

This command owns the **REVIEW** waterfall stage (6/6). Keep `/meta-dashboard` in sync — fire-and-forget, never let it block evaluation:
- **First action:** `bash ${CLAUDE_PLUGIN_ROOT}/scripts/stage-emit.sh "<plan-path>" review in_progress`
- **On finish (grade ≥ B):** `bash ${CLAUDE_PLUGIN_ROOT}/scripts/stage-emit.sh "<plan-path>" review completed` (use `blocked` if it fails the bar)

`<plan-path>` is the plan/feature you were invoked on. This shows the plan at Stage 6 — the waterfall's terminal stage before archive.

## Flow

### 1. Environment health check

Run `references/eval-protocol.md` health check. Read health endpoints from config. If services are down, report and exit.

### 2. Round 1: Dispatch all 8 agents

Agents from `references/eval-agents.md`. Dispatch in parallel. Collect findings.

### 3. Design quality scoring

Invoke `design-eval` skill. Reads design doc path from `bash scripts/config-get.sh meta_dev.paths.design_doc`. Score on 4 dimensions.

### 4. Triage

Bundle findings by severity and emit the structured
`PASS | CONDITIONAL_PASS | FAIL` review artifact from
`workflow-skills/code-review-protocol/SKILL.md`.

- Without explicit fix authorization: stop after the report. Do not dispatch a
  fixer, edit, stage, or commit.
- With `--fix`/go authorization: preserve the original verdict, apply only
  causally supported in-scope fixes, run focused verification, exact-path
  commit changed files, then continue to the next evaluation round.

### 5. Round 2 (and 3 if authorized and needed)

After an authorized remediation, re-dispatch agents. Check resolution and
regressions. Otherwise omit extra rounds that would only repeat the same
unchanged evidence.

### 6. Final report

Per `references/eval-protocol.md` template. Grade ≥ B → pass. Grade < B → flag for human review.

Config: `bash scripts/config-get.sh` for paths/models/eval sections.
