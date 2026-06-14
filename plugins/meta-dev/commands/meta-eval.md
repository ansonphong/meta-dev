---
name: meta-eval
description: Dedicated evaluator agent — tests implementations against design criteria, catches what self-review misses
argument-hint: <plan-path | feature-name> [--criteria design|functional|full] [--rounds N]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: opus
---

# /meta-eval

Post-execution evaluation. Dispatch 8 specialized agents, score design quality, loop until grade ≥ B.

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
