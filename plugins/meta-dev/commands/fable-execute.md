---
name: fable-execute
argument-hint: <task description> [--repo <name>] [--readonly] [--model <model>] [--effort <level>]  # --repo names from .claude/meta-dev-repos.json
description: Execute a task via headless Anthropic Fable 5 Claude Code — spawns a SEPARATE Claude Code process on the real Anthropic backend (ambient login), the top of the ambient ladder. Reach for it on the HARDEST, most-complex tasks that demand extreme reasoning and long-horizon coherence, run off the main thread.
---

# /fable-execute — Anthropic Fable 5 Headless Execution

Spawn a headless Claude Code worker on the **real Anthropic backend**, pinned to **Fable 5** (`claude-fable-5`), to execute a task and report back. You stay on your current backend for orchestration; Fable does the work in an **isolated process**. This is the **top of the ambient-Anthropic ladder** — the one to reach for when a task is genuinely the hardest kind: extreme reasoning depth and coherence held across a long horizon.

Uses `scripts/claude-headless-exec --backend fable` under the hood.

## Why this exists

Fable 5 is a **general ambient-Anthropic worker** with a specific edge: it's the tier you escalate to when even Opus-grade judgment is being stretched — the most complex reasoning and the longest coherence chains. `/fable-execute` puts that capability **off the main thread** (subagent-first: the conductor's context stays lean; only a distilled result comes back) via a **fresh `claude -p` process** with `--model claude-fable-5` (**no `[1m]` suffix**) and a scrubbed env — so it can't inherit the session's 1M beta and get billed at the premium long-context rate.

**It authenticates via your ambient `~/.claude` login** — no API key, no third-party endpoint. Billing is against your normal Claude subscription/login, same as any local run.

**Fable's other job — the escalation advisor.** Because it is the top of the ladder, Fable is also who the harness asks *before* it asks Phong. Any run about to stop on a judgment call routes through the `fable-consult` skill first (`scripts/fable-consult.sh`), which pins this same backend read-only at `--effort xhigh`, and adopts the answer only at ≥0.90 confidence backed by `file:line` evidence and a stated falsifier. That path is always on under `--autonomous`. If you are hand-dispatching a hard *decision* rather than a task, prefer `fable-consult` over `/fable-execute` — you get the veto list, the calibration caps, the consult caps, and the decision log for free.

## When to Use

Reach for `/fable-execute` when the task is **the hardest kind** and wants the strongest ambient-Anthropic reasoning, off the main thread:
- Extreme-complexity reasoning where you want more headroom than Opus — gnarly architecture, subtle system-wide coherence, the bug nothing else has cracked
- Long-horizon work that must stay **coherent** across many dependent steps (where DeepSeek drifts and you want maximum reasoning quality)
- Any hard task you'd otherwise keep on the main thread but that would flood the conductor's context — hand it to Fable and take back a distilled result

For cheap bulk/mechanical work, prefer `/deep-execute` (DeepSeek); for long-horizon agentic work `/glm-execute` (GLM); for Anthropic-quality at 200K price `/sonnet-execute`; for top-tier Opus off-thread `/opus-execute`. `/fable-execute` is the **hardest-task, maximum-reasoning** tier — use it deliberately, not for routine work.

## Test discipline — keep every test cycle cheap

When the task runs tests, **path-scope, always.** Run only the named test file — `pytest path/to/test_x.py -q` — never bare `pytest`, `pytest <dir>/`, or `-k <expr>` (they collect the whole tree first). NEVER `svelte-check`, `tsc --noEmit`, `npm run build`, or the full suite in an inner cycle. Confirm green once; don't re-run a passing test.

## Step 1: Parse Arguments

The user's input is: `$ARGUMENTS`

Parse these optional flags:
- `--repo <name>` — target repo (default: auto-detect from cwd; names from .claude/meta-dev-repos.json)
- `--readonly` — restrict to read-only tools (review/analysis tasks)
- `--claim <plan-dir>` — **concurrency safety (shared tree):** claim this plan directory before dispatch. The wrapper ABORTS if another live session holds an overlapping scope, and auto-releases on exit. Use whenever the worker edits `plans/**`. (`--claim-warn` warns instead of aborting.) See `references/execute-charter.md` → Concurrency Safety.
- `--model <model>` — override default model (default: `claude-fable-5`; **do not add `[1m]`**)
- `--effort <level>` — thinking/reasoning effort: `low|medium|high|xhigh|max` (**default: `high`** — the hardest-task tier thinks hard by default; raise to `xhigh`/`max` for the truly brutal problems)
- `--max-turns <n>` — cap agent turns (default: unset — worker runs to completion)

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
${CLAUDE_PLUGIN_ROOT}/scripts/claude-headless-exec \
  --backend fable \
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
- **No API key needed** — `--backend fable` uses your ambient `~/.claude` login; billed to your normal plan.
