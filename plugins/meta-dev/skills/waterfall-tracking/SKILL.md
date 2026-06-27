---
name: waterfall-tracking
description: Stand up and maintain a visible stage-level task list for the /meta-dev 6-stage waterfall. Use in autopilot/walk runs so the user can walk away and watch Brainstorm→Design→Plan→Harden→Execute→Review progress live. Stage granularity only — never mirrors /meta-execute's per-task list.
allowed-tools: [TaskCreate, TaskUpdate, Bash]
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

### 2b. Mirror every transition to the durable dashboard (MANDATORY)

The `TaskUpdate` list is **ephemeral** — it vanishes when the run ends. So at **every** stage transition, alongside the `TaskUpdate`, emit a durable stage event (fire-and-forget — never let it block the run):

```
bash ${CLAUDE_PLUGIN_ROOT}/scripts/stage-emit.sh "<plan-path>" <stage> <status>
```
- `<plan-path>` — the plan file/dir for this subject (prefix per subject in multi-item runs).
- `<stage>` — `brainstorm | design | plan | harden | execute | review` (maps to 1→6).
- `<status>` — `in_progress` on start, `completed` on exit-criteria, `blocked` on halt — mirror the same status you pass to `TaskUpdate`.

`stage-emit.sh` patches the plan's YAML `stage:`/`status:` frontmatter in place — that frontmatter is the single source of truth for the plan's stage — and appends a slim history event to `events.jsonl`. `/meta-dashboard` then computes live from the plans via `scripts/plan-index.py`; there is no plan `state.json` to maintain. Emit on start AND on completion of each stage; emitting twice is harmless (last write wins). The stage-owning commands also emit when run standalone, so the dashboard stays correct whether the waterfall runs via `/meta-dev` or a command is invoked directly.

### 3. Nested, not duplicated

Stage 5 delegates to `/meta-execute`, which stands up its OWN per-*task* list (one entry per `### Task N:` in the plan). That is a separate, finer-grained tracker. Mark `Stage 5 — Execute` `in_progress`, let `/meta-execute` drive its task list, then mark `Stage 5` `completed` on return. **Never mirror execute's individual tasks into the stage list** — two lists at two granularities, zero overlap.

## Rules

- **Stage granularity only.** This list tracks the six waterfall stages, nothing finer.
- **Live, not retrospective.** Every transition is mirrored the moment it happens, never reconstructed at the end.
- **Honest trail.** Skips, blocks, and halts are shown as such — a `completed` stage means its exit criteria were genuinely met.
