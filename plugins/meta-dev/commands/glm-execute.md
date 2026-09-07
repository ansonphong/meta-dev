---
name: glm-execute
argument-hint: <task description> [--repo <name>] [--readonly] [--budget auto|low|medium|high] [--model <model>]  # --repo names from .meta-dev/repos.json
description: Execute a task via headless GLM Claude Code — spawns a separate Claude Code instance on the GLM (Z.AI) backend, executes the task, and reports results
---

# /glm-execute — GLM Headless Execution

Spawn a headless Claude Code worker on the **GLM (Z.AI)** backend to execute a task, then report the results back. The worker runs independently — you stay on your current host for orchestration while GLM handles the assigned task.

Uses `scripts/claude-headless-exec --backend glm` under the hood.

**The worker is a full Claude Code instance — it is not limited to code execution.** Its "task" can be any prompt (research, design draft, audit, refactor, investigate) **or an explicit meta-dev command to run internally** — `/meta-execute`, `/meta-planner`, `/loop-gap`, `/meta-eval`, `/sniff`, etc. Pair with `--readonly` for read-only ops (research/review/audit). This makes it a general worker for any waterfall stage, not just EXECUTE.

**Harness:** this worker **is** Claude Code, so Claude slash commands work inside it. Interactive Grok and Codex hosts **also** have meta-dev (Grok skills/slash; Codex `$meta-dev:*`). A **headless** `/grok-execute` or `/codex-execute` worker is not Claude Code — brief those with a direct task (Codex: `--skill`/`--command`), not "run `/loop-gap`". Host loading and routing: `references/work-ladder.md` and `references/adaptive-workflow.md`.

## Scope and routing

Use GLM when selected by the user or configured backend pool and supported by current credentials. Do not assume a project stack or personal backend preference. Use measured task fit and `references/work-ladder.md` plus `references/adaptive-workflow.md`.

A worker may own its assigned bounded task or slice through focused verification. Keep per-task acceptance records and use `planctl` for state writes. A phase assignment does not authorize a recursive worker swarm; invoke `/meta-execute` internally only when orchestration was explicitly requested.

## Read-only evidence

`--readonly` overrides `--tools` in either argument order and exposes only
Read, Glob, and Grep. It disables shell commands, delegation, skill execution,
MCP integrations, and ambient customization sources; it does not use permission
bypass. Supply a scoped diff artifact and relevant files in the brief, because
this worker cannot run `git diff` or tests. If evidence requires commands, use
an authorized native reviewer with verified read-only tooling, or have the
caller produce the artifact. Missing evidence must be reported, not invented.
The launcher still writes its own result/log artifacts; the worker cannot edit
project files through its available tools.

## Test discipline — keep every test cycle cheap

When the task runs tests, **focus-scope, always.** Run only the named test file/node. NEVER bare/directory pytest, `-k` without a file, package-wide npm/Vitest/Jest, `npm run check`, `svelte-check`, project-wide `tsc`, a build, or a full suite—not per task and not at phase end. Those belong to CI/ship or a separate explicit request. Reuse green evidence only while its relevant code and dependencies remain unchanged. Unrelated/unchanged `BASELINE_RED` never blocks optimistic momentum. (Canonical: `references/execute-charter.md` → Focused Verification Doctrine.)

## Step 1: Parse Arguments

The user's input is: `$ARGUMENTS`

Parse these optional flags:
- `--repo <name>` — target repo (default: auto-detect from cwd; names from .meta-dev/repos.json)
- `--readonly` — expose only Read,Glob,Grep (no shell, writes, delegation, MCP, or skills)
- `--claim <plan-dir>` — **concurrency safety (shared tree):** claim this plan directory before dispatch. The wrapper ABORTS if another live session holds an overlapping scope, and auto-releases on exit. Use whenever the worker edits `plans/**`. (`--claim-warn` warns instead of aborting.) See `references/execute-charter.md` → Concurrency Safety.
- `--model <model>` — override default model (default: `glm-5.2`; haiku-tier: `glm-4.5`)
- `--budget auto|low|medium|high` — **depth cap** (default `auto`). Classify before dispatch. Doctrine: `references/execute-budget.md`.
- `--max-turns <n>` — cap agent turns (default: from `--budget`)

Everything else is the task description.

If no task description is provided, ask the user what task to execute.

## Step 2: Confirm the Plan

Summarize what will be executed:
- **Backend:** GLM (`glm-5.2` or as specified)
- **Repo:** (detected or specified)
- **Task:** (the task description)
- **Mode:** read-only or read-write

If the task is destructive (deletes files, drops data, modifies prod), confirm with the user before proceeding.

## Step 3: Execute

Run the headless worker. For tasks expected to take >30 seconds, use `run_in_background: true` so the session stays responsive.

**Concurrency preflight:** verify account and host capacity, then clamp the shared worker cap to available slots. If capacity is unknown, serialize this backend conservatively. Do not inspect other sessions' environment contents or assume a universal account quota. Queue work when no slot is available.

```bash
# Build the command
${PLUGIN_ROOT}/scripts/claude-headless-exec \
  --backend glm \
  --repo <repo> \
  --model <model> \
  ${READONLY:+--readonly} \
  --budget "$BUDGET" \
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
4. **Next steps** — report scoped commit SHAs, per-outcome verification, and unfinished work. Do not push from the worker.

## Safety Notes

- The headless worker runs with the tools specified (default: Read,Write,Edit,Bash,Grep,Glob)
- `--readonly` restricts to Read,Glob,Grep — use for audits/reviews
- For authorized edits, the worker commits only its scoped files; read-only work creates no commit.
- GLM API key must be set (`GLM_API_KEY` env var) — the script checks this
- GLM workers automatically get `CLAUDE_CODE_EFFORT_LEVEL=high` and `API_TIMEOUT_MS=7200000` (120 min)
