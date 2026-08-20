# Work Ladder — the ONE source of truth

> **Last verified:** 2026-08-20

Which backends may be **auto-selected** for delegated work, which are
**review-only**, and when to stay **native**. Every command, skill, and
reference that talks about delegation order links here — never restates it.

**Binding doctrine (also `CLAUDE.md` → Delegation Discipline):**

- **Pooled worker = Grok only.** Implementation, investigation, mechanical
  bulk, UI without vision, Grok-swarm gap scans. Use Grok subagents
  **liberally** (fan-out, swarms).
- **Claude and Codex are $20 / $30-mo plans.** Quota is small. Do not farm
  them for execute, bulk, or swarms.
- **Cross-family review is what Opus and Codex are for.** At harden and
  code-review gates, fire **one** `/opus-execute` and **one** `/codex-execute`
  (prefer `--readonly`). Not a swarm. Not a loop. Not "also implement this."
- **Claude Pro is the conductor, not a farm.** Do not spawn native Task/Agent
  Haiku/Sonnet/Opus subagents for work Grok should own.

## Pool is Grok

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/config-get.sh" meta_dev.ladder.pool
# → ["grok"]
```

Project layer (`plans/_dashboard/settings.json`):

```json
"ladder": { "pool": ["grok"], "native_only_when_required": true }
```

**Auto-select `grok` only.** Opus and Codex are **not** in the pool — they are
explicit review dispatches. If this key still returns `deep` / extra rungs,
ignore them for automatic selection.

`meta_dev.ladder.native_only_when_required` (default `true`) says delegation is
the default posture. See **Stay native only when** below.

**Explicit flags:** `--grok` is the pooled default. `--opus` / `--codex` (and
`/opus-execute` / `/codex-execute`) are **review-only**. `--deep` / `--glm` /
`--sonnet` / `--fable` force that backend **only when Phong named it this
turn**. Fable stays EXPRESS-PERMISSION even when named.

## Host override — Grok does the work

> **When the conductor host is Claude Code (Claude Pro), the default processing
> worker is Grok (`/grok-execute` / `--grok` / Grok `spawn_subagent`).** The
> conductor holds gates, slash commands, permission, and integration. Grok does
> the processing. Do **not** spawn native Task/Agent subagents to "stay local."
>
> At a **harden** or **code-review** gate, add one `/opus-execute` and one
> `/codex-execute` on the same artifact. That is the whole Claude/Codex budget
> for that gate.

**Grok Build host:** same split. Doctrine also auto-loads from
`.grok/rules/host-behavior.md`.

## Route by task shape

| Task shape | Backend | Why |
|---|---|---|
| Almost all delegated work: mechanical edits, multi-file investigation, diagnosis, implementation (with go), plan drafting, Grok-swarm gap scans, UI without vision, parallel tracks | **Grok** (`--grok` / `/grok-execute` / Grok `spawn_subagent`) | **The only pooled worker.** Spend it. Fan out freely. |
| Stage 4 harden extra-family pass · Stage 6 / phase-gate **code review** | **One `/opus-execute` + one `/codex-execute`** (prefer `--readonly`) | Cross-family lens. $20/30-mo quota — **one pass each per gate**, not a swarm. Grok still does the first named review. |
| DeepSeek, GLM, `/sonnet-execute`, `/fable-execute`, native Claude Task/Agent | **Parked** | Dispatch **only** when Phong names that backend this turn. Fable stays EXPRESS-PERMISSION even then. |

**Cost is never a reason to skip Grok for work, and quota is always a reason
not to execute on Opus or Codex.** Under Claude Code, **reach for Grok before
doing multi-step work on the main thread**.

Do **not** use `/opus-execute` or `/codex-execute` for implementation,
mechanical bulk, brainstorm, design, plan writing, or Stage 5 execute.

## Stay native only when

Native means the **conductor thread** — not a Claude Task/Agent subagent.
Stay on the conductor when the task:

- **needs our harness** — it must run a meta-dev slash command or a project skill internally (a Grok worker cannot run `/meta-*`);
- **needs vision** — screenshots, design review, image comparison (external backends are text+tools only);
- **needs tight interactive back-and-forth** with Phong;
- **is a one-liner** — a single known-file lookup or edit, where dispatch overhead exceeds the work;
- **is conductor judgment** — Rule #1 permission, waterfall stage gates, integrating worker returns, final synthesis Phong reads;
- **is verification of your own work** — own loop, never a subagent.

Otherwise, **default to Grok** and use subagents liberally. Independent tracks
may run in parallel. Liberal fan-out overrides "prefer one subagent over several."
Harden / code-review gates then add the one Opus + one Codex pass.

## Foreign harnesses: give them tasks, never commands

`--opus` / `/opus-execute` spawn a full **Claude Code** instance, so that
worker *can* run our slash commands. Still brief it as a **review**, not a farm.

**Grok and Codex cannot run Claude slash commands.** They are their own agents
— no `/meta-execute` or `/loop-gap`. Give them a direct task ("audit this diff
for gap class Y and report findings"), never "run `/loop-gap` on this plan".
Anything needing the Claude command harness stays with the conductor.

Grok (and Codex) have no PreToolUse hook here, so git bans reach them as
**advisory prompt text only**. State the git rules in every Grok/Codex task
spec. Codex review passes should be `--readonly` so they cannot write.

## Parked backends

These remain wired. They are **never auto-selected**. Dispatch only when Phong
names them this turn:

| Flag / command | Backend |
|---|---|
| `--deep` / `/deep-execute` | DeepSeek |
| `--glm` / `/glm-execute` | GLM 5.2 |
| `--sonnet` / `/sonnet-execute` | Anthropic Sonnet 5 headless |
| `--fable` / `/fable-execute` | Anthropic Fable 5 headless — EXPRESS-PERMISSION even when named |
| native Task/Agent Haiku/Sonnet/Opus | Claude Pro farm — banned unless named |

`/opus-execute` and `/codex-execute` are **review-only**, not parked.

## Adding or reordering a backend

Edit `meta_dev.ladder.pool` in the project layer
(`plans/_dashboard/settings.json`) — or the local layer for a machine-only
change. Do **not** edit the shipped default in `templates/settings.json`; that
moves with plugin version bumps. Cascade rules:
`references/config-cascade.md`.

Keep the execute pool at `["grok"]`. Do not add `opus` or `codex` to the pool
— that would farm the $20/30-mo plans.
