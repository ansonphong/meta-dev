# Execution briefs — Grok subagents + per-backend prompts

> **Last verified:** 2026-08-30

Pool and cost table: `references/work-ladder.md`. Picker:
project `.claude/context/harness/subagent-picker.md`.

Three rules for every execute path (`/meta-execute`, `/grok-execute`,
`/codex-execute`, `/meta-task-agent`, and the rest):

1. **Farm pieces.** Grok `spawn_subagent` (pick 4.5 vs 4.6) or Codex
   Spark/Luna/Terra/Sol. Do not dump a whole job into one context. Keep
   the parent as a conductor of verdicts — not of transcripts.
2. **Shape the prompt for the backend you are sending it to.** Match brief
   **length** to the job: collect = 4–8 lines. The same paragraph is not a
   good brief for Grok, Codex, and Opus.
3. **When a worker finishes, the user sees the answer.** Distill — do not
   dump logs. Do not collapse an investigation to `SHA=n/a files=none`.
   `/meta-task-agent` prints Found/Do on every return. `/meta-execute`
   still uses a one-line SHA for the checkbox flip, plus surprises.

The runners inject a short backend block automatically
(`scripts/lib/execute-brief.sh`). The **task body** is still the
conductor's job — inline files, acceptance, and git form for *that*
harness. Doctrine for depth caps: `execute-budget.md`.

## Use subagents whenever they keep the parent lean

The scarce resource is **parent context**, not wall-clock. **Grok drives.
Codex is used liberally.** DeepSeek is paused.

- Independent pieces (disjoint files, parallel greps, separate verify)
  → Grok `spawn_subagent` (4.5 collect / 4.6 real work) or Codex
  Spark/Luna/Terra/Sol. `/meta-task-agent` stays **host-native**.
- The parent does not re-read diffs or tool transcripts.
- Do **not** farm grep to Opus, Sonnet, or Sol. Those are rare / hard rungs.
- Do **not** dispatch `/deep-execute` unless Phong names it this turn.

Stay on the conductor only for the slash palette, interactive Phong,
one-liners, gates, and integrating returns. Everything else is a
subagent. Lean brief: collect = `TASK` + `RETURN`.

## Per-backend prompt shape

Do not send a Claude slash to Grok/Codex headless. Do not send "read the
plan file" to Codex. Do not paste a harness novel into a collect worker.

| Backend | Task body | Never |
|---------|-----------|-------|
| **Grok** | Direct task. Absolute paths. Collect = 4–8 lines. Write briefs add git bans + `commit --only` (no PreToolUse). Pass `grok-4.5` or `grok-4.6`. | "run `/loop-gap`" as a Claude slash |
| **Codex** | Direct task. Collect = `TASK` + `RETURN`. Ordinary: **inline** the 30–60 lines that matter. `--tier spark\|luna\|terra\|sol`. | "read `00-master-plan.md` and reconstruct"; a Claude slash |
| **Opus / Sonnet** | Rare. UI craft or extra-family review. `--readonly` on review. One pass. | Grep / mechanical bulk / swarm / loop |
| **DeepSeek** | **Paused.** Named-only. If named: one small unit, named files, one acceptance. | Auto-select |
| **Fable / GLM** | Named-only. Claude Code: slash OK. Still a bounded task. | Unrelated refactors |
| **Antigravity (`agy`)** | Named-only. Direct task. Gemini 3.7 Flash default. | "run `/loop-gap`"; nested subagents (agy blocks them) |

The injector adds the harness block. You still write the **task** in that
row's voice.

## Campaign member conductor (`/runbook execute`)

The campaign thread does **not** implement checkboxes. It spawns one worker per
READY member. That worker **is** a `/meta-execute` (or `/meta-dev` stages 1–4)
conductor for one plan.

| Host | Member-conductor brief |
|------|------------------------|
| **Grok** | Direct task. Absolute plan path. "Read `<plugin>/commands/meta-execute.md` and run it for this plan. Farm checkboxes with `spawn_subagent`. Git bans + `commit --only`. Return STATE/SHA/SURPRISES." Never "run `/meta-execute`". |
| **Claude** | `Execute /meta-execute <plan>` (or `/meta-dev --to 4` if not hardened). The child follows the work-ladder. |
| **Codex** | Direct task. Inline the execute procedure (or `--skill`). Member conductor = sol/high; inner mechanical checkboxes may be spark. Never "read the master and reconstruct." |

Cap **3** member conductors in flight. Nested checkbox cap 8 is the child's job.

## Injector

Headless runners call `md_brief_wrap_prompt` after the budget wrap.
`BACKEND` must be set (`grok` / `deep` / `codex` / `opus` / `sonnet` /
`fable` / `glm` / `agy`). Host-native `/meta-execute` fills the Backend brief
slot in `execute-dispatch.md` from the same table.
