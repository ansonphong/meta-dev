---
name: codex-execute
argument-hint: <task description> [--repo <name>] [--readonly] [--budget auto|low|medium|high] [--tier <spark|luna|terra|sol|astra>] [--effort <none|low|medium|high|xhigh|max|ultra>] [--model <model>] [--sandbox <mode>]
description: Run a bounded task with headless OpenAI Codex. Brief a DIRECT task or use --skill/--command. Select spark|luna|terra|sol|astra and effort explicitly. Terra is gpt-6-sol at medium; Sol is gpt-6-sol at high; Astra is gpt-6-astra. There is no gpt-6-terra.
---

# /codex-execute - GPT Task Runner

Run a direct, bounded task through `codex exec`.

## Harness — Codex has meta-dev

meta-dev is installed on **Claude Code, Codex, and Grok Build**.

**Interactive Codex** runs the plugin as native skills: `$meta-dev:meta-execute`, `$meta-dev:loop-gap`, `@meta-dev:meta-execute`, and the rest. That is the same plugin, not a stub.

**This command** is **headless** `codex exec`. It cannot invoke a skill by typing `/loop-gap` the way Claude Code does. It **does** have the plugin:

- Every dispatch injects a generated harness preamble: the framework root, the roster of all protocols (`skills/`) and procedures (`commands/`), the binding LAWS (planctl is the only write door; never hand-edit a checkbox; report failures honestly), and a Claude→Codex translation table. So the worker knows the harness exists and is told to use it — rather than freelancing, which is what a bare Codex dispatch does.
- `--skill` / `--command` hand it the same markdown Claude Code reads, from the source tree. No install, no version-keyed cache to go stale.

**Brief this worker with a direct task** (or `--skill` / `--command`). **Inline** the 30–60 lines that matter — supply the acceptance contract and live-code anchors, with targeted reads when needed. Never "run `/loop-gap` on this plan" as if this were Claude Code. The runner injects a Codex brief (`references/execute-briefs.md`). Claude-family headless (`/deep-execute`, `/opus-execute`, …) *can* run that slash internally. Host loading and routing: `references/work-ladder.md` and `references/adaptive-workflow.md`.

The runner's fallback is `gpt-6-sol` at `medium` (the terra role). The installed Codex catalog has no `gpt-6-terra`, so the terra role is ordinary `gpt-6-sol` at medium. Sol is the same `gpt-6-sol` at high for plan/harden/review. Luna is `gpt-6-luna` at low. Spark stays `gpt-5.3-codex-spark` for mechanical work. Astra is opt-in `gpt-6-astra` at high. State the selected tier and effort before dispatching. An explicit `--tier`, `--effort`, or `--model` from the user always wins, including a 5.6 id the caller types. `gpt-6-astra` and `gpt-6-sol` reject effort `none`. `gpt-6-luna` rejects `none` and `ultra`.

## Test discipline — keep every test cycle cheap

When the task runs tests, **focus-scope, always.** Run only the named test file/node — `pytest path/to/test_x.py -q` (add `-m "not slow and not gpu and not integration"` if the suite marks them). NEVER bare/directory pytest, `pytest -k` without a file, package-wide npm/Vitest/Jest, `npm run check`, `svelte-check`, project-wide `tsc`, a build, or a full suite—not per task and not at phase end. Those belong to CI/ship or a separate explicit user request. Reuse green evidence only while its relevant code and dependencies remain unchanged. Classify results as `FOCUSED_PASS`, causally proven `TASK_RED`, unrelated/unchanged `BASELINE_RED`, `INFRA_RED`, or `BROAD_VERIFY_OMITTED`. Only `TASK_RED` repairs/defer its direct branch; optimistic momentum continues everywhere else. (Codex cannot rely on reading the charter internally, so this clause IS the rule for Codex runs; the dispatcher also injects it.)

## Step 1: Parse Arguments

The user's input is `$ARGUMENTS`.

Parse these flags:
- `--repo <name>`: target repo; otherwise detect from `pwd`.
- `--readonly`: force the `read-only` sandbox.
- `--tier <spark|luna|terra|sol|astra>`: model family selection.
- `--budget auto|low|medium|high`: depth cap (default `auto`). Classify this task or review's scope and risk; do not inherit implementation depth for a simple review. See `references/execute-budget.md`. Optional suggestion: `scripts/jev-decide.sh`. Honor fail-open. An explicit `--model` still wins. Risk tags still force a high budget. Never put the key in the worker brief. Jev does not grant permission.
- `--effort <none|low|medium|high|xhigh|max|ultra>`: override the tier's reasoning effort. Explicit `--effort` wins over `--budget`. `gpt-6-astra` and `gpt-6-sol` support every listed effort except `none`. `gpt-6-luna` rejects `none` and `ultra`. Other models depend on their catalog support.
- `--model <model>`: exact Codex model ID; it overrides tier selection but not a supplied effort.
- `--sandbox <mode>`: `read-only`, `workspace-write`, or `danger-full-access`.
- `--timeout <ms|30s|30m|2h>`: wall-clock limit; default is from `--budget` (medium = 90 min). Pass only if the user typed `--timeout`.
- `--skill <name>`: run a meta-dev **protocol** (`workflow-skills/<name>/SKILL.md`).
- `--command <name>`: run a meta-dev **procedure** (`commands/<name>.md`).
- `--no-framework`: omit the harness preamble. Only for trivial one-shots (a lookup, a probe) — never for real work.
- `--multi-agent`: enable Codex `spawn_agent` (4 concurrent). Native delegation may select models when the host exposes that capability. Under-development flag; opt-in deliberately.

Resolve ownership and worker caps through `references/adaptive-workflow.md`. A Sol/Astra worker may own a bounded coherent slice; do not require nested delegation per checkbox. Model selection does not imply host async tools, dynamic effort, or additional permissions.

Everything else is the task. Ask for a task if none is provided.

## Step 2: Select Model and Effort

Classify the task by scope, ambiguity, reversibility, and quality sensitivity. Pick the smallest tier and effort that can meet the acceptance criteria. Do not select a higher tier merely because the task has many words.

| Task shape | Tier and effort | Default sandbox |
| --- | --- | --- |
| High-volume mechanical code work where latency matters: bulk rename, boilerplate, mass lint/format fix, quick syntax triage | `spark` / `low` | `workspace-write` for an authorized edit; else `read-only` |
| Read-only lookup, one-file mechanical edit, focused test diagnosis | `luna` / `low` | `read-only` for analysis; `workspace-write` only for an authorized edit |
| Normal bug fix, known-scope feature, focused refactor, standard diff review | `terra` / `medium` | `workspace-write` for requested changes; otherwise `read-only` |
| Cross-module behavior, ambiguous root cause, security/reliability review, migration, architecture work | `sol` / `high` | `read-only` for chat-only verdict; **`workspace-write` if any report/plan file is required** |
| High-impact or difficult task with measurable quality criteria and evidence that `high` is insufficient | `sol` / `xhigh` | match the requested action (write path → `workspace-write`) |
| Only the hardest quality-first work, after `xhigh` is demonstrably insufficient | `sol` / `max` | match the requested action (write path → `workspace-write`) |
| Opt-in GPT-6 quality work: difficult implementation, architecture, or review | `astra` / `high` | match the requested action (write path → `workspace-write`) |

| Tier | Model ID | Default effort |
| --- | --- | --- |
| `spark` | `gpt-5.3-codex-spark` | `low` |
| `luna` | `gpt-6-luna` | `low` |
| `terra` | `gpt-6-sol` | `medium` |
| `sol` | `gpt-6-sol` | `high` |
| `astra` | `gpt-6-astra` | `high` |

`gpt-6-astra` and `gpt-6-sol` support `low`, `medium`, `high`, `xhigh`, `max`, and `ultra`. They do not support `none`. `gpt-6-luna` supports `low`, `medium`, `high`, `xhigh`, and `max`. It does not support `none` or `ultra`. Use `low` for lightweight work, `medium` for balanced reasoning, and `high` for Sol and Astra quality defaults. Escalate to `xhigh` or `max` when evaluation criteria justify more reasoning. The Codex catalog describes `ultra` as maximum reasoning with automatic task delegation; select it deliberately for Astra or Sol work that warrants that behavior. It does not make the runner enable `--multi-agent` automatically. Never infer sandbox permissions from tier or effort.

These tier defaults apply with `--budget auto` or `medium`. Without explicit `--effort`, budget `low` selects `low` and budget `high` selects `xhigh`. `--model` replaces only the model ID; the selected tier/budget still supplies effort unless overridden. Project settings may opt in via `meta_dev.codex.models.<role>`, for example `{"tier":"astra","effort":"ultra"}`; shipped routes remain unchanged.

**Availability is account- and CLI-dependent.** Codex CLI 0.155.1 lists `gpt-6-astra`, `gpt-6-sol`, and `gpt-6-luna`. It has no `gpt-6-terra`. The runner binds the terra role to `gpt-6-sol` at medium. Astra's catalog default is `medium`; the runner defaults the Astra tier to `high`. Catalog visibility is not a live account entitlement check; confirm model access in the target environment. Do not infer quota pools or limits from tier names.

**Routing meta-dev work specifically** (these map to the harness's own stages):

| meta-dev work | Tier / effort | Dispatch as |
| --- | --- | --- |
| Bulk mechanical sweep across many plan files (stamp, rename, path fix) | `spark` / `low` | plain task |
| Phase-gate or diff review | `sol` / `high` | `--skill code-review-protocol` |
| Over-engineering / complexity audit | `terra` / `medium` | `--skill sniff-test` |
| Executing a phase file task-by-task | `terra` / `medium` | `--command meta-execute` |
| Plan gap-scan (HARDEN) | `sol` / `high` | `--command meta-loop-gap` · **`workspace-write`** (report on disk) |
| Architecture, security, ambiguous root cause | `sol` / `xhigh` | plain task · `--readonly` only if chat-only; **file/report → no `--readonly`** |
| Explicit GPT-6 quality evaluation or difficult bounded task | `astra` / `high` (or explicitly selected effort) | plain task · sandbox follows deliverable |

### ⛔ Sandbox vs deliverable (mandatory)

**Sandbox is part of the task.** Do not default Sol architecture/gap work to `--readonly` when the brief names a file.

| Situation | Sandbox |
|-----------|---------|
| Pure analysis; answer only in the worker return; no file, no commit | `--readonly` OK |
| Any on-disk deliverable: gap report, plan/brainstorm/design edit, code, commit, fixture, artifact under `plans/` | **`workspace-write` (omit `--readonly`)** |
| User said `--readonly` but task needs a file | Keep read-only and return the report in the final message, or ask for permission to write; never silently widen the sandbox |

When writes are authorized, a named on-disk artifact needs **workspace-write**. An explicit read-only restriction remains binding: return results in the final message or ask for write permission. `workspace-write` must allow `.git` when commits are required — never “conductor commits for Codex.”

For a review, explanation, or diagnosis **with no artifact**, make no changes and select `--readonly`. For gap reports, plan harden artifacts, or any named output path, use **`workspace-write`**. For a change, build, or fix request, make only the in-scope local changes and run relevant non-destructive, path-scoped validation. Require confirmation for external writes, destructive operations, purchases, or a material scope expansion.

## Step 3: Confirm and Execute

Before running, summarize:
- **Model:** resolved model ID, tier, and reasoning effort.
- **Repo / work dir:** detected or supplied repo.
- **Task:** direct bounded instruction with success criteria and relevant paths.
- **Sandbox:** read-only or workspace-write, with the reason.

**Inline the task contract.** Include acceptance criteria, task handles, scoped paths, and relevant plan/design excerpts in the text passed with `--`. Include live-code anchors for targeted inspection. Avoid repeated full-plan reads; do not forbid the reads needed to verify a stale anchor or dependency. A coherent slice retains an acceptance record for each outcome.

If the task writes, confirm the requested scope is authorized. If it is destructive or writes outside the repo, obtain explicit confirmation.

```bash
${PLUGIN_ROOT}/scripts/codex-headless-exec \
  ${REPO:+--repo "$REPO"} \
  --budget "$BUDGET" \
  --tier "$TIER" \
  --effort "$EFFORT" \
  ${MODEL:+--model "$MODEL"} \
  ${SKILL:+--skill "$SKILL"} \
  ${COMMAND:+--command "$COMMAND"} \
  ${READONLY:+--readonly} \
  ${SANDBOX:+--sandbox "$SANDBOX"} \
  -- <direct task with acceptance criteria>
```

The runner maps tiers to the model IDs in Step 2 and forwards effort as `model_reasoning_effort`. It validates tier and effort before invoking Codex. It rejects `none` when the effective model is `gpt-6-astra` or `gpt-6-sol`, and rejects `none` and `ultra` when the effective model is `gpt-6-luna`, including an explicit `--model` override.

**BINDING — host tool timeout.** Always background Codex workers — they routinely take 30–180 minutes. The runner owns the wall (`--budget`: low 30m / medium 90m / high 180m). A 5-second or 5-minute host bash/spawn timeout kills a healthy worker and wastes the tokens already spent.

- **Grok:** `background: true` **and** `timeout: 0`. Never `timeout: 5000`, `120000`, or `300000`.
- **Codex host:** background the process; no short command timeout.
- Pass `--timeout` on the runner **only** if the user typed `--timeout` in `$ARGUMENTS`.
- Waiting on the job: `timeout_ms` ≥ 1800000 (30 min) or poll until exit.

```bash
# Astra tier default: high
${PLUGIN_ROOT}/scripts/codex-headless-exec --tier astra --readonly -- "Review the supplied diff for correctness; return findings only."
# Explicit effort wins even over a low execution budget
${PLUGIN_ROOT}/scripts/codex-headless-exec --tier astra --effort ultra --budget low --readonly -- "Evaluate the supplied algorithm against the stated invariants."
# Exact model override with balanced Astra reasoning
${PLUGIN_ROOT}/scripts/codex-headless-exec --model gpt-6-astra --effort medium --readonly -- "Explain the supplied function."
```

## Step 4: Report Results

Read `OUTPUT_FILE`, which is clean JSON containing `is_error`, `result`, `num_turns`, `duration_ms`, `session_id`, `usage`, and `backend`. Inspect `.raw` for the complete event stream and `.stderr` for runner errors.

Report the selected model and effort, work completed, files changed, validation performed, commit SHA, and remaining risks. For an authorized implementation task, Codex must locally commit its exact scoped edits before returning even when validation is red/BLOCKED; red blocks DONE and remote push, not persistence. Read-only/review tasks create no empty commit. Exit `3` means result distillation failed, `4` means the worker reported an error, `124` means timeout, and `125` means the liveness watchdog halted the run.
