---
name: meta-orchestrator
description: Front-door dispatcher — detects intent and routes to the right meta-dev command
argument-hint: <natural-language-intent>
allowed-tools: [Read, Write, Bash, Glob, Grep, Agent]
model: opus
---

# /meta-orchestrator

Front-door dispatcher. Routes natural language to the correct meta-dev command.

## Detection & Routing

- "new idea" / "brainstorm" / "explore" → `/meta-classify` + `/meta-dev --to 2`
- "plan" / "restructure" / "master plan" → `/meta-planner`
- Explicit build/execute/autopilot intent → **Autopilot sequence** below, within
  the user's requested stage bounds. Incidental keywords are not authorization.
- "harden" / "gap scan" / "loop-gap" → `/loop-gap`
- "probe" / "investigate deeply" / "dig into" / "go deep on" / "why does X keep" / "get to the bottom of" → `/meta-probe`
- "review" / "evaluate" / "grade" → `/meta-eval`
- "security" / "audit" → `/meta-security`
- "UX" / "design review" → `/meta-ux` or `/meta-review-design`
- "ship" / "release" / "deploy" → discover the project's declared release
  procedure; do not assume a desktop/web stack or command name.
- "cleanup" / "housekeeping" / "archive" → `/housekeeping`
- "dashboard" / "status" → `/meta-dashboard`
- "config" / "settings" → `/meta-config`
- "init" / "setup" → `/meta-init`
- "repair" / "fix" → `/meta-repair`
- "sweep" / "maintenance" → `/meta-sweep`
- "task agent" / "async bots" / "spin off subagents" → `/meta-task-agent`

If ambiguous, present options with confidence scores.

## Autopilot sequence (execute / build / implement / autopilot intent)

Preserve the user's intent and requested stage ceiling. Read
`references/adaptive-workflow.md`; resolve depth before routing. Reuse valid
existing hardening/review evidence rather than repeating the same pass.

1. **HARDEN** — If current evidence is absent/stale and hardening is in scope,
   run `/meta-loop-gap <plan>` at the resolved depth. Source fixes still need
   implementation authority; confidence is not permission.
2. **EXECUTE** — Run `/meta-execute <plan>` with resolved task/slice ownership.
   Preserve per-handle evidence, planctl state, and host-wide worker limits.
3. **REVIEW** — Use meta-execute's covering native review; do not dispatch a
   duplicate Opus or cross-family pass merely because execution returned.
4. **VERDICT** — Report accepted work and blockers. Release/deploy is a separate
   authorization boundary, not an automatic consequence of a clean review.

**Flags:**
- `--no-harden` → skip step 1 only. Steps 2–4 still run.

Explicit `--from`/`--to` stage bounds are honored without expanding the task.
