# Work Ladder — the ONE source of truth

> **Last verified:** 2026-08-20

Which backends may be **auto-selected** for delegated work, and when to stay
**native** instead. Every command, skill, and reference that talks about
delegation order links here — never restates it.

**Binding doctrine (also `CLAUDE.md` → Delegation Discipline):**

- **Pooled worker = Grok only.** Every subagent is a Grok worker.
- **Use Grok subagents liberally** — fan-out, swarms, whenever the work is more
  than a few tool calls.
- **Claude Pro is the conductor, not a farm.** Do not spawn Claude headless
  workers unless Phong names that backend this turn.
- **Codex is out.** No subscription. Do not auto-select Codex.

## Pool is Grok — do not fall through config

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/config-get.sh" meta_dev.ladder.pool
```

**Auto-select `grok` only.** If this key still returns `deep` / `codex` / anything
else, those rungs are **parked** — ignore them for automatic selection. Doctrine
here wins over a stale config value.

Plugin `templates/settings.json` may still ship `["deep","grok","codex"]`. That
is not permission to dispatch DeepSeek or Codex. To make `config-get` match
doctrine, set the **project** layer:

```json
"ladder": { "pool": ["grok"], "native_only_when_required": true }
```

in `plans/_dashboard/settings.json`. Do **not** edit the shipped default in
`templates/settings.json`.

`meta_dev.ladder.native_only_when_required` (default `true`) says delegation is
the default posture. See **Stay native only when** below.

**Explicit flags always win — and they are parked by default.** `--deep` /
`--glm` / `--codex` / `--sonnet` / `--opus` / `--fable` force that backend
**only when Phong named it this turn**. `--grok` is the pooled default. Fable
stays EXPRESS-PERMISSION even when named.

## Host override — Grok is the only subagent

> **When the conductor host is Claude Code (Claude Pro), the default processing
> worker is Grok (`/grok-execute` / `--grok` / Grok `spawn_subagent`).** The
> conductor holds gates, slash commands, permission, and integration. Grok does
> the processing. Do **not** spawn native Task/Agent Haiku/Sonnet/Opus
> subagents, and do **not** call `/opus-execute` / `/sonnet-execute` /
> `/fable-execute`, unless Phong names that backend this turn.
>
> Mechanical bulk, UI/frontend (no vision on this thread), harden, review, and
> multi-file work all go to Grok. Vision, slash harness, true one-liners, and
> phase-gate judgment stay on the conductor.

**Grok Build host:** same rule. Doctrine also auto-loads from
`.grok/rules/host-behavior.md`.

## Route by task shape

| Task shape | Backend | Why |
|---|---|---|
| Almost all delegated work: mechanical edits, multi-file investigation, diagnosis, implementation (with go), plan drafting, gap scans, harden, review, UI without vision on this thread, parallel tracks | **Grok** (`--grok` / `/grok-execute` / Grok `spawn_subagent`) | **The only pooled worker.** Spend it. Fan out freely. |
| DeepSeek, Codex (any tier), GLM, Claude headless (Sonnet/Opus/Fable), native Claude Task/Agent | **Parked** | Dispatch **only** when Phong names that backend this turn. Fable stays EXPRESS-PERMISSION even then. |

**Cost is never a reason to skip Grok, and an old ladder is never a reason to
call Codex or DeepSeek.** Under Claude Code, **reach for Grok before doing
multi-step work on the main thread**.

Reviewers are a Grok `meta-dev:review-agent` (named reviewer, not self-review).
Cross-family Codex/DeepSeek review is parked with those backends.

## Stay native only when

Native means the **conductor thread** — not a Claude Task/Agent subagent, not
`/opus-execute`. Stay on the conductor when the task:

- **needs our harness** — it must run a meta-dev slash command or a project skill internally (a Grok worker cannot run `/meta-*`);
- **needs vision** — screenshots, design review, image comparison (external backends are text+tools only);
- **needs tight interactive back-and-forth** with Phong;
- **is a one-liner** — a single known-file lookup or edit, where dispatch overhead exceeds the work;
- **is conductor judgment** — Rule #1 permission, waterfall stage gates, integrating worker returns, final synthesis Phong reads;
- **is verification of your own work** — own loop, never a subagent.

Otherwise, **default to Grok** and use subagents liberally. Independent tracks
may run in parallel. Liberal fan-out overrides "prefer one subagent over several."

## Foreign harnesses: give them tasks, never commands

`--deep`, `--glm`, `--sonnet`, `--opus`, and `--fable` spawn a full **Claude Code**
instance on another model's endpoint. **Do not use them unless Phong named that
backend this turn.** Claude Pro quota is the interactive session, not a farm.

**Grok cannot run Claude slash commands.** It is its own agent with its own tool
surface — no `/meta-execute` or `/loop-gap`. Give it a direct task ("fix the
failing test in Z", "audit X for gap class Y and report findings"), never
"run `/loop-gap` on this plan". Anything needing the Claude command harness
stays with the conductor.

Grok has no PreToolUse hook here, so git bans (rebase/pull/merge, `git stash`,
`git add -A`) reach Grok as **advisory prompt text only**, not enforced
interception. State the git rules in every Grok task spec.

**Codex is out.** No `/codex-execute`. If Phong later names Codex, give it a
direct task the same way — never a bare `/command`.

## Parked backends

These remain wired. They are **never auto-selected**. Dispatch only when Phong
names them this turn:

| Flag / command | Backend |
|---|---|
| `--deep` / `/deep-execute` | DeepSeek |
| `--codex` / `/codex-execute` | Codex (GPT) — **no subscription** |
| `--glm` / `/glm-execute` | GLM 5.2 |
| `--sonnet` / `/sonnet-execute` | Anthropic Sonnet 5 headless |
| `--opus` / `/opus-execute` | Anthropic Opus 5 headless |
| `--fable` / `/fable-execute` | Anthropic Fable 5 headless — EXPRESS-PERMISSION even when named |
| native Task/Agent Haiku/Sonnet/Opus | Claude Pro farm — banned unless named |

To restore a parked backend to automatic selection, Phong must say so, then add
it to `meta_dev.ladder.pool` in `plans/_dashboard/settings.json`.

## Adding or reordering a backend

Edit `meta_dev.ladder.pool` in the project layer
(`plans/_dashboard/settings.json`) — or the local layer for a machine-only
change. Do **not** edit the shipped default in `templates/settings.json`; that
moves with plugin version bumps. Cascade rules:
`references/config-cascade.md`.

Until that key is `["grok"]`, treat extra rungs as parked anyway.
