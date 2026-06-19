---
name: waterfall-tracking
description: Stand up and maintain a visible stage-level task list for the /meta-dev 6-stage waterfall. Use in autopilot/walk runs so the user can walk away and watch Brainstorm→Design→Plan→Harden→Execute→Review progress live. Stage granularity only — never mirrors /meta-execute's per-task list.
allowed-tools: [TaskCreate, TaskUpdate]
---

# Waterfall Tracking Skill

Make the `/meta-dev` waterfall **watchable**. Cruise/walk exists so the user can walk away and see progress; the watching surface is a visible task list at *stage* granularity. This is the same proven discipline as `/meta-execute`'s "visible main-thread task list" (`commands/meta-execute.md` → Prerequisite), one level up.

**Invoked by `/meta-dev`** at the start of any autopilot/walk run (keywords `cruise`/`autopilot`/`auto`/`walk`/`unattended`, the `--cruise` flag, or Accept-Edits mode). Mandatory in autopilot/walk; recommended-but-optional in interactive mode.

## Procedure

### 1. Create once, up front (before Stage 1)

Call `TaskCreate` — one entry per waterfall stage, named for what it does. Chain dependencies (each stage depends on the prior):

```
Stage 1 — Brainstorm
Stage 2 — Design
Stage 3 — Plan (/meta-planner)
Stage 4 — Harden (/loop-gap)
Stage 5 — Execute (/meta-execute)
Stage 6 — Review (/meta-eval + audit + housekeeping)
```

No tracker visible = the run has not started correctly. For multi-item runs, create one stage list per subject and prefix entries with the subject so concurrent pipelines stay legible.

### 2. Update as state changes (never batched at the end)

- Stage starts → `TaskUpdate` to `in_progress`.
- Exit criteria met (the per-stage exit-criteria table in the plugin's `dev-modes` reference) → `completed`; then commit the stage artifacts.
- Stage halts after max retries → `blocked` with the failure reason; the rest of that subject's stages stay `pending` (error isolation — one subject's failure never halts others).
- Quick-fix bypass skips Stages 1-4 → mark them `completed` with a `⏭ skipped (trivial)` note so the trail is honest about what actually ran.

### 3. Nested, not duplicated

Stage 5 delegates to `/meta-execute`, which stands up its OWN per-*task* list (one entry per `### Task N:` in the plan). That is a separate, finer-grained tracker. Mark `Stage 5 — Execute` `in_progress`, let `/meta-execute` drive its task list, then mark `Stage 5` `completed` on return. **Never mirror execute's individual tasks into the stage list** — two lists at two granularities, zero overlap.

## Rules

- **Stage granularity only.** This list tracks the six waterfall stages, nothing finer.
- **Live, not retrospective.** Every transition is mirrored the moment it happens, never reconstructed at the end.
- **Honest trail.** Skips, blocks, and halts are shown as such — a `completed` stage means its exit criteria were genuinely met.
