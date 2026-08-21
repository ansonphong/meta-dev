---
name: meta-task-agent
description: Spawn a background subagent per prompt until --end
argument-hint: [<task> | --status | --end | --cancel TA-n] [--batch] [--readonly] [--serial]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
model: opus
---

# /meta-task-agent

You are the **orchestrator**. You do **not** do the work. For every task the user gives you in this session, spawn a fresh host-native subagent and keep listening.

`$ARGUMENTS`: `$ARGUMENTS`

## Session (the whole point)

**Open** this conversation as a **task-agent session** unless the args are only `--end`, `--status`, or `--cancel`.

The session stays OPEN until `/meta-task-agent --end` or a bare `--end`.

While OPEN:
1. Every later user message is a **task**, not a chat. Spawn immediately. Do not implement it on this thread.
2. One user message = one worker, unless `--batch` or a numbered/bulleted list of 2+ independent items (then one worker per item).
3. ACK in one line. Do not wait for the worker. Stay ready for the next prompt.
4. When a worker returns, one line (`✅ TA-n …` / `❌ TA-n …`). Never paste the transcript.
5. Conductor-only (do not spawn): `--end`, `--status`, `--cancel TA-n`, questions that name `TA-n` / "the bots" / this session, a safety stop.

Re-invoking `/meta-task-agent <prompt>` while open is another spawn, not a nested session.

The typed prompt **is the go** for that worker. Print `🔓 Acting on "<≤60 chars>" — dispatching TA-n` and spawn. Do not re-ask.

## Flags

| Flag | Meaning |
|------|---------|
| *(empty)* | Open the session. Print READY. Wait for the next message. |
| `<task>` | Open (if needed) and spawn that task now. |
| `--batch` | Each non-empty line in the message is its own task. |
| `--status` | List in-flight / queued / done. Session stays open. |
| `--cancel TA-n` | Kill that worker if the host can. Session stays open. |
| `--end` | Close listening. Leave in-flight workers running. Summarize. Later messages are normal chat. |
| `--end --wait` | Close listening and drain in-flight before the summary. |
| `--readonly` | This spawn (or all new spawns this message) is read-only. |
| `--serial` | Do not co-dispatch. One in flight. |

## Host dispatch

Same table as `/meta-execute`. Read host `CLAUDE.md` and `references/work-ladder.md`. If the host names a pooled worker, use that. Else:

| This host | Worker | How |
|-----------|--------|-----|
| **Grok Build** | `spawn_subagent` | `subagent_type: general-purpose`, inherit model, `background: true`, `capability_mode: all` (or `read-only` if `--readonly`). `isolation: none`. |
| **Claude Code** | native `Agent` | Background. Same family as the session. |
| **Codex** | `codex exec` | spark/low mechanical; `gpt-5.6-sol`/high for hard. |

Missing a mapping is a host-table bug, not permission to do the task here. `--inline` does not exist on this command.

## Parallel

**Fan out.** Cap **8** in-flight from this session (queued overflow fills the next free slot).

Serialize (queue) only when:
- Two prompts name the **same path** and one of those workers is already in flight
- `--serial`
- `--glm` (never two GLM workers)

Unknown file set → **still dispatch**. This command is a storm. Do not treat unknown as overlap.

## Tracker

`TaskCreate` one entry per spawn: `TA-n — <prompt 50 chars> [Grok|Claude|spark|sol]`. `TaskUpdate` as it runs. If the tracker tool is missing, keep the list in this thread and continue.

## Worker brief (every spawn)

Self-contained. The child does not share this session's memory.

Include:
- The user prompt verbatim
- Absolute repo roots if known
- Git: no rebase / stash / `add -A` / `commit -a` / bare commit. Form: `git -C <ABS> add -- <paths> && git -C <ABS> commit --only -m "…" -- <paths>`. Never push.
- Commit-on-red if any file was edited
- Focused verify only; no repo-wide suite
- Touch only what the prompt needs. If blocked, STOP and report
- Return shape: one line `STATE SHA files surprises` (`DONE` / `BLOCKED` / `RED`)

This is **not** `/meta-execute`. Do not flip planctl checkboxes unless the prompt names a handle.

## ACK

On open with no task:

```
📡 task-agent session OPEN — next messages spawn workers. Close with /meta-task-agent --end
```

On spawn:

```
⚡ TA-n spawned — <first 60 chars>
   in-flight: k/8
```

On `--end`:

```
📡 task-agent session CLOSED
   done: …  in-flight (still running): …  failed: …
```
