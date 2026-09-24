---
name: opus-execute
argument-hint: <task description> [--repo <name>] [--readonly] [--budget auto|low|medium|high] [--model <model>] [--effort <level>]  # --repo names from .meta-dev/repos.json
description: Execute a task via headless Anthropic Opus Claude Code — spawns a SEPARATE Claude Code process so top-tier Anthropic reasoning runs OFF the main thread and the conductor's context window stays lean. Default model is claude-opus-5-5. An explicit --model is forwarded unchanged.
---

# /opus-execute — Anthropic Opus Headless Execution

Spawn a headless Claude Code worker on the **real Anthropic backend**, pinned to **`claude-opus-5-5`** when `--model` is omitted, to execute a task and report back. You stay on your current backend for orchestration; the worker does the hard reasoning in an **isolated process** — so the heaviest Opus-grade work happens without bloating the conductor's context window.

Uses `scripts/claude-headless-exec --backend opus` under the hood.

**Harness:** this worker **is** Claude Code (ambient Anthropic login, default model `claude-opus-5-5`). It can run meta-dev slash commands internally (`/meta-execute`, `/loop-gap`, …). Interactive Grok and Codex hosts **also** have this plugin (Grok skills/slash; Codex `$meta-dev:*`). A **headless** `/grok-execute` or `/codex-execute` worker is not Claude Code — brief those with a direct task, not "run `/loop-gap`". Host loading and routing: `references/work-ladder.md` and `references/adaptive-workflow.md`. It can perform implementation-through-verification or a read-only review; use the task's intent and resolved workflow depth. The runner injects an Opus brief (`references/execute-briefs.md`).

## Scope and routing

A separate process isolates the worker's context. Opus 4.8, Opus 5, and Opus 5.5 profiles can own bounded coherent slices through implementation and focused verification; they are not restricted to review or UI work. Read-only review creates no edits.

Backend eligibility, quotas, and preferences come from the JSON cascade. Resolve the actual executor and risk before selecting plan detail or delegation depth: `references/work-ladder.md` and `references/adaptive-workflow.md`.

The runner uses the ambient Claude login. Confirm access, supported model IDs, context capacity, and billing in the target environment; isolated processes are not a billing guarantee.

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
- `--model <model>` — override the default `claude-opus-5-5`. The value is forwarded unchanged. Any caller-supplied Opus id is accepted, including `claude-opus-5`, `claude-opus-4-8`, and ids outside that pair. It is not rewritten to `claude-opus-5-5`.
- `--budget auto|low|medium|high` — bounded work depth (default `auto`), classified by task scope and risk. See `references/execute-budget.md`.
- `--effort <level>` — thinking/reasoning effort: `low|medium|high|xhigh|max` (**default: `high`**; drop to `medium`/`low` to conserve the Opus cap on lighter work)
- `--max-turns <n>` — cap agent turns (default: from `--budget`)

Everything else is the task description. If no task description is provided, ask the user what task to execute.

### Chooser

Anthropic (22 Sept 2026): Claude Opus 5.5 (`claude-opus-5-5`) is for long-running agentic coding and knowledge work. Context is 1M tokens. Max output is 128k. Thinking stays on. Use one pass for extra-family review or hard work that needs an Anthropic agent. Do not use it for grep, inventory, or ordinary Codex or Grok execution.

When `--model` is omitted, the worker and the nested Opus/subagent pin are `claude-opus-5-5`, and the runner effort default is `high`. The effort menu is `low`, `medium`, `high`, `xhigh`, `max`. Drop to `medium` or `low` on a lighter review to conserve the cap. An explicit `--model` is forwarded unchanged, including `claude-opus-5`, `claude-opus-4-8`, and any other caller-supplied id such as `claude-opus-future`. It is not rewritten to `claude-opus-5-5` and not rejected for failing a closed list.

## Step 2: Confirm the Plan

Summarize what will be executed:
- **Backend:** Anthropic Opus — `claude-opus-5-5` when `--model` is omitted (ambient login). An explicit `--model` replaces that id.
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
  --backend opus \
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
- `--backend opus` uses the ambient Claude login; verify account access and limits before dispatch.
