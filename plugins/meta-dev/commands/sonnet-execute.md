---
name: sonnet-execute
argument-hint: <task description> [--repo <name>] [--readonly] [--budget auto|low|medium|high] [--model <model>] [--effort <level>]  # --repo names from .claude/meta-dev-repos.json
description: Execute a task via headless Anthropic Sonnet 5 Claude Code — spawns a SEPARATE Claude Code process off the main thread, so Anthropic-grade Sonnet judgment runs without consuming the conductor's context window. Sonnet 5 is 1M-context on the first-party API.
---

# /sonnet-execute — Anthropic Sonnet 5 Headless Execution

Spawn a headless Claude Code worker on the **real Anthropic backend**, pinned to **Sonnet 5**, to execute a task and report back. You stay on your current backend (Opus) for orchestration; Sonnet does the work in an **isolated process**.

Uses `scripts/claude-headless-exec --backend sonnet` under the hood.

**Harness:** this worker **is** Claude Code (ambient Anthropic login, model Sonnet 5). It can run meta-dev slash commands internally (`/meta-execute`, `/loop-gap`, …). Interactive Grok and Codex hosts **also** have this plugin (Grok skills/slash; Codex `$meta-dev:*`). A **headless** `/grok-execute` or `/codex-execute` worker is not Claude Code — brief those with a direct task, not "run `/loop-gap`". Full split: `references/work-ladder.md` → *Who has meta-dev*. On this tree `/sonnet-execute` is **parked** unless Phong names it this turn.

## Why this exists — keep the conductor's context lean

When the orchestrating session runs `opus[1m]`, the `[1m]` flag turns on the **1M context beta for the whole session**. A Sonnet **subagent** dispatched via the Agent/Task tool runs *inside* that session beta, so it goes out as **Sonnet-1M** and is billed at the premium long-context tier.

`/sonnet-execute` launches a **fresh `claude -p` process** with `--model claude-sonnet-5` and a scrubbed env. Your Opus thread keeps running untouched, and — the actual point — the worker's reads, tool churn and intermediate reasoning never enter the conductor's context; only a distilled result comes back.

> **There is no 200K/1M tradeoff to manage here (verified 2026-07-25).** Claude Code's own docs: *"On the Anthropic API, Sonnet 5 always runs with the 1M context window. There is no 200K variant, no `[1m]` suffix to select, and no usage credits required on any plan."* Measured to confirm: `--model claude-sonnet-5` and `--model 'claude-sonnet-5[1m]'` both report `contextWindow=1000000`, so the suffix is a **no-op** on first-party — don't add it. 1M bills at standard rates with **no premium above 200K**. This command is about context hygiene and model-tier choice, not billing avoidance.
>
> The one place `[1m]` still matters: **Bedrock / Google Cloud / Microsoft Foundry**, where a model ID *without* `[1m]` uses 200K. We run first-party via the ambient login, so it does not apply.

**It authenticates via your ambient Claude login** — no API key, no third-party endpoint. Billing is against your normal Claude subscription/login, same as any local run.

## When to Use

Reach for `/sonnet-execute` when you want **Anthropic-grade Sonnet judgment** off the main thread:
- Frontend / Svelte work needing design consistency (where DeepSeek/GLM fall short)
- Stateful multi-file refactors that want Anthropic reasoning, not headless-backend quality
- Reviews/audits where you want a Sonnet lens but cheaply (`--readonly`)
- Any time you'd normally spawn a Sonnet subagent from an `opus[1m]` session — use this instead to avoid the 1M bill

For cheap bulk/mechanical work, still prefer `/deep-execute` (DeepSeek); for long-horizon agentic work prefer `/glm-execute` (GLM). `/sonnet-execute` is the **Anthropic-quality** middle option (Sonnet 5 is $3/$15 per MTok, and $2/$10 through 2026-08-31 under introductory pricing).

## Test discipline — keep every test cycle cheap

When the task runs tests, **focus-scope, always.** Run only the named test file/node. NEVER bare/directory pytest, `-k` without a file, package-wide npm/Vitest/Jest, `npm run check`, `svelte-check`, project-wide `tsc`, a build, or a full suite—not per task and not at phase end. Those belong to CI/ship or a separate explicit request. One green is green; never rerun it. Unrelated/unchanged `BASELINE_RED` never blocks optimistic momentum.

## Step 1: Parse Arguments

The user's input is: `$ARGUMENTS`

Parse these optional flags:
- `--repo <name>` — target repo (default: auto-detect from cwd; names from .claude/meta-dev-repos.json)
- `--readonly` — restrict to read-only tools (review/analysis tasks)
- `--claim <plan-dir>` — **concurrency safety (shared tree):** claim this plan directory before dispatch. The wrapper ABORTS if another live session holds an overlapping scope, and auto-releases on exit. Use whenever the worker edits `plans/**`. (`--claim-warn` warns instead of aborting.) See `references/execute-charter.md` → Concurrency Safety.
- `--model <model>` — override default model (default: `claude-sonnet-5`). **Don't add `[1m]`** — it is a no-op on first-party API, where Sonnet 5 is always 1M
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

Run the headless worker. For tasks expected to take >30 seconds, use `run_in_background: true` so the session stays responsive.

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/claude-headless-exec \
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
4. **Next steps** — changes are **not** auto-committed; remind the user to review and commit.

## Safety Notes

- Default tools: Read,Write,Edit,Bash,Grep,Glob. `--readonly` restricts to Read,Bash,Grep.
- The worker's changes are NOT automatically committed — remind the user to review and commit.
- **No API key needed** — `--backend sonnet` uses your ambient Claude login; billed to your normal plan at standard rates (1M carries no premium above 200K).
