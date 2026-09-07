---
name: fable-execute
argument-hint: <task description> [--repo <name>] [--readonly] [--budget auto|low|medium|high] [--model <model>] [--effort <level>]  # --repo names from .meta-dev/repos.json
description: Execute an explicitly authorized bounded task via headless Anthropic Fable 5 Claude Code using the ambient login and configured workflow policy.
---

# /fable-execute — Anthropic Fable 5 Headless Execution

Spawn a headless Claude Code worker on the Anthropic backend, pinned to **Fable 5** (`claude-fable-5`), to execute a bounded task and report back. You stay on the current host for orchestration; the worker uses an isolated process.

Uses `scripts/claude-headless-exec --backend fable` under the hood.

**Harness:** this worker **is** Claude Code (ambient Anthropic login, model Fable 5). It can run meta-dev slash commands internally (`/meta-execute`, `/loop-gap`, …). Interactive Grok and Codex hosts **also** have this plugin (Grok skills/slash; Codex `$meta-dev:*`). A **headless** `/grok-execute` or `/codex-execute` worker is not Claude Code — brief those with a direct task, not "run `/loop-gap`". Host loading and routing: `references/work-ladder.md` and `references/adaptive-workflow.md`. This optional backend requires explicit user authorization; configured pauses still apply.

## Scope and routing

Use this optional backend for an explicitly authorized bounded task. Backend rankings, account limits, and escalation preferences belong in configuration; do not infer a mandatory Fable consultation before asking the user.

A separate process isolates context, not cost. Confirm model access and account limits in the target environment. See `references/work-ladder.md` and `references/adaptive-workflow.md` for capability policy, bounded ownership, and review depth.

## Test discipline — keep every test cycle cheap

When the task runs tests, **focus-scope, always.** Run only the named test file/node. NEVER bare/directory pytest, `-k` without a file, package-wide npm/Vitest/Jest, `npm run check`, `svelte-check`, project-wide `tsc`, a build, or a full suite—not per task and not at phase end. Those belong to CI/ship or a separate explicit request. Reuse green evidence only while its relevant code and dependencies remain unchanged. Unrelated/unchanged `BASELINE_RED` never blocks optimistic momentum.

## Step 1: Parse Arguments

The user's input is: `$ARGUMENTS`

Parse these optional flags:
- `--repo <name>` — target repo (default: auto-detect from cwd; names from .meta-dev/repos.json)
- `--readonly` — restrict to read-only tools (review/analysis tasks)
- `--claim <plan-dir>` — **concurrency safety (shared tree):** claim this plan directory before dispatch. The wrapper ABORTS if another live session holds an overlapping scope, and auto-releases on exit. Use whenever the worker edits `plans/**`. (`--claim-warn` warns instead of aborting.) See `references/execute-charter.md` → Concurrency Safety.
- `--model <model>` — override default model (default: `claude-fable-5`; **do not add `[1m]`**)
- `--budget auto|low|medium|high` — depth cap (default `auto`). Classify task scope and risk; explicit backend selection alone does not warrant maximum depth. See `references/execute-budget.md`.
- `--effort <level>` — thinking/reasoning effort: `low|medium|high|xhigh|max` (**default: `high`** — the hardest-task tier thinks hard by default; raise to `xhigh`/`max` for the truly brutal problems)
- `--max-turns <n>` — cap agent turns (default: from `--budget`)

Everything else is the task description. If no task description is provided, ask the user what task to execute.

## Step 2: Confirm the Plan

Summarize what will be executed:
- **Backend:** Anthropic Fable 5 — `claude-fable-5` (ambient login)
- **Effort:** high (or the `--effort` value)
- **Repo:** (detected or specified)
- **Task:** (the task description)
- **Mode:** read-only or read-write

If the task is destructive (deletes files, drops data, modifies prod), confirm with the user before proceeding.

## Step 3: Execute

Run the headless worker. For tasks expected to take >30 seconds, use `run_in_background: true` so the session stays responsive.

```bash
${PLUGIN_ROOT}/scripts/claude-headless-exec \
  --backend fable \
  --repo <repo> \
  ${MODEL:+--model "$MODEL"} \
  --budget "$BUDGET" \
  ${EFFORT:+--effort "$EFFORT"} \
  ${READONLY:+--readonly} \
  ${MAX_TURNS:+--max-turns "$MAX_TURNS"} \
  -- <task description>
```

**Repo detection:** if `--repo` is given, use it; otherwise check `pwd` — if inside a child repo, use that; if ambiguous (in parent), ask which repo to target.

**Background execution:** when a backgrounded task completes, read the output file and report.

## Step 4: Report Results

The script distills the worker's output — three files per run:
- **`OUTPUT_FILE`** (printed as `OUTPUT_FILE=<path>`) — clean JSON: `{is_error, subtype, num_turns, duration_ms, session_id, result}`. `json.load()` it directly.
- **`<OUTPUT_FILE>.raw`** — full raw event transcript (deep debugging only).
- **`<OUTPUT_FILE>.stderr`** — worker stderr.

The script also prints the distilled `result` between `RESULT` rules.

When execution completes:
1. **Read `OUTPUT_FILE`** (or the printed `RESULT` block) — already clean JSON.
2. **Check `is_error`** — exit `3` = distill failed (inspect `.raw`), exit `4` = worker reported `is_error:true`.
3. **Summarize** — what the worker did, files touched, any issues.
4. **Next steps** — report scoped commit SHAs and per-outcome verification, plus any unfinished work. Do not push from the worker.

## Safety Notes

- Default tools: Read,Write,Edit,Bash,Grep,Glob. `--readonly` restricts to Read,Bash,Grep.
- For authorized edits, the worker commits only its scoped files; read-only work creates no commit. Red verification blocks completion and push, not local persistence.
- **No API key needed** — `--backend fable` uses your ambient Claude login; billed to your normal plan.
