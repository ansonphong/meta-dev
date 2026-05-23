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
- "autopilot" / "cruise control" / "cruise" / "full send" / "build it" / "go" / "execute" / "implement" / "build" → **Autopilot sequence** (see below). NEVER route to `--from 5 --to 5` — that skips hardening.
- "harden" / "gap scan" / "loop-gap" → `/loop-gap`
- "probe" / "investigate deeply" / "dig into" / "go deep on" / "why does X keep" / "get to the bottom of" → `/meta-probe`
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

## Autopilot sequence (execute / build / implement / autopilot intent)

When the user says **autopilot** (or execute / build / implement / "go" / "cruise control"), run these steps **IN ORDER**. Do NOT collapse to execute-only. Narrate each step as you go. This is the default — hardening is included every time unless explicitly skipped.

1. **HARDEN (before)** — Unless `--no-harden` is present, run `/loop-gap <plan>` to gap-scan the PLAN. Apply auto-fixes (confidence ≥ 0.8), surface blockers for review. This is the "Phase 4 hardening" step that must never be silently skipped.
2. **EXECUTE** — Run `/meta-execute <plan>` (unchanged: one fresh Sonnet per task, verify + commit + push between).
3. **CODE REVIEW (after)** — Invoke the `superpowers:requesting-code-review` skill on the produced diff. This is a code review of the built code — NOT a second loop-gap pass.
4. **VERDICT** — If review returns blocking issues → fix loop (re-dispatch via `/meta-execute` or `/meta-repair`) before ship. Else green-light → `/meta-ship`.

**Flags:**
- `--no-harden` → skip step 1 only. Steps 2–4 still run.

The old `--from 5 --to 5` execute-only shortcut is **REMOVED from front-door routing** because it deterministically skipped hardening. It is still reachable by typing the raw `/meta-dev --from 5 --to 5` if a user explicitly wants execute-only.
