---
name: codex-execute
argument-hint: <task description> [--repo <name>] [--readonly] [--tier <spark|luna|terra|sol>] [--effort <none|low|medium|high|xhigh|max>] [--model <model>] [--sandbox <mode>]
description: Run a bounded task with headless OpenAI Codex using task-aware GPT model and reasoning-effort routing.
---

# /codex-execute - GPT Task Runner

Run a direct, bounded task through `codex exec`.

**The worker has the meta-dev framework.** Every dispatch injects a generated harness preamble: the framework root, the roster of all protocols (`skills/`) and procedures (`commands/`), the binding LAWS (planctl is the only write door; never hand-edit a checkbox; report failures honestly), and a Claude→Codex translation table. So the worker knows the harness exists and is told to use it — rather than freelancing its own process, which is what a bare Codex dispatch does.

Codex cannot invoke a slash command, but it can **follow** any procedure file once handed the path. That is what `--skill` and `--command` do, and it keeps ONE source of truth: Codex reads the same markdown Claude Code does, from the source tree, with no install and no version-keyed cache to go stale.

**Route Spark-first** (see Step 2 — Spark bills to a separate quota, so it is effectively free capacity). The runner's fallback default is `gpt-5.6-terra`/`medium`, but you should be *choosing* a tier every time, not inheriting that. State the selected tier and effort before dispatching. An explicit `--tier`, `--effort`, or `--model` from the user always wins.

## Test discipline — keep every test cycle cheap

When the task runs tests, **focus-scope, always.** Run only the named test file/node — `pytest path/to/test_x.py -q` (add `-m "not slow and not gpu and not integration"` if the suite marks them). NEVER bare/directory pytest, `pytest -k` without a file, package-wide npm/Vitest/Jest, `npm run check`, `svelte-check`, project-wide `tsc`, a build, or a full suite—not per task and not at phase end. Those belong to CI/ship or a separate explicit user request. One green is green; worker and conductor never repeat it. Classify results as `FOCUSED_PASS`, causally proven `TASK_RED`, unrelated/unchanged `BASELINE_RED`, `INFRA_RED`, or `BROAD_VERIFY_OMITTED`. Only `TASK_RED` repairs/defer its direct branch; optimistic momentum continues everywhere else. (Codex cannot rely on reading the charter internally, so this clause IS the rule for Codex runs; the dispatcher also injects it.)

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
- `--skill <name>`: run a meta-dev **protocol** (`workflow-skills/<name>/SKILL.md`).
- `--command <name>`: run a meta-dev **procedure** (`commands/<name>.md`).
- `--no-framework`: omit the harness preamble. Only for trivial one-shots (a lookup, a probe) — never for real work.
- `--multi-agent`: enable Codex `spawn_agent` (4 concurrent). **Parallelism only — spawned agents inherit the parent's model, so this does NOT save quota.** Under-development flag; opt-in deliberately.

**You may dispatch `--tier spark` directly**, and should whenever the task is mechanical — it is a separate quota (Step 2). Every worker also receives instructions to delegate its own mechanical sub-work to spark via `codex exec -m gpt-5.3-codex-spark`, so a `sol` worker spends its expensive reasoning only on the judgment-bearing part.

Everything else is the task. Ask for a task if none is provided.

## Step 2: Select Model and Effort

### ⚡ SPARK FIRST — it bills to a SEPARATE quota

**Default to `spark` unless the task genuinely needs more.** `codex /status` reports two independent weekly pools: one shared by `gpt-5.6-sol|terra|luna`, and a separate `GPT-5.3-Codex-Spark` pool. **Spark work does not consume the 5.6 budget at all.**

So Spark is not merely "the fast tier" — it is *free capacity running alongside* your main budget. Every mechanical pass Spark absorbs is 5.6 quota preserved for the reasoning-heavy work only `sol` can do. Sending bulk work to `terra` "because it's the default" actively burns the scarce pool to do something the free pool handles fine.

**Ask in this order:**
1. **Can `spark` do this competently?** → use `spark`. It is coding-tuned and lowest-latency, so it beats `luna` on any bulk *code* pass.
2. If not, does it need real reasoning (ambiguity, cross-module behaviour, security, architecture)? → `sol`.
3. Only otherwise → `terra`.

**Spark handles well:** bulk renames, boilerplate, mass lint/format fixes, syntax triage, mechanical multi-file edits, "which file defines X", grep-and-summarize sweeps, fan-out probes, single-file focused edits with clear acceptance criteria.

**Spark is the wrong tool for:** ambiguous root cause, cross-module reasoning, security/reliability review, architecture, migrations, anything where being subtly wrong is expensive. Escalate those to `sol` without hesitation — that is what the preserved budget is *for*.

When work decomposes, split it: let `spark` do the mechanical 80% and spend `sol` only on the judgment-bearing remainder.

---

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

**Spark bills to a SEPARATE weekly bucket.** `codex /status` reports two independent pools — one shared by `gpt-5.6-sol|terra|luna`, and a distinct `GPT-5.3-Codex-Spark Weekly limit`. Spark work therefore does not consume the 5.6 budget at all. Route to `spark` whenever it is competent for the task, not merely when latency matters: every mechanical pass it absorbs is 5.6 quota preserved for the reasoning-heavy work only `sol` can do. When choosing between `spark` and `luna` for a bulk *code* pass, prefer `spark` — it is coding-tuned AND free relative to the shared pool.

**Availability is account-scoped — verified live 2026-07-18 on this ChatGPT account:** `gpt-5.3-codex-spark`, `gpt-5.6-luna|terra|sol` all answer. `gpt-5.6-codex` is **rejected** by the API (*"not supported when using Codex with a ChatGPT account"*), so it is deliberately absent from the ladder. Re-probe before adding any new model ID rather than assuming a newer number is available.

**Routing meta-dev work specifically** (these map to the harness's own stages):

| meta-dev work | Tier / effort | Dispatch as |
| --- | --- | --- |
| Bulk mechanical sweep across many plan files (stamp, rename, path fix) | `spark` / `low` | plain task |
| Phase-gate or diff review | `sol` / `high` | `--skill code-review-protocol` |
| Over-engineering / complexity audit | `terra` / `medium` | `--skill sniff-test` |
| Executing a phase file task-by-task | `terra` / `medium` | `--command meta-execute` |
| Plan gap-scan (HARDEN) | `sol` / `high` | `--command meta-loop-gap` |
| Architecture, security, ambiguous root cause | `sol` / `xhigh` | plain task, `--readonly` |

For a review, explanation, diagnosis, or plan, make no changes and select `--readonly` unless the user explicitly asks for implementation. For a change, build, or fix request, make only the in-scope local changes and run relevant non-destructive, path-scoped validation. Require confirmation for external writes, destructive operations, purchases, or a material scope expansion.

## Step 3: Confirm and Execute

Before running, summarize:
- **Model:** resolved model ID, tier, and reasoning effort.
- **Repo / work dir:** detected or supplied repo.
- **Task:** direct bounded instruction with success criteria and relevant paths.
- **Sandbox:** read-only or workspace-write, with the reason.

**Inline the task — do not reference it.** Put the acceptance criteria and the relevant plan/design excerpt directly in the task text you pass with `--`. Do not point Codex at a plan file to reconstruct what to do: it will re-read that file repeatedly and the re-reads dominate the run. Paste the ~30–60 lines that matter — far cheaper than a dozen re-reads of the whole file.

If the task writes, confirm the requested scope is authorized. If it is destructive or writes outside the repo, obtain explicit confirmation.

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/codex-headless-exec \
  ${REPO:+--repo "$REPO"} \
  --tier "$TIER" \
  --effort "$EFFORT" \
  ${MODEL:+--model "$MODEL"} \
  ${SKILL:+--skill "$SKILL"} \
  ${COMMAND:+--command "$COMMAND"} \
  ${READONLY:+--readonly} \
  ${SANDBOX:+--sandbox "$SANDBOX"} \
  ${TIMEOUT:+--timeout "$TIMEOUT"} \
  -- <direct task with acceptance criteria>
```

The runner maps tiers to `gpt-5.3-codex-spark`, `gpt-5.6-luna`, `gpt-5.6-terra`, and `gpt-5.6-sol`, and sends the selected effort through Codex configuration. It validates tier and effort values before starting. For tasks expected to take more than 30 seconds, run in the background.

## Step 4: Report Results

Read `OUTPUT_FILE`, which is clean JSON containing `is_error`, `result`, `num_turns`, `duration_ms`, `session_id`, `usage`, and `backend`. Inspect `.raw` for the complete event stream and `.stderr` for runner errors.

Report the selected model and effort, work completed, files changed, validation performed, commit SHA, and remaining risks. For an authorized implementation task, Codex must locally commit its exact scoped edits before returning even when validation is red/BLOCKED; red blocks DONE and remote push, not persistence. Read-only/review tasks create no empty commit. Exit `3` means result distillation failed, `4` means the worker reported an error, `124` means timeout, and `125` means the liveness watchdog halted the run.
