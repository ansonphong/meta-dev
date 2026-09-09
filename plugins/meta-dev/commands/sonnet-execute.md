---
name: sonnet-execute
argument-hint: <task description> [--repo <name>] [--readonly] [--budget auto|low|medium|high] [--model <model>] [--effort <level>]  # --repo names from .meta-dev/repos.json
description: Execute a task via headless Anthropic Sonnet 5 Claude Code — spawns a SEPARATE Claude Code process off the main thread, so Anthropic-grade Sonnet judgment runs without consuming the conductor's context window. Sonnet 5 is 1M-context on the first-party API.
---

# /sonnet-execute — Anthropic Sonnet 5 Headless Execution

Spawn a headless Claude Code worker on the **real Anthropic backend**, pinned to **Sonnet 5**, to execute a task and report back. You stay on your current host for orchestration; Sonnet does the work in an **isolated process**.

Uses `scripts/claude-headless-exec --backend sonnet` under the hood.

**Harness:** this worker **is** Claude Code (ambient Anthropic login, model Sonnet 5). It can run meta-dev slash commands internally (`/meta-execute`, `/loop-gap`, …). Interactive Grok and Codex hosts **also** have this plugin (Grok skills/slash; Codex `$meta-dev:*`). A **headless** `/grok-execute` or `/codex-execute` worker is not Claude Code — brief those with a direct task, not "run `/loop-gap`". Host loading and routing: `references/work-ladder.md` and `references/adaptive-workflow.md`. It can implement, review, or diagnose a bounded task; UI work is not its exclusive role.

## Scope and routing

The headless process keeps working context separate from the conductor. Use Sonnet for a bounded task when its measured quality and cost fit. Do not assume the conductor's model or a particular frontend stack.

Backend eligibility, account quotas, and preferences come from the JSON cascade. Use `references/work-ladder.md` and `references/adaptive-workflow.md`; a provider name does not mandate another delegation layer.

The runner uses the ambient Claude login. Confirm model access, context capacity, and billing in the target environment; isolation is not a billing guarantee.

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

When the task runs tests, **focus-scope, always.** Run only the named test file/node. NEVER bare/directory pytest, `-k` without a file, package-wide npm/Vitest/Jest, `npm run check`, `svelte-check`, project-wide `tsc`, a build, or a full suite—not per task and not at phase end. Those belong to CI/ship or a separate explicit request. Reuse green evidence only while its relevant code and dependencies remain unchanged. Unrelated/unchanged `BASELINE_RED` never blocks optimistic momentum.

## Step 1: Parse Arguments

The user's input is: `$ARGUMENTS`

Parse these optional flags:
- `--repo <name>` — target repo (default: auto-detect from cwd; names from .meta-dev/repos.json)
- `--readonly` — expose only Read,Glob,Grep (no shell, writes, delegation, MCP, or skills)
- `--claim <plan-dir>` — **concurrency safety (shared tree):** claim this plan directory before dispatch. The wrapper ABORTS if another live session holds an overlapping scope, and auto-releases on exit. Use whenever the worker edits `plans/**`. (`--claim-warn` warns instead of aborting.) See `references/execute-charter.md` → Concurrency Safety.
- `--model <model>` — override default `claude-sonnet-5`; use an ID supported by the target host.
- `--budget auto|low|medium|high` — **depth cap** (default `auto`). Classify before dispatch. Doctrine: `references/execute-budget.md`.
- `--effort <level>` — thinking/reasoning effort: `low|medium|high|xhigh|max` (**default: `high`** — Anthropic's own Sonnet 5 default; drop to `medium`/`low` to conserve the Max Sonnet cap on bulk work)
- `--max-turns <n>` — cap agent turns (default: from `--budget`)

Everything else is the task description. If no task description is provided, ask the user what task to execute.

## Step 2: Confirm the Plan

Summarize what will be executed:
- **Backend:** Anthropic Sonnet — `claude-sonnet-5` (1M context, ambient login)
- **Effort:** high (or the `--effort` value)
- **Repo:** (detected or specified)
- **Task:** (the task description)
- **Mode:** read-only or read-write

If the task is destructive (deletes files, drops data, modifies prod), confirm with the user before proceeding.

## Step 3: Execute

Run the headless worker. Always background it — these jobs routinely take 30–180 minutes.

**BINDING — host tool timeout.** The runner owns the wall (`--budget`: low 30m / medium 90m / high 180m). A 5-second or 5-minute host bash/spawn timeout kills a healthy worker and wastes the tokens already spent.

- **Grok:** `background: true` **and** `timeout: 0` (disables wrapper kill). Never `timeout: 5000`, `120000`, or `300000`.
- **Claude Code:** `run_in_background: true`. Do not set a Bash timeout under 2 hours.
- Pass `--timeout` on the runner **only** if the user typed `--timeout` in `$ARGUMENTS`. Never copy the host tool timeout into `--timeout`.
- Waiting on the job: `timeout_ms` ≥ 1800000 (30 min) or poll until exit. `timeout_ms: 300000` is a 5-minute cut-off.

```bash
${PLUGIN_ROOT}/scripts/claude-headless-exec \
  --backend sonnet \
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

- Default tools: Read,Write,Edit,Bash,Grep,Glob. `--readonly` restricts to Read,Glob,Grep.
- For authorized edits, the worker commits only its scoped files; read-only work creates no commit. Red verification blocks completion and push, not local persistence.
- `--backend sonnet` uses the ambient Claude login; verify account access and limits before dispatch.
