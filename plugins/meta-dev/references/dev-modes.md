# Dev Modes — Cruise Control, Interactive, Probe Trigger

How `/meta-dev` operates in different modes.

## Mode Detection

At startup, `/meta-dev` detects the mode:
- **Cruise (autopilot):** `--cruise` flag OR keyword detection in subject ("autopilot", "cruise", "auto", "walk", "unattended") OR Accept Edits permission mode
- **Interactive:** Default. Stage-by-stage with user confirmation between stages.
- **Probe-triggered:** Subject contains probe keywords ("why", "stuck", "loop", "keep failing", "wrong", "investigate", "debug")

**Independent flag — `--codex` (cross-family gap-scan).** Orthogonal to the mode above; combines with any of them. When present, `/meta-dev` inserts **Stage 4.5: Codex Gap-Scan Pass** between HARDEN (Stage 4) and EXECUTE (Stage 5) — a read-only cross-family (GPT) audit of the hardened plan, with findings fed back to GLM/DeepSeek to integrate. Full procedure: `references/dev-swarms.md` → "Stage 4.5". OFF by default; absent the flag the waterfall runs Stage 4 → Stage 5 unchanged. The pass is entirely pre-execution and does not relax the Stage-5 gate.

## Quick-Fix Waterfall Bypass

**Before mode detection, triage the subject for triviality.** Not every subject deserves the full 6-stage waterfall. Trivial work bypasses Stages 1-4 and goes **straight to Stage 5 (Execute)**.

A subject is **trivial** (bypass eligible) when ALL of these hold:
- Touches roughly 3 files or fewer
- Introduces NO new behavior (typo fix, config change, copy edit, dependency pin, mechanical refactor, version bump, status/doc update)
- Has an obvious, well-understood implementation with no design questions

A subject is **non-trivial** (full waterfall required) when EITHER holds:
- Touches more than ~3 files, OR
- Introduces new behavior (new feature, new API surface, new UX flow, schema change, new module)

**Bypass routing:**
- Trivial → skip Stages 1-4, run Stage 5 (`/meta-execute`) directly, then Stage 6 review as normal.
- Non-trivial → run the full 6-stage pipeline.
- When in doubt, treat as non-trivial (the full pipeline is the safe default).

The bypass only skips the *planning/hardening* stages — it never skips execution review or the Stage-5 safety boundary below.

## Cruise Control (Autopilot) — THE HEADLINE FEATURE

**Cruise mode drives all 6 stages unattended.** It chains: brainstorm → design → plan → harden → execute → review → done. Zero human prompts between stages.

### Stage Progress Task List (autopilot/walk — MANDATORY)

**Cruise/walk exists so the user can walk away and watch the waterfall progress.** Stand up a visible stage-level task list via `TaskCreate` BEFORE Stage 1 and keep it live with `TaskUpdate` for the whole run — `in_progress` on start, `completed` on exit-criteria, `blocked` on halt. No tracker visible = the run has not started correctly. It is the *stage*-level tracker; Stage 5's `/meta-execute` runs its own *task*-level list, distinct and never mirrored. Interactive mode: recommended but optional; autopilot/walk makes it mandatory.

**The full procedure (entries, dependencies, multi-item, skip/block handling, nesting) lives in the `waterfall-tracking` skill** (`skills/waterfall-tracking/SKILL.md`) — invoke it; the loop below wires its updates into stage advancement.

### The 6-Stage Complete-Then-Advance Loop

```
stand up the 6-stage task list (TaskCreate) — autopilot/walk: mandatory
for each stage in [brainstorm, design, plan, harden, execute, review]:
  1. TaskUpdate stage → in_progress
  2. Run the stage's full procedure (see references/dev-swarms.md)
  3. Check exit criteria (below)
  4. If criteria met: TaskUpdate stage → completed, commit stage artifacts, advance
  5. If criteria NOT met after max retries: TaskUpdate stage → blocked, halt this subject's pipeline, report
# IF --codex was passed: after Stage 4 exits green, run Stage 4.5 (Codex gap-scan) before Stage 5.
#   It is a conditional sub-stage of harden, not a 7th stage — track it as a nested item under Harden
#   (or its own row) per the exit-criteria table. Procedure: references/dev-swarms.md → "Stage 4.5".
```

### Per-Stage Exit Criteria (must be met before advancing)

| Stage | Exit criteria | Max retries |
|-------|--------------|-------------|
| 1 Brainstorm | Direction converged (synthesis agent reports convergence) | 2 |
| 2 Design | Design doc produced + design-quality gate grade ≥ B | 2 |
| 3 Plan | Master plan + phase files generated + loop-gap config exists | 2 |
| 4 Harden | Loop-gap reports "NO GAPS REMAINING" | 3 |
| 4.5 Codex gap-scan (`--codex` only) | Codex reports no material gaps, OR 2-call cap hit with findings triaged + logged; plan reflects integrated fixes | 2 Codex calls (hard cap) |
| 5 Execute | All tasks DONE, working tree clean | 1 (failures escalate) |
| 6 Review | Eval grade ≥ B, context synced, plan archived, dashboards updated | 2 |

### commit per stage

After each stage completes (exit criteria met):
1. `git add <stage artifacts>`
2. `git commit -m "chore(dev): complete Stage N — <stage-name> for <subject>"`
3. `git push`

This creates a clean git trail: 6 commits minimum for a full cruise run.

### error isolation

A single failing stage halts only THAT subject's pipeline (halt only that subject, not others). It does not halt the orchestrator.
- If Stage 4 (harden) fails: subject is left at "plan generated, hardening failed"
- Other subjects (multi-item mode) continue independently
- Failed stage emits to inbox with severity based on stage

### Chaining the Ported Commands

Cruise mode chains the PORTED plugin commands (not local):
- Stage 3 → `/meta-planner` (thin orchestrator, this plugin)
- Stage 4 → `/loop-gap` (this plugin)
- Stage 5 → `/meta-execute` (thin orchestrator, this plugin)
- Stage 6 → `/meta-eval` + `/meta-audit` + `/housekeeping` (this plugin)

## Interactive Mode

Same 6-stage loop, but pauses for user confirmation before each stage transition:
1. Complete stage N
2. Report: "Stage N complete. Ready to move to Stage N+1?"
3. Wait for user GO
4. Advance

## Probe Trigger

When subject contains probe keywords: delegate to `/meta-probe` FIRST for diagnosis, then return to the waterfall with probe findings injected into Stage 1 (brainstorm).

## Multi-Item Orchestration

When given multiple subjects (comma-separated or quoted list):
- Cap 2 concurrent subjects (shared context budget)
- Each subject gets its own independent 6-stage pipeline
- Error isolation: one subject failing does not affect others
- Queue remaining subjects; advance next when one completes

## Important Rules (Safety Invariants)

These hold in ALL modes — interactive, cruise, probe, and quick-fix bypass.

1. **NEVER write code before Stage 5.** Stages 1-4 (brainstorm, design, plan, harden) are pure documentation/planning. No source files are touched until Execute. (The quick-fix bypass is the only path that reaches Stage 5 early — and only because it has *no* planning stages to write code ahead of.)
2. **The default stop is Stage 4 — execution requires explicit user permission. This is the safety boundary.** `/meta-dev` defaults to halting after hardening with a runnable, reviewed plan; it does NOT auto-execute unless the user explicitly authorizes Stage 5 (via `--to 5`/`--to 6`, cruise/autopilot, or a direct GO).
   - **Cruise mode defaults its gate to `none`**, which removes per-stage prompts. That makes restating this Stage-5/Stage-4 boundary MORE important, not less: invoking cruise (or `--to 6`) IS the explicit permission to cross into execution. Absent that explicit signal, stop at Stage 4.
3. **Plans NEVER go in source or doc directories.** ALL plans, designs, and hardening artifacts live under the configured `plans_root` (`bash scripts/config-get.sh meta_dev.paths.plans_root`). NEVER write them into source trees, `docs/`, or any child/sub-repo. This is non-negotiable across every stage.
