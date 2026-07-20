# Loop Protocol — execute → review → fix (phase-gated)

## Roles
- **Conductor** (main thread, Opus): dispatches, reads ONE verdict line per
  phase + each worker's one-line result. NEVER reads a diff, OUTPUT_FILE.raw,
  or the reviewer transcript.
- **Worker** — **unflagged = NATIVE TO THE HOST HARNESS** (the default): in
  Claude Code a native `Agent`/Task subagent, no external process spawn; in Codex
  native delegation via
  `codex exec -m gpt-5.3-codex-spark -c model_reasoning_effort=low --sandbox workspace-write '<bounded task>'`
  (Spark bills to a **separate weekly quota** from the gpt-5.6 family → cheapest
  tier available). Everything else is an **explicit opt-in** headless process:
  DeepSeek `--backend deep`, GLM `--backend glm`, or Anthropic Sonnet-200K
  `--backend sonnet` via ${CLAUDE_PLUGIN_ROOT}/scripts/claude-headless-exec;
  Codex `--codex` via ${CLAUDE_PLUGIN_ROOT}/scripts/codex-headless-exec (no
  --backend) — Codex is a first-class executor, not review-only.
  `--backend sonnet` is a SEPARATE `claude -p` process pinned to
  `claude-sonnet-5` (no `[1m]`). **The 1M caveat is conditional, not a blanket
  ban on native subagents:** ONLY when the conductor session is itself running
  the 1M beta (`opus[1m]`) does an Anthropic-model `Agent` subagent inherit that
  beta and bill at the 1M rate — in that case route Sonnet work through
  `--backend sonnet`, whose process carries no such beta → standard 200K tier.
  Nothing in the loop auto-detects the session tier, so confirm it before
  applying the caveat; on a non-1M session the native subagent has no 1M
  exposure and is the correct default worker.
  Output → OUTPUT_FILE; conductor reads only the distilled `result`.
- **Reviewer**: Agent subagent, agentType `meta-dev:review-agent` (Opus). Given
  {phase_spec, phase_pre_sha, phase_verify_cmds}, it computes its OWN
  `git diff <phase_pre_sha>..HEAD` and returns the verdict JSON below.
- **Fixer**: a headless worker fed the reviewer's `issues`.

## Per-task work (worker self-manages — no Opus per task)
1. At phase start record `PHASE_PRE_SHA=$(git rev-parse HEAD)`.
2. For EACH task in the phase: dispatch a FRESH worker (new headless process,
   clean context) with the task spec INCLUDING its `Verify:` command. The
   worker runs its own verify hook and self-fixes locally. If it changed any
   declared file, it stages those exact paths and creates a local commit before
   every return — green, red, BLOCKED, or exhausted. Red gates acceptance, not
   persistence. Conductor reads only the one-line `result`; only after green it
   pushes and flips that task via
   `bash ${CLAUDE_PLUGIN_ROOT}/scripts/task-done.sh <plan> <handle>` (shim over
   `planctl check` — the unified state layer's single write door) using the
   handle the conductor **already bound on the runtime task entry at dispatch**
   (not parsed from the worker). Worker never Edits a checkbox. Conductor
   commits the flipped plan file per task (momentum). No Opus review at this
   granularity. A red result keeps its local commit, leaves the handle open and
   the remote untouched, and enters the repair/failure path.

   **Self-commit is universal — never write a "don't commit" exemption into a
   worker spec.** Every executor in the ladder can commit; where one could not,
   that was our configuration and it was repaired in the executor (Codex's
   read-only `.git`, fixed by a `writable_roots` grant in `codex-headless-exec`,
   2026-07-20). If you believe a backend cannot commit, fix the executor or
   route the task elsewhere — do not encode it in prose. An uncommitted worker
   edit is unowned, and on this tree a peer's broad `git add` will adopt it.
   Correspondingly, a worker whose spec contradicts this must REPORT the
   conflict in its return rather than silently obeying the narrower instruction.

## Phase gate — the single Opus checkpoint per phase
Task commits/checks already accepted by their narrower per-task gates remain in
history and on the remote. This aggregate gate controls phase completion and
new fixer pushes; a FAIL never rewrites or unchecks earlier accepted tasks.

3. At phase end dispatch the Reviewer. Verdict JSON (review-agent's real shape):
   `{ "verdict": "PASS | CONDITIONAL_PASS | FAIL", "confidence": 0-1,
   "blast_radius": "isolated | file | module | cross-cutting | dependency-graph",
   "issues": [ {severity,file,line,title,description,suggested_fix} ],
   "summary": "..." }`.
4. Branch:
   - **PASS** → advance to next phase. Persist the verdict for the end-of-run
     DONE-gate — the `on-run-complete.sh` Stop hook stamps the plan DONE only
     when a pass is on record, so emit one per phase PASS:
     `NOW=$(date -u +%FT%TZ); bash ${CLAUDE_PLUGIN_ROOT}/scripts/planctl.sh review "$PLAN_REL" pass --by "conductor"`.
   - **CONDITIONAL_PASS** → apply the `suggested_fix`es via one Fixer on the
     active tier's primary backend (see Tier mapping). The fixer exact-path
     commits its scoped edits before returning on either result; advance only
     on green (no re-review needed for minor issues).
   - **FAIL** → Fix ladder (step 5).
5. **Fix ladder** (max 2 worker attempts, then surface) — backends per the
   **active tier** (see Tier mapping), never looping the same backend twice on
   the same failure:
   - Attempt 1: Fixer on the tier's **primary** backend fed `issues`; it locally
     commits scoped edits before return → re-Review (step 3).
   - Attempt 2 (still FAIL): Fixer on the tier's **escalation** backend; it
     locally commits scoped edits before return → re-Review.
   - Attempt 3 — **consult Fable before surfacing.** Two failures on the same
     thing is the definition of a hard challenge, and surfacing it costs the
     user a round-trip (a whole night, under `--autonomous`). Run
     `scripts/fable-consult.sh --question "<what is failing and why the two
     fixes did not work>" --plan <plan>` with the failure output in the packet.
     Exit `0` (≥0.90 with evidence + falsifier) → apply its recommendation as
     one final scoped fixer attempt, then re-Review. Any other exit → surface,
     carrying Fable's recommendation into the dossier. Never loop this rung.
   - Still FAIL → ensure the fixer's scoped edits are locally committed, write
     the failure dossier to the inbox (repair-loop convention), and surface the
     one-line `summary`. Leave ledger/phase state, remote, and advancement
     untouched; the red commits remain as durable repair evidence. Stop.

## Runbook dashboard sync — re-render the owning runbook at every phase gate (NON-NEGOTIABLE for runbook members)
The campaign-runbook `🎯 LIVE EXECUTION DASHBOARD` is a **pull-based** artifact —
it only reflects reality when `scripts/runbook-render.py` is actually run. On a
long-horizon execution the conductor advances checkboxes + the plan's `stage:`
but, unless this step fires, **nothing re-renders the dashboard**, so it freezes
mid-run and a later handoff silently overclaims. So: at **each phase gate, AFTER
the verdict resolves and the phase's work is committed** (same seam as the
context watchdog below), the conductor re-renders the owning runbook if the
plan-under-execution is a member of one:

```bash
# PLAN_REL = the executing plan's path relative to repo root (e.g.
#   plans/app/UNIFIED-EDITING-CANVAS/20-IMAGE-OFFSET/00-master-plan.md)
RB=$(grep -rlF --include='_runbook-*.md' "$PLAN_REL" plans/ 2>/dev/null | head -1)
if [ -n "$RB" ]; then
  python3 ${CLAUDE_PLUGIN_ROOT}/scripts/runbook-render.py "$RB"   # stderr prints ⚠ stage-drift
  git add "$RB" && git commit -q -m "chore(runbook): refresh dashboard — $(basename "$(dirname "$PLAN_REL")") phase landed"
fi
```

- The render is **idempotent** — if nothing changed it rewrites the same block
  and the commit is empty (skip it: `git diff --cached --quiet || git commit …`).
- It writes ONLY the sentineled PROGRESS block; the narrative + CURRENT phase
  tracker (human SHAs) are never touched.
- Heed its **stderr `⚠ stage-drift`** lines: a plan at ~100% checkboxes still
  parked below Stage 6 means *advance its `stage:`* (the plan really is done) or
  leave it (genuinely awaiting review/acceptance) — but NEVER let a handoff call
  it "done" while the dashboard shows it mid-stage. The render keeps the two honest.
- **Plan completion:** the `on-run-complete.sh` Stop hook stamps the member plan
  `stage:`→6 / status done and re-renders the runbook once execution is complete
  (all execution checkboxes flipped) AND a `review_verdict(pass)` is on record
  (emitted at each phase PASS above). The conductor no longer hand-bumps stage→6
  — the gate owns it deterministically (idempotent: re-stamping a done plan is a
  no-op).
- Single-phase plans (no `## Phase N`) have only the end seam → the render fires
  once at end-of-plan; still strictly better than never.

## Stalled worker — a halt is a PAUSE, never a silent pass
Every headless backend (`claude-headless-exec`, `codex-headless-exec`) runs a
**liveness watchdog**: if a worker's RAW event-stream goes silent for `STALL_SECS`
(default 5 min) it is killed and **auto-reset** up to `STALL_MAX_RESETS` (default 3).
If it stalls through the whole budget the script **HALTS with exit 125** and a
`[STALLED — … Run PAUSED for review]` result line. The conductor MUST treat that
as a **pause**, not a task pass and not a fix-ladder FAIL: do NOT advance the phase,
do NOT re-dispatch on the fix ladder (the worker was wedged, not wrong). Surface
the one-line STALLED notice + the partial `$RAW_FILE` path and STOP for the user.
A non-stall FAIL (exit ≠ 125, real verdict) still flows through the normal fix
ladder below.

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

## Scratchpad staging — unique paths, atomic writes, fail-loud (NON-NEGOTIABLE)
When the conductor stages an intermediate artifact for a worker (a review
prompt, a distilled diff, a phase log), it MUST NOT reuse a bare fixed name
(`review-prompt.txt`, `p3.log`) in the session scratchpad. Parallel lenses
(codex + grok + tests dispatched together) then race on that one name, a reader
sees a truncated/empty file, the wrapper reports the empty prompt, and the lens
is silently skipped. Rules:

1. **Unique per-run dir.** `RUN="$SCRATCH/run-$(date +%s)-$$"; mkdir -p "$RUN"`.
   Every staged file lives under `$RUN` with a role+lens-qualified name
   (`$RUN/codex-review.prompt`, `$RUN/grok-review.prompt`) — never a bare name.
2. **Atomic write.** Build to `.tmp`, then `mv`, so a concurrent reader never
   observes a half-written file: `build > "$f.tmp" && mv "$f.tmp" "$f"`.
3. **Verify before dispatch.** `[ -s "$f" ] || { echo "prompt build empty" >&2; exit 1; }`
   — never feed a file to a worker without proving it is non-empty first.
4. **Pass the prompt BY FILE, absolutely.** Prefer
   `codex-headless-exec --prompt-file "$f"` (codex/grok/claude runners accept it)
   over `-- "$(cat "$f")"`, and pass an ABSOLUTE path — a headless worker resolves
   "the scratchpad" to its OWN session dir, not the conductor's. The runners now
   hard-fail on an empty `--prompt-file`, so a mis-staged file surfaces LOUDLY
   instead of degrading to a silent usage error.

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
(Reviewer is ALWAYS the Opus `meta-dev:review-agent` — independent of tier.)
- **unflagged (the default): Worker=native to the host harness** — Claude Code
  native `Agent` subagent; Codex native `gpt-5.3-codex-spark` delegation
  (separate weekly quota). Fix ladder native→deep.
- `--deep`: Worker=deep, Fix ladder deep→glm.
- `--glm`: Worker=glm, Fix ladder glm→deep.
- **GLM concurrency cap (critical):** the Z.AI account allows only ~3 concurrent `glm-5.2` requests total, shared across every live GLM session (interactive + worker). The conductor MUST **serialize `--glm` workers — never dispatch two in parallel**; parallel GLM fan-out deterministically oversubscribes the ceiling and both workers 529-loop. Before each GLM dispatch, count active Z.AI-pointed procs (the pre-flight in `commands/glm-execute.md`); if the ceiling is saturated, queue rather than spawn. The beta-strip proxy retries `[1305]` for ~2 min, so a single serialized worker survives bursty contention — but serialization is what prevents the self-inflicted steady-state saturation that retry alone cannot out-wait.
- `--sonnet`: Worker=sonnet (Anthropic 200K via `--backend sonnet`), Fix ladder
  sonnet→glm. EVERY sonnet step — per-task execution AND the attempt-1 fixer —
  runs through `claude-headless-exec --backend sonnet` (a separate `claude -p`,
  200K, no `[1m]`); never an Anthropic-model `Agent` subagent **when the
  conductor session is running `opus[1m]`** — it would bill those at the 1M
  rate. Opus reviews the phase diff;
  attempt-2 escalation is a headless GLM worker (still no 1M exposure) before
  surfacing. Reach for `--sonnet` when you want Anthropic-grade Sonnet judgment
  off the main thread at the 200K price.
- `--codex`: a **first-class per-task execution worker** (via
  `codex-headless-exec`), Fix ladder codex→glm — and still the cross-family
  CODE-REVIEW lens at the phase gate (an alternative/additional GPT-vs-Claude
  reviewer over the phase diff). Both roles are live; pick one per dispatch.
