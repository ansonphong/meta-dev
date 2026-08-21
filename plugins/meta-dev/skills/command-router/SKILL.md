---
name: command-router
description: "Resolve a legacy meta-dev alias when no exact native command skill matches."
---

# Command Router

Canonical commands are first-class native skills. Use this router only for a
legacy bare alias, an unknown spelling, or a host without the packaged skills.
It never copies a procedure.

## Resolve

1. **Find the catalog.** It is `commands/` two levels up from this file:
   `<plugin-root>/commands/`. Resolve it from this SKILL.md's own path, never
   from a guessed cwd. Sanity-check with `ls <plugin-root>/commands/ | head`.

2. **Map the name.** Strip any leading `/`. Every `meta-<name>` command has a
   bare `<name>` twin that is a pure redirect — **they are one command**. Try
   `<name>.md`, then `meta-<name>.md`. Never deliberate between the pair.
   No match → `ls` the catalog and ask which was meant. Do not improvise a
   procedure for a command that does not exist.

3. **Read and adapt.** Read
   `../../references/workflows/command-adapter.md`, then read the resolved
   command completely and follow both.

**Worked example.** User types `/meta-execute plans/app/00-master-plan.md`.
1. Catalog → `<plugin-root>/commands/`.
2. Name `meta-execute` → try `execute.md` (hit; it is the bare twin, a pure redirect) → the real body is `meta-execute.md`. Read **that**.
3. Read it end to end, then follow it, translating tools as below.

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

`execute`, `task-agent`, `overlord`, `runbook` and `dev` carry conductor duties —
checkbox flips, session-mode spawns, phase-gate review, dashboards. Running one
as a dispatched worker produces state you cannot reliably maintain. If you are a
worker rather than the session driver, say so and ask for a bounded task instead.
