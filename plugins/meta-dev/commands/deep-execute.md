---
name: deep-execute
argument-hint: <task description> [--repo <name>] [--readonly] [--flash] [--pro] [--vision] [--tier <flash|pro|vision>] [--effort low|high|max] [--budget auto|low|medium|high] [--model <model>]  # --repo names from .meta-dev/repos.json
description: Execute a task via headless DeepSeek Claude Code — default deepseek-flash (V4.1 Flash 1017) with Max reasoning; --pro selects V4 Pro; Flash supports images
---

# /deep-execute — DeepSeek Headless Execution

> Check `meta_dev.ladder.paused` in the merged settings before dispatch. A configured pause blocks this backend; the plugin ships no account-specific quota restriction.

Spawn a headless Claude Code worker on the **DeepSeek** backend to execute a task, then report the results back. The worker runs independently — you stay on your current backend for orchestration while DeepSeek does the work.

Uses `scripts/claude-headless-exec --backend deep` under the hood.

**Default model: `deepseek-flash`; default reasoning: `max`.** The canonical API ID serves **DeepSeek-V4.1-Flash-1017** (verified 2026-10-30). It supports text and images with a **1M** context window. `--pro` selects the separate `deepseek-v4-pro` (V4 Pro 0813), which does not support vision. `--vision` remains a compatibility flag for the same multimodal Flash model. Legacy API IDs `deepseek-v4-flash` and `deepseek-v4-flash-vision-exp` are accepted by DeepSeek as aliases to Flash 1017; prefer `deepseek-flash` for new calls.

**Max is explicit, not the provider default.** The runner sets `CLAUDE_CODE_EFFORT_LEVEL=max` and `alwaysThinkingEnabled: true` in the worker settings, and removes inherited `MAX_THINKING_TOKENS` so a value of `0` cannot disable thinking. Explicit `--effort low|high|max` overrides the default. `--budget` bounds turns and wall time without lowering DeepSeek effort. DeepSeek's API default is **high**; `medium` and `xhigh` map to **high**, while `max` maps to **max**. Asking for “think harder” in the prompt does not configure effort.

**Evidence and limits.** [DeepSeek's Claude Code guide](https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code/) documents `CLAUDE_CODE_EFFORT_LEVEL=max`. The [Anthropic API guide](https://api-docs.deepseek.com/guides/anthropic_api/) supports `thinking: {"type": "enabled"}` and `output_config: {"effort": "max"}`; `thinking.budget_tokens` is ignored. See the [effort mapping](https://api-docs.deepseek.com/guides/thinking_mode/) and [current model IDs](https://api-docs.deepseek.com/quick_start/pricing/). The focused stub test checks the child environment/settings; only a captured outgoing request proves what an installed Claude Code version sends. Never label a stub check as a live API verification or promise answer quality.

[Artificial Analysis](https://artificialanalysis.ai/models/creators/deepseek) ranked Flash 1017 (Max) above Pro 0813 (Max) on 2026-10-30: Intelligence Index **32 vs 23**, roughly **175 vs 81 tokens/s**, and benchmark cost/task **$0.60 vs $1.77**. These are dated measurements, not a universal quality guarantee; recheck before making a new model recommendation.

**The worker is a full Claude Code instance — it is not limited to code execution.** Its "task" can be any prompt (research, audit, summarize, refactor, investigate) **or an explicit meta-dev command to run internally** — `/meta-execute`, `/meta-planner`, `/loop-gap`, `/meta-eval`, `/sniff`, etc. Pair with `--readonly` for read-only ops (research/review/audit). This makes it a general worker for any waterfall stage, not just EXECUTE.

**Harness:** this worker **is** Claude Code, so Claude slash commands work inside it. Interactive Grok and Codex hosts **also** have meta-dev (Grok skills/slash; Codex `$meta-dev:*`). A **headless** `/grok-execute` or `/codex-execute` worker is not Claude Code — brief those with a direct task (Codex: `--skill`/`--command`), not "run `/loop-gap`". Host loading and routing: `references/work-ladder.md` and `references/adaptive-workflow.md`.

**Brief:** provide the assigned task or slice, named files, acceptance criteria, and focused verification. Do not create a nested swarm unless independently useful and authorized. See `references/execute-briefs.md` and `references/adaptive-workflow.md`.

## Flash vs Pro — pick the model

| | **Flash** (`deepseek-flash`) — **default** | **Pro** (`deepseek-v4-pro`) |
|--|----------------------------------------|---------------------------|
| Version | V4.1 Flash 1017 | V4 Pro 0813 |
| Context | 1M | 1M |
| Images | JPEG, PNG, GIF, WebP | Not supported |
| Default effort | Max | Max |
| Flag | default / `--flash` / `--vision` | `--pro` |

**Flash-first. Conductor judgment:** use Flash for text and visual work. Use Pro when explicitly requested; do not assume its name means it outperforms the newer Flash. `--flash`, `--pro`, and `--vision` remain exclusive; `--tier flash|pro|vision` is equivalent. A user `--model` overrides tier selection, and an explicit `--effort` overrides Max. Nested worker slots default to multimodal Flash with the same process-wide effort setting.

Report the selected model **and effort** before dispatch. For example:

```bash
# default = Flash 1017 + Max reasoning
claude-headless-exec --backend deep --repo app -- "Hard multi-step agentic refactor"

# explicit Pro + Max reasoning
claude-headless-exec --backend deep --pro --repo app -- "Use the Pro model ID"

# explicit lower effort when requested
claude-headless-exec --backend deep --effort high --repo app -- "Bounded task"
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
- `--flash` — force `deepseek-flash`; alias of `--tier flash`.
- `--pro` — force `deepseek-v4-pro`; alias of `--tier pro`.
- `--vision` — compatibility alias of `--tier vision`, selecting the same multimodal `deepseek-flash`. No separate vision model is needed.
- `--tier <flash|pro|vision>` — default **flash**; `--model` takes precedence.
- `--model <model>` — exact API model ID override; forwarded unchanged. Prefer `deepseek-flash` or `deepseek-v4-pro`; DeepSeek also accepts the legacy Flash aliases above.
- `--effort <low|high|max>` — reasoning effort, default **max**. The shared runner also accepts `medium` / `xhigh`, but DeepSeek maps both to **high**. An explicit override is binding.
- `--budget auto|low|medium|high` — depth cap (default `auto`). Classify the actual task; use focused bounds and configured capability policy. See `references/execute-budget.md`.
- `--max-turns <n>` — cap agent turns (default: from `--budget`)

Everything else is the task description.

If no task description is provided, ask the user what task to execute.

## Step 2: Confirm the Plan

Summarize what will be executed:
- **Backend/model/effort:** DeepSeek (`deepseek-flash`, **max** by default); report explicit model/tier and effort overrides.
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
# Build the command (defaults: deepseek-flash + max effort)
${PLUGIN_ROOT}/scripts/claude-headless-exec \
  --backend deep \
  --repo <repo> \
  ${FLASH:+--flash} \
  ${PRO:+--pro} \
  ${VISION:+--vision} \
  ${TIER:+--tier "$TIER"} \
  ${MODEL:+--model "$MODEL"} \
  ${EFFORT:+--effort "$EFFORT"} \
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
