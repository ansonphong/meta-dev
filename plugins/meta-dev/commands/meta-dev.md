---
name: meta-dev
description: Universal development lifecycle orchestrator — pushes any subject through the 6-stage waterfall using agent swarms
argument-hint: <subject | plan-path | "idea one" "idea two" ...> [--from <stage>] [--to <stage>] [--gate all|exec|none]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
model: sonnet
---

# /meta-dev

6-stage development waterfall orchestrator. Invokes HOTL skills for classification/contract, delegates to meta-planner, meta-execute, meta-eval, and housekeeping.

## Stage pipeline

1. **Brainstorm** → invoke `hotl-classification` skill
2. **Design** → invoke `dod-contract` skill + optional `/meta-ux`, `frontend-design`
3. **Plan** → delegate to `/meta-planner`
4. **Harden** → delegate to `/loop-gap` (plan gap-scan, BEFORE execute — never skip)
5. **Execute** → delegate to `/meta-execute` (activates `/meta-guard`)
6. **Review** → invoke `superpowers:requesting-code-review` (code review of built diff) + delegate to `/meta-eval`, `/meta-audit`, `/meta-ux`, `/housekeeping`

> **Execute-intent (autopilot) runs stages 4→6, never stage 5 alone.** See the Autopilot sequence in `meta-orchestrator.md`. Hardening (stage 4) is default-on; `--no-harden` skips only that step.

Config: `plans/_dashboard/settings.json` (read via scripts/config-get.sh).

See `.claude/commands/meta-planner.md` for plan structuring, `.claude/commands/meta-execute.md` for execution.
