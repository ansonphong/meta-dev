---
name: runbook-orchestration
description: Stand up and drive a campaign runbook — a single orchestration manuscript that sequences multiple related plans by dependency and walks them through the 6-stage waterfall in serial/parallel waves, with a live computed dashboard. Use when coordinating a multi-plan feature arc (not a single plan — that's /meta-dev). Invoked by the /runbook command.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, TaskCreate, TaskUpdate]
---

# Runbook Orchestration Skill

A **campaign runbook** is the orchestration layer **above a single plan**. `/meta-dev` drives ONE
subject through Brainstorm→Design→Plan→Harden→Execute→Review. A runbook drives **N related plans**
through that waterfall in dependency order, with one live dashboard tracking the whole arc.

```
plans/meta-runbook.md          META runbook — global cross-repo ledger (one entry per campaign)
  └─ _runbook-YYYY-MM-DD.md     CAMPAIGN runbook — sequences N member plans, drives the waterfall  ← THIS skill
       └─ plan dirs/files        individual plans — each driven by /meta-dev or /meta-execute
            └─ - [ ] tasks         checkboxes (per phase / per task)
```

**When a runbook, not a plan?** When the work is a *set* of interdependent plans that must land in a
specific order (a feature arc, a launch wave, a migration spanning subsystems). One plan → `/meta-dev`.
A trio of plans with a dependency DAG and a shared acceptance story → a runbook.

**What the runbook owns** that nothing else does: the **cross-plan execution order** (topo-sorted from
each member's `depends`/`blocks` frontmatter — metadata the dashboard captures but never consumed until
now), the **wave strategy** (which members can run in parallel by file-footprint disjointness), the
**campaign-level gates/invariants**, and a **live computed progress dashboard** embedded in the file.

---

## Lifecycle (the verbs `/runbook` dispatches)

### `new <feature-dir | plan-paths…>` — scaffold a runbook
1. Resolve the member set: a feature dir (e.g. `plans/app/UNIFIED-EDITING-CANVAS/`) → its tracked
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
Walk `members` in order. For each member: if it is not yet planned/hardened, run `/meta-dev <member>`
(full waterfall); if it is HARDEN-clean and execute-ready, run `/meta-execute <member>` (or
`/auto-execute` for phase-by-phase headless). The runbook orchestrates **across** plans; `/meta-execute`
and `/auto-execute` orchestrate **within** a plan (they already walk `00-master-plan + phase-N`). After
each phase/plan lands: **re-run `runbook-render.py`** to refresh the dashboard, **write the
closeout into the member's `00-master-plan.md` `## Closeout` section** (never append to the
runbook), and flip the member's status. **Parallel is fine — the only lock is the file.**
Members honor dependency order (a member consuming another's output waits), but any members whose
write-sets don't overlap may execute concurrently. The single hard rule: **never write a file that
is already dirty on the working tree** — each worker picks up only files that are CLEAN at dispatch
(`git status`), so two can never double-write the same file. (Does not relax the GLM ~3-request API
cap — a separate rate limit, not file safety.)
> **Dashboard auto-syncs during member execution.** `/meta-execute` + `/auto-execute` re-render THIS
> runbook at every phase gate (loop-protocol → "Runbook dashboard sync"), so the LIVE EXECUTION
> DASHBOARD never freezes mid-run. The render's stderr `⚠ stage-drift` flags any member at ~100%
> checkboxes still parked below Stage 6 — advance its `stage:` (truly done) or leave it (awaiting
> review), but never let a handoff claim "done" while the dashboard shows it mid-stage.
> ⛔ EXECUTE STAYS GATED. Every member's code-writing needs Phong's explicit "go" (per CLAUDE.md). A
> runbook never auto-advances execution. Design/plan/harden waves are non-gated — drive them freely.

### `chain <new-feature/label>` — daisy-chain a successor
When an arc completes (or a new arc breaks off a landed foundation), create a successor
`_runbook-<today>.md` with `predecessor:` = the current runbook, and set the current runbook's
`successor:` + `status: done`. The successor's narrative opens "builds on that **landed** foundation"
(the 06-26 → 06-28 pattern). Use this to (a) keep a finished campaign's record immutable while a new one
starts, or (b) split an over-large runbook into a focused successor.

### `add <plan>` / `done <plan>` / `archive`
- `add` — insert a plan into `members` at the dependency-correct position; re-render.
- `done` — flip the member's own frontmatter + write its `## Closeout` into the member's `00-master-plan.md`; re-render. No closeout prose in the runbook.
- `archive` — when ALL members are `done`: mark the runbook `status: done`, move its META-runbook
  entry Sequence→Shipped, and (per repo convention) move the campaign to `_archive/` if the whole arc
  is shipped. Never delete a runbook.

---

## Registration in the META runbook (`plans/meta-runbook.md`)

A campaign registers as a **`=== RUNBOOK: <path> · <label> ===` marker** placed in `## Sequence`
immediately above its member plan entries:

```
=== RUNBOOK: plans/app/UNIFIED-EDITING-CANVAS/_runbook-2026-06-28.md · UEC Toolbar+Provenance arc ===
plans/app/UNIFIED-EDITING-CANVAS/17-REPLAYABLE-PROVENANCE/00-master-plan.md
plans/app/UNIFIED-EDITING-CANVAS/16-TOOLBAR/followup-1/00-design.md
…member plans, in runbook order…
```

- The **member plans stay the tracked Sequence units** — the global `/meta-dashboard` counts real
  per-plan progress (the marker line starts with `===`, so `plan-index.py` never mistakes it for a
  plan path).
- The marker is the **pointer + grouping**: it says "these next plans are driven by that campaign
  runbook." Position relative to the `=== MILESTONE: PRODUCT LAUNCH … ===` marker decides pre/post
  launch, same as any plan (CLAUDE.md → meta-runbook geography).
- Campaign runbook files (`_runbook-*.md`) are themselves **excluded** from the plan scan
  (`plan-index.py` NOISE) — they are orchestration manuscripts, not plans, and carry the campaign
  dashboard in-file.

---

## Gates & invariants (binding)

1. **Order is binding.** `members` order = execution order, topo-sorted from `depends`/`blocks`. Never
   reorder without amending the runbook + re-rendering.
2. **EXECUTE is gated** (CLAUDE.md). Design/plan/harden are free; code-writing per member waits for
   "go". `chain`/`new`/`refresh`/`add`/`done` are non-gated authoring/bookkeeping.
3. **The PROGRESS block is computed, not hand-edited.** Author everything else; let
   `runbook-render.py` own the sentineled span. Status truth lives in member frontmatter + checkboxes.
4. **File-level exclusion, not session-level.** Multiple workers MAY execute this runbook concurrently —
   parallelism is encouraged. The one hard rule: never write a file that is already **dirty** on the
   working tree (that's a peer's in-flight edit). Each worker picks up only files that are CLEAN at
   dispatch, so no two ever collide on the same file — disjoint-footprint members thus run freely in
   parallel. Never a tree-wide `git add` (it sweeps a peer's dirty files); stage explicit paths only.
   (The GLM ~3-request cap is a separate API limit, not this rule.)
5. **Daisy chain is immutable backward.** A completed runbook is never rewritten; a successor links to
   it via `predecessor`. The chain is the campaign's history.
6. **Self-maintaining rule.** A runbook has exactly 3 sections: the header (frontmatter + ≤3-sentence
   purpose), the computed `## 🎯 DASHBOARD`, and the `## DEPENDENCY ORDER` + `## GATES & INVARIANTS`
   contract. Never append run history to a runbook. Never hand-author a per-member block. If you'd write
   more than one line about a member, it goes in that member's `00-master-plan.md` `## Closeout`. The
   dashboard is regenerated by `runbook-render.py`, never hand-edited.

---

## Delegation (per CLAUDE.md ladder)

Authoring a runbook's narrative + topo-sort + wave strategy is campaign-design judgment → **Opus** (the
main thread). Driving members through HARDEN/EXECUTE delegates **DeepSeek → GLM** exactly as `/meta-dev`
does; code review at gates → **Codex** (review-only). The runbook is the conductor's score; the
headless backends play it.

References: `references/runbook-template.md` (skeleton + frontmatter schema + dashboard contract).
