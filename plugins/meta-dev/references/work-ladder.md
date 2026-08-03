# Work Ladder — the ONE source of truth

> **Last verified:** 2026-08-02

Which backends may be **auto-selected** for delegated work, in what order they
**escalate**, and when to stay **native** instead. Every command, skill, and
reference that talks about delegation order links here — never restates it.

## Resolve it, don't hardcode it

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/config-get.sh" meta_dev.ladder.pool
# → ["deep","grok","codex"]
```

`meta_dev.ladder.pool` is ordered **cheapest-first, and that order IS the
escalation order** on a failed phase review: try the next entry after the one
that failed, once. One key, two jobs — routing-by-problem-shape is judgment and
lives in the table below, not in config.

`meta_dev.ladder.native_only_when_required` (default `true`) says delegation is
the default posture. See **Stay native only when** below for what qualifies.

**Explicit flags always win.** `--deep` / `--glm` / `--codex` / `--grok` /
`--sonnet` / `--opus` / `--fable` force their backend and can reach one that is
not pooled. The pool governs *automatic* selection only.

## Host override — Claude Code is Grok-first

> **When the conductor host is Claude Code (Opus / Sonnet / Fable main thread), the
> default processing worker is Grok (`/grok-execute` / `--grok`).** Opus holds
> gates, slash commands, permission, and integration. Grok does most multi-step
> processing most of the time. This is binding project policy (also in
> `CLAUDE.md` → Delegation Discipline), not a suggestion.
>
> Pure mechanical bulk still goes DeepSeek / Codex Spark first. Vision, slash
> harness, true one-liners, and phase-gate judgment stay native. Everything else
> that would burn conductor context → Grok.

## Route by task shape

| Task shape | Backend | Why |
|---|---|---|
| Bounded mechanical edits, renames, boilerplate, scoped searches, lint/format/syntax triage | **DeepSeek** (`--deep`) | Cheapest bulk tier. Default model is **`deepseek-v4-flash`** (Flash-0731); escalate hard reasoning with `--tier pro` → `deepseek-v4-pro`. Fan out freely. |
| The same mechanical shapes, when the work is *code* | **Codex Spark** (`--codex --tier spark`) | Coding-tuned and on a **separate weekly quota we rarely exhaust** — effectively free capacity. Prefer it over `luna` on bulk code; never default bulk to `terra`. |
| **Default multi-step work under Claude Code host**; independent frontier reasoning; gap checks and plan hardening; a wanted *third* model family; hard diagnosis; bounded implementation needing a strong model | **Grok** (`--grok` / `/grok-execute`) | **Claude Code's default processing worker.** xAI-family lens catches what Anthropic- and OpenAI-family review both miss. **Grok Heavy (2026-07-26) = a large compute bucket**, and Grok 4.5 is Opus-4.8-class while running faster than Opus — so **spend it freely**; it is no longer rationed and no longer reserved for the single hardest task. |
| Long-horizon stateful execution; multi-file features; the OpenAI-family review lens at phase gates / Stage 6 | **Codex** (`--codex`) | First-class executor *and* cross-family reviewer. **Route `spark` first** on anything mechanical; use **Terra** (medium) for ordinary execution and **Sol** (high) for plan/harden/review — those share the limited 5.6 pool, so every pass spark absorbs preserves it. |

**Cost is never a reason to skip a backend — task shape is the only one.** DeepSeek,
Codex Spark, and Grok are all abundant capacity we have already paid for; under
Claude Code, **reach for Grok before doing multi-step work on the main Opus
thread**. What must not happen is escalating a cheap pool with a bigger prompt
when the task actually needs frontier judgment — that goes to Grok or `sol`.

Reviewers are a separate axis: the phase-gate reviewer is always the Opus
`meta-dev:review-agent` subagent regardless of which backend executed. Cross-family
review (Codex, Grok) is an *additional* lens, not a replacement.

## Stay native only when

Native means an `Agent` subagent under Claude Code, or Codex-native delegation
under Codex — no external backend. Codex may select its native model: Terra for
execution/lightweight work and Sol for planning, hardening, and review. Reach
for it when the task:

- **needs our harness** — it must run a meta-dev slash command or a project skill internally;
- **needs vision** — screenshots, design review, image comparison (external backends are text+tools only);
- **needs tight interactive back-and-forth** with the conductor;
- **is a one-liner** — a single known-file lookup or edit, where dispatch overhead exceeds the work;
- **is conductor judgment** — Rule #1 permission, waterfall stage gates, integrating worker returns (Claude Code host only).

Otherwise, under **Claude Code host, default to Grok** (`/grok-execute`). Under
other hosts, otherwise delegate per the shape table above.

## Foreign harnesses: give them tasks, never commands

`--deep`, `--glm`, `--sonnet`, `--opus`, and `--fable` spawn a full **Claude Code**
instance on another model's endpoint, so those workers have our whole harness and
can run our slash commands internally.

**Codex and Grok cannot run Claude slash commands.** They are their own agents
with their own tool surfaces — no `/meta-execute` or `/loop-gap`. Give them a
direct task ("fix the failing test in Z", "audit X for gap class Y and report
findings"), never "run `/loop-gap` on this plan". Anything needing the Claude
command harness stays with the conductor or a Claude-harness worker.

Codex does support lifecycle hooks. When the meta-dev plugin is installed and
its hooks are trusted, its Codex adapter bridges the shared guard policy to
Codex tool events. Never use `--dangerously-bypass-hook-trust` in normal work.
State the git rules in direct task specs as defense in depth (and because a
headless invocation can precede hook installation/trust). Grok has no such
adapter here, so its rules remain advisory prompt text.

## GLM: available, not pooled

GLM 5.2 was **retired from the default ladder on 2026-07-24** — it is no longer
part of the working rotation. `/glm-execute` and `--glm` remain fully wired and
supported; GLM is simply never auto-selected. To bring it back, add `"glm"` to
`meta_dev.ladder.pool` in `plans/_dashboard/settings.json`. Nothing else needs
to change.

## Adding or reordering a backend

Edit `meta_dev.ladder.pool` in the project layer
(`plans/_dashboard/settings.json`) — or the local layer for a machine-only
change. Do **not** edit the shipped default in `templates/settings.json`; that
moves with plugin version bumps. Cascade rules:
`references/config-cascade.md`.
