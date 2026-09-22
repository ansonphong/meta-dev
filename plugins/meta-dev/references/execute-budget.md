# Execution budget — depth cap, not thinking effort

> **Last verified:** 2026-09-09

`--budget` stops a worker from overthinking and wandering. It is **not**
`--effort` (how hard the model thinks per turn) and **not**
`--max-budget-usd` (Claude API spend).

**Default is `auto`.** The dispatcher classifies the task *before* launch.
The runner never goes uncapped.

## Levels

| Level | Turns | Wall clock | Effort (only if `--effort` omitted) | Worker must |
|-------|-------|------------|--------------------------------------|-------------|
| **low** | 12 | 30 min | `low` | Do the named thing. No extra investigation. No subagents. Stop at first acceptance. |
| **medium** | 32 | 90 min | leave backend default | Declared files only. One repair pass. No unrelated refactors. |
| **high** | 80 | 180 min | `xhigh` if the backend has it, else `high` | Go as deep as the task needs. Still no unrelated work. Cap 3 repair rounds. |

These walls match real headless jobs (DeepSeek / Codex / Grok / Opus / Fable
often run 30+ min). Do not pass a host bash/spawn timeout (5s, 2 min, 5 min)
as `--timeout` — the runner ignores those as leaks and uses the budget wall.

`--timeout` accepts `30m` / `2h` / `1800s` / milliseconds. A bare number
below 1000 is **seconds**, not milliseconds.

Liveness: stream workers use a silence watchdog of **max(20 min, wall/4)**
(capped 45 min). Thinking models that emit nothing for 5 minutes are healthy.

`--effort`, `--max-turns`, and `--timeout` win over the table for that knob
unless `--timeout` is a host-tool leak (5s–5min in ms) — those are ignored
and the budget wall is used. `--budget` still injects the depth rules.

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
bash "${PLUGIN_ROOT}/scripts/classify-execute-budget.sh" \
  --campaign auto -- "Rename getCwd across the project"
```

`scripts/jev-decide.sh` may suggest a budget and rung. A missing key fails open
to the keyword word above. `risk-tag.sh` still forces high on money, auth, and
schema tags, including when Jev or an explicit `--budget` says low. Jev is not
a permission grant. An explicit `--model` still wins.

## `/meta-execute --budget`

Campaign budget is a **ceiling**:

- omitted / `auto` → classify each task; a coherent slice uses its highest member's classification
- `low|medium|high` → no task may exceed that level; a mechanical task may still drop to low

Forward the **resolved** `--budget low|medium|high` to every worker (headless
flag, or the Budget block in `references/execute-dispatch.md` for host-native
spawn). Do not dispatch uncapped.

Review budget follows the review's ambiguity and risk, not its provider or the
implementation budget. Start with a bounded pass and add specialists only for
unresolved risks. A difficult security review can warrant `high`; model family
alone cannot. Resolve reviewer counts and slice bounds through
`references/adaptive-workflow.md`; backend availability and user limits come
from `references/work-ladder.md` and the JSON settings cascade.

Task visibility and focused evidence remain per outcome when one worker owns a
slice. A larger context window does not raise the worker count, budget ceiling,
or permissions. Host async tools and dynamic effort require confirmed support.

## Who classifies

The **conductor** (slash command / host-native `/meta-execute`). Not the
worker. The worker only obeys the cap it was given.

## Flags

All of: `/deep-execute`, `/grok-execute`, `/opus-execute`, `/sonnet-execute`,
`/fable-execute`, `/glm-execute`, `/codex-execute`, `/antigravity-execute`,
`/cursor-execute`, `/auto-execute`, `/meta-execute`.

```
--budget auto|low|medium|high     # default auto
```

Alias: `med` → `medium`.
