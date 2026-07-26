---
name: command-router
description: "Run any meta-dev command from a harness that has no commands surface (Codex, Grok). Resolves a command name such as execute, dev, dashboard, ship, runbook, sweep, inbox, auto-execute to its markdown procedure and follows it inline. Use whenever the user asks for /meta-execute, /meta-dev, /ship, /dashboard or any other meta-dev slash command and no such command is available, or when $meta-dev:<name> returns no matches."
allowed-tools: [Read, Bash, Glob, Grep]
---

# command-router — every meta-dev command, from a harness that has none

Claude Code auto-discovers `commands/*.md` as slash commands. **Codex does not** —
the plugin manifest has no `commands` key and Codex has no commands surface, so
`$meta-dev:` autocompletes against the plugin's skills only. `$meta-dev:execute`
returns "no matches" because `execute` is a command, not a skill.

This skill is the bridge. It does **not** copy any procedure — it points at the
one source of truth and follows it in place.

## Resolve

1. **Find the catalog.** It is `commands/` two levels up from this file:
   `<plugin-root>/commands/`. Resolve it from this SKILL.md's own path, never
   from a guessed cwd. Sanity-check with `ls <plugin-root>/commands/ | head`.

2. **Map the name.** Strip any leading `/`. Every `meta-<name>` command has a
   bare `<name>` twin that is a pure redirect — **they are one command**. Try
   `<name>.md`, then `meta-<name>.md`. Never deliberate between the pair.
   No match → `ls` the catalog and ask which was meant. Do not improvise a
   procedure for a command that does not exist.

3. **Read it and follow it inline.** The whole file, before acting. If it
   delegates to another command or a named skill, read that file too.

**Worked example.** User types `/meta-execute plans/app/00-master-plan.md`.
1. Catalog → `<plugin-root>/commands/`.
2. Name `meta-execute` → try `execute.md` (hit; it is the bare twin, a pure redirect) → the real body is `meta-execute.md`. Read **that**.
3. Read it end to end, then follow it, translating tools as below.

## Translate as you read

That markdown is written for Claude Code. In Codex:

- `${CLAUDE_PLUGIN_ROOT}` = the plugin root resolved in step 1.
- You have **no** Read/Grep/Glob/Task tools and **no** slash commands. Read with
  your shell (`rg`/`sed`/`cat`), edit with `apply_patch`.
- Where it says invoke `/foo` or a named skill → **read that file, follow it inline.**
- Where it says dispatch subagents → delegate with
  `codex exec -m gpt-5.3-codex-spark -c model_reasoning_effort=low --sandbox <mode> '<bounded task + acceptance criteria>'`.
  **Pick the sandbox deliberately:** `workspace-write` when the delegate must
  edit files, `read-only` when it only reads and reports back for you to apply.
  A read-only delegate cannot write — handing it a code-writing task fails silently-ish.
  Spark bills to a **separate quota** from gpt-5.6, so bulk mechanical sub-work
  costs the main budget nothing. Prefer this over `spawn_agent`, which has no
  model parameter and silently inherits the parent's expensive model.
- `allowed-tools:` and `model:` in a command's frontmatter are Claude-only. Ignore them.

**First session in a while?** Run
`bash <plugin-root>/scripts/codex-doctor.sh` once. It catches the blocked-network
and stale-plugin-cache failures before they waste a dispatch.

## Laws that still bind you

1. **planctl is the ONLY write door for plan state.** `bash <plugin-root>/scripts/planctl.sh <verb>`.
   Never hand-edit a `- [ ]` checkbox — the index and the markdown will disagree
   and the dashboards will lie. Note exit 1 means *partial* success; parse `flipped`.
2. **Plans live in the project's `plans/` tree; CODE lives in the child repos.** Never cross them.
3. **Report honestly.** A verify command that fails gets said out loud, with output.
   A green claim over a red run is the one unrecoverable error.
4. **Touch only what your task declares.** Task contradicts what is on disk → STOP and report.
5. **The trusted Codex PreToolUse hook is the primary git guard.** It validates
   Bash commands against the shared-worktree policy before execution. The manual
   rules remain defense in depth: stage explicit paths only; never `git stash`,
   `rebase`, `pull`, or `merge` without `--ff-only`.

## Conductor commands are a poor worker target

`execute`, `overlord`, `runbook` and `dev` carry conductor duties — checkbox
flips, phase-gate review, dashboards. Running one as a dispatched worker
produces state you cannot reliably maintain. If you are a worker rather than the
session driver, say so and ask for a bounded task instead.
