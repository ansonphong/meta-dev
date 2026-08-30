---
name: antigravity-execute
argument-hint: "<task description> [--repo <name>] [--readonly] [--flash|--pro|--opus|--sonnet|--oss] [--model <id>] [--budget auto|low|medium|high] [--effort low|medium|high]  # --repo names from .claude/meta-dev-repos.json"
description: "Execute a task via headless Google Antigravity CLI (agy). NOT Claude Code and NOT the retired Gemini CLI. Default gemini-3.7-flash-high (1M context, native multimodal, Search grounding). --opus is Claude Opus 4.6 Thinking on Google quota. Named-only — never pooled. Brief a DIRECT task, never a Claude slash."
---

# /antigravity-execute — Antigravity Headless Execution

Spawn a headless **Google Antigravity** worker (`agy --print=… --output-format json`) and report the result back. You stay on this host as conductor.

Uses `scripts/agy-headless-exec`. Same `OUTPUT_FILE` contract as grok/codex/deep (`{is_error, subtype, num_turns, duration_ms, session_id, result, usage, backend, stop_reason}`). Plugs into `/auto-execute` and `/meta-execute --agy`.

Alias: `/agy-execute` (identical).

## Capabilities card

| | |
|--|--|
| **Harness** | Google Antigravity CLI (`agy` 1.1+). Same agent core as Antigravity 2.0. **Not** Claude Code. **Not** the retired `gemini` CLI. |
| **Default** | `gemini-3.7-flash-high` — **Gemini 3.7 Flash**, GA coding/agent workhorse. Pinned so the TUI's last model cannot leak. |
| **Gemini strengths** | **1M-token** whole-repo investigation; **native** image / video / audio (no `--vision` flag — Flash already sees); **Google Search grounding**; Flash-speed agent loop; `--pro` → Gemini 3.1 Pro for harder reasoning. |
| **Claude on Google's dime** | `--opus` → **Claude Opus 4.6 (Thinking)**; `--sonnet` → **Claude Sonnet 4.6**. Billed against **Antigravity / Google AI quota**, not Anthropic. Separate Claude+GPT bar from Gemini. **Not Claude Code** — no `/meta-execute` inside, Opus **4.6** not 4.8/5. Starter quota dies fast on Opus — do not farm it. |
| **Also** | `--oss` → GPT-OSS 120B (same Claude+GPT quota bar). |
| **Writes** | Yes (`--mode accept-edits --dangerously-skip-permissions`). `--readonly` → `--mode plan`. Commit-on-red. |
| **Pool** | **Parked / named-only.** Never auto-selected. Never added to `meta_dev.ladder.pool`. Dispatch only when Phong named `/antigravity-execute` / `--agy` this turn. |
| **Cannot** | Run Claude slash commands. Nested subagents (agy blocks child-spawns). Be a 4th interactive host. |

Reach for it when the **task** wants Gemini's 1M context, Search-grounded freshness, or native video/audio — or when Phong wants Google-quota Claude as a fourth-family lens. Do **not** reach for it as a Grok substitute. Do **not** auto-farm inner checkbox workers here.

## Harness — this worker is not Claude Code

meta-dev is on Claude Code, Codex, and Grok Build. **Antigravity does not load meta-dev.** Headless `agy` is Google's harness.

**Brief a DIRECT task.** Say *"Audit X and report findings"* — never *"run `/loop-gap`"*. Do not point it at a meta-dev `SKILL.md`. The runner injects an Antigravity brief (`references/execute-briefs.md`). Full split: `references/work-ladder.md` → *Who has meta-dev*.

## When to Use

**Reach for Antigravity when Phong named it, and the shape matches:**

- Whole-repo / monorepo investigation that wants **1M context**
- Native multimodal (screenshot **and** video/audio — DeepSeek Vision is images-only)
- Search-grounded "what is current" lookup while editing
- Extra-family review on Google's Claude Opus 4.6 bar (`--opus --readonly`) — one pass, not a swarm

**Prefer the pool instead:** mechanical/collect → Spark/Luna or grok-4.5; multi-file implement → Grok `spawn_subagent` / `/grok-execute` or Codex Terra. Antigravity is the Google lens, **named-only**, not the daily executor. DeepSeek is paused.

## Test discipline — keep every test cycle cheap

When the task runs tests, **focus-scope, always.** Run only the named test file/node. NEVER bare/directory pytest, `-k` without a file, package-wide npm/Vitest/Jest, `npm run check`, `svelte-check`, project-wide `tsc`, a build, or a full suite—not per task and not at phase end. Those belong to CI/ship or a separate explicit request. One green is green; never rerun it. Unrelated/unchanged `BASELINE_RED` never blocks optimistic momentum. (Antigravity cannot rely on reading the charter internally, so this clause IS the rule for agy runs.)

## Step 1: Parse Arguments

The user's input is: `$ARGUMENTS`

Parse these optional flags:
- `--repo <name>` — target repo (default: auto-detect; names from `.claude/meta-dev-repos.json`)
- `--readonly` — plan mode, no writes (audits/reviews)
- `--flash` — Gemini 3.7 Flash (default)
- `--pro` — Gemini 3.1 Pro
- `--opus` — Claude Opus 4.6 Thinking (Google quota)
- `--sonnet` — Claude Sonnet 4.6 (Google quota)
- `--oss` — GPT-OSS 120B
- `--model <id>` — explicit `agy models` id (wins over tier flags)
- `--budget auto|low|medium|high` — **depth cap** (default `auto`). Classify before dispatch. Doctrine: `references/execute-budget.md`.
- `--effort low|medium|high` — reasoning effort (agy has no `xhigh`; runner maps it to `high`)
- `--timeout <ms>` — wall-clock (default: from `--budget`)

`--flash`, `--pro`, `--opus`, `--sonnet`, and `--oss` are exclusive. Everything else is the task description. If none is given, ask what task to run.

## Step 2: Select Model

**Default model is `gemini-3.7-flash-high`.** Always pass it. An unpinned worker inherits the TUI last-used model (often Opus 4.6) and burns the Claude bar.

| Task shape | Flag | Model |
| --- | --- | --- |
| Default coding/agent, 1M-context grep, multimodal, Search | (none) / `--flash` | `gemini-3.7-flash-high` |
| Harder Gemini reasoning | `--pro` | `gemini-3.1-pro-high` |
| Google-quota Claude, extra-family review | `--opus` | `claude-opus-4-6-thinking` |
| Cheaper Google-quota Claude | `--sonnet` | `claude-sonnet-4-6` |
| Open-weights GPT on Google quota | `--oss` | `gpt-oss-120b-medium` |

A user `--model` / tier flag is binding. Unsure → Flash, never Opus.

## Step 3: Confirm the Plan

Summarize before running:
- **Backend:** Antigravity (`agy --output-format json`)
- **Model:** gemini-3.7-flash-high (or the override)
- **Budget:** resolved `low|medium|high`
- **Repo / Work dir**
- **Task**
- **Mode:** read-only (plan) or execute

If the task is destructive or writes outside the repo, confirm first. For review/audit, **default to `--readonly`**.

## Step 4: Execute

For tasks expected to take >30s, use `run_in_background: true`.

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/agy-headless-exec \
  ${REPO:+--repo "$REPO"} \
  ${MODEL:+--model "$MODEL"} \
  ${FLASH:+--flash} ${PRO:+--pro} ${OPUS:+--opus} ${SONNET:+--sonnet} ${OSS:+--oss} \
  --budget "$BUDGET" \
  ${EFFORT:+--effort "$EFFORT"} \
  ${READONLY:+--readonly} \
  ${TIMEOUT:+--timeout "$TIMEOUT"} \
  -- <task description>
```

**Repo detection:** `--repo` wins; else infer from `pwd`; if ambiguous, ask.

`agy --print` consumes the next argv — the runner attaches `--print=…` so `--output-format` cannot be stolen. JSON is one object at completion; a long run looks silent until it returns.

## Step 5: Report Results

Three files per run:
- **`OUTPUT_FILE`** — clean JSON. `json.load()` it. `backend` is `agy`.
- **`<OUTPUT_FILE>.raw`** — full agy JSON.
- **`<OUTPUT_FILE>.stderr`** — worker stderr.

When execution completes:
1. Read `OUTPUT_FILE` / the printed `RESULT` block.
2. Check `is_error` and exit code — `3` = distill failed, `4` = worker error, `124` = timed out.
3. Summarize what it found/did, files touched, quota surprises.
4. Execute workers **must have committed** (commit-on-red). Dirty return is an executor bug.

## Safety Notes

- `agy` must be on PATH (or `~/.local/bin/agy`) and authenticated (Google account / Antigravity Starter, or `GEMINI_API_KEY` + `modelProvider: gemini` in `~/.gemini/antigravity-cli/settings.json`).
- `--readonly` is `--mode plan`. Do not pair it with `--disable-slash-commands` (that voids plan mode).
- Execute mode uses `--dangerously-skip-permissions`. The worker **must** `git -C <ABS> add -- <paths> && git -C <ABS> commit --only -m "…" -- <paths>` before returning. Never push.
- Uncommitted agy edits are a **bug**. Do not write "the conductor commits" into an Antigravity brief.
- **Quota is the constraint** — Starter is weekly and small. Gemini Flash is the spendable default. Opus/Sonnet share a **separate** Claude+GPT bar that dies in minutes on agent work. Do not swarm `--opus`.
