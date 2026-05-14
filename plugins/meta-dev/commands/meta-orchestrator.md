---
name: meta-orchestrator
description: Front-door dispatcher — detects intent and routes to the right meta-dev command
argument-hint: <natural-language-intent>
allowed-tools: [Read, Write, Bash, Glob, Grep, Agent]
model: sonnet
---

# /meta-orchestrator

Front-door dispatcher. Routes natural language to the correct meta-dev command.

## Detection & Routing

- "new idea" / "brainstorm" / "explore" → `/meta-classify` + `/meta-dev --to 2`
- "plan" / "restructure" / "master plan" → `/meta-planner`
- "execute" / "implement" / "build" → `/meta-dev --from 5 --to 5 --gate none`
- "harden" / "gap scan" / "loop-gap" → `/loop-gap`
- "review" / "evaluate" / "grade" → `/meta-eval`
- "security" / "audit" → `/meta-security`
- "UX" / "design review" → `/meta-ux` or `/meta-review-design`
- "ship" / "deploy" / "release" → `/meta-ship`
- "cleanup" / "housekeeping" / "archive" → `/housekeeping`
- "dashboard" / "status" → `/meta-dashboard`
- "config" / "settings" → `/meta-config`
- "init" / "setup" → `/meta-init`
- "repair" / "fix" → `/meta-repair`
- "sweep" / "maintenance" → `/meta-sweep`

If ambiguous, present options with confidence scores.
