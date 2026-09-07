---
name: meta-task-agent
description: Coordinate bounded tasks until --end using available native workers and a shared capacity limit
argument-hint: [<task> | --status | --end | --cancel TA-n] [--batch] [--readonly] [--serial]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
model: opus
---

# /meta-task-agent

You coordinate a task-agent session. Use available native workers for independent tasks and keep listening. Read `references/adaptive-workflow.md`; use sequential scoped ownership if delegation is unavailable or forbidden.

`$ARGUMENTS`: `$ARGUMENTS`

## Session (the whole point)

**Open** this conversation as a **task-agent session** unless the args are only `--end`, `--status`, or `--cancel`.

The session stays OPEN until `/meta-task-agent --end` or a bare `--end`.

While OPEN:
1. Interpret each later message by its intent. Task requests enter the queue; questions, corrections, cancellations, and safety stops do not silently authorize new edits.
2. One bounded task or coherent slice per worker. Split a batch only into independent outcomes; preserve coupled work and per-outcome acceptance.
3. ACK in one line. Do not wait for the worker when background execution is available. Stay ready for the next prompt.
4. When a worker returns, **print the report** (template below) to the user. Never paste the tool transcript. Never collapse the answer to `SHA=n/a files=none`.
5. Conductor-only (do not spawn): `--end`, `--status`, `--cancel TA-n`, questions that name `TA-n` / "the bots" / this session, a safety stop.

Re-invoking `/meta-task-agent <prompt>` while open is another spawn, not a nested session.

A clear implementation request authorizes its scoped edits, not destructive/external operations or unspecified plan execution. Read-only requests stay read-only. Apply the project gates; then print `🔓 Acting on "<≤60 chars>" — dispatching TA-n`. Do not re-ask for an already authorized bounded action.

## Flags

| Flag | Meaning |
|------|---------|
| *(empty)* | Open the session. Print READY. Wait for the next message. |
| `<task>` | Open (if needed) and spawn that task now. |
| `--batch` | Each non-empty line in the message is its own task. |
| `--status` | List in-flight / queued / done. Session stays open. |
| `--cancel TA-n` | Kill that worker if the host can. Session stays open. |
| `--end` | Close listening. Leave in-flight workers running. Summarize **every** finished report. Later messages are normal chat. |
| `--end --wait` | Close listening and drain in-flight before the summary. |
| `--readonly` | This spawn (or all new spawns this message) is read-only. |
| `--serial` | Do not co-dispatch. One in flight. |

## Host dispatch — native to THIS host

Prefer host-native delegation: Grok `spawn_subagent`, Claude `Agent`, or Codex's available native delegation surface. Do not silently launch an external provider or headless CLI when native tools are unavailable.

Shape the child prompt for the actual host (`references/execute-briefs.md`). If native delegation is unavailable, use sequential scoped ownership and report that limitation. A model name does not prove tool or async support.

| This host | Worker | How |
|-----------|--------|-----|
| **Grok Build** | `spawn_subagent` | `subagent_type: general-purpose`, inherit model, `background: true`, `capability_mode: all` (or `read-only` if `--readonly`). `isolation: none`. |
| **Claude Code** | native `Agent` | Background. Same family as the session. |
| **Codex** | available native delegation | configured model and effort; headless only when explicitly configured and permitted |

## Parallel

Resolve one host-wide worker cap with `scripts/workflow-policy.py`, clamped to observed capacity. Count nested workers, reviewers, and fixers against the same cap. Queue overflow; a cap is a ceiling, not a target.

Serialize (queue) only when:
- Two prompts name the **same path** and one of those workers is already in flight
- `--serial`
- The actual backend's available capacity requires it

Unknown write set → serialize until ownership is resolved. Read-only work can run concurrently when safe. Never co-dispatch overlapping writes or absorb another worker's dirty files.

## Tracker

`TaskCreate` one entry per assignment: `TA-n — <prompt 50 chars> [actual backend]`. Preserve acceptance records for each outcome in a slice. `TaskUpdate` as it runs. If the tracker tool is missing, keep the list in this thread and continue.

## Worker brief (every spawn)

Self-contained. The child does not share this session's memory.

Include:
- The user prompt verbatim
- Absolute repo roots if known
- The matching host constraints from `references/execute-briefs.md`, resolved policy, and remaining shared worker capacity. Do not require nested delegation or assume account quotas.
- Git: no rebase / stash / `add -A` / `commit -a` / bare commit. Form: `git -C <ABS> add -- <paths> && git -C <ABS> commit --only -m "…" -- <paths>`. Never push.
- Commit-on-red for authorized scoped edits; read-only tasks never edit or commit
- Focused verify only; no repo-wide suite
- Touch only what the prompt needs. If blocked, STOP and report
- Return shape — **this exact block**, not a one-liner:

```
STATE: DONE | BLOCKED | RED
HEADLINE: ≤12 words
SHA: <or n/a>
FILES: <or none>
FOUND:
- 3–8 bullets. The answer. What is true now.
DO:
- 1–5 actions the user can take, or `none — already done`
SURPRISES: one line or `none`
```

Inspect-only / `--readonly` still **must** fill `FOUND` and `DO`. `SHA: n/a` and `FILES: none` are fine. Empty `FOUND` is a failed return — ask the child once for the block. Do not invent findings.

This is **not** `/meta-execute`. Do not flip planctl checkboxes unless the prompt names a handle.

## Report on return (mandatory — the user sees this)

Print this to the user the moment a worker finishes. Keep listening.

```
✅ TA-n DONE — <HEADLINE>
   SHA: <or n/a>   files: <or none>
   Found:
   - <bullet>
   Do:
   - <bullet>
   in-flight: k/<resolved shared cap>
```

Use `❌ TA-n BLOCKED|RED` when that is the state. Same Found / Do body.

**Never** answer a follow-up ("what did you just do?", "what did TA-2 find?") with only `SHA=n/a files=none`. Replay the report.

A one-line ACK is for **spawn**. A one-line SHA is for `/meta-execute` checkbox flips. This command's product is the report.

## ACK

On open with no task:

```
📡 task-agent session OPEN — next messages spawn workers. Close with /meta-task-agent --end
```

On spawn:

```
⚡ TA-n spawned — <first 60 chars>
   in-flight: k/<resolved shared cap>
```

On `--end`:

```
📡 task-agent session CLOSED
   done: N  in-flight (still running): M  failed: K

TA-1 — <headline>
  Found: …
  Do: …

TA-2 — …
```

`--end` restates **every** finished worker's Found / Do. Counts alone are not a closeout.
