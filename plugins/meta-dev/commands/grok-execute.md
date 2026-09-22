---
name: grok-execute
argument-hint: "<task description> [--repo <name>] [--readonly] [--model <grok-4.6|grok-4.5>] [--budget auto|low|medium|high] [--effort <low|medium|high|xhigh>] [--max-turns <n>]  # --repo names from .meta-dev/repos.json"
description: "Run a bounded direct task with headless Grok Build. Default grok-4.6; select model, effort, and workflow depth from configured policy. Preserve sandbox and scope boundaries."
---

# /grok-execute — Grok Headless Execution

Spawn a headless **xAI Grok** worker (`grok --prompt-file … --output-format json`) to run a task, then report the result back. You stay on your current host for orchestration while Grok does a bounded, focused job.

Uses `scripts/grok-headless-exec` under the hood, which emits the **same clean result contract** as `claude-headless-exec` and `codex-headless-exec` (`OUTPUT_FILE` = `{is_error, subtype, num_turns, duration_ms, session_id, result, usage, backend, stop_reason}`), so it plugs into `/auto-execute` exactly like `/deep-execute`, `/glm-execute`, and `/codex-execute`.

## Harness — Grok has meta-dev; this worker is not Claude Code

meta-dev is installed on **Claude Code, Codex, and Grok Build**. Interactive Grok runs the same plugin as skills / slash commands (`/meta-execute`, `/loop-gap`, `/meta-dev`, …). You have used those in the TUI.

This command spawns **headless** Grok (`grok --prompt-file`). That is still Grok Build, so it **loads the same plugins/skills** as the TUI. It is **not** a Claude Code process, so it does **not** run Claude's slash-command engine (`commands/*.md` + `$ARGUMENTS`).

`/deep-execute`, `/opus-execute`, `/sonnet-execute`, `/fable-execute`, and `/glm-execute` spawn a full **Claude Code** instance — those workers *can* be told "run `/loop-gap` on this plan". A Grok worker cannot.

**Brief this worker with a direct task**, or tell it to follow a named Grok skill / `SKILL.md` path. Say *"Fix the failing test in Z"* or *"Audit X for gap class Y and report findings"* — not *"run `/loop-gap` on this plan"* as if this were Claude Code. Let it own the assigned coherent slice. Delegate only authorized independent work within the shared worker cap. The runner injects a Grok brief (`references/execute-briefs.md`). Do not reuse a DeepSeek or Codex paragraph. Host loading and routing: `references/work-ladder.md` and `references/adaptive-workflow.md`.

## When to Use — full execution worker AND cross-family review

Grok occupies a unique slot: it is **both** a general execution tier **and** a cross-family reviewer.

- **As an executor:** Grok 4.6 is a frontier-tier model that **can write files** (like Codex under `--sandbox workspace-write`) — so it can do real bounded implementation work (fixes, refactors, scaffolding), not just read-and-report. Use grok-4.5 / `--effort low` for collect and mechanical; grok-4.6 for ordinary and hard.
- **As a reviewer:** Point it (read-only via `--readonly`) at a diff, the changed files, or a specific finding. A different model family can provide independent evidence, but this is an optional risk-based review, not a guaranteed defect detector or mandatory extra pass.

**Routing:** resolve `meta_dev.ladder` and `meta_dev.workflow` through the shared settings cascade. Grok is an available backend, not a mandatory default pool member. Select it based on verified access and task fit; quota, provider preference, and cross-family review are opt-in configuration. See `references/work-ladder.md` and `references/adaptive-workflow.md`.

## Test discipline — keep every test cycle cheap

When the task runs tests, **focus-scope, always.** Run only the named test file/node. NEVER bare/directory pytest, `-k` without a file, package-wide npm/Vitest/Jest, `npm run check`, `svelte-check`, project-wide `tsc`, a build, or a full suite—not per task and not at phase end. Those belong to CI/ship or a separate explicit request. Reuse green evidence only while its relevant code and dependencies remain unchanged. Unrelated/unchanged `BASELINE_RED` never blocks optimistic momentum. (Grok cannot rely on reading the charter internally, so this clause IS the rule for Grok runs.)

## Step 1: Parse Arguments

The user's input is: `$ARGUMENTS`

Parse these optional flags:
- `--repo <name>` — target repo (default: auto-detect from cwd; names from .meta-dev/repos.json)
- `--readonly` — enforced read-only (deny Write/Edit). Use for all audits/reviews. Grok's deny-rule sandbox blocks every write path (write tool, shell redirection, search_replace) — verified empirically.
- `--model <grok-4.6|grok-4.5>` — override grok model (default: `grok-4.6`, pinned). `grok-4.5` is still supported. An explicit `--model` from the user always wins.
- `--budget auto|low|medium|high` — **depth cap** (default `auto`). Classify the task before dispatch: mechanical → `low`, ordinary → `medium`, hard/auth/schema/pipeline → `high`. Unsure → `medium`. Forward the **resolved** word (`low|medium|high`), never `auto`, unless you want the runner's medium fallback. Caps turns and wall clock so the worker cannot wander. Not `--effort`. Doctrine: `references/execute-budget.md`.
- `--effort <low|medium|high|xhigh>` — reasoning effort. **You pick this from the task**, every time. Do not inherit the TUI/`config.toml` default (often `xhigh`). `xhigh` exists on `grok-4.6` only; `grok-4.5` accepts `low|medium|high`. The runner's omit-fallback is `high` so a forgotten flag does not silently become TUI `xhigh`. Canonical CLI also lists `none|minimal|max`; the runner maps `none`/`minimal` → `low` and `max` → `xhigh` on 4.6 / `high` on 4.5. Explicit `--effort` wins over `--budget`'s effort hint.
- `--max-turns <n>` — cap agent turns (default: from `--budget`)
- `--timeout <ms>` — wall-clock timeout (default: from `--budget`)

Everything else is the task description. If none is given, ask what task to run.

## Step 2: Select Model and Effort

**Pick `--model` and `--effort` from the task every time.** Do not inherit the TUI `xhigh` default. Classify budget first (`low` mechanical, `medium` ordinary, `high` hard — unsure → medium). State model, budget, and effort before dispatching. An explicit user `--budget` / `--effort` / `--model` always wins. Helper: `scripts/classify-execute-budget.sh`. Optional suggestion: `scripts/jev-decide.sh`. Honor fail-open. Never put the key in the worker brief. Jev does not grant permission.

| Task shape | Model | Effort |
| --- | --- | --- |
| Filename collect, grep, inventory, cheap fan-out, one-file mechanical | `grok-4.5` | `low` |
| Ordinary implementation, focused refactor, standard gap check, standard diff review | `grok-4.6` | `high` |
| Hard diagnosis, architecture, plan harden, adversarial review, anything where being subtly wrong is expensive | `grok-4.6` | `xhigh` |
| Images the worker must see | `grok-4.6` | `high` |

`xhigh` is the new 4.6 extra-high reasoning tier. Use it when the task earns it — not as a blanket default. `high` is the omit-fallback on both models.

## Step 3: Confirm the Plan

Summarize before running:
- **Backend:** Grok (`grok --output-format json`)
- **Model:** grok-4.5 (collect/mechanical) or grok-4.6 (ordinary/hard) — the one you classified
- **Budget:** resolved `low|medium|high` (never leave `auto` for the runner if you classified)
- **Effort:** the level you selected above (or the user's `--effort`)
- **Repo / Work dir:** (detected or specified)
- **Task:** (the task description)
- **Mode:** read-only (audit/review) or execute (writes allowed)

If the task is destructive or writes outside the repo, confirm with the user first. For gap-checking/hardening/review, **default to `--readonly`** — Grok reports, you decide.

## Step 4: Execute

Run the headless worker. Always background it — these jobs routinely take 30–180 minutes.

**BINDING — host tool timeout.** The runner owns the wall (`--budget`: low 30m / medium 90m / high 180m). A 5-second or 5-minute host bash/spawn timeout kills a healthy worker and wastes the tokens already spent.

- **Grok:** `background: true` **and** `timeout: 0` (disables wrapper kill). Never `timeout: 5000`, `120000`, or `300000`.
- Pass `--timeout` on the runner **only** if the user typed `--timeout` in `$ARGUMENTS`. Never copy the host tool timeout into `--timeout`.
- Waiting on the job: `timeout_ms` ≥ 1800000 (30 min) or poll until exit. `timeout_ms: 300000` is a 5-minute cut-off.

```bash
${PLUGIN_ROOT}/scripts/grok-headless-exec \
  ${REPO:+--repo "$REPO"} \
  ${MODEL:+--model "$MODEL"} \
  --budget "$BUDGET" \
  ${EFFORT:+--effort "$EFFORT"} \
  ${MAX_TURNS:+--max-turns "$MAX_TURNS"} \
  ${READONLY:+--readonly} \
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
- Account access, quota, and concurrency limits vary. Check the target environment; never assume a subscription or unlimited capacity.
