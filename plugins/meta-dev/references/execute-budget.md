# Execution budget — depth cap, not thinking effort

> **Last verified:** 2026-08-22

`--budget` stops a worker from overthinking and wandering. It is **not**
`--effort` (how hard the model thinks per turn) and **not**
`--max-budget-usd` (Claude API spend).

**Default is `auto`.** The dispatcher classifies the task *before* launch.
The runner never goes uncapped.

## Levels

| Level | Turns | Wall clock | Effort (only if `--effort` omitted) | Worker must |
|-------|-------|------------|--------------------------------------|-------------|
| **low** | 12 | 15 min | `low` | Do the named thing. No extra investigation. No subagents. Stop at first acceptance. |
| **medium** | 32 | 45 min | leave backend default | Declared files only. One repair pass. No unrelated refactors. |
| **high** | 80 | 120 min | `xhigh` if the backend has it, else `high` | Go as deep as the task needs. Still no unrelated work. Cap 3 repair rounds. |

`--effort`, `--max-turns`, and `--timeout` always win over the table for that
knob. `--budget` still injects the depth rules.

`--budget auto` at a **runner** (no classifier ran) falls back to **medium**
and logs it. Do not leave that as the usual path — classify at dispatch.

## Auto-select (dispatcher)

Classify the **task**, not the plan's mood. When unsure → **medium**, never
high.

| Pick **low** when | Pick **high** when |
|---|---|
| rename, find-replace, one-file string edit, boilerplate, copy, changelog, typo, `--flash` mechanical, single known-file lookup | auth / payment / schema / render-pipeline, root cause unclear, already failed once, architecture, multi-module design, "make it correct end-to-end" |

Everything else is **medium**.

Helper (prints one word: `low|medium|high`):

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/classify-execute-budget.sh" \
  --campaign auto -- "Rename getCwd across the project"
```

## `/meta-execute --budget`

Campaign budget is a **ceiling**:

- omitted / `auto` → classify **each task** independently
- `low|medium|high` → no task may exceed that level; a mechanical task may still drop to low

Forward the **resolved** `--budget low|medium|high` to every worker (headless
flag, or the Budget block in `references/execute-dispatch.md` for host-native
spawn). Do not dispatch uncapped.

Review-only Opus/Codex passes on this tree stay one pass each. Budget `low`
is enough for a `--readonly` extra-family scan unless the gate is genuinely
hard — then `medium`. Never `high` on a review lens just because the execute
wave was high.

## Who classifies

The **conductor** (slash command / host-native `/meta-execute`). Not the
worker. The worker only obeys the cap it was given.

## Flags

All of: `/deep-execute`, `/grok-execute`, `/opus-execute`, `/sonnet-execute`,
`/fable-execute`, `/glm-execute`, `/codex-execute`, `/antigravity-execute`,
`/auto-execute`, `/meta-execute`.

```
--budget auto|low|medium|high     # default auto
```

Alias: `med` → `medium`.
