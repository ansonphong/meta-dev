---
name: sonnet-execute
argument-hint: <task description> [--repo <name>] [--readonly] [--model <model>] [--effort <level>]  # --repo names from .claude/meta-dev-repos.json
description: Execute a task via headless Anthropic Sonnet Claude Code — spawns a SEPARATE Claude Code process pinned to the 200K Sonnet variant (NOT 1M), so it is never billed at the 1M rate the way a Sonnet subagent dispatched from an opus[1m] session would be.
---

# /sonnet-execute — Anthropic Sonnet (200K) Headless Execution

Spawn a headless Claude Code worker on the **real Anthropic backend**, pinned to the **standard 200K Sonnet** model, to execute a task and report back. You stay on your current backend (Opus) for orchestration; Sonnet does the work in an **isolated process**.

Uses `scripts/claude-headless-exec --backend sonnet` under the hood.

## Why this exists — the 1M billing trap

When the orchestrating session runs `opus[1m]`, the `[1m]` flag turns on the **1M context beta for the whole session**. A Sonnet **subagent** dispatched via the Agent/Task tool runs *inside* that session beta, so it goes out as **Sonnet-1M** and is billed at the premium long-context tier.

`/sonnet-execute` sidesteps that entirely: it launches a **fresh `claude -p` process** with `--model claude-sonnet-5` (**no `[1m]` suffix**) and a scrubbed env. No 1M beta is active → standard **200K** Sonnet pricing. Your Opus thread keeps running `opus[1m]` untouched.

**It authenticates via your ambient `~/.claude` login** — no API key, no third-party endpoint. Billing is against your normal Claude subscription/login, same as any local run, just at the 200K tier.

## When to Use

Reach for `/sonnet-execute` when you want **Anthropic-grade Sonnet judgment** off the main thread but **must not pay the 1M rate**:
- Frontend / Svelte work needing design consistency (where DeepSeek/GLM fall short)
- Stateful multi-file refactors that want Anthropic reasoning, not headless-backend quality
- Reviews/audits where you want a Sonnet lens but cheaply (`--readonly`)
- Any time you'd normally spawn a Sonnet subagent from an `opus[1m]` session — use this instead to avoid the 1M bill

For cheap bulk/mechanical work, still prefer `/deep-execute` (DeepSeek); for long-horizon agentic work prefer `/glm-execute` (GLM). `/sonnet-execute` is the **Anthropic-quality, 200K-priced** middle option.

## Test discipline — keep every test cycle cheap

When the task runs tests, **path-scope, always.** Run only the named test file — `pytest path/to/test_x.py -q` — never bare `pytest`, `pytest <dir>/`, or `-k <expr>` (they collect the whole tree first). NEVER `svelte-check`, `tsc --noEmit`, `npm run build`, or the full suite in an inner cycle. Confirm green once; don't re-run a passing test.

## Step 1: Parse Arguments

The user's input is: `$ARGUMENTS`

Parse these optional flags:
- `--repo <name>` — target repo (default: auto-detect from cwd; names from .claude/meta-dev-repos.json)
- `--readonly` — restrict to read-only tools (review/analysis tasks)
- `--model <model>` — override default model (default: `claude-sonnet-5` — the 200K variant; **do not add `[1m]`**)
- `--effort <level>` — thinking/reasoning effort: `low|medium|high|xhigh|max` (**default: `high`** — Anthropic's own Sonnet 5 default; drop to `medium`/`low` to conserve the Max Sonnet cap on bulk work)
- `--max-turns <n>` — cap agent turns (default: unset — worker runs to completion)

Everything else is the task description. If no task description is provided, ask the user what task to execute.

## Step 2: Confirm the Plan

Summarize what will be executed:
- **Backend:** Anthropic Sonnet — `claude-sonnet-5` (200K, ambient login)
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
- **No API key needed** — `--backend sonnet` uses your ambient `~/.claude` login; billed to your normal plan at the **200K** tier (never 1M).
