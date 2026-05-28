# Dev Modes — Cruise Control, Interactive, Probe Trigger

How `/meta-dev` operates in different modes.

## Mode Detection

At startup, `/meta-dev` detects the mode:
- **Cruise (autopilot):** `--cruise` flag OR keyword detection in subject ("autopilot", "cruise", "auto", "unattended") OR Accept Edits permission mode
- **Interactive:** Default. Stage-by-stage with user confirmation between stages.
- **Probe-triggered:** Subject contains probe keywords ("why", "stuck", "loop", "keep failing", "wrong", "investigate", "debug")

## Cruise Control (Autopilot) — THE HEADLINE FEATURE

**Cruise mode drives all 6 stages unattended.** It chains: brainstorm → design → plan → harden → execute → review → done. Zero human prompts between stages.

### The 6-Stage Complete-Then-Advance Loop

```
for each stage in [brainstorm, design, plan, harden, execute, review]:
  1. Run the stage's full procedure (see references/dev-swarms.md)
  2. Check exit criteria (below)
  3. If criteria met: commit stage artifacts, advance to next stage
  4. If criteria NOT met after max retries: halt this subject's pipeline, report
```

### Per-Stage Exit Criteria (must be met before advancing)

| Stage | Exit criteria | Max retries |
|-------|--------------|-------------|
| 1 Brainstorm | Direction converged (synthesis agent reports convergence) | 2 |
| 2 Design | Design doc produced + design-quality gate grade ≥ B | 2 |
| 3 Plan | Master plan + phase files generated + loop-gap config exists | 2 |
| 4 Harden | Loop-gap reports "NO GAPS REMAINING" | 3 |
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
