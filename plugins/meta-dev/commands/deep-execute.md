---
name: deep-execute
argument-hint: <task description> [--repo <name>] [--readonly] [--model <model>]  # --repo names from .claude/meta-dev-repos.json
description: Execute a task via headless DeepSeek Claude Code — spawns a separate Claude Code instance on the DeepSeek backend, executes the task, and reports results
---

# /deep-execute — DeepSeek Headless Execution

Spawn a headless Claude Code worker on the **DeepSeek** backend to execute a task, then report the results back. The worker runs independently — you stay on your current backend (Opus/GLM) for orchestration while DeepSeek does the cheap bulk execution.

Uses `scripts/claude-headless-exec --backend deep` under the hood.

**The worker is a full Claude Code instance — it is not limited to code execution.** Its "task" can be any prompt (research, audit, summarize, refactor, investigate) **or an explicit meta-dev command to run internally** — `/meta-execute`, `/meta-planner`, `/loop-gap`, `/meta-eval`, `/sniff`, etc. Pair with `--readonly` for read-only ops (research/review/audit). This makes it a general worker for any waterfall stage, not just EXECUTE.

## When to Use

DeepSeek is the **cheap, scalable workhorse** — strongest when the task is **short, bounded, and self-contained**. It does excellent thorough work on a single well-scoped unit (in head-to-head it produced a more exhaustive live-code verification table than GLM), but it **loses the plot on long-horizon work** — across many dependent steps it drifts off-thread. Keep each DeepSeek unit small and route the long arc to GLM.

**Reach for DeepSeek when:**
- **Bulk / mechanical execution** — cheapest exec model; farm out renames, mechanical edits, codemods, boilerplate
- **Wide parallel fan-out** — many *disjoint, small* units across files/repos, each handed off complete; DeepSeek scales horizontally where GLM would be overkill
- **Bounded single-file transforms** — one file, one clear deliverable, verify hook attached
- **Thorough audit of a narrow target** — a single function/file/contract where depth-on-one-thing matters more than holding a long thread
- **Review-then-execute** — you (Opus/GLM) plan, DeepSeek does the grunt edits

**Don't use DeepSeek for** (route to GLM instead):
- Long-horizon, multi-phase plan execution (`/meta-execute` on a big plan) — it drifts
- Tasks where step N depends on correctly carrying context from steps 1..N-1
- Frontend/Svelte work needing design consistency across many components

**Rule of thumb:** *break it small → DeepSeek; keep it whole → GLM.* For a big job, let GLM drive and farm the mechanical leaves to DeepSeek.

## Executing a phase/wave file (multi-phase meta-planner plans)

When `/auto-execute` (or the user) hands you **one phase/wave file** from a multi-phase meta-planner plan — e.g. `plans/<repo>/<plan-dir>/00-master-plan.md` — that **single phase file is your entire unit of work for the round**:

- **Follow the phase loop end-to-end.** Do NOT freelance task-by-task — the loop (claim → dispatch → verify → commit) is what keeps you on-thread across the phase's `Task N.1 → N.2 → …` sequence. The conductor owns the checkbox flip; you never edit one.
  - *Claude Code worker:* run `/meta-execute <phase-file>` internally.
  - *Any other harness:* read `skills/agentic-exec-loop/references/loop-protocol.md` and execute it directly — it is the same procedure, and it is the portable form. Name the SKILL, not the slash command: slash commands are Claude-Code-only, skills are not.
- **Read `00-master-plan.md` first** for cross-phase context, then execute **ONLY the one phase you were given** — never touch other `phase-*.md` files. `/auto-execute` owns phase ordering and reviews each phase between rounds.
- **Follow the project test policy** — critical-breakage tests only; do not retrofit or over-test.
- **Report** which tasks landed (SHAs) + anything that blocked, so the conductor can review the phase diff and advance to the next phase.

⚠️ A full phase is multi-task and **stateful** (Task N.2 depends on N.1) — that's the edge of DeepSeek's comfort zone (drift risk on long phases). DeepSeek is a good fit for a **short phase of small, disjoint tasks**; long/stateful phases should route to GLM. `/auto-execute` makes that call.

**Empirical (2026-06-26, identical hardening-audit task):** DeepSeek-V4-pro — 20 turns · 209s, very thorough verification table, found a real gap. GLM-5.2 — 9 turns · 178s, found a different (subtler) gap. DeepSeek burned ~2× the turns for comparable single-shot quality → its edge is *throughput when fanned out*, not solo long-horizon reasoning.

## Test discipline — keep every test cycle cheap

When the task runs tests, **focus-scope, always.** Run only the named test file/node. NEVER bare/directory pytest, `-k` without a file, package-wide npm/Vitest/Jest, `npm run check`, `svelte-check`, project-wide `tsc`, a build, or a full suite—not per task and not at phase end. Those belong to CI/ship or a separate explicit request. One green is green; never rerun it. Unrelated/unchanged `BASELINE_RED` never blocks optimistic momentum. (Canonical: `references/execute-charter.md` → Focused Verification Doctrine.)

## Step 1: Parse Arguments

The user's input is: `$ARGUMENTS`

Parse these optional flags:
- `--repo <name>` — target repo (default: auto-detect from cwd; names from .claude/meta-dev-repos.json)
- `--readonly` — restrict to read-only tools (review/analysis tasks)
- `--claim <plan-dir>` — **concurrency safety (shared tree):** claim this plan directory before dispatch. The wrapper ABORTS if another live session holds an overlapping scope, and auto-releases on exit. Use whenever the worker edits `plans/**`. (`--claim-warn` warns instead of aborting.) See `references/execute-charter.md` → Concurrency Safety.
- `--model <model>` — override default model (default: `deepseek-v4-pro`; fast option: `deepseek-v4-flash`)
- `--max-turns <n>` — cap agent turns (default: unset — worker runs to completion)

Everything else is the task description.

If no task description is provided, ask the user what task to execute.

## Step 2: Confirm the Plan

Summarize what will be executed:
- **Backend:** DeepSeek (`deepseek-v4-pro` or as specified)
- **Repo:** (detected or specified)
- **Task:** (the task description)
- **Mode:** read-only or read-write

If the task is destructive (deletes files, drops data, modifies prod), confirm with the user before proceeding.

## Step 3: Execute

Run the headless worker. For tasks expected to take >30 seconds, use `run_in_background: true` so the session stays responsive.

```bash
# Build the command
${CLAUDE_PLUGIN_ROOT}/scripts/claude-headless-exec \
  --backend deep \
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
- DeepSeek API key must be set (`DEEPSEEK_API_KEY` env var) — the script checks this
