---
name: meta-dev
description: Six-stage development with native execution, scoped ownership and evidence-backed review
argument-hint: <subject|plan-path> [--from <stage>] [--to <stage>] [--gate all|exec|none] [--research auto|focused|full] [--harden auto|focused|full] [--granularity auto|task|slice] [--codex] [--autonomous]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
---

# /meta-dev

Follow `references/workflows/protocol.md` for the six stage outcomes, authority
and final review. Use the native host's tools and configured model; choose a
working method proportional to the task. Routine work keeps intent, approach,
checks and results in chat. Apply the protocol's plan-file gate before creating
a plan; invoking `/meta-dev` does not itself request a plan file.
Do not turn stages into mandatory specialist-command or skill invocations.

Resolve relevant depth/capacity once through `references/adaptive-workflow.md`.
Reuse existing valid artifacts and evidence. When a plan exists, planctl is the
state write door; record meaningful stage changes with `scripts/stage-emit.sh <plan> <stage>
<in_progress|completed|blocked>`. Dashboard failures do not establish acceptance
or block independent implementation. Without a plan, report progress/results in
chat; do not create a plan for stage bookkeeping. Use an available native tracker without
building another runtime ledger.

Planning-only work defaults to Stage 4. An explicit scoped implementation go
allows implementation and closing review without routine transition prompts.
Respect explicit `--from`/`--to` ceilings and protected human gates. `--gate none`
removes transition prompts, not authority boundaries. `--autonomous` carries
existing authority; it never grants deployment, spending or destructive actions.
For existing mode flag details use `references/dev-modes.md` only when needed.

Implementation uses `references/execute-charter.md`; use
`commands/meta-execute.md` for plan dispatch/acceptance details when needed.
Do not reload the same contract at each stage or implicitly invoke audit,
evaluation, gap-loop, housekeeping or a cross-family review. Required independent
review remains. Report actual artifacts, checks, commits and unresolved gates;
push only under release authority. No ceremonial opening or report card required.
