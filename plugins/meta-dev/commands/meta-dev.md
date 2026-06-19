---
name: meta-dev
description: Universal development lifecycle orchestrator — pushes any subject through the 6-stage waterfall using agent swarms
argument-hint: <subject | plan-path | "idea one" "idea two" ...> [--from <stage>] [--to <stage>] [--gate all|exec|none]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
model: opus
---

# /meta-dev

6-stage development waterfall orchestrator. Autopilot (cruise control) drives all stages unattended.

## Mode Detection

Read `references/dev-modes.md`. Detect: cruise (--cruise flag, keyword, or Accept Edits), interactive (default), or probe-trigger (investigative keywords).

**Quick-fix bypass:** Before detecting mode, triage triviality (see `references/dev-modes.md` → "Quick-Fix Waterfall Bypass"). Trivial work (≤~3 files, no new behavior) skips Stages 1-4 and goes straight to Stage 5; non-trivial (>3 files OR new behavior) runs the full pipeline. When in doubt, treat as non-trivial.

## Stage Pipeline

Stage definitions in `references/dev-swarms.md`. Each stage delegates to ported plugin commands:

1. **Brainstorm** → research swarm (Wave 1)
2. **Design** → design doc + design-eval quality gate (Stage 2.5)
3. **Plan** → `/meta-planner` (generates master + phase files + loop-gap config)
4. **Harden** → `/loop-gap` (gap-scan to "NO GAPS REMAINING")
5. **Execute** → `/meta-execute` (subagent-driven, verify + commit per task)
6. **Review** → `/meta-eval` + `/meta-audit` + `/housekeeping` (archive + sync dashboards)

## Stage Progress Tracking (autopilot/walk — non-negotiable)

**When the run is autopilot (`cruise`/`autopilot`/`auto`/`walk`/`unattended`/`--cruise`), stand up a visible 6-stage task list via `TaskCreate` BEFORE Stage 1** — one entry per waterfall stage — **and keep it live with `TaskUpdate`** (`in_progress` on start → `completed` on exit-criteria → `blocked` on halt). The user walks away to watch the waterfall progress, so this tracker is a primary deliverable; no tracker visible = run not started correctly. It is the *stage*-level tracker; Stage 5's `/meta-execute` runs its own *task*-level list — distinct, never mirrored. Full pattern: `references/dev-modes.md` → "Stage Progress Task List".

## Cruise Control (Autopilot)

Read `references/dev-modes.md` for the full autopilot loop. Key rules:
- Complete each stage fully (including its internal swarm/gates) before advancing
- Per-stage exit criteria must be met (see dev-modes.md table)
- Commit after every stage (minimum 6 commits for a full run)
- Error isolation: one failing stage halts only that subject, not the whole run
- Chains the PORTED plugin commands, not local

## Multi-Item Mode

When given multiple subjects: cap 2 concurrent. Each independent pipeline. Queue remainder.

## Post-Stage Housekeeping

After each stage: update exec-order `Stage: N/6` annotation. After Stage 6: full housekeeping per `references/dev-housekeeping.md` (archive, update STATUS, update exec-order, commit).

## Safety Invariants

These hold in ALL modes (see `references/dev-modes.md` → "Important Rules"):
1. **NEVER write code before Stage 5** — Stages 1-4 are pure planning/docs.
2. **Default stop is Stage 4; execution needs explicit user permission** — this is the safety boundary. Cruise mode defaults its gate to `none`, so invoking cruise/`--to 6` IS that explicit permission; absent it, stop at Stage 4.
3. **Plans NEVER go in source or doc dirs** — all plan/design/hardening artifacts live under the configured `plans_root`, never in source trees, `docs/`, or child repos.

Config: `bash scripts/config-get.sh` for paths/models/filesystem sections.
