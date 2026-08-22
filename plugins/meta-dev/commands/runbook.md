---
name: runbook
description: Campaign runbook orchestrator — sequence N related plans by dependency and farm host-native member conductors through the 6-stage waterfall as one arc, with a live computed dashboard. One level above /meta-dev (single plan); one below the global plans/meta-runbook.md. Verbs new|refresh|execute|chain|add|done|archive.
argument-hint: "[new <dir|plans…> | refresh | execute [--serial] | chain <label> | add <plan> | done <plan> | archive] [prompt]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
model: opus
---

# /runbook

Manage a **campaign runbook** — sequences related plans through the 6-stage waterfall
as one arc. One level above `/meta-dev`; one below `plans/meta-runbook.md`.
**First step:** invoke `meta-dev:runbook-orchestration` for full procedure + gating rules.
**Use for:** feature arcs, launch waves, cross-subsystem migrations. Single plan → `/meta-dev`.

## Verbs

| Verb | What it does | Gated? |
|------|--------------|:------:|
| `new <dir\|paths…>` | Resolve → topo-sort → scaffold → render → register in meta-runbook | no |
| `refresh` / *(bare)* | Boxed campaign status (planctl-backed); `<path>` = that campaign | no |
| `execute` / `go` | Farm READY members as host-native member conductors; parallel where file-disjoint (cap 3) | **YES** |
| `chain <label>` | Successor runbook, daisy-chain | no |
| `add <plan>` | Insert at dependency-correct slot | no |
| `done <plan>` | Mark member done | no |
| `archive` | All done → `status:done`, move Sequence→Shipped, archive | no |

**Progress block:** `planctl runbook render <rb>` (sentinel write, lazy dirty-set).
**Boxed view:** `planctl runbook <path>` (interactive terminal surface).
**Detail:** `references/runbook-view.md` · `workflow-skills/runbook-orchestration/`.

## ⛔ `execute` / `go` — campaign conductor (non-negotiable)

You are the **campaign conductor**. You do **not** implement member tasks on this thread.

`/runbook execute` **is** the campaign go for non-sensitive members. Re-ask only for auth / schema /
payment / cross-repo. `--inline` does not exist. Do not flatten the campaign into a Grok Rhai workflow.

1. `TaskCreate` one entry per member. Keep it live.
2. A member is **READY** when deps are releasable, its declared write-set is disjoint from in-flight
   members, and it is not blocked. Unknown write-set → serialize (do not guess).
3. Dispatch every READY member as a **member conductor** (Host dispatch below). Cap **3** in-flight.
   Fill the next slot the moment a child returns. `--serial` → one member at a time.
4. Each child runs `commands/meta-execute.md` for one execute-ready plan, or `commands/meta-dev.md`
   stages 1–4 if not yet hardened. Nested checkbox workers (cap 8) are **that child's** job.
5. On each return: `TaskUpdate`, `runbook-render.py`, commit the dashboard if it changed, write
   `## Closeout` on the member master (never this runbook), fill the next READY slot.
6. Context watchdog every 3 completed members: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/context-gauge.py`.
   `CONTEXT_VERDICT=OVER` → `/meta-compact` forward.
7. Unrelated dirty files: commit discrete, keep moving. Never stash. Overlap with an in-flight child → wait.

### Host dispatch

Always host-native. Shape the brief (`references/execute-briefs.md` → Campaign member conductor).

| This host | Member conductor | How |
|-----------|------------------|-----|
| **Grok Build** | `spawn_subagent` | `general-purpose`, inherit model, `background: true`, `capability_mode: all`. **Direct task.** Never "run `/meta-execute`". |
| **Claude Code** | native `Agent` | `Execute /meta-execute <plan>` is legal **here only**. Child follows work-ladder. |
| **Codex** | `codex exec` | Member conductor = sol/high. Direct + inline the procedure. |

**Grok and Codex: do not send a slash command.** They cannot run it. Point them at the command file.

Git in every brief: no rebase / stash / `add -A` / `commit -a` / bare commit.
`git -C <ABS> add -- <paths> && git -C <ABS> commit --only -m "…" -- <paths>`. Never push. Commit-on-red.

Child return: `STATE: DONE|BLOCKED|RED` · `PLAN:` · `STAGE:` · `SHA:` · `SURPRISES:`.

`--glm` on a member: never two GLM member conductors. Forward `--review` / `--budget` when passed.

A member `TASK_RED` parks that member and its dependents. Independent READY members continue.
