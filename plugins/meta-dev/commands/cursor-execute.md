---
name: cursor-execute
argument-hint: "<task description> [--repo <name>] [--readonly] [--composer|--grok [4.5|4.6] [effort]|--opus|--sol|--sonnet|--luna|--fable|--codex] [--model <id>] [--effort <level>] [--fast] [--budget auto|low|medium|high]  # --repo names from .meta-dev/repos.json"
description: "Run a bounded direct task with headless Cursor Agent (cursor-agent --print). Default Cursor Models pool (Composer 2.5 / Cursor Grok 4.6). Named-only. Brief a DIRECT task, never a Claude slash. Informal --grok 4.6 xhigh routes to cursor-grok-4.6-xhigh."
---

# /cursor-execute — Cursor Agent Headless Execution

Spawn a headless **Cursor Agent** worker (`cursor-agent --print --output-format json`) and report the result back. You stay on this host as conductor.

Uses `scripts/cursor-headless-exec`. Same `OUTPUT_FILE` contract as grok/codex/agy (`{is_error, subtype, num_turns, duration_ms, session_id, result, usage, backend, stop_reason}`). Plugs into `/auto-execute --cursor` and `/meta-execute --cursor`.

## Capabilities card

| | |
|--|--|
| **Harness** | Cursor Agent CLI (`cursor-agent` 2026.09+). **Not** Claude Code. **Not** Grok Build. **Not** a 4th interactive meta-dev host. |
| **Default** | **Cursor Models pool** — Composer 2.5 (collect / budget low) or Cursor Grok 4.6 (ordinary `high`, hard `xhigh`). Pinned so the TUI last-used model cannot leak. |
| **Writes** | Yes (`--print --force --trust --sandbox disabled`). `--readonly` → `--mode ask` (read-only Q&A, no `--force`). Commit-on-red. |
| **Auth** | Ambient `cursor-agent login` (`~/.config/cursor/auth.json`). Optional `CURSOR_API_KEY`. Missing binary or `isAuthenticated != true` aborts **without** a billed run. |
| **Pool** | **Parked / named-only.** Never auto-selected. Never added to `meta_dev.ladder.pool`. Dispatch only when the user named `/cursor-execute` / `--cursor` this turn. |
| **Cannot** | Run Claude slash commands. Be treated as native Grok 4.6 500k context. Nested Cloud Agent `--worker` pools (out of scope). |

## Harness — this worker is not Claude Code

meta-dev is on Claude Code, Codex, and Grok Build. **Headless Cursor does not load meta-dev slash commands.**

**Brief a DIRECT task.** Say *"Audit X and report findings"* or *"Fix the failing test in Z"* — never *"run `/loop-gap`"*. The runner injects a Cursor brief (`references/execute-briefs.md`). Host loading and routing: `references/work-ladder.md` and `references/adaptive-workflow.md`.

## Two usage pools

Cursor bills two buckets. This command defaults to the first so included Composer/Grok credits get used unless the user names an Other-Models id.

| Pool | What is in it | When to use |
|--|--|--|
| **Cursor Models** | Composer 2.5, Cursor Grok 4.6, Cursor Grok 4.5 | Default. Everyday + hard first-party work. |
| **Other Models** | Opus 5, GPT-5.6 Sol/Luna, Fable 5, Sonnet 5, GPT-5.3 Codex, Gemini 3.7 Flash, GPT-5.5, … | Only when the user names `--opus` / `--sol` / `--sonnet` / `--luna` / `--fable` / `--codex` / `--model <id>`. These usually advertise **1M** context. |

## Context limits (Cursor-side — not the vendor native window)

| Family | Catalog prefix | Context **in Cursor** | Notes |
|--|--|--|--|
| Composer 2.5 | `composer-2.5` / `composer-2.5-fast` | **200k** | No Max Mode expansion. Standard vs Fast only. |
| Cursor Grok 4.6 | `cursor-grok-4.6-{low,medium,high,xhigh}[-fast]` | **256k** | **Not** xAI native 500k. Staff-confirmed 256k by design. |
| Cursor Grok 4.5 | `cursor-grok-4.5-{low,medium,high}[-fast]` | **256k** | Same 256k cap. No `xhigh` id — runner maps `xhigh` → `high`. |
| Opus 5 / Opus 4.8 | `claude-opus-5-*` / `claude-opus-4-8-*` | **1M** | Other Models. `--opus` → thinking-high. |
| GPT-5.6 Sol | `gpt-5.6-sol-{none,low,medium,high,xhigh,max}[-fast]` | **1M** | `--sol`. |
| GPT-5.6 Luna | `gpt-5.6-luna-high` | **1M** | `--luna`. Only one live id. |
| Sonnet 5 | `claude-sonnet-5-thinking-{high,xhigh}` | **1M** | `--sonnet`. No `-fast` id. |
| Fable 5 | `claude-fable-5-thinking-{high,xhigh}` | **1M** | `--fable`. Also Fable 5.1 ids via `--model`. |
| GPT-5.3 Codex | `gpt-5.3-codex[-{low,high,xhigh}][-fast]` | catalog | `--codex`. |
| Gemini 3.7 Flash | `gemini-3.7-flash-high` | catalog | `--model` only. |
| Auto | `auto` | Cursor picks | `--model auto` only — do not use as the runner default. |

The chooser must **not** treat Cursor Grok as a 500k window. Need a 1M window → the user must name `--opus` / `--sol` / `--sonnet` / `--luna` / `--fable` / a 1M `--model`.

Live ids drift. `--model <id>` passes unknown catalog ids through. Refresh with `cursor-agent --list-models`.

## When the user does not name a model

Stay on the **Cursor Models** pool. Never auto-pick Opus/Sol.

| Task shape | Flag you pass | Catalog id | Context |
| --- | --- | --- | --- |
| Collect / mechanical / budget `low` | `--composer` (or omit + `--budget low`) | `composer-2.5` | 200k |
| Ordinary implement / standard review | (none) / `--grok 4.6 high` | `cursor-grok-4.6-high` | 256k |
| Hard / architecture / budget `high` | `--grok 4.6 xhigh` | `cursor-grok-4.6-xhigh` | 256k |
| Need 1M / extra family | user must name `--opus` / `--sol` / … | Other Models | 1M |

`--fast` appends `-fast` when that catalog id exists (Composer, Grok, Opus, Sol, Codex). It is a speed/price tier, not a bigger window.

## Informal routing (user typed this)

| User said | Runner flags | Resolves to |
| --- | --- | --- |
| `--grok 4.6 xhigh` | `--grok 4.6 xhigh` | `cursor-grok-4.6-xhigh` |
| `--grok 4.5` | `--grok 4.5` | `cursor-grok-4.5-high` |
| `--composer` | `--composer` | `composer-2.5` |
| `--composer --fast` | `--composer --fast` | `composer-2.5-fast` |
| `--opus` | `--opus` | `claude-opus-5-thinking-high` |
| `--sol --effort xhigh` | `--sol --effort xhigh` | `gpt-5.6-sol-xhigh` |
| `--sonnet` | `--sonnet` | `claude-sonnet-5-thinking-high` |
| `--luna` | `--luna` | `gpt-5.6-luna-high` |
| `--fable` | `--fable` | `claude-fable-5-thinking-high` |
| `--codex` | `--codex` | `gpt-5.3-codex` |
| `--model cursor-grok-4.6-xhigh` | `--model …` | pass-through |

`--composer`, `--grok`, `--opus`, `--sol`, `--sonnet`, `--luna`, `--fable`, and `--codex` are exclusive. `--model` wins over aliases.

## Test discipline — keep every test cycle cheap

When the task runs tests, **focus-scope, always.** Run only the named test file/node. NEVER bare/directory pytest, `-k` without a file, package-wide npm/Vitest/Jest, `npm run check`, `svelte-check`, project-wide `tsc`, a build, or a full suite—not per task and not at phase end. Those belong to CI/ship or a separate explicit request. Reuse green evidence only while its relevant code and dependencies remain unchanged. Unrelated/unchanged `BASELINE_RED` never blocks optimistic momentum. (Cursor cannot rely on reading the charter internally, so this clause IS the rule for Cursor runs.)

## Step 1: Parse Arguments

The user's input is: `$ARGUMENTS`

Parse these optional flags:
- `--repo <name>` — target repo (default: auto-detect; names from `.meta-dev/repos.json`)
- `--readonly` — ask mode, read-only Q&A (audits/reviews)
- `--composer` / `--grok [4.5|4.6] [effort]` / `--opus` / `--sol` / `--sonnet` / `--luna` / `--fable` / `--codex`
- `--model <id>` — explicit `cursor-agent models` id (wins)
- `--effort low|medium|high|xhigh|max|none`
- `--fast`
- `--shape collect|ordinary|hard` — chooser hint
- `--budget auto|low|medium|high` — **depth cap** (default `auto`). Classify before dispatch. Doctrine: `references/execute-budget.md`.
- `--timeout <ms>` — wall-clock (default: from `--budget`)

Family aliases are exclusive. Everything else is the task description. If none is given, ask what task to run.

Treat `--grok 4.6 xhigh` as one alias: version `4.6`, effort `xhigh`. Do not swallow the task as the version.

## Step 2: Select Model

**Default is the Cursor Models pool.** Always pass a resolved `--model` (the runner pins it). An unpinned worker inherits the TUI last-used model.

A user `--model` / alias / `--effort` / `--fast` is binding. Unsure and unnamed → Composer (low) or Cursor Grok 4.6 high (ordinary), never Opus.

## Step 3: Confirm the Plan

Summarize before running:
- **Backend:** Cursor (`cursor-agent --print --output-format json`)
- **Model:** the resolved catalog id
- **Pool:** Cursor Models vs Other Models
- **Context:** 200k Composer / 256k Cursor Grok / 1M third-party
- **Budget:** resolved `low|medium|high`
- **Repo / Work dir**
- **Task**
- **Mode:** read-only (plan) or execute (`--force`)

If the task is destructive or writes outside the repo, confirm first. For review/audit, **default to `--readonly`**.

## Step 4: Execute

Always background it — these jobs routinely take 30–180 minutes.

**BINDING — host tool timeout.** The runner owns the wall (`--budget`: low 30m / medium 90m / high 180m). A 5-second or 5-minute host bash/spawn timeout kills a healthy worker and wastes the tokens already spent.

- **Grok host:** `background: true` **and** `timeout: 0` (disables wrapper kill). Never `timeout: 5000`, `120000`, or `300000`.
- Pass `--timeout` on the runner **only** if the user typed `--timeout` in `$ARGUMENTS`. Never copy the host tool timeout into `--timeout`.
- Waiting on the job: `timeout_ms` ≥ 1800000 (30 min) or poll until exit. `timeout_ms: 300000` is a 5-minute cut-off.

```bash
${PLUGIN_ROOT}/scripts/cursor-headless-exec \
  ${REPO:+--repo "$REPO"} \
  ${MODEL:+--model "$MODEL"} \
  ${COMPOSER:+--composer} ${GROK:+--grok $GROK_VER $GROK_EFFORT} \
  ${OPUS:+--opus} ${SOL:+--sol} ${SONNET:+--sonnet} \
  ${LUNA:+--luna} ${FABLE:+--fable} ${CODEX:+--codex} \
  --budget "$BUDGET" \
  ${EFFORT:+--effort "$EFFORT"} \
  ${FAST:+--fast} \
  ${READONLY:+--readonly} \
  -- <task description>
```

**Repo detection:** `--repo` wins; else infer from `pwd`; if ambiguous, ask.

`--print` is boolean; the prompt is positional. JSON is one object at completion (no stream); a long run looks silent until it returns. Cursor emits **no JSON on failure** — stderr only; the distiller treats empty stdout as error.

## Step 5: Report Results

Three files per run:
- **`OUTPUT_FILE`** — clean JSON. `json.load()` it. `backend` is `cursor`.
- **`<OUTPUT_FILE>.raw`** — full cursor-agent JSON (or empty on failure).
- **`<OUTPUT_FILE>.stderr`** — worker stderr.

When execution completes:
1. Read `OUTPUT_FILE` / the printed `RESULT` block.
2. Check `is_error` and exit code — `3` = distill failed, `4` = worker error, `124` = timed out, `2` = auth missing.
3. Summarize what it found/did, files touched, quota surprises.
4. Execute workers **must have committed** (commit-on-red). Dirty return is an executor bug.

## Safety Notes

- `cursor-agent` must be on PATH (or `~/.local/bin/cursor-agent`) and authenticated (`cursor-agent status --format json` → `isAuthenticated: true`).
- `--readonly` is `--mode ask` and must **not** pass `--force`. Ask mode is read-only Q&A.
- Execute mode uses `--force --trust --sandbox disabled`. The worker **must** `git -C <ABS> add -- <paths> && git -C <ABS> commit --only -m "…" -- <paths>` before returning. Never push.
- Uncommitted Cursor edits are a **bug**. Do not write "the conductor commits" into a Cursor brief.
- Quotas vary by plan (Cursor Models vs Other Models). Confirm available capacity; never assume unlimited Ultra credits.
