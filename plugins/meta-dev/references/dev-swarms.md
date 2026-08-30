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

## Stage 4.5: extra-family gap-scan — Opus (or Sonnet if UI) + Codex Sol

**On by default as part of Stage 4 harden.** One pass each. No DeepSeek. No swarm.

**Goal:** an independent **cross-family** read on the hardened plan, right before code gets written. Stage 4 Grok swarms are same-family. Opus/Sonnet + Codex Sol catch the blind spots.

**Precondition:** Stage 4 Grok swarms have reported "NO GAPS REMAINING" (or run in parallel with the last Grok pass). This is not a substitute for `/loop-gap`.

**The pass (the conductor — Opus — runs this; do NOT hand Codex a `/command`, it can't run our harness):**

1. **Codex gap scan (read-only).** Dispatch **one** Codex worker via `/codex-execute --readonly` (→ `scripts/codex-headless-exec`), pointed at the plan dir (master + phase files). Direct task, e.g.:
   > *"Audit these plan files for gaps: missing coverage, internal contradictions, unhardened edge cases, ordering/dependency errors, unstated assumptions, and integration seams between phases. Produce a structured gap report grouped by severity. Read-only — do not edit any file."*
   Write the report per **`references/plan-artifacts.md`** — the one naming rule: directory plan → `<plan-dir>/gap-report-codex.md`; **single-file plan → `<plan-stem>.gap-report-codex.md`**, a sibling carrying the plan's full stem. No date, no counter — a re-scan overwrites its own report and git holds the history.
2. **Triage (Opus).** Read Codex's report; sort findings into **actionable gaps** vs. noise / false-positives / out-of-scope. Opus judgment, one read — do not blindly pipe every Codex line into a fix.
3. **Integrate-back (Grok).** Feed the actionable gaps to **Grok** to integrate into the plan markdown. Mechanical stamps may go to Spark / Luna / grok-4.5. This is plan-editing, **pre-execution, no source code** — squarely inside the Stage-4 safety boundary. DeepSeek and GLM are paused / named-only.
4. **Bounded re-scan (quota-conscious).** If the integrate pass was substantial, optionally run **one** confirming Codex re-scan. **Hard cap: 2 Codex calls total** (1 scan + 1 confirm). Codex runs on a limited Codex Plus quota — never loop it. After the cap, proceed regardless; log any remaining low-severity findings in the report.

**Exit criteria:** Codex reports no material (high/medium) gaps, OR the 2-call cap is hit with remaining findings triaged and logged. Plan markdown reflects the integrated fixes.

**Safety:** this entire stage is **pre-execution** — Codex is read-only, the integrate-back edits only plan docs. It never writes source code and never crosses the Stage-5 execution boundary. Stage 5 remains gated on explicit user permission exactly as without `--codex`.

## Stage 5: Execute

**Goal:** Run the plan task-by-task.

Delegate to `/meta-execute` (now ported — thin orchestrator + references).

**Exit criteria:** All tasks DONE. Working tree clean.

## Stage 6: Review

**Goal:** Evaluate implementation, sync context, archive, update dashboards.

- Delegate to `/meta-eval` (now ported) → evaluation report
- Delegate to `/meta-audit` → pipeline health check
- Delegate to `/housekeeping` → archive plan, update ledger (drop from `meta-runbook.md` `## Sequence`, one compact line in `meta-runbook-archive.md`), commit

**Exit criteria:** Eval grade ≥ B. Context files updated. Plans archived. meta-runbook current. Dashboards current.
