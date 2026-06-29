---
name: runbook
description: Campaign runbook orchestrator — sequence N related plans by dependency and drive them through the 6-stage waterfall as one arc, with a live computed dashboard. One level above /meta-dev (single plan); one below the global plans/meta-runbook.md. Verbs new|refresh|execute|chain|add|done|archive.
argument-hint: "[new <dir|plans…> | refresh | execute | chain <label> | add <plan> | done <plan> | archive] [prompt]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
model: opus
---

# /runbook

Manage a **campaign runbook** — `_runbook-YYYY-MM-DD.md`, the orchestration manuscript that sequences
multiple related plans and drives them through the waterfall as a single arc. This command is the entry
point; the procedure + doctrine live in the **`meta-dev:runbook-orchestration`** skill (invoke it first).

```
plans/meta-runbook.md          META runbook — global cross-repo ledger (one entry per campaign)
  └─ _runbook-YYYY-MM-DD.md     CAMPAIGN runbook — what /runbook manages
       └─ plan dirs/files        members — each driven by /meta-dev or /meta-execute
```

**Use `/runbook` (not `/meta-dev`) when** the work is a *set* of interdependent plans that must land in
a specific order — a feature arc, launch wave, or cross-subsystem migration. A single plan → `/meta-dev`.

## First step — always

Invoke the `meta-dev:runbook-orchestration` skill. It defines what a runbook is, the frontmatter schema,
the daisy-chain model, META-runbook registration, gates, and the dashboard contract. Then dispatch on
the verb below. **The prompt after the verb is freeform** — interpret it (which plans, what theme, which
side of the launch milestone) per the skill; "manage the runbook according to what the person prompts."

## Verbs

| Verb | What it does | Gated? |
|------|--------------|:------:|
| `new <feature-dir \| plan-paths…>` | Resolve members → topo-sort from their `depends`/`blocks` → scaffold `_runbook-<today>.md` from the template → render dashboard → register marker in `plans/meta-runbook.md`. | no |
| `refresh` / *(bare)* | Re-run `runbook-render.py` to recompute the PROGRESS block from members' live frontmatter + checkboxes. | no |
| `execute` / `go` | Walk `members` in order; per member run `/meta-dev` (unplanned) or `/meta-execute`/`/auto-execute` (execute-ready); refresh after each phase/plan. Serial per repo. | **YES** — per-member "go" |
| `chain <label>` | Create a successor runbook (`predecessor:` = current), mark current `status: done` + set `successor:`. Daisy-chain or break-off. | no |
| `add <plan>` | Insert a plan into `members` at the dependency-correct slot; re-render. | no |
| `done <plan>` | Mark a member `done` (frontmatter is truth); re-render. | no |
| `archive` | All members done → runbook `status: done`, move META-runbook entry Sequence→Shipped, archive per repo convention. Never delete. | no |

## Scripts

- `${CLAUDE_PLUGIN_ROOT}/scripts/runbook-render.py <runbook-file>` — computes the dashboard PROGRESS
  block (reuses `plan-index.py`). Idempotent; writes only the sentineled span.

## Rules

- **Track it.** Stand up a TaskCreate list (one entry per member, `<id> — <what> [<Backend>]`) for any
  `execute` run, mirroring CLAUDE.md's granular-tasklist doctrine; flip each member as it lands.
- **EXECUTE is gated.** `new`/`refresh`/`chain`/`add`/`done`/`archive` are non-gated authoring. `execute`
  writes code → needs Phong's explicit "go" per member; never auto-advance.
- **Delegate.** Authoring the manuscript + topo-sort + wave strategy = Opus. Driving members through
  HARDEN/EXECUTE = DeepSeek→GLM; gate reviews = Codex (review-only). The runbook is the score.
- **The PROGRESS block is computed** — never hand-edit between the `<!-- RUNBOOK:PROGRESS … -->`
  sentinels; author the narrative + CURRENT phase tracker around it.
