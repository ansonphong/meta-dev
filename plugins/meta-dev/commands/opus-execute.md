---
name: opus-execute
argument-hint: <task description> [--repo <name>] [--readonly] [--model <model>] [--effort <level>]  # --repo names from .claude/meta-dev-repos.json
description: Execute a task via headless Anthropic Opus Claude Code — spawns a SEPARATE Claude Code process pinned to the 200K Opus variant (NOT 1M), so top-tier Anthropic reasoning runs OFF the main thread (keeps the conductor's context lean) and is never billed at the 1M rate an Opus subagent from an opus[1m] session would incur.
---

# /opus-execute — Anthropic Opus (200K) Headless Execution

Spawn a headless Claude Code worker on the **real Anthropic backend**, pinned to the **standard 200K Opus** model, to execute a task and report back. You stay on your current backend for orchestration; the worker does the hard reasoning in an **isolated process** — so the heaviest Opus-grade work happens without bloating the conductor's context window.

Uses `scripts/claude-headless-exec --backend opus` under the hood.

## Why this exists — the 1M billing trap + context economy

Two wins, one mechanism:

1. **Dodge the 1M bill.** When the orchestrating session runs `opus[1m]`, the `[1m]` flag turns on the **1M context beta for the whole session**. An Opus **subagent** dispatched via the Agent/Task tool runs *inside* that beta, so it goes out as **Opus-1M** and is billed at the premium long-context tier. `/opus-execute` launches a **fresh `claude -p` process** with `--model claude-opus-4-8` (**no `[1m]` suffix**) and a scrubbed env → no 1M beta → standard **200K** Opus pricing. Your main thread keeps running untouched.
2. **Keep the conductor lean.** The worker runs in its own context window and returns a distilled result — the main thread never absorbs the intermediate reasoning, files read, or tool churn. This is the subagent-first doctrine with Opus-grade judgment.

**It authenticates via your ambient `~/.claude` login** — no API key, no third-party endpoint. Billing is against your normal Claude subscription/login, same as any local run, just at the 200K tier.

## When to Use

Reach for `/opus-execute` when a task genuinely needs **top-tier Anthropic reasoning** (`[O]` tier — architecture, hardening, security review, deep multi-file design) but you want it **off the main thread** and **not billed at 1M**:
- Hard reasoning you'd normally keep on Opus, but that would otherwise flood the conductor's context (long file reads, wide exploration, multi-round diagnosis)
- Any time you'd spawn an Opus subagent from an `opus[1m]` session — use this instead to avoid the 1M bill
- Architecture / design / security passes where Sonnet's lens isn't enough but you don't want to burn the main window

For cheap bulk/mechanical work, prefer `/deep-execute` (DeepSeek); for long-horizon agentic work `/glm-execute` (GLM); for **Anthropic-quality at 200K price without needing Opus depth**, `/sonnet-execute`. `/opus-execute` is the **top-tier-Anthropic, 200K-priced, off-thread** option; for the very hardest reasoning + long-horizon coherence, `/fable-execute`.

## Test discipline — keep every test cycle cheap

When the task runs tests, **path-scope, always.** Run only the named test file — `pytest path/to/test_x.py -q` — never bare `pytest`, `pytest <dir>/`, or `-k <expr>` (they collect the whole tree first). NEVER `svelte-check`, `tsc --noEmit`, `npm run build`, or the full suite in an inner cycle. Confirm green once; don't re-run a passing test.

## Step 1: Parse Arguments

The user's input is: `$ARGUMENTS`

Parse these optional flags:
- `--repo <name>` — target repo (default: auto-detect from cwd; names from .claude/meta-dev-repos.json)
- `--readonly` — restrict to read-only tools (review/analysis tasks)
- `--claim <plan-dir>` — **concurrency safety (shared tree):** claim this plan directory before dispatch. The wrapper ABORTS if another live session holds an overlapping scope, and auto-releases on exit. Use whenever the worker edits `plans/**`. (`--claim-warn` warns instead of aborting.) See `references/execute-charter.md` → Concurrency Safety.
- `--model <model>` — override default model (default: `claude-opus-4-8` — the 200K variant; **do not add `[1m]`**)
- `--effort <level>` — thinking/reasoning effort: `low|medium|high|xhigh|max` (**default: `high`**; drop to `medium`/`low` to conserve the Opus cap on lighter work)
- `--max-turns <n>` — cap agent turns (default: unset — worker runs to completion)

Everything else is the task description. If no task description is provided, ask the user what task to execute.

## Step 2: Confirm the Plan

Summarize what will be executed:
- **Backend:** Anthropic Opus — `claude-opus-4-8` (200K, ambient login)
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
- **No API key needed** — `--backend opus` uses your ambient `~/.claude` login; billed to your normal plan at the **200K** tier (never 1M).
