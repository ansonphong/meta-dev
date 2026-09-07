---
name: runbook-orchestration
description: Stand up and drive a campaign runbook — a single orchestration manuscript that sequences multiple related plans by dependency and farms host-native member conductors through the 6-stage waterfall in file-disjoint parallel waves, with a live computed dashboard. Use when coordinating a multi-plan feature arc (not a single plan — that's /meta-dev). Invoked by the /runbook command.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, TaskCreate, TaskUpdate]
---

# Runbook Orchestration Skill

A **campaign runbook** is the orchestration layer **above a single plan**. `/meta-dev` drives ONE
subject through Brainstorm→Design→Plan→Harden→Execute→Review. A runbook drives **N related plans**
through that waterfall in dependency order, with one live dashboard tracking the whole arc.

```
plans/meta-runbook.md          META live ledger (lean Sequence + milestones; keep ~≤150 lines)
plans/meta-runbook-archive.md  Cold Shipped history (not routine context)
  └─ _runbook-YYYY-MM-DD.md     CAMPAIGN runbook — sequences N member plans, drives the waterfall  ← THIS skill
       └─ plan dirs/files        individual plans — each driven by a member conductor following /meta-dev or /meta-execute
            └─ - [ ] tasks         checkboxes (per phase / per task)
```

**When a runbook, not a plan?** When the work is a *set* of interdependent plans that must land in a
specific order (a feature arc, a launch wave, a migration spanning subsystems). One plan → `/meta-dev`.
A trio of plans with a dependency DAG and a shared acceptance story → a runbook.

**What the runbook owns** that nothing else does: the **cross-plan execution order** (topo-sorted from
each member's `depends`/`blocks` frontmatter), the **wave strategy** (which members can run in parallel
by file-footprint disjointness), the **campaign-level gates/invariants**, and a **live computed
progress dashboard** embedded in the file.

**What the runbook does *not* own:** checkbox implementation, per-task commits, inner parallel waves.
Those belong to `commands/meta-execute.md` (and `commands/meta-dev.md` for stages 1–4).
The campaign conductor delegates bounded member ownership when useful and permitted;
otherwise it follows the same canonical procedures sequentially. Read
`references/adaptive-workflow.md` before assigning ownership.

Do **not** flatten a campaign into a host-specific workflow script (Grok Rhai or otherwise). The
`_runbook-*.md` file plus `planctl` is the SSOT on every host.

---

## Lifecycle (the verbs `/runbook` dispatches)

### `new <feature-dir | plan-paths…>` — scaffold a runbook
1. Resolve the member set: a feature dir (e.g. `plans/<area>/<campaign>/`) → its tracked
   master files (`00-master-plan.md`/`00-design.md`/dated masters; never `phase-*.md`), or an explicit
   list of plan paths.
2. Read each member's frontmatter `depends`/`blocks` and **topologically sort** into an execution
   order. Cycles or missing deps → STOP and surface; never guess an order.
3. Detect parallelizable waves: members with **disjoint file footprints** (grep their write-sets) may
   share a wave; any shared file → serialize. Footprint analysis is judgment work — note assumptions.
4. Scaffold `_runbook-<today>.md` in the feature dir from `references/runbook-template.md`: write the
   frontmatter (`type: runbook`, ordered `members:`, `predecessor:` if chaining), the
   ≤3-sentence purpose header, the dashboard sentinels, and the `## DEPENDENCY ORDER` +
   `## GATES & INVARIANTS` contract. Do NOT author PACKAGE / LIVE STATUS / queued-summaries /
   CURRENT phase-tracker / HIGHER CONCEPT sections — the runbook is exactly 3 zones.
5. Run `scripts/runbook-render.py <file>` (shim over `planctl runbook render` — the unified state layer) to fill the computed PROGRESS block.
6. **Register in the META runbook** (see below).

### `(no verb) | status | refresh` — recompute the dashboard
Run `scripts/runbook-render.py <runbook>` (shim over `planctl runbook render`) to refresh the PROGRESS block from members' **live**
frontmatter + checkboxes. Pure read→compute→write-one-span; safe to run anytime. This is the
"dashboard like /meta-dashboard" surface, scoped to the campaign.

### `execute | go` — drive the sequence (EXECUTE-gated)

**You are the campaign conductor.** Preserve campaign dependency ordering while each member
uses the canonical single-plan workflow. Delegation is conditional, not a second permission gate.

`/runbook execute` / `go` **is** the campaign go for every non-sensitive member. Re-ask only for
auth / schema / payment / cross-repo / destructive members (protocol `sensitive`). A runbook never
auto-starts Stage 5 without that go. Design / plan / harden waves are free.

#### 1. Inventory + tracker

Read `members` in order. For each member, record stage, `depends`/`blocks`, and the **declared
write-set** (plan Files / anchors). Recompute waves from live footprints — do not blindly trust the
authored wave list if files moved.

`TaskCreate` one entry per member (`<id> — <why> [actual backend]`) when available;
otherwise keep a concise status list. Keep it live with `TaskUpdate`. Inner per-task
acceptance records belong to each member's canonical execution procedure.

#### 2. Host dispatch — native to THIS host

Use a bounded **member conductor** per READY member when native delegation is available
and permitted. Grok may expose `spawn_subagent`, Claude `Agent`, and Codex native delegation;
observe the actual tools and capacity. Model names do not establish host capabilities.
If delegation is unavailable or prohibited, use sequential scoped ownership with the same
gates and evidence. Do not silently launch a foreign service or assume a headless CLI exists.

Shape direct briefs with `references/execute-briefs.md`. Host syntax is an adapter concern;
Grok/Codex headless workers do not receive Claude slash commands.

#### 3. Safe parallel waves (member grain)

**Parallelize when it is safe. Serialize when it would collide.** Do not walk `members` one-at-a-time
if two READY members can run together.

A member is **READY** when all of these hold:
1. Every `depends` predecessor is releasable at the stage this wave needs (execute wave: predecessor
   Stage 6 DONE, or the authored gate).
2. Its **declared write-set is disjoint** from every member conductor (and fixer) currently in flight
   from this run.
3. It is not blocked / parked / waiting on a `TASK_RED` parent member.
4. Execute wave: member is HARDEN-clean (stage ≥ 4, that stage passed). Else dispatch a stages-1–4
   conductor instead (`commands/meta-dev.md`, halt at 4).

**Dispatch:** resolve the host-wide worker cap through `scripts/workflow-policy.py`, clamped
to observed available capacity. Count member conductors, nested task/slice workers,
reviewers, and fixers against that one shared cap. Never multiply a per-member limit by
the number of members. Allocate each child a remaining slot allowance; if none remains,
it uses sequential ownership. Fill a released slot with the next READY independent member.
Caps are ceilings, not occupancy targets.

**Serialize (do not co-dispatch) when ANY of:**
- Declared write-sets overlap (same path in two members).
- `--serial`.
- Observed account/host capacity requires serialization.
- Unknown / undeclared write-set — treat as overlapping; do not guess.
- Sensitive member waiting on a fresh human confirm.

An overlapping in-flight owner requires coordination before editing or committing. Leave
unrelated dirty files alone; continue independent work. Never adopt another session's edits,
use tree-wide staging, or stash.

#### 4. Member brief (every spawn)

Self-contained. The child does not share this session's memory.

Include:
- Absolute plan path + absolute repo roots.
- Which procedure to follow, as a **file to read**, not a slash:
  - Execute-ready → read `commands/meta-execute.md` completely and run it for that one plan.
  - Not yet hardened → read `commands/meta-dev.md` and drive stages 1–4 only, then stop.
- Git: no rebase / stash / `add -A` / `commit -a` / bare commit. Form:
  `git -C <ABS> add -- <paths> && git -C <ABS> commit --only -m "…" -- <paths>`. Never push.
- Commit-on-red if any declared file was edited.
- Focused verify only; no repo-wide suite.
- Include resolved task/slice ownership, per-outcome acceptance, and the remaining shared
  worker allowance. Do not require a fresh worker per checkbox or unbounded nested delegation.
- Forward `--review` / `--budget` when the user passed them on `/runbook execute`.
- Return this block:

```
STATE: DONE | BLOCKED | RED
PLAN: <path>
STAGE: <n>
SHA: <or n/a>
SURPRISES: one line or none
```

Claude may use its installed command loader. Grok/Codex headless workers: do not send a slash command; provide the task or procedure file. Never assume plugin installation.

#### 5. Oversight on each return

Do not wait for the whole wave. On every child return:
1. `TaskUpdate` that member.
2. Re-render: `python3 ${PLUGIN_ROOT}/scripts/runbook-render.py <runbook>` (heed stderr
   `⚠ stage-drift`).
3. Commit the dashboard if it changed: `git -C <ABS> add -- <rb> && git -C <ABS> commit --only -m "chore(runbook): refresh dashboard" -- <rb>`.
4. Write member closeout into that member's `00-master-plan.md` `## Closeout` (never the runbook).
5. Fill the next READY slot.
6. At committed member/review seams, use the session-bound context watchdog from
   `workflow-skills/agentic-exec-loop/references/loop-protocol.md` with actual host/session
   identity and known capacity. On `CONTEXT_VERDICT=OVER`, drain active work and preserve a
   forward handoff before the next dispatch. Unknown telemetry is nonblocking.

The completion hook also reconciles dirty campaign runbooks at end of turn. Mid-run render keeps the live
dashboard from freezing on a long arc.

A member `TASK_RED` parks **that member and its dependents**. Independent READY members continue.

#### 6. Campaign review

When the last execute-ready member lands, each member needs a covering closing review
record (`planctl review`) from its canonical execution procedure. Reuse existing evidence
only when it covers the current revision and acceptance scope. If review is missing, obtain
it for that member. Verify declared cross-plan interfaces and integration gates are covered;
add a targeted native integration review only for uncovered interactions.

Cross-family review is opt-in, not mandatory. A dashboard or completion hook cannot prove
that a review occurred. Use `planctl` for state writes and dirty runbook rendering.

### `chain <new-feature/label>` — daisy-chain a successor
When an arc completes (or a new arc breaks off a landed foundation), create a successor
`_runbook-<today>.md` with `predecessor:` = the current runbook, and set the current runbook's
`successor:` through the state door. Mark it done only if required member acceptance and
review gates have passed; a successor does not close unfinished work. The successor's narrative opens "builds on that **landed** foundation"
Use this to (a) keep a finished campaign's record immutable while a new one
starts, or (b) split an over-large runbook into a focused successor.

### `add <plan>` / `done <plan>` / `archive`
- `add` — insert a plan into `members` at the dependency-correct position; re-render.
- `done` — verify required acceptance/review, update the member through `planctl`, and write
  its `## Closeout` in the member master. Re-render; no closeout prose in the runbook.
- `archive` — when ALL members are `done`: mark the runbook `status: done`, drop its META-runbook
  marker + members from live `## Sequence`, append one compact line to `plans/meta-runbook-archive.md`,
  and (per repo convention) move the campaign to `_archive/` if the whole arc is shipped. Never
  delete a runbook; never re-paste closeout novels into live `meta-runbook.md`.

---

## Registration in the META runbook (`plans/meta-runbook.md`)

A campaign registers as a **`=== RUNBOOK: <path> · <label> ===` marker** placed in `## Sequence`
immediately above its member plan entries:

```
=== RUNBOOK: plans/<area>/<campaign>/_runbook-<date>.md · <label> ===
plans/<area>/<campaign>/<member-a>/00-master-plan.md
plans/<area>/<campaign>/<member-b>/00-master-plan.md
…member plans, in runbook order…
```

- The **member plans stay the tracked Sequence units** — the global `/meta-dashboard` counts real
  per-plan progress (the marker line starts with `===`, so `plan-index.py` never mistakes it for a
  plan path).
- The marker is the **pointer + grouping**: it says "these next plans are driven by that campaign
  runbook." Position relative to the `=== MILESTONE: PRODUCT LAUNCH … ===` marker decides pre/post
  launch, same as any plan (the host project contract defines meta-runbook geography).
- Campaign runbook files (`_runbook-*.md`) are themselves **excluded** from the plan scan
  (`plan-index.py` NOISE) — they are orchestration manuscripts, not plans, and carry the campaign
  dashboard in-file.

---

## Gates & invariants (binding)

1. **Order is binding.** `members` order = dependency order, topo-sorted from `depends`/`blocks`.
   READY waves may skip ahead of a blocked sibling; they never skip an unmet `depends`. Never
   reorder without amending the runbook + re-rendering.
2. **EXECUTE is gated.** `/runbook execute` / `go` is the campaign go. Design/plan/harden are free.
   `chain`/`new`/`refresh`/`add`/`done` are non-gated authoring/bookkeeping. Sensitive members still
   re-ask.
3. **The PROGRESS block is computed, not hand-edited.** Author everything else; let
   `runbook-render.py` own the sentineled span. Status truth lives in member frontmatter + checkboxes.
4. **File-level exclusion.** File-disjoint members may run concurrently within one host-wide
   worker cap, including nested work. Unknown or overlapping write sets serialize. Leave
   unrelated dirty files alone. Never tree-wide stage, stash, or multiply concurrency caps.
5. **Daisy chain is immutable backward.** A completed runbook is never rewritten; a successor links to
   it via `predecessor`. The chain is the campaign's history.
6. **Self-maintaining rule.** A runbook has exactly 3 sections: the header (frontmatter + ≤3-sentence
   purpose), the computed `## 🎯 DASHBOARD`, and the `## DEPENDENCY ORDER` + `## GATES & INVARIANTS`
   contract. Never append run history to a runbook. Never hand-author a per-member block. If you'd write
   more than one line about a member, it goes in that member's `00-master-plan.md` `## Closeout`. The
   dashboard is regenerated by `runbook-render.py`, never hand-edited.
7. **Canonical ownership.** A member uses `commands/meta-execute.md` task/slice ownership;
   do not duplicate that loop here. Native delegation is preferred when useful; unavailable
   delegation falls back to sequential ownership with unchanged safety and evidence.

---

## Delegation

Authoring and topology analysis stay on this session. Delegate members only when useful,
available, and permitted. All child work shares the same host-wide cap. The native reviewer
may inspect relevant diffs; no conductor context ban may suppress necessary evidence.

Backend and account preferences come from `references/work-ladder.md` and the settings
cascade. `references/adaptive-workflow.md` controls depth, ownership, and optional external
review; do not duplicate fixed model rankings in campaign procedures.

References: `references/runbook-template.md` (skeleton + frontmatter schema + dashboard contract);
`commands/meta-execute.md` (member execute); `references/execute-briefs.md` (member-conductor brief).
