---
name: codex-execute
argument-hint: <task description> [--repo <name>] [--readonly] [--tier <spark|luna|terra|sol>] [--effort <none|low|medium|high|xhigh|max>] [--model <model>] [--sandbox <mode>]
description: Run a bounded task with headless OpenAI Codex using task-aware GPT model and reasoning-effort routing.
---

# /codex-execute - GPT Task Runner

Run a direct, bounded task through `codex exec`. Codex is its own agent harness: give it the task and success criteria directly. Do not ask it to invoke a meta-dev slash command.

The default is `gpt-5.6-terra` with `medium` reasoning. Route based on the work, then state the selected tier and effort before dispatching. An explicit `--tier`, `--effort`, or `--model` from the user always wins.

## Step 1: Parse Arguments

The user's input is `$ARGUMENTS`.

Parse these flags:
- `--repo <name>`: target repo; otherwise detect from `pwd`.
- `--readonly`: force the `read-only` sandbox.
- `--tier <spark|luna|terra|sol>`: model family selection.
- `--effort <none|low|medium|high|xhigh|max>`: override the tier's reasoning effort.
- `--model <model>`: exact Codex model ID; it overrides tier selection but not a supplied effort.
- `--sandbox <mode>`: `read-only`, `workspace-write`, or `danger-full-access`.
- `--timeout <ms>`: wall-clock limit; default is `7200000`.

Everything else is the task. Ask for a task if none is provided.

## Step 2: Select Model and Effort

Classify the task by scope, ambiguity, reversibility, and quality sensitivity. Pick the smallest tier and effort that can meet the acceptance criteria. Do not select a higher tier merely because the task has many words.

| Task shape | Tier and effort | Default sandbox |
| --- | --- | --- |
| High-volume mechanical code work where latency matters: bulk rename, boilerplate, mass lint/format fix, quick syntax triage | `spark` / `low` | `workspace-write` for an authorized edit; else `read-only` |
| Read-only lookup, one-file mechanical edit, focused test diagnosis | `luna` / `low` | `read-only` for analysis; `workspace-write` only for an authorized edit |
| Normal bug fix, known-scope feature, focused refactor, standard diff review | `terra` / `medium` | `workspace-write` for requested changes; otherwise `read-only` |
| Cross-module behavior, ambiguous root cause, security/reliability review, migration, architecture work | `sol` / `high` | `read-only` until implementation is explicitly authorized |
| High-impact or difficult task with measurable quality criteria and evidence that `high` is insufficient | `sol` / `xhigh` | match the requested action |
| Only the hardest quality-first work, after `xhigh` is demonstrably insufficient | `sol` / `max` | match the requested action |

`gpt-5.6-sol` is the flagship model, `gpt-5.6-terra` is the balanced model, `gpt-5.6-luna` is optimized for efficient high-volume work, and `gpt-5.3-codex-spark` is the Codex-specialized speed model — coding-tuned and lowest-latency, so it beats `luna` on bulk mechanical *code* passes while `luna` remains the better generalist for prose/analysis. `high`, `xhigh`, and especially `max` increase latency and usage; use them only when the task's risk or evaluation criteria justify it. Never infer that `danger-full-access` is needed from tier or effort.

**Availability is account-scoped — verified live 2026-07-18 on this ChatGPT account:** `gpt-5.3-codex-spark`, `gpt-5.6-luna|terra|sol` all answer. `gpt-5.6-codex` is **rejected** by the API (*"not supported when using Codex with a ChatGPT account"*), so it is deliberately absent from the ladder. Re-probe before adding any new model ID rather than assuming a newer number is available.

For a review, explanation, diagnosis, or plan, make no changes and select `--readonly` unless the user explicitly asks for implementation. For a change, build, or fix request, make only the in-scope local changes and run relevant non-destructive, path-scoped validation. Require confirmation for external writes, destructive operations, purchases, or a material scope expansion.

## Step 3: Confirm and Execute

Before running, summarize:
- **Model:** resolved model ID, tier, and reasoning effort.
- **Repo / work dir:** detected or supplied repo.
- **Task:** direct bounded instruction with success criteria and relevant paths.
- **Sandbox:** read-only or workspace-write, with the reason.

If the task writes, confirm the requested scope is authorized. If it is destructive or writes outside the repo, obtain explicit confirmation.

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/codex-headless-exec \
  ${REPO:+--repo "$REPO"} \
  --tier "$TIER" \
  --effort "$EFFORT" \
  ${MODEL:+--model "$MODEL"} \
  ${READONLY:+--readonly} \
  ${SANDBOX:+--sandbox "$SANDBOX"} \
  ${TIMEOUT:+--timeout "$TIMEOUT"} \
  -- <direct task with acceptance criteria>
```

The runner maps tiers to `gpt-5.3-codex-spark`, `gpt-5.6-luna`, `gpt-5.6-terra`, and `gpt-5.6-sol`, and sends the selected effort through Codex configuration. It validates tier and effort values before starting. For tasks expected to take more than 30 seconds, run in the background.

## Step 4: Report Results

Read `OUTPUT_FILE`, which is clean JSON containing `is_error`, `result`, `num_turns`, `duration_ms`, `session_id`, `usage`, and `backend`. Inspect `.raw` for the complete event stream and `.stderr` for runner errors.

Report the selected model and effort, work completed, files changed, validation performed, and remaining risks. Exit `3` means result distillation failed, `4` means the worker reported an error, `124` means timeout, and `125` means the liveness watchdog halted the run. Codex changes are never automatically committed.
