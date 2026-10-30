---
name: meta-dev
description: Six-stage development with native execution, scoped ownership and evidence-backed review
argument-hint: <subject|plan-path> [--from <stage>] [--to <stage>] [--gate all|exec|none] [--research auto|focused|full] [--harden auto|focused|full] [--granularity auto|task|slice] [--codex] [--autonomous]
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent, TaskCreate, TaskUpdate]
---

# /meta-dev

Follow `references/workflows/protocol.md` for the six stage outcomes, authority
and final review. Use the native host's tools and configured model; choose a
working method proportional to the task. Follow the protocol's artifact contract:
Stage 1 requires `brainstorm.md` and may add supporting research; Stage 2 requires `design.md` and may add
supporting files; Stage 3 creates `00-master-plan.md` and invokes
`commands/meta-planner.md` when detailed task planning or phases are applicable,
otherwise produces a one-page master plan. Stage 4 edits and hardens all
applicable preceding artifacts, including planner output. Explicit user overrides
apply. Never create a master plan in Stage 1 or Stage 2, even for bookkeeping.
Any stage may save supporting research in the subject directory's `research/`
subfolder; link it from the stage artifact without replacing required files.
Do not turn other stage names into mandatory specialist-command invocations.

Resolve relevant depth/capacity once through `references/adaptive-workflow.md`.
Reuse existing valid artifacts and evidence. When a plan exists, planctl is the
state write door; record meaningful stage changes with `scripts/stage-emit.sh <plan> <stage>
<in_progress|completed|blocked>`. Dashboard failures do not establish acceptance
or block independent implementation. Without a plan, report progress/results in
chat; do not create a plan for stage bookkeeping. Use an available native tracker without
building another runtime ledger.

Brainstorm/Stage 1 requests stop at Stage 1; design/Stage 2 requests stop at
Stage 2. Natural-language limits bind just like `--to`. Other planning-only work
defaults to Stage 4. An explicit scoped implementation go
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
