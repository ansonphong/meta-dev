---
name: meta-eval
description: Dedicated evaluator agent — tests implementations against design criteria, catches what self-review misses
argument-hint: <plan-path | feature-name> [--criteria design|functional|full] [--rounds N]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /meta-eval

Post-execution evaluation. Dispatch 8 specialized agents, score design quality, loop until grade ≥ B.

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

### 4. Triage + fix round

Auto-fix trivials. Bundle findings by severity. Fix. Commit.

### 5. Round 2 (and 3 if needed)

Re-dispatch agents. Check resolution. Check regressions. Report grade.

### 6. Final report

Per `references/eval-protocol.md` template. Grade ≥ B → pass. Grade < B → flag for human review.

Config: `bash scripts/config-get.sh` for paths/models/eval sections.
