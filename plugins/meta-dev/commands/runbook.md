---
name: runbook
description: Campaign runbook orchestrator — sequence N related plans by dependency and drive them through the 6-stage waterfall as one arc, with a live computed dashboard. One level above /meta-dev (single plan); one below the global plans/meta-runbook.md. Verbs new|refresh|execute|chain|add|done|archive.
argument-hint: "[new <dir|plans…> | refresh | execute | chain <label> | add <plan> | done <plan> | archive] [prompt]"
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
| `execute` / `go` | Walk members in order; refresh after each; parallel where file-disjoint | **YES** |
| `chain <label>` | Successor runbook, daisy-chain | no |
| `add <plan>` | Insert at dependency-correct slot | no |
| `done <plan>` | Mark member done | no |
| `archive` | All done → `status:done`, move Sequence→Shipped, archive | no |

**Progress block:** `planctl runbook render <rb>` (sentinel write, lazy dirty-set).
**Boxed view:** `planctl runbook <path>` (interactive terminal surface).
**Detail:** `references/runbook-view.md` · `skills/runbook-orchestration/`.
