---
name: opus-execute
argument-hint: <task description> [--repo <name>] [--readonly] [--budget auto|low|medium|high] [--model <model>] [--effort <level>]  # --repo names from .claude/meta-dev-repos.json
description: Execute a task via headless Anthropic Opus 5 Claude Code — spawns a SEPARATE Claude Code process so top-tier Anthropic reasoning runs OFF the main thread and the conductor's context window stays lean. Opus 5 is 1M-context on the first-party API.
---

# /opus-execute — Anthropic Opus 5 Headless Execution

Spawn a headless Claude Code worker on the **real Anthropic backend**, pinned to **Opus 5**, to execute a task and report back. You stay on your current backend for orchestration; the worker does the hard reasoning in an **isolated process** — so the heaviest Opus-grade work happens without bloating the conductor's context window.

Uses `scripts/claude-headless-exec --backend opus` under the hood.

**Harness:** this worker **is** Claude Code (ambient Anthropic login, model Opus 5). It can run meta-dev slash commands internally (`/meta-execute`, `/loop-gap`, …). Interactive Grok and Codex hosts **also** have this plugin (Grok skills/slash; Codex `$meta-dev:*`). A **headless** `/grok-execute` or `/codex-execute` worker is not Claude Code — brief those with a direct task, not "run `/loop-gap`". Full split: `references/work-ladder.md` → *Who has meta-dev*. On this tree `/opus-execute` is **review-only** (harden / code-review, one pass, prefer `--readonly`). Brief it as a **review**, not a farm. The runner injects an Opus brief (`references/execute-briefs.md`).

## Why this exists — context economy

Two wins, one mechanism:

1. **Keep the conductor's context lean.** The worker runs in its own context window and returns only a distilled result — the main thread never absorbs the intermediate reasoning, files read, or tool churn. This is the delegation doctrine with Opus-grade judgment.

   > **No 200K/1M tradeoff to manage (verified 2026-07-25).** This command used to claim it pinned a "200K variant" to dodge a 1M premium. That is false on this model generation. Measured: `claude-opus-5`, `claude-opus-4-8`, `claude-sonnet-5` and `claude-fable-5` all report `contextWindow=1000000`, and `claude-opus-5[1m]` reports the same — the suffix is a **no-op** on first-party, so don't add it. Claude Code's docs confirm the plan side: *"On Max, Team, and Enterprise plans … Opus is automatically upgraded to 1M context with no additional configuration"*, and *"The 1M context window uses standard model pricing with no premium for tokens beyond 200K."* There is nothing to dodge.
   >
   > `[1m]` only matters on **Bedrock / Google Cloud / Microsoft Foundry**, where a model ID without it uses 200K. We run first-party via the ambient login.

2. **Top-tier Anthropic reasoning, off-thread.** Opus-grade judgment on a bounded task without spending the conductor's window on it.

**It authenticates via your ambient Claude login** — no API key, no third-party endpoint. Billing is against your normal Claude subscription/login, same as any local run.

## When to Use

Reach for `/opus-execute` when a task genuinely needs **top-tier Anthropic reasoning** (`[O]` tier — architecture, hardening, security review, deep multi-file design) but you want it **off the main thread** and **not billed at 1M**:
- Hard reasoning you'd normally keep on Opus, but that would otherwise flood the conductor's context (long file reads, wide exploration, multi-round diagnosis)
- Any time you'd spawn an Opus subagent from an `opus[1m]` session — use this instead to avoid the 1M bill
- Architecture / design / security passes where Sonnet's lens isn't enough but you don't want to burn the main window

For cheap bulk/mechanical work, prefer `/deep-execute` (DeepSeek); for long-horizon agentic work `/glm-execute` (GLM); for **Anthropic quality without needing Opus depth**, `/sonnet-execute`. `/opus-execute` is the **top-tier-Anthropic, 200K-priced, off-thread** option; for the very hardest reasoning + long-horizon coherence, `/fable-execute`.

## Test discipline — keep every test cycle cheap

When the task runs tests, **focus-scope, always.** Run only the named test file/node. NEVER bare/directory pytest, `-k` without a file, package-wide npm/Vitest/Jest, `npm run check`, `svelte-check`, project-wide `tsc`, a build, or a full suite—not per task and not at phase end. Those belong to CI/ship or a separate explicit request. One green is green; never rerun it. Unrelated/unchanged `BASELINE_RED` never blocks optimistic momentum.

## Step 1: Parse Arguments

The user's input is: `$ARGUMENTS`

Parse these optional flags:
- `--repo <name>` — target repo (default: auto-detect from cwd; names from .claude/meta-dev-repos.json)
- `--readonly` — restrict to read-only tools (review/analysis tasks)
- `--claim <plan-dir>` — **concurrency safety (shared tree):** claim this plan directory before dispatch. The wrapper ABORTS if another live session holds an overlapping scope, and auto-releases on exit. Use whenever the worker edits `plans/**`. (`--claim-warn` warns instead of aborting.) See `references/execute-charter.md` → Concurrency Safety.
- `--model <model>` — override default model (default: `claude-opus-5`; **do not add `[1m]`** — that opts the worker into the session-wide beta this command exists to avoid)
- `--budget auto|low|medium|high` — **depth cap** (default `auto`). On this tree Opus is review-only — pick `low` or `medium`, not `high`. Doctrine: `references/execute-budget.md`.
- `--effort <level>` — thinking/reasoning effort: `low|medium|high|xhigh|max` (**default: `high`**; drop to `medium`/`low` to conserve the Opus cap on lighter work)
- `--max-turns <n>` — cap agent turns (default: from `--budget`)

Everything else is the task description. If no task description is provided, ask the user what task to execute.

## Step 2: Confirm the Plan

Summarize what will be executed:
- **Backend:** Anthropic Opus — `claude-opus-5` (ambient login)
- **Effort:** high (or the `--effort` value)
- **Repo:** (detected or specified)
- **Task:** (the task description)
- **Mode:** read-only or read-write

If the task is destructive (deletes files, drops data, modifies prod), confirm with the user before proceeding.

## Step 3: Execute

Run the headless worker. For tasks expected to take >30 seconds, use `run_in_background: true` so the session stays responsive.

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/claude-headless-exec \
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
4. **Next steps** — changes are **not** auto-committed; remind the user to review and commit.

## Safety Notes

- Default tools: Read,Write,Edit,Bash,Grep,Glob. `--readonly` restricts to Read,Bash,Grep.
- The worker's changes are NOT automatically committed — remind the user to review and commit.
- **No API key needed** — `--backend opus` uses your ambient Claude login; billed to your normal plan at standard rates (1M carries no premium above 200K).
