# Development Swarms — Stage-Specific Agent Configurations

How `/meta-dev` dispatches agent swarms per waterfall stage. Model tiers read from `bash scripts/config-get.sh meta_dev.models.stage_overrides.<stage>`.

## Stage 1: Brainstorm (Wave 1 — Research)

**Goal:** Understand intent, explore alternatives, converge on direction.

Dispatch 4-6 agents in parallel:
- **Root-cause agent** — what problem are we really solving?
- **Best-practice agent** — how have similar problems been solved?
- **UX agent** — what does the user experience look like?
- **Elegance agent** — what's the simplest thing that could work?
- **Robustness/FMEA agent** — what could go wrong?
- **Security agent** — what are the trust boundaries?

Each agent: different perspective, same neutral problem statement. No agent sees another's output.

**Synthesis:** One synthesis agent reads all outputs, identifies convergent themes + divergent opinions, produces direction recommendation.

**Exit criteria:** Clear understanding of what to build, why, and rough scope. User confirmation (in interactive mode) or auto-continue (in cruise mode).

## Stage 2: Design (Wave 2 — Synthesis)

**Goal:** Produce design doc with architecture, data models, API shapes, UX flows.

**Design generation:** 1-2 agents produce the design doc.

**Design quality gate (Stage 2.5):** Dispatch `design-eval` skill. Must meet grade threshold before advancing.

**Exit criteria:** Design doc covers all Stage 1 requirements. Design quality ≥ B.

## Stage 3: Plan

**Goal:** Generate execution-ready plan with phase files, tasks, verify hooks.

Delegate to `/meta-planner` (now ported — thin orchestrator + references).

**Exit criteria:** Master plan + phase files generated. Loop-gap config exists.

## Stage 4: Harden

**Goal:** Gap-scan plan to "NO GAPS REMAINING."

Delegate to `/loop-gap` with the loop-gap config from Stage 3.

**Exit criteria:** Loop-gap reports "NO GAPS REMAINING."

## Stage 5: Execute

**Goal:** Run the plan task-by-task.

Delegate to `/meta-execute` (now ported — thin orchestrator + references).

**Exit criteria:** All tasks DONE. Working tree clean.

## Stage 6: Review

**Goal:** Evaluate implementation, sync context, archive, update dashboards.

- Delegate to `/meta-eval` (now ported) → evaluation report
- Delegate to `/meta-audit` → pipeline health check
- Delegate to `/housekeeping` → archive plan, update STATUS/exec-order, commit

**Exit criteria:** Eval grade ≥ B. Context files updated. Plans archived. Dashboards current.
