---
name: deep-execute
argument-hint: <task description> [--repo <name>] [--readonly] [--flash] [--pro] [--vision] [--tier <flash|pro|vision>] [--budget auto|low|medium|high] [--model <model>]  # --repo names from .meta-dev/repos.json
description: Execute a task via headless DeepSeek Claude Code — default deepseek-v4-flash (V4.1 Flash as of 2026-09-10); --pro → pro; --vision → deepseek-v4-flash-vision-exp
---

# /deep-execute — DeepSeek Headless Execution

> Check `meta_dev.ladder.paused` in the merged settings before dispatch. A configured pause blocks this backend; the plugin ships no account-specific quota restriction.

Spawn a headless Claude Code worker on the **DeepSeek** backend to execute a task, then report the results back. The worker runs independently — you stay on your current backend for orchestration while DeepSeek does the work.

Uses `scripts/claude-headless-exec --backend deep` under the hood.

**Default model: `deepseek-v4-flash`** (DeepSeek-V4.1-Flash on this stable ID as of **2026-09-10**). DeepSeek serves the latest Flash weights on that ID — do not pin a dated preview name such as `deepseek-v4.1-flash-expires-on-0910`. Official testing showed V4.1 Flash surpassing V4 Pro on performance, cost, speed, and task completion time. **`--pro`** pins `deepseek-v4-pro` (until V4.1 Pro ships, DeepSeek routes Pro requests to V4.1 Flash and bills Flash prices). **`--vision`** pins `deepseek-v4-flash-vision-exp` (experimental multimodal; JPEG/PNG/GIF/WebP). Text Flash/Pro IDs still reject images (HTTP 400) unless/until official docs say otherwise. All three share a **1M** context window.

**The worker is a full Claude Code instance — it is not limited to code execution.** Its "task" can be any prompt (research, audit, summarize, refactor, investigate) **or an explicit meta-dev command to run internally** — `/meta-execute`, `/meta-planner`, `/loop-gap`, `/meta-eval`, `/sniff`, etc. Pair with `--readonly` for read-only ops (research/review/audit). This makes it a general worker for any waterfall stage, not just EXECUTE.

**Harness:** this worker **is** Claude Code, so Claude slash commands work inside it. Interactive Grok and Codex hosts **also** have meta-dev (Grok skills/slash; Codex `$meta-dev:*`). A **headless** `/grok-execute` or `/codex-execute` worker is not Claude Code — brief those with a direct task (Codex: `--skill`/`--command`), not "run `/loop-gap`". Host loading and routing: `references/work-ladder.md` and `references/adaptive-workflow.md`.

**Brief:** provide the assigned task or slice, named files, acceptance criteria, and focused verification. Do not create a nested swarm unless independently useful and authorized. See `references/execute-briefs.md` and `references/adaptive-workflow.md`.

## Flash vs Pro vs Vision — pick the tier

| | **Flash** (`deepseek-v4-flash`) — **default** | **Pro** (`deepseek-v4-pro`) | **Vision** (`deepseek-v4-flash-vision-exp`) |
|--|-----------------------------------------------|-----------------------------|--------------------------------------------|
| Size / role | V4.1 Flash (default primary; Pro-class quality at Flash price/speed) | Pro ID (upgrade; may route to V4.1 Flash until V4.1 Pro) | Flash-class + image input (experimental) |
| Context | 1M | 1M | 1M |
| Images | No (HTTP 400) | No (HTTP 400) | JPEG, PNG, GIF, WebP |
| Role | Default reasoning + agent + mechanical work | Explicit Pro-ID request | Screenshots, UI, charts, photos |
| Flag | default / `--flash` | `--pro` | `--vision` |

**Flash-first.** Unflagged `/deep-execute` is Flash (V4.1). Force Pro with `--pro` (or `--tier pro`). Force Vision with `--vision` (or `--tier vision`). `--flash`, `--pro`, and `--vision` are exclusive. Nested Haiku/subagent slots stay Flash; on a Vision worker they pin to Vision so a screenshot Read cannot 400.

**Conductor judgment (only when the user did not pass a tier flag):** default Flash. You MAY add `--pro` when the user asks for Pro explicitly, or when a future V4.1 Pro is the better fit and the Pro ID is no longer a Flash route. You MAY add `--vision` when the task must look at images, screenshots, charts, or rendered UI — text Flash/Pro will 400. Unsure and not visual → Flash. A user `--flash` / `--pro` / `--vision` / `--tier` / `--model` is binding — do not override it.

Say the chosen model and why in the Step 2 confirm line, so a Pro or Vision switch is visible.

```bash
# default = Flash (V4.1 Flash on deepseek-v4-flash)
claude-headless-exec --backend deep --repo app -- "Hard multi-step agentic refactor"

# force Pro ID
claude-headless-exec --backend deep --pro --repo app -- "Use the Pro model ID"

# force Vision (images)
claude-headless-exec --backend deep --vision --repo app -- "Describe src/ui/screenshot.png"
```

## Scope and routing

Use DeepSeek when selected by the user or configured backend pool and supported by current credentials. Start with bounded tasks. Model capability profiles and project measurements, not a fixed provider ranking, determine whether coherent slices are appropriate.

For a delegated phase, retain its explicit scope and per-task acceptance records. Read the master once for relevant dependencies; do not launch `/meta-execute` recursively merely because the assignment contains several checkboxes. Only invoke that procedure when the dispatcher explicitly requested orchestration. `planctl` is the only state writer.

See `references/work-ladder.md` and `references/adaptive-workflow.md` for routing, risk floors, ownership, and resource caps.

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
- `--flash` — force Flash (`deepseek-v4-flash`). Alias of `--tier flash`. Redundant with the default; use it to lock Flash against a Pro or Vision judgment.
- `--pro` — force Pro (`deepseek-v4-pro`). Alias of `--tier pro`. Binding when the user passed it.
- `--vision` — force Vision (`deepseek-v4-flash-vision-exp`). Alias of `--tier vision`. Binding. Use when the worker must Read images (JPEG/PNG/GIF/WebP). Exclusive vs `--flash` / `--pro`.
- `--tier <flash|pro|vision>` — DeepSeek model tier (default: **`flash`** → `deepseek-v4-flash`; `pro` → `deepseek-v4-pro`; `vision` → `deepseek-v4-flash-vision-exp`). `--flash`, `--pro`, and `--vision` are boolean sugars.
- `--model <model>` — exact model ID override (`deepseek-v4-flash`, `deepseek-v4-pro`, or `deepseek-v4-flash-vision-exp`); wins over `--tier` / `--flash` / `--pro` / `--vision`
- `--budget auto|low|medium|high` — depth cap (default `auto`). Classify the actual task; use focused bounds and configured capability policy. See `references/execute-budget.md`.
- `--max-turns <n>` — cap agent turns (default: from `--budget`)

Everything else is the task description.

If no task description is provided, ask the user what task to execute.

## Step 2: Confirm the Plan

Summarize what will be executed:
- **Backend:** DeepSeek (`deepseek-v4-flash` by default, or `--pro` / `--vision` / `--tier` / `--model` as specified). If you judged Pro or Vision, say why.
- **Repo:** (detected or specified)
- **Task:** (the task description)
- **Mode:** read-only or read-write

If the task is destructive (deletes files, drops data, modifies prod), confirm with the user before proceeding.

## Step 3: Execute

Run the headless worker. For tasks expected to take >30 seconds, use `run_in_background: true` so the session stays responsive.

```bash
# Build the command (default model = deepseek-v4-flash)
${PLUGIN_ROOT}/scripts/claude-headless-exec \
  --backend deep \
  --repo <repo> \
  ${FLASH:+--flash} \
  ${PRO:+--pro} \
  ${VISION:+--vision} \
  ${TIER:+--tier "$TIER"} \
  ${MODEL:+--model "$MODEL"} \
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
- DeepSeek API key must be set (`DEEPSEEK_API_KEY` env var) — the script checks this
