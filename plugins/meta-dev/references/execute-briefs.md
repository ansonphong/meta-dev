# Execution briefs — Grok subagents + per-backend prompts

> **Last verified:** 2026-08-22

Two rules for every execute path (`/meta-execute`, `/grok-execute`,
`/deep-execute`, `/codex-execute`, and the rest):

1. **Farm pieces to Grok subagents.** Do not dump a whole job into one
   context. Keep the parent as a conductor of verdicts.
2. **Shape the prompt for the backend you are sending it to.** The same
   paragraph is not a good brief for Grok, DeepSeek, and Codex.

The runners inject a short backend block automatically
(`scripts/lib/execute-brief.sh`). The **task body** is still the
conductor's job — inline files, acceptance, and git form for *that*
harness. Doctrine for depth caps: `execute-budget.md`.

## Use Grok subagents whenever possible

The scarce resource is **parent context**, not wall-clock.

- Independent pieces (disjoint files, parallel greps, separate verify)
  → **Grok `spawn_subagent`** (or `/grok-execute` from a Claude host).
- The parent keeps one-line returns. It does not re-read diffs.
- A Grok **worker** that gets a multi-piece task does the same: spawn
  children for the pieces; do not chew the whole tree on one thread.
- Do **not** farm those pieces to Opus or Codex. Those plans are
  review-only and quota-tight.
- DeepSeek is for a **small bounded unit**, not a swarm parent.

Stay on the conductor only for the slash palette, interactive Phong,
one-liners, gates, and integrating returns. Everything else is a
subagent.

## Per-backend prompt shape

Do not send a Claude slash to Grok/Codex headless. Do not send a
long-horizon arc to DeepSeek. Do not send "read the plan file" to Codex.

| Backend | Task body | Never |
|---------|-----------|-------|
| **Grok** | Direct task. Absolute paths. Git bans + `commit --only` in the brief (no PreToolUse). Tell it to `spawn_subagent` for independent pieces. | "run `/loop-gap`" as a Claude slash |
| **DeepSeek** | One small unit. Named files. One acceptance. Critical-breakage tests only. | A stateful multi-step phase as one worker; "explore the repo" |
| **Codex** | Direct task. **Inline** the 30–60 lines that matter. `--skill`/`--command` if a procedure applies. JSON handoff. | "read `00-master-plan.md` and reconstruct"; a Claude slash |
| **Opus** | Review brief. `--readonly`. One pass. Findings only. | Implement / farm / loop |
| **Sonnet / Fable / GLM** | Claude Code: slash OK. Still a bounded task. GLM may hold a short stateful phase. | Unrelated refactors |

The injector adds the harness block. You still write the **task** in that
row's voice.

## Injector

Headless runners call `md_brief_wrap_prompt` after the budget wrap.
`BACKEND` must be set (`grok` / `deep` / `codex` / `opus` / `sonnet` /
`fable` / `glm`). Host-native `/meta-execute` fills the Backend brief
slot in `execute-dispatch.md` from the same table.
