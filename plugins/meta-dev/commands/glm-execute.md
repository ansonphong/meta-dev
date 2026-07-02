---
name: glm-execute
argument-hint: <task description> [--repo <name>] [--readonly] [--model <model>]  # --repo names from .claude/meta-dev-repos.json
description: Execute a task via headless GLM Claude Code — spawns a separate Claude Code instance on the GLM (Z.AI) backend, executes the task, and reports results
---

# /glm-execute — GLM Headless Execution

Spawn a headless Claude Code worker on the **GLM (Z.AI)** backend to execute a task, then report the results back. The worker runs independently — you stay on your current backend (Opus/DeepSeek) for orchestration while GLM handles the execution with its strong frontend/Svelte capabilities.

Uses `scripts/claude-headless-exec --backend glm` under the hood.

**The worker is a full Claude Code instance — it is not limited to code execution.** Its "task" can be any prompt (research, design draft, audit, refactor, investigate) **or an explicit meta-dev command to run internally** — `/meta-execute`, `/meta-planner`, `/loop-gap`, `/meta-eval`, `/sniff`, etc. Pair with `--readonly` for read-only ops (research/review/audit). This makes it a general worker for any waterfall stage, not just EXECUTE.

## When to Use

GLM is the **robust, consistent driver** — it holds a thread across many dependent steps where DeepSeek drifts. Make GLM the executor for any job that is **long-horizon, stateful, or frontend**, and let it farm small mechanical leaves to DeepSeek.

**Reach for GLM when:**
- **Long-horizon / multi-phase execution** — whole-plan `/meta-execute`, multi-file refactors, anything where step N depends on steps 1..N-1. GLM stays on-task; this is its core edge.
- **Frontend / Svelte / Flask** — GLM 5.2 excels at Svelte 5 runes and Flask template work and keeps design consistency across components.
- **Hardening / review where judgment matters** — in head-to-head it found the subtler gap in fewer turns.
- **Cross-backend verification** — have GLM review/verify work DeepSeek did (or vice versa).
- **High-effort reasoning** — `CLAUDE_CODE_EFFORT_LEVEL=high` is set automatically; 1M context + 50-min timeout handle large, deep tasks.

**Prefer DeepSeek instead when** the work is a *small, bounded, parallelizable* unit (mechanical edit, codemod, narrow single-file transform) and you want the cheapest throughput — fan those out via `/deep-execute`.

**Rule of thumb:** *keep it whole → GLM; break it small → DeepSeek.* GLM drives the arc; DeepSeek farms the leaves.

## Executing a phase/wave file (multi-phase meta-planner plans)

When `/auto-execute` (or the user) hands you **one phase/wave file** from a multi-phase meta-planner plan — e.g. `plans/<repo>/<plan-dir>/00-master-plan.md` — that **single phase file is your entire unit of work for the round**. This is GLM's sweet spot: a cohesive, stateful, multi-task phase held on one thread.

- **Run `/meta-execute <phase-file>` internally** (the command is available in the worker's harness). Do NOT freelance task-by-task — `/meta-execute` is the per-task executor (claim → dispatch → verify → commit → checkbox flip) and is what keeps you on-thread across the phase's `Task N.1 → N.2 → …` sequence.
- **Read `00-master-plan.md` first** for cross-phase context, then execute **ONLY the one phase you were given** — never touch other `phase-*.md` files. `/auto-execute` owns phase ordering and reviews each phase between rounds.
- **Follow the project test policy** — critical-breakage tests only; do not retrofit or over-test.
- **Report** which tasks landed (SHAs) + anything that blocked, so the conductor can review the phase diff and advance to the next phase.

**Empirical (2026-06-26, identical hardening-audit task):** GLM-5.2 — 9 turns · 178s, found a subtle runtime-binding gap. DeepSeek-V4-pro — 20 turns · 209s. GLM converged in ~½ the turns with sharper single-shot judgment — consistent with its long-horizon robustness.

## Test discipline — keep every test cycle cheap

When the task runs tests, **path-scope, always.** Run only the named test file — `pytest path/to/test_x.py -q` (add `-m "not slow and not gpu and not integration"` if the suite marks them). NEVER bare `pytest`, `pytest <dir>/`, or `pytest … -k <expr>` (they collect the whole tree first). NEVER `svelte-check`, `tsc --noEmit`, `npm run build`, or the full suite in an inner cycle — those run once at the end. Confirm green once; don't re-run a passing test. (Canonical: meta-dev `references/execute-charter.md` → Fast Test Doctrine.)

## Step 1: Parse Arguments

The user's input is: `$ARGUMENTS`

Parse these optional flags:
- `--repo <name>` — target repo (default: auto-detect from cwd; names from .claude/meta-dev-repos.json)
- `--readonly` — restrict to read-only tools (review/analysis tasks)
- `--model <model>` — override default model (default: `glm-5.2[1m]`; fast option: `glm-4.7-flashx`)
- `--max-turns <n>` — cap agent turns (default: unset — worker runs to completion)

Everything else is the task description.

If no task description is provided, ask the user what task to execute.

## Step 2: Confirm the Plan

Summarize what will be executed:
- **Backend:** GLM (`glm-5.2[1m]` or as specified)
- **Repo:** (detected or specified)
- **Task:** (the task description)
- **Mode:** read-only or read-write

If the task is destructive (deletes files, drops data, modifies prod), confirm with the user before proceeding.

## Step 3: Execute

Run the headless worker. For tasks expected to take >30 seconds, use `run_in_background: true` so the session stays responsive.

```bash
# Build the command
${CLAUDE_PLUGIN_ROOT}/scripts/claude-headless-exec \
  --backend glm \
  --repo <repo> \
  --model <model> \
  ${READONLY:+--readonly} \
  ${MAX_TURNS:+--max-turns "$MAX_TURNS"} \
  -- <task description>
```

**Repo detection:**
- If `--repo` is specified, use that
- Otherwise, check `pwd` — if we're inside a child repo, use that repo
- If ambiguous (in parent repo), ask which repo to target

**Background execution:** when a backgrounded task completes, read the output file and report.

## Step 4: Report Results

The script distills the worker's output for you — three files per run:
- **`OUTPUT_FILE`** (printed as `OUTPUT_FILE=<path>`) — a **clean, parseable JSON object**: `{is_error, subtype, num_turns, duration_ms, session_id, result}`. `result` is the worker's final message text. `json.load()` this directly.
- **`<OUTPUT_FILE>.raw`** — the full raw event transcript (only needed for deep debugging).
- **`<OUTPUT_FILE>.stderr`** — the worker's stderr (the harmless `claude.ai connectors` notice lands here, not in the result).

The script also prints the distilled `result` text to stdout between `RESULT` rules, so for a foreground run you can read it straight from the command output.

When execution completes:
1. **Read `OUTPUT_FILE`** (or the printed `RESULT` block) — it is already clean JSON; no array-parsing needed.
2. **Check `is_error`** (and the `Exit code`/`is_error` lines in the summary) — exit `3` = distill failed (inspect `.raw`), exit `4` = the worker reported `is_error:true`.
3. **Summarize** — what the worker did, files touched, any issues.
4. **Next steps** — if the worker left work incomplete, suggest what to do next; remind the user changes are **not** auto-committed.

## Safety Notes

- The headless worker runs with the tools specified (default: Read,Write,Edit,Bash,Grep,Glob)
- `--readonly` restricts to Read,Bash,Grep — use for audits/reviews
- The worker's changes are NOT automatically committed — remind the user to review and commit
- GLM API key must be set (`GLM_API_KEY` env var) — the script checks this
- GLM workers automatically get `CLAUDE_CODE_EFFORT_LEVEL=high` and `API_TIMEOUT_MS=7200000` (120 min)
