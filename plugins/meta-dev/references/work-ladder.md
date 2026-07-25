# Work Ladder — the ONE source of truth

> **Last verified:** 2026-07-24

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

## Route by task shape

| Task shape | Backend | Why |
|---|---|---|
| Bounded mechanical edits, renames, boilerplate, scoped searches, lint/format/syntax triage | **DeepSeek** (`--deep`) | Cheapest bulk tier. Fan out freely. |
| Independent frontier reasoning; a wanted *third* model family; hard single-file diagnosis | **Grok** (`--grok`) | xAI-family lens catches what Anthropic- and OpenAI-family review both miss. Budget it like Codex, **not** like DeepSeek — it is not a fan-out farm. |
| Long-horizon stateful execution; multi-file features; the OpenAI-family review lens at phase gates / Stage 6 | **Codex** (`--codex`) | First-class executor *and* cross-family reviewer. Route `spark` tier first — it bills to a separate weekly quota from the shared `gpt-5.6` pool. |

Reviewers are a separate axis: the phase-gate reviewer is always the Opus
`meta-dev:review-agent` subagent regardless of which backend executed. Cross-family
review (Codex, Grok) is an *additional* lens, not a replacement.

## Stay native only when

Native means an `Agent` subagent under Claude Code, or `codex exec` spark
delegation under Codex — no external process. Reach for it when the task:

- **needs our harness** — it must run a meta-dev slash command or a project skill internally;
- **needs vision** — screenshots, design review, image comparison (external backends are text+tools only);
- **needs tight interactive back-and-forth** with the conductor;
- **is a one-liner** — a single known-file lookup or edit, where dispatch overhead exceeds the work.

Otherwise delegate.

## Foreign harnesses: give them tasks, never commands

`--deep`, `--glm`, `--sonnet`, `--opus`, and `--fable` spawn a full **Claude Code**
instance on another model's endpoint, so those workers have our whole harness and
can run our slash commands internally.

**Codex and Grok cannot.** They are their own agents with their own tool surfaces —
no `/meta-execute`, no `/loop-gap`, no project skills. Give them a direct task
("fix the failing test in Z", "audit X for gap class Y and report findings"),
never "run `/loop-gap` on this plan". Anything needing our harness stays with the
conductor or a Claude-harness worker.

Codex and Grok also have **no PreToolUse hook**, so `guard-check.sh` does not
port — the git bans reach them as advisory prompt text only. State the git rules
explicitly in every Codex/Grok task spec.

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
