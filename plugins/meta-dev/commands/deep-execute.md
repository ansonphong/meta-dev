---
name: deep-execute
argument-hint: <task description> [--repo <name>] [--readonly] [--flash] [--vision] [--tier <flash|pro|vision>] [--budget auto|low|medium|high] [--model <model>]  # --repo names from .meta-dev/repos.json
description: Execute a task via headless DeepSeek Claude Code — default deepseek-v4-pro (V4-Pro-0813 GA); --flash → flash; --vision → deepseek-v4-flash-vision-exp
---

# /deep-execute — DeepSeek Headless Execution

> Check `meta_dev.ladder.paused` in the merged settings before dispatch. A configured pause blocks this backend; the plugin ships no account-specific quota restriction.

Spawn a headless Claude Code worker on the **DeepSeek** backend to execute a task, then report the results back. The worker runs independently — you stay on your current backend for orchestration while DeepSeek does the work.

Uses `scripts/claude-headless-exec --backend deep` under the hood.

**Default model: `deepseek-v4-pro`** (DeepSeek-V4-Pro-0813, GA as of 2026-08-13). DeepSeek serves the latest Pro weights on that stable ID — do not pin a dated name. Flash (`deepseek-v4-flash`, Flash-0731) is the cheaper/faster bulk downgrade. **`--vision`** pins `deepseek-v4-flash-vision-exp` (experimental multimodal; JPEG/PNG/GIF/WebP). Pro and Flash **cannot** see images (HTTP 400). All three share a **1M** context window.

**The worker is a full Claude Code instance — it is not limited to code execution.** Its "task" can be any prompt (research, audit, summarize, refactor, investigate) **or an explicit meta-dev command to run internally** — `/meta-execute`, `/meta-planner`, `/loop-gap`, `/meta-eval`, `/sniff`, etc. Pair with `--readonly` for read-only ops (research/review/audit). This makes it a general worker for any waterfall stage, not just EXECUTE.

**Harness:** this worker **is** Claude Code, so Claude slash commands work inside it. Interactive Grok and Codex hosts **also** have meta-dev (Grok skills/slash; Codex `$meta-dev:*`). A **headless** `/grok-execute` or `/codex-execute` worker is not Claude Code — brief those with a direct task (Codex: `--skill`/`--command`), not "run `/loop-gap`". Host loading and routing: `references/work-ladder.md` and `references/adaptive-workflow.md`.

**Brief:** provide the assigned task or slice, named files, acceptance criteria, and focused verification. Do not create a nested swarm unless independently useful and authorized. See `references/execute-briefs.md` and `references/adaptive-workflow.md`.

## Pro vs Flash vs Vision — pick the tier

| | **Pro** (`deepseek-v4-pro`) — **default** | **Flash** (`deepseek-v4-flash`) | **Vision** (`deepseek-v4-flash-vision-exp`) |
|--|------------------------------------------|--------------------------------|--------------------------------------------|
| Size | 1.6T total / 49B active | 284B total / 13B active | Flash-class + image input (experimental) |
| Context | 1M | 1M | 1M |
| Images | No (HTTP 400) | No (HTTP 400) | JPEG, PNG, GIF, WebP |
| Role | Default reasoning + agent work | Mechanical bulk / low-reasoning | Screenshots, UI, charts, photos |
| Flag | default / `--pro` | `--flash` | `--vision` |

**Pro-first.** Unflagged `/deep-execute` is Pro. Force Flash with `--flash` (or `--tier flash`). Force Vision with `--vision` (or `--tier vision`). `--flash`, `--pro`, and `--vision` are exclusive. Nested Haiku/subagent slots on a Pro worker stay Flash; on a Vision worker they pin to Vision so a screenshot Read cannot 400.

**Conductor judgment (only when the user did not pass a tier flag):** default Pro. You MAY add `--flash` when the task is clearly mechanical and low-reasoning — a rename, a codemod, find-replace, boilerplate, or a single-file string edit with no design. You MAY add `--vision` when the task must look at images, screenshots, charts, or rendered UI — Pro and Flash will 400. If the work needs more than one reasoning step and is not visual, keep Pro. Unsure and not visual → Pro. Never Flash-downgrade architecture, review, multi-file design, auth, payment, schema, or render/pipeline work. A user `--flash` / `--vision` / `--tier` / `--model` is binding — do not override it.

Say the chosen model and why in the Step 2 confirm line, so a Flash or Vision switch is visible.

```bash
# default = Pro (V4-Pro-0813)
claude-headless-exec --backend deep --repo app -- "Hard multi-step agentic refactor"

# force Flash (mechanical)
claude-headless-exec --backend deep --flash --repo app -- "Rename getCwd across the project"

# force Vision (images)
claude-headless-exec --backend deep --vision --repo app -- "Describe src/ui/screenshot.png"
```

## Scope and routing

Use DeepSeek when selected by the user or configured backend pool and supported by current credentials. Start with bounded tasks. Model capability profiles and project measurements, not a fixed provider ranking, determine whether coherent slices are appropriate.

For a delegated phase, retain its explicit scope and per-task acceptance records. Read the master once for relevant dependencies; do not launch `/meta-execute` recursively merely because the assignment contains several checkboxes. Only invoke that procedure when the dispatcher explicitly requested orchestration. `planctl` is the only state writer.

See `references/work-ladder.md` and `references/adaptive-workflow.md` for routing, risk floors, ownership, and resource caps.

## Test discipline — keep every test cycle cheap

When the task runs tests, **focus-scope, always.** Run only the named test file/node. NEVER bare/directory pytest, `-k` without a file, package-wide npm/Vitest/Jest, `npm run check`, `svelte-check`, project-wide `tsc`, a build, or a full suite—not per task and not at phase end. Those belong to CI/ship or a separate explicit request. Reuse green evidence only while its relevant code and dependencies remain unchanged. Unrelated/unchanged `BASELINE_RED` never blocks optimistic momentum. (Canonical: `references/execute-charter.md` → Focused Verification Doctrine.)

## Step 1: Parse Arguments

The user's input is: `$ARGUMENTS`

Parse these optional flags:
- `--repo <name>` — target repo (default: auto-detect from cwd; names from .meta-dev/repos.json)
- `--readonly` — restrict to read-only tools (review/analysis tasks)
- `--claim <plan-dir>` — **concurrency safety (shared tree):** claim this plan directory before dispatch. The wrapper ABORTS if another live session holds an overlapping scope, and auto-releases on exit. Use whenever the worker edits `plans/**`. (`--claim-warn` warns instead of aborting.) See `references/execute-charter.md` → Concurrency Safety.
- `--flash` — force Flash (`deepseek-v4-flash`). Alias of `--tier flash`. Binding when the user passed it.
- `--pro` — force Pro (`deepseek-v4-pro`). Redundant with the default; use it to lock Pro against a Flash or Vision judgment.
- `--vision` — force Vision (`deepseek-v4-flash-vision-exp`). Alias of `--tier vision`. Binding. Use when the worker must Read images (JPEG/PNG/GIF/WebP). Exclusive vs `--flash` / `--pro`.
- `--tier <flash|pro|vision>` — DeepSeek model tier (default: **`pro`** → `deepseek-v4-pro`; `flash` → `deepseek-v4-flash`; `vision` → `deepseek-v4-flash-vision-exp`). `--flash`, `--pro`, and `--vision` are boolean sugars.
- `--model <model>` — exact model ID override (`deepseek-v4-pro`, `deepseek-v4-flash`, or `deepseek-v4-flash-vision-exp`); wins over `--tier` / `--flash` / `--vision`
- `--budget auto|low|medium|high` — depth cap (default `auto`). Classify the actual task; use focused bounds and configured capability policy. See `references/execute-budget.md`.
- `--max-turns <n>` — cap agent turns (default: from `--budget`)

Everything else is the task description.

If no task description is provided, ask the user what task to execute.

## Step 2: Confirm the Plan

Summarize what will be executed:
- **Backend:** DeepSeek (`deepseek-v4-pro` by default, or `--flash` / `--vision` / `--tier` / `--model` as specified). If you judged Flash or Vision, say why.
- **Repo:** (detected or specified)
- **Task:** (the task description)
- **Mode:** read-only or read-write

If the task is destructive (deletes files, drops data, modifies prod), confirm with the user before proceeding.

## Step 3: Execute

Run the headless worker. For tasks expected to take >30 seconds, use `run_in_background: true` so the session stays responsive.

```bash
# Build the command (default model = deepseek-v4-pro)
${PLUGIN_ROOT}/scripts/claude-headless-exec \
  --backend deep \
  --repo <repo> \
  ${FLASH:+--flash} \
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
- `--readonly` restricts to Read,Bash,Grep — use for audits/reviews
- For authorized edits, the worker commits only its scoped files; read-only work creates no commit.
- DeepSeek API key must be set (`DEEPSEEK_API_KEY` env var) — the script checks this
