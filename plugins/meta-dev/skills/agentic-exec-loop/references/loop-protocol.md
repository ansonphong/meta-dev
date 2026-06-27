# Loop Protocol — execute → review → fix (phase-gated)

## Roles
- **Conductor** (main thread, Opus): dispatches, reads ONE verdict line per
  phase + each worker's one-line result. NEVER reads a diff, OUTPUT_FILE.raw,
  or the reviewer transcript.
- **Worker** (headless process): DeepSeek `--backend deep` (default) or GLM
  `--backend glm` via ${CLAUDE_PLUGIN_ROOT}/scripts/claude-headless-exec;
  Codex via ${CLAUDE_PLUGIN_ROOT}/scripts/codex-headless-exec (no --backend).
  Output → OUTPUT_FILE; conductor reads only the distilled `result`.
- **Reviewer**: Agent subagent, agentType `meta-dev:review-agent` (Opus). Given
  {phase_spec, phase_pre_sha, phase_verify_cmds}, it computes its OWN
  `git diff <phase_pre_sha>..HEAD` and returns the verdict JSON below.
- **Fixer**: a headless worker fed the reviewer's `issues`.

## Per-task work (worker self-manages — no Opus per task)
1. At phase start record `PHASE_PRE_SHA=$(git rev-parse HEAD)`.
2. For EACH task in the phase: dispatch a FRESH worker (new headless process,
   clean context) with the task spec INCLUDING its `Verify:` command. The
   worker runs its own verify hook and self-fixes locally before returning.
   Conductor reads only the one-line `result`, flips the task checkbox, and
   commits per task (momentum). No Opus review at this granularity.

## Phase gate — the single Opus checkpoint per phase
3. At phase end dispatch the Reviewer. Verdict JSON (review-agent's real shape):
   `{ "verdict": "PASS | CONDITIONAL_PASS | FAIL", "confidence": 0-1,
   "blast_radius": "isolated | file | module | cross-cutting | dependency-graph",
   "issues": [ {severity,file,line,title,description,suggested_fix} ],
   "summary": "..." }`.
4. Branch:
   - **PASS** → advance to next phase.
   - **CONDITIONAL_PASS** → apply the `suggested_fix`es via one deep Fixer,
     then advance (no re-review needed for minor issues).
   - **FAIL** → Fix ladder (step 5).
5. **Fix ladder** (max 2 worker attempts, then surface):
   - Attempt 1: Fixer `--backend deep` fed `issues` → re-Review (step 3).
   - Attempt 2 (still FAIL): Fixer `--backend glm` → re-Review.
   - Still FAIL → failure dossier to the inbox (repair-loop convention) +
     surface the one-line `summary`. Leave the phase uncommitted-beyond-tasks. Stop.

## Context watchdog — pause-and-compact at a seam (conductor-run, NON-NEGOTIABLE on long runs)
A long playbook (many phases) accretes context in the orchestrating Opus thread
even though diffs never cross back — task tracker, verdicts, worker result lines,
and the user-facing narration all accumulate. Left unchecked the harness fires
its blunt hard auto-compact (`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`) mid-phase. The
watchdog gets ahead of that with a GRACEFUL forward-compact at a clean seam.

**The phase boundary IS the convenient seam** — the tree is committed there
(per-task commits + phase gate), so it is always safe to compact.

At **each phase gate, AFTER the verdict resolves and the phase's work is
committed** (i.e. right before advancing to the next phase), the conductor runs:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/context-gauge.py   # default threshold 300000
```

Read only `CONTEXT_VERDICT`:
- **`OK`** (or `UNKNOWN`) → advance to the next phase as normal.
- **`OVER`** → do NOT start the next phase. The current phase is already
  committed (clean seam), so:
  1. Invoke `/meta-compact` (the `meta-dev:meta-compact` skill) — it writes a
     forward handoff whose **▶ NEXT ACTION is "resume the playbook at phase
     N+1"**, naming the plan path + the next phase file + the per-phase loop.
  2. Surface the one-line pause notice + the exact `/compact read …` trigger to
     the user and STOP. Compaction is the user's (or auto-compact's) to pull —
     the loop never runs `/compact` itself.
  3. After the user compacts, the resume contract reads the handoff and
     continues the loop at phase N+1 — no re-orientation, no lost momentum.

Threshold is configurable: `--threshold N`, or env `META_DEV_CONTEXT_THRESHOLD`
(default 300000). This watchdog is a SESSION practice of the orchestrating Opus
(it owns the `/meta-compact` + `/compact` primitives); it is NEVER handed to a
headless worker. Workers have fresh, isolated context per task and never compact.

## Plans without `## Phase N` structure
Treat the whole plan as one phase → a single review at the end (this matches
bare meta-execute's end-of-run review timing). With only one seam (the end), the
context watchdog has no mid-run boundary to act on — for such single-phase plans
the harness auto-compact remains the backstop; the watchdog matters for the
multi-phase playbooks it was built for.

## Context-hygiene contract (NON-NEGOTIABLE)
Per phase, the only things crossing back to main: N one-line worker `result`s
+ one phase verdict. The conductor MUST NOT git diff into its own context,
read OUTPUT_FILE.raw, or read the reviewer transcript. The task tracker
(tasks + per-phase verdict) stays in main for user followability.

## Conductor cache-keepalive during long idle (SESSION practice, not command automation)
The Anthropic prompt cache has a ~300s sliding TTL. When the orchestrating
Opus SESSION dispatches a background worker and then idles, it MAY keep its
cache warm by arming a wakeup at **270s** (4m30s — 30s margin under the 300s
cliff; never 285s+). On wake, if the worker still runs, do a one-line progress
touch and re-arm; on completion proceed warm. This is unconditional arm-on-idle
(short workers finish before 270s and never trigger it — nothing to predict).
This is a behavior of the human-directed orchestrating session (which has the
ScheduleWakeup primitive); it is NOT automated inside the command and is NEVER
given to a headless worker. Cost: each tick ≈ one cached-prefix read (~10%
input) + tiny output; net win only for large-context + long-idle.

## Tier mapping
- `--deep` (default): Worker=deep, Fix ladder deep→glm.
- `--glm`: Worker=glm, Fix ladder glm→deep.
- `--codex` (sparing): Worker=codex (codex-headless-exec); Fix ladder codex→deep.
