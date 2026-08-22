---
name: grok-execute
argument-hint: "<task description> [--repo <name>] [--readonly] [--model <grok-4.6|grok-4.5>] [--budget auto|low|medium|high] [--effort <low|medium|high|xhigh>] [--max-turns <n>]  # --repo names from .claude/meta-dev-repos.json"
description: "Execute a task via headless xAI Grok (Grok Build CLI). Interactive Grok has meta-dev as skills/slash commands. A headless grok --prompt-file worker is still Grok Build (same plugins), not Claude Code — brief a DIRECT task or a skill to follow, never a Claude slash. Grok can read AND write. Frontier-reasoning rung of meta_dev.ladder.pool (alongside /deep-execute for mechanical work). Codex and Opus are review-only, not pooled. Default model grok-4.6; grok-4.5 still available. Dispatcher picks --effort per task (xhigh is grok-4.6 only)."
---

# /grok-execute — Grok Headless Execution

Spawn a headless **xAI Grok** worker (`grok --prompt-file … --output-format json`) to run a task, then report the result back. You stay on your current backend (Opus) for orchestration while Grok does a bounded, focused job.

Uses `scripts/grok-headless-exec` under the hood, which emits the **same clean result contract** as `claude-headless-exec` and `codex-headless-exec` (`OUTPUT_FILE` = `{is_error, subtype, num_turns, duration_ms, session_id, result, usage, backend, stop_reason}`), so it plugs into `/auto-execute` exactly like `/deep-execute`, `/glm-execute`, and `/codex-execute`.

## Harness — Grok has meta-dev; this worker is not Claude Code

meta-dev is installed on **Claude Code, Codex, and Grok Build**. Interactive Grok runs the same plugin as skills / slash commands (`/meta-execute`, `/loop-gap`, `/meta-dev`, …). You have used those in the TUI.

This command spawns **headless** Grok (`grok --prompt-file`). That is still Grok Build, so it **loads the same plugins/skills** as the TUI. It is **not** a Claude Code process, so it does **not** run Claude's slash-command engine (`commands/*.md` + `$ARGUMENTS`).

`/deep-execute`, `/opus-execute`, `/sonnet-execute`, `/fable-execute`, and `/glm-execute` spawn a full **Claude Code** instance — those workers *can* be told "run `/loop-gap` on this plan". A Grok worker cannot.

**Brief this worker with a direct task**, or tell it to follow a named Grok skill / `SKILL.md` path. Say *"Fix the failing test in Z"* or *"Audit X for gap class Y and report findings"* — not *"run `/loop-gap` on this plan"* as if this were Claude Code. Full split: `references/work-ladder.md` → *Who has meta-dev*.

## When to Use — full execution worker AND cross-family review

Grok occupies a unique slot: it is **both** a general execution tier **and** a cross-family reviewer.

- **As an executor:** Grok 4.6 is a frontier-tier model that **can write files** (like Codex under `--sandbox workspace-write`) — so it can do real bounded implementation work (fixes, refactors, scaffolding), not just read-and-report. Use it like `/deep-execute` or `/glm-execute` for a self-contained task where an independent strong model is wanted.
- **As a reviewer:** Point it (read-only via `--readonly`) at a diff, the changed files, or a specific finding. An xAI-family model reviewing Claude/DeepSeek/OpenAI output is a **third independent family** — it catches failure modes that same-family review (and even the OpenAI/Codex lens) miss. That independent-family lens is the entire value of Grok-as-reviewer.

**Where it sits on the work ladder:** Grok is the **frontier-reasoning** rung of the execute pool (`meta_dev.ladder.pool` = `deep`, `grok`). DeepSeek is the cheap mechanical rung. Codex and Opus are **not** in the pool — they are extra-family review only ($20/30-mo). **Grok Heavy (since 2026-07-26) gives us a large compute bucket**, and Grok 4.6 is the current frontier default (4.5 remains available via `--model grok-4.5`) — so **spend it** on non-mechanical work. Mechanical / bounded units go to `/deep-execute`. Full routing table: `references/work-ladder.md`.

## Test discipline — keep every test cycle cheap

When the task runs tests, **focus-scope, always.** Run only the named test file/node. NEVER bare/directory pytest, `-k` without a file, package-wide npm/Vitest/Jest, `npm run check`, `svelte-check`, project-wide `tsc`, a build, or a full suite—not per task and not at phase end. Those belong to CI/ship or a separate explicit request. One green is green; never rerun it. Unrelated/unchanged `BASELINE_RED` never blocks optimistic momentum. (Grok cannot rely on reading the charter internally, so this clause IS the rule for Grok runs.)

## Step 1: Parse Arguments

The user's input is: `$ARGUMENTS`

Parse these optional flags:
- `--repo <name>` — target repo (default: auto-detect from cwd; names from .claude/meta-dev-repos.json)
- `--readonly` — enforced read-only (deny Write/Edit). Use for all audits/reviews. Grok's deny-rule sandbox blocks every write path (write tool, shell redirection, search_replace) — verified empirically.
- `--model <grok-4.6|grok-4.5>` — override grok model (default: `grok-4.6`, pinned). `grok-4.5` is still supported. An explicit `--model` from the user always wins.
- `--budget auto|low|medium|high` — **depth cap** (default `auto`). Classify the task before dispatch: mechanical → `low`, ordinary → `medium`, hard/auth/schema/pipeline → `high`. Unsure → `medium`. Forward the **resolved** word (`low|medium|high`), never `auto`, unless you want the runner's medium fallback. Caps turns and wall clock so the worker cannot wander. Not `--effort`. Doctrine: `references/execute-budget.md`.
- `--effort <low|medium|high|xhigh>` — reasoning effort. **You pick this from the task**, every time. Do not inherit the TUI/`config.toml` default (often `xhigh`). `xhigh` exists on `grok-4.6` only; `grok-4.5` accepts `low|medium|high`. The runner's omit-fallback is `high` so a forgotten flag does not silently become TUI `xhigh`. Canonical CLI also lists `none|minimal|max`; the runner maps `none`/`minimal` → `low` and `max` → `xhigh` on 4.6 / `high` on 4.5. Explicit `--effort` wins over `--budget`'s effort hint.
- `--max-turns <n>` — cap agent turns (default: from `--budget`)
- `--timeout <ms>` — wall-clock timeout (default: from `--budget`)

Everything else is the task description. If none is given, ask what task to run.

## Step 2: Select Model and Effort

**Default model is `grok-4.6`.** Keep `grok-4.5` for an explicit compare, a 4.5-only repro, or a user `--model grok-4.5`. Do not pick 4.5 just because older docs mention it.

**You decide `--budget` and `--effort` from the task.** Classify budget first (`low` mechanical, `medium` ordinary, `high` hard — unsure → medium). State model, budget, and effort before dispatching. An explicit user `--budget` / `--effort` always wins. Helper: `scripts/classify-execute-budget.sh`.

| Task shape | Model | Effort |
| --- | --- | --- |
| Quick lookup, one-file mechanical edit, focused search, cheap fan-out | `grok-4.6` | `low` |
| Ordinary implementation, focused refactor, standard gap check, standard diff review | `grok-4.6` | `high` |
| Hard diagnosis, architecture, plan harden, adversarial / cross-family review, anything where being subtly wrong is expensive | `grok-4.6` | `xhigh` |
| Explicit 4.5 fallback or side-by-side compare | `grok-4.5` | `high` (4.5 has no `xhigh`) |

`xhigh` is the new 4.6 extra-high reasoning tier. Use it when the task earns it — not as a blanket default. `high` is the omit-fallback on both models.

## Step 3: Confirm the Plan

Summarize before running:
- **Backend:** Grok (`grok --output-format json`)
- **Model:** grok-4.6 (or the `--model` override)
- **Budget:** resolved `low|medium|high` (never leave `auto` for the runner if you classified)
- **Effort:** the level you selected above (or the user's `--effort`)
- **Repo / Work dir:** (detected or specified)
- **Task:** (the task description)
- **Mode:** read-only (audit/review) or execute (writes allowed)

If the task is destructive or writes outside the repo, confirm with the user first. For gap-checking/hardening/review, **default to `--readonly`** — Grok reports, you decide.

## Step 4: Execute

Run the headless worker. For tasks expected to take >30s, use `run_in_background: true` so the session stays responsive.

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/grok-headless-exec \
  ${REPO:+--repo "$REPO"} \
  ${MODEL:+--model "$MODEL"} \
  --budget "$BUDGET" \
  ${EFFORT:+--effort "$EFFORT"} \
  ${MAX_TURNS:+--max-turns "$MAX_TURNS"} \
  ${READONLY:+--readonly} \
  ${TIMEOUT:+--timeout "$TIMEOUT"} \
  -- <task description>
```

**Repo detection:** `--repo` wins; else infer from `pwd`; if ambiguous (in parent repo), ask which repo to target.

**Note on progress:** Grok's `--output-format json` writes the entire result object at completion (it does not stream), so a long run will appear silent until it returns. The wall-clock timeout is the safety net — be patient on deep tasks.

## Step 5: Report Results

The script distills the worker's output — three files per run:
- **`OUTPUT_FILE`** (printed as `OUTPUT_FILE=<path>`) — clean JSON: `{is_error, subtype, num_turns, duration_ms, session_id, result, usage, backend, stop_reason}`. `result` is Grok's final message. `json.load()` it directly.
- **`<OUTPUT_FILE>.raw`** — the full `grok --output-format json` object incl. the `thought` trace (deep debugging).
- **`<OUTPUT_FILE>.stderr`** — the worker's stderr.

The script also prints the distilled `result` between `RESULT` rules, so for a foreground run you can read it straight from the command output.

When execution completes:
1. **Read `OUTPUT_FILE`** (or the printed `RESULT` block) — already clean JSON.
2. **Check `is_error`** and the `Exit code` line — exit `3` = distill failed (inspect `.raw`), exit `4` = worker reported error, exit `124` = timed out. A non-`EndTurn` `stop_reason` (e.g. `MaxTurns`) is surfaced as a note appended to the result but does not by itself mark error.
3. **Summarize** — what Grok found/did, files touched (if execute mode), any issues.
4. **Apply / next steps** — for reviews, the value is the findings: triage them and apply fixes yourself or via a worker. For execute tasks the worker **must have committed** (commit-on-red). If it returned dirty, that is an executor bug — recover per `references/execute-charter.md`; do not treat uncommitted Grok edits as expected.

## Safety Notes

- Grok must be authenticated (`~/.grok/auth.json` — via `grok login`, OAuth to grok.com / xAI). The script warns if auth is missing.
- `--readonly` enforces read-only via Grok's deny rules (`--deny Write --deny Edit`), which block every write path including shell redirections. It is NOT paired with `bypassPermissions` (that would defeat it).
- Execute mode uses `--permission-mode bypassPermissions --always-approve` — full autonomy to edit files **and to commit**. The worker **must** `git -C <ABS> add -- <paths> && git -C <ABS> commit --only -m "…" -- <paths>` before returning (commit-on-red). Never push; the conductor owns the remote.
- Uncommitted Grok edits are a **bug**, not a feature. Do not write "the conductor commits" into a Grok brief.
- **Budget is not the constraint** — the grok.com account is on **Grok Heavy**, a large compute bucket, so route work here liberally rather than rationing it. The one thing that still matters is scoping: a well-specified task returns a better result than a vague one, on any model.
