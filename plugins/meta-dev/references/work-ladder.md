# Work Ladder — the ONE source of truth

> **Last verified:** 2026-08-22

Which backends may be **auto-selected** for delegated work, which are
**review-only**, and when to stay **native**. Every command, skill, and
reference that talks about delegation order links here — never restates it.

DeepSeek command policy (Pro / Flash / Vision flags):
`commands/deep-execute.md`. Do not restate the flag table here.

**Binding doctrine (also `CLAUDE.md` → Delegation Discipline):**

- **Pooled execute = DeepSeek + Grok.** Cheapest first: mechanical and
  bounded units to DeepSeek; multi-step / long-horizon / UI / design-sensitive
  work to Grok. Use both **liberally** (fan-out, swarms) on work they own.
- **Claude and Codex are $20 / $30-mo plans.** Quota is small. Do not farm
  them for execute, bulk, or swarms.
- **Cross-family review is what Opus, Codex, and DeepSeek review passes are
  for.** At harden and code-review gates, fire **one** `/opus-execute`, **one**
  `/codex-execute`, and **one** `/deep-execute --readonly` so Grok work is not
  marked by Grok alone. Not a swarm. Not a loop. Not "also implement this."
- **Claude Pro is the conductor, not a farm.** Do not spawn native Task/Agent
  Haiku/Sonnet/Opus subagents for work DeepSeek or Grok should own.

## Pool is DeepSeek then Grok

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/config-get.sh" meta_dev.ladder.pool
# → ["deep", "grok"]
```

Project layer (`plans/_dashboard/settings.json`):

```json
"ladder": { "pool": ["deep", "grok"], "native_only_when_required": true }
```

**Auto-select `deep` then `grok`.** Opus and Codex are **not** in the pool —
they are explicit review dispatches. If this key still returns `codex` / extra
rungs, ignore them for automatic **execute** selection.

`meta_dev.ladder.native_only_when_required` (default `true`) says delegation is
the default posture. See **Stay native only when** below.

**`--budget auto|low|medium|high`** (default `auto`) is the **depth cap** on
every execute path — turns, wall clock, no rabbit holes. Classify before
dispatch. Campaign `/meta-execute --budget` is a ceiling. Doctrine:
`references/execute-budget.md`.

**Explicit flags:** `--deep` / `--grok` are the pooled rungs. `--opus` /
`--codex` (and `/opus-execute` / `/codex-execute`) are **review-only**.
`--glm` / `--sonnet` / `--fable` force that backend **only when Phong named it
this turn**. Fable stays EXPRESS-PERMISSION even when named.

**DeepSeek tier (from `commands/deep-execute.md`):** unflagged `/deep-execute`
is **Pro** (`deepseek-v4-pro`). Add `--flash` for clearly mechanical
low-reasoning work. Add `--vision` when the worker must Read images
(screenshots, UI, charts). Pro and Flash cannot see images (HTTP 400). Never
Flash-downgrade architecture, review, multi-file design, auth, payment,
schema, or render/pipeline work.

## Host override — DeepSeek and Grok do the work

> **When the conductor host is Claude Code (Claude Pro), the default processing
> workers are DeepSeek (`/deep-execute`) for mechanical / bounded units and
> Grok (`/grok-execute`) for the rest.** The conductor holds gates, slash
> commands, permission, and integration. Do **not** spawn native Task/Agent
> subagents to "stay local."
>
> At a **harden** or **code-review** gate, add one `/opus-execute`, one
> `/codex-execute`, and one `/deep-execute --readonly` on the same artifact.
> That is the whole extra-family budget for that gate. Opus and Codex stay
> one pass each ($20/30-mo). DeepSeek is cheap — still one *review* pass at
> the gate; fan it out freely for **execute**.

**Grok Build host:** same split. Doctrine also auto-loads from
`.grok/rules/host-behavior.md`. Mechanical leaves may still go to
`/deep-execute`; Grok `spawn_subagent` owns the rest.

## Route by task shape

| Task shape | Backend | Why |
|---|---|---|
| Mechanical / bulk / bounded: rename, codemod, find-replace, boilerplate, single-file string edit, disjoint fan-out units, narrow one-file transform | **DeepSeek** (`--deep` / `/deep-execute`; `--flash` if clearly mechanical) | **Pooled cheap rung.** Short, self-contained units. DeepSeek drifts on long arcs — keep each unit small. |
| Screenshots, rendered UI, charts, photos the worker must see | **DeepSeek Vision** (`/deep-execute --vision`) | Only DeepSeek pooled worker that can Read images. Pro/Flash 400. |
| Multi-file investigation, diagnosis, implementation (with go), plan drafting, Grok-swarm gap scans, UI/Svelte, long-horizon / stateful phases, parallel tracks that are not mechanical | **Grok** (`--grok` / `/grok-execute` / Grok `spawn_subagent`) | **Pooled frontier rung.** Spend it. Fan out freely. |
| Stage 4 harden extra-family pass · Stage 6 / phase-gate **code review** | **One `/opus-execute` + one `/codex-execute` + one `/deep-execute --readonly`** | Cross-family lens. Opus/Codex: $20/30-mo — **one pass each per gate**. DeepSeek: one review pass at the same gate (Pro, not Flash). Grok still does the first named review. |
| GLM, `/sonnet-execute`, `/fable-execute`, native Claude Task/Agent | **Parked** | Dispatch **only** when Phong names that backend this turn. Fable stays EXPRESS-PERMISSION even then. |

**Do not use DeepSeek for** (route to Grok): long-horizon multi-phase plan
execution as one worker, tasks where step N must carry context from 1..N-1,
frontend/Svelte work that needs design consistency across many components.
Break it small → DeepSeek; keep it whole → Grok.

**Cost is a reason to pick DeepSeek for mechanical work. Quota is always a
reason not to execute on Opus or Codex.** Under Claude Code, **reach for a
pooled worker before doing multi-step work on the main thread**.

Do **not** use `/opus-execute` or `/codex-execute` for implementation,
mechanical bulk, brainstorm, design, plan writing, or Stage 5 execute.

## Stay native only when

Native means the **conductor thread** — not a Claude Task/Agent subagent.
Stay on the conductor when the task:

- **needs this thread's slash palette** — you are the interactive host and the user typed `/meta-*` here. Do **not** stay native just because "Grok/Codex lack meta-dev" — they have the plugin (see **Who has meta-dev** below);
- **needs tight interactive back-and-forth** with Phong;
- **is a one-liner** — a single known-file lookup or edit, where dispatch overhead exceeds the work;
- **is conductor judgment** — Rule #1 permission, waterfall stage gates, integrating worker returns, final synthesis Phong reads;
- **is verification of your own work** — own loop, never a subagent;
- **is interactive vision with Phong** — looking at a screenshot together. Bounded screenshot/UI review that a worker can do alone → `/deep-execute --vision`.

Otherwise, **default to the pool** (DeepSeek if mechanical/bounded, else Grok)
and use subagents liberally. Independent tracks may run in parallel. Liberal
fan-out overrides "prefer one subagent over several." Harden / code-review
gates then add the one Opus + one Codex + one DeepSeek review pass.

## Who has meta-dev

meta-dev is installed on **all three hosts**: Claude Code, Codex, and Grok
Build. "Cannot run slash commands" is **false** for the interactive hosts.

| Surface | How meta-dev runs |
|---|---|
| **Interactive Claude Code** | Native slash commands (`/meta-execute`, `/loop-gap`, …) |
| **Interactive Grok Build** | Same plugin as Grok skills / slash commands (`/meta-execute`, `/loop-gap`, …) |
| **Interactive Codex** | Native skills (`$meta-dev:meta-execute`, `@meta-dev:meta-execute`) |
| **Headless `/deep-execute` `/opus-execute` `/sonnet-execute` `/fable-execute` `/glm-execute`** | Full **Claude Code** process → **can run Claude slash commands internally** |
| **Headless `/grok-execute`** | Grok Build (`grok --prompt-file`). Loads the same Grok plugins/skills as the TUI. Does **not** run Claude's slash-command engine. Brief a **direct task**, or name a skill / `SKILL.md` to follow. Never "run `/loop-gap`" as if this were Claude Code. |
| **Headless `/codex-execute`** | `codex exec`. Interactive Codex has `$meta-dev:*`. Headless cannot invoke by typing `/foo`, but the plugin **is** there: `--skill` / `--command` hand it the same markdown, and the runner injects a harness preamble. Brief a **direct task** (or `--skill`/`--command`). |

**Headless brief rule:** Claude-family workers may be told "run `/loop-gap` on this plan". Grok and Codex headless workers get a **direct task** (or a skill/command path). That is a Claude-engine vs Grok/Codex-engine split, **not** "those hosts lack meta-dev".

`--opus` / `/opus-execute` and `--deep` / `/deep-execute` spawn Claude Code —
they *can* run slash internally. Still brief Opus as a **review**, not a farm.
Brief DeepSeek as a **bounded task**.

Grok (and Codex) have no PreToolUse hook here, so git bans reach them as
**advisory prompt text only**. State the git rules in every Grok/Codex task
spec. Codex and Opus review passes should be `--readonly` so they cannot write.
DeepSeek review passes at a gate should be `--readonly` too.

## Parked backends

These remain wired. They are **never auto-selected**. Dispatch only when Phong
names them this turn:

| Flag / command | Backend |
|---|---|
| `--glm` / `/glm-execute` | GLM 5.2 |
| `--sonnet` / `/sonnet-execute` | Anthropic Sonnet 5 headless |
| `--fable` / `/fable-execute` | Anthropic Fable 5 headless — EXPRESS-PERMISSION even when named |
| native Task/Agent Haiku/Sonnet/Opus | Claude Pro farm — banned unless named |

`/opus-execute` and `/codex-execute` are **review-only**, not parked.
`/deep-execute` is **pooled**, not parked.

## Adding or reordering a backend

Edit `meta_dev.ladder.pool` in the project layer
(`plans/_dashboard/settings.json`) — or the local layer for a machine-only
change. Do **not** edit the shipped default in `templates/settings.json`; that
moves with plugin version bumps. Cascade rules:
`references/config-cascade.md`.

Keep the execute pool at `["deep", "grok"]`. Do not add `opus` or `codex` to
the pool — that would farm the $20/30-mo plans.
