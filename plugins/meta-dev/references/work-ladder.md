# Work Ladder — the ONE source of truth

> **Last verified:** 2026-08-30

Which backends may be **auto-selected**, which are **rare**, which are
**named-only**, and when to stay **native**. Every command, skill, and
reference that talks about delegation order **links here** — never restates
the pool.

Task-shape table (effort, lean briefs, Grok 4.5 vs 4.6): project
`.claude/context/harness/subagent-picker.md`. Durable rule: root `AGENTS.md`
→ Delegation. Grok host: `.grok/rules/host-behavior.md`.

**Project override 2026-08-30:** **Grok drives. Codex is used liberally.
Opus / Sonnet are rare (UI craft + extra-family review). DeepSeek credits
are exhausted — never dispatch it.** `ladder.paused` = `["deep"]`.

## Binding doctrine

- **Pooled execute = Grok + Codex.** Auto-select from
  `meta_dev.ladder.pool` (`["grok", "codex"]` on this tree). Pick the
  **cheapest rung that can return a clean Found / Do**.
- **Farm on ordinary turns**, not only `/meta-execute`. Investigations,
  collect, planning, and `/goal` spin children so the parent stays verdicts.
- **Opus and Sonnet are rare.** One pass: UI / design-system craft that
  needs an Anthropic eye, or extra-family review. Do not swarm. Do not farm
  them for grep or mechanical bulk.
- **DeepSeek is dead for now.** Credits are exhausted. Never dispatch
  `/deep-execute`, `--deep`, or a DeepSeek worker — not auto, not by flag,
  not "named this turn." Route that shape to Spark / Luna / grok-4.5. The
  command file stays wired for when credits return.
- **Claude Pro is the conductor, not a farm.** Do not spawn native
  Task/Agent Haiku/Sonnet/Opus subagents for work Grok or Codex should own.

## Pool is Grok then Codex

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/config-get.sh" meta_dev.ladder.pool
# this tree → ["grok", "codex"]
```

Project layer (`plans/_dashboard/settings.json`):

```json
"ladder": { "pool": ["grok", "codex"], "paused": ["deep"], "native_only_when_required": true }
```

`native_only_when_required: true` means delegation is the default posture.
See **Stay native only when** below.

**`--budget auto|low|medium|high`** (default `auto`) is the **depth cap** —
turns, wall clock, no rabbit holes. Classify before dispatch. Campaign
`/meta-execute --budget` is a ceiling. Doctrine: `references/execute-budget.md`.

**Explicit flags:** `--grok` / `--codex` are pooled. `--opus` / `--sonnet`
are **rare** (UI + extra-family review). `--glm` / `--fable` / `--agy` force
that backend **only when Phong named it this turn**. Fable stays
EXPRESS-PERMISSION even when named. **`--deep` does not win.** `ladder.paused`
contains `deep` — do not run it.

## Cost per task — pick the cheapest rung that can do it

Every dispatch names **backend + model/tier + effort**. Do not inherit
xhigh / Sol / Opus because the parent is thinking hard.

| Cost (cheap → dear) | Worker | Effort | Use for |
|---|---|---|---|
| Cheapest Codex code | **Spark** (`gpt-5.3-codex-spark`) | `low` | Mechanical code, rename, boilerplate, bulk lint. Separate weekly quota — spend it. |
| Cheap Codex search | **Luna** | `low` | Filename collect, grep, inventory, prose extract. |
| Cheap Grok collect | **grok-4.5** (`explore` on a Grok host) | `low` (headless `--effort low`) | Same collect shape on Grok credits. `spawn_subagent` has **model, not effort** — pass `grok-4.5`. |
| Ordinary Grok | **grok-4.6** | `high` | Default driver: investigation, implement (with go), most UI. |
| Ordinary Codex | **Terra** | `medium` | Same shape when an OpenAI-family worker is the better fit. |
| Hard Grok | **grok-4.6** | `xhigh` (4.6 only) | Ambiguous root cause, architecture, auth, pipeline. |
| Hard Codex | **Sol** | `high` (`xhigh` only if `high` is not enough) | Same hard shape; extra-family review. |
| Rare Anthropic UI | **Sonnet 5** | review default | Design-system / Svelte craft that needs that eye. One pass. |
| Rare Anthropic hard | **Opus 5** | review default | Extra-family review, hard UI. One pass. Prefer `--readonly` on review. |
| Images | **grok-4.6** | `high` | Worker must see a screenshot / UI / chart. |
| Named-only | DeepSeek Pro/Flash/Vision · GLM · Fable · Antigravity · native Claude Task/Agent | — | Only if Phong names it this turn. Fable = EXPRESS-PERMISSION. |

Do **not** send grep to Sol, Opus, Sonnet, or Grok 4.6 `xhigh`. Do **not**
swarm Opus, Sonnet, or Sol.

**Lean brief.** Collect = 4–8 lines (`TASK` + `RETURN`). Investigation =
INTENT · FILES · RETURN. Write (needs a go) adds git bans + `commit --only`
+ focused Verify. The child already loads `AGENTS.md` — do not paste it.
Detail: `.claude/context/harness/subagent-picker.md`.

## Host override

**Grok Build host:** Grok children first (`spawn_subagent`, pick 4.5 vs
4.6). Codex Luna/Terra/Sol/Spark **liberally** when that family is the
better fit. Doctrine also auto-loads from `.grok/rules/host-behavior.md`.
Do not dispatch DeepSeek.

**Interactive Codex host:** Spark/Luna for collect and mechanical. Terra
ordinary. Sol hard / native Stage-6 review. Grok via `/grok-execute` when
you want that family. Follow `references/workflows/command-adapter.md`.

**Claude Code host:** same pool — `/grok-execute` and `/codex-execute`.
Do not spawn native Task/Agent to "stay local." Extra-family at harden /
code-review: one `/opus-execute` (Sonnet if UI) + one `/codex-execute`.
No DeepSeek.

## Route by task shape

| Task shape | Backend | Why |
|---|---|---|
| Filename collect, grep, inventory | Codex **Luna** or **Spark**, or Grok **4.5** `explore` | Cheapest collect. Lean brief. |
| Mechanical / bulk / bounded edit | Codex **Spark**, or Grok **4.5** | Spark has its own weekly pool. |
| Ordinary investigation, diagnosis, implement (with go) | **Grok 4.6** or Codex **Terra** | Main driver / second family. |
| Hard / architecture / auth / pipeline | **Grok 4.6** `xhigh` or Codex **Sol** | Judgment earns the spend. |
| UI / design-system craft (Anthropic eye) | **Sonnet** or **Opus** — rare, one pass | Not a farm. Most UI stays Grok/Terra. |
| Images the worker must see | **Grok 4.6** | Multimodal. DeepSeek Vision is paused. |
| Harden / code-review extra family | **one `/opus-execute`** (Sonnet if UI) **+ one `/codex-execute` (Sol)** | One pass each. Not a swarm. No DeepSeek. |
| `/deep-execute` | **Never** | Credits exhausted. `ladder.paused` contains `deep`. Route to Spark / Luna / grok-4.5. |
| GLM, `/fable-execute`, `/antigravity-execute`, native Claude Task/Agent | **Named-only** | Dispatch **only** when Phong names that backend this turn. Fable stays EXPRESS-PERMISSION. Antigravity: Gemini 3.7 Flash default; `--opus` is Claude Opus 4.6 on Google quota. |

## Stay native only when

Native means the **conductor thread** — not a child. Stay on the conductor
when the task:

- **needs this thread's slash palette** — the user typed `/meta-*` here;
- **needs tight interactive back-and-forth** with Phong;
- **is a one-liner** — dispatch overhead exceeds the work;
- **is conductor judgment** — Rule #1, stage gates, integrating returns,
  final synthesis Phong reads;
- **is verification of your own work** — own loop, never a subagent;
- **is interactive vision with Phong** — looking at a screenshot together.
  Bounded screenshot review a worker can do alone → Grok 4.6.

Otherwise **farm**. Independent tracks run in parallel (cap 8; typical 1–3).
The parent holds verdicts, not diffs. Shape each brief for that backend
(`references/execute-briefs.md`).

## Who has meta-dev

meta-dev is installed on **all three hosts**: Claude Code, Codex, and Grok
Build. "Cannot run slash commands" is **false** for the interactive hosts.

| Surface | How meta-dev runs |
|---|---|
| **Interactive Claude Code** | Native slash commands (`/meta-execute`, `/loop-gap`, …) |
| **Interactive Grok Build** | Same plugin as Grok skills / slash commands |
| **Interactive Codex** | Native skills (`$meta-dev:meta-execute`, `@meta-dev:meta-execute`) |
| **Headless `/opus-execute` `/sonnet-execute` `/fable-execute` `/glm-execute` `/deep-execute`** | Full **Claude Code** process → can run Claude slash internally. DeepSeek is paused. |
| **Headless `/grok-execute`** | Grok Build (`grok --prompt-file`). Direct task. Never "run `/loop-gap`" as Claude Code. |
| **Headless `/codex-execute`** | `codex exec`. Direct task or `--skill` / `--command`. |
| **Headless `/antigravity-execute`** | Google Antigravity. Direct task. Named-only. |

**Headless brief rule:** Claude-family workers may be told "run `/loop-gap`
on this plan". Grok and Codex headless workers get a **direct task**.

Grok and Codex have no PreToolUse hook here, so git bans reach them as
**advisory prompt text only**. State the git rules in every write brief.
Review passes prefer `--readonly`.

## Parked / paused backends

These remain wired. They are **never auto-selected**.

| Flag / command | Backend | When |
|---|---|---|
| `/deep-execute` | DeepSeek V4 Pro / Flash / Vision | **Credits exhausted. NEVER dispatch.** `ladder.paused` contains `deep`. |
| `--glm` / `/glm-execute` | GLM 5.2 | Named this turn. |
| `--fable` / `/fable-execute` | Anthropic Fable 5 | EXPRESS-PERMISSION even when named. |
| `--agy` / `/antigravity-execute` | Gemini 3.7 Flash (or `--opus` on Google quota) | Named this turn. |
| native Task/Agent Haiku/Sonnet/Opus | Claude Pro farm | Banned unless named. |

`/opus-execute` and `/sonnet-execute` are **rare**, not parked — UI craft
and extra-family review, one pass. `/codex-execute` is **pooled**, not
review-only. `/grok-execute` is **pooled**.

## Adding or reordering a backend

Edit `meta_dev.ladder.pool` in the project layer
(`plans/_dashboard/settings.json`) — or the local layer for a machine-only
change. Cascade: `references/config-cascade.md`.

Keep the execute pool at `["grok", "codex"]` and `paused` at `["deep"]` while
DeepSeek credits are gone. Do not add `opus` or `sonnet` to the pool. Do not
remove `deep` from `paused` until Phong says credits are back.
